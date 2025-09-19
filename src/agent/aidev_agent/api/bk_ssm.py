# -*- coding: utf-8 -*-
from aidev_agent.api.ssm_client import SSMClient


class SSMApi:
    """SSM API工厂类"""

    @classmethod
    def get_user_client(cls, request) -> SSMClient:
        """
        获取用户态SSM客户端

        Args:
            request: Django request对象，包含用户认证信息

        Returns:
            SSMClient: SSM客户端实例
        """
        client = SSMClient()
        # 从request中提取用户信息
        username = getattr(request, "username", None) or getattr(request.user, "username", None)
        bk_token = request.META.get("HTTP_BK_TOKEN") or request.COOKIES.get("bk_token")

        if username and bk_token:
            # 预设用户信息到客户端，避免后续每次调用都要传递
            client._request_context = {"username": username, "bk_token": bk_token, "is_user_mode": True}

        return client

    @classmethod
    def get_client_client(cls) -> SSMClient:
        """
        获取应用态SSM客户端

        Returns:
            SSMClient: SSM客户端实例
        """
        client = SSMClient()
        client._request_context = {"is_user_mode": False}
        return client

    @classmethod
    def get_client_by_request(cls, request) -> SSMClient:
        """
        通过request获取SSM客户端
        自动判断是否为用户态还是应用态

        Args:
            request: Django request对象

        Returns:
            SSMClient: SSM客户端实例
        """
        # 检查request中是否有用户认证信息
        username = getattr(request, "username", None) or getattr(request.user, "username", None)
        bk_token = request.META.get("HTTP_BK_TOKEN") or request.COOKIES.get("bk_token")

        if username and bk_token:
            # 有用户信息，返回用户态客户端
            return cls.get_user_client(request)
        else:
            # 没有用户信息，返回应用态客户端
            return cls.get_client_client()
