from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager

from bk_plugin.versions.assistant_components import config


class CustomAgentConfigManager(AgentConfigManager):
    # extend your agent config here

    @classmethod
    def get_config(cls, *args, **kwargs) -> AgentConfig:
        agent_config: AgentConfig = AgentConfigManager.get_config(*args, **kwargs)
        agent_config.llm_model_name = config.chat_model
        agent_config.non_thinking_llm_model_name = config.non_thinking_llm
        agent_config.knowledgebase_ids = config.knowledgebase_ids
        agent_config.knowledge_ids = config.knowledge_ids
        agent_config.tool_codes = config.tool_codes
        agent_config.agent_prompt = config.role_prompt
        return agent_config
