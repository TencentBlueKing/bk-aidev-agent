# -*- coding: utf-8 -*-
import os

# 应用模块
INSTALLED_APPS = ("aidev_ai_blueking",)

# SaaS运行版本
RUN_VER = "ieod" if os.environ.get("BKPAAS_ENGINE_REGION", "default") == "ieod" else "open"

BKPAAS_APP_CODE = os.getenv("BKPAAS_APP_ID")
BKAPP_SAAS_PATH = os.getenv("BKAPP_SAAS_PATH") or ("" if RUN_VER == "ieod" else f"/{BKPAAS_APP_CODE}")
