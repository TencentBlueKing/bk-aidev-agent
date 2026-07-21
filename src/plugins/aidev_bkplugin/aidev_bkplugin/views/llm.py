# -*- coding: utf-8 -*-
"""LLM 列表视图：供小鲸等已发布智能体入口拉取当前空间可用模型。

应用态入口（apigw）：``OpenapiLLMViewSet``（见 ``openapi/views.py``）。
用户态入口（应用域名直连）：本模块 ``LLMViewSet``。
两者复用同一 ``list_llms`` 逻辑，差异仅在鉴权 Mixin。
"""

from rest_framework.decorators import action
from rest_framework.views import Response

from aidev_bkplugin.serializers.llm import LLMListRequestSerializer
from aidev_bkplugin.services.llm import LLMService
from aidev_bkplugin.views.base import PluginViewSet


class LLMViewSet(PluginViewSet):
    @action(detail=False, methods=["GET"], url_path="list", url_name="list")
    def list_llms(self, request):
        """获取当前空间可用 LLM 列表，用于聊天时动态切换模型（智能体模型热更新）。"""
        username = self.get_username()
        slz = LLMListRequestSerializer(data=request.query_params)
        slz.is_valid(raise_exception=True)
        data = slz.validated_data
        llms = LLMService.list_llms(
            username=username,
            llm_type=data.get("llm_type", ""),
            supports=data.get("supports", ""),
            fuzzy=data.get("fuzzy", ""),
        )
        return Response(data=llms)
