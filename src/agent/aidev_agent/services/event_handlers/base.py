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
import threading
import uuid
from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, Callable

from ag_ui.core import BaseEvent, CustomEvent, EventType, RunErrorEvent
from ag_ui.core.events import RawEvent, TextMessageContentEvent, TextMessageEndEvent, TextMessageStartEvent

from aidev_agent.core.ag_ui.ask_user_question import (
    ASK_USER_QUESTION_REASON,
    AskUserQuestionHandler,
    InterruptStatus,
    build_updated_builtin_property,
    extract_message_id,
)
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload, should_switch_thinking_step
from aidev_agent.core.ag_ui.events import ExtendToolCallResultEvent
from aidev_agent.core.ag_ui.types import (
    CustomMessageType,
    LangGraphEventTypes,
    SessionPersistenceEventNames,
)
from aidev_agent.core.ag_ui.utils import camel_to_snake, get_interrupt_value, unwrap_interrupt_source
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
        # 追踪当前 thinking step 是否活跃（用于 should_switch_thinking_step 判定，
        # DB 侧事件不含 index，用此标志替代 thinking_process 存在性判定）
        self._thinking_active: bool = False
        # 用于追踪 flow_agent_result 记录，确保同一个 task_id 只有一条记录（后续轮询更新而非创建）
        self._flow_result_content_id: int | None = None
        self._flow_result_message_id: str | None = None
        # message_id -> content_id，用于后续补写/更新同一条记录
        self._content_ids_by_message_id: dict[str, int] = {}
        # 用于追踪本次运行是否因用户取消/暂停而结束
        self._is_cancelled: bool = False
        # RUN_ERROR(cancelled) 与 RUN_FINISHED(cancelled) 可能连续到达，
        # 只允许同一 writer 补写一次“用户已取消”。
        self._cancelled_messages_written: bool = False
        self._cancelled_messages_lock = threading.Lock()
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
        elif event.type == EventType.TOOL_CALL_RESULT:
            self.handle_tool_call_result(event)
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
        """分发自定义事件（从 RAW 事件中解析的 on_custom_event）

        注：OnToolNodeFinish 分支已移除（防御性清理）。Plan A 重建后的 _convert_raw_event
        已把 on_tool_node_finish 转换为 ExtendToolCallResultEvent，DB 侧 __call__ 收到的
        是 TOOL_CALL_RESULT 类型而非 RAW 包裹的 CustomEvent，此分支理论上永远不会触发。
        """
        event_name = event.event.get("name", "")

        if event_name == CustomMessageType.KNOWLEDGE_RAG_RESULT.value:
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

        注：OnToolNodeFinish 分支已移除（防御性清理）。覆写 _handle_on_custom_event
        已把 OnToolNodeFinish CustomEvent 转换为 ExtendToolCallResultEvent，DB 侧 __call__
        收到的 event.type 是 TOOL_CALL_RESULT 而非 CUSTOM，此分支理论上永远不会触发。
        """
        event_name = getattr(event, "name", "")

        if event_name == SessionPersistenceEventNames.ChatModelEnd.value:
            self.handle_model_end(event)
        elif event_name == SessionPersistenceEventNames.ArtifactsGenerated.value:
            self.handle_artifacts_generated(event)
        elif event_name == SessionPersistenceEventNames.AskUserQuestionFinalized.value:
            self.handle_ask_user_question_finalize(event)
        elif event_name == SessionPersistenceEventNames.UserInputSaved.value:
            self.handle_user_input_saved(event)
        elif event_name == CustomMessageType.KNOWLEDGE_RAG_RESULT.value:
            self.handle_reference_document(event)
        elif event_name == CustomMessageType.FLOW_AGENT_START.value:
            self.handle_flow_agent_start(event)
        elif event_name == CustomMessageType.FLOW_AGENT_RESULT.value:
            self.handle_flow_agent_result(event)
        elif event_name == CustomMessageType.FLOW_AGENT_END.value:
            self.handle_flow_agent_end(event)

    def handle_ask_user_question_finalize(self, event) -> None:
        """处理 ask_user_question 跳过/答题事件（终态由 chat.py 预构造后透传）。

        所有决策与协议计算在 chat.py 完成：status（cancelled/resolved）、answers
        （skipped answers 或用户答案）、终态 content（已由 chat.py 调
        ``upgrade_content_to_success`` 升级）均经事件 value 传入。跳过路径的 tool
        记录由 chat.py 显式派发 TOOL_CALL_RESULT 事件（handle_tool_call_result）写入，
        本 handler 仅负责把 interrupt 记录 UPDATE 为指定终态（extract message_id →
        build builtin_property → UPDATE），不再重复调用 upgrade_content_to_success。
        """
        value = event.value if isinstance(event.value, dict) else {}
        bp = value.get("builtin_property") if isinstance(value.get("builtin_property"), dict) else {}
        try:
            content_id = value.get("content_id")
            if content_id is None:
                logger.warning(
                    "[AskUserQuestion] finalize: 事件缺 content_id, 无法定位 interrupt, session=%s",
                    self.session_code,
                )
                return
            upgraded = value.get("content")
            if not isinstance(upgraded, dict):
                logger.warning(
                    "[AskUserQuestion] finalize: 事件缺终态 content, content_id=%s",
                    content_id,
                )
                return
            status = value.get("status") or InterruptStatus.RESOLVED.value
            message_id = extract_message_id(upgraded)
            db_item_adapter = {"property": {"builtin_property": bp}}
            updated_builtin = build_updated_builtin_property(db_item_adapter, message_id, status)
            self._do_update_content(
                content_id=content_id,
                payload={
                    "content": upgraded,
                    "status": "complete",
                    "property": {
                        "builtin_property": updated_builtin,
                        "turn_id": value.get("turn_id") or "",
                    },
                },
                headers=self._get_headers(),
            )
            logger.info(
                "[AskUserQuestion] finalize: content_id=%s, status=%s, message_id=%s, answers=%d",
                content_id,
                status,
                message_id,
                len(value.get("answers") or []),
            )
        except Exception:
            logger.exception("[AskUserQuestion] finalize 失败: session=%s", self.session_code)

    def handle_user_input_saved(self, event) -> None:
        """处理 user 输入落库事件（所有带 input 路径）：直调 _do_create_content 写 user 记录。"""
        value = event.value if isinstance(event.value, dict) else {}
        try:
            self._do_create_content(
                payload={
                    "session_code": self.session_code,
                    "role": PromptRole.USER.value,
                    "content": value.get("content") or "",
                    "status": "success",
                    "property": {"turn_id": value.get("turn_id") or ""},
                },
                headers=self._get_headers(),
            )
        except Exception:
            logger.exception("[AskUserQuestion] user 落库失败: session=%s", self.session_code)

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
        """处理 thinking 消息开始事件

        使用共享 should_switch_thinking_step 决定 _thinking_content 清空时机：
        - 新 turn 开始（_thinking_active=False）：清空 _thinking_content
        - 同 turn 内 step 切换（_thinking_active=True）：不清空，累积多 step 内容

        DB 侧事件不含 index，用 _thinking_active 替代 thinking_process 的存在性判定。
        通过构造 thinking_process={"index": 0}（当 _thinking_active=True 时）与
        reasoning_data={"index": 1} 触发共享函数的 switch=True 分支，复用同一份判定逻辑：
        - _thinking_active=True 时 should_switch_thinking_step 返回 True（step 切换），不清空
        - _thinking_active=False 时 should_switch_thinking_step 返回 False（无前序 step），清空
        """
        thinking_process = {"index": 0} if self._thinking_active else None
        reasoning_data = {"index": 1, "type": "text", "text": ""}
        if not should_switch_thinking_step(thinking_process, reasoning_data):
            # 新 turn 开始，清空
            self._thinking_content = ""
        # step 切换时不清空，保留前序 step 内容
        self._thinking_active = True

    def handle_thinking_message_content(self, event: BaseEvent) -> None:
        """处理 thinking 消息内容事件，累积 thinking 内容"""
        # event 应该有 delta 属性
        delta = getattr(event, "delta", "") or ""
        self._thinking_content += delta

    def handle_thinking_message_end(self, event: BaseEvent) -> None:
        """处理 thinking 消息结束事件

        不重置 _thinking_active：SSE 侧 step 切换时先发 THINKING_TEXT_MESSAGE_END
        再发 THINKING_END/THINKING_START/THINKING_TEXT_MESSAGE_START，若此处重置
        _thinking_active，下一个 START 会被误判为新 turn 开始而清空前序 step 内容。
        _thinking_active 只在 turn 级清理点（handle_model_end/handle_run_finished/
        handle_run_error/_write_cancelled_messages）重置。
        """

    @staticmethod
    def _unwrap_interrupt_source(source: Any) -> Any:
        return unwrap_interrupt_source(source)

    @staticmethod
    def _get_interrupt_value(source: Any, *keys: str) -> Any:
        return get_interrupt_value(source, *keys)

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
                self._thinking_active = False
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
                serialized_reason = serialized.get("reason")

                if serialized_reason == ASK_USER_QUESTION_REASON:
                    # ask_user_question 路径：启用 extract_builtin_property
                    # 字段集：questions/options/answers/multiSelect（无 callback_token/ticket_sn/tool_name）
                    builtin_property = AskUserQuestionHandler().extract_builtin_property(
                        interrupt_id, interrupt, graph_thread_id=getattr(event, "thread_id", "")
                    )
                    logger.info(
                        "[AskUserQuestion] handle_run_finished interrupt builtin_property: "
                        "interrupt_id=%s, reason=%s, keys=%s",
                        interrupt_id,
                        serialized_reason,
                        list(builtin_property.keys()),
                    )
                else:
                    # approval 路径：现有逻辑零改动（base.py 原 L543-562）
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
                        "tool_name": metadata.get("toolName")
                        or serialized.get("toolName")
                        or serialized.get("toolName"),
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
        elif outcome and outcome_type != "interrupt":
            # ask_user_question 续流的 DB 终态写入由 agent 侧 ChatCompletionAgent.execute()
            # 前置派发的会话回写事件负责（handle_ask_user_question_finalize），
            # SSE 层不再承担 DB 写入职责（对齐"谁产生谁写入"原则）。
            # approval 的 interrupt 状态由审批回调 API 更新。
            logger.info(
                "[handle_run_finished] outcome != interrupt, session_code=%s, outcome_type=%s",
                self.session_code,
                outcome_type,
            )

        # 清理
        self._streaming_messages.clear()
        self._thinking_content = ""
        self._thinking_active = False

    def _resolve_pending_interrupts(self) -> None:
        """续流成功后更新 DB 中的 pending interrupt 记录为 resolved。

        BaseSessionWriter 默认空实现（无 DB 查询能力）。子类（如 AGUISessionWriter）
        可重写此方法，从 DB 查询 pending 的 interrupt 记录并更新为 resolved 终态。
        """

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
        with self._cancelled_messages_lock:
            if self._cancelled_messages_written:
                logger.debug("Cancelled messages already written for session_code=%s", self.session_code)
                return
            # 事件处理可能来自 generator 与 producer 两个线程。先占位再执行远端写入，
            # 避免首个请求尚未返回时，RUN_FINISHED 再次进入并产生重复记录。
            self._cancelled_messages_written = True

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
        self._thinking_active = False

    def handle_model_end(self, event: RawEvent | CustomEvent) -> None:
        """处理模型输出结束事件，回写 assistant 消息

        Args:
            event: RawEvent（on_chat_model_end）或 CustomEvent（aidev_session_chat_model_end）

        CustomEvent 分支直接读 SSE 侧 build_model_end_payload 构造的扁平 payload
        （message_id/content/tool_calls/deferred_tool_calls/reasoning_content/reasoning_duration），
        不再 messages_from_dict 反序列化、不再二次推导 tool_calls/content。
        RawEvent 分支（理论上已不触发，见 _dispatch_custom_event_direct 注释）保留兼容，
        统一调 build_model_end_payload 构造 payload，逻辑与 CustomEvent 分支一致。
        """
        if isinstance(event, CustomEvent):
            payload = event.value if isinstance(event.value, dict) else None
            if not payload:
                return
            message_id = payload["message_id"]
            content = payload["content"]
            tool_calls = payload["tool_calls"]
            deferred_tool_calls = payload["deferred_tool_calls"]
            reasoning_content = payload.get("reasoning_content")
            reasoning_duration = payload.get("reasoning_duration", 0)
        else:
            # RawEvent 路径保留（LangGraph 直产 RawEvent 的兼容场景，理论上已不触发）
            output_message = event.event.get("data", {}).get("output")
            if not output_message:
                return
            payload = build_model_end_payload(output_message, self._tools_mapping)
            message_id = payload["message_id"]
            content = payload["content"]
            tool_calls = payload["tool_calls"]
            deferred_tool_calls = payload["deferred_tool_calls"]
            reasoning_content = payload["reasoning_content"]
            reasoning_duration = payload["reasoning_duration"]

        if message_id in self._written_message_ids:
            return

        if reasoning_content:
            self._write_reasoning_message(
                message_id=message_id,
                reasoning_content=reasoning_content,
                duration=reasoning_duration,
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
        self._thinking_active = False
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

        # 映射状态：success -> complete, error -> error（v2 协议）
        is_error = output_message.status == "error"
        platform_status = "error" if is_error else "complete"

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

    def handle_tool_call_result(self, event: ExtendToolCallResultEvent) -> None:
        """处理工具调用结果事件，回写 tool 消息

        直接消费 ExtendToolCallResultEvent 的结构化字段，替代 handle_tool_finish 的二次解包。
        _immediate 场景通过 skip_db 标记跳过 DB 写入。
        additional_metadata 携带完整 additional_kwargs，零信息丢失写入 builtin_property。

        Args:
            event: ExtendToolCallResultEvent（含 tool_call_id / message_id / content / is_error /
                additional_metadata / skip_db）
        """
        # _immediate 场景跳过 DB 写入
        if getattr(event, "skip_db", False):
            return

        tool_call_id = event.tool_call_id
        if tool_call_id in self._written_message_ids:
            return

        # 直接使用事件字段，不再从 event.value 解包 ToolMessage
        is_error = bool(event.is_error) if event.is_error is not None else False
        platform_status = "error" if is_error else "complete"

        # 补充写入延迟的 tool_calls 到对应的 assistant 消息
        if not is_error:
            self._flush_deferred_tool_call(tool_call_id, tool_name=None)

        # additional_metadata 携带完整 additional_kwargs dict
        additional_metadata = getattr(event, "additional_metadata", None) or {}

        self._create_session_content(
            message_id=event.message_id,
            role=PromptRole.TOOL.value,
            content=event.content,
            status=platform_status,
            builtin_property={
                "message_id": tool_call_id,
                "tool_call_id": tool_call_id,
                "additional_kwargs": additional_metadata,
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
        self._thinking_active = False

    def handle_reference_document(self, event: RawEvent | CustomEvent) -> None:
        """处理引用文档事件，回写 activity 消息

        Args:
            event: RawEvent（on_custom_event）或 knowledge_rag_result 的 CustomEvent
        """
        if isinstance(event, CustomEvent):
            event_data = event.raw_event.get("data", {}) if event.raw_event else {}
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

    def handle_artifacts_generated(self, event: CustomEvent) -> None:
        """回写本轮产物识别事件: 优先合并进最近一条 assistant 消息的 property.artifacts(顶层数组);
        合并成功则不再单独落库 activity 消息; 合并失败(无 assistant/异常)时回退单独建 role=activity 消息, 保证产物不丢失。
        SSE 分发与 DB 落库为两条独立路径, 本方法只改落库, 不影响流式 custom event。子类覆写 _merge_artifacts_into_last_assistant 实现合并。"""
        value = event.value if isinstance(event.value, dict) else {}
        artifacts = value.get("artifacts") or []
        run_id = value.get("runId") or ""
        message_id = f"artifacts_{run_id or uuid.uuid4().hex[:12]}"
        if message_id in self._written_message_ids:
            return
        if artifacts and self._merge_artifacts_into_last_assistant(artifacts, value):
            self._written_message_ids.add(message_id)
            return
        self._create_session_content(
            message_id=message_id,
            role=PromptRole.ACTIVITY.value,
            content=json.dumps(value, ensure_ascii=False),
            status="success",
            builtin_property={
                "message_id": message_id,
                "type": ActivityType.ARTIFACTS_GENERATED.value,
                "run_id": run_id,
            },
        )
        self._written_message_ids.add(message_id)

    def _merge_artifacts_into_last_assistant(self, artifacts: list, value: dict) -> bool:
        """把 artifacts 合并进本会话最近一条 assistant 消息的 property.artifacts。默认返回 False(走兜底建 activity);
        能查询/更新已落库消息的子类应覆写此方法, 返回是否合并成功。"""
        return False

    @staticmethod
    def _pick_last_assistant(contents: list):
        """内存选出 id 最大的 assistant 记录; 元素可为 dict 或 ORM 对象; 无则 None。"""
        last = None
        last_id = None
        for item in contents or []:
            role = item.get("role") if isinstance(item, dict) else getattr(item, "role", None)
            if role != PromptRole.ASSISTANT.value:
                continue
            item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
            if item_id is None:
                continue
            if last_id is None or item_id > last_id:
                last_id = item_id
                last = item
        return last

    @staticmethod
    def _merge_artifacts_into_property(prop: dict, artifacts: list) -> dict:
        """把 artifacts 合并进 prop['artifacts'](顶层数组), 按 outputId 去重后追加。"""
        existing = list(prop.get("artifacts") or [])
        existing_ids = set(x.get("outputId") for x in existing if isinstance(x, dict) and x.get("outputId"))
        for art in artifacts or []:
            if not isinstance(art, dict):
                continue
            output_id = art.get("outputId")
            if output_id and output_id in existing_ids:
                continue
            existing.append(art)
            if output_id:
                existing_ids.add(output_id)
        prop["artifacts"] = existing
        return prop

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

        写入失败时不阻断 Agent 执行，但递增 _write_error_count，
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
