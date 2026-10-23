"""Observable contracts for the remaining personal-memory integration branches."""

import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from ag_ui.core import (
    CustomEvent,
    EventType,
    RawEvent,
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageStartEvent,
)
from aidev_agent.core.ag_ui.agent import LangGraphAGUIAgent
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import CustomMessageType, SessionPersistenceEventNames
from aidev_agent.enums import AgentType
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from aidev_agent.services.agent.registry import AgentBuildContext
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.message_metadata import AssistantCompletionTimestamp
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

STAMP = "2026-10-21T00:00:00+00:00"


@pytest.fixture
def review_manager():
    manager = MagicMock(username="alice")
    manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "child-agent",
        "memory_epoch": 1,
        "enabled_at": None,
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    return manager


@pytest.fixture
def review_ledger(monkeypatch):
    writer = AGUISessionWriter(session_code="session-1", client=MagicMock(), username="alice")
    records = []

    def create(*, payload, headers):
        record = copy.deepcopy(payload)
        record.update(id=len(records) + 1, created_at=STAMP)
        record["builtin_property"] = record["property"].get("builtin_property", {})
        records.append(record)
        return record["id"]

    def update(*, content_id, payload, headers):
        record = next(record for record in records if str(record["id"]) == str(content_id))
        record["property"] = copy.deepcopy(payload["property"])
        record["builtin_property"] = record["property"]["builtin_property"]

    monkeypatch.setattr(writer, "_do_create_content", MagicMock(side_effect=create))
    monkeypatch.setattr(writer, "_do_update_content", MagicMock(side_effect=update))
    return writer, records


def pending_answer_event():
    answer = AIMessage(
        id="answer-1",
        content="Original answer",
        response_metadata={"source_timestamp": STAMP, "memory_source_complete": False},
    )
    return CustomEvent(
        type=EventType.CUSTOM,
        name=SessionPersistenceEventNames.ChatModelEnd.value,
        value=build_model_end_payload(answer, {}),
    )


def finalization_event(payload, kind):
    name = SessionPersistenceEventNames.MemorySourceFinalized.value
    if kind == "raw":
        return RawEvent(type=EventType.RAW, event={"event": "on_custom_event", "name": name, "data": payload})
    return CustomEvent(type=EventType.CUSTOM, name=name, value=payload)


@pytest.mark.parametrize("agent_code", [None, "", " \t", 17, True, [], {}])
def test_invalid_discovery_agent_never_constructs_authenticated_client(agent_code, monkeypatch):
    manager = BaseResourceManager(app_code="app", app_secret="test-secret")
    client = MagicMock()
    monkeypatch.setattr(manager, "_memory_client", client)
    with pytest.raises(ValueError, match="agent code"):
        manager.memory_schemas(username="alice", agent_code=agent_code)
    client.assert_not_called()


@pytest.mark.parametrize("kind", ["raw", "custom"])
@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "invalid",
        {},
        {"memory_source_complete": True},
        {"message_id": "answer-1"},
        {"message_id": "", "memory_source_complete": True},
        {"message_id": "answer-1", "memory_source_complete": 1},
        {"message_id": "answer-1", "memory_source_complete": "true"},
    ],
)
def test_malformed_finalization_cannot_promote_persisted_evidence(review_ledger, review_manager, kind, payload):
    writer, records = review_ledger
    writer(pending_answer_event())
    before = copy.deepcopy(records)
    writer(finalization_event(payload, kind))
    assert records == before
    assert writer._memory_source_completions == {}
    writer._do_update_content.assert_not_called()
    assert completed_history(records, "session-1") == []
    for index in range(2):
        runtime = automatic_personal_memory(review_manager, "alice", "session-1", records, [], agent_code="child-agent")
        runtime.complete({"messages": [AIMessage(id=f"next-{index}", content="Next answer")]}, {})
        sent = review_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
        assert [message["message_id"] for message in sent] == [f"next-{index}"]


def test_raw_finalization_dispatch_updates_only_source_eligibility_and_is_idempotent(review_ledger):
    writer, records = review_ledger
    writer(pending_answer_event())
    before = copy.deepcopy(records[0])
    event = finalization_event(
        {"message_id": "answer-1", "memory_source_complete": True, "source_text": "Original answer"}, "raw"
    )
    writer(event)
    writer(event)
    writer._do_update_content.assert_called_once()
    assert records[0]["content"] == before["content"]
    assert records[0]["status"] == before["status"]
    assert records[0]["content"] == "Original answer"
    assert records[0]["builtin_property"] == {**before["builtin_property"], "memory_source_complete": True}
    assert completed_history(records, "session-1") == [
        {"message_id": "answer-1", "role": "assistant", "text": "Original answer", "complete": True, "timestamp": STAMP}
    ]


