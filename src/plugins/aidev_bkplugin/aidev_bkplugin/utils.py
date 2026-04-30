import os
import json
from logging import getLogger
from os import environ

from aidev_agent.api.bk_aidev import BKAidevApi
from django.conf import settings

logger = getLogger(__name__)

# 全局 API client：使用 BKPAAS_APP_ID + BKPAAS_APP_SECRET 认证
bkaidev_api_client = BKAidevApi.get_client(app_code=settings.APP_CODE, app_secret=settings.SECRET_KEY)


def set_user_access_token(request):
    try:
        import bkoauth

        bkoauth.get_access_token(request)
    except Exception as err:
        logger.warning(f"failed to import bkoauth, error: {err}")


def is_local_dev():
    return os.getenv("BKPAAS_ENVIRONMENT", "dev").lower() in {"dev", "development"}
