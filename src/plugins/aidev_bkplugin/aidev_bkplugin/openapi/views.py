# -*- coding: utf-8 -*-

from logging import getLogger

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.decorators import action
from rest_framework.response import Response

from aidev_bkplugin.packages.apigw.permissions import ApigwPermission
from aidev_bkplugin.permissions import AgentPluginPermission
from aidev_agent.enums import ChannelType
from aidev_bkplugin.services.agent_helpers import AgentHelper
from aidev_bkplugin.views.agent import AgentInfoViewSet
from aidev_bkplugin.views.base import PluginViewSet
from aidev_bkplugin.views.chat import ChatCompletionViewSet
from aidev_bkplugin.views.llm import LLMViewSet
from aidev_bkplugin.views.session import ChatSessionContentViewSet, ChatSessionViewSet
from aidev_bkplugin.views.user_operation import UserOperationViewSet

USER_MODEL = get_user_model()

logger = getLogger(__name__)


class OpenapiPluginViewSet(PluginViewSet):
    # 请求必须来自 apigw
    permission_classes = [ApigwPermission, AgentPluginPermission]

    def initial(self, request, *args, **kwargs):
        """在此方法中，将用户信息添加到请求中"""
        username = getattr(request.user, "username", None) or self.get_openapi_username()
        if not username:
            raise ValueError("请提供会话用户名")
        request.user = self.make_user(username)
        return super().initial(request, *args, **kwargs)

    def get_openapi_username(self):
        """获取应用态接口用户名"""
        return self.request.META.get("HTTP_X_BKAIDEV_USER")

    def make_user(self, username: str):
        if not username:
            return None
        user, _ = USER_MODEL.objects.get_or_create(username=username)
        return user


class OpenapiChatCompletionViewSet(OpenapiPluginViewSet, ChatCompletionViewSet):
    @property
    def channel_type(self):
        return ChannelType.API.value


class OpenapiAgentAbilitiesViewSet(OpenapiPluginViewSet):
    """
    获取智能体依赖包
    此接口不鉴权，同时也不需要用户信息
    """

    permission_classes = []

    def list(self, request, *args, **kwargs):
        """获取所有以 aidev 开头的已安装包及其版本"""
        return Response(data=AgentHelper.get_agent_version())

    @action(detail=False, methods=["GET"], url_path="flush", url_name="flush")
    def flush(self, request, *args, **kwargs):
        """刷新缓存"""
        cache.clear()
        return Response(data={"message": "缓存已清除"})


class OpenapiChatSessionViewSet(OpenapiPluginViewSet, ChatSessionViewSet):
    @property
    def channel_type(self):
        return ChannelType.API.value


class OpenapiChatSessionContentViewSet(OpenapiPluginViewSet, ChatSessionContentViewSet):
    pass


class OpenapiAgentInfoViewSet(OpenapiPluginViewSet, AgentInfoViewSet):
    pass


class OpenapiUserOperationViewSet(OpenapiPluginViewSet, UserOperationViewSet):
    pass


class OpenapiAgentAccessViewSet(OpenapiPluginViewSet):
    """访问者对当前智能体的授权状态与权限申请"""

    # 未授权用户也需要查询状态和提交申请，不能走智能体使用权限校验
    permission_classes = [ApigwPermission]

    def list(self, request, *args, **kwargs):
        """查询授权状态：authorized / unauthorized / authorization_pending"""
        result = self.client.api.get_agent_access_status(headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])

    @action(detail=False, methods=["POST"], url_path="apply", url_name="apply")
    def apply(self, request, *args, **kwargs):
        """提交使用权限申请，返回 IAM 审批链接"""
        result = self.client.api.apply_agent_access(json={}, headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])


class OpenapiLLMViewSet(OpenapiPluginViewSet, LLMViewSet):
    """应用态 LLM 列表接口：供小鲸等已发布智能体入口拉取空间可用模型。"""

    pass
