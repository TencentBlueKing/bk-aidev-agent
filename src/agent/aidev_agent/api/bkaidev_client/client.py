# -*- coding: utf-8 -*-

from bkapi_client_core.base import Operation, OperationGroup
from bkapi_client_core.client import BaseClient
from bkapi_client_core.property import bind_property

from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.config import settings
from aidev_agent.enums import CredentialType
from aidev_agent.packages.langchain.tools.base import Tool, make_structured_tool


class OpenApiGroup(OperationGroup):
    create_knowledgebase_query = bind_property(
        Operation,
        name="create_knowledgebase_query",
        method="POST",
        path="/openapi/aidev/resource/v1/knowledgebase/query/",
    )

    appspace_retrieve_knowledgebase = bind_property(
        Operation,
        name="retrieve_knowledgebase",
        method="GET",
        path="/openapi/aidev/resource/v1/knowledgebase/{id}/",
    )

    appspace_retrieve_knowledge = bind_property(
        Operation,
        name="retrieve_knowledge",
        method="GET",
        path="/openapi/aidev/resource/v1/knowledge/{id}/",
    )

    retrieve_tool = bind_property(
        Operation,
        name="retrieve_tool",
        method="GET",
        path="/openapi/aidev/resource/v1/tool/{tool_code}/",
    )

    appspace_retrieve_tool = bind_property(
        Operation,
        name="retrieve_tool",
        method="GET",
        path="/openapi/aidev/resource/v1/tool/{tool_code}/",
    )

    list_chat_session = bind_property(
        Operation,
        name="list_chat_session",
        method="GET",
        path="/openapi/aidev/resource/v1/chat/session/",
    )

    batch_delete_chat_session = bind_property(
        Operation,
        name="batch_delete_chat_session",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session/batch_delete/",
    )

    create_chat_session = bind_property(
        Operation,
        name="create_chat_session",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session/",
    )

    update_chat_session = bind_property(
        Operation,
        name="update_chat_session",
        method="PUT",
        path="/openapi/aidev/resource/v1/chat/session/{session_code}/",
    )

    retrieve_chat_session = bind_property(
        Operation,
        name="retrieve_chat_session",
        method="GET",
        path="/openapi/aidev/resource/v1/chat/session/{session_code}/",
    )

    destroy_chat_session = bind_property(
        Operation,
        name="destroy_chat_session",
        method="DELETE",
        path="/openapi/aidev/resource/v1/chat/session/{session_code}/",
    )

    rename_chat_session = bind_property(
        Operation,
        name="rename_chat_session",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session/{session_code}/ai_rename/",
    )

    create_chat_session_content = bind_property(
        Operation,
        name="create_chat_session_content",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session_content/",
    )

    update_chat_session_content = bind_property(
        Operation,
        name="update_chat_session_content ",
        method="PUT",
        path="/openapi/aidev/resource/v1/chat/session_content/{id}/",
    )

    batch_delete_chat_session_content = bind_property(
        Operation,
        name="batch_delete_chat_session_content ",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session_content/batch_delete/",
    )

    get_chat_session_contents = bind_property(
        Operation,
        name="get_chat_session_contents",
        method="GET",
        path="/openapi/aidev/resource/v1/chat/session_content/content/",
    )

    get_chat_session_context = bind_property(
        Operation,
        name="get_chat_session_context ",
        method="GET",
        path="/openapi/aidev/resource/v1/chat/session/{session_code}/context/",
    )

    destroy_chat_session_content = bind_property(
        Operation,
        name="destroy_chat_session_content",
        method="DELETE",
        path="/openapi/aidev/resource/v1/chat/session_content/{id}/",
    )

    retrieve_agent_config = bind_property(
        Operation,
        name="retrieve_agent_config",
        method="GET",
        path="/openapi/aidev/resource/v1/agent/{agent_code}/",
    )

    add_knowledge_item = bind_property(
        Operation,
        name="add_knowledge_item",
        method="POST",
        path="/openapi/aidev/resource/v1/knowledge/",
    )

    add_dataset_item = bind_property(
        Operation,
        name="add_dataset_item",
        method="POST",
        path="/openapi/aidev/resource/v1/dataset_item/",
    )

    bind_agent_space = bind_property(
        Operation,
        name="bind_agent_space",
        method="POST",
        path="/openapi/aidev/resource/v1/agent/{agent_code}/bind_space/",
    )

    retrieve_resource_v1_prompt = bind_property(
        Operation,
        name="retrieve_resource_v1_prompt",
        method="GET",
        path="/openapi/aidev/resource/v1/prompt/{prompt_code}/",
    )

    retrieve_resource_v1_collection = bind_property(
        Operation,
        name="retrieve_resource_v1_collection",
        method="GET",
        path="/openapi/aidev/resource/v1/collection/{collection_code}/",
    )


class Client(BaseClient, AbstractBKAidevResourceManager):
    api = bind_property(OpenApiGroup, name="api")

    def construct_tool(self, tool_code, **kwargs):
        retrieve_tool = self.api.retrieve_tool if kwargs.pop("appspace", True) else self.api.appspace_retrieve_tool
        result = retrieve_tool(path_params={"tool_code": tool_code}, **kwargs)
        result["data"]["tool_cn_name"] = result["data"]["tool_name"]
        if result["data"].get("credential_type", "") == CredentialType.BLUEAPPS.value:
            tool = Tool.model_validate(result["data"])
            tool.extra = {"bk_app_code": settings.APP_CODE, "bk_app_secret": settings.SECRET_KEY}
            return make_structured_tool(tool)
        return make_structured_tool(Tool.model_validate(result["data"]))

    def knowledge_query(self, data: dict):
        result = self.api.create_knowledgebase_query(data=data)
        return result.get("data", {})

    def retrieve_agent_config(self, agent_code: str, **kwargs) -> dict:
        return self.api.retrieve_agent_config(path_params={"agent_code": agent_code}, **kwargs).get("data", {})

    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]:
        """Get chat session context"""
        return self.api.get_chat_session_context(path_params={"session_code": session_code}, **kwargs).get("data", [])

    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict:
        """Get knowledgebase details"""
        return self.api.appspace_retrieve_knowledgebase(path_params={"id": id}, **kwargs).get("data", {})

    def retrieve_knowledge(self, id: int, **kwargs) -> dict:
        """Get knowledge details"""
        return self.api.appspace_retrieve_knowledge(path_params={"id": id}, **kwargs).get("data", {})
