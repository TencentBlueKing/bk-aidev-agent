import os
import json
from logging import getLogger
from os import environ
from typing import Tuple

import bkoauth
from aidev_agent.api.bk_aidev import BKAidevApi
from django.conf import settings

logger = getLogger(__name__)

# 全局 API client：使用 BKPAAS_APP_ID + BKPAAS_APP_SECRET 认证
bkaidev_api_client = BKAidevApi.get_client(app_code=settings.APP_CODE, app_secret=settings.SECRET_KEY)

# 本地开发用：通过环境变量注入固定 access_token
_dev_access_token = environ.get("BKAPP_ACCESS_TOKEN", "")


def _get_user_access_token(username: str) -> str:
    """获取指定用户的 access_token（优先取本地开发环境变量，再走 bkoauth）"""
    access_token = _dev_access_token
    if not access_token:
        try:
            access_token_obj = bkoauth.get_access_token_by_user(username)
            if access_token_obj and access_token_obj.access_token:
                access_token = access_token_obj.access_token
        except Exception as e:
            logger.warning(f"Failed to get access_token for user={username}, error={e}")
    return access_token


def get_flow_agent_client(username: str) -> Tuple:
    """获取 Flow Agent 专用 client 和已构建好的认证请求头。

    Returns:
        (client, headers) 元组：
        - client: 已注入 access_token 的 BKAidevApi client
        - headers: 包含 X-BKAIDEV-USER 和 X-Bkapi-Authorization 的请求头字典
    """
    flow_client = BKAidevApi.get_client(app_code=settings.APP_CODE, app_secret=settings.SECRET_KEY)
    headers = {"X-BKAIDEV-USER": username}

    access_token = _get_user_access_token(username)
    if access_token:
        flow_client.update_bkapi_authorization(
            bk_app_code=settings.APP_CODE,
            bk_app_secret=settings.SECRET_KEY,
            access_token=access_token,
        )
        headers["X-Bkapi-Authorization"] = json.dumps({"access_token": access_token})

    return flow_client, headers


def set_user_access_token(request):
    try:
        import bkoauth

        bkoauth.get_access_token(request)
    except Exception as err:
        logger.warning(f"failed to import bkoauth, error: {err}")


def is_local_dev():
    return os.getenv("BKPAAS_ENVIRONMENT", "dev").lower() in {"dev", "development"}
