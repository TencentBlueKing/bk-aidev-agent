"""Cross-round memory evidence must survive the session writer boundary."""

import copy
from unittest.mock import MagicMock

import pytest
from ag_ui.core import (
    CustomEvent,
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageStartEvent,
)
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.event import RunId
from langchain_core.messages import AIMessage


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

    monkeypatch.setattr(writer, "_do_create_content", persist)
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
        "memory_epoch": 1,
        "enabled_at": "2026-10-01T00:00:00Z",
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    return manager


def save_answer(writer, answer):
    writer.handle_model_end(
        CustomEvent(
            type=EventType.CUSTOM, name="aidev_session_chat_model_end", value=build_model_end_payload(answer, {})
        )
    )


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
    assert ("first-answer" in [message["message_id"] for message in messages]) is kept
    assert records[0]["status"] == "complete"
    assert records[0]["builtin_property"].get("finish_reason") == reason


@pytest.mark.parametrize("builtin_id", [None, "", "canonical"])
def test_history_identity_falls_back_only_when_canonical_identity_is_absent(builtin_id):
    history = [{"id": 7, "role": "assistant", "content": "Hello", "builtin_property": {"message_id": builtin_id}}]
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
    expected = None if kept else "error" if termination == "error" else "cancelled"
    assert records[0]["builtin_property"].get("finish_reason") == expected


def test_cancellation_after_model_end_does_not_mark_completed_answer_partial(persisted_chat):
    writer, records = persisted_chat
    partial_answer(writer)
    save_answer(writer, AIMessage(id="partial", content="Complete answer", response_metadata={"finish_reason": "stop"}))
    writer.handle_run_finished(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="s", run_id="cancelled"))
    assert len(records) == 1
    assert completed_history(records, "s")[0]["text"] == "Complete answer"
    assert records[0]["builtin_property"]["finish_reason"] == "stop"
