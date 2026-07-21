# -*- coding: utf-8 -*-
"""LLM 列表接口入参 serializer。"""

from rest_framework import serializers


class LLMListRequestSerializer(serializers.Serializer):
    """LLM 列表查询入参，透传给平台应用态 ``app/v1/llms`` 网关接口。"""

    llm_type = serializers.CharField(
        required=False, allow_blank=True, default="", help_text="模型类型，不传时平台默认 chat.completion"
    )
    supports = serializers.CharField(
        required=False, allow_blank=True, default="", help_text="模型能力过滤，逗号分隔，如 tools,vision"
    )
    fuzzy = serializers.CharField(
        required=False, allow_blank=True, default="", help_text="模糊搜索关键词，按 llm_name/description/base_model 匹配"
    )
