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
    duration: float | None = Field(default=None, description="工具调用的耗时")
    error: bool | None = Field(default=None, description="工具调用是否出错")


class ExtendThinkingEndEvent(ThinkingEndEvent):
    """扩展 ThinkingEndEvent, 添加 duration 字段"""

    duration: float | None = Field(default=None, description="推理过程的耗时")
