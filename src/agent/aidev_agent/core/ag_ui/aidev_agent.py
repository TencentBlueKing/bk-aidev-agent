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
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.graph.state import CompiledStateGraph

from aidev_agent.exceptions import extract_model_error_message
from aidev_agent.core.nodes.tool.approval_wrapper import TOOL_APPROVAL_REASON, is_approval_configured

from .agent import LangGraphAGUIAgent
from .approval import ApprovalOutcomeBuilder, ApproveResultLiteral
from .events import (
    ExtendToolCallResultEvent,
    ExtendToolCallStartEvent,
)
from .types import (
    AgentInput,
    CustomEventNames,
    CustomMessageType,
    MessagesInProgressRecord,
    MessageSnapshotEventExtend,
    RunFinishedSuccessOutcome,
    SessionPersistenceEventNames,
    serialize_run_finished_outcome,
)

logger = getLogger(__name__)


class EventDispatcher:
    """事件分发器，用于处理不同类型事件的分发逻辑"""

    def __init__(self, agent: "AidevAGUIAgent"):
        self.agent = agent
        self._suppressed_tool_call_ids: set[str] = set()
        self._dispatch_handlers = {
            EventType.RAW: self._handle_raw_event,
            EventType.CUSTOM: self._handle_custom_event,
            EventType.TOOL_CALL_START: self._handle_tool_call_start,
            EventType.TOOL_CALL_ARGS: self._handle_tool_call_args,
            EventType.TOOL_CALL_END: self._handle_tool_call_end,
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
        # 确保 content 是字符串类型（ToolCallResultEvent.content 要求 str）
        content = tool_msg.content
        if not isinstance(content, str):
            content = str(content) if content else ""
        return self.agent._parent_dispatch(
            ExtendToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                tool_call_id=tool_msg.tool_call_id,
                message_id=tool_msg.id or str(uuid.uuid4()),
                content=content,
                role="tool",
                duration=tool_msg.additional_kwargs.get("duration", None),
                is_error=is_error,
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
            CustomEventNames.OnToolNodeFinish.value: self._handle_tool_node_finish_from_custom,
            CustomEventNames.OnToolNodeImmediate.value: self._handle_tool_node_immediate,
        }

        handler = custom_event_handlers.get(event.name)
        if handler:
            return handler(event)
        return self.agent._parent_dispatch(event)

    def _handle_tool_node_finish_from_custom(self, event: CustomEvent) -> str:
        tool_msg = event.value
        is_error = getattr(tool_msg, "status", None) == "error" or bool(getattr(tool_msg, "error", None))
        # 确保 content 是字符串类型（ToolCallResultEvent.content 要求 str）
        content = tool_msg.content
        if not isinstance(content, str):
            content = str(content) if content else ""
        return self.agent._parent_dispatch(
            ExtendToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                tool_call_id=tool_msg.tool_call_id,
                message_id=tool_msg.id or str(uuid.uuid4()),
                content=content,
                role="tool",
                duration=tool_msg.additional_kwargs.get("duration", None),
                is_error=is_error,
            )
        )

    def _handle_tool_node_immediate(self, event: CustomEvent) -> str:
        """处理子 Agent 中间步骤事件，转为 ExtendToolCallResultEvent 但不触发 DB 写入

        与 _handle_tool_node_finish_from_custom 的区别：
        - duration 为 None（中间步骤无耗时概念）
        - is_error 为 False（中间步骤不可能是错误）
        - 事件名 on_tool_node_immediate 不被 BaseSessionWriter 识别，不会写 DB
        """
        tool_msg = event.value
        # 确保 content 是字符串类型（ToolCallResultEvent.content 要求 str）
        content = tool_msg.content
        if not isinstance(content, str):
            content = str(content) if content else ""
        return self.agent._parent_dispatch(
            ExtendToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                tool_call_id=tool_msg.tool_call_id,
                message_id=tool_msg.id or str(uuid.uuid4()),
                content=content,
                role="tool",
                duration=None,
                is_error=False,
            )
        )

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
        """处理工具调用开始事件，添加描述信息

        对于需要审批的工具，抑制流式 TOOL_CALL 事件，
        审批通知由 approval_check 节点通过 ManuallyEmitMessage 事件发送。
        """
        if self._tool_needs_approval(event.tool_call_name):
            logger.info(f"[EventDispatcher] 抑制需要审批的工具流式事件: {event.tool_call_name} ({event.tool_call_id})")
            self._suppressed_tool_call_ids.add(event.tool_call_id)
            return ""

        _tool = self.agent._tool_mapping.get(event.tool_call_name, None)
        _event = ExtendToolCallStartEvent(
            **{
                **event.model_dump(),
                "description": _tool.description if _tool else "",
                "mcp_name": _tool.metadata.get("mcp_name") if _tool and _tool.metadata else "",
            }
        )
        return self.agent._parent_dispatch(_event)

    def _handle_tool_call_args(self, event: ToolCallArgsEvent) -> str:
        """处理工具调用参数事件，抑制已标记为需要审批的工具"""
        if event.tool_call_id in self._suppressed_tool_call_ids:
            return ""
        return self.agent._parent_dispatch(event)

    def _handle_tool_call_end(self, event: ToolCallEndEvent) -> str:
        """处理工具调用结束事件，抑制已标记为需要审批的工具"""
        if event.tool_call_id in self._suppressed_tool_call_ids:
            self._suppressed_tool_call_ids.discard(event.tool_call_id)
            return ""
        return self.agent._parent_dispatch(event)

    def _tool_needs_approval(self, tool_call_name: str) -> bool:
        """检查工具是否需要审批"""
        _tool = self.agent._tool_mapping.get(tool_call_name, None)
        return is_approval_configured(_tool)


