# -*- coding: utf-8 -*-

from django.apps import AppConfig
from django.conf import settings

try:
    import bkoauth
except ImportError:
    bkoatuh = None


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bkplugin_aidev_agent"

    def ready(self) -> None:
        # register your extension here
        from bkplugin_aidev_agent.services.agent import CommonQAAgentExtend
        from bkplugin_aidev_agent.services.factory import agent_factory

        if bkoauth:
            bkoauth._init_function()

        agent_factory.register(settings.DEFAULT_AGENT, CommonQAAgentExtend)
        return super().ready()
