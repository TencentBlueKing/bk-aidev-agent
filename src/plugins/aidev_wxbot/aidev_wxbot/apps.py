#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django app configuration for aidev_wxbot.
"""

from django.apps import AppConfig


class AidevWxbotConfig(AppConfig):
    """Configuration for aidev_wxbot Django app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_wxbot"
    verbose_name = "AI Dev WeChat Bot"

    def ready(self):
        """Initialize the app when Django starts."""
        # 这里可以添加应用启动时需要执行的代码
