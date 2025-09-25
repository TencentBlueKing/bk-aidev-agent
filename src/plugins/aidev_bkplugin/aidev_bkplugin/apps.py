# -*- coding: utf-8 -*-

from aidev_agent.utils.module_loading import import_string
from django.apps import AppConfig
from django.conf import settings

try:
    import bkoauth
except ImportError:
    bkoatuh = None


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_bkplugin"

    def ready(self) -> None:
        from aidev_bkplugin.services.factory import agent_config_factory, agent_factory

        if bkoauth:
            bkoauth._init_function()

        agent_factory.register(settings.DEFAULT_NAME, import_string(settings.DEFAULT_AGENT))
        agent_config_factory.register(settings.DEFAULT_NAME, import_string(settings.DEFAULT_CONFIG_MANAGER))
        return super().ready()
