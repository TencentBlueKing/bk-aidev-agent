"""Minimal Django settings shared by the aidev_wxbot test suite."""

import os
import tempfile

from aidev_wxbot.settings import *  # noqa: F403

SECRET_KEY = "aidev-wxbot-test-secret"
DEBUG = False
USE_TZ = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {"NAME": os.path.join(tempfile.gettempdir(), "aidev_wxbot_test.sqlite3")},
    }
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "aidev_wxbot_test_apps.AidevBkpluginTestConfig",
    "aidev_wxbot_test_apps.AidevWxbotTestConfig",
]
MIDDLEWARE: list = []
ROOT_URLCONF = "aidev_bkplugin.urls"

APP_CODE = "aidev-test"
APP_TOKEN = "test-token"
BK_APP_CODE = "aidev-test"
BK_APP_SECRET = "test-secret"
USER_TOKEN_KEY_NAME = "access_token"
ENABLE_OTEL_TRACE = False
AIDEV_AGENT = "aidev_agent.services.common_agent.CommonQAAgent"
AIDEV_DATABASE_EVENTS_ENABLED = False
