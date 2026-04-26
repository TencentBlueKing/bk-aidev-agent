# -*- coding: utf-8 -*-

import uuid

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentType, PromptRole
from aidev_agent.services.chat import ChatPrompt
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.flow_agent import FlowAgentCompletionAgent
from aidev_agent.services.messages_handler import ConsumerPreemptedError, StreamCancelledError
from aidev_agent.services.pydantic_models import ExecuteKwargs
from blueapps.core.exceptions import ClientBlueException
from django.http.response import StreamingHttpResponse
from rest_framework.views import Response

from aidev_bkplugin.serializers.chat_completion import ChatCompletionRequestSerializer
from aidev_bkplugin.services.agent import (
    build_chat_completion_agent_by_session_code,
    build_chat_completion_agent_by_thread_id_with_chat_history,
    build_session_detail_url,
    execute_agent_with_save,
    get_or_create_session_by_thread_id,
)
from aidev_bkplugin.utils import bkaidev_api_client
from aidev_bkplugin.views.base import IgnoreClientContentNegotiation, PluginViewSet, _FlowAgentLocalClient, logger


class ChatCompletionViewSet(PluginViewSet):
    # 使用自定义内容协商，忽略 Accept 头限制，支持流式响应
    content_negotiation_class = IgnoreClientContentNegotiation

    def create(self, request):
        """
        入参校验与解析统一交给 ChatCompletionRequestSerializer：
         - agent_type ← get_agent_config_info(username, version=execute_kwargs.version)
                          由 serializer 内部读取，**不接受用户输入**；
         - thread_id  ← request.data.thread_id or execute_kwargs.thread_id
                            or str(uuid.uuid4())（仅当 session_code 也为空时兜底）。
        """

        username = self.get_username()
        session_code = ""  # 给异常分支兜底，避免 except 段引用未定义变量
        event_handler = None  # 用于断点续传

        try:
            serializer = ChatCompletionRequestSerializer(
                data=request.data,
                context={"username": username},
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            execute_kwargs: ExecuteKwargs = data["execute_kwargs"]
            session_code = data["session_code"]
            execute_kwargs.session_code = session_code
            _input = data["input"]
            chat_history_raw = data["chat_history"]
            agent_type = data["agent_type"]
            thread_id = data["thread_id"]

            logger.info(f"resolved agent_type={agent_type}, version={execute_kwargs.version}")

            if agent_type == AgentType.FLOW.value:
                # flow agent 的 thread_id → session_code 转换：仅在调用方传了 thread_id
                # 但未传 session_code 时触发；_handle_flow_agent 只接受 session_code。
                if thread_id and not session_code:
                    try:
                        session_code = get_or_create_session_by_thread_id(username, thread_id)
                        execute_kwargs.session_code = session_code
                        logger.info(
                            "[FLOW_AGENT] Resolved session_code from thread_id: thread_id=%s, session_code=%s",
                            thread_id,
                            session_code,
                        )
                    except Exception:
                        logger.exception("[FLOW_AGENT] Failed to resolve session_code from thread_id=%s", thread_id)
                return self._handle_flow_agent(data, session_code, username)

            if thread_id:
                # chat_history 已经过 serializer 校验，元素必含 role/content
                chat_history = [ChatPrompt(role=each["role"], content=each["content"]) for each in chat_history_raw]
                if _input:
                    chat_history.append(ChatPrompt(role="user", content=_input))
                if not chat_history:
                    raise ClientBlueException(message="input or chat_history is required when using thread_id")
                return self._handle_thread_id_mode_with_chat_history(
                    thread_id=thread_id,
                    chat_history=chat_history,
                    username=username,
                    execute_kwargs=execute_kwargs,
                )

            # 走到这里 thread_id 必为空（上面已 return）；由 serializer 中的 uuid 兜底规则可推出
            # session_code 必为真。保留显式校验仅作为不变式被破坏时的防御性兜底。
            if not session_code:
                raise ClientBlueException(message="session_code or thread_id is required")

            agent_instance = build_chat_completion_agent_by_session_code(
                session_code=session_code,
                username=request.user.username,
                version=execute_kwargs.version,
            )
            if _input:
                # 处理 chat_history 为 None 或空列表的情况（如编辑第一条消息时）
                if not agent_instance.chat_history:
                    agent_instance.chat_history = []
                agent_instance.chat_history.append(ChatPrompt(role="user", content=_input))
            elif not agent_instance.chat_history:
                raise ClientBlueException(message="The chat history cannot be empty. Please provide 'input' parameter.")
            # 执行 agent
            if execute_kwargs.stream:
                generator = agent_instance.execute(execute_kwargs)
                # 断点续传：在流式开始/结束时更新会话状态
                if event_handler and all(
                    hasattr(event_handler, m) for m in ["set_streaming_started", "set_streaming_finished"]
                ):
                    event_handler.set_streaming_started()
                    generator = self._wrap_streaming_with_status(
                        generator,
                        event_handler,
                        session_code=session_code,
                        username=username,
                    )
                return self.streaming_response(generator, session_code=session_code)
            else:
                result = agent_instance.execute(execute_kwargs)
                return Response(result)
        except Exception as err:
            logger.exception(f"ChatCompletionViewSet create error: {err}")
            message = getattr(err, "message", str(err))
            if session_code:
                error_message_id = str(uuid.uuid4())
                AGUISessionWriter(
                    session_code=session_code, client=bkaidev_api_client, username=username
                )._create_session_content(
                    message_id=error_message_id,
                    role=PromptRole.ASSISTANT.value,
                    content=message,
                    status="error",
                    builtin_property={
                        "message_id": error_message_id,
                        "error": True,
                    },
                )
            raise ClientBlueException(message=message)

    def _handle_thread_id_mode_with_chat_history(
        self,
        thread_id: str,
        chat_history: list[ChatPrompt],
        username: str,
        execute_kwargs: ExecuteKwargs,
    ):
        """
        通过 thread_id 自动管理会话，使用 chat_history 初始化，自动保存到 session
        """
        agent_instance, session_code = build_chat_completion_agent_by_thread_id_with_chat_history(
            thread_id=thread_id,
            chat_history=chat_history,
            username=username,
            version=execute_kwargs.version,
        )
        execute_kwargs.session_code = session_code
        result = execute_agent_with_save(agent_instance, execute_kwargs, session_code, username)
        if execute_kwargs.stream:
            return self.streaming_response(result, session_code=session_code)
        return Response(result)

    def _handle_flow_agent(self, data: dict, session_code: str, username: str):
        """处理 Flow Agent 请求

        通过 chat_completion 接口复用流式 SSE 机制，轮询 flow agent 任务状态并推送。

        核心流程：
        1. 将 session_code 传给 start 接口启动新任务
        2. 拿到 task_id 后轮询 task_info 接口
        3. 通过 SSE 流式推送轮询结果
        4. 用户点击「停止」→ revoke bkflow 任务（不可恢复）

        :param data: ``ChatCompletionRequestSerializer.validated_data``
        """
        task_id = data["task_id"] or None
        flow_start_params = dict(data["flow_start_params"])
        # serializer 已用 FloatField 校验，此处仅做 None → 默认值 回落
        poll_interval = (
            data["poll_interval"] if data["poll_interval"] is not None else agent_settings.FLOW_AGENT_POLL_INTERVAL
        )
        poll_timeout = (
            data["poll_timeout"] if data["poll_timeout"] is not None else agent_settings.FLOW_AGENT_POLL_TIMEOUT
        )

        logger.info(
            f"[FLOW_AGENT] _handle_flow_agent: session_code={session_code}, username={username}, task_id={task_id}"
        )

        if poll_interval <= 0:
            raise ClientBlueException(message=f"poll_interval must be positive, got {poll_interval}")
        if poll_timeout <= 0:
            raise ClientBlueException(message=f"poll_timeout must be positive, got {poll_timeout}")

        # 关键：确保 session_code 注入到 flow_start_params 中
        # 后端 FlowAgentStart 接口需要 session_code 来从数据库获取 chat_history 和 input，
        # 并将它们作为 ${input} / ${chat_history} constants 传给 bkflow 任务
        if session_code:
            flow_start_params.setdefault("session_code", session_code)

        # 构建 event_handler（如果有 session_code）
        event_handler = None
        if session_code:
            event_handler = AGUISessionWriter(session_code=session_code, client=bkaidev_api_client, username=username)

        # 构建 resource_manager：传入带认证头的 client
        resource_manager = _FlowAgentLocalClient(username=username)

        agent_instance = FlowAgentCompletionAgent(
            resource_manager=resource_manager,
            session_code=session_code or None,
            task_id=task_id,
            flow_start_params=flow_start_params,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
            event_handler=event_handler,
        )

        try:
            generator = agent_instance.execute()
        except Exception as err:
            logger.exception(f"[FLOW_AGENT] execute error: session_code={session_code}, error={err}")
            message = getattr(err, "message", str(err))
            if session_code:
                error_message_id = str(uuid.uuid4())
                AGUISessionWriter(
                    session_code=session_code, client=bkaidev_api_client, username=username
                )._create_session_content(
                    message_id=error_message_id,
                    role=PromptRole.ASSISTANT.value,
                    content=message,
                    status="error",
                    builtin_property={
                        "message_id": error_message_id,
                        "error": True,
                    },
                )
            raise ClientBlueException(message=message)

        logger.info(f"[FLOW_AGENT] Streaming started: session_code={session_code}, task_id={task_id}")
        return self.streaming_response(generator, session_code=session_code)

    def _wrap_streaming_with_status(self, generator, event_handler, session_code: str = "", username: str = ""):
        """包装流式生成器，在结束时更新会话状态为 finished

        如果消费者被新消费者抢占（断点续传场景），不更新 status，
        让新消费者负责管理会话状态。
        如果客户端断开连接（GeneratorExit），也不更新 status，
        因为 agent 可能仍在运行，用户刷新后需要续传。
        """
        _preempted = False
        _client_disconnected = False
        _cancelled = False
        try:
            for chunk in generator:
                yield chunk
        except GeneratorExit:
            _client_disconnected = True
            logger.info(f"[WRAP_STATUS] Client disconnected (GeneratorExit): session_code={session_code}")
            return
        except ConsumerPreemptedError:
            _preempted = True
            logger.info(f"[WRAP_STATUS] ConsumerPreemptedError: session_code={session_code}")
        except StreamCancelledError:
            _cancelled = True
            logger.info(f"[WRAP_STATUS] StreamCancelledError(用户停止生成): session_code={session_code}")
        except Exception:
            logger.exception(f"[WRAP_STATUS] Unexpected exception: session_code={session_code}")
            raise
        finally:
            # 注意：cancel 信号可能在 finally 之前就被清理了，因此需要先检查
            if not _cancelled and session_code:
                from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper

                if GeneratorStreamingHelper.is_cancelled(session_code):
                    _cancelled = True
                    logger.info(f"[WRAP_STATUS] Generator结束后检测到取消标志: session_code={session_code}")
            if not _preempted and not _client_disconnected and not _cancelled:
                logger.info(f"[WRAP_STATUS] 流正常结束, 调用 set_streaming_finished: session_code={session_code}")
                event_handler.set_streaming_finished()

    def streaming_response(self, generator, session_code: str = ""):
        sr = StreamingHttpResponse(generator)
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        sr.headers["content-type"] = "text/event-stream"
        sr.headers["Otel-Trace-Id"] = getattr(self.request._request, "otel_trace_id", "") or ""
        # 注入 session 相关响应标头，便于客户端获取会话信息和跳转链接
        if session_code:
            sr.headers["x-bkaidev-agent-session-code"] = session_code
            session_url = build_session_detail_url(session_code)
            if session_url:
                sr.headers["x-bkaidev-agent-session-url"] = session_url
                logger.debug(f"[streaming_response] 注入响应标头: session_code={session_code}, url={session_url}")
            else:
                logger.warning(f"[streaming_response] 无法构建 session_url: session_code={session_code}")
        return sr
