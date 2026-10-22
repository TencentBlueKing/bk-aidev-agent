"""Malformed discovery must be rejected before the ordinary model binds tools."""

from unittest.mock import MagicMock

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.memory import automatic_personal_memory
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI


class OfflineOpenAI(ChatOpenAI):
    def _generate(self, *args, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Hello"))])


@pytest.fixture
def schema_manager():
    manager = MagicMock(username="alice")
    manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent",
        "memory_epoch": 1,
        "enabled_at": None,
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    return manager


@pytest.mark.parametrize(
    "parameters",
    [
        {},
        None,
        {"type": "object", "properties": None},
        {"type": "object", "properties": {"query": 1}},
        {"type": "array", "items": {"type": "string"}},
        {"type": "object", "properties": {"query": {"$ref": "#/$defs/Missing"}}},
    ],
)
def test_malformed_schema_preserves_normal_chat(schema_manager, parameters):
    for item in schema_manager.memory_schemas.return_value["schemas"]:
        item["function"]["parameters"] = parameters
    messages = [HumanMessage(content="Hi", id="user")]
    assert automatic_personal_memory(schema_manager, "alice", "session", [], messages, agent_code="agent") is None
    agent = ChatCompletionAgent(
        memory_agent_code="agent",
        chat_model=OfflineOpenAI(api_key="test", model="gpt-test"),
        resource_manager=schema_manager,
        executor_info={"executor": "alice"},
        thread_id="session",
    )
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    assert graph.invoke({"messages": messages}, config)["messages"][-1].content == "Hello"
    schema_manager.memory_tool.assert_not_called()
    schema_manager.complete_memory_round.assert_not_called()


def test_valid_local_schema_reference_remains_supported(schema_manager):
    for item in schema_manager.memory_schemas.return_value["schemas"]:
        item["function"]["parameters"] = {
            "type": "object",
            "$defs": {"Query": {"type": "string"}},
            "properties": {"query": {"$ref": "#/$defs/Query"}},
        }
    runtime = automatic_personal_memory(schema_manager, "alice", "session", [], [], agent_code="agent")
    assert runtime is not None
    assert len(runtime.make_tools()) == 3
