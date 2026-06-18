# -*- coding: utf-8 -*-
"""A2A Agent Provider 层。

提供 AgentBackendResolver（后端注册与解析）和 get_agent_tools（工具生成）。
基于 AgentSpec 声明式定义，通过注册制解析后端类型，生成 LangGraph Tool。

重构自原 tool.py，核心变化：
- AgentBackendResolver 替代硬编码的执行逻辑
- get_agent_tools 接受 AgentSpec 列表而非 SubAgentConfig 列表
- 具体后端执行逻辑由 AgentBackend 实现类负责（Phase 6 实现）
"""

import json
import logging
import uuid
from typing import Annotated, Any

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import InjectedState, ToolRuntime

from aidev_agent.core.ag_ui.types import CustomEventNames
from aidev_agent.core.tools.a2a_tools.agent_tool import A2AAgentTool
from aidev_agent.core.tools.a2a_tools.types import (
    AgentBackend,
    AgentSpec,
    AgentToolInput,
    ExitReason,
    SendMessageInput,
)

logger = logging.getLogger("aidev-agent")


class AgentBackendResolver:
    """Agent 后端注册与解析器。

    通过注册制管理 AgentBackend 类型，新增后端类型只需调用 register()，
    无需修改 resolve() 逻辑。
    """

    def __init__(self) -> None:
        self._backends: dict[str, type[AgentBackend]] = {}

    def register(self, backend_type: str, backend_cls: type[AgentBackend]) -> "AgentBackendResolver":
        """注册后端类型。

        Args:
            backend_type: 后端类型标识（如 "bkai"、"local"）
            backend_cls: 后端实现类

        Returns:
            self（便于链式调用）

        Raises:
            ValueError: 当 backend_type 为空字符串时
        """
        if not backend_type:
            raise ValueError("backend_type must be non-empty")
        self._backends[backend_type] = backend_cls
        return self

    def resolve(self, spec: AgentSpec) -> AgentBackend:
        """根据 AgentSpec 的 backend_type 解析并实例化后端。

        Args:
            spec: Agent 规格，包含 backend_type 字段

        Returns:
            AgentBackend 实例

        Raises:
            ValueError: 当 backend_type 未注册时
        """
        backend_type = spec.backend_type
        if backend_type not in self._backends:
            available = ", ".join(sorted(self._backends.keys())) or "(none)"
            raise ValueError(f"Unknown backend type '{backend_type}'. Available: {available}")
        return self._backends[backend_type]()


def _build_tool_description(specs: list[AgentSpec]) -> str:
    """动态生成工具描述，包含可用 Agent 列表及能力说明。

    Args:
        specs: Agent 规格列表

    Returns:
        工具描述字符串
    """
    lines = [
        "调用子 Agent 执行任务或进行对话。",
        "",
        "可用的 Agent 列表：",
    ]
    for spec in specs:
        lines.append(f"  - {spec.name}: {spec.description}")
    lines.extend(
        [
            "",
            "调用模式说明：",
            "  - task: 一次性任务模式，Agent 完成任务后返回结果",
            "  - member: 成员模式，支持多轮对话，自动通过 session 保持上下文",
        ]
    )
    return "\n".join(lines)


def _find_agent_spec(specs: list[AgentSpec], agent_name: str) -> AgentSpec | None:
    """根据名称查找 Agent 规格。

    Args:
        specs: Agent 规格列表
        agent_name: 要查找的 Agent 名称

    Returns:
        匹配的 AgentSpec，未找到返回 None
    """
    for spec in specs:
        if spec.name == agent_name:
            return spec
    return None


def _check_nesting(config: RunnableConfig | None) -> bool:
    """检查是否已达到最大嵌套深度。

    从 ``configurable.execute_kwargs`` 中读取 ``spawn_depth`` 和 ``max_spawn_depth``，
    当 ``spawn_depth >= max_spawn_depth`` 时返回 True（禁止再创建子 Agent）。

    Args:
        config: 运行时配置

    Returns:
        True 表示已达到最大嵌套深度，不允许再创建子 Agent
    """
    if config is None or not isinstance(config, dict):
        return False
    ek = config.get("configurable", {}).get("execute_kwargs")
    if ek and hasattr(ek, "spawn_depth") and hasattr(ek, "max_spawn_depth"):
        return ek.spawn_depth >= ek.max_spawn_depth
    return False


