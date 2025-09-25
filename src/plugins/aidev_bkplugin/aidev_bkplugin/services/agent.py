from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.enums import AgentBuildType
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.chat import ChatCompletionAgent
from aidev_agent.services.pydantic_models import ChatPrompt
from django.conf import settings
from django.core.cache import cache

from .factory import agent_config_factory, agent_factory


def build_chat_completion_agent_by_session_code(session_code: str) -> ChatCompletionAgent:
    agent_cls = agent_factory.get(settings.DEFAULT_NAME)
    config_manager = agent_config_factory.get(settings.DEFAULT_NAME)
    return AgentInstanceFactory.build_agent(
        build_type=AgentBuildType.SESSION, session_code=session_code, agent_cls=agent_cls, config_manager=config_manager
    )


def build_chat_completion_agent_by_chat_history(chat_history: list[ChatPrompt]) -> ChatCompletionAgent:
    role_contents = get_agent_role_info()
    if role_contents:
        chat_history = role_contents + chat_history
    agent_cls = agent_factory.get(settings.DEFAULT_NAME)
    config_manager = agent_config_factory.get(settings.DEFAULT_NAME)
    agent_instance = AgentInstanceFactory.build_agent(
        build_type=AgentBuildType.DIRECT,
        session_context_data=[each.model_dump() for each in chat_history],
        agent_cls=agent_cls,
        config_manager=config_manager,
    )
    return agent_instance


def get_agent_config_info(username: str | None = None):
    agent_info = cache.get("get_agent_config_info")
    if not agent_info:
        client = BKAidevApi.get_client()
        result = client.api.retrieve_agent_config(
            path_params={"agent_code": settings.APP_CODE}, headers={"X-BKAIDEV-USER": username}
        )
        agent_info = result["data"]
        cache.set(agent_info, settings.DEFAULT_CACHE_TIMEOUT)
    return agent_info


def get_agent_role_info() -> list[ChatPrompt]:
    agent_config_info = get_agent_config_info()
    agent_role_content = agent_config_info["prompt_setting"].get("content", [])
    if not agent_role_content:
        return []

    for each in agent_role_content:
        each["role"] = each["role"].replace("hidden-", "")
        if each["role"] == "pause":
            each["role"] = "assistant"

    return [ChatPrompt(role=each["role"], content=each["content"]) for each in agent_role_content]
