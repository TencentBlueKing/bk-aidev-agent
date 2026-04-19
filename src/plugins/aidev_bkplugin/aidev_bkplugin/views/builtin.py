# -*- coding: utf-8 -*-

import copy
import json
import uuid
from logging import getLogger

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentType, PromptRole
from aidev_agent.services.chat import ChatPrompt
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.flow_agent import FlowAgentCompletionAgent
from aidev_agent.services.messages_handler import ConsumerPreemptedError, GeneratorStreamingHelper, StreamCancelledError
from aidev_agent.services.messages_handler.constants import TimeoutConfig
from aidev_agent.services.messages_handler.factory import message_handler_factory
from aidev_agent.services.pydantic_models import ExecuteKwargs
from bk_plugin_framework.kit.api import custom_authentication_classes
from bk_plugin_framework.kit.decorators import inject_user_token, login_exempt
from blueapps.core.exceptions import ClientBlueException
from django.conf import settings
from django.http.response import StreamingHttpResponse
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.parsers import FileUploadParser
from rest_framework.request import Request
from rest_framework.status import is_success
from rest_framework.views import APIView, Response
from rest_framework.viewsets import ViewSetMixin

from aidev_bkplugin.constants import AGUI_PROTOCOL_VERSION
from aidev_bkplugin.permissions import AgentPluginPermission
from aidev_bkplugin.serializers.chat_completion import ChatCompletionRequestSerializer
from aidev_bkplugin.services.agent import (
    build_chat_completion_agent_by_session_code,
    build_chat_completion_agent_by_thread_id_with_chat_history,
    build_session_detail_url,
    execute_agent_with_save,
    get_agent_config_info,
    get_agent_version,
    get_or_create_session_by_thread_id,
)
from aidev_bkplugin.utils import bkaidev_api_client, get_flow_agent_client, is_local_dev, set_user_access_token


