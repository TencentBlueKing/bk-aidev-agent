"""Agents without personal memory keep the base persistence, timeout and quality-gate behavior."""

import asyncio
import copy
from unittest.mock import MagicMock

import pytest
from ag_ui.core import CustomEvent, EventType
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.core.nodes.model import node as model_node_module
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.core.nodes.model.utils import has_content_after_think_block, strip_think_blocks
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.packages.langchain_core.output_parsers import StructuredOutputToToolMessageParser
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent import memory as memory_module
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.memory import automatic_personal_memory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk
from langchain_core.tools import StructuredTool


class FinishReasonModel(MockChatModel):
    finish_reason: str = "stop"

    async def _astream(self, *args, **kwargs):
        async for chunk in super()._astream(*args, **kwargs):
            yield chunk
        yield ChatGenerationChunk(
            message=AIMessageChunk(content="", response_metadata={"finish_reason": self.finish_reason})
        )


def chain_events(text, *, track, structured=False, finish_reason="stop"):
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = [
        StructuredTool.from_function(lambda q: q, name="lookup", description="Lookup")
    ]
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(content="Question")
    ]
    chain = _build_model_chain(
        llm=FinishReasonModel(responses=[text], finish_reason=finish_reason),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=QualityGate(enable_judge_response=False),
        use_structured_response=structured,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
        track_memory_source=track,
    )
    ctx = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )

    async def collect():
        events, answer = [], None
        async for event in chain.astream_events(ctx, version="v2"):
            if event["event"] == "on_chat_model_end":
                payload = build_model_end_payload(copy.deepcopy(event["data"]["output"]), {})
                events.append(
                    CustomEvent(
                        type=EventType.CUSTOM, name=SessionPersistenceEventNames.ChatModelEnd.value, value=payload
                    )
                )
            elif event["event"] == "on_custom_event":
                events.append(
                    CustomEvent(type=EventType.CUSTOM, name=event["name"], value=copy.deepcopy(event["data"]))
                )
            elif event["event"] == "on_chain_end" and not event["parent_ids"]:
                answer = event["data"]["output"].response
        return events, answer

    return asyncio.run(collect())


def persist(events):
    client, rows = MagicMock(), []

    def create(*, json, headers):
        rows.append(copy.deepcopy(json))
        return {"data": {"id": len(rows)}}

    def update(*, path_params, json, headers, timeout=None):
        rows[path_params["id"] - 1].update(copy.deepcopy(json))

    client.api.create_chat_session_content.side_effect = create
    client.api.update_chat_session_content.side_effect = update
    writer = AGUISessionWriter("s", client, username="alice")
    for event in events:
        writer(event)
    return client, rows


@pytest.mark.parametrize("structured", [False, True])
def test_disabled_memory_adds_no_finalization_update_or_duplicate_body(structured):
    text = '{"action":"Final Answer","action_input":"Plain answer"}' if structured else "Plain answer"
    events, answer = chain_events(text, track=False, structured=structured)
    assert SessionPersistenceEventNames.MemorySourceFinalized.value not in {event.name for event in events}
    assert not {"memory_source_pending", "memory_source_complete", "source_text"} & set(answer.response_metadata)
    client, rows = persist(events)
    assert client.api.create_chat_session_content.call_count == 1
    client.api.update_chat_session_content.assert_not_called()
    assert "source_text" not in rows[0]["property"]["builtin_property"]


@pytest.mark.parametrize("text,stored", [("Plain answer", False), ("  Plain answer\n", True)])
def test_enabled_memory_stores_source_text_only_when_body_differs(text, stored):
    events, _ = chain_events(text, track=True)
    client, rows = persist(events)
    assert client.api.update_chat_session_content.call_count == 1
    builtin = rows[0]["property"]["builtin_property"]
    assert builtin["memory_source_complete"] is True
    assert ("source_text" in builtin) is stored
    assert builtin.get("source_text", rows[0]["content"]) == text


