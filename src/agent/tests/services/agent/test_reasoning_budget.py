"""Reasoning exhaustion is bounded with and without personal memory."""

import asyncio
import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from ag_ui.core import EventType
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import AgentInput
from aidev_agent.core.nodes.model.quality_gate import THINKING_EXHAUSTED_MESSAGE
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent import memory as memory_module
from aidev_agent.services.agent.chat import ChatCompletionAgent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver


class CountingReasoningModel(FakeMessagesListChatModel):
    model_name: str = "reasoning-budget-test"
    invocations: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, *args, **kwargs):
        self.invocations += 1
        return super()._generate(*args, **kwargs)


@pytest.fixture
def budget_agent(agent_enabled, user_allowed, monkeypatch):
    monkeypatch.setattr(memory_module, "_policy_suppressed_until", {})
    manager = MagicMock()
    manager.memory_schemas.return_value = {
        "enabled": user_allowed,
        "agent_code": "budget-agent",
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    manager.memory_search.return_value = {"memories": []}
    model = CountingReasoningModel(
        responses=[
            AIMessage(
                content="",
                additional_kwargs={"reasoning_content": "thinking without an answer"},
                response_metadata={"finish_reason": "length"},
            )
        ]
    )
    agent = ChatCompletionAgent(
        memory_agent_code="budget-agent",
        chat_model=model,
        resource_manager=manager,
        executor_info={"executor": "alice"},
        thread_id="budget-thread",
        agent_info={"memory_settings": {"enabled": agent_enabled}},
    )
    return agent, model, manager


@pytest.mark.parametrize("agent_enabled,user_allowed", [(False, True), (True, False), (True, True)])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_reasoning_exhaustion_makes_one_model_call_and_never_writes_memory(
    budget_agent, agent_enabled, user_allowed, asynchronous
):
    agent, model, manager = budget_agent
    messages = [HumanMessage(id="user-1", content="Remember my preference")]
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    state = {"messages": messages}
    result = asyncio.run(graph.ainvoke(state, config)) if asynchronous else graph.invoke(state, config)
    assert result["messages"][-1].content == THINKING_EXHAUSTED_MESSAGE
    assert model.invocations == 1
    assert manager.memory_schemas.call_count == int(agent_enabled)
    manager.memory_write.assert_not_called()
    manager.memory_update.assert_not_called()
    manager.complete_memory_round.assert_not_called()


@pytest.mark.parametrize("agent_enabled,user_allowed", [(False, True), (True, True)])
async def test_reasoning_budget_failure_reaches_the_chat_card(budget_agent):
    agent, model, _ = budget_agent
    messages = [HumanMessage(id="user-1", content="Remember my preference")]
    graph, config = agent._get_agent(messages, execute_kwargs=ExecuteKwargs())
    graph.checkpointer = InMemorySaver()
    config.setdefault("configurable", {})["thread_id"] = "budget-thread"
    adapter = AidevAGUIAgent(name="budget", graph=graph, config=config)
    request = AgentInput(
        thread_id="budget-thread",
        run_id=str(uuid4()),
        state={},
        messages=[{"id": "user-1", "role": "user", "content": "Remember my preference"}],
        stream_input={"messages": messages},
        tools=[],
        context=[],
        forwarded_props={},
    )
    events = [json.loads(frame.removeprefix("data:").strip()) async for frame in adapter.run(request)]
    text = "".join(event.get("delta", "") for event in events if event["type"] == EventType.TEXT_MESSAGE_CONTENT)
    assert text.count(THINKING_EXHAUSTED_MESSAGE) == 1
    assert model.invocations == 1
