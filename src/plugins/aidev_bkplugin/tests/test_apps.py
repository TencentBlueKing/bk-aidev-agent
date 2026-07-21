# -*- coding: utf-8 -*-
"""测试专用轻量 AppConfig：注册 ``aidev_bkplugin`` 让 ``models.Checkpoint/Write`` 获得 app_label，
但**不重写** ``ready()``，避免 ``aidev_bkplugin/apps.py`` 的 OTel / httpx / bkoauth 等运行时副作用
在测试启动时加载（含远程 ``AgentConfigFetcher.get_info`` 调用）。

仅在 ``tests.settings.INSTALLED_APPS`` 中引用，不影响生产部署。
"""

from django.apps import AppConfig


class BkpluginTestConfig(AppConfig):
    name = "aidev_bkplugin"
    default_auto_field = "django.db.models.BigAutoField"
