# -*- coding: utf-8 -*-
"""AG-UI 事件处理器抽象基类

定义会话回写的通用逻辑，支持三种使用方式：
1. 简单场景：只实现 _do_create_content()，使用默认事件处理逻辑
2. 扩展场景：覆盖 handle_model_end/handle_tool_finish 等方法自定义处理
3. 完全自定义：覆盖 __call__ 方法处理原始事件

断点续传机制（基于 session.status）：
- 流式开始时：set_streaming_started() 将会话状态设为 running
- 流式正常结束时：set_streaming_finished() 将会话状态设为 finished
- 前端查询消息列表时，后端根据 session.status == running 动态标记最后一条 AI 消息为 streaming
- 用户点击「停止」→ revoke bkflow 任务（不可恢复），session.status 设为 finished
"""

import json
import uuid
from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, Callable

from ag_ui.core import BaseEvent, CustomEvent, EventType, RunErrorEvent
from ag_ui.core.events import RawEvent, TextMessageContentEvent, TextMessageEndEvent, TextMessageStartEvent
from langchain_core.messages import messages_from_dict

from aidev_agent.core.ag_ui.types import (
    CustomEventNames,
    CustomMessageType,
    ExtendFunctionCall,
    ExtendToolCall,
    LangGraphEventTypes,
    SessionPersistenceEventNames,
)
from aidev_agent.core.ag_ui.utils import camel_to_snake
from aidev_agent.core.nodes.tool.approval_wrapper import is_approval_configured
from aidev_agent.enums import ActivityType, PromptRole
from aidev_agent.utils.event import RunId

logger = getLogger(__name__)

# Flow Agent 结果中 duration 的默认值
DEFAULT_FLOW_AGENT_DURATION = 0.0


def dict_keys_camel_to_snake(d: dict) -> dict:
    """将字典的 key 从 camelCase 转换为 snake_case"""
    return {camel_to_snake(k): v for k, v in d.items()}


