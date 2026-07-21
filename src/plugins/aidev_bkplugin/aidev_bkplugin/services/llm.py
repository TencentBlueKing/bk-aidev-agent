# -*- coding: utf-8 -*-
"""LLM 服务：调平台应用态 ``app/v1/llms`` 网关接口，拉取当前空间可用模型列表。

供小鲸等已发布智能体入口在聊天时拉取可选模型，配合 ``chat_completion`` 的 ``llm`` 字段
实现智能体模型热更新；同时提供 ``llm`` 空间授权校验能力。
"""

from __future__ import annotations

from logging import getLogger
from typing import Any

from aidev_agent.packages.resource_manager import resource_manager

logger = getLogger(__name__)


class LLMService:
    """调平台应用态 llm 列表网关接口。

    平台接口走 ``AppBaseView`` 应用态鉴权（app_code + app_secret），用户权限过滤通过
    ``X-BKAIDEV-USER`` header 透传；空间解析由平台按 app_code 兜底完成。
    """

    @staticmethod
    def list_llms(
        username: str = "",
        llm_type: str = "",
        supports: str = "",
        fuzzy: str = "",
    ) -> list[dict[str, Any]]:
        """拉取当前空间可用 LLM 列表。

        Args:
            username: 用户名，透传给平台做用户权限过滤；为空时平台仅返回公开 + 空间授权模型。
            llm_type: 模型类型过滤，不传时平台默认 chat.completion。
            supports: 模型能力过滤，逗号分隔（如 ``"tools,vision"``）。
            fuzzy: 模糊搜索关键词。

        Returns:
            平台返回的模型精简列表（llm_code/llm_name/llm_type/icon/...）。
        """
        client = resource_manager().get_client()
        params: dict[str, Any] = {}
        if llm_type:
            params["llm_type"] = llm_type
        if supports:
            # 逗号分隔透传，平台 AppLLMListRequest.normalize_supports 会 split 成 List[str]
            params["supports"] = supports
        if fuzzy:
            params["fuzzy"] = fuzzy
        headers = {"X-BKAIDEV-USER": username} if username else {}
        result = client.api.list_app_v1_llms(params=params, headers=headers)
        return result.get("data", []) or []

    @staticmethod
    def is_llm_accessible(username: str = "", llm_code: str = "") -> bool:
        """校验 ``llm_code`` 是否在当前空间可用模型列表内。

        用于 ``chat_completion`` 收到 ``llm`` 字段时做空间授权校验，避免越权切换到未授权模型。
        ``llm_code`` 为空时视为不覆盖（沿用智能体原配置），直接放行。
        """
        if not llm_code:
            return True
        llms = LLMService.list_llms(username=username)
        return any(llm.get("llm_code") == llm_code for llm in llms)
