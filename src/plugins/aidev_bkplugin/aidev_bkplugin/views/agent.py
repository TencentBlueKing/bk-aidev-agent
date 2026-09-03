# -*- coding: utf-8 -*-

from aidev_agent.enums import PromptRole
from django.conf import settings
from rest_framework.decorators import action
from rest_framework.views import Response

from aidev_bkplugin.serializers.agent import AgentInfoSerializer
from aidev_bkplugin.services.agent_config import AgentConfigFetcher
from aidev_bkplugin.services.agent_helpers import AgentHelper
from aidev_bkplugin.utils import is_local_dev, set_user_access_token
from aidev_bkplugin.views.base import PluginViewSet


class AgentInfoViewSet(PluginViewSet):
    @action(detail=False, methods=["GET"], url_path="info", url_name="info")
    def info(self, request):
        slz = AgentInfoSerializer(data=request.query_params)
        slz.is_valid(raise_exception=True)

        # 根据agent code获取agent配置信息
        agent_code = slz.validated_data.get("agent_code")
        agent_info = AgentConfigFetcher.get_info(username=request.user.username, app_code=agent_code)

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
        return Response(data=AgentHelper.get_agent_version())
