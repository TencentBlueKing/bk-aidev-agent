from enum import Enum
from typing import Annotated, Any, Literal, TypedDict

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
from langchain_core.messages import ChatMessage
from pydantic import BaseModel, Field, computed_field
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

    # Flow Agent 事件
    FLOW_AGENT_START = "flow_agent_start"
    FLOW_AGENT_RESULT = "flow_agent_result"
    FLOW_AGENT_END = "flow_agent_end"
    FLOW_AGENT_RESTART = "flow_agent_restart"


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


# 扩展 Message 的定义，使用 Annotated 和 Field(discriminator="role") 保持 Pydantic 的鉴别器行为
ExtendMessage = Annotated[
    (
        ExtendDeveloperMessage
        | ExtendSystemMessage
        | ExtendAssistantMessage
        | ExtendUserMessage
        | ExtendToolMessage
        | ExtendActivityMessage
        | ReasoningMessage
    ),
    Field(discriminator="role"),
]


class MessageSnapshotEventExtend(MessagesSnapshotEvent):
    messages: list[ExtendMessage]


class AgentInput(RunAgentInput):
    thread_id: str | None = None
    run_id: str | None = None
    messages: list[ExtendMessage]
    tools: list[Tool] = Field(default_factory=list)
    context: list[Context] = Field(default_factory=list)
    forwarded_props: Any = Field(default_factory=dict)


class ActivityMessage(ChatMessage):
    """用于指定自定义消息的类"""

    role: str = "activity"
    content: dict | list[dict] = Field(default_factory=dict)
