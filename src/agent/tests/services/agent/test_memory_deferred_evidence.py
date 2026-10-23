"""Display fallbacks must never qualify incomplete model output as memory evidence."""

import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from ag_ui.core import CustomEvent, EventType, RawEvent
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.message_metadata import AssistantCompletionTimestamp
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult
from langchain_core.tools import StructuredTool


def pending_answer(kind):
    name = "approval_tool" if kind == "approval" else kind
    metadata = {"approval": {"enabled": True}} if kind == "approval" else {}
    tool = SimpleNamespace(name=name, description="Test", metadata=metadata)
    answer = AIMessage(
        id="pending",
        content="Unconfirmed draft",
        tool_calls=[{"id": "call", "name": name, "args": {}}],
        response_metadata={"finish_reason": "tool_calls"},
    )
    return tool, answer


def persist_answer(tool, answer, event_kind):
    client = MagicMock()
    client.api.create_chat_session_content.return_value = {"data": {"id": 7}}
    writer = AGUISessionWriter("session", client, username="alice")
    writer._tools_mapping = {tool.name: tool}
    payload = build_model_end_payload(answer, writer._tools_mapping)
    assert payload["tool_calls"] == [] and len(payload["deferred_tool_calls"]) == 1
    if event_kind == "external":
        payload.pop("memory_source_complete", None)
    event = (
        RawEvent(type=EventType.RAW, event={"data": {"output": answer}})
        if event_kind == "raw"
        else CustomEvent(type=EventType.CUSTOM, name=SessionPersistenceEventNames.ChatModelEnd.value, value=payload)
    )
    writer.handle_model_end(event)
    record = copy.deepcopy(client.api.create_chat_session_content.call_args.kwargs["json"])
    record.update(id=7, builtin_property=record["property"]["builtin_property"])
    return record


@pytest.mark.parametrize("kind", ["approval", "ask_user_question"])
@pytest.mark.parametrize("pending_transform", [False, True])
@pytest.mark.parametrize("event_kind", ["raw", "custom", "external"])
def test_native_deferred_tool_request_is_not_reloaded_as_completed_answer(kind, pending_transform, event_kind):
    tool, answer = pending_answer(kind)
    AssistantCompletionTimestamp(pending_transform=pending_transform).on_llm_end(
        LLMResult(generations=[[ChatGeneration(message=answer)]])
    )
    record = persist_answer(tool, answer, event_kind)
    assert record["content"] == "Unconfirmed draft" and record["status"] == "complete"
    assert record["builtin_property"]["memory_source_complete"] is False
    assert completed_history([record], "session") == []


@pytest.fixture
def memory_manager():
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


def test_next_successful_round_excludes_the_native_pending_tool_request(memory_manager):
    tool, answer = pending_answer("ask_user_question")
    record = persist_answer(tool, answer, "external")
    runtime = automatic_personal_memory(memory_manager, "alice", "session", [record], [], agent_code="agent")
    runtime.complete({"messages": [AIMessage(id="final", content="Confirmed answer")]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [message["message_id"] for message in sent] == ["final"]


class NativeAnswerModel(MockChatModel):
    answer: str = ""

    def _generate(self, *args, **kwargs):
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        id="native-answer",
                        content=self.answer,
                        additional_kwargs={"reasoning_content": "Unconfirmed reasoning"},
                        response_metadata={"finish_reason": "stop"},
                    )
                )
            ]
        )


def native_answer(content):
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = [
        StructuredTool.from_function(lambda query: query, name="lookup", description="Lookup")
    ]
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(content="Hi")
    ]
    chain = _build_model_chain(
        llm=NativeAnswerModel(answer=content),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=QualityGate(enable_judge_response=False),
        use_structured_response=False,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
        track_memory_source=True,
    )
    context = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )
    return chain.invoke(context).response


def persist_native_answer(answer, event_kind):
    client = MagicMock()
    client.api.create_chat_session_content.return_value = {"data": {"id": 7}}
    writer = AGUISessionWriter("session", client, username="alice")
    event = (
        RawEvent(type=EventType.RAW, event={"data": {"output": answer}})
        if event_kind == "raw"
        else CustomEvent(
            type=EventType.CUSTOM,
            name=SessionPersistenceEventNames.ChatModelEnd.value,
            value=build_model_end_payload(answer, {}),
        )
    )
    writer.handle_model_end(event)
    record = copy.deepcopy(client.api.create_chat_session_content.call_args.kwargs["json"])
    record.update(id=7, builtin_property=record["property"]["builtin_property"])
    return record


@pytest.mark.parametrize("content", ["", " \n ", "Final answer"])
@pytest.mark.parametrize("event_kind", ["raw", "custom"])
def test_native_answer_eligibility_survives_display_fallback(memory_manager, content, event_kind):
    answer = native_answer(content)
    assert answer.content == content and answer.response_metadata["source_timestamp"]
    record = persist_native_answer(answer, event_kind)
    assert record["content"] == (content.strip() or "Unconfirmed reasoning")
    current = automatic_personal_memory(memory_manager, "alice", "session", [], [], agent_code="agent")
    current.complete({"messages": [answer]}, {})
    if content.strip():
        memory_manager.complete_memory_round.assert_called_once()
        expected_ids = ["native-answer", "next"]
    else:
        memory_manager.complete_memory_round.assert_not_called()
        assert record["builtin_property"]["memory_source_complete"] is False
        expected_ids = ["next"]
    following = automatic_personal_memory(memory_manager, "alice", "session", [record], [], agent_code="agent")
    following.complete({"messages": [AIMessage(id="next", content="Hello")]}, {})
    sent = memory_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [message["message_id"] for message in sent] == expected_ids
    assert [message["text"] for message in sent] == (["Final answer", "Hello"] if content.strip() else ["Hello"])
