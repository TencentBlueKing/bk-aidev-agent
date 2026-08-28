import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables.fallbacks import RunnableWithFallbacks
from langchain_openai import ChatOpenAI


def test_fallback_model_is_not_forwarded_to_openai_request(monkeypatch):
    def fake_get_request_payload(model, *args, **kwargs):
        return {
            "model": model.model_name,
            "fallback_model": model.fallback_model,
            "retry_strategy": model.retry_strategy,
        }

    monkeypatch.setattr(ChatOpenAI, "_get_request_payload", fake_get_request_payload)
    model = ChatModel.get_setup_instance(
        model="primary-model",
        fallback_model="fallback-model",
        retry_strategy="sdk",
    )

    assert isinstance(model, RunnableWithFallbacks)
    assert model.runnable._get_request_payload([]) == {"model": "primary-model"}
    assert model.fallbacks[0]._get_request_payload([]) == {"model": "fallback-model"}


@pytest.mark.parametrize("fallback_model", [None, "primary-model"])
def test_setup_returns_original_model_without_distinct_fallback(fallback_model):
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model=fallback_model)

    assert isinstance(model, ChatModel)


def test_generate_switches_to_fallback_model(monkeypatch):
    calls = []

    def fake_generate(model, *args, **kwargs):
        calls.append(model.model_name)
        if model.model_name == "primary-model":
            raise RuntimeError("primary unavailable")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="fallback"))])

    monkeypatch.setattr(ChatOpenAI, "_generate", fake_generate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    assert model.invoke([HumanMessage(content="hello")]).content == "fallback"
    assert calls == ["primary-model", "fallback-model"]


async def test_agenerate_switches_to_fallback_model(monkeypatch):
    calls = []

    async def fake_agenerate(model, *args, **kwargs):
        calls.append(model.model_name)
        if model.model_name == "primary-model":
            raise RuntimeError("primary unavailable")
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="fallback"))])

    monkeypatch.setattr(ChatOpenAI, "_agenerate", fake_agenerate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    response = await model.ainvoke([HumanMessage(content="hello")])
    assert response.content == "fallback"
    assert calls == ["primary-model", "fallback-model"]


@pytest.mark.parametrize("fail_after_output", [False, True])
def test_stream_only_falls_back_before_first_output(monkeypatch, fail_after_output):
    calls = []
    chunk = ChatGenerationChunk(message=AIMessageChunk(content="ok"))

    def fake_stream(model, *args, **kwargs):
        calls.append(model.model_name)
        if model.model_name == "primary-model" and fail_after_output:
            yield chunk
        if model.model_name == "primary-model":
            raise RuntimeError("primary unavailable")
        yield chunk

    monkeypatch.setattr(ChatOpenAI, "_stream", fake_stream)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    if fail_after_output:
        with pytest.raises(RuntimeError, match="primary unavailable"):
            list(model.stream([HumanMessage(content="hello")]))
        assert calls == ["primary-model"]
    else:
        assert "".join(item.content for item in model.stream([HumanMessage(content="hello")])) == "ok"
        assert calls == ["primary-model", "fallback-model"]


@pytest.mark.parametrize("fail_after_output", [False, True])
async def test_astream_only_falls_back_before_first_output(monkeypatch, fail_after_output):
    calls = []
    chunk = ChatGenerationChunk(message=AIMessageChunk(content="ok"))

    async def fake_astream(model, *args, **kwargs):
        calls.append(model.model_name)
        if model.model_name == "primary-model" and fail_after_output:
            yield chunk
        if model.model_name == "primary-model":
            raise RuntimeError("primary unavailable")
        yield chunk

    monkeypatch.setattr(ChatOpenAI, "_astream", fake_astream)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    if fail_after_output:
        with pytest.raises(RuntimeError, match="primary unavailable"):
            [item async for item in model.astream([HumanMessage(content="hello")])]
        assert calls == ["primary-model"]
    else:
        items = [item async for item in model.astream([HumanMessage(content="hello")])]
        assert "".join(item.content for item in items) == "ok"
        assert calls == ["primary-model", "fallback-model"]


async def test_astream_events_emit_fallback_chat_model_chunks(monkeypatch):
    async def fake_astream(model, *args, **kwargs):
        if model.model_name == "primary-model":
            raise RuntimeError("primary unavailable")
        yield ChatGenerationChunk(message=AIMessageChunk(content="fallback"))

    monkeypatch.setattr(ChatOpenAI, "_astream", fake_astream)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    events = [event async for event in model.astream_events([HumanMessage(content="hello")])]
    chunks = [event["data"]["chunk"].content for event in events if event["event"] == "on_chat_model_stream"]

    assert "".join(chunks) == "fallback"


def test_bind_tools_is_applied_to_primary_and_fallback():
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")
    tool = {"type": "function", "function": {"name": "ping", "parameters": {"type": "object"}}}

    bound = model.bind_tools([tool])

    assert isinstance(bound, RunnableWithFallbacks)
    assert bound.runnable.bound.model_name == "primary-model"
    assert bound.fallbacks[0].bound.model_name == "fallback-model"


def test_fallback_runnable_can_be_attached_to_chat_agent():
    from aidev_agent.services.agent.chat import ChatCompletionAgent

    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    agent = ChatCompletionAgent(chat_model=model)

    assert agent.chat_model is model


def test_agent_execute_updates_callbacks_for_primary_and_fallback(monkeypatch):
    from aidev_agent.pydantic_models import ExecuteKwargs
    from aidev_agent.services.agent.chat import ChatCompletionAgent

    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")
    callbacks = [BaseCallbackHandler()]
    agent = ChatCompletionAgent(chat_model=model, callbacks=callbacks, messages=[HumanMessage(content="hello")])
    monkeypatch.setattr(ChatCompletionAgent, "_execute", lambda *args: "ok")

    assert agent.execute(ExecuteKwargs()) == "ok"
    assert model.runnable.callbacks == callbacks
    assert model.fallbacks[0].callbacks == callbacks
