from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from ag_ui.core import CustomEvent, EventType
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.services.agent import memory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate


def test_full_cache_prunes_expired_entries_before_eviction(monkeypatch):
    monkeypatch.setattr(memory, "_policy_suppressed_until", {("expired",): 10.0, ("valid",): 30.0})
    monkeypatch.setattr(memory, "POLICY_CACHE_MAX_ENTRIES", 2)
    monkeypatch.setattr(memory.time, "monotonic", lambda: 20.0)
    memory._suppress_policy(("new",), 10)
    assert memory._policy_suppressed_until == {("valid",): 30.0, ("new",): 30.0}


def test_default_source_update_delegates_without_changing_payload():
    target = SimpleNamespace(_do_update_content=MagicMock())
    payload = {"property": {"builtin_property": {"memory_source_complete": False}}}
    BaseSessionWriter._do_update_memory_source(target, 9, payload, {})
    target._do_update_content.assert_called_once_with(content_id=9, payload=payload, headers={})


def test_legacy_user_event_without_identity_keeps_original_contract():
    client = MagicMock()
    writer = AGUISessionWriter("session", client, username="alice")
    writer.handle_user_input_saved(
        CustomEvent(type=EventType.CUSTOM, name="user_input_saved", value={"content": "Hi", "turn_id": "turn"})
    )
    assert client.api.create_chat_session_content.call_args.kwargs["json"]["property"] == {"turn_id": "turn"}


class RejectGate(QualityGate):
    def __call__(self, ctx):
        raise RuntimeError("synthetic gate failure")


class EventSpy(BaseCallbackHandler):
    def __init__(self):
        self.events = []

    def on_custom_event(self, name, data, **kwargs):
        self.events.append(name)


def test_rejected_disabled_memory_response_raises_original_error_without_finalization():
    spy = EventSpy()
    assembly = SimpleNamespace(
        get_choice_tools=lambda ctx: [],
        get_chat_prompt_variables=lambda ctx: {},
        get_chat_prompt_template=lambda ctx: ChatPromptTemplate.from_messages([("human", "Hi")]),
    )
    chain = _build_model_chain(
        llm=MockChatModel(responses=["Hi"]),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=RejectGate(),
        use_structured_response=False,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
    )
    ctx = ProcessorContext(
        state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0)
    )
    with pytest.raises(RuntimeError, match="synthetic gate failure"):
        chain.invoke(ctx, config={"callbacks": [spy]})
    assert spy.events == []
