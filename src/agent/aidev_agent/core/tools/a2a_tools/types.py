# -*- coding: utf-8 -*-
"""A2A Agent 统一类型定义。

以 AgentSpec + AgentBackend 为核心的多智能体范式。

该模块包含：
- AgentBackendType: Agent 后端类型枚举（BKAI / LOCAL / ACP / A2A）
- ExitReason: 子 Agent 退出原因分类枚举（Phase 23）
- AgentSpec: 统一的声明式 Agent 定义
- AgentBackend: Agent 后端执行合约 Protocol（Phase 23 扩展 progress_callback）
- AgentResult: 标准化富结果不可变 BaseModel（Phase 26）
- SubAgentConfig: 旧版子 Agent 配置（过渡期保留）
- AgentToolInput / SendMessageInput: 工具入参模型

注意：AgentSpec.params 接受任意 key-value，每个 key 的验证由 AgentBackend
实现负责。params 不应包含可执行代码或敏感凭证（如 API key）。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class AgentBackendType(str, Enum):
    """Agent 后端类型标识符。"""

    BKAI = "bkai"
    """远程蓝鲸智能体。"""

    LOCAL = "local"
    """本地智能体（Fork 自身）。"""

    ACP = "acp"
    """ACP 协议客户端（ndJSON over stdio）。"""

    A2A = "a2a"
    """A2A 协议客户端（HTTP/JSON-RPC 传输）。"""


class ExitReason(str, Enum):
    """子 Agent 退出原因分类枚举。值可序列化为 JSON 字符串。"""

    COMPLETED = "completed"
    """正常完成。"""

    TIMEOUT = "timeout"
    """执行超时。"""

    MAX_ITERATIONS = "max_iterations"
    """达到最大迭代次数。"""

    INTERRUPTED = "interrupted"
    """被外部中断。"""

    CREDENTIAL_ERROR = "credential_error"
    """鉴权凭证错误。"""

    BACKEND_ERROR = "backend_error"
    """后端通用错误。"""


ProgressCallback = Callable[..., None]
"""进度回调类型别名。签名: cb(event_type: str, **kwargs: Any) -> None"""

# ── bk_agent_team state JSON 字段键常量 ──
# 由 provider.py 和 agent_tool.py 共享引用，消除隐式字符串契约。
# 迁移自 nodes/tool/team_wrapper.py（Phase 28）。
KEY_SESSION_CODE: str = "session_code"
KEY_MEMBER_NAME: str = "member_name"
KEY_AGENT_NAME: str = "agent_name"
KEY_STATUS: str = "status"
KEY_EXIT_REASON: str = "exit_reason"
KEY_TOOL_CALLS: str = "tool_calls"

# Agent 工具名常量。迁移自 nodes/tool/team_wrapper.py（Phase 28, D-11）。
# A2AAgentTool 不需要运行时判断工具名（自身就是 Agent 工具子类），
# 但保留此常量供其他模块引用。
AGENT_TOOL_NAME: str = "Agent"


class AgentSpec(BaseModel):
    """统一的声明式 Agent 定义。

    统一的 Agent 定义，替代原 core/tools/a2a_tools/models.py 中的 SubAgentConfig。

    所有现有 Agent 定义中的信息都可通过 AgentSpec 无损表达。
    """

    name: str = Field(description="Agent 的唯一名称标识")
    description: str = Field(description="Agent 的能力描述，帮助 LLM 判断何时调用")
    backend_type: AgentBackendType = Field(description="后端类型，决定如何执行此 Agent")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "后端特定参数，如 agent_code（BKAI）、prompt_overrides（LOCAL）等。params 不应包含可执行代码或敏感凭证。"
        ),
    )
    timeout_seconds: int = Field(default=300, description="执行超时秒数")

    model_config = ConfigDict(use_enum_values=True)


@runtime_checkable
class AgentBackend(Protocol):
    """Agent 后端执行合约。

    每种后端类型需实现此 Protocol。具体实现放在对应层级（services 或 graphs），
    不放在 tools 层。

    Phase 23: execute() 增加 progress_callback 可选参数，入参为 None 时
    后端以缺省方式收集执行指标。

    Args:
        spec: 要执行的 Agent 规格
        message: 发送给 Agent 的消息/任务描述
        session_code: 可选，会话标识；空字符串为 task 模式
        progress_callback: 可选，进度回调函数
        **kwargs: 后端特定的额外参数

    Returns:
        AgentResult 标准化富结果（阶段 26：frozen BaseModel）
    """

    def new_session(self, spec: AgentSpec, **kwargs: Any) -> str:
        """创建新会话并返回 session_code。

        Backend 自行管理 session 的创建方式：
        - Local / Bkai / A2A: 返回 uuid4().hex
        - ACP: 通过 spawn_agent_process 调用 ACP 协议创建会话，返回 ACP session_id

        Args:
            spec: Agent 规格
            **kwargs: 后端特定的额外参数（如 ACP 的 command, args, cwd, env）

        Returns:
            session_code 字符串
        """
        ...

    def execute(
        self,
        spec: AgentSpec,
        message: str,
        *,
        session_code: str = "",
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """执行 Agent 调用（task / member 统一入口）。

        Args:
            spec: 要执行的 Agent 规格
            message: 发送给 Agent 的消息/任务描述
            session_code: 可选，会话标识；空字符串为 task 模式，非空为 member 模式
            progress_callback: 可选，进度回调函数；None 时后端以缺省方式收集指标
            **kwargs: 后端特定的额外参数

        Returns:
            AgentResult 标准化富结果（不可变 Pydantic 模型）
        """
        ...


class SubAgentConfig(BaseModel):
    """子 Agent 配置信息（过渡期保留）。

    描述一个可被父 Agent 调用的子 Agent 的基本信息和行为配置。
    新代码应直接使用 AgentSpec，此类仅用于向后兼容。
    """

    name: str = Field(..., description="子 Agent 的显示名称，LLM 在工具调用时使用此名称选择 Agent")
    agent_code: str = Field(..., description="Agent 在平台上的唯一标识，用于通过 AgentInstanceFactory 构建 Agent")
    description: str = Field(..., description="Agent 的能力描述，帮助 LLM 判断何时应调用此 Agent")
    mode: Literal["task", "member"] = Field(
        default="task",
        description="调用模式：'task'（一次性任务）或 'member'（多轮对话成员）",
    )
    # 可选的构建参数覆盖
    temperature: Optional[float] = Field(default=None, description="覆盖子 Agent 的模型温度")
    max_tokens: Optional[int] = Field(default=None, description="覆盖子 Agent 的最大回复长度")
    timeout_seconds: int = Field(default=300, description="Task 模式下的超时秒数")

    def to_agent_spec(self) -> AgentSpec:
        """将 SubAgentConfig 转换为统一的 AgentSpec。

        SubAgentConfig 总是映射到 BKAI 后端，因为它的 agent_code 是蓝鲸平台标识。

        Returns:
            对应的 AgentSpec 实例
        """
        return AgentSpec(
            name=self.name,
            description=self.description,
            backend_type=AgentBackendType.BKAI,
            params={
                "agent_code": self.agent_code,
                **({"temperature": self.temperature} if self.temperature is not None else {}),
                **({"max_tokens": self.max_tokens} if self.max_tokens is not None else {}),
            },
            timeout_seconds=self.timeout_seconds,
        )


class AgentResult(BaseModel):
    """Agent 后端标准化富结果。不可变，可序列化。

    阶段 26：从 TypedDict 重写为 frozen Pydantic BaseModel（D-01）。
    精简为 5 个字段（D-02）：status / result / error / tool_calls / exit_reason。
    duration_seconds 已由 timer_wrapper 在 ToolNode 层统一记录，无需冗余。
    agent_type 标识智能体的后端类型（bkai / local），用于前端展示。

    session_code / member_name / agent_name 是 provider 层概念，
    不包含在此模型中（D-02 / D-06）。
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    status: Literal["completed", "failed", "interrupted"] = Field(
        description="执行状态：completed / failed / interrupted"
    )
    agent_type: str = Field(default="", description="智能体后端类型标识（如 bkai / local）")
    result: str = Field(default="", description="完成时的文本结果")
    error: str | None = Field(default=None, description="失败时的错误信息")
    tool_calls: int = Field(default=0, description="工具调用次数")
    exit_reason: ExitReason = Field(
        default=ExitReason.COMPLETED,
        description="退出原因（ExitReason 枚举值，经 use_enum_values=True 序列化为字符串）",
    )


