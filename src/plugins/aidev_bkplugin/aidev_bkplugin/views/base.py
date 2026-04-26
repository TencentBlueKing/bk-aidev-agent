# -*- coding: utf-8 -*-

import json
from logging import getLogger

from bk_plugin_framework.kit.api import custom_authentication_classes
from bk_plugin_framework.kit.decorators import inject_user_token, login_exempt
from django.conf import settings
from django.http.response import StreamingHttpResponse
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.request import Request
from rest_framework.status import is_success
from rest_framework.views import APIView, Response
from rest_framework.viewsets import ViewSetMixin

from aidev_bkplugin.permissions import AgentPluginPermission
from aidev_bkplugin.utils import bkaidev_api_client, get_flow_agent_client


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
