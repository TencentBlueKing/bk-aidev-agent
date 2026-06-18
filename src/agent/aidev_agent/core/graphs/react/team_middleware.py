# -*- coding: utf-8 -*-
"""Team 中间件，用于 ReAct 图。

使用 AgentSpec + AgentBackend 范式替代旧的 graphs/team + react/subagent 模块。

核心组件：
- TeamInfo: Team 运行时状态的 TypedDict（bk_agent_team）
- TeamPromptMiddleware: 将 Team 成员信息注入 system prompt
- TeamConfig: Team 功能配置容器
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, Dict

from typing_extensions import TypedDict

from aidev_agent.core.nodes.model.pydantic_models import NextFunction, ProcessorContext
from aidev_agent.core.tools.a2a_tools.types import AgentSpec

# =============================================================================
# Data Models
# =============================================================================


class TeamInfo(TypedDict, total=False):
    """Team 运行时状态字段，用于 Member 模式下管理成员 session。

    与 AgentSpec（声明式定义）互补：
    - AgentSpec 描述"可调用的 Agent"（构造 Agent 实例的蓝图）
    - TeamInfo 描述"已实例化的成员管理"（运行时状态，管理成员生命周期）

    bk_agent_team 使用 operator.or_ 作为 reducer，确保 Command.update 中的
    成员信息与已有成员增量合并，而非整体替换。
    """

    bk_agent_team: Annotated[Dict[str, Any], operator.or_]


# =============================================================================
# Middlewares
# =============================================================================


@dataclass
class TeamPromptMiddleware:
    """将 Team 成员信息注入到 system prompt 中（模板管道）。"""

    specs: list[AgentSpec]

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        """Process the context and inject Team member info into system prompt.

        Args:
            ctx: The processor context containing state and prompt_slots.
            next: Function to call the next middleware in the pipeline.
        """
        if not self.specs:
            next()
            return
        parts = [
            "\n\n# Team Members\n",
            "以下 Agent 可通过 Agent 工具调用：\n",
        ]
        for spec in self.specs:
            parts.append(f"  - {spec.name}: {spec.description}\n")
        parts.append("\n调用模式说明：\n")
        parts.append("  - task: 一次性任务模式，Agent 完成任务后返回结果\n")
        parts.append("  - member: 成员模式，支持多轮对话，自动通过 session 保持上下文\n")
        if self.specs:
            parts.append("\n成员模式使用说明：\n")
            parts.append("  - 首次调用成员时使用 Agent 工具（会自动创建会话）\n")
            parts.append("  - 同一个 Agent 可以被实例化多次作为不同成员，通过 member_name 参数区分\n")
            parts.append("  - 后续与成员对话时使用 sendMessages 工具（指定 member_name 即可）\n")
        injection = "".join(parts)
        ctx.prompt_slots.system = (ctx.prompt_slots.system or "") + injection
        next()


@dataclass
class ToolFilterMiddleware:
    """工具过滤中间件 — 深度驱动 + 声明驱动双层过滤。

    Pathway 1 (深度驱动 canSpawn): 当 spawn_depth >= max_spawn_depth 时，
    自动剥离 Agent 类工具（"Agent" 和 "sendMessages"），使 LLM 无法看到/调用。

    Pathway 2 (声明驱动): 父 Agent 通过 tool_deny/tool_allow 声明额外限制。
    - tool_deny: 黑名单，列表中的工具名被移除
    - tool_allow: 白名单，非空时仅保留列表内工具名
    """

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        """Filter tools based on spawn depth and parent-declared deny/allow lists.

        Args:
            ctx: The processor context containing config and tools.
            next: Function to call the next middleware in the pipeline.
        """
        ek = ctx.config.get("configurable", {}).get("execute_kwargs") if isinstance(ctx.config, dict) else None
        if ek is None:
            next()
            return

        tools = ctx.tools

        # Layer 1: 深度驱动 — canSpawn 检查
        if ek.spawn_depth >= ek.max_spawn_depth:
            tools = [t for t in tools if t.name not in ("Agent", "sendMessages")]

        # Layer 2: 声明驱动 — 父 Agent 额外限制
        if ek.tool_deny:
            tools = [t for t in tools if t.name not in ek.tool_deny]
        if ek.tool_allow:
            tools = [t for t in tools if t.name in ek.tool_allow]

        ctx.tools = tools
        next()


# =============================================================================
# Configuration Container
# =============================================================================


@dataclass
class TeamConfig:
    """Configuration container for Team functionality."""

    specs: list[AgentSpec] = field(default_factory=list)
    resolver: Any = None
