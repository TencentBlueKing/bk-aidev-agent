# -*- coding: utf-8 -*-

from django.apps import AppConfig
from django.conf import settings


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agent"

    def ready(self) -> None:
        # register your extension here
        from agent.services.agent import CommonQAAgentExtend
        from agent.services.factory import agent_factory

        agent_factory.register(settings.DEFAULT_AGENT, CommonQAAgentExtend)
        return super().ready()