class AidevAGUIAgent(LangGraphAGUIAgent):
    """实现了对自定义事件处理的 AI 辅助 Agent

    事件处理机制：
    1. event_handler: 通用事件钩子，接收所有 BaseEvent，用于 BaseSessionWriter 等外部处理器
    2. EventDispatcher: 内部事件分发器，处理特定事件类型的转换（如工具事件）
    3. cancel_checker: 取消检测回调，返回 True 表示应该取消，Agent 会优雅地发送 RunFinishedEvent

    注意：BaseSessionWriter 处理 CUSTOM（含会话专用名）与 RUN_ERROR 等；RAW 仅保留兼容，流式不再产出
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
        approve_result: ApproveResultLiteral | None = None,
        approval_interrupts: list[dict] | None = None,
    ):
        super().__init__(name=name, graph=graph, description=description, config=config, cancel_checker=cancel_checker)
        self._tool_mapping = tools or {}
        self._event_handler = event_handler
        self._event_dispatcher = EventDispatcher(self)
        self._mcp_fetch_failures = mcp_fetch_failures or []
        self._approve_result = approve_result
        self._approval_interrupts = approval_interrupts or []

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
        skip_encode_custom = frozenset({SessionPersistenceEventNames.ChatModelEnd.value})

        # 每次 SSE 连接先下发完整消息快照，让前端重置到 DB 中的会话状态；
        # 后续 RabbitMQ replay 只负责补当前 run 的流式增量。
        yield event_encoder.encode(
            MessageSnapshotEventExtend(
                type=EventType.MESSAGES_SNAPSHOT,
                messages=list(getattr(input, "messages", []) or []),
            )
        )

        # 续流场景：在 SDK 任何事件之前，先回放一条"终态形态"的 RUN_FINISHED，
        # 让前端能立即据此把原中断卡片更新为审批最终状态（approved / rejected / cancelled）。
        # 仅对"审批中断恢复"场景触发；普通续聊或其他类型恢复不发。
        if self._should_emit_resume_approval_finished():
            try:
                resume_finished = self._build_resume_approval_finished_event(input)
                # 仅做 SSE 输出，不进入 _dispatch_event：
                #   - 不再向 BaseSessionWriter 重复派发（DB 已在审批回调 / cancel 落库时刷写）
                #   - 不进入 EventDispatcher 转换（这是一条纯回放事件，不参与工具事件路由）
                yield event_encoder.encode(resume_finished)
            except Exception:
                logger.exception("[Approval] Failed to emit resume RUN_FINISHED event")

        async for event in super().run(input):
            try:
                # 跳过被抑制的空事件（如审批工具的流式 TOOL_CALL 事件被抑制时返回空字符串）
                if not event:
                    continue

                event_type = getattr(event, "type", "")
                # 特殊处理：不输出 message snapshot 事件（已在上方手动 yield 过完整快照）
                if event_type == EventType.MESSAGES_SNAPSHOT:
                    logger.debug(f"message snapshot: {event}")
                elif event_type == EventType.CUSTOM and getattr(event, "name", "") in skip_encode_custom:
                    continue
                elif (
                    event_type == EventType.CUSTOM
                    and getattr(event, "name", "") == CustomMessageType.COMPRESS_LOG.value
                ):
                    # compress_log 仅输出到 SSE，不写入 DB
                    # CustomEvent 已经过 _dispatch_event（BaseSessionWriter 忽略了它），
                    # 此处展开为 TextMessage 三元组直接编码输出，不经过 _dispatch_event，不接触 BaseSessionWriter
                    compress_log_id = str(uuid.uuid4())
                    delta = event.value.get("compress_log", "") if isinstance(event.value, dict) else ""
                    yield event_encoder.encode(
                        TextMessageStartEvent(
                            type=EventType.TEXT_MESSAGE_START, role="assistant", message_id=compress_log_id
                        )
                    )
                    yield event_encoder.encode(
                        TextMessageContentEvent(
                            type=EventType.TEXT_MESSAGE_CONTENT, message_id=compress_log_id, delta=delta
                        )
                    )
                    yield event_encoder.encode(
                        TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=compress_log_id)
                    )
                else:
                    # RUN_FINISHED 事件：SSE 输出仅保留 metadata.ticket，减少冗余字段
                    if getattr(event, "type", "") == EventType.RUN_FINISHED.value:
                        _outcome = getattr(event, "outcome", None)
                        if isinstance(_outcome, dict) and _outcome.get("type") == "interrupt":
                            for _interrupt in _outcome.get("interrupts", []):
                                _metadata = _interrupt.get("metadata")
                                if isinstance(_metadata, dict):
                                    _interrupt["metadata"] = (
                                        {"ticket": _metadata["ticket"]} if "ticket" in _metadata else None
                                    )
                    yield event_encoder.encode(event)

                # MCP 工具拉取失败消息需要紧跟在 RUN_STARTED 后返回
                if not temp_message_emitted and event_type == EventType.RUN_STARTED and self._mcp_fetch_failures:
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

    def _should_emit_resume_approval_finished(self) -> bool:
        """是否需要在续流首位发送"终态 RUN_FINISHED"。

        触发条件（&，全部满足）：

        1. 存在 ``approve_result``（上游 chat 入口仅审批续流时透传）；
        2. ``approval_interrupts`` 非空（DB 解析出原中断）；
        3. ``interrupts[0].reason == TOOL_APPROVAL_REASON``，保险起见限定审批类型，
           避免未来其他 interrupt 类型误触发。

        其他续流（普通续聊、非审批类型恢复）一律不发。
        """
        if not self._approve_result:
            return False
        if not self._approval_interrupts:
            return False
        first = self._approval_interrupts[0] or {}
        return isinstance(first, dict) and first.get("reason") == TOOL_APPROVAL_REASON

    def _build_resume_approval_finished_event(
        self, input: RunAgentInput
    ) -> RunFinishedEvent:
        """构造续流首条"终态形态" RUN_FINISHED 事件。

        - ``run_id`` 优先取前端续流请求 ``input.resume[0].interruptId``，
          兜底取 ``approval_interrupts[0].id``——确保前端能据此精确定位原中断卡片。
        - ``outcome.type = "success"``，保留 interrupts；同时事件顶层 ``result``
          字段（与 ``outcome`` 平级）承载 interrupts[0] 扁平化数据（metadata 移入
          payload.metadata）。二者由 :meth:`ApprovalOutcomeBuilder.build_run_finished_payload`
          同源构造，与 DB 落库形态一致。

        说明：``ag_ui`` 官方 ``RunFinishedEvent`` 模型原生支持 ``result`` 字段
        （类型为 ``Any | None``），且基于 ConfiguredBaseModel ``extra=allow`` 也允许
        额外的 ``outcome`` 字段透传——直接使用官方事件类型即可输出符合协议的 SSE 载荷。
        """
        interrupt_id: str = ""
        if isinstance(input, AgentInput) and input.resume:
            interrupt_id = input.resume[0].interruptId or ""
        if not interrupt_id and self._approval_interrupts:
            interrupt_id = (self._approval_interrupts[0] or {}).get("id", "") or ""

        outcome_dict, result_dict = ApprovalOutcomeBuilder.build_run_finished_payload(
            self._approval_interrupts, self._approve_result
        )
        return RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id=input.thread_id or "",
            run_id=interrupt_id,
            outcome=outcome_dict,
            result=result_dict,
        )

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
            # 补发 RunFinishedEvent 确保前端和 BaseSessionWriter 收到完整的结束信号
            yield self._dispatch_event(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=input.thread_id or "",
                    run_id=self.active_run.get("id", "") if self.active_run else "",
                    outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
                )
            )
