# -*- coding: utf-8 -*-
import uuid
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Any, Callable

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    EventType,
    RawEvent,
    RunAgentInput,
    RunErrorEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.graph.state import CompiledStateGraph

from aidev_agent.exceptions import extract_model_error_message

from .agent import LangGraphAGUIAgent
from .events import (
    ExtendToolCallResultEvent,
    ExtendToolCallStartEvent,
)
from .types import CustomMessageType, MessagesInProgressRecord

logger = getLogger(__name__)


class EventDispatcher:
    """事件分发器，用于处理不同类型事件的分发逻辑"""

    def __init__(self, agent: "AidevAGUIAgent"):
        self.agent = agent
        self._dispatch_handlers = {
            EventType.RAW: self._handle_raw_event,
            EventType.CUSTOM: self._handle_custom_event,
            EventType.TOOL_CALL_START: self._handle_tool_call_start,
        }

    def dispatch(self, event: BaseEvent) -> str:
        """根据事件类型调用对应的处理方法"""
        handler = self._dispatch_handlers.get(event.type)
        if handler:
            return handler(event)
        return self.agent._parent_dispatch(event)

    def _handle_raw_event(self, event: RawEvent) -> str:
        """处理 RAW 事件"""
        event_name = event.event.get("name", "")

        raw_event_handlers = {
            "on_tool_node_finish": self._handle_tool_node_finish,
            "on_tool_node_start": self._handle_tool_node_start,
            CustomMessageType.KNOWLEDGE_RAG_RESULT.value: self._handle_reference_document_raw,
        }

        handler = raw_event_handlers.get(event_name)
        if handler:
            return handler(event)
        return self.agent._parent_dispatch(event)

    def _handle_tool_node_finish(self, event: RawEvent) -> str:
        """处理工具节点完成事件"""
        tool_msg = event.event.get("data")
        is_error = getattr(tool_msg, "status", None) == "error" or bool(getattr(tool_msg, "error", None))
        return self.agent._parent_dispatch(
            ExtendToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                tool_call_id=tool_msg.tool_call_id,
                message_id=tool_msg.id or str(uuid.uuid4()),
                content=tool_msg.content,
                role="tool",
                duration=tool_msg.additional_kwargs.get("duration", None),
                error=is_error,
            )
        )

    def _handle_tool_node_start(self, event: RawEvent) -> str:
        """处理工具节点开始事件"""
        # 当前不处理，直接返回
        return ""

    def _handle_custom_event(self, event: CustomEvent) -> str:
        """处理自定义事件"""
        custom_event_handlers = {
            CustomMessageType.KNOWLEDGE_RAG_RESULT.value: self._handle_reference_document,
        }

        handler = custom_event_handlers.get(event.name)
        if handler:
            return handler(event)
        return self.agent._parent_dispatch(event)

    def _handle_reference_document(self, event: CustomEvent) -> str:
        """处理引用文档事件（CustomEvent 格式）"""
        value = event.raw_event.get("data", {}).get("data", [])
        return self.agent._parent_dispatch(
            CustomEvent(type=EventType.CUSTOM, name=event.raw_event.get("name"), value=value)
        )

    def _handle_reference_document_raw(self, event: RawEvent) -> str:
        """处理引用文档事件（RawEvent 格式）

        将 LangGraph 的 on_custom_event 原始事件转换为标准的 RawEvent 继续传递给 BaseSessionWriter
        """
        # 直接传递 RawEvent，让 BaseSessionWriter 处理
        return self.agent._parent_dispatch(event)

    def _handle_tool_call_start(self, event: ToolCallStartEvent) -> str:
        """处理工具调用开始事件，添加描述信息"""
        _tool = self.agent._tool_mapping.get(event.tool_call_name, None)
        _event = ExtendToolCallStartEvent(
            **{
                **event.model_dump(),
                "description": _tool.description if _tool else "",
                "mcp_name": _tool.metadata.get("mcp_name") if _tool and _tool.metadata else "",
            }
        )
        return self.agent._parent_dispatch(_event)


