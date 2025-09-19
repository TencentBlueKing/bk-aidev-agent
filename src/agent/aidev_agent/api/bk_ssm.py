# -*- coding: utf-8 -*-
"""
SSM API工厂类
"""

from aidev_agent.api.ssm_client import SSMClient


class SSMApi:
    """SSM API工厂类"""

    @classmethod
    def get_user_client(cls, username: str, bk_token: str) -> SSMClient:
        """
        获取用户态SSM客户端

        Args:
            username: 用户名
            bk_token: 用户登录token

        Returns:
            SSMClient: SSM客户端实例
        """
        return SSMClient()

    @classmethod
    def get_client_client(cls) -> SSMClient:
        """
        获取应用态SSM客户端

        Returns:
            SSMClient: SSM客户端实例
        """
        return SSMClient()

    @classmethod
    def get_client_by_request(cls, request) -> SSMClient:
        """
        通过request获取SSM客户端（应用态）

        Args:
            request: Django request对象

        Returns:
            SSMClient: SSM客户端实例
        """
        return cls.get_client_client()
