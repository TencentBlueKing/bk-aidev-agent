import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.utils.tracing import CLIENT_SPAN_KIND
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI


def _chunk(text: str) -> ChatGenerationChunk:
    return ChatGenerationChunk(message=AIMessageChunk(content=text))


def _install_span_recorder(monkeypatch):
    calls: list[tuple[str, dict, MagicMock]] = []

    @contextmanager
    def fake_recording_span(name, **kwargs):
        span = MagicMock()
        calls.append((name, kwargs, span))
        yield span

    monkeypatch.setattr(
        "aidev_agent.packages.langchain_core.models.llm_gateway.recording_span",
        fake_recording_span,
    )
    return calls


@pytest.mark.parametrize("texts", [["a", "b", "c"], ["only"]])
def test_stream_records_first_token_and_read_stream(monkeypatch, texts):
    calls = _install_span_recorder(monkeypatch)
    monkeypatch.setattr(ChatOpenAI, "_stream", lambda self, *args, **kwargs: iter(_chunk(t) for t in texts))
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")

    assert [chunk.message.content for chunk in model._stream([])] == texts
    assert [name for name, _, _ in calls] == ["llm.first_token", "llm.read_stream"]
    for name, kwargs, _ in calls:
        assert kwargs["kind"] is CLIENT_SPAN_KIND
        assert kwargs["use_global_tracer"] is True
        assert kwargs["attributes"]["gen_ai.request.model"] == "aidev-chat-auto"
    calls[1][2].set_attribute.assert_called_with("llm.stream.remaining_chunks", len(texts) - 1)


def test_stream_empty_only_records_first_token(monkeypatch):
    calls = _install_span_recorder(monkeypatch)
    monkeypatch.setattr(ChatOpenAI, "_stream", lambda self, *args, **kwargs: iter(()))
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")

    assert list(model._stream([])) == []
    assert [name for name, _, _ in calls] == ["llm.first_token"]
    calls[0][2].set_attribute.assert_called_with("llm.stream.empty", True)


def test_astream_records_first_token_and_read_stream(monkeypatch):
    calls = _install_span_recorder(monkeypatch)

    async def fake_astream(self, *args, **kwargs):
        for text in ("x", "y"):
            yield _chunk(text)

    async def collect():
        return [chunk.message.content async for chunk in model._astream([])]

    monkeypatch.setattr(ChatOpenAI, "_astream", fake_astream)
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")

    assert asyncio.run(collect()) == ["x", "y"]
    assert [name for name, _, _ in calls] == ["llm.first_token", "llm.read_stream"]
    assert calls[0][1]["use_global_tracer"] is True
    calls[1][2].set_attribute.assert_called_with("llm.stream.remaining_chunks", 1)
