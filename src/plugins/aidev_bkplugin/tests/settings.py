# -*- coding: utf-8 -*-
"""Minimal Django settings for aidev_bkplugin pytest 运行。

仅满足单元测试导入路径解析与 ORM/缓存/中间件等最小化运行需要，
不复刻线上配置；任何敏感信息均通过 env 注入，禁止在此硬编码。
"""

import os

SECRET_KEY = "aidev-bkplugin-test-secret"
DEBUG = False
USE_TZ = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    # 注册 aidev_bkplugin 让 models.Checkpoint/Write 获得 app_label；用轻量 BkpluginTestConfig
    # 避免 apps.py ready() 的 OTel/httpx/远程 AgentConfigFetcher 副作用
    "tests.test_apps.BkpluginTestConfig",
]

MIDDLEWARE: list = []
ROOT_URLCONF = "aidev_bkplugin.urls"

# —— 仅测试场景使用的占位项；运行环境中由部署侧 env 注入 ——
APP_CODE = os.environ.get("APP_CODE", "aidev-test")
APP_TOKEN = os.environ.get("APP_TOKEN", "test-token")
BK_APP_CODE = os.environ.get("BK_APP_CODE", "aidev-test")
BK_APP_SECRET = os.environ.get("BK_APP_SECRET", "test-secret")
USER_TOKEN_KEY_NAME = "access_token"

# —— OpenTelemetry: 关闭额外 instrumentation，避免单测启动副作用 ——
ENABLE_OTEL_TRACE = False

# —— 智能体 SDK 默认 ——
AIDEV_AGENT = "aidev_agent.services.common_agent.CommonQAAgent"

# —— 客服渠道 ——
CHAT_GROUP_ENABLED = False
CHAT_GROUP_STAFF: list = []
CHAT_GROUP_TYPE = "qyweixin_chat_group"
