# -*- coding: utf-8 -*-
"""``AgentResourceManager``：``ResourceManagerProtocol`` 的默认实现。

负责 Client 创建 / 用户认证注入；业务方法由 ``BaseResourceManager`` 提供。
"""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Any

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.packages.resource_manager.base import BaseResourceManager

try:
    from bkoauth import get_access_token_by_user
except ImportError:
    get_access_token_by_user = None

if TYPE_CHECKING:
    from aidev_agent.api.bk_aidev import Client

logger = getLogger(__name__)


class AgentResourceManager(BaseResourceManager):
    """``ResourceManagerProtocol`` 的默认实现。

    应用态：只传 app_code + app_secret。
    用户态：额外传 username / access_token，自动处理 bkoauth 认证。
    """

    def get_client(self, **kwargs: Any) -> Client:
        """获取已完成认证信息注入的 API Client。"""
        # 1. 创建 Client
        client = BKAidevApi.get_client(
            app_code=self.app_code,
            app_secret=self.app_secret,
            **kwargs,
        )

        # 2. 注入用户认证
        access_token = self.access_token
        if not access_token and self.username and get_access_token_by_user is not None:
            try:
                token = get_access_token_by_user(self.username)
                access_token = getattr(token, "access_token", None)
            except Exception:
                logger.warning("get access_token by username failed: %s", self.username)
                access_token = None
        client.update_bkapi_authorization(access_token=access_token, bk_username=self.username or "")
        return client