@pytest.mark.parametrize(
    "name,handler",
    [
        (CustomMessageType.KNOWLEDGE_RAG_RESULT.value, "handle_reference_document"),
        (CustomMessageType.FLOW_AGENT_START.value, "handle_flow_agent_start"),
    ],
)
def test_memory_raw_dispatch_preserves_existing_custom_event_routes(review_ledger, monkeypatch, name, handler):
    writer, records = review_ledger
    destination = MagicMock()
    monkeypatch.setattr(writer, handler, destination)
    event = RawEvent(type=EventType.RAW, event={"event": "on_custom_event", "name": name, "data": {"original": True}})
    writer(event)
    destination.assert_called_once_with(event)
    assert writer._memory_source_completions == {} and records == []


def sse_source_events():
    return [
        TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id="answer-1", role="assistant"),
        TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id="answer-1", delta="Original answer"),
        pending_answer_event(),
        finalization_event(
            {"message_id": "answer-1", "memory_source_complete": True, "source_text": "Original answer"}, "custom"
        ),
        CustomEvent(type=EventType.CUSTOM, name="public_notice", value={"visible": True}),
        RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="session-1", run_id="run-1"),
    ]


@pytest.mark.asyncio
async def test_actual_sse_encoder_hides_internal_events_but_keeps_persistence_and_public_output(
    review_ledger, monkeypatch
):
    writer, records = review_ledger

    async def upstream(agent, request):
        for event in sse_source_events():
            yield agent._dispatch_event(event)

    monkeypatch.setattr(LangGraphAGUIAgent, "run", upstream)
    agent = AidevAGUIAgent(name="review", graph=MagicMock(), event_handler=writer)
    frames = [
        json.loads(frame.removeprefix("data: ").strip()) async for frame in agent.run(SimpleNamespace(messages=[]))
    ]
    assert [frame["type"] for frame in frames] == [
        "MESSAGES_SNAPSHOT",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "CUSTOM",
        "RUN_FINISHED",
    ]
    assert frames[2]["delta"] == "Original answer"
    assert frames[3]["name"] == "public_notice" and frames[3]["value"] == {"visible": True}
    assert records[0]["content"] == "Original answer"
    assert completed_history(records, "session-1")[0]["message_id"] == "answer-1"
    writer._do_update_content.assert_called_once()


@pytest.fixture
def review_chat_builder(monkeypatch):
    seed = ChatCompletionAgent()
    builder = MagicMock(mcp_fetch_failures=[], file_resources=[])
    fields = {
        "skills": "skills",
        "tools": "tools",
        "knowledge_bases": "knowledge_bases",
        "knowledge_items": "knowledges",
        "subagents": "subagent_specs",
        "chat_history": "chat_history",
        "knowledge_query_options": "knowledge_query_options",
        "model_context_options": "model_context_options",
        "support_vision": "support_vision",
        "checkpointer": "checkpointer",
        "runtime_backend_resolver": "runtime_backend_resolver",
    }
    for method, field in fields.items():
        getattr(builder, "build_" + method).return_value = getattr(seed, field)
    builder.build_executor_info.return_value = {"executor": "alice"}
    builder.build_chat_model.return_value = MockChatModel(responses=["Answer"])
    builder.get_role_prompt.return_value = "Test role"
    monkeypatch.setattr("aidev_agent.services.agent.chat.ChatAgentBuilder", lambda ctx: builder)
    return builder


@pytest.mark.parametrize("agent_code", ["parent-agent", "child-agent"])
def test_chat_build_context_selects_memory_scope_consumed_by_the_real_runtime(
    review_chat_builder, review_manager, agent_code
):
    review_manager.memory_schemas.return_value["agent_code"] = agent_code
    ctx = AgentBuildContext(agent_code, AgentType.CHAT, review_manager, session_code="session-1", username="alice")
    agent = ChatCompletionAgent(memory_agent_code="stale-agent").build(ctx)
    agent.agent_info = {"agent_code": "wrong-fallback-agent"}
    executor = MagicMock()
    agent.agent_cls = executor
    agent._get_agent([HumanMessage(id="user-1", content="Hi")], execute_kwargs=ExecuteKwargs(executor="wrong-user"))
    runtime = executor.get_agent_executor.call_args.kwargs["personal_memory_runtime"]
    assert agent.memory_agent_code == agent_code
    assert runtime.context({})[1]["agent_code"] == agent_code
    review_manager.memory_schemas.assert_called_once_with(username="alice", agent_code=agent_code, timeout=2)
    runtime.complete({"messages": [AIMessage(id="answer-1", content="Answer")]}, {})
    payload = review_manager.complete_memory_round.call_args.args[0]
    assert payload["agent_code"] == agent_code
    assert review_manager.complete_memory_round.call_args.kwargs["username"] == "alice"


def test_completion_callback_ignores_non_assistant_generations_without_corrupting_them():
    user = HumanMessage(id="user-1", content="Not an assistant response")
    answer = AIMessage(id="answer-1", content="Answer")
    response = LLMResult(generations=[[ChatGeneration(message=user), ChatGeneration(message=answer)]])
    AssistantCompletionTimestamp(pending_transform=True).on_llm_end(response)
    assert user.content == "Not an assistant response" and user.response_metadata == {}
    assert answer.response_metadata["source_timestamp"]
    assert answer.response_metadata["memory_source_complete"] is False
