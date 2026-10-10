from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from langchain_core.messages import AIMessage, HumanMessage


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
    result.memory_tool.return_value = {"hits": []}
    return result


def make_runtime(manager, history=None):
    return automatic_personal_memory(
        manager, "alice", "session-1", history or [], [HumanMessage(content="Hi", id="u-1")]
    )


@pytest.mark.parametrize("username", [None, "", "   "])
def test_missing_user_skips_discovery(manager, username):
    assert automatic_personal_memory(manager, username, "s", [], []) is None
    manager.memory_schemas.assert_not_called()


@pytest.mark.parametrize("error", [ConnectionError("not deployed"), TimeoutError("unavailable"), ValueError("invalid")])
def test_unavailable_platform_skips_memory(manager, error):
    manager.memory_schemas.side_effect = error
    assert make_runtime(manager) is None
    manager.memory_schemas.assert_called_once_with(username="alice", timeout=2)


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
    runtime = automatic_personal_memory(manager, "alice", "s", history, [])
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
        chat_model=MockChatModel(responses=["Hello"]),
        resource_manager=manager,
        executor_info={"executor": "alice"},
        thread_id="session-1",
    )
    messages = [HumanMessage(content="Hi", id="u-1")]
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs(executor="other-user"))
    result = graph.invoke({"messages": messages}, config)
    assert result["messages"][-1].content == "Hello"
    manager.memory_schemas.assert_called_once_with(username="alice", timeout=2)
    manager.complete_memory_round.assert_called_once()
    assert manager.complete_memory_round.call_args.kwargs["username"] == "alice"


def test_standard_chat_still_answers_before_platform_deployment(manager):
    manager.memory_schemas.side_effect = ConnectionError("not deployed")
    agent = ChatCompletionAgent(
        chat_model=MockChatModel(responses=["Hello"]),
        resource_manager=manager,
        executor_info={"executor": "alice"},
        thread_id="s",
    )
    messages = [HumanMessage(content="Hi", id="u-1")]
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    assert graph.invoke({"messages": messages}, config)["messages"][-1].content == "Hello"
    manager.complete_memory_round.assert_not_called()
