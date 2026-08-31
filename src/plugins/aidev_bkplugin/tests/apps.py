# -*- coding: utf-8 -*-
"""测试专用 AppConfig。

``aidev_bkplugin.apps.AgentConfig.ready()`` 会初始化 bkoauth、instrument OpenTelemetry，
并通过 ``AgentConfigFetcher.get_info()`` 发起真实 HTTP 请求，不适合在单测启动时执行。
本 AppConfig 复用同一个 app label，只让 Django 发现 ``aidev_bkplugin.models``
（使 Checkpoint / Write 能在测试库建表），不携带任何运行时副作用。
"""

from django.apps import AppConfig


class AidevBkpluginTestConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_bkplugin"
    label = "aidev_bkplugin"


class WxAiBotTestConfig(AppConfig):
    """Register models only, without starting wxbot services."""

    name = "aidev_wxbot.wxaibot"
    label = "wxaibot"
