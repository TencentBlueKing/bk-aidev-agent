# -*- coding: utf-8 -*-
"""Agent 辅助工具：``Client`` 取回、checkpointer、版本探测、会话页 URL 拼接。

均收敛在 ``AgentHelper`` 类下，全部 ``@classmethod``，无实例状态。

> HTML 渲染（思考内容 / 知识库引用）属 ``AgentExecutor`` 流式聚合的内容编码契约，
> 已下沉到 ``AgentExecutor`` 类方法。
"""

from __future__ import annotations

import os
from logging import getLogger
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse

from aidev_agent.packages.resource_manager import ResourceManagerProtocol
from aidev_agent.packages.resource_manager.registry import resource_manager as resource_manager_factory
from django.conf import settings

from aidev_bkplugin.models import Checkpoint, Write
from aidev_bkplugin.packages.checkpoint import BKDjangoSaver

from .agent_config import AgentConfigFetcher

if TYPE_CHECKING:
    from aidev_agent.api.bk_aidev import Client

logger = getLogger(__name__)


class AgentHelper:
    """无状态 helper 集合：按 ``@classmethod`` 暴露 client / 版本 / URL / HTML 工具。"""

    @classmethod
    def get_client(cls, resource_manager: Optional[ResourceManagerProtocol] = None, **kwargs: Any) -> "Client":
        """通过 ``resource_manager.get_client(**kwargs)`` 取 ``Client``。

        替代历史 ``utils.bkaidev_api_client``。``kwargs`` 透传给底层 ``BKAidevApi.get_client``。
        传入 ``resource_manager``（如 view 层的 ``PluginResourceManager(username=...)``）时得到
        用户态 client；不传则回落全局单例，为应用态、不含用户认证，此时用户身份需靠
        ``AGUISessionWriter(..., username=...)`` 等 header 透传。
        """
        resource_manager = resource_manager or resource_manager_factory()
        return resource_manager.get_client(**kwargs)

    @classmethod
    def get_checkpointer(cls):
        """LangGraph 持久化 checkpointer；使用 Django ORM 存储 checkpoint，支持 interrupt/resume。"""
        logger.info("[AgentHelper] get_checkpointer: 创建 BKDjangoSaver 实例")
        return BKDjangoSaver(checkpoint_model=Checkpoint, writes_model=Write)

    @classmethod
    def build_session_detail_url(cls, session_code: str, username: str | None = None) -> str:
        """从 agent 配置 ``saas_url`` 拼小鲸会话详情页 URL。

        返回空串表示无法构建（``session_code`` 为空 / ``saas_url`` 缺失 / 上游异常）。
        """
        if not session_code:
            return ""
        try:
            agent_info = AgentConfigFetcher.get_info(username=username)
            saas_url = agent_info.get("saas_url", "")
            if not saas_url:
                logger.debug(f"[build_session_detail_url] agent 配置中无 saas_url, username={username}")
                return ""
            parsed = urlparse(saas_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            return f"{base_url}/chat-window/?session={session_code}"
        except Exception as e:
            logger.warning(f"[build_session_detail_url] 构建会话详情 URL 失败: session_code={session_code}, error={e}")
            return ""

    @classmethod
    def get_agent_version(cls) -> dict:
        """收集所有以 ``aidev`` 开头的已安装包及版本，并附加 ``VERSION_PATH`` 中的版本号。

        ``pkg_resources`` 延迟 import：仅本方法需要，避免模块加载期对未安装环境强依赖。
        """
        import pkg_resources

        installed_packages = pkg_resources.working_set
        abilities = {package.key: package.version for package in installed_packages if package.key.startswith("aidev")}
        if settings.VERSION_PATH and os.path.isfile(settings.VERSION_PATH):
            with open(settings.VERSION_PATH, "r") as f:
                abilities["version"] = f.read().strip()
        return abilities
