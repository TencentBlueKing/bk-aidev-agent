from bkapi_client_core.base import Operation
from bkapi_client_core.client import BaseClient
from bkapi_client_core.django_helper import _get_client_by_settings
from bkapi_client_core.property import bind_property

from aidev_agent.api.base import ApiProtocol
from aidev_agent.api.domains import SSM_URL
from aidev_agent.config import settings


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
        return _get_client_by_settings(SSMClient, endpoint=SSM_URL, bk_app_code=app_code, bk_app_secret=app_secret)


# 模块级便捷函数
def get_client() -> SSMClient:
    """获取SSM客户端实例"""
    return SSMApi.get_client()
