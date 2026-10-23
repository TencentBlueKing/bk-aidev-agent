"""Canonical answer evidence excludes inline reasoning across persistence and replay."""

import asyncio
import copy
import json
from unittest.mock import MagicMock

import pytest
from ag_ui.core import CustomEvent, EventType
from aidev_agent.api.bk_aidev import Client
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.core.tools.memory import PersonalMemoryRuntime, is_complete_ai_message
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from requests import Response


def build_chain(text, structured, promote):
    model = MockChatModel(responses=[text], model_name="deepseek-r1")
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = [
        StructuredTool.from_function(lambda q: q, name="lookup", description="Lookup")
    ]
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(content="Where do I live?")
    ]
    chain = _build_model_chain(
        llm=model,
        context_assembly=assembly,
        max_retries=0,
        quality_gate=QualityGate(enable_judge_response=False),
        use_structured_response=structured,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=promote,
        track_memory_source=True,
    )
    ctx = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )
    return chain, ctx


async def capture(text, structured, promote):
    chain, ctx = build_chain(text, structured, promote)
    events = []
    answer = None
    async for event in chain.astream_events(ctx, version="v2"):
        if event["event"] == "on_chat_model_end":
            events.append(
                CustomEvent(
                    type=EventType.CUSTOM,
                    name=SessionPersistenceEventNames.ChatModelEnd.value,
                    value=build_model_end_payload(copy.deepcopy(event["data"]["output"]), {}),
                )
            )
        elif (
            event["event"] == "on_custom_event"
            and event["name"] == SessionPersistenceEventNames.MemorySourceFinalized.value
        ):
            events.append(CustomEvent(type=EventType.CUSTOM, name=event["name"], value=copy.deepcopy(event["data"])))
        elif event["event"] == "on_chain_end" and not event["parent_ids"]:
            answer = event["data"]["output"].response
    return events, answer


def persisted_events(events):
    client, rows = MagicMock(), []

    def create(*, json, headers):
        row = copy.deepcopy(json)
        row["id"] = len(rows) + 1
        rows.append(row)
        return {"data": copy.deepcopy(row)}

    def update(*, path_params, json, headers, timeout=None):
        rows[path_params["id"] - 1].update(copy.deepcopy(json))

    client.api.create_chat_session_content.side_effect = create
    client.api.update_chat_session_content.side_effect = update
    writer = AGUISessionWriter("s", client, username="alice")
    for event in events:
        writer(event)
    return rows


def source_manager():
    manager = MagicMock()
    manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent",
        "memory_epoch": 1,
        "enabled_at": None,
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    return manager


@pytest.mark.parametrize(
    "mode,tag",
    [(mode, tag) for mode in ("native", "native_with_promotion") for tag in ("think", "thinking", "reasoning", "THINK")]
    + [("structured", "think")],  # Existing structured parser's supported envelope.
)
def test_hidden_inline_reasoning_is_not_memory_evidence(mode, tag):
    public = "The user lives in Paris."
    thinking = f"<{tag}>\nUnconfirmed hypothesis: the user lives in Berlin.\n</{tag}>\n\n"
    text = thinking + ('{"action":"Final Answer","action_input":"' + public + '"}' if mode == "structured" else public)
    events, answer = asyncio.run(capture(text, mode == "structured", mode == "native_with_promotion"))
    rows, manager = persisted_events(events), source_manager()
    runtime = automatic_personal_memory(manager, "alice", "s", [], [], agent_code="agent")
    runtime.complete({"messages": [answer]}, {})
    sent = manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    restored = completed_history(
        [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows], "s"
    )
    assert restored == sent
    assert len(sent) == 1
    assert sent[0]["text"] == (public if mode == "structured" else "\n\n" + public)
    assert rows[0]["content"] == text  # The displayed response remains intact.
    ledger = [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows]
    runtime = automatic_personal_memory(manager, "alice", "s", ledger, [], agent_code="agent")
    runtime.complete({"messages": [AIMessage(id="next", content="Next answer")]}, {})
    replayed = manager.complete_memory_round.call_args.args[0]["context"]["messages"][0]
    assert replayed == sent[0]  # Text, identity and timestamp (hence fingerprint) remain stable.

    audit = MagicMock()
    audit.invoke.return_value = AIMessage(content='{"memory_ids":[]}')
    reference = PersonalMemoryRuntime(lambda _: {}, reference_model=audit)
    assert reference.referenced_ids(answer, [{"memory_id": "unused", "text": "The user lives in Berlin."}]) == []
    audited = json.loads(audit.invoke.call_args.args[0][-1].content)
    assert audited["answer"] == sent[0]["text"]


def test_optional_memory_finalization_has_a_transport_timeout(monkeypatch):
    events, answer = asyncio.run(capture("Completed answer", False, False))
    client = Client(endpoint="http://127.0.0.1:45678/")
    requests = []

    def transport(**kwargs):
        requests.append(kwargs)
        response = Response()
        response.status_code = 200
        response._content = b'{"result":true,"data":{"id":1}}'
        return response

    monkeypatch.setattr(client.session, "request", transport)
    writer = AGUISessionWriter("s", client, username="alice")
    for event in events:
        writer(event)
    assert writer._write_error_count == 0
    assert [request["method"] for request in requests] == ["POST", "PUT"]
    assert "memory_source_complete" in requests[-1]["json"]["property"]["builtin_property"]
    # This metadata-only request is new even when no memory runtime is configured.
    assert requests[-1]["timeout"] == 2


@pytest.mark.parametrize("source_override", [False, True])
@pytest.mark.parametrize("public", ["", "Public answer"])
def test_legacy_history_and_direct_answers_share_normalization(source_override, public):
    text = "<think>Discarded hypothesis</think>" + public
    builtin = {"message_id": "answer", "source_timestamp": "2026-10-22T00:00:00Z"}
    if source_override:
        builtin["source_text"] = text
    record = {"id": 1, "role": "assistant", "content": text, "builtin_property": builtin}
    history = completed_history([record], "s")
    assert [item["text"] for item in history] == ([public] if public else [])
    answer = AIMessage(content=text, response_metadata=builtin)
    assert is_complete_ai_message(answer) is bool(public)
    user = {"id": 2, "role": "user", "content": text}
    assert completed_history([user], "s")[0]["text"] == text
