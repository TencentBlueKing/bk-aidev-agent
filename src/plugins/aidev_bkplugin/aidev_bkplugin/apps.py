# -*- coding: utf-8 -*-

import logging

from aidev_agent.utils.module_loading import import_string
from django.apps import AppConfig
from django.conf import settings

try:
    import bkoauth
except ImportError:
    bkoauth = None

# OpenTelemetry 是可选 extras，未安装时降级为 no-op。
# 安装方式：pip install aidev-bkplugin[opentelemetry]
try:
    from aidev_bkplugin.packages.opentelemetry import BkAidevAgentInstrumentor
except ImportError:
    BkAidevAgentInstrumentor = None

logger = logging.getLogger(__name__)


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_bkplugin"

    def ready(self) -> None:
        from aidev_bkplugin.services.factory import agent_config_factory, agent_factory

        if bkoauth:
            bkoauth._init_function()

        agent_factory.register(settings.DEFAULT_NAME, import_string(settings.DEFAULT_AGENT))
        agent_config_factory.register(settings.DEFAULT_NAME, import_string(settings.DEFAULT_CONFIG_MANAGER))

        if BkAidevAgentInstrumentor is not None:
            BkAidevAgentInstrumentor().instrument()
        else:
            logger.info(
                "[aidev_bkplugin] OpenTelemetry extras 未安装，跳过自动 instrument；"
                "如需启用请安装 aidev-bkplugin[opentelemetry]。"
            )

        return super().ready()
