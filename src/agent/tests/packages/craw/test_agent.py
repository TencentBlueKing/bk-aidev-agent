# -*- coding: utf-8 -*-
"""CrawCompletionAgent：消息装配 / 非流式 / 流式事件翻译（后端打桩，无真实 HTTP）。"""

import json

import pytest

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw import CrawCompletionAgent, OpenClawBackend
from aidev_agent.packages.craw.agent import build_openai_messages
from aidev_agent.services.agent.registry import AgentBuildContext


class _StubBackend(OpenClawBackend):
    """打桩后端：记录调用参数，回放预置的 chunk / 响应。"""

    def __init__(self, chunks=None, body=None):
        super().__init__(api_url="http://stub", api_key="stub-key")
        self.chunks = chunks or []
        self.body = body or {}
        self.calls = []

    def chat_completions_stream(self, messages, identity=None, session_code=None):
        self.calls.append({"messages": messages, "identity": identity, "session_code": session_code})
        yield from self.chunks

    def chat_completions(self, messages, identity=None, session_code=None):
        self.calls.append({"messages": messages, "identity": identity, "session_code": session_code})
        return self.body


def _build_agent(backend, session_context=None):
    ctx = AgentBuildContext(
        agent_code="demo-agent",
        agent_type=AgentType.CHAT,
        resource_manager=None,
        session_code="sess-1",
        username="demo-user",
        session_context_data=session_context or [{"role": "user", "content": "hi"}],
    )
    return CrawCompletionAgent(backend=backend).build(ctx)


@pytest.mark.parametrize(
    "context, expected",
    [
        ([{"role": "user", "content": "hi"}], [{"role": "user", "content": "hi"}]),
        ([{"role": "ai", "content": "ok"}], [{"role": "assistant", "content": "ok"}]),
        ([{"role": "activity", "content": "x"}], []),
        (
            [{"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "image", "url": "u"}]}],
            [{"role": "user", "content": "a"}],
        ),
    ],
)
def test_build_openai_messages(context, expected):
    assert build_openai_messages(context) == expected


class TestCrawCompletionAgent:
    def test_run_sync_shape(self):
        backend = _StubBackend(body={"choices": [{"message": {"content": "pong"}}], "model": "openclaw", "id": "x"})
        result = _build_agent(backend).execute()
        assert result["choices"][0]["delta"]["content"] == "pong"
        assert backend.calls[0]["session_code"] == "sess-1"
        assert backend.calls[0]["identity"].username == "demo-user"

    def test_stream_translates_to_ag_ui_events(self):
        chunks = [{"choices": [{"delta": {"content": piece}}]} for piece in ("he", "llo")]
        events = []
        agent = _build_agent(_StubBackend(chunks=chunks))
        agent.event_handler = events.append
        list(agent._run_stream())
        types = [event.type.value for event in events]
        assert types == ["RUN_STARTED", "TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END", "RUN_FINISHED"]
        assert "".join(e.delta for e in events if e.type.value == "TEXT_MESSAGE_CONTENT") == "hello"

    def test_stream_upstream_error_emits_run_error(self):
        class _BoomBackend(_StubBackend):
            def chat_completions_stream(self, messages, identity=None, session_code=None):
                raise RuntimeError("boom")
                yield  # pragma: no cover

        events = []
        agent = _build_agent(_BoomBackend())
        agent.event_handler = events.append
        payload = list(agent._run_stream())
        assert any(e.type.value == "RUN_ERROR" for e in events)
        assert any("RUN_FINISHED" in line for line in payload if isinstance(line, str))

    def test_iter_sse_chunks_stops_at_done(self):
        lines = ["data: " + json.dumps({"choices": []}), "data: [DONE]", "data: {\"x\":1}"]
        assert len(list(OpenClawBackend.iter_sse_chunks(iter(lines)))) == 1
