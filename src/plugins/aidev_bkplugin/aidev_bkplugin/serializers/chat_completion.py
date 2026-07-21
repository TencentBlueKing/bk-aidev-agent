# -*- coding: utf-8 -*-
"""ChatCompletionViewSet 入参 serializer。

设计目标：
- 集中校验 ``ChatCompletionViewSet.create`` 的入参，避免在 view 中散落 ``request.data.get(...)``。
- ``execute_kwargs`` 经 :func:`build_execute_kwargs` 转换为 ``ExecuteKwargs`` 实例后直接落入
  ``validated_data["execute_kwargs"]``，下游可直接消费。
- 兼容字段（``session_code``/``thread_id``/``task_id``/``flow_*``/``poll_*``）保留为可选项。
- ``thread_id``/``agent_type`` 的兜底/解析规则也下沉到本 serializer：

  - ``agent_type``：**不接受用户输入**，由 :func:`get_agent_config_info` 按
    ``execute_kwargs.version`` 拉取的 agent 配置唯一决定，写入 ``validated_data["agent_type"]``。
  - ``thread_id``：未传时回落到 ``execute_kwargs.thread_id``；仍为空且 ``session_code`` 也为空时，
    本 serializer 自动生成 uuid 兜底（与 view 旧行为一致，覆盖所有 agent_type 路径）。
"""

import uuid

from aidev_agent.pydantic_models import ExecuteKwargs
from rest_framework import serializers

from aidev_bkplugin.services.agent_execution import build_execute_kwargs
from aidev_bkplugin.services.agent_config import AgentConfigFetcher
from aidev_bkplugin.services.llm import LLMService


class ChatPromptContentField(serializers.Field):
    """chat_history.content 字段：兼容字符串与多模态列表。"""

    default_error_messages = {"invalid": "content must be a string or list[dict]"}

    def to_internal_value(self, data):
        if isinstance(data, str):
            return data
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            return data
        self.fail("invalid")

    def to_representation(self, value):
        return value


class ChatPromptItemSerializer(serializers.Serializer):
    role = serializers.CharField()
    content = ChatPromptContentField()


class ChatCompletionRequestSerializer(serializers.Serializer):
    """ChatCompletionViewSet.create 的统一入参 serializer。

    使用方式::

        serializer = ChatCompletionRequestSerializer(
            data=request.data,
            context={"username": username},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        execute_kwargs = data["execute_kwargs"]  # ExecuteKwargs 实例
        agent_type = data["agent_type"]          # 来自 get_agent_config_info(...)
    """

    input = serializers.CharField(required=False, allow_blank=True, default="")
    chat_history = ChatPromptItemSerializer(many=True, required=False, default=list)
    execute_kwargs = serializers.DictField(required=False, default=dict)
    resume = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    session_code = serializers.CharField(required=False, allow_blank=True, default="")
    thread_id = serializers.CharField(required=False, allow_blank=True, default="")

    # 模型热更新：覆盖智能体原配置的 chat_model / non_thinking_llm，需在当前空间可用模型列表内
    model = serializers.CharField(
        required=False, allow_blank=True, default="", help_text="热切换模型 llm_code，需在当前空间可用模型列表内"
    )

    # 流程智能体
    task_id = serializers.CharField(required=False, allow_blank=True, default="")
    flow_start_params = serializers.DictField(required=False, default=dict)
    poll_interval = serializers.FloatField(required=False, allow_null=True, default=None)
    poll_timeout = serializers.FloatField(required=False, allow_null=True, default=None)

    def validate_execute_kwargs(self, value: dict) -> ExecuteKwargs:
        # 显式声明 stream 默认值（与 ExecuteKwargs pydantic 默认一致），保持行为不变；
        # 同时直接返回 ExecuteKwargs 实例，避免下游再做一次 model_validate。
        merged = {"stream": False, **(value or {})}
        username = (self.context or {}).get("username")
        return build_execute_kwargs(merged, username)

    def validate(self, attrs):
        if (
            not attrs.get("input")
            and not attrs.get("chat_history")
            and not attrs.get("session_code")
            and not attrs.get("thread_id")
        ):
            raise serializers.ValidationError("chat_history, input or session_code is required")

        execute_kwargs: ExecuteKwargs = attrs["execute_kwargs"]
        if attrs.get("resume"):
            execute_kwargs.resume = attrs["resume"]
        username = (self.context or {}).get("username")

        # agent_type：完全由 agent_info 决定，按 execute_kwargs.version 路由（version 为空 → 最新版）。
        agent_info = AgentConfigFetcher.get_info(username=username, version=execute_kwargs.version)
        attrs["agent_type"] = agent_info.get("agent_type", "") or ""

        # thread_id：合并 execute_kwargs.thread_id；与 session_code 同时为空时自动生成 uuid 兜底。
        # 兜底覆盖所有 agent_type（含 flow），与 view 旧行为一致。
        thread_id = attrs.get("thread_id") or (execute_kwargs.thread_id or "")
        if not thread_id and not attrs.get("session_code"):
            thread_id = str(uuid.uuid4())
        attrs["thread_id"] = thread_id

        # model 热切换授权校验：非空时校验是否在当前空间可用模型列表内，避免越权切换到未授权模型
        model = attrs.get("model", "")
        if model and not LLMService.is_llm_accessible(username=username, llm_code=model):
            raise serializers.ValidationError({"model": f"模型 {model} 不在当前空间可用模型列表内"})

        return attrs
