from bkapi_client_core.base import Operation
from bkapi_client_core.client import BaseClient
from bkapi_client_core.property import bind_property

from aidev_agent.api.base import ApiProtocol
from aidev_agent.api.domains import SSM_URL


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
    def get_client(cls) -> SSMClient:
        """获取SSM客户端实例（无Django依赖）"""
        from aidev_agent.config import settings

        # 根据 bkapi_client_core 的标准方式创建客户端
        return SSMClient(
            endpoint=SSM_URL,
            # 认证信息通过标准方式传递
            headers={
                "X-Bk-App-Code": getattr(settings, "APP_CODE", "") or getattr(settings, "BK_APP_CODE", ""),
                "X-Bk-App-Secret": getattr(settings, "SECRET_KEY", "") or getattr(settings, "BK_APP_SECRET", ""),
            },
        )


# 模块级便捷函数
def get_client() -> SSMClient:
    """获取SSM客户端实例"""
    return SSMApi.get_client()
