from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.nodes.model import convert_chat_history_to_messages
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history, session_date
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


@pytest.fixture
def manager():
    result = MagicMock(username="alice")
    result.memory_schemas.return_value = [
        {
            "function": {
                "name": name,
                "description": "Memory tool",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            }
        }
        for name in ["memory_write", "memory_update", "memory_search"]
    ]
    result.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent-a",
        "memory_epoch": 1,
        "enabled_at": None,
        "schemas": result.memory_schemas.return_value,
    }
    result.memory_tool.return_value = {"hits": []}
    return result


def make_runtime(manager, history=None):
    return automatic_personal_memory(
        manager, "alice", "session-1", history or [], [HumanMessage(content="Hi", id="u-1")], agent_code="agent-a"
    )


@pytest.mark.parametrize("username", [None, "", "   "])
def test_missing_user_skips_discovery(manager, username):
    assert automatic_personal_memory(manager, username, "s", [], [], agent_code="agent-a") is None
    manager.memory_schemas.assert_not_called()


@pytest.mark.parametrize("error", [ConnectionError("not deployed"), TimeoutError("unavailable"), ValueError("invalid")])
def test_unavailable_platform_skips_memory(manager, error):
    manager.memory_schemas.side_effect = error
    assert make_runtime(manager) is None
    manager.memory_schemas.assert_called_once_with(username="alice", agent_code="agent-a", timeout=2)


def test_invalid_schemas_skip_memory(manager):
    manager.memory_schemas.return_value = []
    assert make_runtime(manager) is None


def test_full_ledger_preserves_completed_history_and_date(manager):
    history = [
        ChatPrompt(id="old", role="user", content="Original text", created_at="2026-10-01T12:00:00Z"),
        ChatPrompt(id="a", role="assistant", content="Partial", status="error"),
    ]
    runtime = automatic_personal_memory(
        manager,
        "alice",
        "session-1",
        history,
        [HumanMessage(content="Transformed history", id="old"), HumanMessage(content="Hi", id="u-1")],
        agent_code="agent-a",
    )
    username, context = runtime.context({})
    assert username == "alice" and context["session_date"] == "2026-10-01"
    assert [item["text"] for item in context["messages"]] == ["Original text", "Hi"]
    runtime.complete(
        {"messages": [HumanMessage(content="Transformed", id="u-1"), AIMessage(content="Hello", id="a-1")]}, {}
    )
    snapshot = manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [item["text"] for item in snapshot] == ["Original text", "Hi", "Hello"]


def test_legacy_ledger_ids_are_stable():
    records = [{"role": "user", "content": "Hi"}]
    assert completed_history(records, "s") == completed_history(records, "s")
    assert completed_history(records, "s") != completed_history(records, "other")


@pytest.mark.parametrize("timestamp", ["2026-10-09T08:00:00Z", datetime(2026, 10, 9, 8, tzinfo=timezone.utc)])
def test_multiday_history_retains_each_message_time(manager, timestamp):
    history = [
        {"id": "old", "role": "user", "content": "Hi", "created_at": "2026-10-01T08:00:00Z"},
        {"id": "new", "role": "user", "content": "Meeting tomorrow", "created_at": timestamp},
    ]
    runtime = automatic_personal_memory(manager, "alice", "s", history, [], agent_code="agent-a")
    _, context = runtime.context({})
    assert context["session_date"] == "2026-10-01"
    assert context["messages"][-1]["timestamp"] == "2026-10-09T08:00:00+00:00"


@pytest.mark.parametrize("created_at", [None, "invalid", 123])
def test_invalid_created_at_falls_back_to_timestamp(created_at):
    history = [{"role": "user", "content": "Hello", "created_at": created_at, "timestamp": "2026-10-09T08:00:00+08:00"}]
    assert completed_history(history, "s")[0]["timestamp"] == "2026-10-09T08:00:00+08:00"


def test_tool_failure_does_not_interrupt_chat(manager):
    runtime = make_runtime(manager)
    manager.memory_tool.side_effect = ConnectionError("unavailable")
    tool = next(tool for tool in runtime.make_tools() if tool.name == "memory_search")
    assert "temporarily unavailable" in tool.invoke({"query": "Python"})