def test_ordinary_updates_keep_client_default_timeout():
    client = MagicMock()
    writer = AGUISessionWriter("s", client, username="alice")
    writer._do_update_content(1, {"property": {"builtin_property": {"memory_source_complete": False}}}, {})
    assert "timeout" not in client.api.update_chat_session_content.call_args.kwargs
    writer._do_update_memory_source(1, {"property": {"builtin_property": {"memory_source_complete": True}}}, {})
    assert client.api.update_chat_session_content.call_args.kwargs["timeout"] == writer._MEMORY_SOURCE_UPDATE_TIMEOUT


def test_in_process_writer_override_receives_memory_source_updates():
    class InProcessWriter(AGUISessionWriter):
        def __init__(self):
            super().__init__("s", None, username="alice")
            self.updates = []

        def _do_update_content(self, content_id, payload, headers):
            self.updates.append((content_id, payload))

    writer = InProcessWriter()
    writer._do_update_memory_source(1, {"property": {"builtin_property": {"memory_source_complete": True}}}, {})
    assert writer.updates == [(1, {"property": {"builtin_property": {"memory_source_complete": True}}})]
    assert writer._update_timeout is None


def test_deferred_tool_call_flush_keeps_client_default_timeout():
    client = MagicMock()
    writer = AGUISessionWriter("s", client, username="alice")
    writer._content_ids_by_message_id["answer"] = 1
    writer._assistant_builtin_properties["answer"] = {
        "message_id": "answer",
        "tool_calls": [],
        "memory_source_complete": False,
    }
    writer._deferred_approval_tool_calls = {"answer": [{"id": "call-1", "name": "lookup"}]}
    writer._flush_deferred_tool_call("call-1", "lookup")
    kwargs = client.api.update_chat_session_content.call_args.kwargs
    assert kwargs["json"]["property"]["builtin_property"]["tool_calls"] == [{"id": "call-1", "name": "lookup"}]
    assert "timeout" not in kwargs


@pytest.mark.parametrize("track", [False, True])
def test_structured_length_never_triggers_truncation_recovery(track):
    original = AIMessage(
        id="answer",
        content='{"action":"Final Answer","action_input":"Parsed answer"}',
        response_metadata={"finish_reason": "length", "token_usage": {"total_tokens": 9}},
    )
    parsed = StructuredOutputToToolMessageParser(keep_memory_source=track).parse_result(
        [ChatGeneration(message=original)]
    )
    assert "finish_reason" not in parsed.response_metadata and "token_usage" not in parsed.response_metadata
    assert (parsed.id == "answer") is track
    events, answer = chain_events(original.content, track=track, structured=True, finish_reason="length")
    assert answer.content == "Parsed answer" and "finish_reason" not in answer.response_metadata
    finalized = [
        event.value for event in events if event.name == SessionPersistenceEventNames.MemorySourceFinalized.value
    ]
    assert finalized == ([{"message_id": answer.id, "memory_source_complete": False}] if track else [])


@pytest.mark.parametrize(
    "content,expected,has_content",
    [
        ("    <think>long reasoning</think>", "", False),
        ("> <think>x</think>\nanswer", "> \nanswer", True),
        ("```\nfence\n<think>secret</think>", "```\nfence", True),
        ("<think>a</think>\n    code line", "code line", True),
    ],
)
def test_quality_gate_keeps_base_think_block_semantics(content, expected, has_content):
    assert strip_think_blocks(content) == expected
    assert has_content_after_think_block(content) is has_content


def test_indented_think_literal_is_thinking_exhaustion_and_not_evidence():
    events, _ = chain_events("    <think>long reasoning</think>", track=True)
    finalized = [
        event.value for event in events if event.name == SessionPersistenceEventNames.MemorySourceFinalized.value
    ]
    assert finalized and all(item["memory_source_complete"] is False for item in finalized)


@pytest.fixture
def policy_manager():
    manager = MagicMock(username="service-account")
    manager.memory_schemas.return_value = {"enabled": False, "agent_code": "agent-a", "version": "1.0.0"}
    return manager


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(memory_module.time, "monotonic", lambda: now[0])
    return now


