import inspect
import json
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from logging import getLogger
from typing import Any, Callable, Literal

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateDeltaEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ThinkingTextMessageContentEvent,
    ThinkingTextMessageEndEvent,
    ThinkingTextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from langchain_core.messages import (
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig, ensure_config
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from aidev_agent.utils.event import RunId

from .event_builders import build_model_end_payload, should_end_thinking, should_switch_thinking_step
from .events import (
    ExtendThinkingEndEvent,
)
from .types import (
    CustomEventNames,
    Interrupt,
    LangGraphEventTypes,
    LangGraphReasoning,
    MessageInProgress,
    MessagesInProgressRecord,
    MessageSnapshotEventExtend,
    RunFinishedInterruptOutcome,
    RunFinishedSuccessOutcome,
    RunMetadata,
    SchemaKeys,
    SessionPersistenceEventNames,
    State,
    serialize_run_finished_outcome,
)
from .utils import (
    DEFAULT_SCHEMA_KEYS,
    camel_to_snake,
    filter_object_by_schema_keys,
    get_schema_keys,
    json_safe_stringify,
    langchain_messages_to_agui,
    make_json_safe,
    resolve_message_content,
    resolve_reasoning_content,
)

ProcessedEvents = (
    TextMessageStartEvent
    | TextMessageContentEvent
    | TextMessageEndEvent
    | ToolCallStartEvent
    | ToolCallArgsEvent
    | ToolCallEndEvent
    | StateSnapshotEvent
    | StateDeltaEvent
    | MessageSnapshotEventExtend
    | CustomEvent
    | RunStartedEvent
    | RunFinishedEvent
    | RunErrorEvent
    | StepStartedEvent
    | StepFinishedEvent
)

logger = getLogger(__name__)


class LangGraphAgent:
    def __init__(
        self,
        *,
        name: str,
        graph: CompiledStateGraph,
        description: str | None = None,
        config: RunnableConfig | None | dict = None,
        cancel_checker: Callable[[], bool] | None = None,
    ):
        self.name = name
        self.description = description
        self.graph = graph
        self.config = config or {}
        self.messages_in_process: MessagesInProgressRecord = {}
        self.active_run: RunMetadata | None = None
        self.constant_schema_keys = ["messages", "tools"]
        self.front_end_display = True
        # 取消检测回调，返回 True 表示应该取消
        self._cancel_checker = cancel_checker

    def _dispatch_event(self, event: ProcessedEvents) -> str:
        if getattr(event, "raw_event", None):
            event.raw_event = make_json_safe(event.raw_event)

        return event

    async def run(self, input: RunAgentInput) -> AsyncGenerator[str, None]:
        # 获取 forwarded_props, 并且进行命名格式转换
        # aidev_agent sdk使用 和 bkai平台的数据保存 都是 snake 格式
        # 根据当前 AGUI 协议，后端向前端推送的都是 camel 格式
        forwarded_props = {}
        if hasattr(input, "forwarded_props") and input.forwarded_props:
            forwarded_props = {camel_to_snake(k): v for k, v in input.forwarded_props.items()}
        # 更新 RunAgentInput 和 config
        # 避免 input state 和 input messages 为空
        # 强制要求 config 的 configurable 中的 thread_id 指向 thread_id
        input = input.model_copy(
            update={
                "forwarded_props": forwarded_props,
                "state": input.state or {},
                "messages": input.messages or [],
            }
        )
        config = ensure_config(self.config.copy() if self.config else {})
        config["configurable"] = {
            **(config.get("configurable", {})),
            "thread_id": input.thread_id,
        }
        # 启动流，并且把事件推送出去
        async for event in self._handle_stream_events(input, config):
            if event.type != EventType.STATE_SNAPSHOT:
                yield event

    async def _handle_stream_events(self, input: RunAgentInput, config: RunnableConfig) -> AsyncGenerator[str, None]:
        thread_id = input.thread_id
        assert thread_id, "input.thread_id must not be empty"
        INITIAL_ACTIVE_RUN = {
            "id": input.run_id,
            "thread_id": thread_id,
            "thinking_process": None,
            "node_name": None,
            "has_function_streaming": False,
            "has_text_output": False,  # 是否有 AI 文本输出（根据流式是否有TEXT_MESSAGE_START）
            "started_at": datetime.now(timezone.utc),  # 供子类做本轮增量识别（如 artifacts_generated）
        }
        self.active_run = INITIAL_ACTIVE_RUN

        forwarded_props = input.forwarded_props
        node_name_input = forwarded_props.get("node_name", None) if forwarded_props else None

        self.active_run["manually_emitted_state"] = None

        agent_state = await self.graph.aget_state(config)
        resume_input = forwarded_props.get("command", {}).get("resume", None)

        if (
            resume_input is None
            and thread_id
            and self.active_run.get("node_name") != "__end__"
            and self.active_run.get("node_name")
        ):
            self.active_run["mode"] = "continue"
        else:
            self.active_run["mode"] = "start"

        prepared_stream_response = await self.prepare_stream(input=input, agent_state=agent_state, config=config)

        yield self._dispatch_event(
            RunStartedEvent(
                type=EventType.RUN_STARTED,
                thread_id=thread_id,
                run_id=self.active_run["id"],
            )
        )
        self.handle_node_change(node_name_input)

        # In case of resume (interrupt), re-start resumed step
        if resume_input and self.active_run.get("node_name"):
            for ev in self.handle_node_change(self.active_run.get("node_name")):
                yield ev

        state = prepared_stream_response["state"]
        stream = prepared_stream_response["stream"]
        config = prepared_stream_response["config"]
        events_to_dispatch = prepared_stream_response.get("events_to_dispatch", None)

        if events_to_dispatch is not None and len(events_to_dispatch) > 0:
            for event in events_to_dispatch:
                yield self._dispatch_event(event)
            return

        should_exit = False
        current_graph_state = state
        # 标记是否被取消（用于后续发送正确的 RunFinishedEvent）
        _cancelled = False

        async for event in stream:
            # 检测取消信号（在每次循环迭代时检查）
            if self._cancel_checker and self._cancel_checker():
                logger.info(f"Agent cancelled by cancel_checker, thread_id={thread_id}")
                _cancelled = True
                break

            if event["event"] == "error":
                yield self._dispatch_event(
                    RunErrorEvent(
                        type=EventType.RUN_ERROR,
                        message=event["data"]["message"],
                        raw_event=event,
                    )
                )
                break

            current_node_name = event.get("metadata", {}).get("langgraph_node")
            event_type = event.get("event")
            self.active_run["id"] = event.get("run_id")
            exiting_node = False

            if event_type == "on_chain_end" and isinstance(event.get("data", {}).get("output"), dict):
                current_graph_state.update(event["data"]["output"])
                exiting_node = self.active_run["node_name"] == current_node_name

            should_exit = should_exit or (event_type == "on_custom_event" and event["name"] == "exit")

            if current_node_name and current_node_name != self.active_run.get("node_name"):
                for ev in self.handle_node_change(current_node_name):
                    yield ev

            updated_state = self.active_run.get("manually_emitted_state") or current_graph_state
            has_state_diff = updated_state != state
            if exiting_node or (has_state_diff and not self.get_message_in_progress(self.active_run["id"])):
                state = updated_state
                self.active_run["prev_node_name"] = self.active_run["node_name"]
                current_graph_state.update(updated_state)
                yield self._dispatch_event(
                    StateSnapshotEvent(
                        type=EventType.STATE_SNAPSHOT,
                        snapshot=self.get_state_snapshot(state),
                        raw_event=event,
                    )
                )
            async for single_event in self._handle_single_event(event, state):
                yield self._dispatch_event(single_event)

        # 如果被取消，跳过正常的状态获取，直接发送结束事件
        if _cancelled:
            # 结束当前步骤（如果有）
            for ev in self.handle_node_change(None):
                yield ev

            # 根据是否有 AI 文本输出决定事件类型：
            # - 无 AI 输出（仅有 thinking/tool/知识库等）：发 RUN_ERROR，触发暂停补写逻辑
            # - 有 AI 输出：发 RUN_FINISHED(cancelled)，正常回写
            has_text_output = self.active_run.get("has_text_output", False)
            logger.info(
                "Agent cancelled: thread_id=%s, has_text_output=%s",
                thread_id,
                has_text_output,
            )
            if not has_text_output:
                yield self._dispatch_event(
                    RunErrorEvent(
                        type=EventType.RUN_ERROR,
                        message=RunId.CANCELLED_MESSAGE,
                    )
                )
            else:
                yield self._dispatch_event(
                    RunFinishedEvent(
                        type=EventType.RUN_FINISHED,
                        thread_id=thread_id,
                        run_id=RunId.CANCELLED,
                        outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
                    )
                )
            self.active_run = INITIAL_ACTIVE_RUN
            return

        # Agent 已经退出，检查状态和退出原因
        state = await self.graph.aget_state(config)

        tasks = state.tasks if len(state.tasks) > 0 else None
        interrupts = tasks[0].interrupts if tasks else []

        writes = state.metadata.get("writes", {}) or {}
        node_name = self.active_run["node_name"] if interrupts else next(iter(writes), None)
        next_nodes = state.next or ()
        is_end_node = len(next_nodes) == 0 and not interrupts

        node_name = "__end__" if is_end_node else node_name

        interrupt_values = [self._normalize_interrupt_value(interrupt.value) for interrupt in interrupts]

        if self.active_run.get("node_name") != node_name:
            for ev in self.handle_node_change(node_name):
                yield ev

        state_values = state.values if state.values else state
        for ev in self.handle_node_change(None):
            yield ev

        final_snapshot_events = self._build_terminal_snapshot_events(state_values)
        yield self._dispatch_event(final_snapshot_events[0])

        # 续流（resume）场景不再下发终态 MESSAGES_SNAPSHOT：
        # resume 时 state["messages"] 仅来自中断点的 checkpoint，并非完整会话历史
        if not resume_input:
            yield self._dispatch_event(final_snapshot_events[1])

        # 本轮产物识别 hook（子类实现，默认 no-op）；异常内部兜底，不阻断 RUN_FINISHED
        async for ev in self._emit_run_end_extras(state_values, thread_id):
            yield ev

        # 构造 outcome（使用官方类型）
        if interrupt_values:
            outcome = RunFinishedInterruptOutcome(interrupts=interrupt_values)
        else:
            outcome = RunFinishedSuccessOutcome()

        yield self._dispatch_event(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=thread_id,
                run_id=self.active_run["id"],
                outcome=serialize_run_finished_outcome(outcome),
            )
        )
        # Reset active run to how it was before the stream started
        self.active_run = INITIAL_ACTIVE_RUN

    @staticmethod
    def _normalize_interrupt_value(value: Any) -> Interrupt:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {"message": value}
        if not isinstance(value, dict):
            value = {"message": str(value)}

        _metadata = value.get("metadata")
        metadata = _metadata.copy() if isinstance(_metadata, dict) else {}
        interrupt_id = value.get("id") or value.get("interruptId")
        if not interrupt_id:
            logger.warning(
                "Interrupt value missing id/interruptId, generated fallback. reason=%s, toolCallId=%s, message=%s",
                value.get("reason"),
                value.get("toolCallId"),
                str(value.get("message"))[:200],
            )
            interrupt_id = f"int-{uuid.uuid4().hex[:12]}"
        return Interrupt(
            id=interrupt_id,
            reason=value.get("reason") or "tool_call",
            message=value.get("message"),
            toolCallId=value.get("toolCallId"),  # 驼峰命名
            metadata=metadata or None,
        )

    async def _emit_run_end_extras(self, state_values: State, thread_id: str) -> AsyncGenerator[Any, None]:
        """本轮 run 收尾扩展点：MESSAGES_SNAPSHOT 之后、RUN_FINISHED 之前每 run 触发一次。

        父类默认 no-op；子类覆写以 yield 自定义事件，异常须自行兜底避免阻断 RUN_FINISHED。
        典型用法见 :class:`AidevAGUIAgent` 的 ``run_end_extras_hook`` 注入模式。
        """
        return
        yield  # pragma: no cover - 让本方法成为 async generator

    def _build_terminal_snapshot_events(
        self, state_values: State
    ) -> tuple[StateSnapshotEvent, MessageSnapshotEventExtend]:
        return (
            StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot=self.get_state_snapshot(state_values),
            ),
            MessageSnapshotEventExtend(
                type=EventType.MESSAGES_SNAPSHOT,
                messages=langchain_messages_to_agui(state_values.get("messages", [])),
            ),
        )

    async def prepare_stream(self, input: RunAgentInput, agent_state: State, config: RunnableConfig):
        forwarded_props = input.forwarded_props
        thread_id = input.thread_id
        interrupts = agent_state.tasks[0].interrupts if agent_state.tasks and len(agent_state.tasks) > 0 else []
        has_active_interrupts = len(interrupts) > 0
        resume_input = forwarded_props.get("command", {}).get("resume", None)

        state = input.state

        # 运行时状态设置（保留在 agent.py，供 _handle_stream_events / _handle_single_event 读取）
        self.active_run["current_graph_state"] = agent_state.values.copy()
        self.active_run["current_graph_state"].update(state)
        self.active_run["schema_keys"] = self.get_schema_keys(config)

        # interrupt 事件构造（保留在 agent.py）
        events_to_dispatch = []
        if has_active_interrupts and not resume_input:
            interrupt_values = [self._normalize_interrupt_value(interrupt.value) for interrupt in interrupts]
            terminal_state = agent_state.values if agent_state.values else state
            events_to_dispatch.extend(self._build_terminal_snapshot_events(terminal_state))

            outcome = RunFinishedInterruptOutcome(interrupts=interrupt_values)
            events_to_dispatch.append(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=thread_id,
                    run_id=self.active_run["id"],
                    outcome=serialize_run_finished_outcome(outcome),
                )
            )
            return {
                "stream": None,
                "state": None,
                "config": None,
                "events_to_dispatch": events_to_dispatch,
            }

        # continue 模式 state 更新
        if self.active_run["mode"] == "continue":
            await self.graph.aupdate_state(config, state, as_node=self.active_run.get("node_name"))

        # 统一 stream 启动
        subgraphs_stream_enabled = forwarded_props.get("stream_subgraphs") if forwarded_props else False

        kwargs = self.get_stream_kwargs(
            input=input.stream_input,
            subgraphs=bool(subgraphs_stream_enabled),
            version="v2",
            config=config,
        )
        stream = self.graph.astream_events(**kwargs)

        return {"stream": stream, "state": state, "config": config}

    def get_message_in_progress(self, run_id: str) -> MessageInProgress | None:
        return self.messages_in_process.get(run_id)

    def set_message_in_progress(self, run_id: str, data: MessageInProgress):
        current_message_in_progress = self.messages_in_process.get(run_id, {}) or {}
        self.messages_in_process[run_id] = {
            **current_message_in_progress,
            **data,
        }

    def get_schema_keys(self, config) -> SchemaKeys:
        # 转为独立的工具函数，但是不影响调用方
        return get_schema_keys(self.graph, config, self.constant_schema_keys)

    def get_state_snapshot(self, state: State) -> State:
        schema_keys = self.active_run["schema_keys"]
        if schema_keys and schema_keys.get("output"):
            state = filter_object_by_schema_keys(state, [*DEFAULT_SCHEMA_KEYS, *schema_keys["output"]])
        return state

    async def _handle_single_event(
        self,
        event: Any,
        state: State,  # noqa: ARG002
    ) -> AsyncGenerator[BaseEvent, None]:
        event_type = event.get("event")
        if event_type == LangGraphEventTypes.OnChatModelStream:
            async for ev in self._handle_on_chat_model_stream_event(event):
                yield ev
        elif event_type == LangGraphEventTypes.OnChatModelEnd:
            async for ev in self._handle_on_chat_model_end_event(event):
                yield ev
        elif event_type == LangGraphEventTypes.OnCustomEvent:
            async for ev in self._handle_on_custom_event(event):
                yield ev
        elif event_type == LangGraphEventTypes.OnToolEnd:
            async for ev in self._handle_on_tool_end_event(event):
                yield ev

    async def _handle_on_chat_model_stream_event(self, event: Any) -> AsyncGenerator[BaseEvent, None]:
        """协调器：解析 chunk → ctx + thinking/PredictState + 按 event 类型分发到子方法。"""
        # 当 front_end_display 为 False 时，跳过OnChatModelStream事件
        if not self.front_end_display:
            return
        should_emit_messages = event["metadata"].get("emit-messages", True)
        should_emit_tool_calls = event["metadata"].get("emit-tool-calls", True)

        if event["data"]["chunk"].response_metadata.get("finish_reason", None):
            return

        current_stream = self.get_message_in_progress(self.active_run["id"])
        has_current_stream = bool(current_stream and current_stream.get("id"))
        tool_call_data = event["data"]["chunk"].tool_call_chunks[0] if event["data"]["chunk"].tool_call_chunks else None
        predict_state_metadata = event["metadata"].get("predict_state", [])
        tool_call_used_to_predict_state = False
        if tool_call_data and tool_call_data.get("name") and predict_state_metadata:
            tool_call_used_to_predict_state = any(
                predict_tool.get("tool") == tool_call_data["name"] for predict_tool in predict_state_metadata
            )

        # 判断是否为并行工具调用切换：当前 chunk 带有 name+id（新工具起始），
        # 且 current_stream 中已有另一个工具在进行中（tool_call_id 不同）
        is_parallel_tool_switch = (
            tool_call_data
            and tool_call_data.get("name")
            and tool_call_data.get("id")
            and has_current_stream
            and current_stream.get("tool_call_id")
            and current_stream["tool_call_id"] != tool_call_data["id"]
        )

        is_tool_call_start_event = (
            tool_call_data
            and tool_call_data.get("name")
            and (not has_current_stream or not current_stream.get("tool_call_id") or is_parallel_tool_switch)
        )
        is_tool_call_args_event = (
            has_current_stream and current_stream.get("tool_call_id") and tool_call_data and tool_call_data.get("args")
        )
        is_tool_call_end_event = has_current_stream and current_stream.get("tool_call_id") and not tool_call_data

        if is_tool_call_start_event or is_tool_call_end_event or is_tool_call_args_event:
            self.active_run["has_function_streaming"] = True

        reasoning_data = resolve_reasoning_content(event["data"]["chunk"]) if event["data"]["chunk"] else None
        message_content = (
            resolve_message_content(event["data"]["chunk"].content)
            if event["data"]["chunk"] and event["data"]["chunk"].content
            else None
        )
        is_message_content_event = tool_call_data is None and message_content
        is_message_end_event = (
            has_current_stream
            and not current_stream.get("tool_call_id")
            and not is_message_content_event
            and not is_tool_call_start_event
        )

        # thinking 逻辑保留在协调器（不拆分）
        if reasoning_data:
            for each in self.handle_thinking_event(reasoning_data):
                yield each

        if should_end_thinking(self.active_run.get("thinking_process"), reasoning_data):
            yield ThinkingTextMessageEndEvent(
                type=EventType.THINKING_TEXT_MESSAGE_END,
            )
            yield ExtendThinkingEndEvent(
                duration=event.get("data", {}).get("chunk").additional_kwargs.get("reasoning_time", 0),
                type=EventType.THINKING_END,
            )
            self.active_run["thinking_process"] = None

        # PredictState 逻辑保留在协调器（不拆分）
        if tool_call_used_to_predict_state:
            yield CustomEvent(
                type=EventType.CUSTOM,
                name="PredictState",
                value=predict_state_metadata,
                raw_event=event,
            )

        ctx = {
            "current_stream": current_stream,
            "has_current_stream": has_current_stream,
            "tool_call_data": tool_call_data,
            "is_parallel_tool_switch": is_parallel_tool_switch,
            "is_tool_call_start_event": is_tool_call_start_event,
            "is_tool_call_args_event": is_tool_call_args_event,
            "is_tool_call_end_event": is_tool_call_end_event,
            "is_message_content_event": is_message_content_event,
            "is_message_end_event": is_message_end_event,
            "message_content": message_content,
            "should_emit_messages": should_emit_messages,
            "should_emit_tool_calls": should_emit_tool_calls,
        }

        if is_tool_call_end_event:
            async for ev in self._handle_tool_call_end_stream_event(event, ctx):
                yield ev
        elif is_message_end_event:
            async for ev in self._handle_message_end_stream_event(event, ctx):
                yield ev
        elif is_tool_call_start_event and should_emit_tool_calls:
            async for ev in self._handle_tool_call_start_stream_event(event, ctx):
                yield ev
        elif is_tool_call_args_event and should_emit_tool_calls:
            async for ev in self._handle_tool_call_args_stream_event(event, ctx):
                yield ev
        elif is_message_content_event and should_emit_messages:
            async for ev in self._handle_message_content_stream_event(event, ctx):
                yield ev

    async def _handle_tool_call_end_stream_event(self, event: Any, ctx: dict) -> AsyncGenerator[BaseEvent, None]:
        """tool_call_end 分支（ 拆分自 _handle_on_chat_model_stream_event）。"""
        current_stream = ctx["current_stream"]
        yield ToolCallEndEvent(
            type=EventType.TOOL_CALL_END,
            tool_call_id=current_stream["tool_call_id"],
            raw_event=event,
        )
        self.messages_in_process[self.active_run["id"]] = None

    async def _handle_message_end_stream_event(self, event: Any, ctx: dict) -> AsyncGenerator[BaseEvent, None]:
        """message_end 分支（ 拆分自 _handle_on_chat_model_stream_event）。"""
        current_stream = ctx["current_stream"]
        yield TextMessageEndEvent(
            type=EventType.TEXT_MESSAGE_END,
            message_id=current_stream["id"],
            raw_event=event,
        )
        self.messages_in_process[self.active_run["id"]] = None

    async def _handle_tool_call_start_stream_event(self, event: Any, ctx: dict) -> AsyncGenerator[BaseEvent, None]:
        """tool_call_start 分支（ 拆分自 _handle_on_chat_model_stream_event）。"""
        current_stream = ctx["current_stream"]
        has_current_stream = ctx["has_current_stream"]
        is_parallel_tool_switch = ctx["is_parallel_tool_switch"]
        tool_call_data = ctx["tool_call_data"]

        if has_current_stream and not current_stream.get("tool_call_id"):
            yield TextMessageEndEvent(
                type=EventType.TEXT_MESSAGE_END,
                message_id=current_stream["id"],
                raw_event=event,
            )
        elif is_parallel_tool_switch:
            # 并行工具调用切换：先结束上一个工具调用
            yield ToolCallEndEvent(
                type=EventType.TOOL_CALL_END,
                tool_call_id=current_stream["tool_call_id"],
                raw_event=event,
            )
        yield ToolCallStartEvent(
            type=EventType.TOOL_CALL_START,
            tool_call_id=tool_call_data["id"],
            tool_call_name=tool_call_data["name"],
            parent_message_id=event["data"]["chunk"].id,
            raw_event=event,
        )
        self.set_message_in_progress(
            self.active_run["id"],
            MessageInProgress(
                id=event["data"]["chunk"].id,
                tool_call_id=tool_call_data["id"],
                tool_call_name=tool_call_data["name"],
            ),
        )
        current_stream = self.get_message_in_progress(self.active_run["id"])
        if tool_call_data.get("args"):
            yield ToolCallArgsEvent(
                type=EventType.TOOL_CALL_ARGS,
                tool_call_id=current_stream["tool_call_id"],
                delta=tool_call_data["args"],
                raw_event=event,
            )

    async def _handle_tool_call_args_stream_event(self, event: Any, ctx: dict) -> AsyncGenerator[BaseEvent, None]:
        """tool_call_args 分支（ 拆分自 _handle_on_chat_model_stream_event）。"""
        current_stream = ctx["current_stream"]
        tool_call_data = ctx["tool_call_data"]
        yield ToolCallArgsEvent(
            type=EventType.TOOL_CALL_ARGS,
            tool_call_id=current_stream["tool_call_id"],
            delta=tool_call_data["args"],
            raw_event=event,
        )

    async def _handle_message_content_stream_event(self, event: Any, ctx: dict) -> AsyncGenerator[BaseEvent, None]:
        """message_content 分支（ 拆分自 _handle_on_chat_model_stream_event）。"""
        current_stream = ctx["current_stream"]
        message_content = ctx["message_content"]

        if not bool(current_stream and current_stream.get("id")):
            yield TextMessageStartEvent(
                type=EventType.TEXT_MESSAGE_START,
                role="assistant",
                message_id=event["data"]["chunk"].id,
                raw_event=event,
            )
            # 标记已有 AI 文本输出，用于取消时决定发 RUN_ERROR 还是 RUN_FINISHED
            self.active_run["has_text_output"] = True
            self.set_message_in_progress(
                self.active_run["id"],
                MessageInProgress(
                    id=event["data"]["chunk"].id,
                    tool_call_id=None,
                    tool_call_name=None,
                ),
            )
            current_stream = self.get_message_in_progress(self.active_run["id"])

        yield TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT,
            message_id=current_stream["id"],
            delta=message_content,
            raw_event=event,
        )

    async def _handle_on_chat_model_end_event(self, event: Any) -> AsyncGenerator[BaseEvent, None]:
        if not self.front_end_display:
            return
        # ChatModelEnd CustomEvent：把"模型这一轮的完整输出快照"分发给 DB 侧。
        # SSE 侧 AidevAGUIAgent.run() 通过 skip_encode_custom 跳过编码（不进入 SSE 输出）。
        # 顺序：在消息收尾事件（ToolCallEnd/TextMessageEnd）之后发出，确保 DB 侧拿到的是收尾后的完整态。
        # output is None 主要见于模型供应商 adapter 异常路径，不构造事件。
        out = event.get("data", {}).get("output")
        if out is not None:
            yield CustomEvent(
                type=EventType.CUSTOM,
                name=SessionPersistenceEventNames.ChatModelEnd.value,
                value=build_model_end_payload(out, getattr(self, "_tool_mapping", {}) or {}),
            )

        if self.get_message_in_progress(self.active_run["id"]) and self.get_message_in_progress(
            self.active_run["id"]
        ).get("tool_call_id"):
            yield ToolCallEndEvent(
                type=EventType.TOOL_CALL_END,
                tool_call_id=self.get_message_in_progress(self.active_run["id"])["tool_call_id"],
                raw_event=event,
            )
            self.messages_in_process[self.active_run["id"]] = None
        elif self.get_message_in_progress(self.active_run["id"]) and self.get_message_in_progress(
            self.active_run["id"]
        ).get("id"):
            yield TextMessageEndEvent(
                type=EventType.TEXT_MESSAGE_END,
                message_id=self.get_message_in_progress(self.active_run["id"])["id"],
                raw_event=event,
            )
            self.messages_in_process[self.active_run["id"]] = None

    async def _handle_on_custom_event(self, event: Any) -> AsyncGenerator[BaseEvent, None]:
        # 如果接收到 front_end_display 标识位的信息，则更新 front_end_display
        custom_data = event.get("data", {})
        if isinstance(custom_data, dict) and "front_end_display" in custom_data:
            self.front_end_display = custom_data["front_end_display"]
            if not self.front_end_display:
                return

        if event["name"] == CustomEventNames.ManuallyEmitMessage:
            yield TextMessageStartEvent(
                type=EventType.TEXT_MESSAGE_START,
                role="assistant",
                message_id=event["data"]["message_id"],
                raw_event=event,
            )
            # 标记已有 AI 文本输出
            self.active_run["has_text_output"] = True
            yield TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id=event["data"]["message_id"],
                delta=event["data"]["message"],
                raw_event=event,
            )
            yield TextMessageEndEvent(
                type=EventType.TEXT_MESSAGE_END,
                message_id=event["data"]["message_id"],
                raw_event=event,
            )

        elif event["name"] == CustomEventNames.ManuallyEmitToolCall:
            yield ToolCallStartEvent(
                type=EventType.TOOL_CALL_START,
                tool_call_id=event["data"]["id"],
                tool_call_name=event["data"]["name"],
                parent_message_id=event["data"]["id"],
                raw_event=event,
            )
            yield ToolCallArgsEvent(
                type=EventType.TOOL_CALL_ARGS,
                tool_call_id=event["data"]["id"],
                delta=event["data"]["args"]
                if isinstance(event["data"]["args"], str)
                else json.dumps(event["data"]["args"]),
                raw_event=event,
            )
            yield ToolCallEndEvent(
                type=EventType.TOOL_CALL_END,
                tool_call_id=event["data"]["id"],
                raw_event=event,
            )

        elif event["name"] == CustomEventNames.ManuallyEmitState:
            self.active_run["manually_emitted_state"] = event["data"]
            yield StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot=self.get_state_snapshot(self.active_run["manually_emitted_state"]),
                raw_event=event,
            )

        yield CustomEvent(
            type=EventType.CUSTOM,
            name=event["name"],
            value=event["data"],
            raw_event=event,
        )

    async def _handle_on_tool_end_event(self, event: Any) -> AsyncGenerator[BaseEvent, None]:
        tool_call_output = event["data"]["output"]

        if isinstance(tool_call_output, Command):
            # Extract ToolMessages from Command.update
            messages = tool_call_output.update.get("messages", [])
            tool_messages = [m for m in messages if isinstance(m, ToolMessage)]

            # Process each tool message
            for tool_msg in tool_messages:
                if not self.active_run["has_function_streaming"]:
                    yield ToolCallStartEvent(
                        type=EventType.TOOL_CALL_START,
                        tool_call_id=tool_msg.tool_call_id,
                        tool_call_name=tool_msg.name,
                        parent_message_id=tool_msg.id,
                        raw_event=event,
                    )
                    yield ToolCallArgsEvent(
                        type=EventType.TOOL_CALL_ARGS,
                        tool_call_id=tool_msg.tool_call_id,
                        delta=json.dumps(event["data"].get("input", {})),
                        raw_event=event,
                    )
                    yield ToolCallEndEvent(
                        type=EventType.TOOL_CALL_END,
                        tool_call_id=tool_msg.tool_call_id,
                        raw_event=event,
                    )

            return

        if not self.active_run["has_function_streaming"]:
            yield ToolCallStartEvent(
                type=EventType.TOOL_CALL_START,
                tool_call_id=tool_call_output.tool_call_id,
                tool_call_name=tool_call_output.name,
                parent_message_id=tool_call_output.id,
                raw_event=event,
            )
            yield ToolCallArgsEvent(
                type=EventType.TOOL_CALL_ARGS,
                tool_call_id=tool_call_output.tool_call_id,
                delta=dump_json_safe(event["data"]["input"]),
                raw_event=event,
            )
            yield ToolCallEndEvent(
                type=EventType.TOOL_CALL_END,
                tool_call_id=tool_call_output.tool_call_id,
                raw_event=event,
            )

    def handle_thinking_event(self, reasoning_data: LangGraphReasoning) -> Generator[str, Any, str | None]:
        if not reasoning_data or "type" not in reasoning_data or "text" not in reasoning_data:
            return ""

        thinking_step_index = reasoning_data.get("index")

        if should_switch_thinking_step(self.active_run.get("thinking_process"), reasoning_data):
            if self.active_run["thinking_process"].get("type"):
                yield ThinkingTextMessageEndEvent(
                    type=EventType.THINKING_TEXT_MESSAGE_END,
                )
            yield ThinkingEndEvent(
                type=EventType.THINKING_END,
            )
            self.active_run["thinking_process"] = None

        if not self.active_run.get("thinking_process"):
            yield ThinkingStartEvent(
                type=EventType.THINKING_START,
            )
            self.active_run["thinking_process"] = {"index": thinking_step_index}

        if self.active_run["thinking_process"].get("type") != reasoning_data["type"]:
            yield ThinkingTextMessageStartEvent(
                type=EventType.THINKING_TEXT_MESSAGE_START,
            )
            self.active_run["thinking_process"]["type"] = reasoning_data["type"]

        if self.active_run["thinking_process"].get("type"):
            yield ThinkingTextMessageContentEvent(
                type=EventType.THINKING_TEXT_MESSAGE_CONTENT,
                delta=reasoning_data["text"],
            )

    def handle_node_change(self, node_name: str | None):
        """
        Centralized method to handle node name changes and step transitions.
        Automatically manages step start/end events based on node name changes.
        """
        if node_name == "__end__":
            node_name = None

        if node_name != self.active_run.get("node_name"):
            # End current step if we have one
            if self.active_run.get("node_name"):
                yield self.end_step()

            # Start new step if we have a node name
            if node_name:
                yield from self.start_step(node_name)

        self.active_run["node_name"] = node_name

    def start_step(self, step_name: str):
        """Simple step start event dispatcher - node_name management handled by handle_node_change"""
        yield self._dispatch_event(StepStartedEvent(type=EventType.STEP_STARTED, step_name=step_name))

    def end_step(self):
        """Simple step end event dispatcher - node_name management handled by handle_node_change"""
        if not self.active_run.get("node_name"):
            raise ValueError("No active step to end")

        return self._dispatch_event(
            StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=self.active_run["node_name"])
        )

    # Check if some kwargs are enabled per LG version, to "catch all versions" and backwards compatibility
    def get_stream_kwargs(
        self,
        input: Any,
        subgraphs: bool = False,
        version: Literal["v1", "v2"] = "v2",
        config: RunnableConfig | None = None,
        context: dict[str, Any] | None = None,
    ):
        kwargs = {
            "input": input,
            "subgraphs": subgraphs,
            "version": version,
        }

        # Only add context if supported
        sig = inspect.signature(self.graph.astream_events)
        if "context" in sig.parameters:
            base_context = {}
            if isinstance(config, dict) and "configurable" in config and isinstance(config["configurable"], dict):
                base_context.update(config["configurable"])
            if context:  # context might be None or {}
                base_context.update(context)
            if base_context:  # only add if there's something to pass
                kwargs["context"] = base_context

        if config:
            kwargs["config"] = config

        return kwargs


