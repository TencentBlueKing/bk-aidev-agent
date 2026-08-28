# -*- coding: utf-8 -*-

import uuid
from typing import Optional

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentBuildType, AgentType, ChannelType, PromptRole
from aidev_agent.packages.resource_manager import ResourceManagerProtocol
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.messages_handler import ConsumerPreemptedError, StreamCancelledError
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
from blueapps.core.exceptions import ClientBlueException
from django.http.response import StreamingHttpResponse
from rest_framework.views import Response

from aidev_bkplugin.packages.drf.renderers import get_response_trace_id
from aidev_bkplugin.serializers.chat_completion import ChatCompletionRequestSerializer
from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_execution import AgentExecutor
from aidev_bkplugin.services.agent_helpers import AgentHelper
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_bkplugin.views.base import IgnoreClientContentNegotiation, PluginViewSet, logger


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
        # 与 session_code 同理置于 try 外：except 段构造 AGUISessionWriter 时需要 rm
        rm = self.get_resource_manager()
        agent_code = rm.get_agent_code()

        try:
            serializer = ChatCompletionRequestSerializer(
                data=request.data,
                context={"username": username, "agent_code": agent_code, "resource_manager": rm},
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
                session_code = SessionManager(
                    username=username, agent_code=agent_code, resource_manager=rm
                ).get_or_create_by_session_code(
                    session_code,
                    session_name="子智能体调用",
                    is_temporary=session_temporary,
                    channel_type=self.channel_type,
                )

            logger.info(f"resolved agent_type={agent_type}, version={execute_kwargs.version}")

            if agent_type == AgentType.FLOW.value:
                # flow agent 的 thread_id → session_code 转换：仅在调用方传了 thread_id
                # 但未传 session_code 时触发；_handle_flow_agent 只接受 session_code。
                if thread_id and not session_code:
                    try:
                        session_code = SessionManager(
                            username=username, agent_code=agent_code, resource_manager=rm
                        ).get_or_create_by_thread_id(thread_id, channel_type=self.channel_type)
                        execute_kwargs.session_code = session_code
                        logger.info(
                            "[FLOW_AGENT] Resolved session_code from thread_id: thread_id=%s, session_code=%s",
                            thread_id,
                            session_code,
                        )
                    except Exception:
                        logger.exception("[FLOW_AGENT] Failed to resolve session_code from thread_id=%s", thread_id)
                turn_id = self._save_user_input(session_code, username, _input, rm, turn_id)
                if hasattr(execute_kwargs, "turn_id"):
                    execute_kwargs.turn_id = turn_id
                return self._handle_flow_agent(
                    data,
                    session_code,
                    username,
                    turn_id=turn_id,
                    channel_type=self.channel_type,
                    resource_manager=rm,
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
                    resource_manager=rm,
                    model=data.get("model", ""),
                )

            # 走到这里 thread_id 必为空（上面已 return）；由 serializer 中的 uuid 兜底规则可推出
            # session_code 必为真。保留显式校验仅作为不变式被破坏时的防御性兜底。
            if not session_code:
                raise ClientBlueException(message="session_code or thread_id is required")
            # ask_user_question interrupt resume 三态处理的 DB 写入已下沉到 agent 侧
            # ChatCompletionAgent.execute()（提交 1），入口层只产出 turn_id 并透传 _input。
            # 1. resume + input → 用户跳过提问（agent 侧补 tool + cancel interrupt，清空 resume）
            # 2. resume + 无 input → 用户答了题（agent 侧 UPDATE interrupt 为 resolved）
            # 3. 无 resume → 普通新对话（agent 侧补 user 记录）
            turn_id = self._resolve_chat_turn_id(session_code, username, _input, rm, turn_id)
            if hasattr(execute_kwargs, "turn_id"):
                execute_kwargs.turn_id = turn_id
            execute_kwargs.input = _input
            # 模型热更新持久化：model 非空时写回 session.resources.model，使 get session 反映当前模型
            # 写回失败不阻塞 chat 主流程（平台 5xx/网络抖动时仅记录日志）
            model = data.get("model", "")
            if model:
                try:
                    self.client.api.update_chat_session(
                        path_params={"session_code": session_code},
                        json={"model": model},
                        headers={"X-BKAIDEV-USER": username},
                    )
                except Exception:
                    logger.exception(
                        "[chat_completion] 写回 session.resources.model 失败: session_code=%s, model=%s",
                        session_code,
                        model,
                    )

            agent_instance = AgentBuilder(
                username=request.user.username,
                turn_id=turn_id,
                resource_manager=rm,
                agent_code=agent_code,
                model=model,
            ).by_session_code(
                session_code,
                version=execute_kwargs.version,
                channel_type=self.channel_type,
            )
            if not _input and not agent_instance.chat_history:
                raise ClientBlueException(message="The chat history cannot be empty. Please provide 'input' parameter.")
            # 执行 agent
            if execute_kwargs.stream:
                manager = SessionManager(username=username, resource_manager=rm, agent_code=agent_code)
                stream_out = AgentExecutor(manager).execute_with_save(
                    agent_instance,
                    execute_kwargs,
                    session_code,
                    turn_id=turn_id,
                )
                handler = getattr(agent_instance, "event_handler", None)
                if handler and hasattr(handler, "set_streaming_started"):
                    handler.set_streaming_started()
                return self.streaming_response(stream_out, session_code=session_code)
            else:
                manager = SessionManager(username=username, resource_manager=rm, agent_code=agent_code)
                result = AgentExecutor(manager).execute_with_save(
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
                    client=AgentHelper.get_client(resource_manager=rm),
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
        resource_manager: ResourceManagerProtocol,
        model: str = "",
    ):
        """
        通过 thread_id 自动管理会话，使用 chat_history 初始化，自动保存到 session
        """
        agent_code = resource_manager.get_agent_code()
        builder = AgentBuilder(
            username=username,
            turn_id=turn_id,
            resource_manager=resource_manager,
            agent_code=agent_code,
            model=model,
        )
        agent_instance, session_code = builder.by_thread_id_with_chat_history(
            thread_id=thread_id,
            chat_history=chat_history,
            version=execute_kwargs.version,
            channel_type=channel_type,
        )
        # 模型热更新持久化：model 非空时写回 session.resources.model（写回失败不阻塞主流程）
        if model:
            try:
                self.client.api.update_chat_session(
                    path_params={"session_code": session_code},
                    json={"model": model},
                    headers={"X-BKAIDEV-USER": username},
                )
            except Exception:
                logger.exception(
                    "[chat_completion] 写回 session.resources.model 失败: session_code=%s, model=%s",
                    session_code,
                    model,
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

    def _save_user_input(
        self,
        session_code: str,
        username: str,
        content: str,
        resource_manager: Optional[ResourceManagerProtocol] = None,
        turn_id: str = "",
    ) -> str:
        if not session_code or not content:
            return self._resolve_turn_id(session_code, username, resource_manager, turn_id)
        agent_code = resource_manager.get_agent_code() if resource_manager else None
        saved = SessionManager(
            username=username, resource_manager=resource_manager, agent_code=agent_code
        ).save_content(
            session_code=session_code,
            role=PromptRole.USER.value,
            content=content,
            turn_id=turn_id,
        )
        return ((saved.get("property") or {}).get("turn_id") if isinstance(saved, dict) else "") or turn_id

    @staticmethod
    def _resolve_turn_id(
        session_code: str, username: str, resource_manager: Optional[ResourceManagerProtocol] = None, turn_id: str = ""
    ) -> str:
        """用户消息已由 SDK 落库时，从最近一条 user 内容继承 turn_id。"""
        if turn_id:
            return turn_id
        if not session_code:
            return ""
        agent_code = resource_manager.get_agent_code() if resource_manager else None
        contents = SessionManager(
            username, resource_manager=resource_manager, agent_code=agent_code
        ).list_session_contents(session_code)
        for item in reversed(contents):
            if item.get("role") != PromptRole.USER.value:
                continue
            resolved = (item.get("property") or {}).get("turn_id") or ""
            if resolved:
                return resolved
        return ""

    @staticmethod
    def _resolve_chat_turn_id(
        session_code: str,
        username: str,
        _input: str,
        resource_manager: Optional[ResourceManagerProtocol] = None,
        turn_id: str = "",
    ) -> str:
        """产出本轮 user-ai 回复的 turn_id（三分支，必须保序）。

        1. 已有 turn_id → 直接复用
        2. 无输入（答题续流）→ 从最近一条 user 记录继承同轮 turn_id
        3. 否则 → 新生成 uuid4

        注意：本方法只产出 turn_id，不持久化 user 内容（与 ``_save_user_input``
        不同）。user 落库由 agent 侧 ``ChatCompletionAgent.execute()`` 的
        ``UserInputSaved`` 事件负责。
        """
        if turn_id:
            return turn_id
        if not _input:
            return ChatCompletionViewSet._resolve_turn_id(session_code, username, resource_manager, turn_id)
        return uuid.uuid4().hex

    def _handle_flow_agent(
        self,
        data: dict,
        session_code: str,
        username: str,
        *,
        turn_id: str,
        resource_manager: ResourceManagerProtocol,
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
        session_manager = SessionManager(
            username=username, agent_code=resource_manager.get_agent_code(), resource_manager=resource_manager
        )
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
                client=AgentHelper.get_client(resource_manager=resource_manager),
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
            # 通过 **extra 透传给 FlowAgentCompletionAgent.build(ctx)，供 flow start / poll 调用。
            # 必须复用注入的 rm：另建 PluginResourceManager 会丢掉子类自定义的凭证与 agent_code，
            # 使 Flow 路径退回主智能体配置。Flow 用到的接口均已在 ResourceManagerProtocol 声明。
            flow_resource_manager=resource_manager,
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
                    client=AgentHelper.get_client(resource_manager=resource_manager),
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
        if event_handler and hasattr(event_handler, "set_streaming_started"):
            event_handler.set_streaming_started()
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
            if not _cancelled and session_code and GeneratorStreamingHelper.is_cancelled(session_code):
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
        trace_id = get_response_trace_id(self.request._request) or ""
        sr.headers["Otel-Trace-Id"] = trace_id
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
