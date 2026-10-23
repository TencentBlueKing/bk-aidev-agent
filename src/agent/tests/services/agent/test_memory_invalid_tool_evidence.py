"""Malformed native tool calls must remain ineligible across persistence."""

import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.core.tools.memory import PersonalMemoryRuntime, is_complete_ai_message
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.services.agent.memory import completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.message_metadata import finalize_memory_source
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool
from langchain_openai.chat_models.base import _convert_dict_to_message

from .test_memory_callback_order import CaptureBeforeStamp


def malformed_message(finish_reason="tool_calls"):
    message = _convert_dict_to_message(
        {
            "role": "assistant",
            "content": "I will save your preference now.",
            "tool_calls": [
                {"type": "function", "id": "call-bad", "function": {"name": "remember", "arguments": '{"preference":'}}
            ],
        }
    )
    message.response_metadata["finish_reason"] = finish_reason
    return message


class MalformedToolModel(MockChatModel):
    def _generate(self, *args, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=malformed_message())])


def make_chain():
    assembly = SimpleNamespace(
        get_choice_tools=lambda ctx: [
            StructuredTool.from_function(lambda preference: preference, name="remember", description="Remember")
        ],
        get_chat_prompt_variables=lambda ctx: {},
        get_chat_prompt_template=lambda ctx: ChatPromptTemplate.from_messages([("human", "Remember my preference")]),
    )
    return _build_model_chain(
        llm=MalformedToolModel(),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=QualityGate(enable_judge_response=False),
        use_structured_response=False,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
        track_memory_source=True,
    )


def assert_no_completion(answer):
    manager, provider = MagicMock(), MagicMock()
    PersonalMemoryRuntime(provider, manager=manager).complete({"messages": [answer]}, {})
    provider.assert_not_called()
    manager.complete_memory_round.assert_not_called()


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_malformed_tool_request_is_not_current_or_persisted_evidence(asynchronous):
    rows = []
    client = MagicMock()

    def create(*, json, headers):
        rows.append(copy.deepcopy(json))
        return {"data": {"id": 1}}

    def update(*, path_params, json, headers, timeout=None):
        rows[0].update(copy.deepcopy(json))

    client.api.create_chat_session_content.side_effect = create
    client.api.update_chat_session_content.side_effect = update
    writer = AGUISessionWriter("s", client, username="alice")
    context = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )
    config = {"callbacks": [CaptureBeforeStamp(writer)]}
    chain = make_chain()
    result = await chain.ainvoke(context, config=config) if asynchronous else chain.invoke(context, config=config)
    answer = result.response
    assert answer.invalid_tool_calls and not answer.tool_calls
    assert answer.content == "I will save your preference now."
    assert answer.response_metadata["memory_source_complete"] is False
    assert not is_complete_ai_message(answer)
    history = [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows]
    assert completed_history(history, "s") == []
    assert_no_completion(answer)


@pytest.mark.parametrize("finish_reason", [None, "stop", "tool_calls", "function_call"])
def test_invalid_calls_override_explicit_source_acceptance(finish_reason):
    message = malformed_message(finish_reason)
    message.response_metadata.update(memory_source_complete=True, memory_source_pending=True)
    assert not is_complete_ai_message(message)
    assert build_model_end_payload(message, {})["memory_source_complete"] is False
    assert finalize_memory_source(message)["memory_source_complete"] is False


@pytest.mark.parametrize("finish_reason", ["tool_calls", "TOOL_CALLS", "function_call"])
def test_tool_finish_reason_excludes_legacy_history_without_tool_metadata(finish_reason):
    message = AIMessage(
        id="a",
        content="I will call the tool.",
        response_metadata={
            "finish_reason": finish_reason,
            "memory_source_complete": True,
            "memory_source_pending": True,
        },
    )
    assert not is_complete_ai_message(message)
    assert build_model_end_payload(message, {})["memory_source_complete"] is False
    assert finalize_memory_source(message)["memory_source_complete"] is False
    history = [
        {
            "id": "a",
            "role": "assistant",
            "content": message.content,
            "status": "complete",
            "builtin_property": {
                "finish_reason": finish_reason,
                "memory_source_complete": True,
                "source_timestamp": "2026-10-22T00:00:00+00:00",
            },
        }
    ]
    assert completed_history(history, "s") == []
