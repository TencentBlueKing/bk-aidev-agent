"""Cross-round memory evidence must survive the session writer boundary."""

import asyncio
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from unittest.mock import MagicMock

import pytest
from ag_ui.core import (
    CustomEvent,
    EventType,
    RawEvent,
    RunErrorEvent,
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageStartEvent,
)
from aidev_agent.core.ag_ui.agent import LangGraphAgent
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.core.nodes.model import convert_chat_history_to_messages
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.core.tools.memory import PersonalMemoryRuntime, is_complete_ai_message
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.packages.langchain_core.output_parsers import StructuredOutputToToolMessageParser
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.event import RunId
from aidev_agent.utils.message_metadata import finalize_memory_source, memory_finish_reason
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk
from langchain_core.tools import StructuredTool


@pytest.fixture
def persisted_chat(monkeypatch):
    records = []
    writer = AGUISessionWriter(session_code="session-1", client=MagicMock(), username="alice")

    def persist(*, payload, headers):
        record = copy.deepcopy(payload)
        record.update(id=len(records) + 1, created_at="2026-10-22T00:00:00Z")
        record["builtin_property"] = record["property"].get("builtin_property", {})
        records.append(record)
        return record["id"]

    def update(*, content_id, payload, headers):
        record = next(record for record in records if str(record["id"]) == str(content_id))
        record["property"] = copy.deepcopy(payload.get("property", {}))
        record["builtin_property"] = record["property"].get("builtin_property", {})

    monkeypatch.setattr(writer, "_do_create_content", persist)
    monkeypatch.setattr(writer, "_do_update_content", update)
    monkeypatch.setattr(
        ChatCompletionAgent, "_dispatch_custom", lambda self, event: writer.handle_user_input_saved(event)
    )
    return writer, records


@pytest.fixture
def memory_manager():
    manager = MagicMock()
    manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent-a",
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    return manager


def save_answer(writer, answer):
    # These test answers represent a host-accepted result. Persist raw output
    # first, then explicitly finalize it as the standard model chain does.
    answer.response_metadata.update(memory_source_pending=True, memory_source_complete=False)
    writer.handle_model_end(
        CustomEvent(
            type=EventType.CUSTOM, name="aidev_session_chat_model_end", value=build_model_end_payload(answer, {})
        )
    )
    writer.handle_memory_source_finalized(
        CustomEvent(
            type=EventType.CUSTOM,
            name=SessionPersistenceEventNames.MemorySourceFinalized.value,
            value=finalize_memory_source(answer),
        )
    )


def model_messages(history):
    return convert_chat_history_to_messages(
        history,
        model_context_options=None,
        model_name="",
        agent_info=None,
        generating_keyword=None,
        files=[],
        support_vision=False,
    )


