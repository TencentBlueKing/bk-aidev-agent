# PLEASE DO NOT MODIFY THIS FILE!
import json
from logging import getLogger

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.enums import AgentBuildType
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.chat import ChatPrompt, ExecuteKwargs
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

from agent.services.agent import (
    get_agent_config_info,
    get_agent_role_info,
)

logger = getLogger(__name__)


@method_decorator(login_exempt, name="dispatch")
@method_decorator(inject_user_token, name="dispatch")
class PluginViewSet(ViewSetMixin, APIView):
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


class ChatSessionViewSet(PluginViewSet):
    def list(self, request):
        client = BKAidevApi.get_client()
        result = client.api.list_chat_session(headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        client = BKAidevApi.get_client()
        result = client.api.batch_delete_chat_session(json=request.data)
        return Response(data=result["data"])

    def create(self, request):
        client = BKAidevApi.get_client()
        result = client.api.create_chat_session(json=request.data, headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.update_chat_session(path_params={"session_code": pk}, json=request.data)
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.retrieve_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    @action(["POST"], url_path="ai_rename", detail=True)
    def ai_rename(self, request, pk, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.rename_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.destroy_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])


class ChatSessionContentViewSet(PluginViewSet):
    def create(self, request):
        client = BKAidevApi.get_client()
        result = client.api.create_chat_session_content(json=request.data)
        return Response(data=result["data"])

    @action(["GET"], url_path="content", detail=False)
    def content(self, request, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.get_chat_session_contents(params=request.query_params)
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.destroy_chat_session_content(path_params={"id": pk})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.update_chat_session_content(path_params={"id": pk}, json=request.data)
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        client = BKAidevApi.get_client()
        result = client.api.batch_delete_chat_session_content(json=request.data)
        return Response(data=result["data"])


class ChatCompletionViewSet(PluginViewSet):
    def create(self, request):
        execute_kwargs = ExecuteKwargs.model_validate(request.data.get("execute_kwargs", {}))
        session_code = request.data.get("session_code", "")
        if session_code:
            agent_instance = AgentInstanceFactory.build_agent(
                build_type=AgentBuildType.SESSION, session_code=session_code
            )
        else:
            chat_history = request.data.get("chat_prompts", []) or request.data.get("chat_history", [])
            if not chat_history:
                raise ClientBlueException(message="chat_history is required")
            chat_history = [ChatPrompt(role=each["role"], content=each["content"]) for each in chat_history]
            role_contents = get_agent_role_info()
            if role_contents:
                chat_history = role_contents + chat_history

            agent_instance = AgentInstanceFactory.build_agent(
                build_type=AgentBuildType.DIRECT, session_context_data=chat_history
            )

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
        agent_info = get_agent_config_info()
        return Response(data=agent_info)
