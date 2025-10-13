# -*- coding: utf-8 -*-
import logging

from bkapi_client_core.base import Operation
from bkapi_client_core.client import BaseClient
from bkapi_client_core.property import bind_property

from aidev_agent.api.base import ApiProtocol
from aidev_agent.api.domains import SSM_URL
from aidev_agent.config import settings

logger = logging.getLogger(__name__)


class SSMClient(BaseClient):
    """SSM API 客户端"""

    # 生成 access_token
    create_access_token = bind_property(
        Operation,
        name="create_access_token",
        method="POST",
        path="/api/v1/auth/access-tokens",
    )

    # 刷新 access_token
    refresh_access_token = bind_property(
        Operation,
        name="refresh_access_token",
        method="POST",
        path="/api/v1/auth/access-tokens/refresh",
    )

    # 校验 access_token
    verify_access_token = bind_property(
        Operation,
        name="verify_access_token",
        method="POST",
        path="/api/v1/auth/access-tokens/verify",
    )


class SSMApi(ApiProtocol):
    """SSM API 协议"""

    _api_name = "ssm"

    @classmethod
    def get_client(cls, app_code=settings.APP_CODE, app_secret=settings.SECRET_KEY) -> SSMClient:
        """获取SSM客户端实例"""
        app_code = app_code or getattr(settings, "BKPAAS_APP_ID", "") or getattr(settings, "APP_CODE", "")
        app_secret = app_secret or getattr(settings, "BKPAAS_APP_SECRET", "") or getattr(settings, "SECRET_KEY", "")

        if not app_code:
            logger.error("[SSMApi.get_client] app_code为空！")
            raise ValueError("app_code不能为空")
        if not app_secret:
            logger.error("[SSMApi.get_client] app_secret为空！")
            raise ValueError("app_secret不能为空")
        if not SSM_URL:
            logger.error("[SSMApi.get_client] SSM_URL为空！")
            raise ValueError("SSM_URL不能为空")

        try:
            # 创建客户端
            client = SSMClient(endpoint=SSM_URL)

            # 使用正确的认证头部格式
            headers = {
                "X-BK-APP-CODE": app_code,
                "X-BK-APP-SECRET": app_secret,
                "Content-Type": "application/json",
            }

            client.update_headers(headers)
            logger.info(f"[SSMApi.get_client] 客户端创建成功，app_code: {app_code}")
            return client
        except Exception as e:
            logger.error(f"[SSMApi.get_client] 创建客户端失败: {e}")
            raise


# 模块级便捷函数
def get_client(bk_token=None) -> SSMClient:
    """获取SSM客户端实例"""
    logger.info("[get_client] 调用SSMApi.get_client()")
    return SSMApi.get_client(bk_token=bk_token)
