import json
import os

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent, ChatPrompt, ExecuteKwargs
from bk_plugin_framework.kit.api import custom_authentication_classes
from bk_plugin_framework.kit.decorators import inject_user_token, login_exempt
from bkoauth import get_app_access_token
from django.conf import settings
from django.http import HttpResponse
from django.http.response import StreamingHttpResponse
from django.utils.decorators import method_decorator
from langchain_core.prompts import jinja2_formatter
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.status import is_success
from rest_framework.views import APIView, Response
from rest_framework.viewsets import ViewSetMixin

from ..versions.assistant_components import config

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


@method_decorator(login_exempt, name="dispatch")
@method_decorator(inject_user_token, name="dispatch")
class PluginViewSet(ViewSetMixin, APIView):
    authentication_classes = custom_authentication_classes

    @staticmethod
    def get_bkapi_authorization_info(request) -> str:
        auth_info = {
            "bk_app_code": settings.BK_APP_CODE,
            "bk_app_secret": settings.BK_APP_SECRET,
            settings.USER_TOKEN_KEY_NAME: request.token,
        }
        if settings.BKPAAS_ENVIRONMENT != "dev":
            access_token = get_app_access_token().access_token
            auth_info.update({"access_token": access_token})

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
    def create(self, request):
        client = BKAidevApi.get_client()
        result = client.api.create_chat_session(json=request.data)
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        client = BKAidevApi.get_client()
        result = client.api.retrieve_chat_session(path_params={"session_code": pk})
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


class ChatCompletionViewSet(PluginViewSet):
    def create(self, request):
        execute_kwargs = ExecuteKwargs.model_validate(request.data.get("execute_kwargs", {}))
        session_code = request.data.get("session_code", "")
        agent_instance = self._build_agent_by_session_code(session_code)

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

    def _build_agent_by_session_code(self, session_code: str) -> ChatCompletionAgent:
        llm = ChatModel.get_setup_instance(model=config.chat_model)
        client = BKAidevApi.get_client()

        result = client.api.get_chat_session_context(path_params={"session_code": session_code})
        knowledge_bases = [
            client.api.appspace_retrieve_knowledgebase(path_params={"id": _id})["data"]
            for _id in config.knowledgebase_ids
        ]
        tools = [client.construct_tool(tool_code) for tool_code in config.tool_codes]

        return ChatCompletionAgent(
            chat_model=llm,
            chat_history=[ChatPrompt.model_validate(each) for each in result.get("data", [])],
            knowledge_bases=knowledge_bases,
            tools=tools,
        )


class IndexView(APIView):
    def get(self, request):
        client = BKAidevApi.get_client()
        result = client.api.retrieve_agent_config(path_params={"agent_code": settings.APP_CODE})
        agent_name = result["data"]["agent_name"]
        with open(f"{BASE_DIR}/dist/index.html") as fo:
            rendered = jinja2_formatter(
                fo.read(),
                SITE_URL="",
                BK_STATIC_URL="",
                BK_API_PREFIX="/bk_plugin/plugin_api",
                BK_USER_NAME=getattr(request.user, "username", ""),
                BK_AGENT_NAME=agent_name,
            )
        return HttpResponse(rendered)


class AgentInfoViewSet(PluginViewSet):
    @action(detail=False, methods=["GET"], url_path="info", url_name="info")
    def info(self, request):
        client = BKAidevApi.get_client()
        result = client.api.retrieve_agent_config(path_params={"agent_code": settings.APP_CODE})
        return Response(data=result["data"])
