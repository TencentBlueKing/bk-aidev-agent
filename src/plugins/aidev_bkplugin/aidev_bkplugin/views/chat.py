# -*- coding: utf-8 -*-

import uuid

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentBuildType, AgentType, ChannelType, PromptRole
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.messages_handler import ConsumerPreemptedError, StreamCancelledError
from blueapps.core.exceptions import ClientBlueException
from django.http.response import StreamingHttpResponse
from rest_framework.views import Response

from aidev_bkplugin.serializers.chat_completion import ChatCompletionRequestSerializer
from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_execution import AgentExecutor
from aidev_bkplugin.services.agent_helpers import AgentHelper
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_bkplugin.views.base import IgnoreClientContentNegotiation, PluginResourceManager, PluginViewSet, logger


class ChatCompletionViewSet(PluginViewSet):
    # 使用自定义内容协商，忽略 Accept 头限制，支持流式响应
    content_negotiation_class = IgnoreClientContentNegotiation

    @property
    def channel_type(self):
        """区分用户态调用渠道：
        - 走网关API（API渠道）
        - 走应用域名直连（小鲸弹窗渠道）
        """
        request = getattr(self, "request", None)
        app = getattr(request, "app", None) if request is not None else None
        if app is not None and getattr(app, "verified", False):
            return ChannelType.API.value
        return ChannelType.POPUP.value

    def create(self, request):
        """
        入参校验与解析统一交给 ChatCompletionRequestSerializer：
         - agent_type ← AgentConfigFetcher.get_info(username=, version=execute_kwargs.version)
                          由 serializer 内部读取，**不接受用户输入**；
         - thread_id  ← request.data.thread_id or execute_kwargs.thread_id
                            or str(uuid.uuid4())（仅当 session_code 也为空时兜底）。
        """

        username = self.get_username()
        session_code = ""  # 给异常分支兜底，避免 except 段引用未定义变量
        turn_id = ""  # 由 execute_kwargs 或 _save_user_input / _resolve_turn_id 填充

        try:
            serializer = ChatCompletionRequestSerializer(
                data=request.data,
                context={"username": username},
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            # 获取 execute_kwargs
            execute_kwargs: ExecuteKwargs = data["execute_kwargs"]
            session_code = data["session_code"]
            execute_kwargs.session_code = session_code
            turn_id = execute_kwargs.turn_id or ""
            session_temporary = data.get("session_temporary")
            # 获取输入
            _input = data["input"]
            chat_history_raw = data["chat_history"]
            agent_type = data["agent_type"]
            thread_id = data["thread_id"]
            # persist_input: 当为 True 且 session_code 为空时，自动创建 session
            if execute_kwargs.persist_input and session_code:
                session_code = SessionManager(username=username).get_or_create_by_session_code(
                    session_code, session_name="子智能体调用", is_temporary=session_temporary
                )

            logger.info(f"resolved agent_type={agent_type}, version={execute_kwargs.version}")

            if agent_type == AgentType.FLOW.value:
                # flow agent 的 thread_id → session_code 转换：仅在调用方传了 thread_id
                # 但未传 session_code 时触发；_handle_flow_agent 只接受 session_code。
                if thread_id and not session_code:
                    try:
                        session_code = SessionManager(username=username).get_or_create_by_thread_id(thread_id)
                        execute_kwargs.session_code = session_code
                        logger.info(
                            "[FLOW_AGENT] Resolved session_code from thread_id: thread_id=%s, session_code=%s",
                            thread_id,
                            session_code,
                        )
                    except Exception:
                        logger.exception("[FLOW_AGENT] Failed to resolve session_code from thread_id=%s", thread_id)
                turn_id = self._save_user_input(session_code, username, _input, turn_id)
                if hasattr(execute_kwargs, "turn_id"):
                    execute_kwargs.turn_id = turn_id
                return self._handle_flow_agent(
                    data, session_code, username, turn_id=turn_id, channel_type=self.channel_type
                )

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
                    turn_id=turn_id,
                    channel_type=self.channel_type,
                )

            # 走到这里 thread_id 必为空（上面已 return）；由 serializer 中的 uuid 兜底规则可推出
            # session_code 必为真。保留显式校验仅作为不变式被破坏时的防御性兜底。
            if not session_code:
                raise ClientBlueException(message="session_code or thread_id is required")
            turn_id = self._save_user_input(session_code, username, _input, turn_id)
            if hasattr(execute_kwargs, "turn_id"):
                execute_kwargs.turn_id = turn_id
            agent_instance = AgentBuilder(username=request.user.username, turn_id=turn_id).by_session_code(
                session_code,
                version=execute_kwargs.version,
                channel_type=self.channel_type,
            )
            if not _input and not agent_instance.chat_history:
                raise ClientBlueException(message="The chat history cannot be empty. Please provide 'input' parameter.")
            # 执行 agent
            if execute_kwargs.stream:
                manager = SessionManager(username=username)
                stream_out = AgentExecutor(manager).execute_with_save(
                    agent_instance,
                    execute_kwargs,
                    session_code,
                    turn_id=turn_id,
                )
                handler = getattr(agent_instance, "event_handler", None)
                if handler and all(hasattr(handler, m) for m in ["set_streaming_started", "set_streaming_finished"]):
                    handler.set_streaming_started()
                    stream_out = self._wrap_streaming_with_status(
                        stream_out,
                        handler,
                        session_code=session_code,
                        username=username,
                    )
                return self.streaming_response(stream_out, session_code=session_code)
            else:
                result = AgentExecutor(SessionManager(username=username)).execute_with_save(
                    agent_instance,
                    execute_kwargs,
                    session_code,
                    turn_id=turn_id,
                )
                return Response(result)
        except Exception as err:
            logger.exception(f"ChatCompletionViewSet create error: {err}")
            message = getattr(err, "message", str(err))
            if session_code:
                error_message_id = str(uuid.uuid4())
                AGUISessionWriter(
                    session_code=session_code,
                    client=AgentHelper.get_client(),
                    username=username,
                    turn_id=turn_id,
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
        turn_id: str,
        channel_type: str,
    ):
        """
        通过 thread_id 自动管理会话，使用 chat_history 初始化，自动保存到 session
        """
        builder = AgentBuilder(username=username, turn_id=turn_id)
        agent_instance, session_code = builder.by_thread_id_with_chat_history(
            thread_id=thread_id,
            chat_history=chat_history,
            version=execute_kwargs.version,
            channel_type=channel_type,
        )
        turn_id = builder.turn_id or turn_id
        execute_kwargs.session_code = session_code
        if hasattr(execute_kwargs, "turn_id"):
            execute_kwargs.turn_id = turn_id
        result = AgentExecutor(builder.session_manager).execute_with_save(
            agent_instance,
            execute_kwargs,
            session_code,
            turn_id=turn_id,
        )
        if execute_kwargs.stream:
            return self.streaming_response(result, session_code=session_code)
        return Response(result)

    def _save_user_input(self, session_code: str, username: str, content: str, turn_id: str = "") -> str:
        if not session_code or not content:
            return self._resolve_turn_id(session_code, username, turn_id)
        saved = SessionManager(username=username).save_content(
            session_code=session_code,
            role=PromptRole.USER.value,
            content=content,
            turn_id=turn_id,
        )
        return ((saved.get("property") or {}).get("turn_id") if isinstance(saved, dict) else "") or turn_id

    @staticmethod
    def _resolve_turn_id(session_code: str, username: str, turn_id: str = "") -> str:
        """用户消息已由 SDK 落库时，从最近一条 user 内容继承 turn_id。"""
        if turn_id:
            return turn_id
        if not session_code:
            return ""
        contents = SessionManager(username).list_session_contents(session_code)
        for item in reversed(contents):
            if item.get("role") != PromptRole.USER.value:
                continue
            resolved = (item.get("property") or {}).get("turn_id") or ""
            if resolved:
                return resolved
        return ""

    def _handle_flow_agent(
        self,
        data: dict,
        session_code: str,
        username: str,
        *,
        turn_id: str,
        channel_type: str = "",
    ):
        """处理 Flow Agent 请求

        通过 chat_completion 接口复用流式 SSE 机制，轮询 flow agent 任务状态并推送。

        核心流程：
        1. 将 session_code 传给 start 接口启动新任务
        2. 拿到 task_id 后轮询 task_info 接口
        3. 通过 SSE 流式推送轮询结果
        4. 用户点击「停止」→ revoke bkflow 任务（不可恢复）

        :param data: ``ChatCompletionRequestSerializer.validated_data``
        :param channel_type: 调用渠道，透传给 flow_agent/start/接口
        """
        # 续流判别：节点 retry/skip 成功后 user_operation 会在
        # session.property.flow_info.resume_pending 置位（并记录 resume_action="retry"/"skip"）；
        # 此处读到标记即用 flow_info.task_id 续流轮询，并把 resume_action 透传给
        # FlowAgentCompletionAgent.resume_from_node，触发 flow_agent_restart 和后续
        # flow_agent_update 状态推送；使用后一次性清除标记，否则（无标记）起新 bkflow 任务。
        session_manager = SessionManager(username=username)
        task_id = None
        resume_action: str = ""
        if session_code:
            flow_info = session_manager.get_flow_info(session_code)
            if flow_info.get("resume_pending"):
                resume_task_id = flow_info.get("task_id") or ""
                if resume_task_id:
                    task_id = resume_task_id
                    resume_action = flow_info.get("resume_action") or ""
                    logger.info(
                        "[FLOW_AGENT] resume_pending 命中，续流既有任务: session_code=%s, task_id=%s, action=%s",
                        session_code,
                        task_id,
                        resume_action,
                    )
                else:
                    logger.warning(
                        "[FLOW_AGENT] resume_pending=True 但 flow_info 无 task_id，回落起新任务: session_code=%s",
                        session_code,
                    )
                # 一次性消费标记，避免下一轮新对话被误判为续流（同时清除 resume_action）
                try:
                    session_manager.set_flow_resume_pending(session_code, False)
                except Exception:
                    logger.exception("[FLOW_AGENT] 清除 resume_pending 失败: session_code=%s", session_code)
        flow_start_params = dict(data["flow_start_params"])
        # serializer 已用 FloatField 校验，此处仅做 None → 默认值 回落
        poll_interval = (
            data["poll_interval"] if data["poll_interval"] is not None else agent_settings.FLOW_AGENT_POLL_INTERVAL
        )
        poll_timeout = (
            data["poll_timeout"] if data["poll_timeout"] is not None else agent_settings.FLOW_AGENT_POLL_TIMEOUT
        )

        logger.info(
            f"[FLOW_AGENT] _handle_flow_agent: session_code={session_code}, username={username}, task_id={task_id}, "
            f"channel_type={channel_type}"
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
        # 透传调用渠道，避免后端 create_task 把 popup/rtx 等真实渠道误改为 API
        if channel_type:
            flow_start_params.setdefault("channel_type", channel_type)

        # 构建 event_handler（如果有 session_code）
        event_handler = None
        if session_code:
            event_handler = AGUISessionWriter(
                session_code=session_code,
                client=AgentHelper.get_client(),
                username=username,
                turn_id=turn_id,
                task_id=str(task_id) if task_id else "",
            )

        # FlowAgent 不需要工厂 SESSION 路径的会话上下文清洗（_get_agent_config /
        # _check_agent_switch / get_chat_session_context 等），统一走 DIRECT；
        # session_code 通过工厂 __init__ 透传到 factory.session_code，再由
        # FlowAgentCompletionAgent.build 取用。
        agent_instance = AgentInstanceFactory.build_agent(
            agent_type=AgentType.FLOW,
            build_type=AgentBuildType.DIRECT,
            session_code=session_code or None,
            session_context_data=[],
            event_handler=event_handler,
            username=username,
            # 通过 **extra 透传给 FlowAgentCompletionAgent.build(ctx)；
            # flow_resource_manager 是 flow start 接口专用 client（带特殊认证），与
            # 工厂的 resource_manager（用于会话上下文等通用 API）解耦。
            flow_resource_manager=PluginResourceManager(username=username),
            task_id=task_id,
            flow_start_params=flow_start_params,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
            resume_from_node=resume_action or None,
        )

        try:
            generator = agent_instance.execute()
        except Exception as err:
            logger.exception(f"[FLOW_AGENT] execute error: session_code={session_code}, error={err}")
            message = getattr(err, "message", str(err))
            if session_code:
                error_message_id = str(uuid.uuid4())
                AGUISessionWriter(
                    session_code=session_code,
                    client=AgentHelper.get_client(),
                    username=username,
                    turn_id=turn_id,
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
        _stream_completed = False
        try:
            for chunk in generator:
                yield chunk
            _stream_completed = True
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
            if _stream_completed and not _preempted and not _client_disconnected and not _cancelled:
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
            session_url = AgentHelper.build_session_detail_url(session_code)
            if session_url:
                sr.headers["x-bkaidev-agent-session-url"] = session_url
                logger.debug(f"[streaming_response] 注入响应标头: session_code={session_code}, url={session_url}")
            else:
                logger.warning(f"[streaming_response] 无法构建 session_url: session_code={session_code}")
        return sr
