"""Finalization keeps visible evidence and the remote replacement contract."""

import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock

import pytest
from ag_ui.core import CustomEvent, EventType, RawEvent
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.packages.langchain_core.output_parsers import StructuredOutputToToolMessageParser
from aidev_agent.services.agent.memory import completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.message_metadata import finalize_memory_source
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration

STAMP = "2026-10-20T00:00:00+00:00"
PUBLIC = "The user lives in Paris."
RAW = '<think>\nDiscarded Berlin hypothesis.\n</think>\n\n{"action":"Final Answer","action_input":"The user lives in Paris."}'


@pytest.fixture
def remote_ledger():
    client, rows = MagicMock(), []

    def create(*, json, headers):
        row = copy.deepcopy(json)
        row.update(id=len(rows) + 1, created_at=STAMP)
        row["property"].setdefault("artifacts", ["existing-file"])
        rows.append(row)
        return {"data": copy.deepcopy(row)}

    def update(*, path_params, json, headers, timeout=None):
        row = next(row for row in rows if row["id"] == path_params["id"])
        row.update(copy.deepcopy(json))  # The API replaces property; it never merges it.
        return {"data": copy.deepcopy(row)}

    client.api.create_chat_session_content.side_effect = create
    client.api.update_chat_session_content.side_effect = update
    writer = AGUISessionWriter("session", client, username="alice", turn_id="turn")
    writer.trace_id = "entry-trace"
    return writer, rows, client


def answer_and_finalization():
    raw = AIMessage(
        id="answer",
        content=RAW,
        response_metadata={
            "source_timestamp": STAMP,
            "memory_source_pending": True,
            "memory_source_complete": False,
        },
    )
    parser = StructuredOutputToToolMessageParser(
        llm=MockChatModel(responses=[], model_name="deepseek-r1"), keep_memory_source=True
    )
    answer = parser.parse_result([ChatGeneration(message=raw)])
    return raw, answer, finalize_memory_source(answer)


def finalize_event(payload, kind="custom"):
    name = SessionPersistenceEventNames.MemorySourceFinalized.value
    if kind == "raw":
        return RawEvent(type=EventType.RAW, event={"event": "on_custom_event", "name": name, "data": payload})
    return CustomEvent(type=EventType.CUSTOM, name=name, value=payload)


def save_raw(writer, raw):
    writer.handle_model_end(
        CustomEvent(
            type=EventType.CUSTOM,
            name=SessionPersistenceEventNames.ChatModelEnd.value,
            value=build_model_end_payload(raw, {}),
        )
    )


def snapshot(rows):
    return [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows]


@pytest.mark.parametrize("kind", ["raw", "custom"])
@pytest.mark.parametrize("early", [False, True])
def test_visible_source_and_owned_property_survive_replacement(remote_ledger, kind, early):
    writer, rows, client = remote_ledger
    raw, answer, payload = answer_and_finalization()
    if early:
        writer(finalize_event(payload, kind))
    save_raw(writer, raw)
    writer(finalize_event(payload, kind))
    writer(finalize_event(payload, kind))
    prop = rows[0]["property"]
    assert {key: prop[key] for key in ("turn_id", "trace_id", "artifacts")} == {
        "turn_id": "turn",
        "trace_id": "entry-trace",
        "artifacts": ["existing-file"],
    }
    assert rows[0]["content"] == RAW and rows[0]["status"] == "complete"
    assert completed_history(snapshot(rows), "session") == [
        {
            "message_id": answer.id,
            "role": "assistant",
            "text": PUBLIC,
            "complete": True,
            "timestamp": STAMP,
        }
    ]
    assert client.api.update_chat_session_content.call_count == (0 if early else 1)


