# -*- coding: utf-8 -*-
"""
企微渠道认证适配。
封装企微渠道特有的身份解析和 API Gateway 认证逻辑：
- resolve_channel_admin_rtx: 从渠道配置获取管理员 RTX，用于 bkoauth 认证
- WxFlowAgentClient: 满足 ResourceManagerProtocol 中 flow agent 方法的企微认证适配器
"""

from __future__ import annotations

from logging import getLogger

from aidev_bkplugin.views.base import PluginResourceManager

from .channel_config import get_channel_contact
from ..api.bkaidev import BkAiDevApi

logger = getLogger(__name__)


def resolve_channel_admin_rtx(fallback_username: str) -> str:
    """
    从渠道配置的 contact 字段获取管理员 RTX 名。
    企微用户通过回调进入时，传入的是企微内部 userid
    无法直接用于 bkoauth 认证和会话归属。
    统一使用渠道配置中的管理员 RTX 作为身份标识。
    """
    try:
        configs = BkAiDevApi().retrieve_agent_channel_configs("rtx")
        if not configs:
            logger.warning("[resolve_rtx] 渠道配置返回空列表，请确认智能体已启用企微渠道")
        else:
            for cfg in configs:
                contact = get_channel_contact(cfg)
                if contact:
                    logger.info(f"[resolve_rtx] 使用渠道管理员 RTX: {contact}")
                    return contact
            logger.warning("[resolve_rtx] 渠道配置中未找到 contact 字段")
    except Exception as e:
        logger.warning(f"[resolve_rtx] 获取渠道配置失败: {e}")
    logger.warning(f"[resolve_rtx] 无法获取管理员 RTX，原样使用: {fallback_username}")
    return fallback_username


class WxFlowAgentClient(PluginResourceManager):

    def __init__(self, username: str, rtx_username: str | None = None):
        self._username = username
        rtx = rtx_username or resolve_channel_admin_rtx(username)
        super().__init__(username=rtx)

    def start_flow_agent(self, data: dict | None = None) -> dict:
        """启动 flow agent 任务，满足 ResourceManagerProtocol 协议。"""
        logger.info(
            f"[WxFlowAgentClient] start_flow_agent: "
            f"wx_user={self._username}, rtx_user={self.username}"
        )
        return super().start_flow_agent(data=data or {})
