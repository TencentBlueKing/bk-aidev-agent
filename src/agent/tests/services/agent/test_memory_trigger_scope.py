"""单次按指定内容、单轮只含当前问答，重新开启不补抽取历史。"""

import copy
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.tools.memory import PersonalMemoryRuntime
from aidev_agent.services.agent.memory import automatic_personal_memory
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture
def scope_manager():
    manager = MagicMock()
    manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent",
        "schemas": [
            {
                "function": {
                    "name": name,
                    "description": "Memory",
                    "parameters": {
                        "type": "object",
                        "properties": {"role": {"type": "string"}, "text": {"type": "string"}},
                    },
                }
            }
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    manager.memory_tool.return_value = {"memories": []}
    return manager


def history_pair(prefix, eligible=True):
    return [
        {"id": prefix + "-u", "role": "user", "content": prefix + " user"},
        {
            "id": prefix + "-a",
            "role": "assistant",
            "content": prefix + " answer",
            "builtin_property": {"memory_source_complete": eligible},
        },
    ]


@pytest.mark.parametrize("eligible", [False, True])
@pytest.mark.parametrize("history_size", [1, 40])
def test_reenable_only_submits_new_question_and_answer(scope_manager, eligible, history_size):
    history = sum([history_pair(str(i), eligible) for i in range(history_size)], [])
    original = copy.deepcopy(history)
    messages = [HumanMessage(id="new-u", content="New question")]
    assert (
        automatic_personal_memory(
            scope_manager, "alice", "s", history, messages, agent_code="agent", memory_settings={"enabled": False}
        )
        is None
    )
    scope_manager.memory_schemas.assert_not_called()
    runtime = automatic_personal_memory(
        scope_manager, "alice", "s", history, messages, agent_code="agent", memory_settings={"enabled": True}
    )
    assert [item["message_id"] for item in runtime.context({})[1]["messages"]] == ["new-u"]
    runtime.complete({"messages": [AIMessage(id="new-a", content="New answer")]}, {})
    payload = scope_manager.complete_memory_round.call_args.args[0]
    assert [item["message_id"] for item in payload["context"]["messages"]] == ["new-u", "new-a"]
    assert history == original


@pytest.mark.parametrize("role,expected", [("user", ["new-u"]), ("assistant", ["old-a"]), ("all", ["old-a", "new-u"])])
def test_explicit_single_trigger_sends_only_selected_original(scope_manager, role, expected):
    history = history_pair("earlier") + history_pair("old")
    runtime = automatic_personal_memory(
        scope_manager,
        "alice",
        "s",
        history,
        [HumanMessage(id="new-u", content="Save the selected original")],
        agent_code="agent",
        memory_settings={"enabled": True},
    )
    runtime.make_tools()[0].invoke({"role": role})
    payload = scope_manager.memory_tool.call_args.args[0]
    assert payload["call"] == {"role": role}
    assert [item["message_id"] for item in payload["context"]["messages"]] == expected
    scope_manager.complete_memory_round.assert_not_called()


def test_generated_text_trigger_never_sends_history(scope_manager):
    runtime = automatic_personal_memory(
        scope_manager,
        "alice",
        "s",
        history_pair("old"),
        [HumanMessage(id="new-u", content="Remember Python")],
        agent_code="agent",
        memory_settings={"enabled": True},
    )
    runtime.make_tools()[0].invoke({"text": "The user prefers Python"})
    payload = scope_manager.memory_tool.call_args.args[0]
    assert payload["call"]["text"] == "The user prefers Python"
    assert [item["message_id"] for item in payload["context"]["messages"]] == ["new-u"]


def test_custom_runtime_cannot_merge_all_graph_history_into_round(scope_manager):
    context = {
        "username": "alice",
        "agent_code": "agent",
        "session_id": "s",
        "session_date": "2026-10-26",
        "messages": [],
    }
    runtime = PersonalMemoryRuntime(lambda _: context, manager=scope_manager)
    old = [HumanMessage(id="old-u", content="Old question"), AIMessage(id="old-a", content="Old answer")]
    current = [
        HumanMessage(id="new-u", content="New question", response_metadata={"timestamp": "2026-10-26T00:00:00Z"}),
        AIMessage(id="new-a", content="New answer"),
    ]
    runtime.complete({"messages": old + current}, {})
    payload = scope_manager.complete_memory_round.call_args.args[0]
    assert [item["message_id"] for item in payload["context"]["messages"]] == ["new-u", "new-a"]
    assert payload["context"]["messages"][0]["timestamp"] == "2026-10-26T00:00:00+00:00"
