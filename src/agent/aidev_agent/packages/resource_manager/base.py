# -*- coding: utf-8 -*-
"""``BaseResourceManager``：资源管理器通用业务基类。

本基类收敛资源方法的业务装配和构造函数：
- 构造函数接收 app_code / app_secret / access_token / username 等通用参数；
- path_params / params / data 的组织；
- 后端响应 ``data`` 字段抽取；
- tool 结构转换。

Client 的创建、认证信息注入由 ``get_client()`` 负责，子类可覆写。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

from langchain_core.tools import StructuredTool

from aidev_agent.config import settings
from aidev_agent.enums import CredentialType
from aidev_agent.packages.langchain_core.tools import Tool, ToolExtra, make_structured_tool

if TYPE_CHECKING:
    from aidev_agent.api.bk_aidev import Client


class BaseResourceManager:
    """资源管理器通用业务基类。

    子类需实现 ``get_client()`` 返回已完成认证注入的 ``Client``。

    :param app_code: 应用编码，用于创建 API Client。
    :param app_secret: 应用密钥，用于创建 API Client。
    :param access_token: 用户 access_token，注入到 X-Bkapi-Authorization。
    :param username: 用户名
    """

    def __init__(
        self,
        app_code: str = "",
        app_secret: str = "",
        access_token: str = "",
        username: str = "",
        **kwargs: Any,
    ) -> None:
        self.app_code = app_code or settings.APP_CODE
        self.app_secret = app_secret or settings.SECRET_KEY
        self.access_token = access_token
        self.username = username
        self._extra = kwargs

    def get_client(self, **kwargs: Any) -> Client:
        """获取已完成认证信息注入的 API Client。子类必须实现。"""
        raise NotImplementedError

    # ---------- 资源方法 (7) ----------

    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict:
        client = self.get_client()
        return client.api.appspace_retrieve_knowledgebase(path_params={"id": id}, **kwargs).get("data", {})

    def retrieve_knowledge(self, id: int, **kwargs) -> dict:
        client = self.get_client()
        return client.api.appspace_retrieve_knowledge(path_params={"id": id}, **kwargs).get("data", {})

    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]:
        client = self.get_client()
        return client.api.get_chat_session_context(
            path_params={"session_code": session_code}, **kwargs
        ).get("data", [])

    def retrieve_agent_config(self, agent_code: str, version: Optional[str] = None, **kwargs) -> dict:
        params = kwargs.pop("params", None) or {}
        if version is not None:
            params["version"] = version
        if params:
            kwargs["params"] = params
        client = self.get_client()
        return client.api.retrieve_agent_config(path_params={"agent_code": agent_code}, **kwargs).get("data", {})

    def retrieve_skill(self, skill_id: str, version: str, **kwargs) -> dict:
        params = kwargs.pop("params", {})
        params["version"] = version
        client = self.get_client()
        return client.api.retrieve_resource_v1_skill(
            path_params={"skill_id": skill_id}, params=params, **kwargs
        ).get("data", {})

    def construct_tool(self, tool_code: str, **kwargs) -> StructuredTool:
        operation_name = "retrieve_tool" if kwargs.pop("appspace", True) else "appspace_retrieve_tool"
        client = self.get_client()
        operation = getattr(client.api, operation_name)
        result = operation(path_params={"tool_code": tool_code}, **kwargs)
        result["data"]["tool_cn_name"] = result["data"]["tool_name"]
        if result["data"].get("credential_type", "") != CredentialType.NULL.value:
            tool = Tool.model_validate(result["data"])
            tool.extra = ToolExtra(
                header={
                    "X-Bkapi-Authorization": json.dumps(
                        {"bk_app_code": self.app_code, "bk_app_secret": self.app_secret}
                    )
                }
            )
            return make_structured_tool(tool)
        return make_structured_tool(Tool.model_validate(result["data"]))

    def knowledge_query(self, data: dict[str, Any]) -> dict:
        client = self.get_client()
        return client.api.create_knowledgebase_query(data=data).get("data", {})

    # ---------- Flow Agent 方法 (8) ----------

    def start_flow_agent(self, data: dict, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_start(data=data, **kwargs).get("data", {})

    def get_flow_agent_task_info(self, task_id: str, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_task_info(
            path_params={"task_id": task_id}, **kwargs
        ).get("data", {})

    def retry_flow_agent_node(self, session_code: str, node_id: str, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_retry_node(
            path_params={"session_code": session_code, "node_id": node_id}, **kwargs
        ).get("data", {})

    def skip_flow_agent_node(self, session_code: str, node_id: str, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_skip_node(
            path_params={"session_code": session_code, "node_id": node_id}, **kwargs
        ).get("data", {})

    def stop_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_task_stop(
            data={"session_code": session_code}, **kwargs
        ).get("data", {})

    def pause_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_task_pause(
            data={"session_code": session_code}, **kwargs
        ).get("data", {})

    def resume_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_task_resume(
            data={"session_code": session_code}, **kwargs
        ).get("data", {})

    def get_flow_agent_task_node_info(self, task_id: str, node_id: str, **kwargs) -> dict:
        client = self.get_client()
        return client.api.flow_agent_task_node_info(
            path_params={"task_id": task_id, "node_id": node_id}, **kwargs
        ).get("data", {})