@pytest.mark.parametrize("text", [None, "", "  ", 17, [], {}])
def test_invalid_complete_source_cannot_promote_raw_evidence(remote_ledger, text):
    writer, rows, client = remote_ledger
    raw, _, payload = answer_and_finalization()
    save_raw(writer, raw)
    writer(finalize_event({**payload, "source_text": text}))
    assert completed_history(snapshot(rows), "session") == []
    client.api.update_chat_session_content.assert_not_called()
    assert writer._memory_source_completions == {}


@pytest.mark.parametrize("error", [ConnectionError("offline"), NotImplementedError("unsupported")])
def test_failed_finalization_remains_ineligible_until_successful_retry(remote_ledger, error):
    writer, rows, client = remote_ledger
    raw, _, payload = answer_and_finalization()
    save_raw(writer, raw)
    update = client.api.update_chat_session_content.side_effect
    client.api.update_chat_session_content.side_effect = error
    writer(finalize_event(payload))
    assert completed_history(snapshot(rows), "session") == []
    assert writer._assistant_message_properties["answer"]["builtin_property"]["memory_source_complete"] is False
    client.api.update_chat_session_content.side_effect = update
    writer(finalize_event(payload))
    assert completed_history(snapshot(rows), "session")[0]["text"] == PUBLIC
    assert client.api.update_chat_session_content.call_count == 2


def test_failed_creation_never_looks_persisted_after_early_finalization(remote_ledger):
    writer, rows, client = remote_ledger
    raw, _, payload = answer_and_finalization()
    client.api.create_chat_session_content.side_effect = ConnectionError("offline")
    writer(finalize_event(payload))
    save_raw(writer, raw)
    writer(finalize_event(payload))
    assert rows == [] and writer._content_ids_by_message_id == {}
    assert writer._assistant_message_properties == {}
    client.api.update_chat_session_content.assert_not_called()


@pytest.mark.parametrize("late_complete", [False, True])
def test_duplicate_or_conflicting_finalizations_keep_first_canonical_source(remote_ledger, late_complete):
    writer, rows, client = remote_ledger
    raw, _, payload = answer_and_finalization()
    save_raw(writer, raw)
    writer(finalize_event(payload))
    writer(
        finalize_event(
            {
                **payload,
                "memory_source_complete": late_complete,
                "source_text": "Wrong draft",
                "source_timestamp": "2026-10-23T00:00:00Z",
            }
        )
    )
    assert completed_history(snapshot(rows), "session")[0]["text"] == PUBLIC
    assert completed_history(snapshot(rows), "session")[0]["timestamp"] == STAMP
    client.api.update_chat_session_content.assert_called_once()


@pytest.mark.parametrize("early", [False, True])
def test_unrelated_writer_update_cannot_replace_finalized_source(remote_ledger, early):
    writer, rows, _ = remote_ledger
    raw, _, payload = answer_and_finalization()
    save_raw(writer, raw)
    stale = copy.deepcopy(rows[0]["property"])
    stale["artifacts"].append("new-file")
    if not early:
        writer(finalize_event(payload))
    writer._do_update_content(1, {"property": stale}, {})
    if early:
        writer(finalize_event(payload))
    assert rows[0]["property"]["artifacts"] == ["existing-file", "new-file"]
    assert completed_history(snapshot(rows), "session")[0]["text"] == PUBLIC


def test_finalization_and_deferred_tool_update_serialize_without_lost_properties(remote_ledger):
    writer, rows, client = remote_ledger
    raw, _, payload = answer_and_finalization()
    save_raw(writer, raw)
    entered, release = Event(), Event()
    update = client.api.update_chat_session_content.side_effect

    def blocked(**kwargs):
        entered.set()
        assert release.wait(2)
        return update(**kwargs)

    client.api.update_chat_session_content.side_effect = blocked
    call = {"id": "tool", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}
    writer._deferred_approval_tool_calls["answer"] = [call]
    with ThreadPoolExecutor(max_workers=2) as pool:
        final = pool.submit(writer, finalize_event(payload))
        assert entered.wait(2)
        deferred = pool.submit(writer._flush_deferred_tool_call, "tool", "lookup")
        release.set()
        final.result(timeout=2)
        deferred.result(timeout=2)
    prop = rows[0]["property"]
    assert prop["turn_id"] == "turn" and prop["artifacts"] == ["existing-file"]
    assert prop["builtin_property"]["source_text"] == PUBLIC
    assert prop["builtin_property"]["tool_calls"] == [call]
    assert completed_history(snapshot(rows), "session") == []  # Still a tool message.