def dump_json_safe(value):
    return json.dumps(value, default=json_safe_stringify) if not isinstance(value, str) else value


State = dict[str, Any]
SchemaKeys = dict[str, list[str]]
TextMessageEvents = TextMessageStartEvent | TextMessageContentEvent | TextMessageEndEvent
ToolCallEvents = ToolCallStartEvent | ToolCallArgsEvent | ToolCallEndEvent


class LangGraphAGUIAgent(LangGraphAgent):
    def __init__(
        self,
        *,
        name: str,
        graph: CompiledStateGraph,
        description: str | None = None,
        config: RunnableConfig | None | dict = None,
        cancel_checker: Callable[[], bool] | None = None,
    ):
        super().__init__(name=name, graph=graph, description=description, config=config, cancel_checker=cancel_checker)
        self.constant_schema_keys = self.constant_schema_keys + ["copilotkit"]

    def _dispatch_event(self, event) -> str:
        """Override the dispatch event method to handle custom CopilotKit events and filtering

        Note: ManuallyEmitMessage/ManuallyEmitToolCall/ManuallyEmitState 事件的处理
        已在父类 _handle_single_event 中完成，此处仅处理 CopilotKit 特有的 copilotkit_exit
        和基于 metadata 的过滤逻辑。
        """
        if event.type == EventType.CUSTOM:
            custom_event = event
            # 仅处理 CopilotKit 特有的 exit 事件
            if custom_event.name == "copilotkit_exit":
                return super()._dispatch_event(
                    CustomEvent(
                        type=EventType.CUSTOM,
                        name="Exit",
                        value=True,
                        raw_event=event,
                    )
                )

        # Handle filtering based on metadata for text messages and tool calls
        raw_event = getattr(event, "raw_event", None)
        if raw_event:
            is_message_event = event.type in [
                EventType.TEXT_MESSAGE_START,
                EventType.TEXT_MESSAGE_CONTENT,
                EventType.TEXT_MESSAGE_END,
            ]
            is_tool_event = event.type in [
                EventType.TOOL_CALL_START,
                EventType.TOOL_CALL_ARGS,
                EventType.TOOL_CALL_END,
            ]

            metadata = getattr(raw_event, "metadata", {}) or {}

            if (
                "copilotkit:emit-tool-calls" in metadata
                and metadata["copilotkit:emit-tool-calls"] is False
                and is_tool_event
            ):
                return ""  # Don't dispatch this event

            if (
                "copilotkit:emit-messages" in metadata
                and metadata["copilotkit:emit-messages"] is False
                and is_message_event
            ):
                return ""  # Don't dispatch this event

        return super()._dispatch_event(event)

    async def _handle_single_event(self, event: Any, state: State) -> AsyncGenerator[BaseEvent, None]:
        """Override to add custom event processing for PredictState events"""

        # First, check if this is a raw event that should generate a PredictState event
        if event.get("event") == LangGraphEventTypes.OnChatModelStream.value:
            predict_state_metadata = event.get("metadata", {}).get("copilotkit:emit-intermediate-state", [])
            event["metadata"]["predict_state"] = predict_state_metadata

        # Call the parent method to handle all other events
        async for event_str in super()._handle_single_event(event, state):
            yield event_str
