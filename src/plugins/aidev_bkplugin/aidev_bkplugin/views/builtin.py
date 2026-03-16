# -*- coding: utf-8 -*-

import copy
import json
import uuid
from logging import getLogger

from aidev_agent.enums import PromptRole
from aidev_agent.services.chat import ChatPrompt
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.messages_handler import ConsumerPreemptedError, GeneratorStreamingHelper, StreamCancelledError
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
from aidev_bkplugin.services.agent import (
    build_chat_completion_agent_by_chat_history,
    build_chat_completion_agent_by_session_code,
    build_chat_completion_agent_by_thread_id_with_chat_history,
    build_execute_kwargs,
    execute_agent_with_save,
    get_agent_config_info,
    get_agent_version,
)
from aidev_bkplugin.utils import bkaidev_api_client, set_user_access_token


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


@method_decorator(login_exempt, name="dispatch")
@method_decorator(inject_user_token, name="dispatch")
class PluginViewSet(ViewSetMixin, APIView):
    permission_classes = [AgentPluginPermission]
    authentication_classes = custom_authentication_classes

    def initialize_request(self, request, *args, **kwargs):
        if request.user:
            setattr(request, "_user", request.user)
        return super().initialize_request(request, *args, **kwargs)

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
    def list(self, request):
        result = client.api.list_chat_session(headers={"X-BKAIDEV-USER": request.user.username})
        result["data"] = [each for each in result["data"] if each.get("protocol_version") == AGUI_PROTOCOL_VERSION]
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = client.api.batch_delete_chat_session(json=request.data)
        return Response(data=result["data"])

    def create(self, request):
        data = {**request.data, "protocol_version": AGUI_PROTOCOL_VERSION}
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
        from aidev_agent.services.messages_handler.factory import message_handler_factory

        username = request.user.username
        session_code = request.data.get("session_code", "")

        # 获取 message_handler 用于清理
        message_handler = message_handler_factory.get()

        # 停止 agent 侧的流式生产者
        if session_code:
            GeneratorStreamingHelper.cancel(session_code)

            # 标记 session 已停止，下次进入时只展示已有内容，不启动新生产者
            if hasattr(message_handler, "mark_stopped"):
                message_handler.mark_stopped(session_code)

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
        # 调用Agent 的时候需要传入的相关参数
        username = request.user.username
        execute_kwargs = build_execute_kwargs(request.data.get("execute_kwargs", {}), username)
        session_code = request.data.get("session_code", "")
        execute_kwargs.session_code = request.data.get("session_code", "")

        _input = request.data.get("input", "")
        event_handler = None  # 用于断点续传

        try:
            thread_id = execute_kwargs.thread_id
            if not thread_id and not session_code:
                thread_id = str(uuid.uuid4())
            if thread_id:
                # 统一使用 chat_history 模式
                chat_history = request.data.get("chat_prompts", []) or request.data.get("chat_history", [])
                chat_history = [
                    ChatPrompt(role=each["role"], content=each["content"])
                    for each in chat_history
                    if "role" in each and "content" in each
                ]
                # 如果有 input，追加到 chat_history
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

            # 构造 agent_instance，在 ChatCompletion 中，获取到的是 ChatCompletionAgent
            if session_code:
                agent_instance = build_chat_completion_agent_by_session_code(
                    session_code=session_code,
                    username=request.user.username,
                )
                # 获取 event_handler 用于后续更新会话状态
                event_handler = agent_instance.event_handler
                # 如果有 input 参数，追加到会话历史（支持新会话或追加消息）
                if _input:
                    # 处理 chat_history 为 None 或空列表的情况（如编辑第一条消息时）
                    if not agent_instance.chat_history:
                        agent_instance.chat_history = []
                    agent_instance.chat_history.append(ChatPrompt(role="user", content=_input))
                # 校验：如果没有 input 且 chat_history 为空，抛出明确的错误
                elif not agent_instance.chat_history:
                    raise ClientBlueException(
                        message="The chat history cannot be empty. Please provide 'input' parameter."
                    )
            else:
                chat_history = request.data.get("chat_prompts", []) or request.data.get("chat_history", [])
                if not chat_history and not _input:
                    raise ClientBlueException(message="chat_history, input or session_code is required")
                chat_history = [
                    ChatPrompt(role=each["role"], content=each["content"])
                    for each in chat_history
                    if "role" in each and "content" in each
                ]
                if _input:
                    chat_history.append(ChatPrompt(role="user", content=_input))
                agent_instance = build_chat_completion_agent_by_chat_history(chat_history, username)
            # 执行 agent
            if execute_kwargs.stream:
                generator = agent_instance.execute(execute_kwargs)
                # 断点续传：在流式开始/结束时更新会话状态
                if event_handler and all(
                    hasattr(event_handler, m) for m in ["set_streaming_started", "set_streaming_finished"]
                ):
                    event_handler.set_streaming_started()
                    generator = self._wrap_streaming_with_status(generator, event_handler)
                return self.streaming_response(generator)
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
        )
        execute_kwargs.session_code = session_code
        result = execute_agent_with_save(agent_instance, execute_kwargs, session_code, username)
        if execute_kwargs.stream:
            return self.streaming_response(result)
        return Response(result)

    def _wrap_streaming_with_status(self, generator, event_handler):
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
            return
        except ConsumerPreemptedError:
            _preempted = True
        except StreamCancelledError:
            _cancelled = True
        except Exception:
            raise
        finally:
            if not _preempted and not _client_disconnected and not _cancelled:
                event_handler.set_streaming_finished()

    def streaming_response(self, generator):
        sr = StreamingHttpResponse(generator)
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        sr.headers["content-type"] = "text/event-stream"
        sr.headers["Otel-Trace-Id"] = getattr(self.request._request, "otel_trace_id", "") or ""
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
