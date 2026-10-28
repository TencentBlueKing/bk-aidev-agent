import json
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.graphs.react.memory_middleware import PersonalMemoryPromptMiddleware
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.pydantic_models import AgentExecutorKwargs, SecuritySettings
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate


@pytest.fixture
def prepared(runtime):
    runtime.manager.memory_tool.return_value = {
        "hits": [
            {"memory_id": "used", "text": "Use Python", "score": 0.03},
            {"memory_id": "unused", "text": "Prefer tea", "score": 0.02},
        ]
    }
    state = {"messages": [HumanMessage(content="How should I write this?", id="user-1")]}
    state.update(runtime.prepare(state, {}))
    return state


def test_prefetched_hit_is_only_renewed_when_used(runtime, prepared):
    answer = AIMessage(content="Use Python", id="answer", additional_kwargs={"personal_memory_references": ["used"]})
    prepared["messages"].append(answer)
    runtime.complete(prepared, {})
    assert runtime.manager.complete_memory_round.call_args.args[0]["memory_ids"] == ["used"]
    assert runtime.manager.memory_tool.call_args.args[0]["context"]["messages"] == []
    assert runtime.manager.memory_tool.call_args.kwargs["timeout"] == 2


def test_unused_prefetched_hits_do_not_renew(runtime, prepared):
    runtime.reference_model.invoke.return_value = AIMessage(content=json.dumps({"memory_ids": []}))
    prepared["messages"].append(AIMessage(content="Hello", id="answer"))
    runtime.complete(prepared, {})
    assert runtime.manager.complete_memory_round.call_args.args[0]["memory_ids"] == []


@pytest.mark.parametrize("field,value", [("username", "bob"), ("session_id", "other"), ("tenant_id", "other")])
def test_prefetch_is_never_reused_in_another_scope(runtime, prepared, field, value):
    provider = runtime.context_provider
    runtime.context_provider = lambda config: {**provider(config), field: value}
    assert runtime.prepared_hits(prepared, {}) == []


def test_prefetch_is_not_reused_after_input_changes(runtime, prepared):
    prepared["messages"] = [HumanMessage(content="A different question", id="user-1")]
    assert runtime.prepared_hits(prepared, {}) == []


@pytest.mark.parametrize("failure", ["disabled", "exception"])
def test_prefetch_failure_replaces_previous_round_state(runtime, prepared, failure):
    runtime.best_effort = True
    if failure == "disabled":
        runtime.policy["enabled"] = False
    else:
        runtime.manager.memory_tool.side_effect = TimeoutError("search")
    prepared.update(runtime.prepare(prepared, {}))
    assert runtime.prepared_hits(prepared, {}) == []


@pytest.mark.parametrize("length,count,chars", [(20, 3, 60), (2200, 2, 4000)])
def test_prefetch_limits_content_and_rejects_nonpositive_scores(runtime, prepared, length, count, chars):
    runtime.manager.memory_tool.return_value = {
        "hits": [
            {"memory_id": "bad", "text": "unrelated", "score": 0},
            *[{"memory_id": str(i), "text": "x" * length, "score": 0.01} for i in range(5)],
        ]
    }
    result = runtime.prepare(prepared, {})["personal_memory"]["hits"]
    assert len(result) == count and sum(len(hit["text"]) for hit in result) == chars
    assert all(hit["memory_id"] != "bad" for hit in result)


def test_memory_text_is_template_data_not_template_source(runtime, prepared):
    prepared["personal_memory"]["hits"][0]["text"] = "Keep {{ 7 * 7 }} literally"
    ctx = ProcessorContext(state=prepared, config={})
    PersonalMemoryPromptMiddleware(runtime)(ctx, MagicMock())
    prompt = ChatPromptTemplate.from_messages([("system", ctx.prompt_slots.system)], template_format="jinja2")
    rendered = prompt.format_messages(**ctx.variables)[0].content
    assert "{{ 7 * 7 }}" in rendered and "Keep 49" not in rendered


class PromptSpy(BaseCallbackHandler):
    def __init__(self):
        self.messages = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.messages.extend(message.content for batch in messages for message in batch)


@pytest.mark.parametrize("business_prompt", [False, True], ids=["default_system", "business_system"])
def test_default_graph_injects_memory_into_real_model_prompt_once(runtime, prepared, business_prompt):
    spy = PromptSpy()
    model = MockChatModel(responses=["Use Python"], callbacks=[spy])
    runtime.reference_model.invoke.return_value = AIMessage(content='{"memory_ids": ["used"]}')
    runtime.manager.memory_tool.reset_mock()
    builder = ReActAgentBuilder().set_llm(model).enable_personal_memory(runtime)
    builder.set_bkai_options(AgentExecutorKwargs(security_settings=SecuritySettings()))
    graph, config = builder.build()
    messages = [HumanMessage(content="How should I write this?", id="user-1")]
    if business_prompt:
        messages.insert(0, SystemMessage(content="You are a concise coding assistant."))
    graph.invoke({"messages": messages}, config)
    assert any("个人记忆参考" in text and "Use Python" in text for text in spy.messages)
    if business_prompt:
        assert any("You are a concise coding assistant." in text for text in spy.messages)
    assert runtime.manager.memory_tool.call_count == 1
    assert runtime.manager.complete_memory_round.call_args.args[0]["memory_ids"] == ["used"]
