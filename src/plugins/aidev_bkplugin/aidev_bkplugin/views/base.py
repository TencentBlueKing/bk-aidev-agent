# -*- coding: utf-8 -*-

import contextlib
import json
from logging import getLogger
from typing import Any, Optional

from aidev_agent.packages.resource_manager import ResourceManagerProtocol
from bk_plugin_framework.kit.decorators import inject_user_token
from django.conf import settings
from django.http.response import StreamingHttpResponse
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.request import Request
from rest_framework.status import is_success
from rest_framework.views import APIView, Response
from rest_framework.viewsets import ViewSetMixin

from aidev_bkplugin.packages.drf.authentication import custom_authentication_classes
from aidev_bkplugin.packages.drf.decorators import login_exempt
from aidev_bkplugin.permissions import AgentPluginPermission
from aidev_bkplugin.services.agent_builder import LLMOverrideResourceManager
from aidev_bkplugin.services.agent_helpers import AgentHelper


class PluginResourceManager(LLMOverrideResourceManager):
    """带用户态认证注入的资源管理器。

    传入 ``username``，基类 ``get_client()`` 自动通过 bkoauth 取 ``access_token`` 注入到 client header。
    view 层经 ``PluginViewSet.get_resource_manager()`` 按请求构造，并向下注入给
    ``SessionManager`` / ``AgentBuilder`` / ``AGUISessionWriter``，取代历史上的
    ``resource_manager()`` 全局单例。

    继承 ``LLMOverrideResourceManager`` 以携带 ``model`` 覆盖能力：view 层构造时 ``model`` 为空，
    由 ``AgentBuilder`` 在装配 agent 时按请求补上，使模型热更新与用户态认证共存于同一个 rm。
    """

    def __init__(self, username: str, model: str = ""):
        super().__init__(username=username, model=model)
        self._cached_client = None

    def get_client(self, **kwargs: Any):
        """按实例缓存 ``client``。

        基类每次 ``get_client()`` 都会 ``resolve_access_token``，即一次 bkoauth ``AccessToken``
        表查询（token 临期还会同步发请求续期）。本类是请求级对象，同一实例上的 client 可安全复用，
        避免 ``SessionManager`` 等多次取 client 时反复查库。
        带 ``kwargs`` 的调用参数各异，不参与缓存。
        """
        if kwargs:
            return super().get_client(**kwargs)
        if self._cached_client is None:
            self._cached_client = super().get_client()
        return self._cached_client


class IgnoreClientContentNegotiation(DefaultContentNegotiation):
    """忽略客户端 Accept 头限制的内容协商类。

    支持流式响应（``text/event-stream``）避免 406 Not Acceptable。
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        return (renderers[0], renderers[0].media_type)


logger = getLogger(__name__)
# TODO: 「pre-request 模式」建议应该去掉全局的client，通过声明resource manager来获得client。
client = AgentHelper.get_client()


@method_decorator(login_exempt, name="dispatch")
@method_decorator(inject_user_token, name="dispatch")
class PluginViewSet(ViewSetMixin, APIView):
    permission_classes = [AgentPluginPermission]
    authentication_classes = custom_authentication_classes

    def initialize_request(self, request, *args, **kwargs):
        if request.user:
            setattr(request, "_user", request.user)
        return super().initialize_request(request, *args, **kwargs)

    def get_resource_manager(self) -> Optional[ResourceManagerProtocol]:
        """子类可覆盖，返回自定义的 ``resource_manager``。"""
        return PluginResourceManager(username=self.get_username())

    def get_client(self, **kwargs: Any):
        """View 层取 ``client`` 的统一入口。

        子类可整体覆盖此方法以完全自定义构造逻辑；也可以只覆盖
        ``get_resource_manager`` 进行细粒度定制。
        ``kwargs`` 用于一次性透传额外参数。
        """
        return AgentHelper.get_client(resource_manager=self.get_resource_manager(), **kwargs)

    @property
    def client(self):
        """请求生命周期内缓存的 ``client``。
        让子类可以直接用 ``self.client.api.xxx(...)``，避免每次调用重建。
        缓存键挂在 ``request._plugin_client`` 上，不污染进程全局。
        """
        cached = getattr(self.request, "_plugin_client", None)
        if cached is None:
            cached = self.get_client()
            # request 在异常路径下可能不可写，这里降级为不缓存。
            with contextlib.suppress(Exception):
                setattr(self.request, "_plugin_client", cached)
        return cached

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