@pytest.mark.parametrize("response", [{"data": {}}, {"data": []}])
def test_unidentified_creation_cannot_seed_property_cache(remote_ledger, response):
    writer, rows, client = remote_ledger
    raw, _, payload = answer_and_finalization()
    client.api.create_chat_session_content.side_effect = None
    client.api.create_chat_session_content.return_value = response
    save_raw(writer, raw)
    writer(finalize_event(payload))
    assert rows == [] and writer._assistant_message_properties == {}
    assert writer._content_ids_by_message_id == {}
    client.api.update_chat_session_content.assert_not_called()


@pytest.mark.parametrize(
    "reason,tools", [("length", []), ("content_filter", []), ("stop", [{"id": "t", "name": "lookup", "args": {}}])]
)
def test_ineligible_finalization_does_not_add_a_source_or_redundant_update(remote_ledger, reason, tools):
    writer, rows, client = remote_ledger
    raw = AIMessage(
        id="answer",
        content="Incomplete",
        tool_calls=tools,
        response_metadata={
            "source_timestamp": STAMP,
            "finish_reason": reason,
            "memory_source_pending": True,
            "memory_source_complete": False,
        },
    )
    payload = finalize_memory_source(raw)
    save_raw(writer, raw)
    writer(finalize_event(payload))
    assert payload == {"message_id": "answer", "memory_source_complete": False}
    assert completed_history(snapshot(rows), "session") == []
    client.api.update_chat_session_content.assert_not_called()


def test_creation_response_can_supply_inherited_turn_and_extra_property(remote_ledger):
    writer, rows, client = remote_ledger
    writer.turn_id = ""
    create = client.api.create_chat_session_content.side_effect

    def inherited(**kwargs):
        response = create(**kwargs)
        rows[0]["property"]["turn_id"] = "server-turn"
        rows[0]["property"]["docSchema"] = [[{"text": "Server metadata"}]]
        response["data"]["property"] = copy.deepcopy(rows[0]["property"])
        return response

    client.api.create_chat_session_content.side_effect = inherited
    raw, _, payload = answer_and_finalization()
    save_raw(writer, raw)
    writer(finalize_event(payload))
    assert rows[0]["property"]["turn_id"] == "server-turn"
    assert rows[0]["property"]["docSchema"] == [[{"text": "Server metadata"}]]
    assert completed_history(snapshot(rows), "session")[0]["text"] == PUBLIC


@pytest.mark.parametrize("patch", [{"property": {"artifacts": ["new-file"]}}, {"content": "Updated display"}])
def test_update_without_source_identity_preserves_canonical_evidence(remote_ledger, patch):
    writer, rows, _ = remote_ledger
    raw, _, payload = answer_and_finalization()
    save_raw(writer, raw)
    writer(finalize_event(payload))
    writer._do_update_content(1, patch, {})
    assert completed_history(snapshot(rows), "session")[0]["text"] == PUBLIC
    assert rows[0]["property"]["turn_id"] == "turn"
    assert rows[0]["content"] == patch.get("content", RAW)


def test_unbound_update_preserves_callers_explicit_property_contract(remote_ledger):
    writer, rows, client = remote_ledger
    raw, _, _ = answer_and_finalization()
    save_raw(writer, raw)
    resumed = AGUISessionWriter("session", client, username="alice")
    patch = {"property": {"artifacts": ["replacement"]}}
    resumed._do_update_content(1, patch, {})
    assert rows[0]["property"] == patch["property"]
    assert resumed._assistant_message_properties == {}
