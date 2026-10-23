"""Custom completion paths keep accepted evidence and saved properties intact."""

from unittest.mock import MagicMock

import pytest
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.services.agent.memory import completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage

SOURCE = {
    "memory_source_complete": True,
    "source_text": "Canonical full answer",
    "source_timestamp": "2026-10-22T00:00:00+00:00",
}

DISPLAY_RECORD = {"role": "assistant", "status": "complete", "content": "Display body"}


class MetadataFreeGate(QualityGate):
    def __call__(self, ctx):
        ctx.response = ctx.response.model_copy(update={"response_metadata": {}})
        return ctx


class Events(BaseCallbackHandler):
    def __init__(self):
        self.names = []

    def on_custom_event(self, name, data, **kwargs):
        self.names.append(name)


@pytest.fixture
def metadata_free_chain():
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = []
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(content="Question")
    ]
    chain = _build_model_chain(
        llm=MockChatModel(responses=["Complete answer"]),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=MetadataFreeGate(),
        use_structured_response=False,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
        track_memory_source=True,
    )
    ctx = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )
    return chain, ctx


@pytest.mark.asyncio
async def test_async_gate_without_pending_preserves_answer_and_emits_no_acceptance(metadata_free_chain):
    chain, ctx = metadata_free_chain
    events = Events()
    result = await chain.ainvoke(ctx, config={"callbacks": [events]})
    assert result.response.content == "Complete answer"
    assert SessionPersistenceEventNames.MemorySourceFinalized.value not in events.names


@pytest.fixture
def writer_without_tool_metadata():
    client = MagicMock()
    writer = AGUISessionWriter("session", client, username="alice")
    writer._content_ids_by_message_id["answer"] = 1
    writer._assistant_message_properties["answer"] = {
        "retained": "old-property",
        "builtin_property": {"message_id": "answer", "retained_builtin": "old-builtin"},
    }
    writer._assistant_builtin_properties["answer"] = dict(SOURCE)
    return writer, client


def test_writer_without_tool_metadata_preserves_source_and_saved_attributes(writer_without_tool_metadata):
    writer, client = writer_without_tool_metadata
    incoming = {"new_property": "new-value", "builtin_property": {"message_id": "answer", "finish_reason": "stop"}}
    writer._do_update_memory_source(1, {"property": incoming}, {})
    kwargs = client.api.update_chat_session_content.call_args.kwargs
    assert kwargs["path_params"] == {"id": 1}
    assert kwargs["timeout"] == writer._MEMORY_SOURCE_UPDATE_TIMEOUT
    prop = kwargs["json"]["property"]
    assert prop["retained"] == "old-property" and prop["new_property"] == "new-value"
    assert prop["builtin_property"] == {
        "message_id": "answer",
        "retained_builtin": "old-builtin",
        "finish_reason": "stop",
        **SOURCE,
    }
    assert writer._assistant_message_properties["answer"] == prop
    history = [{**DISPLAY_RECORD, "builtin_property": prop["builtin_property"]}]
    assert completed_history(history, "session") == [
        {
            "message_id": "answer",
            "role": "assistant",
            "text": SOURCE["source_text"],
            "complete": True,
            "timestamp": SOURCE["source_timestamp"],
        }
    ]