def _check_interrupt(config: RunnableConfig | None) -> bool:
    """检查是否通过 configurable._interrupt_requested 请求了中断。

    按 D-03：中断信号由外部在 config.configurable._interrupt_requested 中设置。
    此函数仅读取标志；设置标志的机制不在本阶段范围内。

    Args:
        config: 运行时配置，可能包含 configurable._interrupt_requested

    Returns:
        如果已请求中断则返回 True
    """
    if config is None:
        return False
    if isinstance(config, dict):
        return bool(config.get("configurable", {}).get("_interrupt_requested", False))
    return False


def _extract_progress_callback(config: RunnableConfig | None) -> Any | None:
    """从 config.configurable 中提取 progress_callback（如果存在）。

    Phase 23 定义了 ProgressCallback 类型，AgentBackend Protocol 接受它，
    但 provider.py 从未将其传递下去。此函数从 config 中提取 callback，
    以便注入到 backend.execute() 调用。

    如果不存在则返回 None — 后端会将 None 视为 no-op（跳过心跳）。

    Args:
        config: 运行时配置，可能包含 configurable.progress_callback

    Returns:
        可调用对象或 None
    """
    if config is None:
        return None
    if isinstance(config, dict):
        return config.get("configurable", {}).get("progress_callback")
    return None


def _make_progress_callback(
    raw_progress_callback: Any | None,
    tool_call_id: str,
    dispatch_config: RunnableConfig,
) -> Any:
    """构造 progress_callback 闭包，将 intermediate_steps 事件 dispatch 到前端。

    当 type="subagent.intermediate_steps" 时，构造 ToolMessage 并通过
    dispatch_custom_event("on_tool_node_immediate") 发送到前端（不触发 DB 写入）。
    其他类型（如 subagent.heartbeat）透传给原始 raw_progress_callback。

    Args:
        raw_progress_callback: 原始心跳回调（可能为 None）
        tool_call_id: 当前工具调用的 ID，用于构造 ToolMessage
        dispatch_config: 用于 dispatch_custom_event 的 config

    Returns:
        包装后的 progress_callback 可调用对象
    """

    def progress_callback(type: str, content: str = "", **kwargs: Any) -> None:
        if type == "subagent.intermediate_steps" and content:
            msg = ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
                id=uuid.uuid4().hex,
                name="Agent",
            )
            dispatch_custom_event(
                CustomEventNames.OnToolNodeImmediate.value,
                data=msg,
                config=dispatch_config,
            )
        if raw_progress_callback is not None:
            raw_progress_callback(type, content=content, **kwargs)

    return progress_callback


