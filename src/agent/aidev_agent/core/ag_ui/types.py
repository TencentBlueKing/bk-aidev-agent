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
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator
from typing_extensions import NotRequired


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
    ArtifactsGenerated = "artifacts_generated"
    AskUserQuestionFinalized = "ask_user_question_finalized"
    UserInputSaved = "user_input_saved"


class ArtifactPayload(TypedDict):
    """轮次产物条目。

    outputId 就是文件在会话 PV 里的 path，前端点击时原样作为
    `pv_files/download_url?path=<outputId>` 的参数换取即时签名 URL。
    """

    outputId: str
    type: str
    name: str
    size: int


class ArtifactsGeneratedValue(TypedDict):
    """`artifacts_generated` CustomEvent 的 value 结构。"""

    runId: str
    status: Literal["complete", "empty"]
    artifacts: list[ArtifactPayload]


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

    # 压缩通知事件（实时 SSE 推送，name=info）
    INFO = "info"


class ExtendBaseMessage(BaseModel):
    status: Literal["complete", "streaming", "pending", "error", "stop"] = "complete"
    created_at: str | None = Field(default=None, description="该条消息的创建时间，仅供 MESSAGES_SNAPSHOT 展示")

    @computed_field
    def message_id(self) -> str:
        return self.id


class ExtendDeveloperMessage(ExtendBaseMessage, DeveloperMessage):
    pass


class ExtendSystemMessage(ExtendBaseMessage, SystemMessage):
    pass


class ExtendAssistantMessage(ExtendBaseMessage, AssistantMessage):
    # 首帧 MESSAGES_SNAPSHOT（历史还原）携带的开放属性字典，与前端 IMessageProperty 契约对齐。
    # 本轮文件产物放在 property["artifacts"]，元素结构与实时 `artifacts_generated` 事件同构
    # （形如 {"outputId","type","name","size"}）；默认 None，无产物的历史消息不受影响。
    property: dict | None = Field(default=None, description="开放属性字典（历史还原用，如 artifacts）")


class ExtendUserMessage(ExtendBaseMessage, UserMessage):
    pass


class ExtendToolMessage(ExtendBaseMessage, ToolMessage):
    duration: float | None = Field(default=None, description="工具调用的耗时")


class ExtendActivityMessage(ExtendBaseMessage, AGUIActivityMessage):
    content: dict[str, Any] | list[dict]


class ExtendInfoMessage(ExtendBaseMessage):
    """AG-UI 侧的系统信息消息（role=info）。

    用于向前端推送系统级提示（如上下文压缩通知），进入 state["messages"]
    供 MESSAGES_SNAPSHOT 重建与前端展示，但不会送入 LLM 输入。
    """

    id: str
    role: Literal["info"] = "info"  # pyright: ignore[reportIncompatibleVariableOverride]
    content: str


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
        | ExtendInfoMessage
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
    next_interrupt: Any = Field(
        default=None,
        description="lw4：resume 未就绪时的下一张 pending 卡（get_resume_input 的 next_interrupt）。"
        "LangGraphAgent.prepare_stream 在 stream_input 为 None 时消费它构造 RUN_FINISHED(interrupt)"
        " 结束事件（events_to_dispatch 快照-结束通道）；ready/普通路径该字段为 None 且不被消费。",
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


class InfoMessage(ChatMessage):
    """系统信息消息（role=info）的 LangChain 消息。

    用于承载系统级提示（如上下文压缩通知），进入 ``state["messages"]`` 供
    MESSAGES_SNAPSHOT 重建与前端展示，但会被 ``basic_middleware`` 按
    ``isinstance(..., InfoMessage)`` 过滤剔除，不会送入 LLM 输入。
    """

    role: str = "info"
    content: str = ""

    @model_validator(mode="before")
    @classmethod
    def _accept_message_id(cls, data: Any) -> Any:
        """允许构造时使用 message_id 作为 id 的别名。

        始终 pop message_id（无论 id 是否已存在），避免从 checkpoint
        恢复时 message_id 残留导致 computed_field 重复输出。
        """
        if isinstance(data, dict) and "message_id" in data:
            if "id" not in data:
                data["id"] = data["message_id"]
            data.pop("message_id", None)
        return data

    @computed_field
    def message_id(self) -> str:
        """序列化时输出蛇形 message_id，与 SSE 流 CustomEvent 中的 messageId 对应。"""
        return self.id


class ReasoningLangChainMessage(ChatMessage):
    """思考过程消息（role=reasoning）的 LangChain 消息。

    用于 DB 历史中的 reasoning 行进入 MESSAGES_SNAPSHOT；在 LLM 入口被过滤，
    不会送入 graph 输入。
    """

    role: Literal["reasoning"] = "reasoning"  # pyright: ignore[reportIncompatibleVariableOverride]
    content: list[str] = Field(default_factory=list)


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
