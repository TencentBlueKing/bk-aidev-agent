"""An early host snapshot must fail closed when finalization cannot persist."""

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
from aidev_agent.services.agent.memory import completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool


class CaptureBeforeStamp(BaseCallbackHandler):
    def __init__(self, writer):
        self.writer = writer

    def on_llm_end(self, response, **kwargs):
        self.writer(
            CustomEvent(
                type=EventType.CUSTOM,
                name=SessionPersistenceEventNames.ChatModelEnd.value,
                value=build_model_end_payload(copy.deepcopy(response.generations[0][0].message), {}),
            )
        )

    def on_custom_event(self, name, data, **kwargs):
        if name == SessionPersistenceEventNames.MemorySourceFinalized.value:
            self.writer(CustomEvent(type=EventType.CUSTOM, name=name, value=copy.deepcopy(data)))


class RejectDraft(QualityGate):
    def _judge_response_completion(self, *args, **kwargs):
        return False


def callback_writer(failed_update):
    rows, raw_copies = [], []
    client = MagicMock()

    def create(*, json, headers):
        row = copy.deepcopy(json)
        row["id"] = len(rows) + 1
        rows.append(row)
        raw_copies.append(copy.deepcopy(row))
        return {"data": copy.deepcopy(row)}

    client.api.create_chat_session_content.side_effect = create

    def update(*, path_params, json, headers, timeout=None):
        rows[path_params["id"] - 1].update(copy.deepcopy(json))

    client.api.update_chat_session_content.side_effect = ConnectionError("unavailable") if failed_update else update
    writer = AGUISessionWriter("session", client, username="alice")
    return writer, rows, raw_copies


def callback_chain(raw, structured, quality_gate):
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = [
        StructuredTool.from_function(lambda q: q, name="lookup", description="Lookup")
    ]
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(id="u", content="Answer?")
    ]
    chain = _build_model_chain(
        llm=MockChatModel(responses=[raw]),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=quality_gate,
        use_structured_response=structured,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
    )
    context = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )
    return chain, context


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("structured", [False, True])
async def test_failed_reconciliation_cannot_qualify_early_callback_copy(structured, async_mode):
    writer, rows, _ = callback_writer(True)
    raw = (
        '{"action":"Final Answer","action_input":"Draft rejected by quality gate"}'
        if structured
        else "Draft rejected by quality gate"
    )
    chain, context = callback_chain(raw, structured, RejectDraft())
    with pytest.raises(RecoveryRetryError):
        config = {"callbacks": [CaptureBeforeStamp(writer)]}
        if async_mode:
            await chain.ainvoke(context, config=config)
        else:
            chain.invoke(context, config=config)
    assert len(rows) == 1
    history = [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows]
    assert completed_history(history, "session") == [], history


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("failed_update", [False, True])
async def test_accepted_callback_copy_keeps_canonical_source_only_after_success(structured, async_mode, failed_update):
    writer, rows, raw_copies = callback_writer(failed_update)
    public = "Accepted answer"
    raw = '{"action":"Final Answer","action_input":"Accepted answer"}' if structured else public
    chain, ctx = callback_chain(raw, structured, QualityGate(enable_judge_response=False))
    config = {"callbacks": [CaptureBeforeStamp(writer)]}
    result = await chain.ainvoke(ctx, config=config) if async_mode else chain.invoke(ctx, config=config)
    assert result.response.content == public
    assert raw_copies[0]["property"]["builtin_property"]["memory_source_complete"] is False
    assert rows[0]["content"] == raw
    history = completed_history(
        [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows], "session"
    )
    expected = (
        []
        if failed_update
        else [
            {
                "message_id": result.response.id,
                "role": "assistant",
                "text": public,
                "complete": True,
                "timestamp": result.response.response_metadata["source_timestamp"],
            }
        ]
    )
    assert history == expected