@pytest.mark.parametrize(
    "configure,ttl",
    [
        (lambda manager: None, memory_module.POLICY_DISABLED_TTL),
        (
            lambda manager: setattr(manager.memory_schemas, "side_effect", TimeoutError("slow")),
            memory_module.POLICY_FAILURE_TTL,
        ),
    ],
)
def test_disabled_or_failed_policy_is_not_probed_again_until_ttl(policy_manager, clock, configure, ttl):
    configure(policy_manager)
    for _ in range(3):
        assert automatic_personal_memory(policy_manager, "alice", "s", [], [], agent_code="agent-a") is None
    assert policy_manager.memory_schemas.call_count == 1
    clock[0] += ttl - 0.001
    automatic_personal_memory(policy_manager, "alice", "s", [], [], agent_code="agent-a")
    assert policy_manager.memory_schemas.call_count == 1
    clock[0] += 0.002
    automatic_personal_memory(policy_manager, "alice", "s", [], [], agent_code="agent-a")
    assert policy_manager.memory_schemas.call_count == 2


def test_policy_suppression_is_scoped_by_tenant_agent_and_user(policy_manager, clock):
    automatic_personal_memory(policy_manager, "alice", "s", [], [], agent_code="agent-a")
    automatic_personal_memory(policy_manager, "bob", "s", [], [], agent_code="agent-a")
    automatic_personal_memory(policy_manager, "alice", "s", [], [], agent_code="agent-b")
    other_tenant = MagicMock(tenant_id="tenant-b")
    other_tenant.memory_schemas.return_value = {"enabled": False}
    automatic_personal_memory(other_tenant, "alice", "s", [], [], agent_code="agent-a")
    assert policy_manager.memory_schemas.call_count == 3
    other_tenant.memory_schemas.assert_called_once()


def test_enabled_policy_is_probed_every_round(policy_manager, clock):
    policy_manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent-a",
        "version": "1.0.0",
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    for _ in range(2):
        assert automatic_personal_memory(policy_manager, "alice", "s", [], [], agent_code="agent-a") is not None
    assert policy_manager.memory_schemas.call_count == 2


def test_policy_cache_stays_bounded(policy_manager, clock, monkeypatch):
    monkeypatch.setattr(memory_module, "POLICY_CACHE_MAX_ENTRIES", 3)
    for index in range(5):
        automatic_personal_memory(policy_manager, f"user-{index}", "s", [], [], agent_code="agent-a")
    assert len(memory_module._policy_suppressed_until) == 3
    automatic_personal_memory(policy_manager, "user-0", "s", [], [], agent_code="agent-a")
    assert policy_manager.memory_schemas.call_count == 6


def recorded_tracking(monkeypatch):
    seen = []
    original = model_node_module._build_model_chain

    def record(**kwargs):
        seen.append(kwargs["track_memory_source"])
        return original(**kwargs)

    monkeypatch.setattr(model_node_module, "_build_model_chain", record)
    return seen


@pytest.mark.parametrize("executor_info", [None, {}, {"executor": ""}])
def test_memory_owner_never_falls_back_to_resource_manager_account(policy_manager, monkeypatch, executor_info):
    seen = recorded_tracking(monkeypatch)
    agent = ChatCompletionAgent(
        memory_agent_code="agent-a",
        chat_model=MockChatModel(responses=["Hello"]),
        resource_manager=policy_manager,
        executor_info=executor_info,
        thread_id="s",
    )
    messages = [HumanMessage(content="Hi", id="u-1")]
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    assert graph.invoke({"messages": messages}, config)["messages"][-1].content == "Hello"
    policy_manager.memory_schemas.assert_not_called()
    assert seen == [False]


def test_standard_chat_tracks_memory_source_only_when_enabled(policy_manager, monkeypatch):
    seen = recorded_tracking(monkeypatch)
    agent = ChatCompletionAgent(
        memory_agent_code="agent-a",
        chat_model=MockChatModel(responses=["Hello"]),
        resource_manager=policy_manager,
        executor_info={"executor": "alice"},
        thread_id="s",
    )
    messages = [HumanMessage(content="Hi", id="u-1")]
    agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    assert seen == [False]
