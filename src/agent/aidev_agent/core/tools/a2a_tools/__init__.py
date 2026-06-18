# -*- coding: utf-8 -*-
"""A2A 工具模块。

提供 Agent-to-Agent 调用能力，支持 Task（一次性任务）和 Member（多轮对话）两种模式。
Phase 23: 增加可观测性类型导出（ExitReason、AgentResult、progress 工具函数）。
"""

from aidev_agent.core.tools.a2a_tools.bkai_backend import BkAiBackend
from aidev_agent.core.tools.a2a_tools.local_backend import LocalBackend
from aidev_agent.core.tools.a2a_tools.provider import AgentBackendResolver, get_agent_tools
from aidev_agent.core.tools.a2a_tools.types import (
    AgentBackendType,
    AgentSpec,
    ProgressCallback,
)

__all__ = [
    "AgentBackendType",
    "AgentBackendResolver",
    "AgentSpec",
    "BkAiBackend",
    "LocalBackend",
    "ProgressCallback",
    "get_agent_tools",
]
