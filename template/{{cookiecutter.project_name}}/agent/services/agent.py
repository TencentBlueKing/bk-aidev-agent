# Sample for rewrite CommonQAAgent

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent
from aidev_agent.services.pydantic_models import ChatPrompt
from bk_plugin.factory import agent_factory
from bk_plugin.meta import DEFAULT_AGENT
from bk_plugin.versions.assistant_components import config


class CommonQAAgentExtend(CommonQAAgent):
    # 可以根据实际情况扩展
    pass


def build_chat_completion_agent(chat_history: list[ChatPrompt]) -> ChatCompletionAgent:
    client = BKAidevApi.get_client()
    config.sync_config()
    llm = ChatModel.get_setup_instance(model=config.chat_model)
    knowledge_bases = [
        client.api.appspace_retrieve_knowledgebase(path_params={"id": _id})["data"] for _id in config.knowledgebase_ids
    ]
    knowledge_items = [
        client.api.appspace_retrieve_knowledge(path_params={"id": _id})["data"] for _id in config.knowledge_ids
    ]
    tools = [client.construct_tool(tool_code) for tool_code in config.tool_codes]
    agent_cls = agent_factory.get(DEFAULT_AGENT)
    return ChatCompletionAgent(
        chat_model=llm,
        role_prompt=config.role_prompt,
        tools=tools,
        knowledge_bases=knowledge_bases,
        knowledge_items=knowledge_items,
        chat_history=chat_history,
        agent_cls=agent_cls,
    )