class AgentToolInput(BaseModel):
    """Agent 工具的输入参数模型。

    LLM 调用 Agent 工具时需要提供的参数。
    """

    agent_name: str = Field(
        ...,
        description="要调用的 Agent 名称，必须是已注册的子 Agent 之一",
    )
    message: str = Field(
        ...,
        description="发送给 Agent 的消息/任务描述",
    )
    mode: Optional[str] = Field(
        default=None,
        description=(
            "调用模式：'task' 或 'member'。"
            "task: 创建一次性任务，等待完成后返回结果；"
            "member: 创建/复用会话成员，支持多轮对话。"
            "不传则默认为 task 模式。"
        ),
    )
    member_name: Optional[str] = Field(
        default=None,
        description=(
            "成员实例名称，仅在 member 模式下使用。"
            "同一个 Agent 可以被实例化多次作为不同成员，通过 member_name 区分。"
            "不传则默认使用 agent_name 作为 member_name。"
        ),
    )


class SendMessageInput(BaseModel):
    """sendMessages 工具的输入参数模型。"""

    member_name: str = Field(
        ...,
        description=("要发送消息的成员实例名称。同一个 Agent 可以被实例化多次，通过 member_name 区分不同实例。"),
    )
    message: str = Field(
        ...,
        description="发送给成员 Agent 的消息内容",
    )
