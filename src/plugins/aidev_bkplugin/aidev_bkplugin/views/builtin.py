# -*- coding: utf-8 -*-

import copy
import json
from logging import getLogger

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.enums import PromptRole
from aidev_agent.services.chat import ChatPrompt
from bk_plugin_framework.kit.api import custom_authentication_classes
from bk_plugin_framework.kit.decorators import inject_user_token, login_exempt
from blueapps.core.exceptions import ClientBlueException
from django.conf import settings
from django.http.response import StreamingHttpResponse
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.status import is_success
from rest_framework.views import APIView, Response
from rest_framework.viewsets import ViewSetMixin

from aidev_bkplugin.permissions import AgentPluginPermission
from aidev_bkplugin.services.agent import (
    build_chat_completion_agent_by_chat_history,
    build_chat_completion_agent_by_session_code,
    build_execute_kwargs,
    get_agent_config_info,
)
from aidev_bkplugin.utils import set_user_access_token

logger = getLogger(__name__)


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
        # 目前仅对 Restful Response 进行处理
        if isinstance(response, Response):
            if is_success(response.status_code):
                response.status_code = status.HTTP_200_OK
                response.data = {
                    "result": True,
                    "data": response.data,
                    "code": "success",
                    "message": "ok",
                }
            else:
                response.data = {
                    "result": False,
                    "data": None,
                    "code": f"{response.status_code}",
                    "message": response.data,
                }
        return super().finalize_response(request, response, *args, **kwargs)


client = BKAidevApi.get_client(app_code=settings.BK_APP_CODE, app_secret=settings.BK_APP_SECRET)


class ChatSessionViewSet(PluginViewSet):
    def list(self, request):
        result = client.api.list_chat_session(headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = client.api.batch_delete_chat_session(json=request.data)
        return Response(data=result["data"])

    def create(self, request):
        result = client.api.create_chat_session(json=request.data, headers={"X-BKAIDEV-USER": request.user.username})
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
        result = client.api.stop_chat_session_content(headers={"X-BKAIDEV-USER": username})
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
    def create(self, request):
        # 调用Agent 的时候需要传入的相关参数
        execute_kwargs = build_execute_kwargs(request.data.get("execute_kwargs", {}), request.user.username)
        session_code = request.data.get("session_code", "")
        execute_kwargs.session_code = request.data.get("session_code", "")
        # 构造 agent_instance，在 ChatCompletion 中，获取到的是 ChatCompletionAgent
        if session_code:
            agent_instance = build_chat_completion_agent_by_session_code(session_code)
        else:
            chat_history = request.data.get("chat_prompts", []) or request.data.get("chat_history", [])
            _input = request.data.get("input", "")
            if not chat_history and not _input:
                raise ClientBlueException(message="chat_history or input is required")
            chat_history = [ChatPrompt(role=each["role"], content=each["content"]) for each in chat_history]
            if _input:
                chat_history.append(ChatPrompt(role="user", content=_input))
            agent_instance = build_chat_completion_agent_by_chat_history(chat_history)
        # 执行 agent
        if execute_kwargs.stream:
            generator = agent_instance.execute(execute_kwargs)
            return self.streaming_response(generator)
        else:
            result = agent_instance.execute(execute_kwargs)
            return Response(result)

    def streaming_response(self, generator):
        sr = StreamingHttpResponse(generator)
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        sr.headers["content-type"] = "text/event-stream"
        return sr


class AgentInfoViewSet(PluginViewSet):
    @action(detail=False, methods=["GET"], url_path="info", url_name="info")
    def info(self, request):
        agent_info = get_agent_config_info(request.user.username)

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
