# -*- coding: utf-8 -*-
"""LLM 服务：调平台应用态 ``/resource/v1/agents/llms/`` 网关接口，拉取当前空间可用模型列表。

供小鲸等已发布智能体入口在聊天时拉取可选模型，配合 ``chat_completion`` 的 ``model`` 字段
实现智能体模型热更新；同时提供 ``model`` 空间授权校验能力。
"""

from __future__ import annotations

from logging import getLogger
from typing import Any

from aidev_agent.packages.resource_manager.agent import AgentResourceManager

logger = getLogger(__name__)


class LLMService:
    """调平台 llm 列表网关接口（``/resource/v1/agents/llms/``）。

    走 APIGW 用户态鉴权：``AgentResourceManager(username=...)`` 注入 ``bk_username`` / ``access_token``，
    满足 APIGW 对用户身份的要求；``X-BKAIDEV-USER`` header 同步透传给平台做用户权限过滤。
    空间由平台侧 ``AppLLMListView``（继承 ``AIDevBaseView``）从 ``app_code`` 解析 ``AgentPlugin.space_id`` 得到，
    无需 agent 透传 ``space_id``。
    """

    @staticmethod
    def list_llms(
        username: str = "",
        llm_type: str = "",
        fuzzy: str = "",
        supports: str = "",
    ) -> list[dict[str, Any]]:
        """拉取当前空间可用 LLM 列表。

        空间由平台侧 ``AppLLMListView`` 从 ``app_code`` 解析 ``AgentPlugin.space_id`` 得到，
        无需 agent 透传 ``space_id``。

        Args:
            username: 用户名，透传给平台做用户权限过滤；为空时平台仅返回公开 + 空间授权模型。
            llm_type: 模型类型过滤，不传时平台默认 chat.completion。
            fuzzy: 模糊搜索关键词。
            supports: 按模型支持的功能过滤，逗号分隔字符串（如 ``tool_call,vision``），
                透传平台由 ``AppLLMListRequest`` 归一为 list。

        Returns:
            平台返回的模型精简列表（llm_code/llm_name/llm_type/icon/...）。
        """
        # 用户态 client：传 bk_username 给 APIGW 用户身份鉴权
        client = AgentResourceManager(username=username).get_client()
        params: dict[str, Any] = {}
        if llm_type:
            params["llm_type"] = llm_type
        if fuzzy:
            params["fuzzy"] = fuzzy
        if supports:
            params["supports"] = supports
        headers = {"X-BKAIDEV-USER": username} if username else {}
        result = client.api.list_agents_v1_llms(params=params, headers=headers)
        return result.get("data", []) or []

    @staticmethod
    def is_llm_accessible(username: str = "", llm_code: str = "") -> bool:
        """校验 ``llm_code`` 是否在当前空间可用模型列表内。

        用于 ``chat_completion`` 收到 ``model`` 字段时做空间授权校验，避免越权切换到未授权模型。
        ``llm_code`` 为空时视为不覆盖（沿用智能体原配置），直接放行。
        """
        if not llm_code:
            return True
        llms = LLMService.list_llms(username=username)
        return any(llm.get("llm_code") == llm_code for llm in llms)
