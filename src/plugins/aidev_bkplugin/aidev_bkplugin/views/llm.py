# -*- coding: utf-8 -*-
"""LLM 列表视图：供小鲸等已发布智能体入口拉取当前空间可用模型。

应用态入口（apigw）：``OpenapiLLMViewSet``（见 ``openapi/views.py``）。
用户态入口（应用域名直连）：本模块 ``LLMViewSet``。
两者复用同一拉取逻辑，差异仅在鉴权 Mixin。
"""

from rest_framework.views import Response

from aidev_bkplugin.serializers.llm import LLMListRequestSerializer
from aidev_bkplugin.services.llm import LLMService
from aidev_bkplugin.views.base import PluginViewSet


class LLMViewSet(PluginViewSet):
    def list(self, request):
        """获取当前空间可用 LLM 列表，用于聊天时动态切换模型（智能体模型热更新）。

        space_id 由 ``LLMService.list_llms`` 内部从当前 agent 所在空间（agent_info）取，
        无需前端透传。
        """
        username = self.get_username()
        slz = LLMListRequestSerializer(data=request.query_params)
        slz.is_valid(raise_exception=True)
        data = slz.validated_data
        llms = LLMService.list_llms(
            username=username,
            llm_type=data.get("llm_type", ""),
            fuzzy=data.get("fuzzy", ""),
            supports=data.get("supports", ""),
        )
        return Response(data=llms)