class BaseSessionWriter(ABC):
    """会话回写器抽象基类

    通过 __call__ 方法接收所有 AG-UI 事件，分发到对应的类型化处理方法。

    断点续传通过会话状态判断实现：
    - 流式开始：set_streaming_started() 更新 session.status = running
    - 流式正常结束：set_streaming_finished() 更新 session.status = finished
    - 消息直接通过 create 创建，无需占位/变形

    取消/暂停回写机制：
    - 当用户在非 assistant 阶段（thinking/tool/activity）暂停时，handle_run_finished()
      会转为 RUN_ERROR 语义，回写已有内容并补一条 role=assistant, content="用户已取消",
      status="fail" 的消息
    - 当用户在 assistant 阶段暂停时，已有的 assistant 消息以 status="complete" 正常回写

    使用方式：
    1. 简单场景：只实现 `_do_create_content` 方法，使用默认事件处理逻辑
    2. 扩展场景：覆盖 `handle_model_end`/`handle_tool_finish` 等方法自定义处理
    3. 完全自定义：覆盖 `__call__` 方法处理原始事件

    Example:
        ```python
        # 简单场景 - 只需实现回写方法
        class MyWriter(BaseSessionWriter):
            def _do_create_content(self, payload, headers):
                db.save(payload)
                return None  # 不支持返回记录 ID

        # 扩展场景 - 自定义某类事件的处理
        class MyWriter(BaseSessionWriter):
            def handle_reference_document(self, event):
                # 自定义引用文档的处理逻辑
                ...

        # 完全自定义 - 直接处理原始事件
        class MyWriter(BaseSessionWriter):
            def __call__(self, event):
                # 完全自定义的事件处理逻辑
                ...
        ```
    """

    # 用户取消时补写的默认提示文本，与 RunId.CANCELLED_MESSAGE 保持一致
    PAUSED_CONTENT_MESSAGE = "用户已取消"

    def __init__(self, session_code: str, username: str = "", tools: list | None = None, turn_id: str = ""):
        """初始化回写器

        Args:
            session_code: 会话标识
            username: 用户名
            tools: 工具列表，用于获取工具描述信息
            turn_id: 同一次 user-ai 回复的轮次 ID。非空时会写入到所有创建/更新的
                session_content.property.turn_id 字段，用于：
                1) bkplugin 异步轮询按 turn_id 命中本轮 ai 回复（poll_task_state）
                2) flow_agent 续流时按 turn_id 复用已有记录
                3) 同一 thread/session 内区分多轮 user-ai 配对
        """
        self.session_code: str = session_code
        self.username: str = username
        self.turn_id: str = turn_id or ""
        self._tools_mapping: dict[str, Any] = {}
        if tools:
            self.set_tools(tools)
        # 用于内存去重，避免重复回写
        self._written_message_ids: set[str] = set()
        # 用于追踪正在流式输出的消息，累积内容
        # key: message_id, value: {"content": str}
        self._streaming_messages: dict[str, dict] = {}
        # 用于追踪 thinking/reasoning 内容
        # key: "thinking", value: {"content": str}
        self._thinking_content: str = ""
        # 用于追踪 flow_agent_result 记录，确保同一个 task_id 只有一条记录（后续轮询更新而非创建）
        self._flow_result_content_id: int | None = None
        self._flow_result_message_id: str | None = None
        # message_id -> content_id，用于后续补写/更新同一条记录
        self._content_ids_by_message_id: dict[str, int] = {}
        # 用于追踪本次运行是否因用户取消/暂停而结束
        self._is_cancelled: bool = False
        # 用于追踪 handle_model_end 是否已成功回写 assistant 消息
        # 当 on_chat_model_end 触发时，assistant 消息已完整输出，取消时不应再补写暂停消息
        self._model_end_written: bool = False
        # 用于追踪需要审批但尚未执行的 tool_calls，待工具实际执行后补充写入
        # key: assistant_message_id, value: list[ExtendToolCall dict]
        self._deferred_approval_tool_calls: dict[str, list[dict]] = {}
        # 用于追踪已写入的 assistant 消息的 builtin_property，以便后续追加 tool_calls 时合并
        # key: assistant_message_id, value: builtin_property dict
        self._assistant_builtin_properties: dict[str, dict] = {}

    # ---------- 公共事件入口 ----------

    def set_tools(self, tools: list | None) -> None:
        self._tools_mapping = {tool.name: tool for tool in tools} if tools else {}

    def __call__(self, event: BaseEvent) -> None:
        """事件入口 - 分发到对应的处理方法

        Args:
            event: AG-UI 事件
        """
        if event.type == EventType.RAW:
            self._dispatch_raw_event(event)
        elif event.type == EventType.CUSTOM:
            self._dispatch_custom_event_direct(event)
        elif event.type == EventType.RUN_ERROR:
            self.handle_run_error(event)
        elif event.type == EventType.TEXT_MESSAGE_START:
            self.handle_text_message_start(event)
        elif event.type == EventType.TEXT_MESSAGE_CONTENT:
            self.handle_text_message_content(event)
        elif event.type == EventType.TEXT_MESSAGE_END:
            self.handle_text_message_end(event)
        elif event.type == EventType.THINKING_TEXT_MESSAGE_START:
            self.handle_thinking_message_start(event)
        elif event.type == EventType.THINKING_TEXT_MESSAGE_CONTENT:
            self.handle_thinking_message_content(event)
        elif event.type == EventType.THINKING_TEXT_MESSAGE_END:
            self.handle_thinking_message_end(event)
        elif event.type == EventType.RUN_FINISHED:
            self.handle_run_finished(event)

    def _dispatch_raw_event(self, event: RawEvent) -> None:
        """分发原始事件到类型化处理方法"""
        langchain_event = event.event.get("event")

        if langchain_event == LangGraphEventTypes.OnChatModelEnd.value:
            self.handle_model_end(event)
        elif langchain_event == LangGraphEventTypes.OnCustomEvent.value:
            self._dispatch_custom_event(event)

    def _dispatch_custom_event(self, event: RawEvent) -> None:
        """分发自定义事件（从 RAW 事件中解析的 on_custom_event）"""
        event_name = event.event.get("name", "")

        if event_name == CustomEventNames.OnToolNodeFinish.value:
            self.handle_tool_finish(event)
        elif event_name == CustomMessageType.KNOWLEDGE_RAG_RESULT.value:
            self.handle_reference_document(event)
        elif event_name == CustomMessageType.FLOW_AGENT_START.value:
            self.handle_flow_agent_start(event)
        elif event_name == CustomMessageType.FLOW_AGENT_RESULT.value:
            self.handle_flow_agent_result(event)
        elif event_name == CustomMessageType.FLOW_AGENT_END.value:
            self.handle_flow_agent_end(event)

    def _dispatch_custom_event_direct(self, event) -> None:
        """分发直接的 CUSTOM 类型事件（非 RAW 包裹）

        LangGraph 流式已不产出 RawEvent；工具节点完成、知识库结果等与 RAW 路径对齐到此。
        """
        event_name = getattr(event, "name", "")

        if event_name == SessionPersistenceEventNames.ChatModelEnd.value:
            self.handle_model_end(event)
        elif event_name == CustomEventNames.OnToolNodeFinish.value:
            self.handle_tool_finish(event)
        elif event_name == CustomMessageType.KNOWLEDGE_RAG_RESULT.value:
            self.handle_reference_document(event)
        elif event_name == CustomMessageType.FLOW_AGENT_START.value:
            self.handle_flow_agent_start(event)
        elif event_name == CustomMessageType.FLOW_AGENT_RESULT.value:
            self.handle_flow_agent_result(event)
        elif event_name == CustomMessageType.FLOW_AGENT_END.value:
            self.handle_flow_agent_end(event)

    # ---------- 事件处理方法 ----------

    def handle_text_message_start(self, event: TextMessageStartEvent) -> None:
        """处理文本消息开始事件，开始追踪流式内容

        Args:
            event: TEXT_MESSAGE_START 事件
        """
        message_id = event.message_id
        if not message_id or message_id in self._written_message_ids:
            return

        # 初始化消息内容追踪，标记是否为审批通知（以 activity 回写）
        is_approval_notice = message_id.startswith("approval_notice_")
        self._streaming_messages[message_id] = {"content": "", "is_approval_notice": is_approval_notice}

    def handle_text_message_content(self, event: TextMessageContentEvent) -> None:
        """处理文本消息内容事件，累积内容

        Args:
            event: TEXT_MESSAGE_CONTENT 事件
        """
        message_id = event.message_id
        if not message_id:
            return

        # 累积内容
        if message_id in self._streaming_messages:
            self._streaming_messages[message_id]["content"] += event.delta or ""

    def handle_text_message_end(self, event: TextMessageEndEvent) -> None:
        """处理文本消息结束事件

        注意：实际的消息回写由 handle_model_end 完成，
        这里只负责记录消息结束状态，避免重复处理。

        Args:
            event: TEXT_MESSAGE_END 事件
        """
        message_id = event.message_id
        if not message_id:
            return

    def handle_thinking_message_start(self, event: BaseEvent) -> None:
        """处理 thinking 消息开始事件，重置 thinking 内容"""
        self._thinking_content = ""

    def handle_thinking_message_content(self, event: BaseEvent) -> None:
        """处理 thinking 消息内容事件，累积 thinking 内容"""
        # event 应该有 delta 属性
        delta = getattr(event, "delta", "") or ""
        self._thinking_content += delta

    def handle_thinking_message_end(self, event: BaseEvent) -> None:
        """处理 thinking 消息结束事件"""

    @staticmethod
    def _unwrap_interrupt_source(source: Any) -> Any:
        if not isinstance(source, dict) or source.get("type") != "RUN_FINISHED":
            return source

        outcome = source.get("outcome")
        if not isinstance(outcome, dict) or outcome.get("type") != "interrupt":
            return source

        interrupts = outcome.get("interrupts") or []
        if interrupts:
            return interrupts[0]
        return source

    @staticmethod
    def _get_interrupt_value(source: Any, *keys: str) -> Any:
        source = BaseSessionWriter._unwrap_interrupt_source(source)
        # LangGraph Interrupt 对象：实际 payload 在 source.value 中，
        # 需要解包后才能按 dict 方式查找 callbackToken、metadata 等字段
        original_source = source
        if not isinstance(source, dict) and hasattr(source, "value"):
            inner = source.value
            if isinstance(inner, dict):
                source = inner

        metadata = {}
        raw_metadata = source.get("metadata") if isinstance(source, dict) else getattr(source, "metadata", None)
        if isinstance(raw_metadata, dict):
            metadata = raw_metadata

        nested_candidates = []
        if isinstance(metadata.get("ticket"), dict):
            nested_candidates.append(metadata["ticket"])
        if isinstance(metadata.get("approval"), dict):
            nested_candidates.append(metadata["approval"])
        if isinstance(metadata.get("target"), dict):
            nested_candidates.append(metadata["target"])
        if isinstance(metadata.get("execution"), dict):
            nested_candidates.append(metadata["execution"])

        for candidate in nested_candidates:
            for key in keys:
                if key in candidate and candidate[key] is not None:
                    return candidate[key]

        for key in keys:
            if key in metadata and metadata[key] is not None:
                return metadata[key]

        for key in keys:
            if isinstance(source, dict):
                if key in source and source[key] is not None:
                    return source[key]
            else:
                value = getattr(source, key, None)
                if value is not None:
                    return value

        # 兜底：对于 Interrupt 对象（source 已被替换为 value），
        # 仍尝试从原始对象的属性中查找（如 Interrupt.id）
        if original_source is not source:
            for key in keys:
                value = getattr(original_source, key, None)
                if value is not None:
                    return value

    def _get_interrupt_id(self, source: Any) -> str | None:
        return self._get_interrupt_value(source, "id", "interruptId")

    def _build_interrupt_run_finished_content(
        self,
        *,
        thread_id: str,
        run_id: str,
        interrupts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """构造落库 content（与 SSE RUN_FINISHED 事件的 outcome 结构保持一致）。

        返回结构：
            {
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [ {id, reason, message, toolCallId, metadata}, ... ]
                }
            }
        """
        return {
            "outcome": {
                "type": "interrupt",
                "interrupts": interrupts,
            }
        }

    def _build_interrupt_builtin_property(
        self, interrupt_id: str, interrupt: Any, graph_thread_id: str | None = None
    ) -> dict[str, Any]:
        ticket = self._get_interrupt_value(interrupt, "ticket")
        return {
            "message_id": interrupt_id,
            "type": self._get_interrupt_value(interrupt, "type") or "tool_approval",
            "interrupt_id": interrupt_id,
            "reason": self._get_interrupt_value(interrupt, "reason"),
            "tool_call_id": self._get_interrupt_value(interrupt, "toolCallId", "tool_call_id"),
            "tool_name": self._get_interrupt_value(interrupt, "toolName", "tool_name", "display_name", "name"),
            "callback_token": self._get_interrupt_value(interrupt, "callbackToken", "callback_token"),
            "ticket_sn": ticket.get("sn") if isinstance(ticket, dict) else None,
            "graph_thread_id": graph_thread_id or self._get_interrupt_value(interrupt, "threadId", "thread_id"),
        }

    def _upsert_interrupt_session_content(
        self,
        *,
        message_id: str,
        content: dict[str, Any],
        builtin_property: dict[str, Any],
    ) -> None:
        content_id = self._content_ids_by_message_id.get(message_id)
        if content_id is not None:
            self._update_session_content(
                content_id=content_id,
                message_id=message_id,
                content=content,
                builtin_property=builtin_property,
            )
            self._written_message_ids.add(message_id)
            return

        created_id = self._create_session_content(
            message_id=message_id,
            role=PromptRole.INTERRUPT.value,
            content=content,
            status="pending",
            builtin_property=builtin_property,
        )
        if created_id is not None:
            self._content_ids_by_message_id[message_id] = created_id
        self._written_message_ids.add(message_id)

    def handle_run_finished(self, event: BaseEvent) -> None:
        """处理运行结束事件，回写所有累积的消息内容

        这是一个后备机制：当 on_chat_model_end 事件没有被触发时，
        通过 RUN_FINISHED 事件来回写累积的流式消息内容。

        取消/暂停场景处理：
        - 取消 + 有 assistant 输出：以 status="complete" 正常回写，发 RUN_FINISHED
        - 取消 + 无 assistant 输出（仅有 thinking/tool/知识库/MCP 等）：
          回写已有内容 + 补一条 role=assistant, content="用户已取消", status="fail" 的消息，
          并转为 RUN_ERROR 语义（确保前端正确展示暂停状态）

        Args:
            event: RUN_FINISHED 事件
        """
        # 检测取消标识：run_id 为 "cancelled" 或 "stopped" 表示用户主动取消/暂停
        run_id = getattr(event, "run_id", "")
        if run_id in (RunId.CANCELLED, RunId.STOPPED):
            self._is_cancelled = True
            logger.info(
                "Run finished with cancel signal: session_code=%s, run_id=%s",
                self.session_code,
                run_id,
            )

        # 获取 thinking 内容
        thinking_content = self._thinking_content.strip() if self._thinking_content else ""

        # 判断是否有 assistant 内容已流式输出或已通过 handle_model_end 回写
        has_assistant_output = (
            any(mid not in self._written_message_ids for mid in self._streaming_messages) or self._model_end_written
        )

        # 取消 + 无 AI 输出：回写已有内容 + 补写"用户已取消" + status=fail
        if self._is_cancelled and not has_assistant_output:
            self._write_cancelled_messages(thinking_content)
            return

        # 正常回写或取消+有AI输出（正常回写即可）
        for message_id, message_data in list(self._streaming_messages.items()):
            if message_id in self._written_message_ids:
                continue

            content = message_data.get("content", "")
            is_approval_notice = message_data.get("is_approval_notice", False)

            if is_approval_notice:
                # 审批通知以 activity 角色入库，对 LLM 不可见
                self._create_session_content(
                    message_id=message_id,
                    role=PromptRole.ACTIVITY.value,
                    content=content if content else "",
                    status="complete",
                    builtin_property={
                        "message_id": message_id,
                        "type": "approval_notice",
                    },
                )
                self._written_message_ids.add(message_id)
                continue

            # 先回写 reasoning 内容（如果有）
            if thinking_content:
                self._write_reasoning_message_simple(
                    message_id=message_id,
                    reasoning_content=thinking_content,
                )

            # 回写 assistant 消息（status="complete"，不区分取消/非取消）
            self._write_assistant_message(
                message_id=message_id,
                content=content if content else "",
                tool_calls=[],
            )

            # 标记为已写入
            self._written_message_ids.add(message_id)

        # 如果没有流式消息但有 thinking 内容，也需要回写
        if not self._streaming_messages and thinking_content:
            fallback_message_id = str(uuid.uuid4())

            # 回写 reasoning
            self._write_reasoning_message_simple(
                message_id=fallback_message_id,
                reasoning_content=thinking_content,
            )

            # 取消场景：补写"用户已取消" + status=fail
            if self._is_cancelled:
                self._write_assistant_message(
                    message_id=fallback_message_id,
                    content=self.PAUSED_CONTENT_MESSAGE,
                    tool_calls=[],
                    status="fail",
                )
            else:
                self._write_assistant_message(
                    message_id=fallback_message_id,
                    content="",
                    tool_calls=[],
                )

            self._written_message_ids.add(fallback_message_id)

        # 处理中断场景：回写 role=interrupt 的记录
        # 注：dispatch_custom_event 在 interrupt() 前派发的事件，因 LangGraph stream
        # 在中断后立刻终止，on_interrupt 自定义事件可能无法被消费，因此在此处兜底回写
        outcome = getattr(event, "outcome", None)
        # 兼容 outcome 为 dict 或对象的情况
        outcome_type = (
            outcome.get("type") if isinstance(outcome, dict) else getattr(outcome, "type", None) if outcome else None
        )
        logger.info(
            "[ToolApproval] handle_run_finished outcome check: outcome=%s, outcome_type=%s, outcome_type_attr=%s",
            outcome,
            type(outcome).__name__ if outcome else None,
            outcome_type,
        )
        if outcome and outcome_type == "interrupt":
            # 读取 interrupts 数据
            interrupts = (
                outcome.get("interrupts") if isinstance(outcome, dict) else getattr(outcome, "interrupts", [])
            ) or []
            # 防御性检查：如果任何 interrupt_id 已在 _written_message_ids 中，说明已写入过，跳过整个 interrupt 分支
            already_written = any(
                self._get_interrupt_id(interrupt) in self._written_message_ids
                for interrupt in interrupts
                if self._get_interrupt_id(interrupt)
            )
            if already_written:
                logger.info(
                    "[ToolApproval] handle_run_finished: skip interrupt write, "
                    "some interrupt_id already written, interrupts=%s, written=%s",
                    [self._get_interrupt_id(i) for i in interrupts],
                    list(self._written_message_ids),
                )
                self._streaming_messages.clear()
                self._thinking_content = ""
                return

            serialized_interrupts = [
                interrupt.model_dump(by_alias=True) if hasattr(interrupt, "model_dump") else interrupt
                for interrupt in interrupts
            ]
            run_finished_content = self._build_interrupt_run_finished_content(
                thread_id=getattr(event, "thread_id", ""),
                run_id=getattr(event, "run_id", ""),
                interrupts=serialized_interrupts,
            )
            for idx, interrupt in enumerate(interrupts):
                interrupt_id = self._get_interrupt_id(interrupt)
                if not interrupt_id:
                    continue
                # 直接从 serialized_interrupts（即 content 中的数据）提取 builtin_property，
                # 避免 AG-UI Interrupt 对象序列化时丢失审批字段
                serialized = serialized_interrupts[idx] if idx < len(serialized_interrupts) else {}
                metadata = serialized.get("metadata") or {}
                ticket = metadata.get("ticket") or {}
                # 工具入参：优先取 metadata.toolArgs，兜底取 serialized.toolArgs
                tool_args = metadata.get("toolArgs")
                if not isinstance(tool_args, dict):
                    tool_args = serialized.get("toolArgs")
                if not isinstance(tool_args, dict):
                    tool_args = {}
                builtin_property = {
                    "message_id": interrupt_id,
                    "type": metadata.get("type") or serialized.get("type") or "tool_approval",
                    "interrupt_id": interrupt_id,
                    "reason": serialized.get("reason"),
                    "tool_call_id": serialized.get("toolCallId") or serialized.get("tool_call_id"),
                    "tool_name": metadata.get("toolName") or serialized.get("toolName") or serialized.get("toolName"),
                    "tool_args": tool_args,
                    "callback_token": metadata.get("callbackToken") or serialized.get("callbackToken"),
                    "ticket_sn": ticket.get("sn") or metadata.get("ticketSn") or serialized.get("ticketSn"),
                    "graph_thread_id": getattr(event, "thread_id", ""),
                }
                # 记录从 outcome.interrupts 提取的字段，方便排查是否完整
                logger.info(
                    "[ToolApproval] handle_run_finished interrupt builtin_property: "
                    "interrupt_id=%s, callback_token=%s, ticket_sn=%s, tool_name=%s, keys=%s",
                    interrupt_id,
                    builtin_property.get("callback_token"),
                    builtin_property.get("ticket_sn"),
                    builtin_property.get("tool_name"),
                    list(builtin_property.keys()),
                )
                self._upsert_interrupt_session_content(
                    message_id=interrupt_id,
                    content=run_finished_content,
                    builtin_property=builtin_property,
                )

        # 清理
        self._streaming_messages.clear()
        self._thinking_content = ""

    def _write_cancelled_messages(self, thinking_content: str) -> None:
        """回写取消/暂停场景下的消息

        当用户在非 assistant 阶段（thinking/tool/知识库/MCP）取消时：
        1. 回写已有的 thinking/reasoning 内容
        2. 回写未写入的流式 assistant 消息（如有部分内容）
        3. 补写一条 role=assistant, content="用户已取消", status="fail" 的消息

        此方法由 handle_run_finished（取消+无AI输出）和 handle_run_error（取消场景）
        共同调用，避免逻辑重复。

        Args:
            thinking_content: 已累积的 thinking 内容
        """
        logger.info(
            "Writing cancelled messages: session_code=%s, has_thinking=%s, streaming_messages=%d, _is_cancelled=%s",
            self.session_code,
            bool(thinking_content),
            len(self._streaming_messages),
            self._is_cancelled,
        )

        # 1. 回写未写入的 thinking/reasoning 内容
        if thinking_content:
            reasoning_message_id = f"rsn_{uuid.uuid4().hex[:12]}"
            self._write_reasoning_message_simple(
                message_id=reasoning_message_id,
                reasoning_content=thinking_content,
            )
            self._written_message_ids.add(reasoning_message_id)

        # 2. 回写未写入的流式 assistant 消息（如有部分内容）
        for message_id, message_data in list(self._streaming_messages.items()):
            if message_id in self._written_message_ids:
                continue
            content = message_data.get("content", "")
            self._write_assistant_message(
                message_id=message_id,
                content=content if content else "",
                tool_calls=[],
            )
            self._written_message_ids.add(message_id)

        # 3. 补写 "用户已取消" + status=fail 的 assistant 消息
        paused_message_id = f"paused_{uuid.uuid4().hex[:12]}"
        self._write_assistant_message(
            message_id=paused_message_id,
            content=self.PAUSED_CONTENT_MESSAGE,
            tool_calls=[],
            status="fail",
        )
        self._written_message_ids.add(paused_message_id)

        # 清理
        self._streaming_messages.clear()
        self._thinking_content = ""

    def handle_model_end(self, event: RawEvent | CustomEvent) -> None:
        """处理模型输出结束事件，回写 assistant 消息

        Args:
            event: RawEvent（on_chat_model_end）或 CustomEvent（aidev_session_chat_model_end）
        """
        if isinstance(event, CustomEvent):
            inner = (event.value or {}).get("output") if isinstance(event.value, dict) else None
            if not inner:
                return
            output_message = messages_from_dict([inner])[0]
        else:
            output_message = event.event.get("data", {}).get("output")
            if not output_message:
                return

        message_id = output_message.id

        if message_id in self._written_message_ids:
            return

        # 构建 tool_calls，过滤需要审批的工具（审批通过执行后再补充写入）
        tool_calls, deferred_tool_calls = self._build_tool_calls_with_approval_filter(output_message)

        # 处理 reasoning 内容（如 deepseek-reasoner）
        reasoning_content = output_message.additional_kwargs.get("reasoning_content")

        # 处理最终回复内容
        # 有延迟的审批 tool_calls 时，视为"尚未调用工具"，不使用"正在调用工具..."占位
        content = self._resolve_content(
            output_message.content,
            tool_calls,
            reasoning_content,
            has_deferred_tool_calls=bool(deferred_tool_calls),
        )

        if reasoning_content:
            self._write_reasoning_message(
                message_id=message_id,
                reasoning_content=reasoning_content,
                output_message=output_message,
            )

        self._write_assistant_message(
            message_id=message_id,
            content=content,
            tool_calls=tool_calls,
        )

        # 记录需要审批但尚未执行的 tool_calls，待工具实际执行后补充写入
        if deferred_tool_calls:
            self._deferred_approval_tool_calls[message_id] = deferred_tool_calls

        self._written_message_ids.add(message_id)
        # 清理追踪
        self._streaming_messages.pop(message_id, None)
        # 清空 thinking 内容，避免 handle_run_finished 重复回写
        self._thinking_content = ""
        # 标记 model_end 已回写，取消时不需要补写暂停消息
        self._model_end_written = True

    def handle_tool_finish(self, event: RawEvent | CustomEvent) -> None:
        """处理工具执行完成事件，回写 tool 消息

        对于需要审批的工具，审批通过后工具实际执行时触发此事件，
        此时将延迟的 tool_calls 补充写入对应的 assistant 消息。

        Args:
            event: RawEvent 或 on_tool_node_finish 的 CustomEvent（value 为 ToolMessage）
        """
        output_message = event.value if isinstance(event, CustomEvent) else event.event.get("data")
        if not output_message:
            return

        tool_call_id = output_message.tool_call_id
        if tool_call_id in self._written_message_ids:
            return

        # 映射状态：success -> complete, error -> fail
        is_error = output_message.status == "error"
        platform_status = "fail" if is_error else "complete"

        # 补充写入延迟的 tool_calls 到对应的 assistant 消息
        # 仅在工具实际执行成功时补充（审批拒绝的不补充）
        if not is_error:
            self._flush_deferred_tool_call(tool_call_id, tool_name=getattr(output_message, "name", None))

        self._create_session_content(
            message_id=output_message.id or tool_call_id,
            role=PromptRole.TOOL.value,
            content=output_message.content,
            status=platform_status,
            builtin_property={
                "message_id": tool_call_id,
                "tool_call_id": tool_call_id,
                "additional_kwargs": output_message.additional_kwargs,
            },
        )
        self._written_message_ids.add(tool_call_id)

    def handle_run_error(self, event: RunErrorEvent) -> None:
        """处理运行时错误事件，回写 assistant 失败消息

        对于取消/暂停场景（message 为 RunId.CANCELLED_MESSAGE），
        会先回写已有的非 assistant 内容（thinking/tool/知识库/MCP 等），
        再补写 content="用户已取消", status="fail" 的 assistant 消息。
        对于真正的运行错误，直接写入错误消息。

        Args:
            event: 运行错误事件
        """
        # 检测是否为取消/暂停触发的 RUN_ERROR
        # Agent 层取消时发送 RUN_ERROR(message=RunId.CANCELLED_MESSAGE)
        # 防御 event.message 为 None 的场景（非标准事件对象）
        error_message = event.message or ""
        is_cancel_error = error_message == RunId.CANCELLED_MESSAGE
        if is_cancel_error:
            self._is_cancelled = True
            logger.info(
                "handle_run_error detected cancel: session_code=%s, message=%s",
                self.session_code,
                error_message,
            )
            # 取消场景：统一走 _write_cancelled_messages 回写已有内容 + 补写暂停消息
            thinking_content = self._thinking_content.strip() if self._thinking_content else ""
            self._write_cancelled_messages(thinking_content)
            return

        # 真正的运行错误处理
        logger.info(
            "handle_run_error writing error message: session_code=%s, message=%s",
            self.session_code,
            error_message,
        )
        # 回写未写入的 thinking/reasoning 内容（如有）
        thinking_content = self._thinking_content.strip() if self._thinking_content else ""
        if thinking_content:
            reasoning_message_id = f"rsn_{uuid.uuid4().hex[:12]}"
            self._write_reasoning_message_simple(
                message_id=reasoning_message_id,
                reasoning_content=thinking_content,
            )
            self._written_message_ids.add(reasoning_message_id)

        # 回写未写入的流式 assistant 消息（如有部分内容）
        for message_id, message_data in list(self._streaming_messages.items()):
            if message_id in self._written_message_ids:
                continue
            content = message_data.get("content", "")
            self._write_assistant_message(
                message_id=message_id,
                content=content if content else "",
                tool_calls=[],
            )
            self._written_message_ids.add(message_id)

        # 补写错误消息
        error_message_id = f"error_{uuid.uuid4().hex[:12]}"
        self._create_session_content(
            message_id=error_message_id,
            role=PromptRole.ASSISTANT.value,
            content=error_message,
            status="fail",
            builtin_property={
                "message_id": error_message_id,
                "error": True,
            },
        )

        # 清理
        self._streaming_messages.clear()
        self._thinking_content = ""

    def handle_reference_document(self, event: RawEvent | CustomEvent) -> None:
        """处理引用文档事件，回写 activity 消息

        Args:
            event: RawEvent（on_custom_event）或 knowledge_rag_result 的 CustomEvent
        """
        if isinstance(event, CustomEvent):
            event_data = event.value if isinstance(event.value, dict) else {}
        else:
            event_data = event.event.get("data", {})
        message_id = event_data.get("message_id")
        reference_documents = [dict_keys_camel_to_snake(each) for each in event_data.get("data", [])]

        if not reference_documents:
            return

        if not message_id:
            message_id = f"ref_{uuid.uuid4().hex[:12]}"

        if message_id in self._written_message_ids:
            return

        # content 需要序列化为 JSON 字符串，因为数据库 content 字段是 TextField
        self._create_session_content(
            message_id=message_id,
            role=PromptRole.ACTIVITY.value,
            content=json.dumps(reference_documents, ensure_ascii=False),
            status="success",
            builtin_property={
                "message_id": message_id,
                "type": ActivityType.REFERENCE_DOCUMENT.value,
            },
        )
        self._written_message_ids.add(message_id)

    def handle_flow_agent_result(self, event) -> None:
        """处理 Flow Agent 结果事件，回写 activity 消息

        同一个 task 的轮询结果只保留一条记录：
        - 第一次轮询时创建记录并保存 content_id
        - 后续轮询时更新同一条记录的 content

        Args:
            event: 包含 flow_agent_result 数据的事件（CustomEvent 或 RawEvent）
        """
        # 兼容 CustomEvent（直接有 value 属性）和 RawEvent（嵌套在 event dict 中）
        # value 格式：list[dict]（数组格式，每个元素包含 task_id, task_name, task_state, nodes, statistics, task_outputs 等字段）
        if hasattr(event, "value"):
            if isinstance(event.value, list):
                event_data = event.value[0] if event.value else {}
            elif isinstance(event.value, dict):
                event_data = event.value
            else:
                event_data = {}
        else:
            event_data = event.event.get("data", {})

        # 直接使用 dict 格式，包含 task_id, task_name, task_state, nodes, statistics, task_outputs 等字段
        content = json.dumps(event_data, ensure_ascii=False)

        if self._flow_result_content_id is not None:
            # 已有记录，更新内容
            self._update_session_content(
                content_id=self._flow_result_content_id,
                message_id=self._flow_result_message_id,
                content=content,
                builtin_property={
                    "message_id": self._flow_result_message_id,
                    "tool_calls": [],  # 前端兼容：添加空的 tool_calls 数组
                    "tool_call_id": "",
                    "additional_kwargs": {},
                    "error": False,
                    "type": ActivityType.FLOW_AGENT.value,
                    "duration": DEFAULT_FLOW_AGENT_DURATION,
                },
            )
        else:
            # 首次创建
            message_id = f"flow_result_{uuid.uuid4().hex[:12]}"
            self._flow_result_message_id = message_id
            content_id = self._create_session_content(
                message_id=message_id,
                role=PromptRole.ACTIVITY.value,
                content=content,
                status="complete",
                builtin_property={
                    "message_id": message_id,
                    "tool_calls": [],  # 前端兼容：添加空的 tool_calls 数组
                    "tool_call_id": "",
                    "additional_kwargs": {},
                    "error": False,
                    "type": ActivityType.FLOW_AGENT.value,
                    "duration": DEFAULT_FLOW_AGENT_DURATION,
                },
            )
            if content_id is not None:
                self._flow_result_content_id = content_id

    def handle_flow_agent_end(self, event) -> None:
        """处理 Flow Agent 结束事件，回写 assistant 消息并更新 session 元数据

        1. 回写 role=assistant 消息（task_outputs 作为 AI 回复内容）
        2. 断点续传：更新 session 中的 task_id

        Args:
            event: 包含 flow_agent_end 数据的事件（CustomEvent 或 RawEvent）
        """
        if hasattr(event, "value"):
            if isinstance(event.value, list):
                event_data = event.value[0] if event.value else {}
            elif isinstance(event.value, dict):
                event_data = event.value
            else:
                event_data = {}
        else:
            event_data = event.event.get("data", {})

        task_id = event_data.get("task_id", "")
        task_outputs = event_data.get("task_outputs")

        # 1. 回写 assistant 消息（task_outputs 作为 AI 回复内容）
        if task_outputs:
            # task_outputs 可能格式：[{"key": "output", "value": "..."}] 或直接是字符串
            if isinstance(task_outputs, list):
                # 尝试从列表中提取 value 字段
                content_parts = []
                for item in task_outputs:
                    if isinstance(item, dict):
                        content_parts.append(str(item.get("value", "")))
                    else:
                        content_parts.append(str(item))
                content = "\n".join(content_parts)
            else:
                content = str(task_outputs)

            if content and content.strip():
                message_id = f"flow_assistant_{uuid.uuid4().hex[:12]}"
                self._write_assistant_message(
                    message_id=message_id,
                    content=content,
                    tool_calls=[],
                )

        # 2. 断点续传：任务结束，更新 session 中的 task_id（确保最终状态已持久化）
        if task_id:
            self.update_flow_agent_info(task_id=task_id)

    def handle_flow_agent_start(self, event) -> None:
        """处理 Flow Agent 启动事件，持久化 task_id 到 session 元数据

        在 flow_agent_start 事件触发时，将 task_id 写入 session_property.flow_info，
        前端切回 session 时通过 GET /session/{session_code}/ 即可获取。

        Args:
            event: 包含 flow_agent_start 数据的事件（CustomEvent 或 RawEvent）
        """
        if hasattr(event, "value"):
            if isinstance(event.value, list):
                event_data = event.value[0] if event.value else {}
            elif isinstance(event.value, dict):
                event_data = event.value
            else:
                event_data = {}
        else:
            event_data = event.event.get("data", {})

        task_id = event_data.get("task_id", "")
        if task_id:
            self.update_flow_agent_info(task_id=str(task_id))
        else:
            logger.warning("handle_flow_agent_start: task_id 为空，跳过持久化: event_data=%s", event_data)

    # ---------- handle_model_end 辅助方法 ----------

    def _build_tool_calls(self, output_message: Any) -> list:
        """从模型输出中构建 tool_calls 列表"""
        tool_calls, _ = self._build_tool_calls_with_approval_filter(output_message)
        return tool_calls

    def _build_tool_calls_with_approval_filter(self, output_message: Any) -> tuple[list, list]:
        """从模型输出中构建 tool_calls 列表，将需要审批的工具分离出来延迟写入。

        Returns:
            (immediate_tool_calls, deferred_tool_calls)
            - immediate_tool_calls: 不需要审批的工具调用，立即写入
            - deferred_tool_calls: 需要审批的工具调用，待审批通过执行后补充写入
        """
        immediate_tool_calls = []
        deferred_tool_calls = []
        for each in output_message.tool_calls or []:
            _tool = self._tools_mapping.get(each["name"])
            tool_call_dict = ExtendToolCall(
                id=each["id"],
                function=ExtendFunctionCall(
                    name=each["name"],
                    arguments=json.dumps(each["args"]),
                    description=_tool.description if _tool else "",
                    mcp_name=_tool.metadata.get("mcp_name", "") if _tool and _tool.metadata else "",
                ),
            ).model_dump()

            if is_approval_configured(_tool):
                deferred_tool_calls.append(tool_call_dict)
            else:
                immediate_tool_calls.append(tool_call_dict)
        return immediate_tool_calls, deferred_tool_calls

    def _resolve_content(
        self, content: str, tool_calls: list, reasoning_content: str | None, *, has_deferred_tool_calls: bool = False
    ) -> str:
        """解析最终回复内容

        对于 DeepSeek reasoning 模型，最终回复可能在 reasoning_content 而不是 content。
        当有 tool_calls 时，content 为空是正常的（AI 只是调用工具）。
        当没有 tool_calls 且 content 为空时，尝试使用 reasoning_content 作为回复内容。

        Args:
            content: 原始回复内容
            tool_calls: 立即写入的 tool_calls 列表
            reasoning_content: reasoning 内容（如 deepseek-reasoner）
            has_deferred_tool_calls: 是否有延迟写入的审批 tool_calls
        """
        content_stripped = content.strip() if content else ""

        if not content_stripped and has_deferred_tool_calls:
            # 所有 tool_calls 都是审批延迟的，工具尚未执行，避免把 reasoning_content 误当作 assistant 内容
            return ""
        if not content_stripped and not tool_calls and reasoning_content:
            # reasoning 模型的最终回复在 reasoning_content 中
            return reasoning_content
        elif not content_stripped and tool_calls:
            # 有立即写入的 tool_calls 但 content 为空/只有空白字符，使用一个有意义的占位符
            return "正在调用工具..."
        elif not content_stripped:
            # 没有 tool_calls 也没有内容，使用空字符串（可能会失败）
            return ""
        return content_stripped

    def _write_reasoning_message(
        self,
        message_id: str,
        reasoning_content: str,
        output_message: Any = None,
        duration: int = 0,
    ) -> None:
        """回写 reasoning 消息

        Args:
            message_id: 当前 assistant 消息 ID
            reasoning_content: reasoning 内容
            output_message: 模型输出对象（可选，用于提取 duration）
            duration: reasoning 时长（当 output_message 为 None 时使用）
        """
        reasoning_message_id = f"rsn_{message_id}"
        if reasoning_message_id in self._written_message_ids:
            return

        reasoning_content_list = reasoning_content if isinstance(reasoning_content, list) else [reasoning_content]
        reasoning_json = json.dumps(reasoning_content_list, ensure_ascii=False)

        # 优先从 output_message 获取 duration，否则使用参数
        actual_duration = duration
        if output_message is not None:
            actual_duration = output_message.additional_kwargs.get("reasoning_time", 0)

        reasoning_property = {
            "message_id": reasoning_message_id,
            "duration": actual_duration,
        }

        self._create_session_content(
            message_id=reasoning_message_id,
            role=PromptRole.REASONING.value,
            content=reasoning_json,
            status="complete",
            builtin_property=reasoning_property,
        )

        self._written_message_ids.add(reasoning_message_id)

    # 保留别名以保持向后兼容
    def _write_reasoning_message_simple(
        self,
        message_id: str,
        reasoning_content: str,
    ) -> None:
        """回写 reasoning 消息（简化版，无 duration 信息）

        Note: 此方法为向后兼容保留，内部调用 _write_reasoning_message
        """
        self._write_reasoning_message(message_id, reasoning_content, duration=0)

    def _write_assistant_message(
        self,
        message_id: str,
        content: str,
        tool_calls: list,
        status: str = "complete",
    ) -> None:
        """回写 assistant 消息

        Args:
            message_id: assistant 消息 ID
            content: 消息内容
            tool_calls: 工具调用列表
            status: 消息状态，默认 "complete"；取消/暂停场景使用 "fail"
        """
        assistant_property = {
            "message_id": message_id,
            "tool_calls": tool_calls,
        }

        # 记录 builtin_property，以便后续追加审批 tool_calls 时合并
        self._assistant_builtin_properties[message_id] = dict(assistant_property)

        self._create_session_content(
            message_id=message_id,
            role=PromptRole.ASSISTANT.value,
            content=content,
            status=status,
            builtin_property=assistant_property,
        )

    def _flush_deferred_tool_call(self, tool_call_id: str, tool_name: str | None = None) -> None:
        """将延迟写入的审批 tool_call 补充到对应的 assistant 消息

        当需要审批的工具实际执行完成后（handle_tool_finish），调用此方法
        将该 tool_call 从 _deferred_approval_tool_calls 中取出，更新到
        对应的 assistant 消息的 tool_calls 列表中。

        续流场景：_deferred_approval_tool_calls 为空时，调用
        _flush_deferred_tool_call_fallback 让子类通过数据库等方式补充。

        Args:
            tool_call_id: 工具调用 ID，用于匹配延迟记录
            tool_name: 工具名称（续流 fallback 时使用）
        """
        matched_assistant_id = None
        matched_tool_call = None

        # 优先从内存中的延迟记录查找
        for assistant_id, deferred_calls in self._deferred_approval_tool_calls.items():
            for tc in deferred_calls:
                if tc.get("id") == tool_call_id:
                    matched_assistant_id = assistant_id
                    matched_tool_call = tc
                    break
            if matched_assistant_id:
                break

        if matched_tool_call:
            # 从延迟列表中移除已处理的 tool_call
            remaining = [
                tc for tc in self._deferred_approval_tool_calls[matched_assistant_id] if tc.get("id") != tool_call_id
            ]
            if remaining:
                self._deferred_approval_tool_calls[matched_assistant_id] = remaining
            else:
                del self._deferred_approval_tool_calls[matched_assistant_id]

            # 合并已有 builtin_property 和新的 tool_call
            existing_property = self._assistant_builtin_properties.get(matched_assistant_id, {})
            merged_tool_calls = list(existing_property.get("tool_calls", []))
            merged_tool_calls.append(matched_tool_call)
            merged_property = {**existing_property, "tool_calls": merged_tool_calls}
            self._assistant_builtin_properties[matched_assistant_id] = merged_property

            # 更新 assistant 消息
            content_id = self._content_ids_by_message_id.get(matched_assistant_id)
            if content_id is None:
                logger.warning(
                    "Cannot flush deferred tool_call: no content_id for assistant message %s",
                    matched_assistant_id,
                )
                return

            # 只更新 property，不传 content 避免覆盖已有内容
            self._safe_call(
                self._do_update_content,
                matched_assistant_id,
                "update_deferred_tool_call",
                content_id=content_id,
                payload={
                    "property": {
                        "builtin_property": merged_property,
                    },
                },
                headers=self._get_headers(),
            )
        else:
            # 续流 fallback：内存中没有延迟记录，让子类通过数据库等方式补充
            self._flush_deferred_tool_call_fallback(tool_call_id, tool_name)

    def _flush_deferred_tool_call_fallback(self, tool_call_id: str, tool_name: str | None = None) -> None:
        """续流场景下补充写入审批 tool_call 的 fallback 方法

        当 _deferred_approval_tool_calls 为空（续流时新实例）时调用，
        子类可覆写此方法通过数据库查询等方式定位 assistant 消息并补充 tool_call。

        默认实现为空操作。

        Args:
            tool_call_id: 工具调用 ID
            tool_name: 工具名称
        """

    # ---------- 底层回写方法 ----------

    def _get_headers(self) -> dict[str, str]:
        """构建请求头"""
        return {"X-BKAIDEV-USER": self.username} if self.username else {}

    def _safe_call(self, fn: Callable, message_id: str, action: str, **kwargs: Any) -> Any:
        """安全调用回写函数，统一处理异常和日志

        D-02: 写入失败时不阻断 Agent 执行，但递增 _write_error_count，
        供 set_streaming_finished 判断 session 最终状态。

        Args:
            fn: 实际执行的回写函数（_do_create_content / _do_update_content 等）
            message_id: 消息 ID，仅用于日志
            action: 操作名称，仅用于日志（如 "create", "update"）
            **kwargs: 传递给 fn 的参数

        Returns:
            fn 的返回值，异常时返回 None
        """
        try:
            return fn(**kwargs)
        except Exception as e:
            logger.exception(f"Failed to {action} session content: message_id={message_id}, error={e}", exc_info=True)
            return None

    def _create_session_content(
        self,
        message_id: str,
        role: str,
        content: str | list | dict,
        status: str,
        builtin_property: dict[str, Any],
    ) -> int | None:
        """创建会话内容（内部方法）

        Returns:
            创建成功时返回记录 ID（如果子类支持），否则返回 None
        """
        if role == PromptRole.INTERRUPT.value:
            logger.info(
                "[ToolApproval] _create_session_content role=interrupt: "
                "message_id=%s, content_type=%s, status=%s, builtin_property_keys=%s",
                message_id,
                type(content).__name__,
                status,
                list(builtin_property.keys()) if isinstance(builtin_property, dict) else "N/A",
            )
        payload = {
            "session_code": self.session_code,
            "role": role,
            "content": content,
            "status": status,
            "property": {
                "builtin_property": builtin_property,
            },
        }
        if self.turn_id:
            payload["property"]["turn_id"] = self.turn_id
        content_id = self._safe_call(
            self._do_create_content, message_id, "create", payload=payload, headers=self._get_headers()
        )
        if content_id is not None:
            self._content_ids_by_message_id[message_id] = content_id
        return content_id

    def _update_session_content(
        self,
        content_id: int,
        message_id: str,
        content: str | list | dict,
        builtin_property: dict[str, Any],
    ) -> None:
        """更新已有的会话内容（内部方法）

        Args:
            content_id: 记录 ID（数据库主键）
            message_id: 消息标识，仅用于日志
            content: 更新的内容
            builtin_property: 更新的 builtin_property
        """
        payload = {
            "content": content,
            "property": {
                "builtin_property": builtin_property,
            },
        }
        if self.turn_id:
            payload["property"]["turn_id"] = self.turn_id
        self._safe_call(
            self._do_update_content,
            message_id,
            "update",
            content_id=content_id,
            payload=payload,
            headers=self._get_headers(),
        )
        self._content_ids_by_message_id[message_id] = content_id

    @abstractmethod
    def _do_create_content(self, payload: dict[str, Any], headers: dict[str, str]) -> int | None:
        """执行具体的回写操作

        子类必须实现此方法来定义具体的回写逻辑。

        Args:
            payload: 回写数据，包含 session_code, role, content, status, property 等字段
            headers: HTTP 头信息，包含用户信息等

        Returns:
            创建成功时返回记录 ID（如果支持获取 ID），否则返回 None

        Raises:
            Exception: 回写失败时抛出异常，由基类统一处理日志记录
        """

    def _do_update_content(self, content_id: int, payload: dict[str, Any], headers: dict[str, str]) -> None:
        """更新已有的会话内容记录

        默认实现为空操作。子类可覆盖此方法来支持更新。

        Args:
            content_id: 记录 ID（数据库主键）
            payload: 更新数据，包含 content, property 等字段
            headers: HTTP 头信息
        """

    # ---------- 断点续传支持（基于会话状态判断） ----------

    def set_streaming_started(self) -> None:
        """标记流式传输开始

        子类应覆盖此方法来更新会话状态为 running。
        默认实现为空操作。
        """

    def set_streaming_finished(self) -> None:
        """标记流式传输结束

        子类应覆盖此方法来更新会话状态。
        默认实现为空操作。

        注意：当 _is_cancelled 为 True 时，子类应将会话状态设为 cancelled 而非 finished，
        以便前端正确展示暂停/取消状态。
        """

    def update_flow_agent_info(self, task_id: str) -> None:
        """更新 session 中的 Flow Agent task_id

        子类应覆盖此方法来将 task_id 持久化到 session_property.flow_info 元数据。
        默认实现为空操作。

        Args:
            task_id: bkflow 任务 ID
        """
