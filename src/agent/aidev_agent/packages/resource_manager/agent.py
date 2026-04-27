# -*- coding: utf-8 -*-
"""``AgentResourceManager``：``ResourceManagerProtocol`` 的默认实现。

持有底层 ``Client``（``aidev_agent.api.bkaidev_client.client``）做 HTTP 调用；
业务装配（``Tool / ToolExtra / settings`` 拼装、``version`` 入 ``params``、
``data`` 字段抽取等）收敛在本类内部，``Client`` 只负责 OpenAPI operation 调用。
"""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.tools import StructuredTool

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.api.bkaidev_client.client import Client
from aidev_agent.config import settings
from aidev_agent.enums import CredentialType
from aidev_agent.packages.langchain_core.tools import Tool, ToolExtra, make_structured_tool


class AgentResourceManager:
    """``ResourceManagerProtocol`` 的默认实现，包装底层 ``Client``。

    ``client`` 默认走 ``BKAidevApi.get_client()`` 自取；测试 / 多租户场景可显式注入。
    """

    def __init__(self, client: Optional[Client] = None) -> None:
        self.client = client if client is not None else BKAidevApi.get_client()

    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict:
        return self.client.api.appspace_retrieve_knowledgebase(path_params={"id": id}, **kwargs).get("data", {})

    def retrieve_knowledge(self, id: int, **kwargs) -> dict:
        return self.client.api.appspace_retrieve_knowledge(path_params={"id": id}, **kwargs).get("data", {})

    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]:
        return self.client.api.get_chat_session_context(path_params={"session_code": session_code}, **kwargs).get(
            "data", []
        )

    def retrieve_agent_config(self, agent_code: str, version: Optional[str] = None, **kwargs) -> dict:
        params = kwargs.pop("params", None) or {}
        if version is not None:
            params["version"] = version
        if params:
            kwargs["params"] = params
        return self.client.api.retrieve_agent_config(path_params={"agent_code": agent_code}, **kwargs).get("data", {})

    def retrieve_skill(self, skill_id: str, version: str, **kwargs) -> dict:
        params = kwargs.pop("params", {})
        params["version"] = version
        return self.client.api.retrieve_resource_v1_skill(
            path_params={"skill_id": skill_id}, params=params, **kwargs
        ).get("data", {})

    def construct_tool(self, tool_code: str, **kwargs) -> StructuredTool:
        retrieve_tool = (
            self.client.api.retrieve_tool if kwargs.pop("appspace", True) else self.client.api.appspace_retrieve_tool
        )
        result = retrieve_tool(path_params={"tool_code": tool_code}, **kwargs)
        result["data"]["tool_cn_name"] = result["data"]["tool_name"]
        if result["data"].get("credential_type", "") != CredentialType.NULL.value:
            tool = Tool.model_validate(result["data"])
            tool.extra = ToolExtra(
                header={
                    "X-Bkapi-Authorization": json.dumps(
                        {"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.SECRET_KEY}
                    )
                }
            )
            return make_structured_tool(tool)
        return make_structured_tool(Tool.model_validate(result["data"]))

    def knowledge_query(self, data: dict[str, Any]) -> dict:
        result = self.client.api.create_knowledgebase_query(data=data)
        return result.get("data", {})
