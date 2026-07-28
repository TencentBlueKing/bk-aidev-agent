# -*- coding: utf-8 -*-
import os
from urllib.parse import urlparse

# 应用模块
INSTALLED_APPS = ("aidev_ai_blueking",)

# SaaS运行版本
RUN_VER = "ieod" if os.environ.get("BKPAAS_ENGINE_REGION", "default") == "ieod" else "open"

BKPAAS_APP_CODE = os.getenv("BKPAAS_APP_ID")


def _get_bkapp_saas_path(run_ver: str, app_code: str | None) -> str:
    if market_entrance_url := os.getenv("BKPAAS_MARKET_ENTRANCE_URL"):
        return urlparse(market_entrance_url).path.rstrip("/")
    return os.getenv("BKAPP_SAAS_PATH") or ("" if run_ver == "ieod" else f"/{app_code}")


BKAPP_SAAS_PATH = _get_bkapp_saas_path(RUN_VER, BKPAAS_APP_CODE)