def test_callback_failure_does_not_interrupt_answer(manager):
    runtime = make_runtime(manager)
    manager.complete_memory_round.side_effect = ConnectionError("unavailable")
    assert runtime.complete({"messages": [AIMessage(content="Hello", id="a-1")]}, {}) == {}
    assert manager.complete_memory_round.call_args.kwargs == {"username": "alice", "timeout": 2}


def test_standard_chat_automatically_enables_memory(manager):
    agent = ChatCompletionAgent(
        memory_agent_code="agent-a",
        chat_model=MockChatModel(responses=["Hello"]),
        resource_manager=manager,
        executor_info={"executor": "alice"},
        thread_id="session-1",
    )
    messages = [HumanMessage(content="Hi", id="u-1")]
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs(executor="other-user"))
    result = graph.invoke({"messages": messages}, config)
    assert result["messages"][-1].content == "Hello"
    manager.memory_schemas.assert_called_once_with(username="alice", agent_code="agent-a", timeout=2)
    manager.complete_memory_round.assert_called_once()
    assert manager.complete_memory_round.call_args.kwargs["username"] == "alice"


def test_standard_chat_still_answers_before_platform_deployment(manager):
    manager.memory_schemas.side_effect = ConnectionError("not deployed")
    agent = ChatCompletionAgent(
        memory_agent_code="agent-a",
        chat_model=MockChatModel(responses=["Hello"]),
        resource_manager=manager,
        executor_info={"executor": "alice"},
        thread_id="s",
    )
    messages = [HumanMessage(content="Hi", id="u-1")]
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    assert graph.invoke({"messages": messages}, config)["messages"][-1].content == "Hello"
    manager.complete_memory_round.assert_not_called()


@pytest.mark.parametrize("enabled", [False, None])
def test_disabled_agent_skips_tools_and_snapshot_upload(manager, enabled):
    manager.memory_schemas.return_value["enabled"] = enabled
    assert make_runtime(manager) is None
    manager.memory_tool.assert_not_called()
    manager.complete_memory_round.assert_not_called()


@pytest.mark.parametrize("agent_code", ["", None, "   "])
def test_missing_agent_skips_memory_discovery(manager, agent_code):
    assert automatic_personal_memory(manager, "alice", "s", [], [], agent_code=agent_code) is None
    manager.memory_schemas.assert_not_called()


def test_discovery_cannot_switch_agent_identity(manager):
    manager.memory_schemas.return_value["agent_code"] = "agent-b"
    assert make_runtime(manager) is None
    manager.complete_memory_round.assert_not_called()


def test_reopened_agent_only_uploads_fresh_messages(manager):
    manager.memory_schemas.return_value.update(memory_epoch=3, enabled_at="2026-10-09T08:00:00Z")
    history = [
        {"id": "old", "role": "user", "content": "Old", "created_at": "2026-10-01T08:00:00Z"},
        {"id": "new", "role": "user", "content": "New", "created_at": "2026-10-09T08:00:00Z"},
    ]
    runtime = automatic_personal_memory(manager, "alice", "s", history, [], agent_code="agent-a")
    runtime.complete({"messages": [AIMessage(content="Answer", id="a")]}, {})
    payload = manager.complete_memory_round.call_args.args[0]
    assert payload["agent_code"] == "agent-a" and payload["memory_epoch"] == 3
    assert [message["message_id"] for message in payload["context"]["messages"]] == ["new", "a"]
    assert "agent_code" not in payload["context"]


@pytest.fixture
def real_input_agent(manager, monkeypatch):
    history = [
        ChatPrompt(id="old", role="user", content="Old", created_at="2026-10-01T00:00:00Z"),
        ChatPrompt(id="unknown-time", role="user", content="Undated old history"),
    ]
    agent = ChatCompletionAgent(
        chat_history=history,
        event_handler=MagicMock(spec=BaseSessionWriter),
        memory_agent_code="agent-a",
        chat_model=MockChatModel(responses=["Understood."]),
        resource_manager=manager,
        executor_info={"executor": "alice"},
        thread_id="s",
    )
    monkeypatch.setattr(ChatCompletionAgent, "_dispatch_custom", lambda *args: None)
    return agent