class IgnoreClientContentNegotiation(DefaultContentNegotiation):
    """
    自定义内容协商类，忽略客户端 Accept 头的限制。
    用于支持流式响应（text/event-stream），避免 406 Not Acceptable 错误。
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        # 直接返回第一个渲染器，忽略客户端 Accept 头
        return (renderers[0], renderers[0].media_type)


logger = getLogger(__name__)
client = bkaidev_api_client


class _FlowAgentLocalClient:
    """
    包装 flow agent start 接口，自动附加用户认证信息
    """

    def __init__(self, username: str):
        self._username = username

    def start_flow_agent(self, **kwargs) -> dict:
        flow_client, auth_headers = get_flow_agent_client(self._username)
        headers = kwargs.pop("headers", {})
        # auth_headers 提供认证信息，调用方传入的 headers 可覆盖
        auth_headers.update(headers)
        kwargs["headers"] = auth_headers
        return flow_client.start_flow_agent(**kwargs)


@method_decorator(login_exempt, name="dispatch")
@method_decorator(inject_user_token, name="dispatch")
class PluginViewSet(ViewSetMixin, APIView):
    permission_classes = [AgentPluginPermission]
    authentication_classes = custom_authentication_classes

    def initialize_request(self, request, *args, **kwargs):
        if request.user:
            setattr(request, "_user", request.user)
        return super().initialize_request(request, *args, **kwargs)

    def get_username(self) -> str:
        """
        获取用户名
        用户名获取逻辑（按优先级）：
        - 用户态接口：优先使用 request.user.username（来自 apigw jwt，经 inject_user_token 注入）
        - 应用态接口：降级到 request.META.get("HTTP_X_BKAIDEV_USER") 获取
        """
        username = self.request.user.username if hasattr(self.request, "user") else ""
        if not username:
            username = self.request.META.get("HTTP_X_BKAIDEV_USER", "")
        if not username:
            logger.warning(
                "[PluginViewSet] 无法获取用户名: request.user=%r, meta=%r",
                getattr(self.request.user, "username", None),
                self.request.META.get("HTTP_X_BKAIDEV_USER"),
            )
            raise ValueError("无法获取用户名，请确保请求已正确鉴权或提供 X-BKAIDEV-USER header")
        return username

    @staticmethod
    def get_bkapi_authorization_info(request: Request) -> str:
        auth_info = {
            "bk_app_code": settings.BK_APP_CODE,
            "bk_app_secret": settings.BK_APP_SECRET,
            settings.USER_TOKEN_KEY_NAME: request.token,
        }
        return json.dumps(auth_info)

    def finalize_response(self, request, response, *args, **kwargs):
        if isinstance(response, StreamingHttpResponse):
            return response
        # 目前仅对 Restful Response 进行处理
        if isinstance(response, Response):
            trace_id = getattr(request, "otel_trace_id", None)
            if is_success(response.status_code):
                response.status_code = status.HTTP_200_OK
                response.data = {
                    "result": True,
                    "data": response.data,
                    "code": "success",
                    "message": "ok",
                    "trace_id": trace_id,
                }
            else:
                response.data = {
                    "result": False,
                    "data": None,
                    "code": f"{response.status_code}",
                    "message": response.data,
                    "trace_id": trace_id,
                }
        return super().finalize_response(request, response, *args, **kwargs)


class ChatSessionViewSet(PluginViewSet):
    session_type: str = "dev" if is_local_dev() else "agent"

    def list(self, request):
        result = client.api.list_chat_session(
            headers={"X-BKAIDEV-USER": request.user.username}, params={"session_type": self.session_type}
        )
        result["data"] = [each for each in result["data"] if each.get("protocol_version") == AGUI_PROTOCOL_VERSION]
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = client.api.batch_delete_chat_session(json=request.data)
        return Response(data=result["data"])

    def create(self, request):
        data = {**request.data, "protocol_version": AGUI_PROTOCOL_VERSION, "session_type": self.session_type}
        result = client.api.create_chat_session(json=data, headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        result = client.api.update_chat_session(path_params={"session_code": pk}, json=request.data)
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        result = client.api.retrieve_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    @action(["POST"], url_path="ai_rename", detail=True)
    def ai_rename(self, request, pk, **kwargs):
        result = client.api.rename_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    @action(
        ["POST"],
        url_path="upload/(?P<file_name>.+)",
        detail=True,
        parser_classes=[FileUploadParser],
    )
    def upload(self, request, pk, file_name, **kwargs):
        if not request.data.get("file", None):
            raise ClientBlueException(message="file is required")
        _data = dict(
            path_params={"session_code": pk, "file_name": file_name},
            data=request.data.get("file", None).read(),
            keep_data=True,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{file_name}"',
            },
        )
        logger.info(f"upload_chat_session_file data: {_data}")
        result = client.api.upload_chat_session_file(
            **_data,
        )
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        result = client.api.destroy_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])


class ChatSessionContentViewSet(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = client.api.create_chat_session_content(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])

    @action(["GET"], url_path="content", detail=False)
    def content(self, request, **kwargs):
        result = client.api.get_chat_session_contents(params=request.query_params)
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        result = client.api.destroy_chat_session_content(path_params={"id": pk})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        result = client.api.update_chat_session_content(path_params={"id": pk}, json=request.data)
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = client.api.batch_delete_chat_session_content(json=request.data)
        return Response(data=result["data"])

    @action(["POST"], url_path="stop", detail=False)
    def stop(self, request):
        username = request.user.username
        session_code = request.data.get("session_code", "")

        # 获取 message_handler 用于清理
        message_handler = message_handler_factory.get()

        # 停止 agent 侧的流式生产者
        if session_code:
            # 1. 发送取消信号（进程内 + 跨进程）
            GeneratorStreamingHelper.cancel(session_code)

            # 2. 等待 SSE 消费者真正退出（收到 CANCELLED_CHUNK 并完成 mark_stopped）
            #    正常情况下几百毫秒内完成，超时则降级为当前行为
            stream_finished = False
            if hasattr(message_handler, "wait_for_consumer_cancelled"):
                try:
                    stream_finished = message_handler.wait_for_consumer_cancelled(
                        session_code,
                        timeout=TimeoutConfig.STOP_WAIT_STREAM_FINISH_TIMEOUT,
                    )
                    if stream_finished:
                        logger.info(f"Stream finished confirmed for session_code={session_code}")
                    else:
                        logger.warning(
                            f"Timeout waiting for stream to finish for session_code={session_code}, "
                            f"proceeding with stop anyway"
                        )
                except Exception as e:
                    logger.exception(f"Error waiting for stream finish: {e}")

            # 3. 如果等待超时（消费者可能已崩溃），兜底标记 stopped
            if not stream_finished and hasattr(message_handler, "mark_stopped"):
                message_handler.mark_stopped(session_code)

            # 4. 清理 cancelled 信号（避免残留）
            if hasattr(message_handler, "clear_cancelled_signal"):
                try:
                    message_handler.clear_cancelled_signal(session_code)
                except Exception as e:
                    logger.exception(f"Error clearing cancelled signal: {e}")

        # 5. 如果是 flow 类型智能体，额外调用 flow agent stop 接口撤销 bkflow 任务（不可恢复）
        #    用户点击「停止」→ revoke（任务变为 REVOKED/FAILED），不可恢复
        if session_code:
            try:
                agent_info = get_agent_config_info(username)
                if agent_info.get("agent_type") == "flow":
                    logger.info(f"Flow agent detected, revoking flow task for session_code={session_code}")
                    flow_client, flow_headers = get_flow_agent_client(username)
                    revoke_result = flow_client.stop_flow_agent_task(
                        session_code=session_code,
                        headers=flow_headers,
                    )
                    logger.info(f"[FLOW_AGENT] revoke 调用成功: session_code={session_code}, result={revoke_result}")
                    # revoke 后更新 session 中的 flow_agent_status 为 failed
                    try:
                        client.api.update_chat_session(
                            path_params={"session_code": session_code},
                            json={"flow_agent_status": "failed"},
                            headers={"X-BKAIDEV-USER": username},
                        )
                    except Exception as e:
                        logger.exception(
                            f"Error updating flow_agent_status after revoke: session_code={session_code}, error={e}"
                        )
            except Exception as e:
                logger.exception(f"Error revoking flow agent task: session_code={session_code}, error={e}")

        result = client.api.stop_chat_session_content(json=request.data, headers={"X-BKAIDEV-USER": username})

        return Response(data=result["data"])


class ChatSessionContentFeedbackViewSet(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = client.api.create_feedback(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])

    @action(["GET"], url_path="reasons", detail=False)
    def reasons(self, request, **kwargs):
        result = client.api.get_feedback_reasons(params=request.query_params)
        return Response(data=result["data"])


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


class AgentInfoViewSet(PluginViewSet):
    @action(detail=False, methods=["GET"], url_path="info", url_name="info")
    def info(self, request):
        agent_info = get_agent_config_info(request.user.username)

        conversation_settings = agent_info.get("conversation_settings", {})
        commands = conversation_settings.get("commands", [])
        if isinstance(commands, list):
            for command in commands:
                if not isinstance(command, dict):
                    continue
                command_id = command.get("id")
                command_agent_code = command.get("agent_code")
                if command_id and command_agent_code and command_id == command_agent_code:
                    command["components"] = []
                if command.get("icon") and is_local_dev():
                    command["icon"] = command["icon"].replace("https://", "http://")

        # 新增群聊信息
        agent_info["chat_group"] = {
            "enabled": settings.CHAT_GROUP_ENABLED,
            "staff": settings.CHAT_GROUP_STAFF,
            "username": request.user.username,
        }
        prompt_setting = agent_info.get("prompt_setting", {})
        prompt_setting["collection_content"] = []
        prompt_setting["collection_variables"] = []
        prompt_setting["content"] = [
            content for content in prompt_setting["content"] if content.get("role") == PromptRole.PAUSE.value
        ]
        agent_info["prompt_setting"] = prompt_setting
        agent_info.pop("otel_info", None)
        return Response(data=agent_info)

    @action(detail=False, methods=["GET"], url_path="ping", url_name="ping")
    def ping(self, request):
        set_user_access_token(request)
        response = Response(data="pong")
        response["Access-Control-Allow-Origin"] = request.headers.get("Origin")
        response["Access-Control-Allow-Credentials"] = "true"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Max-Age"] = "1000"
        response["Access-Control-Allow-Headers"] = "X-Requested-With, Content-Type"
        return response

    @action(detail=False, methods=["GET"], url_path="version", url_name="version")
    def version(self, request, *args, **kwargs):
        """获取所有以 aidev 开头的已安装包及其版本"""
        return Response(data=get_agent_version())


class ChatGroupViewSet(PluginViewSet):
    def create(self, request):
        data = request.data
        username = request.user.username

        data["users"] = copy.deepcopy(settings.CHAT_GROUP_STAFF)
        data["users"].append(username)
        data["chat_group_type"] = settings.CHAT_GROUP_TYPE
        data["username"] = username

        result = client.api.create_chat_group(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])


class ChatSessionShareView(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = client.api.share_chat_session(
            json=request.data,
            headers={"X-BKAIDEV-USER": username},
        )
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        result = client.api.get_shared_chat(
            path_params={"share_token": pk},
        )
        return Response(data=result["data"])
