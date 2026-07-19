import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI


def test_generate_switches_to_fallback_model(monkeypatch):
    calls = []
    expected = object()

    def fake_generate(model, *args, **kwargs):
        calls.append(model.model_name)
        if model.model_name == "primary-model":
            raise RuntimeError("primary unavailable")
        return expected

    monkeypatch.setattr(ChatOpenAI, "_generate", fake_generate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    assert model._generate([]) is expected
    assert calls == ["primary-model", "fallback-model"]


async def test_agenerate_switches_to_fallback_model(monkeypatch):
    calls = []
    expected = object()

    async def fake_agenerate(model, *args, **kwargs):
        calls.append(model.model_name)
        if model.model_name == "primary-model":
            raise RuntimeError("primary unavailable")
        return expected

    monkeypatch.setattr(ChatOpenAI, "_agenerate", fake_agenerate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    assert await model._agenerate([]) is expected
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
            list(model._stream([]))
        assert calls == ["primary-model"]
    else:
        assert list(model._stream([])) == [chunk]
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
            [item async for item in model._astream([])]
        assert calls == ["primary-model"]
    else:
        assert [item async for item in model._astream([])] == [chunk]
        assert calls == ["primary-model", "fallback-model"]
