import inspect
import json
import uuid
from collections.abc import AsyncGenerator, Generator
from logging import getLogger
from typing import Any, Callable, Literal

from ag_ui.core import (
    CustomEvent,
    EventType,
    RawEvent,
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
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig, ensure_config
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from .events import (
    ExtendThinkingEndEvent,
)
from .types import (
    CustomEventNames,
    LangGraphEventTypes,
    LangGraphReasoning,
    MessageInProgress,
    MessagesInProgressRecord,
    MessageSnapshotEventExtend,
    RunMetadata,
    SchemaKeys,
    State,
)
from .utils import (
    DEFAULT_SCHEMA_KEYS,
    agui_messages_to_langchain,
    camel_to_snake,
    filter_object_by_schema_keys,
    get_stream_payload_input,
    json_safe_stringify,
    langchain_messages_to_agui,
    make_json_safe,
    resolve_message_content,
    resolve_reasoning_content,
)
from aidev_agent.utils.event import RunId

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
    | RawEvent
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
        # 取消检测回调，返回 True 表示应该取消
        self._cancel_checker = cancel_checker

    def _dispatch_event(self, event: ProcessedEvents) -> str:
        if event.type == EventType.RAW:
            event.event = make_json_safe(event.event)
        elif event.raw_event:
            event.raw_event = make_json_safe(event.raw_event)

        return event

    async def run(self, input: RunAgentInput) -> AsyncGenerator[str, None]:
        forwarded_props = {}
        if hasattr(input, "forwarded_props") and input.forwarded_props:
            forwarded_props = {camel_to_snake(k): v for k, v in input.forwarded_props.items()}
        async for event_str in self._handle_stream_events(
            input.model_copy(update={"forwarded_props": forwarded_props})
        ):
            yield event_str

    async def _handle_stream_events(self, input: RunAgentInput) -> AsyncGenerator[str, None]:
        thread_id = input.thread_id or str(uuid.uuid4())
        INITIAL_ACTIVE_RUN = {
            "id": input.run_id,
            "thread_id": thread_id,
            "thinking_process": None,
            "node_name": None,
            "has_function_streaming": False,
            "has_text_output": False,  # 是否有 AI 文本输出（根据流式是否有TEXT_MESSAGE_START）
        }
        self.active_run = INITIAL_ACTIVE_RUN

        forwarded_props = input.forwarded_props
        node_name_input = forwarded_props.get("node_name", None) if forwarded_props else None

        self.active_run["manually_emitted_state"] = None

        config = ensure_config(self.config.copy() if self.config else {})
        config["configurable"] = {
            **(config.get("configurable", {})),
            "thread_id": thread_id,
        }

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

            yield self._dispatch_event(RawEvent(type=EventType.RAW, event=event))

            async for single_event in self._handle_single_event(event, state):
                yield single_event

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
                    )
                )
            self.active_run = INITIAL_ACTIVE_RUN
            return

        state = await self.graph.aget_state(config)

        tasks = state.tasks if len(state.tasks) > 0 else None
        interrupts = tasks[0].interrupts if tasks else []

        writes = state.metadata.get("writes", {}) or {}
        node_name = self.active_run["node_name"] if interrupts else next(iter(writes), None)
        next_nodes = state.next or ()
        is_end_node = len(next_nodes) == 0 and not interrupts

        node_name = "__end__" if is_end_node else node_name

        for interrupt in interrupts:
            yield self._dispatch_event(
                CustomEvent(
                    type=EventType.CUSTOM,
                    name=LangGraphEventTypes.OnInterrupt.value,
                    value=dump_json_safe(interrupt.value),
                    raw_event=interrupt,
                )
            )

        if self.active_run.get("node_name") != node_name:
            for ev in self.handle_node_change(node_name):
                yield ev

        state_values = state.values if state.values else state
        yield self._dispatch_event(
            StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot=self.get_state_snapshot(state_values),
            )
        )

        yield self._dispatch_event(
            MessageSnapshotEventExtend(
                type=EventType.MESSAGES_SNAPSHOT,
                messages=langchain_messages_to_agui(state_values.get("messages", [])),
            )
        )

        for ev in self.handle_node_change(None):
            yield ev

        yield self._dispatch_event(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=thread_id,
                run_id=self.active_run["id"],
            )
        )
        # Reset active run to how it was before the stream started
        self.active_run = INITIAL_ACTIVE_RUN

    async def prepare_stream(self, input: RunAgentInput, agent_state: State, config: RunnableConfig):
        state_input = input.state or {}
        messages = input.messages or []
        forwarded_props = input.forwarded_props or {}
        thread_id = input.thread_id

        # 不再依赖 checkpoint 中的 messages，直接使用后端数据库传来的完整历史
        state_input["messages"] = []
        self.active_run["current_graph_state"] = agent_state.values.copy()
        langchain_messages = agui_messages_to_langchain(messages)
        state = self.langgraph_default_merge_state(state_input, langchain_messages, input)
        self.active_run["current_graph_state"].update(state)
        config["configurable"]["thread_id"] = thread_id
        interrupts = agent_state.tasks[0].interrupts if agent_state.tasks and len(agent_state.tasks) > 0 else []
        has_active_interrupts = len(interrupts) > 0
        resume_input = forwarded_props.get("command", {}).get("resume", None)

        self.active_run["schema_keys"] = self.get_schema_keys(config)

        non_system_messages = [msg for msg in langchain_messages if not isinstance(msg, SystemMessage)]
        if len(agent_state.values.get("messages", [])) > len(non_system_messages):
            # Find the last user message by working backwards from the last message
            last_user_message = None
            for i in range(len(langchain_messages) - 1, -1, -1):
                if isinstance(langchain_messages[i], HumanMessage):
                    last_user_message = langchain_messages[i]
                    break

            if last_user_message:
                return await self.prepare_regenerate_stream(
                    input=input, message_checkpoint=last_user_message, config=config
                )

        events_to_dispatch = []
        if has_active_interrupts and not resume_input:
            events_to_dispatch.append(
                RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id=thread_id,
                    run_id=self.active_run["id"],
                )
            )

            for interrupt in interrupts:
                events_to_dispatch.append(
                    CustomEvent(
                        type=EventType.CUSTOM,
                        name=LangGraphEventTypes.OnInterrupt.value,
                        value=dump_json_safe(interrupt.value),
                        raw_event=interrupt,
                    )
                )

            events_to_dispatch.append(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=thread_id,
                    run_id=self.active_run["id"],
                )
            )
            return {
                "stream": None,
                "state": None,
                "config": None,
                "events_to_dispatch": events_to_dispatch,
            }

        if self.active_run["mode"] == "continue":
            await self.graph.aupdate_state(config, state, as_node=self.active_run.get("node_name"))

        if resume_input:
            stream_input = Command(resume=resume_input)
        else:
            payload_input = get_stream_payload_input(
                mode=self.active_run["mode"],
                state=state,
                schema_keys=self.active_run["schema_keys"],
            )
            stream_input = {**forwarded_props, **payload_input} if payload_input else None

        subgraphs_stream_enabled = input.forwarded_props.get("stream_subgraphs") if input.forwarded_props else False

        # 传完整的消息历史给 LangGraph
        stream_messages = stream_input["messages"] if stream_input else []
        kwargs = self.get_stream_kwargs(
            input={"messages": stream_messages},
            config=config,
            subgraphs=bool(subgraphs_stream_enabled),
            version="v2",
        )

        stream_input_final = kwargs.pop("input")
        stream = self.graph.astream_events(stream_input_final, **kwargs)

        return {"stream": stream, "state": state, "config": config}

    async def prepare_regenerate_stream(  # pylint: disable=too-many-arguments
        self,
        input: RunAgentInput,
        message_checkpoint: HumanMessage,
        config: RunnableConfig,
    ):
        thread_id = input.thread_id

        time_travel_checkpoint = await self.get_checkpoint_before_message(message_checkpoint.id, thread_id)
        if time_travel_checkpoint is None:
            return None

        fork = await self.graph.aupdate_state(
            time_travel_checkpoint.config,
            time_travel_checkpoint.values,
            as_node=time_travel_checkpoint.next[0] if time_travel_checkpoint.next else "__start__",
        )

        stream_input = self.langgraph_default_merge_state(time_travel_checkpoint.values, [message_checkpoint], input)
        subgraphs_stream_enabled = input.forwarded_props.get("stream_subgraphs") if input.forwarded_props else False
        if resume := input.forwarded_props.get("command", {}).get("resume"):
            stream_input = Command(resume=resume)

        kwargs = self.get_stream_kwargs(
            input=stream_input,
            fork=fork,
            subgraphs=bool(subgraphs_stream_enabled),
            version="v2",
            config=config,
        )
        stream = self.graph.astream_events(**kwargs)

        return {
            "stream": stream,
            "state": time_travel_checkpoint.values,
            "config": config,
        }

    def get_message_in_progress(self, run_id: str) -> MessageInProgress | None:
        return self.messages_in_process.get(run_id)

    def set_message_in_progress(self, run_id: str, data: MessageInProgress):
        current_message_in_progress = self.messages_in_process.get(run_id, {}) or {}
        self.messages_in_process[run_id] = {
            **current_message_in_progress,
            **data,
        }

    def get_schema_keys(self, config) -> SchemaKeys:
        try:
            input_schema = self.graph.get_input_jsonschema(config)
            output_schema = self.graph.get_output_jsonschema(config)
            config_schema = (
                self.graph.get_context_jsonschema(config).get("definitions", {}).get("Config", {}).get("properties", {})
            )

            input_schema_keys = list(input_schema["properties"].keys()) if "properties" in input_schema else []
            output_schema_keys = list(output_schema["properties"].keys()) if "properties" in output_schema else []
            config_schema_keys = list(config_schema.keys()) if isinstance(config_schema, dict) else []
            context_schema_keys = []

            if hasattr(self.graph, "context_schema") and self.graph.context_schema is not None:
                context_schema = self.graph.context_schema().schema()
                context_schema_keys = (
                    list(context_schema["properties"].keys()) if "properties" in context_schema else []
                )

            return {
                "input": [*input_schema_keys, *self.constant_schema_keys],
                "output": [*output_schema_keys, *self.constant_schema_keys],
                "config": config_schema_keys,
                "context": context_schema_keys,
            }
        except Exception:
            return {
                "input": self.constant_schema_keys,
                "output": self.constant_schema_keys,
                "config": [],
                "context": [],
            }

    def langgraph_default_merge_state(self, state: State, messages: list[BaseMessage], input: RunAgentInput) -> State:
        # 直接使用传入的 messages（后端数据库的完整历史）
        merged_messages = messages
        tools = input.tools or []
        tools_as_dicts = []
        if tools:
            for tool in tools:
                if hasattr(tool, "model_dump"):
                    tools_as_dicts.append(tool.model_dump())
                elif hasattr(tool, "dict"):
                    tools_as_dicts.append(tool.dict())
                else:
                    tools_as_dicts.append(tool)

        all_tools = [*state.get("tools", []), *tools_as_dicts]

        # Remove duplicates based on tool name
        seen_names = set()
        unique_tools = []
        for tool in all_tools:
            tool_name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            if tool_name and tool_name not in seen_names:
                seen_names.add(tool_name)
                unique_tools.append(tool)
            elif not tool_name:
                # Keep tools without names (shouldn't happen, but just in case)
                unique_tools.append(tool)

        return {
            **state,
            "messages": merged_messages,
            "tools": unique_tools,
            "ag-ui": {"tools": unique_tools, "context": input.context or []},
        }

    def get_state_snapshot(self, state: State) -> State:
        schema_keys = self.active_run["schema_keys"]
        if schema_keys and schema_keys.get("output"):
            state = filter_object_by_schema_keys(state, [*DEFAULT_SCHEMA_KEYS, *schema_keys["output"]])
        return state

    async def _handle_single_event(
        self,
        event: Any,
        state: State,  # noqa: ARG002
    ) -> AsyncGenerator[str, None]:
        event_type = event.get("event")
        if event_type == LangGraphEventTypes.OnChatModelStream:
            should_emit_messages = event["metadata"].get("emit-messages", True)
            should_emit_tool_calls = event["metadata"].get("emit-tool-calls", True)

            if event["data"]["chunk"].response_metadata.get("finish_reason", None):
                return

            current_stream = self.get_message_in_progress(self.active_run["id"])
            has_current_stream = bool(current_stream and current_stream.get("id"))
            tool_call_data = (
                event["data"]["chunk"].tool_call_chunks[0] if event["data"]["chunk"].tool_call_chunks else None
            )
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
                has_current_stream
                and current_stream.get("tool_call_id")
                and tool_call_data
                and tool_call_data.get("args")
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

            if reasoning_data:
                for each in self.handle_thinking_event(reasoning_data):
                    yield each

            if reasoning_data is None and self.active_run.get("thinking_process", None) is not None:
                yield self._dispatch_event(
                    ThinkingTextMessageEndEvent(
                        type=EventType.THINKING_TEXT_MESSAGE_END,
                    )
                )
                yield self._dispatch_event(
                    ExtendThinkingEndEvent(
                        duration=event.get("data", {}).get("chunk").additional_kwargs.get("reasoning_time", 0),
                        type=EventType.THINKING_END,
                    )
                )
                self.active_run["thinking_process"] = None

            if tool_call_used_to_predict_state:
                yield self._dispatch_event(
                    CustomEvent(
                        type=EventType.CUSTOM,
                        name="PredictState",
                        value=predict_state_metadata,
                        raw_event=event,
                    )
                )

            if is_tool_call_end_event:
                yield self._dispatch_event(
                    ToolCallEndEvent(
                        type=EventType.TOOL_CALL_END,
                        tool_call_id=current_stream["tool_call_id"],
                        raw_event=event,
                    )
                )
                self.messages_in_process[self.active_run["id"]] = None
                return

            if is_message_end_event:
                yield self._dispatch_event(
                    TextMessageEndEvent(
                        type=EventType.TEXT_MESSAGE_END,
                        message_id=current_stream["id"],
                        raw_event=event,
                    )
                )
                self.messages_in_process[self.active_run["id"]] = None
                return

            if is_tool_call_start_event and should_emit_tool_calls:
                if has_current_stream and not current_stream.get("tool_call_id"):
                    yield self._dispatch_event(
                        TextMessageEndEvent(
                            type=EventType.TEXT_MESSAGE_END,
                            message_id=current_stream["id"],
                            raw_event=event,
                        )
                    )
                elif is_parallel_tool_switch:
                    # 并行工具调用切换：先结束上一个工具调用
                    yield self._dispatch_event(
                        ToolCallEndEvent(
                            type=EventType.TOOL_CALL_END,
                            tool_call_id=current_stream["tool_call_id"],
                            raw_event=event,
                        )
                    )
                yield self._dispatch_event(
                    ToolCallStartEvent(
                        type=EventType.TOOL_CALL_START,
                        tool_call_id=tool_call_data["id"],
                        tool_call_name=tool_call_data["name"],
                        parent_message_id=event["data"]["chunk"].id,
                        raw_event=event,
                    )
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
                    yield self._dispatch_event(
                        ToolCallArgsEvent(
                            type=EventType.TOOL_CALL_ARGS,
                            tool_call_id=current_stream["tool_call_id"],
                            delta=tool_call_data["args"],
                            raw_event=event,
                        )
                    )
                return

            if is_tool_call_args_event and should_emit_tool_calls:
                yield self._dispatch_event(
                    ToolCallArgsEvent(
                        type=EventType.TOOL_CALL_ARGS,
                        tool_call_id=current_stream["tool_call_id"],
                        delta=tool_call_data["args"],
                        raw_event=event,
                    )
                )
                return

            if is_message_content_event and should_emit_messages:
                if not bool(current_stream and current_stream.get("id")):
                    yield self._dispatch_event(
                        TextMessageStartEvent(
                            type=EventType.TEXT_MESSAGE_START,
                            role="assistant",
                            message_id=event["data"]["chunk"].id,
                            raw_event=event,
                        )
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

                yield self._dispatch_event(
                    TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=current_stream["id"],
                        delta=message_content,
                        raw_event=event,
                    )
                )
                return

        elif event_type == LangGraphEventTypes.OnChatModelEnd:
            if self.get_message_in_progress(self.active_run["id"]) and self.get_message_in_progress(
                self.active_run["id"]
            ).get("tool_call_id"):
                resolved = self._dispatch_event(
                    ToolCallEndEvent(
                        type=EventType.TOOL_CALL_END,
                        tool_call_id=self.get_message_in_progress(self.active_run["id"])["tool_call_id"],
                        raw_event=event,
                    )
                )
                if resolved:
                    self.messages_in_process[self.active_run["id"]] = None
                yield resolved
            elif self.get_message_in_progress(self.active_run["id"]) and self.get_message_in_progress(
                self.active_run["id"]
            ).get("id"):
                resolved = self._dispatch_event(
                    TextMessageEndEvent(
                        type=EventType.TEXT_MESSAGE_END,
                        message_id=self.get_message_in_progress(self.active_run["id"])["id"],
                        raw_event=event,
                    )
                )
                if resolved:
                    self.messages_in_process[self.active_run["id"]] = None
                yield resolved

        elif event_type == LangGraphEventTypes.OnCustomEvent:
            if event["name"] == CustomEventNames.ManuallyEmitMessage:
                yield self._dispatch_event(
                    TextMessageStartEvent(
                        type=EventType.TEXT_MESSAGE_START,
                        role="assistant",
                        message_id=event["data"]["message_id"],
                        raw_event=event,
                    )
                )
                # 标记已有 AI 文本输出
                self.active_run["has_text_output"] = True
                yield self._dispatch_event(
                    TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=event["data"]["message_id"],
                        delta=event["data"]["message"],
                        raw_event=event,
                    )
                )
                yield self._dispatch_event(
                    TextMessageEndEvent(
                        type=EventType.TEXT_MESSAGE_END,
                        message_id=event["data"]["message_id"],
                        raw_event=event,
                    )
                )

            elif event["name"] == CustomEventNames.ManuallyEmitToolCall:
                yield self._dispatch_event(
                    ToolCallStartEvent(
                        type=EventType.TOOL_CALL_START,
                        tool_call_id=event["data"]["id"],
                        tool_call_name=event["data"]["name"],
                        parent_message_id=event["data"]["id"],
                        raw_event=event,
                    )
                )
                yield self._dispatch_event(
                    ToolCallArgsEvent(
                        type=EventType.TOOL_CALL_ARGS,
                        tool_call_id=event["data"]["id"],
                        delta=event["data"]["args"]
                        if isinstance(event["data"]["args"], str)
                        else json.dumps(event["data"]["args"]),
                        raw_event=event,
                    )
                )
                yield self._dispatch_event(
                    ToolCallEndEvent(
                        type=EventType.TOOL_CALL_END,
                        tool_call_id=event["data"]["id"],
                        raw_event=event,
                    )
                )

            elif event["name"] == CustomEventNames.ManuallyEmitState:
                self.active_run["manually_emitted_state"] = event["data"]
                yield self._dispatch_event(
                    StateSnapshotEvent(
                        type=EventType.STATE_SNAPSHOT,
                        snapshot=self.get_state_snapshot(self.active_run["manually_emitted_state"]),
                        raw_event=event,
                    )
                )

            yield self._dispatch_event(
                CustomEvent(
                    type=EventType.CUSTOM,
                    name=event["name"],
                    value=event["data"],
                    raw_event=event,
                )
            )

        elif event_type == LangGraphEventTypes.OnToolEnd:
            tool_call_output = event["data"]["output"]

            if isinstance(tool_call_output, Command):
                # Extract ToolMessages from Command.update
                messages = tool_call_output.update.get("messages", [])
                tool_messages = [m for m in messages if isinstance(m, ToolMessage)]

                # Process each tool message
                for tool_msg in tool_messages:
                    if not self.active_run["has_function_streaming"]:
                        yield self._dispatch_event(
                            ToolCallStartEvent(
                                type=EventType.TOOL_CALL_START,
                                tool_call_id=tool_msg.tool_call_id,
                                tool_call_name=tool_msg.name,
                                parent_message_id=tool_msg.id,
                                raw_event=event,
                            )
                        )
                        yield self._dispatch_event(
                            ToolCallArgsEvent(
                                type=EventType.TOOL_CALL_ARGS,
                                tool_call_id=tool_msg.tool_call_id,
                                delta=json.dumps(event["data"].get("input", {})),
                                raw_event=event,
                            )
                        )
                        yield self._dispatch_event(
                            ToolCallEndEvent(
                                type=EventType.TOOL_CALL_END,
                                tool_call_id=tool_msg.tool_call_id,
                                raw_event=event,
                            )
                        )

                return

            if not self.active_run["has_function_streaming"]:
                yield self._dispatch_event(
                    ToolCallStartEvent(
                        type=EventType.TOOL_CALL_START,
                        tool_call_id=tool_call_output.tool_call_id,
                        tool_call_name=tool_call_output.name,
                        parent_message_id=tool_call_output.id,
                        raw_event=event,
                    )
                )
                yield self._dispatch_event(
                    ToolCallArgsEvent(
                        type=EventType.TOOL_CALL_ARGS,
                        tool_call_id=tool_call_output.tool_call_id,
                        delta=dump_json_safe(event["data"]["input"]),
                        raw_event=event,
                    )
                )
                yield self._dispatch_event(
                    ToolCallEndEvent(
                        type=EventType.TOOL_CALL_END,
                        tool_call_id=tool_call_output.tool_call_id,
                        raw_event=event,
                    )
                )

    def handle_thinking_event(self, reasoning_data: LangGraphReasoning) -> Generator[str, Any, str | None]:
        if not reasoning_data or "type" not in reasoning_data or "text" not in reasoning_data:
            return ""

        thinking_step_index = reasoning_data.get("index")

        if (
            self.active_run.get("thinking_process")
            and self.active_run["thinking_process"].get("index")
            and self.active_run["thinking_process"]["index"] != thinking_step_index
        ):
            if self.active_run["thinking_process"].get("type"):
                yield self._dispatch_event(
                    ThinkingTextMessageEndEvent(
                        type=EventType.THINKING_TEXT_MESSAGE_END,
                    )
                )
            yield self._dispatch_event(
                ThinkingEndEvent(
                    type=EventType.THINKING_END,
                )
            )
            self.active_run["thinking_process"] = None

        if not self.active_run.get("thinking_process"):
            yield self._dispatch_event(
                ThinkingStartEvent(
                    type=EventType.THINKING_START,
                )
            )
            self.active_run["thinking_process"] = {"index": thinking_step_index}

        if self.active_run["thinking_process"].get("type") != reasoning_data["type"]:
            yield self._dispatch_event(
                ThinkingTextMessageStartEvent(
                    type=EventType.THINKING_TEXT_MESSAGE_START,
                )
            )
            self.active_run["thinking_process"]["type"] = reasoning_data["type"]

        if self.active_run["thinking_process"].get("type"):
            yield self._dispatch_event(
                ThinkingTextMessageContentEvent(
                    type=EventType.THINKING_TEXT_MESSAGE_CONTENT,
                    delta=reasoning_data["text"],
                )
            )

    async def get_checkpoint_before_message(self, message_id: str, thread_id: str):
        if not thread_id:
            raise ValueError("Missing thread_id in config")

        history_list = []
        async for snapshot in self.graph.aget_state_history({"configurable": {"thread_id": thread_id}}):
            history_list.append(snapshot)

        history_list.reverse()
        for idx, snapshot in enumerate(history_list):
            messages = snapshot.values.get("messages", [])
            if any(getattr(m, "id", None) == message_id for m in messages):
                if idx == 0:
                    # No snapshot before this
                    # Return synthetic "empty before" version
                    empty_snapshot = snapshot
                    empty_snapshot.values["messages"] = []
                    return empty_snapshot

                snapshot_values_without_messages = snapshot.values.copy()
                del snapshot_values_without_messages["messages"]
                checkpoint = history_list[idx - 1]

                merged_values = {
                    **checkpoint.values,
                    **snapshot_values_without_messages,
                }
                checkpoint = checkpoint._replace(values=merged_values)

                return checkpoint

        raise ValueError("Message ID not found in history")

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
        fork: Any | None = None,
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

        if fork:
            kwargs.update(fork)

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

    async def _handle_single_event(self, event: Any, state: State) -> AsyncGenerator[str, None]:
        """Override to add custom event processing for PredictState events"""

        # First, check if this is a raw event that should generate a PredictState event
        if event.get("event") == LangGraphEventTypes.OnChatModelStream.value:
            predict_state_metadata = event.get("metadata", {}).get("copilotkit:emit-intermediate-state", [])
            event["metadata"]["predict_state"] = predict_state_metadata

        # Call the parent method to handle all other events
        async for event_str in super()._handle_single_event(event, state):
            yield event_str

    def langgraph_default_merge_state(self, state: State, messages: list[BaseMessage], input: Any) -> State:
        """Override to add CopilotKit actions to the state"""
        merged_state = super().langgraph_default_merge_state(state, messages, input)
        # Extract tools from the merged state and add them as CopilotKit actions
        agui_properties = merged_state.get("ag-ui", {}) or merged_state

        return {
            **merged_state,
            "copilotkit": {
                "actions": agui_properties.get("tools", []),
                "context": agui_properties.get("context", []),
            },
        }


# Default checkpointer (can be overridden)
default_checkpointer = MemorySaver()
