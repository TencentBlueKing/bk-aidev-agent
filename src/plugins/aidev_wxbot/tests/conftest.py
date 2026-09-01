# -*- coding: utf-8 -*-
"""Test-only stubs for dependencies provided by the BK plugin runtime."""

import os
import sys
import tempfile
from types import ModuleType

import pytest
from django.apps import AppConfig


class AidevBkpluginTestConfig(AppConfig):
    """Register bkplugin models without running production startup hooks."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_bkplugin"
    label = "aidev_bkplugin"


class AidevWxbotTestConfig(AppConfig):
    """Register wxbot models without starting transport services."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_wxbot"
    label = "aidev_wxbot"


TEST_APP_CONFIG_MODULE = "aidev_wxbot_test_app_configs"
sys.modules.setdefault(TEST_APP_CONFIG_MODULE, sys.modules[__name__])


@pytest.hookimpl(tryfirst=True)
def pytest_configure():
    """Configure Django before pytest-django initializes the app registry."""
    from aidev_agent.config import settings as agent_settings
    from django.conf import settings

    agent_settings.set("BKAI_EVENT_DATABASE_ENABLED", False)
    if settings.configured:
        return
    from aidev_wxbot import settings as wxbot_settings

    values = {key: getattr(wxbot_settings, key) for key in dir(wxbot_settings) if key.isupper()}
    values.update(
        SECRET_KEY="aidev-wxbot-test-secret",
        DEBUG=False,
        USE_TZ=True,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
                "TEST": {"NAME": os.path.join(tempfile.gettempdir(), "aidev_wxbot_test.sqlite3")},
            }
        },
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            f"{TEST_APP_CONFIG_MODULE}.AidevBkpluginTestConfig",
            f"{TEST_APP_CONFIG_MODULE}.AidevWxbotTestConfig",
        ],
        MIDDLEWARE=[],
        ROOT_URLCONF="aidev_bkplugin.urls",
        APP_CODE="aidev-test",
        APP_TOKEN="test-token",
        BK_APP_CODE="aidev-test",
        BK_APP_SECRET="test-secret",
        USER_TOKEN_KEY_NAME="access_token",
        ENABLE_OTEL_TRACE=False,
        AIDEV_AGENT="aidev_agent.services.common_agent.CommonQAAgent",
    )
    settings.configure(**values)


def inject_user_token(func):
    return func


framework_module = ModuleType("bk_plugin_framework")
kit_module = ModuleType("bk_plugin_framework.kit")
decorators_module = ModuleType("bk_plugin_framework.kit.decorators")
decorators_module.inject_user_token = inject_user_token
kit_module.decorators = decorators_module
framework_module.kit = kit_module

sys.modules.setdefault("bk_plugin_framework", framework_module)
sys.modules.setdefault("bk_plugin_framework.kit", kit_module)
sys.modules.setdefault("bk_plugin_framework.kit.decorators", decorators_module)


@pytest.fixture
def wxbot_spans(monkeypatch):
    """真实 OTel 内存导出器，不上报到外部服务。"""
    from aidev_agent.utils import tracing
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "_agent_tracer", provider.get_tracer("wxbot-test"))
    yield exporter
    provider.shutdown()
