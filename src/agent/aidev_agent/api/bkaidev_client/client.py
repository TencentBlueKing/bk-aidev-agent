# -*- coding: utf-8 -*-

from bkapi_client_core.base import Operation, OperationGroup
from bkapi_client_core.client import BaseClient, RequestContextBuilder
from bkapi_client_core.property import bind_property


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

    upload_chat_session_file = bind_property(
        Operation,
        name="upload_chat_session_file",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session/{session_code}/upload/{file_name}/",
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

    stop_chat_session_content = bind_property(
        Operation,
        name="stop_chat_session_content",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session_content/stop/",
    )

    create_chat_group = bind_property(
        Operation,
        name="create_chat_group",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/chat_group/",
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

    retrieve_resource_v1_mcp = bind_property(
        Operation,
        name="retrieve_resource_v1_mcp",
        method="GET",
        path="/openapi/aidev/resource/v1/mcp/{mcp_code}/",
    )

    retrieve_resource_v1_skill = bind_property(
        Operation,
        name="retrieve_resource_v1_skill",
        method="GET",
        path="/openapi/aidev/resource/v1/agents/skill/{skill_id}/",
    )

    create_feedback = bind_property(
        Operation,
        name="create_feedback",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/session_feedback/",
    )

    get_feedback_reasons = bind_property(
        Operation,
        name="get_feedback_reasons",
        method="GET",
        path="/openapi/aidev/resource/v1/chat/session_feedback/reasons/",
    )

    share_chat_session = bind_property(
        Operation,
        name="share_chat_session",
        method="POST",
        path="/openapi/aidev/resource/v1/chat/share/",
    )

    get_shared_chat = bind_property(
        Operation,
        name="get_shared_chat",
        method="GET",
        path="/openapi/aidev/resource/v1/chat/share/{share_token}/",
    )

    upgrade_agent_sessions = bind_property(
        Operation,
        name="upgrade_agent_sessions",
        method="POST",
        path="/openapi/aidev/resource/v1/agent/agent_sessions/upgrade/",
    )

    flow_agent_start = bind_property(
        Operation,
        name="flow_agent_start",
        method="POST",
        path="/openapi/aidev/resource/v1/flow_agent/start/",
    )

    flow_agent_task_info = bind_property(
        Operation,
        name="flow_agent_task_info",
        method="GET",
        path="/openapi/aidev/resource/v1/flow_agent/task_info/{task_id}/",
    )

    flow_agent_task_node_info = bind_property(
        Operation,
        name="flow_agent_task_node_info",
        method="GET",
        path="/openapi/aidev/resource/v1/flow_agent/task_node_info/{task_id}/{node_id}/",
    )

    flow_agent_task_stop = bind_property(
        Operation,
        name="flow_agent_task_stop",
        method="POST",
        path="/openapi/aidev/resource/v1/flow_agent/task/stop/",
    )

    flow_agent_task_pause = bind_property(
        Operation,
        name="flow_agent_task_pause",
        method="POST",
        path="/openapi/aidev/resource/v1/flow_agent/task/pause/",
    )

    flow_agent_task_resume = bind_property(
        Operation,
        name="flow_agent_task_resume",
        method="POST",
        path="/openapi/aidev/resource/v1/flow_agent/task/resume/",
    )


class AidevRequestContextBuilder(RequestContextBuilder):
    def build(self, endpoint, operation_context):
        return super().build(endpoint, operation_context)

    def build_data(
        self,
        context,
        data=None,
    ):
        if context.pop("keep_data", False):
            context["data"] = data
            return
        super().build_data(context, data)


class Client(BaseClient):
    """蓝鲸 AIDev OpenAPI 纯客户端"""

    _build_class = AidevRequestContextBuilder
    api = bind_property(OpenApiGroup, name="api")

    def start_flow_agent(self, data: dict, **kwargs) -> dict:
        """Start a flow agent task"""
        return self.api.flow_agent_start(data=data, **kwargs).get("data", {})

    def get_flow_agent_task_info(self, task_id: str, **kwargs) -> dict:
        """Get flow agent task info"""
        return self.api.flow_agent_task_info(path_params={"task_id": task_id}, **kwargs).get("data", {})

    def get_flow_agent_task_node_info(self, task_id: str, node_id: str, **kwargs) -> dict:
        """Get flow agent task node info"""
        return self.api.flow_agent_task_node_info(path_params={"task_id": task_id, "node_id": node_id}, **kwargs).get(
            "data", {}
        )

    def stop_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        """Stop (revoke) a flow agent task"""
        return self.api.flow_agent_task_stop(data={"session_code": session_code}, **kwargs).get("data", {})

    def pause_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        """Pause a flow agent task"""
        return self.api.flow_agent_task_pause(data={"session_code": session_code}, **kwargs).get("data", {})

    def resume_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        """Resume a paused flow agent task"""
        return self.api.flow_agent_task_resume(data={"session_code": session_code}, **kwargs).get("data", {})
