# -*- coding: utf-8 -*-

from django.apps import AppConfig
from django.conf import settings

try:
    import bkoauth
except ImportError:
    bkoatuh = None


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agent"

    def ready(self) -> None:
        # register your extension here
        from agent.services.agent import CommonQAAgentExtend
        from agent.services.factory import agent_factory

        if bkoauth:
            bkoauth._init_function()

        agent_factory.register(settings.DEFAULT_AGENT, CommonQAAgentExtend)
        return super().ready()
