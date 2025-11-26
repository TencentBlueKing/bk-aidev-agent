# -*- coding: utf-8 -*-

from logging import getLogger

import pkg_resources
from django.contrib.auth import get_user_model
from rest_framework.response import Response

from aidev_bkplugin.packages.apigw.permissions import ApigwPermission
from aidev_bkplugin.permissions import AgentPluginPermission
from aidev_bkplugin.views.builtin import (
    AgentInfoViewSet,
    ChatCompletionViewSet,
    ChatSessionContentViewSet,
    ChatSessionViewSet,
    PluginViewSet,
)

USER_MODEL = get_user_model()

logger = getLogger(__name__)


class OpenapiPluginViewSet(PluginViewSet):
    # 请求必须来自 apigw
    permission_classes = [ApigwPermission, AgentPluginPermission]

    def initialize_request(self, request, *args, **kwargs):
        """在此方法中，将用户信息添加到请求中"""
        username = self.get_openapi_username()
        if not username:
            raise ValueError("请提供会话用户名")
        request.user = self.make_user(username)
        return super().initialize_request(request, *args, **kwargs)

    def get_openapi_username(self):
        """获取应用态接口用户名"""
        return self.request.META.get("HTTP_X_BKAIDEV_USER")

    def make_user(self, username: str):
        if not username:
            return None
        user, _ = USER_MODEL.objects.get_or_create(username=username)
        return user


class OpenapiChatCompletionViewSet(OpenapiPluginViewSet, ChatCompletionViewSet):
    pass


class OpenapiAgentAbilitiesViewSet(PluginViewSet):
    """
    获取智能体依赖包
    此接口不鉴权，同时也不需要用户信息
    """

    permission_classes = []

    def list(self, request, *args, **kwargs):
        """获取所有以 aidev 开头的已安装包及其版本"""
        installed_packages = pkg_resources.working_set
        abilities = {package.key: package.version for package in installed_packages if package.key.startswith("aidev")}
        return Response(data=abilities)


class OpenapiChatSessionViewSet(OpenapiPluginViewSet, ChatSessionViewSet):
    pass


class OpenapiChatSessionContentViewSet(OpenapiPluginViewSet, ChatSessionContentViewSet):
    pass


class OpenapiAgentInfoViewSet(OpenapiPluginViewSet, AgentInfoViewSet):
    pass
