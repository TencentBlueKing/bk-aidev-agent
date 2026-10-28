# -*- coding: utf-8 -*-
"""``AgentResourceManager``：``ResourceManagerProtocol`` 的默认实现。

负责 Client 创建 / 用户认证注入；业务方法由 ``BaseResourceManager`` 提供。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.packages.resource_manager.base import BaseResourceManager

if TYPE_CHECKING:
    from aidev_agent.api.bk_aidev import Client


class AgentResourceManager(BaseResourceManager):
    """``ResourceManagerProtocol`` 的默认实现。

    应用态：只传 app_code + app_secret。
    用户态：额外传 username / access_token，自动处理 bkoauth 认证。
    """

    def get_client(self, **kwargs: Any) -> Client:
        """获取已完成认证信息注入的 API Client。"""
        client = BKAidevApi.get_client(
            app_code=self.app_code,
            app_secret=self.app_secret,
            **kwargs,
        )
        access_token = self.resolve_access_token(self.username) or None
        client.update_bkapi_authorization(access_token=access_token, bk_username=self.username or "")
        self._inject_tenant_header(client)
        return client