@pytest.mark.parametrize("canonical_id", ["17", "canonical-user"])
@pytest.mark.parametrize(
    "stamp,after_cutoff", [(None, False), ("2026-10-01T00:00:00Z", False), ("2026-10-21T00:00:00Z", True)]
)
def test_resume_keeps_ledger_identity_and_time(memory_manager, canonical_id, stamp, after_cutoff):
    builtin = {"message_id": canonical_id, "created_at": "2026-10-22T00:00:00Z"}
    if stamp:
        builtin["source_timestamp"] = stamp
    history = [ChatPrompt(id="17", role="user", content="Original preference", builtin_property=builtin)]
    messages = model_messages(history)
    assert messages[-1].id == "17"  # Keep the existing model-message protocol.
    runtime = automatic_personal_memory(memory_manager, "alice", "s", history, messages, agent_code="agent-a")
    runtime.complete({"messages": messages + [AIMessage(id="answer", content="Continued")]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    original = {"message_id": canonical_id, "role": "user", "text": "Original preference", "complete": True}
    if stamp:
        original["timestamp"] = stamp.replace("Z", "+00:00")
    expected = [original]
    assert sent[:-1] == expected
    assert sent[-1]["message_id"] == "answer"


def test_new_input_after_resume_keeps_its_received_time(persisted_chat, memory_manager):
    writer, records = persisted_chat
    old = ChatPrompt(id="17", role="user", content="Old", builtin_property={"message_id": "old-canonical"})
    agent = ChatCompletionAgent(chat_history=[old], event_handler=writer)
    agent._prepare_pre_run_history(ExecuteKwargs(input="New preference"))
    current = agent.chat_history[-1]
    messages = model_messages(agent.chat_history)
    runtime = automatic_personal_memory(
        memory_manager, "alice", "s", agent.chat_history, messages, agent_code="agent-a"
    )
    runtime.complete({"messages": messages + [AIMessage(id="answer", content="Understood")]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [item["message_id"] for item in sent] == [current.id, "answer"]
    assert sent[0]["timestamp"] == current.created_at
    assert completed_history(records, "s")[0] == sent[0]


@pytest.mark.parametrize("source", ["response_metadata", "additional_kwargs", None])
def test_legacy_visible_input_never_invents_a_timestamp(memory_manager, source):
    stamp = "2026-10-21T00:00:00+00:00"
    metadata = {source: {"created_at": stamp}} if source else {}
    message = HumanMessage(id="legacy-user", content="Preference", **metadata)
    runtime = automatic_personal_memory(memory_manager, "alice", "s", [], [message], agent_code="agent-a")
    snapshot = runtime.context({})[1]["messages"]
    assert snapshot[0].get("timestamp") == (stamp if source else None)
    runtime.complete({"messages": [message, AIMessage(id="answer", content="Understood")]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    expected_ids = ["legacy-user", "answer"]
    assert [item["message_id"] for item in sent] == expected_ids


def test_reloaded_rounds_do_not_duplicate_historical_users(persisted_chat, memory_manager):
    writer, records = persisted_chat
    agent = ChatCompletionAgent(chat_history=[], event_handler=writer)
    agent._prepare_pre_run_history(ExecuteKwargs(input="Original preference"))
    original = completed_history(agent.chat_history, "s")[0]
    for index in range(3):
        messages = model_messages(agent.chat_history)
        runtime = automatic_personal_memory(
            memory_manager, "alice", "s", agent.chat_history, messages, agent_code="agent-a"
        )
        answer = AIMessage(id=f"answer-{index}", content=f"Answer {index}")
        runtime.complete({"messages": messages + [answer]}, {})
        sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
        assert [item for item in sent if item["role"] == "user"] == [original]
        assert len(sent) == 2
        save_answer(writer, answer)
        agent.chat_history = [ChatPrompt.model_validate(record) for record in records]

    runtime = automatic_personal_memory(
        memory_manager, "alice", "s", agent.chat_history, model_messages(agent.chat_history), agent_code="agent-a"
    )
    runtime.complete({"messages": [AIMessage(id="after-reopen", content="Answer")]}, {})
    assert memory_manager.complete_memory_round.call_count == 4


def test_current_user_identity_and_source_time_survive_persistence(persisted_chat):
    writer, records = persisted_chat
    agent = ChatCompletionAgent(chat_history=[], event_handler=writer)
    agent._prepare_pre_run_history(ExecuteKwargs(input="I prefer Python", turn_id="turn-1"))
    current = agent.chat_history[-1]
    first = completed_history(agent.chat_history, "session-1")
    reloaded = completed_history([ChatPrompt.model_validate(record) for record in records], "session-1")
    assert str(records[0]["id"]) != current.id
    assert reloaded == first
    assert reloaded[0]["message_id"] == current.id
    assert reloaded[0]["timestamp"] == current.created_at


@pytest.mark.parametrize(
    "reason,kept",
    [
        (None, True),
        ("stop", True),
        ("length", False),
        ("max_tokens", False),
        ("content_filter", False),
        ("incomplete", False),
        ("cancelled", False),
        ("stopped", False),
        ("error", False),
    ],
)
def test_completed_answer_gate_survives_persistence(persisted_chat, memory_manager, reason, kept):
    writer, records = persisted_chat
    answer = AIMessage(id="first-answer", content="First answer", response_metadata={"finish_reason": reason})
    save_answer(writer, answer)
    history = [ChatPrompt.model_validate(record) for record in records]
    runtime = automatic_personal_memory(memory_manager, "alice", "session-1", history, [], agent_code="agent-a")
    runtime.complete({"messages": [AIMessage(id="next-answer", content="Next answer")]}, {})
    messages = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [message["message_id"] for message in messages] == ["next-answer"]
    assert bool(runtime.tool_source_provider("assistant")) is kept
    assert records[0]["status"] == "complete"
    assert records[0]["builtin_property"].get("finish_reason") == reason


@pytest.mark.parametrize("builtin_id", [None, "", "canonical"])
def test_history_identity_falls_back_only_when_canonical_identity_is_absent(builtin_id):
    history = [
        {
            "id": 7,
            "role": "assistant",
            "content": "Hello",
            "timestamp": "2026-10-20T00:00:00Z",
            "builtin_property": {"message_id": builtin_id},
        }
    ]
    assert completed_history(history, "session-1")[0]["message_id"] == (builtin_id or "7")


def test_invalid_source_time_falls_back_to_persisted_time():
    history = [
        {
            "id": 7,
            "role": "user",
            "content": "Hello",
            "created_at": "2026-10-21T00:00:00Z",
            "builtin_property": {"source_timestamp": "invalid"},
        }
    ]
    assert completed_history(history, "session-1")[0]["timestamp"] == "2026-10-21T00:00:00+00:00"


def test_user_event_without_source_time_still_preserves_identity(persisted_chat):
    writer, records = persisted_chat
    writer.handle_user_input_saved(
        CustomEvent(
            type=EventType.CUSTOM, name="user_input_saved", value={"content": "Hello", "message_id": "canonical"}
        )
    )
    assert records[0]["builtin_property"] == {"message_id": "canonical"}


def partial_answer(writer):
    writer.handle_text_message_start(
        TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id="partial", role="assistant")
    )
    writer.handle_text_message_content(
        TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id="partial", delta="Partial fact")
    )


@pytest.mark.parametrize(
    "termination,kept",
    [("complete", True), ("cancelled", False), ("stopped", False), ("cancel_error", False), ("error", False)],
)
def test_partial_answer_termination_survives_next_round(persisted_chat, memory_manager, termination, kept):
    writer, records = persisted_chat
    kept = False  # Stream-only history has no verifiable source completion time.
    partial_answer(writer)
    if termination in {"error", "cancel_error"}:
        message = RunId.CANCELLED_MESSAGE if termination == "cancel_error" else "Failure"
        writer.handle_run_error(RunErrorEvent(type=EventType.RUN_ERROR, message=message))
    else:
        writer.handle_run_finished(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="s", run_id=termination))
    history = [ChatPrompt.model_validate(record) for record in records]
    runtime = automatic_personal_memory(memory_manager, "alice", "s", history, [], agent_code="agent-a")
    runtime.complete({"messages": [AIMessage(id="next-answer", content="Next answer")]}, {})
    messages = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert ("partial" in [message["message_id"] for message in messages]) is kept
    assert records[0]["status"] == "complete"  # Display semantics are preserved.
    assert "source_timestamp" not in records[0]["builtin_property"]
    expected = None if termination == "complete" else "error" if termination == "error" else "cancelled"
    assert records[0]["builtin_property"].get("finish_reason") == expected


def test_cancellation_after_model_end_does_not_mark_completed_answer_partial(persisted_chat):
    writer, records = persisted_chat
    partial_answer(writer)
    save_answer(writer, AIMessage(id="partial", content="Complete answer", response_metadata={"finish_reason": "stop"}))
    writer.handle_run_finished(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="s", run_id="cancelled"))
    assert len(records) == 1
    assert completed_history(records, "s")[0]["text"] == "Complete answer"
    assert records[0]["builtin_property"]["finish_reason"] == "stop"


class CompletionClock(datetime):
    current = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current


class TimestampedStreamingModel(MockChatModel):
    provider_time: str | None = None
    finish_reason: str = "stop"

    async def _astream(self, *args, **kwargs):
        async for chunk in super()._astream(*args, **kwargs):
            yield chunk
        metadata = {"finish_reason": self.finish_reason}
        if self.provider_time:
            metadata["created_at"] = self.provider_time
        yield ChatGenerationChunk(message=AIMessageChunk(content="", response_metadata=metadata))


def completion_chain(provider_time, *, model=None, config=None, structured=False, promote=False, tools=None):
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = tools or []
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(content="Remember Python")
    ]
    chain = _build_model_chain(
        llm=model or TimestampedStreamingModel(responses=["I prefer Python"], provider_time=provider_time),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=QualityGate(enable_judge_response=False),
        use_structured_response=structured,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=promote,
        track_memory_source=True,
    )
    ctx = ProcessorContext(
        state={"messages": []}, config=config or {}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )
    return chain, ctx


async def streamed_completion(provider_time, *, finalizations=None, **options):
    chain, ctx = completion_chain(provider_time, **options)
    model_output = final_output = None
    async for event in chain.astream_events(ctx, version="v2"):
        if event["event"] == "on_chat_model_end":
            model_output = event["data"]["output"].model_copy(deep=True)
        if (
            finalizations is not None
            and event["event"] == "on_custom_event"
            and event["name"] == SessionPersistenceEventNames.MemorySourceFinalized.value
        ):
            finalizations.append(copy.deepcopy(event["data"]))
        if event["event"] == "on_chain_end" and not event["parent_ids"]:
            final_output = event["data"]["output"].response.model_copy(deep=True)
    return model_output, final_output


def persist_model_event(writer, answer, event_kind):
    payload = build_model_end_payload(answer.model_copy(deep=True), {})
    if event_kind == "raw":
        event = RawEvent(type=EventType.RAW, event={"data": {"output": answer.model_copy(deep=True)}})
    else:
        event = CustomEvent(type=EventType.CUSTOM, name="aidev_session_chat_model_end", value=copy.deepcopy(payload))
    writer.handle_model_end(event)
    writer.handle_model_end(event.model_copy(deep=True))
    return payload


@pytest.mark.parametrize("event_kind", ["raw", "custom"])
@pytest.mark.parametrize("provider_time", [None, "2026-10-19T12:00:00Z"])
@pytest.mark.parametrize("writer_first", [False, True])
def test_streamed_completion_time_survives_copies_and_three_rounds(
    persisted_chat, memory_manager, monkeypatch, event_kind, provider_time, writer_first
):
    writer, records = persisted_chat
    monkeypatch.setattr("aidev_agent.utils.message_metadata.datetime", CompletionClock)
    finalizations = []
    event_answer, state_answer = asyncio.run(streamed_completion(provider_time, finalizations=finalizations))
    stamp = provider_time.replace("Z", "+00:00") if provider_time else CompletionClock.current.isoformat()
    assert (
        event_answer.response_metadata["source_timestamp"]
        == state_answer.response_metadata["source_timestamp"]
        == stamp
    )
    runtime = automatic_personal_memory(memory_manager, "alice", "s", [], [], agent_code="agent-a")
    if writer_first:
        persist_model_event(writer, event_answer, event_kind)
    runtime.complete({"messages": [state_answer]}, {})
    first = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"][0]
    if not writer_first:
        persist_model_event(writer, event_answer, event_kind)
    assert completed_history(records, "s") == []
    for source in finalizations:
        writer(
            CustomEvent(
                type=EventType.CUSTOM, name=SessionPersistenceEventNames.MemorySourceFinalized.value, value=source
            )
        )
    assert completed_history(records, "s") == [first]
    assert first["timestamp"] == stamp
    assert_three_reloaded_rounds(records, memory_manager, first)


def assert_three_reloaded_rounds(records, manager, original):
    for index in range(3):
        history = [ChatPrompt.model_validate(record) for record in copy.deepcopy(records)]
        runtime = automatic_personal_memory(
            manager, "alice", "s", history, model_messages(history), agent_code="agent-a"
        )
        runtime.complete({"messages": [AIMessage(id=f"next-{index}", content="Next answer")]}, {})
        sent = manager.complete_memory_round.call_args.args[0]["context"]["messages"]
        matching = [item for item in sent if item["message_id"] == original["message_id"]]
        assert matching == []
        selected = runtime.tool_source_provider("assistant")
        assert selected == [original]
        assert source_fingerprint(selected[0]) == source_fingerprint(original)
    manager.memory_schemas.return_value.update(version="1.0.0")
    runtime = automatic_personal_memory(manager, "alice", "s", history, model_messages(history), agent_code="agent-a")
    runtime.complete({"messages": [AIMessage(id="after-reopen", content="New answer")]}, {})
    sent = manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert original["message_id"] not in [item["message_id"] for item in sent]


@pytest.mark.parametrize("stamp", [None, "invalid"])
def test_legacy_assistant_database_write_time_is_not_completion_evidence(memory_manager, stamp):
    history = [{"id": 7, "role": "assistant", "content": "Old answer", "created_at": "2026-10-22T00:00:00Z"}]
    history[0]["builtin_property"] = {"source_timestamp": stamp}
    assert completed_history(history, "s") == []
    runtime = automatic_personal_memory(memory_manager, "alice", "s", history, [], agent_code="agent-a")
    runtime.complete({"messages": [AIMessage(id="new", content="New answer")]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [item["message_id"] for item in sent] == ["new"]


class CompletionSpy(BaseCallbackHandler):
    def __init__(self):
        self.outputs = []

    def on_llm_end(self, response, **kwargs):
        self.outputs.append(response)


class FailingStreamingModel(MockChatModel):
    async def _astream(self, *args, **kwargs):
        async for chunk in super()._astream(*args, **kwargs):
            raise ConnectionError("Use fallback")
            yield chunk


@pytest.mark.parametrize("invocation", ["sync", "async"])
def test_model_binding_and_request_callbacks_survive_completion_stamp(invocation):
    bound, requested = CompletionSpy(), CompletionSpy()
    model = TimestampedStreamingModel(responses=["Complete answer"]).with_config(callbacks=[bound])
    options = {"model": model, "config": {"callbacks": [requested]}}
    if invocation == "async":
        _, state_answer = asyncio.run(streamed_completion(None, **options))
    else:
        chain, ctx = completion_chain(None, **options)
        state_answer = chain.invoke(ctx).response
    event_answer = bound.outputs[0].generations[0][0].message
    assert len(bound.outputs) == len(requested.outputs) == 1
    assert model.config["callbacks"] == [bound]
    assert state_answer.content == "Complete answer"
    assert state_answer.response_metadata["source_timestamp"] == event_answer.response_metadata["source_timestamp"]


def test_model_fallback_keeps_original_completion_time():
    model = FailingStreamingModel(responses=["Fail"]).with_fallbacks(
        [TimestampedStreamingModel(responses=["Fallback answer"], provider_time="2026-10-20T00:00:00Z")]
    )
    event_answer, state_answer = asyncio.run(streamed_completion(None, model=model))
    assert state_answer.content == "Fallback answer"
    assert event_answer.response_metadata["source_timestamp"] == state_answer.response_metadata["source_timestamp"]
    assert state_answer.response_metadata["source_timestamp"] == "2026-10-20T00:00:00+00:00"


@pytest.mark.parametrize("structured,promote", [(True, False), (False, True)])
def test_model_transformations_keep_source_completion_metadata(structured, promote):
    action = "Final Answer" if structured else "lookup"
    answer = "I prefer Python" if structured else {"query": "Python"}
    text = json.dumps({"action": action, "action_input": answer}) if structured else '[lookup]\n{"query":"Python"}'
    model = TimestampedStreamingModel(
        responses=[text],
        provider_time="2026-10-20T00:00:00Z",
    )
    tool = StructuredTool.from_function(lambda query: query, name="lookup", description="Lookup")
    event_answer, state_answer = asyncio.run(
        streamed_completion(None, model=model, structured=structured, promote=promote, tools=[tool])
    )
    assert state_answer.id == event_answer.id
    assert state_answer.response_metadata["source_timestamp"] == event_answer.response_metadata["source_timestamp"]
    assert memory_finish_reason(state_answer.response_metadata) == "stop"
    assert ("finish_reason" in state_answer.response_metadata) is not structured
    assert bool(state_answer.tool_calls) is promote
    assert state_answer.content == ("I prefer Python" if structured else model.responses[0])


@pytest.mark.parametrize("reason,complete", [("stop", True), ("length", False), ("content_filter", False)])
def test_structured_final_answer_keeps_completion_gate(reason, complete):
    original = AIMessage(
        id="answer",
        content='{"action":"Final Answer","action_input":"Parsed answer"}',
        response_metadata={"source_timestamp": "2026-10-20T00:00:00+00:00", "finish_reason": reason},
    )
    parsed = StructuredOutputToToolMessageParser(keep_memory_source=True).parse_result(
        [ChatGeneration(message=original)]
    )
    assert parsed.id == original.id
    assert parsed.response_metadata == {
        "source_timestamp": original.response_metadata["source_timestamp"],
        "memory_source_finish_reason": reason,
    }
    assert parsed.content == "Parsed answer"
    assert is_complete_ai_message(parsed) is complete


def source_fingerprint(record):
    source = {key: record[key] for key in ("message_id", "role", "text", "timestamp")}
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


async def persist_standard_model_stream(
    writer, mode, finish_reason="stop", *, event_kind="custom", finalize_first=False, omit_final=False
):
    text = (
        '  {"action":"Final Answer","action_input":"I prefer Python"} \n'
        if mode == "structured"
        else "  I prefer Python \n"
    )
    if mode == "promotion":
        text = '[lookup]\n{"query":"Python"}'
    elif mode == "structured_tool":
        text = '{"action":"lookup","action_input":{"query":"Python"}}'
    model = TimestampedStreamingModel(
        responses=[text], provider_time="2026-10-20T00:00:00Z", finish_reason=finish_reason
    )
    if mode == "fallback":
        model = FailingStreamingModel(responses=["Fail"]).with_fallbacks([model])
    tool = StructuredTool.from_function(lambda query: query, name="lookup", description="Lookup")
    chain, ctx = completion_chain(
        None,
        model=model,
        structured=mode in {"structured", "structured_tool"},
        promote=mode == "promotion",
        tools=[tool],
    )
    agent = LangGraphAgent.__new__(LangGraphAgent)
    agent.front_end_display = True
    agent.messages_in_process = {"run-1": None}
    agent.active_run = {"id": "run-1", "thread_id": "s"}
    agent._tool_mapping = {}
    final = None
    pending = []
    async for event in chain.astream_events(ctx, version="v2"):
        if event["event"] == "on_chat_model_end" or (
            event["event"] == "on_custom_event"
            and event["name"] == SessionPersistenceEventNames.MemorySourceFinalized.value
        ):
            pending.append(copy.deepcopy(event))
        if event["event"] == "on_chain_end" and not event["parent_ids"]:
            final = event["data"]["output"].response.model_copy(deep=True)
    if finalize_first:
        pending.reverse()
    for event in pending:
        if omit_final and event["event"] == "on_custom_event":
            continue
        if event_kind == "raw":
            writer(RawEvent(type=EventType.RAW, event=event))
        else:
            async for custom in agent._handle_single_event(event, {}):
                writer(custom)
    return final


@pytest.mark.parametrize("mode", ["plain", "structured", "fallback"])
@pytest.mark.parametrize("event_kind", ["raw", "custom"])
@pytest.mark.parametrize("finalize_first", [False, True])
def test_standard_agui_source_id_text_time_and_fingerprint_survive_replay(
    persisted_chat, memory_manager, mode, event_kind, finalize_first
):
    writer, records = persisted_chat
    answer = asyncio.run(
        persist_standard_model_stream(writer, mode, event_kind=event_kind, finalize_first=finalize_first)
    )
    runtime = automatic_personal_memory(memory_manager, "alice", "s", [], [], agent_code="agent-a")
    runtime.complete({"messages": [answer]}, {})
    current = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"][0]
    assert current == completed_history(records, "s")[0]
    assert source_fingerprint(current) == source_fingerprint(completed_history(records, "s")[0])
    assert records[0]["content"] == (
        '{"action":"Final Answer","action_input":"I prefer Python"}'
        if mode == "structured"
        else current["text"].strip()
    )
    if mode == "structured":
        assert records[0]["builtin_property"]["source_text"] == answer.content
    assert answer.content == ("I prefer Python" if mode == "structured" else "  I prefer Python \n")
    assert_three_reloaded_rounds(records, memory_manager, current)


@pytest.mark.parametrize(
    "mode,reason",
    [("structured", "length"), ("structured", "content_filter"), ("promotion", "stop"), ("structured_tool", "stop")],
)
@pytest.mark.parametrize("event_kind", ["raw", "custom"])
@pytest.mark.parametrize("finalize_first", [False, True])
def test_transformed_incomplete_or_tool_response_never_submits_completion(
    persisted_chat, memory_manager, mode, reason, event_kind, finalize_first
):
    writer, records = persisted_chat
    answer = asyncio.run(
        persist_standard_model_stream(writer, mode, reason, event_kind=event_kind, finalize_first=finalize_first)
    )
    runtime = automatic_personal_memory(memory_manager, "alice", "s", [], [], agent_code="agent-a")
    runtime.complete({"messages": [answer]}, {})
    memory_manager.complete_memory_round.assert_not_called()
    assert (
        answer.tool_calls
        if mode in {"promotion", "structured_tool"}
        else memory_finish_reason(answer.response_metadata) == reason
    )
    for index in range(3):
        runtime = automatic_personal_memory(
            memory_manager, "alice", "s", copy.deepcopy(records), [], agent_code="agent-a"
        )
        runtime.complete({"messages": [AIMessage(id=f"next-{index}", content="Next answer")]}, {})
        sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
        assert answer.id not in [message["message_id"] for message in sent]
    assert records[0]["builtin_property"]["memory_source_complete"] is False


def test_source_text_preserves_user_evidence_and_guides_reference_audit(memory_manager):
    user = HumanMessage(
        id="user", content="  My preference  ", response_metadata={"created_at": "2026-10-20T00:00:00Z"}
    )
    answer = AIMessage(
        id="answer", content="Final rendered answer", response_metadata={"source_text": "  Original source  "}
    )
    tool = ToolMessage(content="hit", tool_call_id="call", artifact={"personal_memory_hits": [{"memory_id": "used"}]})
    runtime = automatic_personal_memory(memory_manager, "alice", "s", [], [user], agent_code="agent-a")
    runtime.reference_model = MagicMock()
    runtime.reference_model.invoke.return_value = AIMessage(content='{"memory_ids":["used"]}')
    runtime.complete({"messages": [user, tool, answer]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert sent[0]["text"] == user.content
    assert sent[1]["text"] == "  Original source  "
    audit = json.loads(runtime.reference_model.invoke.call_args.args[0][1].content)
    assert audit["answer"] == "  Original source  "


@pytest.mark.parametrize("failed_update", [False, True])
def test_missing_or_failed_finalization_keeps_history_ineligible(
    persisted_chat, memory_manager, monkeypatch, failed_update
):
    writer, records = persisted_chat
    if failed_update:
        monkeypatch.setattr(writer, "_do_update_content", MagicMock(side_effect=ConnectionError("Unavailable")))
    answer = asyncio.run(persist_standard_model_stream(writer, "structured", omit_final=not failed_update))
    assert answer.response_metadata["memory_source_complete"] is True
    assert records[0]["builtin_property"]["memory_source_complete"] is False
    for index in range(3):
        runtime = automatic_personal_memory(memory_manager, "alice", "s", records, [], agent_code="agent-a")
        runtime.complete({"messages": [AIMessage(id=f"next-{index}", content="Next answer")]}, {})
        sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
        assert answer.id not in [message["message_id"] for message in sent]


def test_old_assistant_without_verifiable_source_time_is_never_evidence(memory_manager):
    history = [
        {"id": 7, "role": "assistant", "content": '[lookup]\n{"query":"Python"}', "created_at": "2026-10-22T00:00:00Z"}
    ]
    for index in range(3):
        runtime = automatic_personal_memory(memory_manager, "alice", "s", history, [], agent_code="agent-a")
        runtime.complete({"messages": [AIMessage(id=f"next-{index}", content="Next answer")]}, {})
        sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
        assert "7" not in [message["message_id"] for message in sent]


def test_finalization_waits_for_inflight_creation_and_duplicate_events_are_idempotent(persisted_chat, monkeypatch):
    writer, records = persisted_chat
    entered, release = Event(), Event()
    original = writer._do_create_content

    def blocked_create(**kwargs):
        entered.set()
        assert release.wait(2)
        return original(**kwargs)

    monkeypatch.setattr(writer, "_do_create_content", blocked_create)
    update = MagicMock(wraps=writer._do_update_content)
    monkeypatch.setattr(writer, "_do_update_content", update)
    answer = AIMessage(id="answer", content="Complete", response_metadata={"memory_source_complete": False})
    final = CustomEvent(
        type=EventType.CUSTOM,
        name=SessionPersistenceEventNames.MemorySourceFinalized.value,
        value={"message_id": "answer", "memory_source_complete": True, "source_text": "Complete"},
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = pool.submit(save_answer, writer, answer)
        assert entered.wait(2)
        finalized = pool.submit(writer, final)
        release.set()
        created.result(timeout=2)
        finalized.result(timeout=2)
    writer(final.model_copy(deep=True))
    assert len(records) == 1
    assert records[0]["builtin_property"]["memory_source_complete"] is True
    assert update.call_count == 1


def test_undated_assistant_input_is_not_promoted_to_new_evidence(memory_manager):
    runtime = automatic_personal_memory(
        memory_manager, "alice", "session-1", [], [AIMessage(id="old", content="Old preference")], agent_code="agent-a"
    )
    assert runtime.context({})[1]["messages"] == []
    answer = AIMessage(id="new", content="New answer", response_metadata={"timestamp": "2026-10-21T00:00:00Z"})
    runtime.complete({"messages": [answer]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [message["message_id"] for message in sent] == ["new"]


def test_custom_runtime_only_submits_final_answer_from_state_history(memory_manager):
    context = {
        "username": "alice",
        "agent_code": "agent-a",
        "session_id": "session-1",
        "session_date": "2026-10-21",
        "messages": [],
    }
    runtime = PersonalMemoryRuntime(
        lambda _: context, manager=memory_manager, schemas=memory_manager.memory_schemas.return_value
    )
    old = AIMessage(id="old", content="Earlier answer", response_metadata={"timestamp": "2026-10-20T00:00:00Z"})
    answer = AIMessage(id="new", content="Current answer", response_metadata={"timestamp": "2026-10-21T00:00:00Z"})
    runtime.complete({"messages": [old, answer]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert {message["message_id"]: message["timestamp"] for message in sent} == {
        "new": "2026-10-21T00:00:00+00:00",
    }
    assert answer.response_metadata["source_timestamp"] == "2026-10-21T00:00:00+00:00"


@pytest.mark.parametrize(
    "structured,text", [(True, "I prefer Python"), (False, "  I prefer Python  "), (False, "I prefer Python")]
)
def test_no_ledger_replay_retains_original_source_across_rounds(memory_manager, structured, text):
    content = json.dumps({"action": "Final Answer", "action_input": text}) if structured else text
    source = AIMessage(id="answer-1", content=content, response_metadata={"source_timestamp": "2026-10-20T00:00:00Z"})
    answer = (
        StructuredOutputToToolMessageParser(keep_memory_source=True).parse_result([ChatGeneration(message=source)])
        if structured
        else source
    )
    runtime = automatic_personal_memory(memory_manager, "alice", "session-1", [], [], agent_code="agent-a")
    runtime.complete({"messages": [answer]}, {})
    original = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"][0]
    assert original["text"] == (text if structured else content)
    for round_index in [2, 3]:
        restored = automatic_personal_memory(memory_manager, "alice", "session-1", [], [answer], agent_code="agent-a")
        current = AIMessage(
            id=f"answer-{round_index}",
            content="Next answer",
            response_metadata={"source_timestamp": "2026-10-21T00:00:00Z"},
        )
        restored.complete({"messages": [current]}, {})
        replayed = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"][0]
        assert replayed["message_id"] == current.id
        assert replayed["message_id"] != original["message_id"]
        assert restored.tool_source_provider("assistant") == [original]