def get_agent_tools(
    specs: list[AgentSpec],
    resolver: AgentBackendResolver,
) -> list[StructuredTool]:
    """创建 A2A Agent 调用工具。

    工厂函数，接收 AgentSpec 列表和后端解析器，返回一个名为 "Agent" 的 StructuredTool。
    该工具支持 Task 和 Member 两种调用模式。
    当存在 member 模式 spec 时，额外返回 sendMessages 工具。

    Args:
        specs: 已注册的 Agent 规格列表
        resolver: 后端解析器，用于根据 spec.backend_type 路由到具体后端

    Returns:
        包含 "Agent" 工具的列表；若有 member 模式 spec，还包含 "sendMessages" 工具。
        specs 为空时返回空列表
    """
    if not specs:
        return []

    def agent_call(
        *,
        agent_name: str,
        message: str,
        mode: str = "task",
        member_name: str = "",
        config: RunnableConfig,
        state: Annotated[dict[str, Any], InjectedState] = None,  # type: ignore[assignment]
        tool_runtime: ToolRuntime = None,
    ) -> str:
        """调用子 Agent 执行任务或进行对话。"""
        # 1. 嵌套保护
        if _check_nesting(config):
            raise RuntimeError("已达到最大嵌套深度，不允许再创建子 Agent")

        # 2. 查找目标 Agent 规格
        spec = _find_agent_spec(specs, agent_name)
        if spec is None:
            available_names = [s.name for s in specs]
            raise ValueError(f"未知的 Agent: {agent_name}。可用的 Agent: {', '.join(available_names)}")

        # 3. 确定调用模式
        effective_mode = mode or "task"
        if effective_mode not in ("task", "member"):
            raise ValueError(f"不支持的调用模式: {effective_mode}。支持 'task' 或 'member'")

        # 4. 通过 resolver 解析后端
        backend = resolver.resolve(spec)

        # 5. 根据模式构造 session_code 和响应额外字段
        extra_response_fields: dict[str, str] = {}
        if effective_mode == "member":
            effective_member_name = member_name or agent_name
            team_info: Any | dict[Any, Any] = (state or {}).get("bk_agent_team", {}) if state else {}
            member_info = team_info.get(effective_member_name, {})
            session_code = member_info.get("session_code", "")
            if not session_code:
                session_code = backend.new_session(spec)
            extra_response_fields = {"session_code": session_code, "member_name": effective_member_name}
        else:
            session_code = backend.new_session(spec)

        # 6. 中断信号检查（D-03）
        raw_progress_callback = _extract_progress_callback(config)
        if _check_interrupt(config):
            result = {
                "status": "interrupted",
                "agent_name": agent_name,
                "exit_reason": ExitReason.INTERRUPTED.value,
                "error": "执行已被外部请求中断",
                "api_calls": 0,
                "duration_seconds": 0,
            }
            result.update(extra_response_fields)
            return json.dumps(result, ensure_ascii=False)

        # 7. 构造 progress_callback 闭包：intermediate_steps → dispatch_custom_event
        progress_callback = _make_progress_callback(
            raw_progress_callback=raw_progress_callback,
            tool_call_id=tool_runtime.tool_call_id if tool_runtime else "",
            dispatch_config=tool_runtime.config if tool_runtime else config,
        )

        # 8. 执行后端 + 包装结果
        backend_result = backend.execute(
            spec,
            message,
            session_code=session_code,
            config=config,
            progress_callback=progress_callback,
            state=state,
        )
        wrapper = backend_result.model_dump()
        wrapper["agent_name"] = agent_name
        wrapper.update(extra_response_fields)
        return json.dumps(wrapper, ensure_ascii=False)

    def send_messages(
        member_name: str,
        message: str,
        config: RunnableConfig | None = None,
        state: Annotated[dict[str, Any], InjectedState] = None,  # type: ignore[assignment]
        tool_runtime: ToolRuntime = None,
    ) -> str:
        """向已初始化的成员 Agent 发送消息（仅 member 模式）。"""
        # 0. 嵌套保护（CR #5：send_messages 不再是旁路入口，与 agent_call 对齐）
        if _check_nesting(config):
            return json.dumps(
                {
                    "status": "failed",
                    "agent_name": member_name,
                    "exit_reason": ExitReason.BACKEND_ERROR.value,
                    "error": "已达到最大嵌套深度，不允许再创建子 Agent",
                    "api_calls": 0,
                    "duration_seconds": 0,
                },
                ensure_ascii=False,
            )

        # 1. 从 state 获取 session_code
        team_info = (state or {}).get("bk_agent_team", {}) if state else {}
        member = team_info.get(member_name, {})
        session_code = member.get("session_code", "")
        if not session_code:
            return json.dumps(
                {
                    "status": "failed",
                    "error": f"成员 '{member_name}' 尚未初始化，请先用 Agent 工具创建成员",
                },
                ensure_ascii=False,
            )

        # 2. 通过 member 的 agent_name 查找 spec
        agent_name = member.get("agent_name", member_name)
        spec = _find_agent_spec(specs, agent_name)
        if spec is None:
            return json.dumps(
                {
                    "status": "failed",
                    "error": f"未知的 Agent: {agent_name}",
                },
                ensure_ascii=False,
            )

        # 3. 调用 backend.execute
        backend = resolver.resolve(spec)

        # 3.1 构造 progress_callback 闭包（与 agent_call 一致：intermediate_steps → dispatch_custom_event）
        raw_progress_callback = _extract_progress_callback(config)
        progress_callback = _make_progress_callback(
            raw_progress_callback=raw_progress_callback,
            tool_call_id=tool_runtime.tool_call_id if tool_runtime else "",
            dispatch_config=tool_runtime.config if tool_runtime else config,
        )

        backend_result = backend.execute(
            spec,
            message,
            session_code=session_code,
            config=config,
            progress_callback=progress_callback,
            state=state,
        )
        return json.dumps(backend_result.model_dump(), ensure_ascii=False)

    description = _build_tool_description(specs)

    agent_tool = A2AAgentTool.from_function(
        func=agent_call,
        name="Agent",
        description=description,
        args_schema=AgentToolInput,
        metadata={"tool_name": "智能体调用"},
    )
    tools: list[StructuredTool] = [agent_tool]

    # sendMessages 工具（mode 由运行时决定，任何 Agent 均可能以 member 模式调用）
    send_msg_tool = StructuredTool.from_function(
        func=send_messages,
        name="sendMessages",
        description=(
            "向已初始化的成员 Agent 发送消息（仅 member 模式）。"
            "首次调用成员需先使用 Agent 工具。"
            "使用 member_name 指定目标成员实例。"
        ),
        args_schema=SendMessageInput,
    )
    tools.append(send_msg_tool)

    return tools
