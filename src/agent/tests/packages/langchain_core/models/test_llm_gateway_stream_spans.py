import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel, _served_model_var
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

    # 未带 finish_reason 的流会在尾部补一个内容为空的合成 chunk，此处只看内容 chunk
    contents = [chunk.message.content for chunk in model._stream([]) if chunk.message.content]
    assert contents == texts
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
        return [chunk.message.content async for chunk in model._astream([]) if chunk.message.content]

    monkeypatch.setattr(ChatOpenAI, "_astream", fake_astream)
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")

    assert asyncio.run(collect()) == ["x", "y"]
    assert [name for name, _, _ in calls] == ["llm.first_token", "llm.read_stream"]
    assert calls[0][1]["use_global_tracer"] is True
    calls[1][2].set_attribute.assert_called_with("llm.stream.remaining_chunks", 1)


def _first_chunk(generator):
    return next(iter(generator))


@pytest.mark.parametrize("texts", [["a", "b", "c"], ["only"]])
def test_stream_first_chunk_carries_time_to_first_chunk(monkeypatch, texts):
    monkeypatch.setattr(ChatOpenAI, "_stream", lambda self, *args, **kwargs: iter(_chunk(t) for t in texts))
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")

    ttfc = _first_chunk(model._stream([])).generation_info["time_to_first_chunk"]
    assert isinstance(ttfc, float)
    assert ttfc >= 0


@pytest.mark.parametrize("texts", [["x", "y"], ["only"]])
def test_astream_first_chunk_carries_time_to_first_chunk(monkeypatch, texts):
    async def fake_astream(self, *args, **kwargs):
        for text in texts:
            yield _chunk(text)

    monkeypatch.setattr(ChatOpenAI, "_astream", fake_astream)
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")

    async def collect_first():
        gen = model._astream([])
        first = await gen.__anext__()
        return first.generation_info["time_to_first_chunk"]

    ttfc = asyncio.run(collect_first())
    assert isinstance(ttfc, float)
    assert ttfc >= 0


@pytest.mark.parametrize(
    "chunk",
    [
        {"id": "chatcmpl-1", "choices": [{"delta": {"content": "a"}, "finish_reason": None}]},
        {"id": "chatcmpl-2", "choices": []},
    ],
)
def test_convert_chunk_captures_provider_id(chunk):
    """provider 外层 chunk id 捞回 generation_info；choices 为空的 usage-only chunk 同样携带"""
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")

    generation_chunk = model._convert_chunk_to_generation_chunk(chunk, AIMessageChunk, None)

    assert generation_chunk is not None
    assert generation_chunk.generation_info["id"] == chunk["id"]


def _gateway_chunk(text, model="qwen3"):
    """构造一条与网关流式响应等价的原始 chunk（外层带 model，choices 内无 finish_reason）。"""
    return {"id": "chatcmpl-1", "model": model, "choices": [{"delta": {"content": text}, "finish_reason": None}]}


def _finish_chunk(reason="stop"):
    return {"id": "chatcmpl-1", "model": "qwen3", "choices": [{"delta": {}, "finish_reason": reason}]}


@pytest.mark.parametrize("texts", [["a", "b", "c"], ["only"]])
def test_stream_synthesizes_stop_tail_chunk(monkeypatch, texts):
    """网关流式响应不带 finish_reason：正常读完后补 1 个 stop 尾 chunk，model_name 为单一值不拼接"""
    monkeypatch.setattr(ChatOpenAI, "_stream", lambda self, *args, **kwargs: iter(_chunk(t) for t in texts))
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")
    model._convert_chunk_to_generation_chunk(_gateway_chunk("a"), AIMessageChunk, None)

    chunks = list(model._stream([]))

    assert [c.message.content for c in chunks] == [*texts, ""]
    assert chunks[-1].generation_info == {"finish_reason": "stop", "model_name": "qwen3"}
    assert chunks[-1].message.chunk_position == "last"


@pytest.mark.parametrize(
    "chunks, expected",
    [
        ([_finish_chunk()], ["a"]),
        ([_gateway_chunk("a"), _gateway_chunk("b"), _finish_chunk("length")], ["a", "b", "c"]),
    ],
)
def test_stream_skips_tail_chunk_when_finish_reason_present(monkeypatch, chunks, expected):
    """流内已带 finish_reason（含首 chunk 即带）时不合成尾 chunk"""
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")
    converted = [model._convert_chunk_to_generation_chunk(item, AIMessageChunk, None) for item in chunks]
    for text, item in zip("abc", converted):
        item.message.content = text
    monkeypatch.setattr(ChatOpenAI, "_stream", lambda self, *args, **kwargs: iter(converted))

    assert [c.message.content for c in model._stream([])] == expected


def test_stream_without_served_model_omits_model_name(monkeypatch):
    """未捕获到 provider 模型名时合成尾 chunk 只带 finish_reason"""
    monkeypatch.setattr(ChatOpenAI, "_stream", lambda self, *args, **kwargs: iter([_chunk("a")]))
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")
    _served_model_var.set(None)

    tail = list(model._stream([]))[-1]

    assert tail.generation_info == {"finish_reason": "stop"}


@pytest.mark.parametrize("texts", [["x", "y"], ["only"]])
def test_astream_synthesizes_stop_tail_chunk(monkeypatch, texts):
    """异步流式与同步路径对称：不带 finish_reason 的流补 1 个 stop 尾 chunk"""

    async def fake_astream(self, *args, **kwargs):
        for text in texts:
            yield _chunk(text)

    async def collect():
        return [chunk async for chunk in model._astream([])]

    monkeypatch.setattr(ChatOpenAI, "_astream", fake_astream)
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")
    model._convert_chunk_to_generation_chunk(_gateway_chunk("a"), AIMessageChunk, None)

    chunks = asyncio.run(collect())

    assert [c.message.content for c in chunks] == [*texts, ""]
    assert chunks[-1].generation_info == {"finish_reason": "stop", "model_name": "qwen3"}


def test_astream_without_served_model_omits_model_name(monkeypatch):
    """异步路径未捕获 served 模型名时合成尾 chunk 只带 finish_reason"""

    async def fake_astream(self, *args, **kwargs):
        yield _chunk("x")

    async def collect():
        return [chunk async for chunk in model._astream([])]

    monkeypatch.setattr(ChatOpenAI, "_astream", fake_astream)
    model = ChatModel.get_setup_instance(model="aidev-chat-auto", base_url="https://example.com/v1")
    _served_model_var.set(None)

    tail = asyncio.run(collect())[-1]

    assert tail.generation_info == {"finish_reason": "stop"}
