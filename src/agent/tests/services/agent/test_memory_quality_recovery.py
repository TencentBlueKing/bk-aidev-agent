"""Only quality-accepted responses may become evidence in later rounds."""

import asyncio
import copy
from unittest.mock import MagicMock

import pytest
from ag_ui.core import CustomEvent, EventType
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext, RecoveryRetryError
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

FINAL = "Final answer: the user lives in Paris."


class RejectDraftGate(QualityGate):
    def _judge_response_completion(self, response, working_messages, **kwargs):
        return not response.content.startswith("Draft")


class LedgerCallback(BaseCallbackHandler):
    def __init__(self, writer):
        self.writer = writer

    def on_llm_end(self, response, **kwargs):
        for generations in response.generations:
            for generation in generations:
                self.writer(
                    CustomEvent(
                        type=EventType.CUSTOM,
                        name=SessionPersistenceEventNames.ChatModelEnd.value,
                        value=build_model_end_payload(copy.deepcopy(generation.message), {}),
                    )
                )

    def on_custom_event(self, name, data, **kwargs):
        if name == SessionPersistenceEventNames.MemorySourceFinalized.value:
            self.writer(CustomEvent(type=EventType.CUSTOM, name=name, value=copy.deepcopy(data)))


@pytest.fixture
def ledger():
    client, rows = MagicMock(), []

    def create(*, json, headers):
        row = copy.deepcopy(json)
        row.update(id=len(rows) + 1)
        rows.append(row)
        return {"data": copy.deepcopy(row)}

    def update(*, path_params, json, headers, timeout=None):
        row = next(row for row in rows if row["id"] == path_params["id"])
        row.update(copy.deepcopy(json))
        return {"data": copy.deepcopy(row)}

    client.api.create_chat_session_content.side_effect = create
    client.api.update_chat_session_content.side_effect = update
    return AGUISessionWriter("session", client, username="alice"), rows


@pytest.fixture
def manager():
    resource = MagicMock()
    resource.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent",
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    return resource


def recovery_chain(first, promote, outcome):
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = [
        StructuredTool.from_function(lambda query: query, name="lookup", description="Lookup")
    ]
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(id="user", content="Where do I live?")
    ]
    retries = 0 if outcome == "no_retry" else 1
    chain = _build_model_chain(
        llm=MockChatModel(responses=[first, FINAL if outcome == "success" else first]),
        context_assembly=assembly,
        max_retries=retries,
        quality_gate=RejectDraftGate(),
        use_structured_response=False,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=promote,
        track_memory_source=True,
    )
    context = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=retries)
    )
    return chain, context


def invoke_recovery(chain, context, config, asynchronous, exhausted):
    def invoke():
        return (
            asyncio.run(chain.ainvoke(context, config=config)) if asynchronous else chain.invoke(context, config=config)
        )

    if exhausted:
        with pytest.raises(RecoveryRetryError):
            invoke()
        return context.response
    return invoke().response


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("outcome", ["success", "exhausted", "no_retry"])
@pytest.mark.parametrize("promote", [False, True])
@pytest.mark.parametrize("first", ["<think>Unconfirmed Berlin hypothesis.</think>", "Draft: The user lives in Berlin."])
def test_recovery_eligibility_survives_history_reload(ledger, manager, asynchronous, outcome, promote, first):
    writer, rows = ledger
    chain, context = recovery_chain(first, promote, outcome)
    config = {"callbacks": [LedgerCallback(writer)]}
    exhausted = outcome == "exhausted" or outcome == "no_retry" and first.startswith("Draft")
    answer = invoke_recovery(chain, context, config, asynchronous, exhausted)
    expected = [FINAL] if outcome == "success" else []
    assert answer.content == (FINAL if expected else first)
    assert len(rows) == (1 if outcome == "no_retry" else 2)
    assert rows[0]["content"] == first  # Existing display and persistence are preserved.
    history = [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows]
    assert [item["text"] for item in completed_history(history, "session")] == expected
    current = automatic_personal_memory(manager, "alice", "session", [], [], agent_code="agent")
    current.complete({"messages": [answer]}, {})
    assert manager.complete_memory_round.call_count == bool(expected)
    following = automatic_personal_memory(manager, "alice", "session", history, [], agent_code="agent")
    following.complete({"messages": [AIMessage(id="next", content="Next completed answer")]}, {})
    sent = manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [item["text"] for item in following.tool_source_provider("assistant")] == expected
    assert [item["text"] for item in sent] == ["Next completed answer"]
