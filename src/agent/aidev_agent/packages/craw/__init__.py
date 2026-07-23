# -*- coding: utf-8 -*-
"""Craw 适配层：CLI 形态 Agent 内核（OpenClaw / Hermes / …）的统一接入。

Craw = 以本机 API 服务（localhost / 同容器 / 同 Pod）形态运行的 CLI Agent
内核。本包提供两条链路的 SDK 组件：

1. **Proxy（对话转发）**：``CrawCompletionAgent`` 实现 ``AgentProtocol``，
   把 AIDEV 的 CHAT 执行转发给 craw 的 OpenAI 兼容 ``/v1/chat/completions``，
   SSE 翻译成 AG-UI 事件；``enable_chat_takeover()`` env 门控接管
   （``BKAI_CRAW_BACKEND=openclaw|hermes``，未设零影响）。
2. **周期读写**：``CrawSyncer`` 周期任务——read（health / 状态文件）+
   write（把平台 Agent 定义 Prompt / MCP / Skills 下发到 craw home，读回
   校验）。最小形态只下发人设 ``SOUL.md``；``agent_config_to_artifacts``
   可把平台 ``AgentConfig`` 渲染成整组产物。

用户 Token 隔离：``CrawIdentity`` 携带 username + access_token，
``X-Bkai-Access-Token`` 头透传给 craw 侧（对齐 bkai-cli 池模式反代契约，
由前置反代做每用户内核 / MCP 凭证隔离）；本层日志只落
``identity_id``（sha256 前 16 位），绝不落原始 token。

新增内核 = 继承 ``BaseCrawBackend`` 覆写差异点 +
``craw_backend_registry.register(name, MyBackend)``。
"""

from aidev_agent.packages.craw.agent import CrawCompletionAgent
from aidev_agent.packages.craw.base import BaseCrawBackend, CrawIdentity, CrawIdentityError, CrawUpstreamError
from aidev_agent.packages.craw.hermes import HermesBackend
from aidev_agent.packages.craw.openclaw import OpenClawBackend
from aidev_agent.packages.craw.registry import CrawBackendProtocol, craw_backend_registry, get_backend
from aidev_agent.packages.craw.sync import (
    CrawSyncer,
    CrawSyncResult,
    agent_config_to_artifacts,
    render_soul,
)
from aidev_agent.packages.craw.takeover import enable_chat_takeover

craw_backend_registry.register(OpenClawBackend.name, OpenClawBackend)
craw_backend_registry.register(HermesBackend.name, HermesBackend)

__all__ = [
    "BaseCrawBackend",
    "CrawBackendProtocol",
    "CrawCompletionAgent",
    "CrawIdentity",
    "CrawIdentityError",
    "CrawSyncResult",
    "CrawSyncer",
    "CrawUpstreamError",
    "HermesBackend",
    "OpenClawBackend",
    "agent_config_to_artifacts",
    "craw_backend_registry",
    "enable_chat_takeover",
    "get_backend",
    "render_soul",
]
