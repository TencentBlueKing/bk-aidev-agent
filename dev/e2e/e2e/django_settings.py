"""Django settings overlay used only by the local E2E runner."""

from __future__ import annotations

import os
from importlib import import_module

base_settings = import_module("bk_plugin.patch.plugin")
for setting_name in dir(base_settings):
    if setting_name.isupper():
        globals()[setting_name] = getattr(base_settings, setting_name)

auth_middleware = "django.contrib.auth.middleware.AuthenticationMiddleware"
e2e_middleware = "e2e.django_auth.E2EAuthMiddleware"
middleware = list(base_settings.MIDDLEWARE)
if e2e_middleware not in middleware:
    middleware.insert(middleware.index(auth_middleware) + 1, e2e_middleware)
    MIDDLEWARE = tuple(middleware)

ROOT_URLCONF = "e2e.django_urls"

if sqlite_path := os.getenv("E2E_SQLITE_PATH"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_path,
        }
    }