class AidevAGUIAgent(LangGraphAGUIAgent):
    """实现了对自定义事件处理的 AI 辅助 Agent

    事件处理机制：
    1. event_handler: 通用事件钩子，接收所有 BaseEvent，用于 BaseSessionWriter 等外部处理器
    2. EventDispatcher: 内部事件分发器，处理特定事件类型的转换（如工具事件）
    3. cancel_checker: 取消检测回调，返回 True 表示应该取消，Agent 会优雅地发送 RunFinishedEvent

    注意：BaseSessionWriter 已实现完整的事件分发逻辑，会自行处理 RAW/RUN_ERROR 等事件类型
    """

    def __init__(
        self,
        *,
        name: str,
        graph: CompiledStateGraph[Any, None, Any, Any],
        description: str | None = None,
        config: RunnableConfig | None | MessagesInProgressRecord = None,
        tools: dict[str, StructuredTool] | None = None,
        event_handler: Callable[[BaseEvent], None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
        mcp_fetch_failures: list[dict] | None = None,
    ):
        super().__init__(name=name, graph=graph, description=description, config=config, cancel_checker=cancel_checker)
        self._tool_mapping = tools or {}
        self._event_handler = event_handler
        self._event_dispatcher = EventDispatcher(self)
        self._mcp_fetch_failures = mcp_fetch_failures or []

    @staticmethod
    def _format_mcp_fetch_failure_message(failures: list[dict[str, Any]]) -> str:
        """将 MCP 拉取失败列表格式化为一条临时错误消息。"""
        lines = []
        for failure in failures:
            server_name = failure.get("server_name") or "unknown"
            message = failure.get("message") or "MCP tool fetch failed"
            lines.append(f"[{server_name}] {message}")
        return "\n".join(lines)

    async def run(self, input: RunAgentInput) -> AsyncGenerator[str, None]:
        """运行 Agent 并生成编码后的事件流"""
        event_encoder = EventEncoder()
        temp_message_emitted = False
        async for event in super().run(input):
            try:
                # 特殊处理：不输出 message snapshot 事件
                if getattr(event, "type", "") == EventType.MESSAGES_SNAPSHOT.value:
                    logger.debug(f"message snapshot: {event}")
                else:
                    yield event_encoder.encode(event)

                # MCP 工具拉取失败消息需要紧跟在 RUN_STARTED 后返回
                if (
                    not temp_message_emitted
                    and getattr(event, "type", "") == EventType.RUN_STARTED.value
                    and self._mcp_fetch_failures
                ):
                    custom_event = CustomEvent(
                        type=EventType.CUSTOM,
                        name=CustomMessageType.TEMP_MESSAGE.value,
                        value={
                            "message": self._format_mcp_fetch_failure_message(self._mcp_fetch_failures),
                            "status": "error",
                        },
                    )
                    self._dispatch_event(custom_event)
                    yield event_encoder.encode(custom_event)
                    temp_message_emitted = True
            except Exception as e:
                logger.exception(f"Failed to encode event: {e}")
                raise e

    def _dispatch_event(self, event: BaseEvent) -> str:
        """分发事件，使用 EventDispatcher 处理不同类型的事件"""
        # 触发外部事件处理器（如 BaseSessionWriter）
        if self._event_handler:
            try:
                self._event_handler(event)
            except Exception as e:
                logger.exception(f"Event handler failed: {e}")

        return self._event_dispatcher.dispatch(event)

    def _parent_dispatch(self, event: BaseEvent) -> str:
        """调用父类的事件分发方法"""
        return super()._dispatch_event(event)

    async def _handle_stream_events(self, input: RunAgentInput) -> AsyncGenerator[str, None]:
        """处理流事件，添加异常处理"""
        try:
            async for event in super()._handle_stream_events(input):
                yield event
        except Exception as e:
            logger.exception(f"Failed to handle stream events: {e}")
            error_chunk = extract_model_error_message(e)
            yield self._dispatch_event(RunErrorEvent(message=error_chunk))
