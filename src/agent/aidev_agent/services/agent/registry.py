# -*- coding: utf-8 -*-
"""Agent 协议与注册中心

统一 Agent 的「构建期」与「运行时」契约，所有 Agent 类型实现 ``AgentProtocol``：
- ``build(ctx)`` 构建期实例方法（种子模式）：调用方先 ``cls()`` 生成空种子
  实例，再 ``seed.build(ctx)`` 在 ``self`` 上原地装配并返回 ``self``。
  要求实现类的所有字段都可空构造（必填字段需放宽为 ``Optional`` 默认 ``None``）。
- ``execute() / stop()`` 运行时方法。

新增 Agent 类型 = 实现 ``AgentProtocol`` 的一个类 +
``agent_registry.register(MyAgent.agent_type, MyAgent)``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Generator, Optional, Protocol, Type

from aidev_agent.enums import AgentType
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.utils.factory import SimpleFactory

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

    from aidev_agent.packages.resource_manager import ResourceManagerProtocol
    from aidev_agent.pydantic_models import AgentConfig
    from aidev_agent.services.common_agent import CommonAgentProtocol


# ============================== 构建期上下文 ==============================


@dataclass
class ChatBuildExtras:
    """Chat agent 构建期专属字段（仅在 ``agent_type == CHAT`` 时填充）"""

    agent_cls: Optional["CommonAgentProtocol"] = None
    callbacks: list[Any] = field(default_factory=list)
    auth_headers: Optional[dict[str, str]] = None
    default_headers: Optional[dict[str, str]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    retry_strategy: Optional[str] = None
    checkpointer: Optional["BaseCheckpointSaver"] = None


@dataclass
class FlowBuildExtras:
    """Flow agent 构建期专属字段（仅在 ``agent_type == FLOW`` 时填充）

    与 ``AgentBuildContext.resource_manager`` 解耦：``flow_resource_manager`` 是 flow
    start 接口专用资源管理器（通常带特殊认证），缺省时由 ``FlowAgentCompletionAgent.build``
    回落到 ``ctx.resource_manager``，最终回落到全局 ``resource_manager()`` 工厂。
    """

    flow_resource_manager: Optional["ResourceManagerProtocol"] = None
    task_id: Optional[str] = None
    flow_start_params: dict = field(default_factory=dict)
    poll_interval: Optional[float] = None
    poll_timeout: Optional[float] = None
    resume_from_node: Optional[str] = None


@dataclass
class AgentBuildContext:
    """Agent 构建期上下文（无 factory 反向引用）

    工厂在 ``_make_build_context`` 时一次性把所有 build 期需要的输入装入；
    ``agent_class().build(ctx)`` 内部仅依赖 ctx 自身字段，不再反向取 factory。

    Attributes:
        agent_code: 当前生效的 agent_code（``_check_agent_switch`` 后的 final）。
        agent_type: Agent 类型；与 ``chat`` / ``flow`` 子对象互斥关系一致，
            便于显式 dispatch。
        agent_config: 主智能体配置（已对应 ``agent_code`` 取回，避免下游重复请求）。
        resource_manager: 通用 API 资源管理器（含 ``get_agent_config`` / ``retrieve_agent_config``
            等业务方法；子 agent_code 的配置取回也通过它）。
        session_code: 会话代码。
        username: 用户名。
        session_context_data: 已清洗的会话上下文（去 system / 不完整 tool_calls
            由 builder 处理）。
        switch_agent: 是否发生命令切换。
        event_handler: AG-UI 事件回写器。
        chat: Chat 专属构建参数（仅 CHAT 类型）。
        flow: Flow 专属构建参数（仅 FLOW 类型）。
        extra: 透传扩展（未来其他 agent_type 用；现有 flow 字段已迁出至 ``flow``）。
    """

    agent_code: str
    agent_type: AgentType
    resource_manager: "ResourceManagerProtocol"
    agent_config: Optional["AgentConfig"] = None
    """主智能体配置（CHAT 路径在 ``_make_build_context`` 时预读；FLOW 路径不依赖配置，
    保持 ``None`` 以避免对未注册 agent_code 的 FLOW 任务发出无意义请求）。
    """
    session_code: Optional[str] = None
    username: Optional[str] = None
    session_context_data: list[dict] = field(default_factory=list)
    switch_agent: bool = False
    event_handler: Optional[Callable] = None
    chat: Optional[ChatBuildExtras] = None
    flow: Optional[FlowBuildExtras] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================== Agent 协议 ==============================


class AgentProtocol(Protocol):
    """Agent 统一协议（覆盖构建与运行时）

    实现者直接是 Agent 类本身（如 ``ChatCompletionAgent`` / ``FlowAgentCompletionAgent``）：
    - 通过实例方法 ``build(ctx)`` 从 ``AgentBuildContext`` 构造 fully-built 实例。
    - 通过 ``execute / stop`` 提供运行时能力。

    协议仅作类型注解用途，不做运行时 ``isinstance`` 校验。
    """

    agent_type: ClassVar[AgentType]

    def build(self, ctx: AgentBuildContext) -> "AgentProtocol":
        """在 ``self``（``cls()`` 空种子实例）上原地装配 fully-built 实例并返回（``return self``）。

        调用约定：先用 ``cls()`` 生成空种子实例，再 ``seed.build(ctx)`` 触发本方法。
        要求实现类的所有字段都可空构造（必填字段需放宽为 ``Optional`` 默认 ``None``），
        并且 pydantic 实现需允许属性赋值（默认即允许，未配置 ``frozen`` /
        ``validate_assignment``）。

        实现内部按需读取 ``ctx`` 的通用字段（``agent_code`` / ``agent_config`` /
        ``resource_manager`` / ``session_code`` / ``username`` 等）与子对象
        （``ctx.chat`` / ``ctx.flow``），原地写到 ``self`` 后 ``return self``。
        """
        ...

    def execute(self, execute_kwargs: ExecuteKwargs | None = None) -> Generator[str, None, None] | str:
        """执行 Agent，流式返回字符串生成器，非流式返回结果"""
        ...

    def stop(self) -> None:
        """停止 Agent 执行"""
        ...


# ============================== 注册中心 ==============================
#
# 直接使用 :class:`aidev_agent.utils.factory.SimpleFactory`，与
# ``aidev_bkplugin/services/factory.py`` 的 ``agent_factory`` 共用同一注册抽象，
# 不再引入项目专属的注册中心子类。
#
# 调用约定：
# - 注册：``agent_registry.register(MyAgent.agent_type, MyAgent)``
# - 取实现类：``agent_registry.must_get(agent_type)``（未注册抛 ``RuntimeError``）；
#   或 ``agent_registry[agent_type]``。``get`` 未注册时返回 Teapot 默认（懒失败语义）。
# - 列已注册类型：``list(agent_registry.keys())`` / ``agent_type in agent_registry``。

agent_registry: SimpleFactory[AgentType, Type[AgentProtocol]] = SimpleFactory("agent")
