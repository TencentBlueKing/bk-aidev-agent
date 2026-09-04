from aidev_agent.packages.resource_manager import AgentResourceManager
from aidev_agent.pydantic_models import AgentConfig

from bk_plugin.config import AGENT_CONFIG


class CustomAgentResourceManager(AgentResourceManager):
    """读取 ``bk_plugin.config.AGENT_CONFIG`` 覆盖平台返回的 agent 配置。

    通过 ``aidev_bkplugin.settings.AIDEV_RESOURCE_MANAGER`` 注入到全局
    ``resource_manager()`` 工厂；plugin 与 SDK 业务层一律走 ``resource_manager().get_agent_config(...)``。
    """

    def get_agent_config(self, agent_code, version=None, **kwargs) -> AgentConfig:
        agent_config = super().get_agent_config(agent_code, version=version, **kwargs)
        for key, value in AGENT_CONFIG.items():
            if hasattr(agent_config, key) and value:
                setattr(agent_config, key, value)
        return agent_config
