from enum import Enum
from typing import Annotated, Any, List, Literal, TypedDict

from ag_ui.core import (
    ActivityMessage as AGUIActivityMessage,
)
from ag_ui.core import (
    AssistantMessage,
    Context,
    DeveloperMessage,
    FunctionCall,
    RunAgentInput,
    SystemMessage,
    Tool,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from ag_ui.core.events import MessagesSnapshotEvent
from ag_ui.core.types import ConfiguredBaseModel
from langchain_core.messages import ChatMessage
from pydantic import BaseModel, Field, computed_field, field_validator
from typing_extensions import Literal, NotRequired


class LangGraphEventTypes(str, Enum):
    OnChainStart = "on_chain_start"
    OnChainStream = "on_chain_stream"
    OnChainEnd = "on_chain_end"
    OnChatModelStart = "on_chat_model_start"
    OnChatModelStream = "on_chat_model_stream"
    OnChatModelEnd = "on_chat_model_end"
    OnToolStart = "on_tool_start"
    OnToolEnd = "on_tool_end"
    OnCustomEvent = "on_custom_event"
    OnInterrupt = "on_interrupt"
    Error = "error"


class CustomEventNames(str, Enum):
    ManuallyEmitMessage = "manually_emit_message"
    ManuallyEmitToolCall = "manually_emit_tool_call"
    ManuallyEmitState = "manually_emit_state"
    Exit = "exit"
    OnToolNodeFinish = "on_tool_node_finish"
    OnToolNodeImmediate = "on_tool_node_immediate"


class SessionPersistenceEventNames(str, Enum):
    """会话回写用 CustomEvent.name；ChatModelEnd 默认不进入 SSE。"""

    ChatModelEnd = "aidev_session_chat_model_end"


State = dict[str, Any]


class SchemaKeys(TypedDict):
    input: NotRequired[list[str] | None]
    output: NotRequired[list[str] | None]
    config: NotRequired[list[str] | None]
    context: NotRequired[list[str] | None]


class ThinkingProcess(TypedDict):
    index: int
    type: NotRequired[Literal["text"] | None]


class MessageInProgress(TypedDict):
    id: str
    tool_call_id: NotRequired[str | None]
    tool_call_name: NotRequired[str | None]


class RunMetadata(TypedDict):
    id: str
    schema_keys: NotRequired[SchemaKeys | None]
    node_name: NotRequired[str | None]
    prev_node_name: NotRequired[str | None]
    exiting_node: NotRequired[bool]
    manually_emitted_state: NotRequired[State | None]
    thread_id: NotRequired[ThinkingProcess | None]
    thinking_process: NotRequired[str | None]
    has_function_streaming: NotRequired[bool]


MessagesInProgressRecord = dict[str, MessageInProgress | None]


class ExtendFunctionCall(FunctionCall):
    description: str | None = None
    mcp_name: str | None = None


class ExtendToolCall(ToolCall):
    function: ExtendFunctionCall


class BaseLangGraphPlatformMessage(TypedDict):
    content: str
    role: str
    additional_kwargs: NotRequired[dict[str, Any]]
    type: str
    id: str


class LangGraphPlatformResultMessage(BaseLangGraphPlatformMessage):
    tool_call_id: str
    name: str


class LangGraphPlatformActionExecutionMessage(BaseLangGraphPlatformMessage):
    tool_calls: list[ExtendToolCall]


LangGraphPlatformMessage = (
    LangGraphPlatformActionExecutionMessage | LangGraphPlatformResultMessage | BaseLangGraphPlatformMessage
)


class PredictStateTool(TypedDict):
    tool: str
    state_key: str
    tool_argument: str


class LangGraphReasoning(TypedDict):
    type: str
    text: str
    index: int


# #######     #
# 以下均为扩展 #
# ######     #


class CustomMessageType(Enum):
    KNOWLEDGE_RAG_START = "knowledge_rag_start"
    KNOWLEDGE_RAG_END = "knowledge_rag_end"
    KNOWLEDGE_RAG_TEXT_CONTENT = "knowledge_rag_text_content"
    KNOWLEDGE_RAG_RESULT = "knowledge_rag_result"
    INTERRUPT = "interrupt"
    CUSTOM = "custom"
    MCP_TOOL_FETCH_FAILED = "mcp_tool_fetch_failed"
    TEMP_MESSAGE = "temp_message"
    APPROVAL_RESULT = "approval_result"

    # Flow Agent 事件
    FLOW_AGENT_START = "flow_agent_start"
    FLOW_AGENT_RESULT = "flow_agent_result"
    FLOW_AGENT_END = "flow_agent_end"
    FLOW_AGENT_RESTART = "flow_agent_restart"
    FLOW_AGENT_UPDATE = "flow_agent_update"

    # 压缩日志事件
    COMPRESS_LOG = "compress_log"


class ExtendBaseMessage(BaseModel):
    status: Literal["complete", "streaming", "pending", "error", "stop"] = "complete"

    @computed_field
    def message_id(self) -> str:
        return self.id


class ExtendDeveloperMessage(ExtendBaseMessage, DeveloperMessage):
    pass


class ExtendSystemMessage(ExtendBaseMessage, SystemMessage):
    pass


class ExtendAssistantMessage(ExtendBaseMessage, AssistantMessage):
    pass


class ExtendUserMessage(ExtendBaseMessage, UserMessage):
    pass


class ExtendToolMessage(ExtendBaseMessage, ToolMessage):
    duration: float | None = Field(default=None, description="工具调用的耗时")


class ExtendActivityMessage(ExtendBaseMessage, AGUIActivityMessage):
    content: dict[str, Any] | list[dict]


class ReasoningMessage(ExtendBaseMessage):
    id: str
    role: Literal["reasoning"] = "reasoning"  # pyright: ignore[reportIncompatibleVariableOverride]
    content: list[str]
    encryptedContent: str | None = None
    duration: float | None = Field(default=None, description="推理过程的耗时")

    @computed_field
    def messageId(self) -> str:
        """对于思考的内容,需要更新一下messageId格式"""
        return f"reasoning-{self.id}"


class ExtendInterruptMessage(ExtendBaseMessage):
    """AG-UI 侧的中断/审批消息（role=interrupt）。

    用于在 MESSAGES_SNAPSHOT 中承载工具审批等中断卡片，content 与落库
    ``role=interrupt`` 会话内容一致（形如 ``{"outcome": {"type": "interrupt", "interrupts": [...]}}``）。
    """

    id: str
    role: Literal["interrupt"] = "interrupt"  # pyright: ignore[reportIncompatibleVariableOverride]
    content: dict[str, Any] | list[dict]
    name: str | None = None


# 扩展 Message 的定义，使用 Annotated 和 Field(discriminator="role") 保持 Pydantic 的鉴别器行为
ExtendMessage = Annotated[
    (
        ExtendDeveloperMessage
        | ExtendSystemMessage
        | ExtendAssistantMessage
        | ExtendUserMessage
        | ExtendToolMessage
        | ExtendActivityMessage
        | ExtendInterruptMessage
        | ReasoningMessage
    ),
    Field(discriminator="role"),
]


class MessageSnapshotEventExtend(MessagesSnapshotEvent):
    messages: list[ExtendMessage]


class ResumeItem(ConfiguredBaseModel):
    """恢复请求项，用于提交中断处理结果"""

    interruptId: str
    status: Literal["resolved", "cancelled"]
    payload: Any | None = None


class AgentInput(RunAgentInput):
    """扩展的 Agent 输入，添加 resume 字段支持中断恢复"""

    thread_id: str
    run_id: str | None = None
    messages: list[ExtendMessage]
    tools: list[Tool] = Field(default_factory=list)
    context: list[Context] = Field(default_factory=list)
    forwarded_props: Any = Field(default_factory=dict)
    resume: list[ResumeItem] | None = Field(default=None, description="中断恢复请求")
    stream_input: Any = Field(
        default=None, description="stream 输入（chat.py 预处理，供 agent.py.prepare_stream 使用）"
    )


class ActivityMessage(ChatMessage):
    """用于指定自定义消息的类"""

    role: str = "activity"
    content: dict | list[dict] = Field(default_factory=dict)


class InterruptMessage(ActivityMessage):
    """承载中断/审批消息（role=interrupt）的 LangChain 消息。

    继承 :class:`ActivityMessage`，以复用 model 节点中间件（``basic_middleware``）
    按 ``isinstance(..., ActivityMessage)`` 进行的过滤逻辑——这样审批卡片虽进入
    ``state["messages"]``（用于 MESSAGES_SNAPSHOT 重建与前端展示），但绝不会被
    送入 LLM 输入，避免污染模型上下文。
    """

    role: str = "interrupt"
    content: dict | list[dict] = Field(default_factory=dict)


class Interrupt(ConfiguredBaseModel):
    """中断信息，用于 RunFinishedInterruptOutcome"""

    id: str
    reason: str
    message: str | None = None
    toolCallId: str | None = None  # 官方协议使用驼峰命名
    metadata: dict[str, Any] | None = None


class RunFinishedOutcomeType(str, Enum):
    """RunFinishedEvent.outcome 的 type 字段取值"""

    SUCCESS = "success"
    INTERRUPT = "interrupt"


def serialize_run_finished_outcome(outcome: Any | None) -> dict[str, Any] | None:
    """将本地 outcome 模型转换为 ag-ui 事件可接受的字典形态。"""

    if outcome is None:
        return None
    if hasattr(outcome, "model_dump"):
        return outcome.model_dump(by_alias=True)
    if isinstance(outcome, dict):
        return outcome
    return dict(outcome)


class RunFinishedSuccessOutcome(ConfiguredBaseModel):
    """运行正常完成的 Outcome"""

    type: Literal["success"] = "success"


class RunFinishedInterruptOutcome(ConfiguredBaseModel):
    """运行被中断暂停的 Outcome"""

    type: Literal["interrupt"] = "interrupt"
    interrupts: List[Interrupt]

    @field_validator("interrupts")
    @classmethod
    def _interrupts_nonempty(cls, value: List[Interrupt]) -> List[Interrupt]:
        if not value:
            raise ValueError("outcome 'interrupt' requires at least one interrupt")
        return value