@pytest.mark.parametrize("epoch", [1, 3])
def test_real_chat_input_keeps_identity_and_time_after_activation(manager, real_input_agent, epoch):
    manager.memory_schemas.return_value.update(memory_epoch=epoch, enabled_at="2026-10-09T00:00:00Z")
    agent = real_input_agent
    before = datetime.now(timezone.utc)
    agent._prepare_pre_run_history(ExecuteKwargs(input="I prefer Python"))
    current = agent.chat_history[-1]
    assert current.id and before <= datetime.fromisoformat(current.created_at) <= datetime.now(timezone.utc)
    messages = convert_chat_history_to_messages(
        agent.chat_history,
        model_context_options=None,
        model_name="",
        agent_info=None,
        generating_keyword=None,
        files=[],
        support_vision=False,
    )
    assert messages[-1].id == current.id
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    graph.invoke({"messages": messages}, config)
    payload = manager.complete_memory_round.call_args.args[0]
    records = payload["context"]["messages"]
    assert [(item["role"], item["text"]) for item in records] == [
        ("user", "I prefer Python"),
        ("assistant", "Understood."),
    ]
    assert records[0]["message_id"] == current.id
    assert records[0]["timestamp"] == current.created_at
    assert payload["memory_epoch"] == epoch
    assert "created_at" not in agent.chat_history[1].model_dump()


def test_current_input_snapshot_is_stable_across_repeated_completion(manager):
    history = [ChatPrompt(id="u", role="user", content="Hi", created_at="2026-10-09T00:00:00Z")]
    runtime = automatic_personal_memory(
        manager, "alice", "s", history, [HumanMessage(content="Hi", id="u")], agent_code="agent-a"
    )
    state = {"messages": [AIMessage(content="Hello", id="a")]}
    runtime.complete(state, {})
    first = manager.complete_memory_round.call_args.args[0]
    runtime.complete(state, {})
    assert manager.complete_memory_round.call_args.args[0] == first
    assert [item["message_id"] for item in first["context"]["messages"]] == ["u", "a"]


def test_history_skips_non_evidence_and_keeps_stable_fallback_id():
    history = [
        None,
        {"role": "system", "content": "Secret"},
        {"role": "user", "content": []},
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Tool", "builtin_property": {"tool_calls": [{}]}},
        {"role": "user", "content": "Hi"},
    ]
    snapshot = completed_history(history, "s")
    assert len(snapshot) == 1 and snapshot[0]["text"] == "Hi"
    assert snapshot == completed_history(history, "s")
    assert session_date([None, {"created_at": "invalid"}, {"timestamp": "2026-10-09T12:00:00Z"}]) == "2026-10-09"
    assert session_date([None, {}]) == datetime.now(timezone.utc).date().isoformat()


@pytest.mark.parametrize(
    "messages",
    [
        [SystemMessage(content="System", id="system")],
        [HumanMessage(content="Missing ID")],
        [HumanMessage(content=[{"type": "text", "text": "Multimodal"}], id="u")],
        [AIMessage(content="Partial", id="a", response_metadata={"finish_reason": "length"})],
        [AIMessage(content="", id="a", tool_calls=[{"name": "tool", "args": {}, "id": "call"}])],
    ],
)
def test_visible_non_evidence_is_not_added(manager, messages):
    runtime = automatic_personal_memory(manager, "alice", "s", [], messages, agent_code="agent-a")
    assert runtime.context({})[1]["messages"] == []


def test_incompatible_manager_skips_discovery(manager):
    manager.complete_memory_round = None
    assert make_runtime(manager) is None
    manager.memory_schemas.assert_not_called()


@pytest.mark.parametrize("manager_value,session_id", [(None, "s"), (object(), "")])
def test_missing_manager_or_session_skips_memory(manager_value, session_id):
    assert automatic_personal_memory(manager_value, "alice", session_id, [], [], agent_code="agent-a") is None
