from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager

from bk_plugin.config import AGENT_CONFIG


class CustomAgentConfigManager(AgentConfigManager):
    # extend your agent config here

    @classmethod
    def get_config(cls, *args, **kwargs) -> AgentConfig:
        agent_config: AgentConfig = AgentConfigManager.get_config(*args, **kwargs)

        # 使用本地配置覆盖
        for key, config in AGENT_CONFIG.items():
            if hasattr(agent_config, key) and AGENT_CONFIG.get(key):
                setattr(agent_config, key, config)

        return agent_config
