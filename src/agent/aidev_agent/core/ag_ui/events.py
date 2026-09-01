from ag_ui.core.events import ThinkingEndEvent, ToolCallResultEvent, ToolCallStartEvent
from pydantic import BaseModel, Field


class McpToolFetchFailedPayload(BaseModel):
    """MCP 工具拉取失败事件的 payload，用于 CUSTOM 事件 value"""

    server_name: str = Field(..., description="失败的 MCP 服务器名")
    message: str = Field(..., description="错误信息")
    error_type: str | None = Field(default=None, description="可选，异常类型名")


class ExtendToolCallStartEvent(ToolCallStartEvent):
    description: str | None = None
    mcp_name: str | None = Field(default=None, description="工具调用的模型名称")


class ExtendToolCallResultEvent(ToolCallResultEvent):
    tool_call_name: str | None = Field(default=None, description="工具名，供无 START 事件的恢复流展示")
    duration: float | None = Field(default=None, description="工具调用的耗时")
    is_error: bool | None = Field(default=None, description="工具调用是否出错")
    additional_metadata: dict | None = Field(
        default=None, description="完整 additional_kwargs dict，含 duration/description/tool_approval 等"
    )
    skip_db: bool = Field(default=False, description="子 Agent 中间步骤标记，DB 侧检查后跳过写入")


class ExtendThinkingEndEvent(ThinkingEndEvent):
    """扩展 ThinkingEndEvent, 添加 duration 字段"""

    duration: float | None = Field(default=None, description="推理过程的耗时")
