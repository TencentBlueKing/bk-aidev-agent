# -*- coding: utf-8 -*-
"""CrawCompletionAgent：消息装配 / 非流式 / 流式事件翻译 / 身份 fail-closed（后端打桩，无真实 HTTP）。"""

import json

import pytest

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw import CrawCompletionAgent, CrawIdentityError, OpenClawBackend
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


class _StubResourceManager:
    """打桩 resource_manager：按预设返回 / 抛错。"""

    def __init__(self, token="fake-token-xyz", error=None):
        self.token = token
        self.error = error

    def resolve_access_token(self, username):
        if self.error is not None:
            raise self.error
        return self.token


_DEFAULT_RM = object()


def _build_agent(backend, session_context=None, resource_manager=_DEFAULT_RM, agent_cls=CrawCompletionAgent):
    ctx = AgentBuildContext(
        agent_code="demo-agent",
        agent_type=AgentType.CHAT,
        resource_manager=_StubResourceManager() if resource_manager is _DEFAULT_RM else resource_manager,
        session_code="sess-1",
        username="demo-user",
        session_context_data=session_context or [{"role": "user", "content": "hi"}],
    )
    return agent_cls(backend=backend).build(ctx)


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
        assert types == [
            "RUN_STARTED",
            "TEXT_MESSAGE_START",
            "TEXT_MESSAGE_CONTENT",
            "TEXT_MESSAGE_CONTENT",
            "TEXT_MESSAGE_END",
            "RUN_FINISHED",
        ]
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
        lines = ["data: " + json.dumps({"choices": []}), "data: [DONE]", 'data: {"x":1}']
        assert len(list(OpenClawBackend.iter_sse_chunks(iter(lines)))) == 1


class TestIdentityFailClosed:
    """身份装配 fail-closed：绝不降级为无身份请求落入默认路由。"""

    def test_identity_carries_resolved_token(self):
        agent = _build_agent(_StubBackend(), resource_manager=_StubResourceManager(token="fake-token-xyz"))
        assert agent.identity.username == "demo-user"
        assert agent.identity.access_token == "fake-token-xyz"

    def test_empty_token_raises(self):
        with pytest.raises(CrawIdentityError):
            _build_agent(_StubBackend(), resource_manager=_StubResourceManager(token=""))

    def test_resolve_error_raises(self):
        with pytest.raises(CrawIdentityError):
            _build_agent(_StubBackend(), resource_manager=_StubResourceManager(error=RuntimeError("rm down")))

    def test_missing_resource_manager_raises(self):
        # 有 username 但没有 resource_manager，同样无法取 token → fail-closed
        with pytest.raises(CrawIdentityError):
            _build_agent(_StubBackend(), resource_manager=None)

    def test_anonymous_requires_opt_in(self):
        ctx = AgentBuildContext(
            agent_code="demo-agent",
            agent_type=AgentType.CHAT,
            resource_manager=None,
            session_code="sess-1",
            username="",
            session_context_data=[{"role": "user", "content": "hi"}],
        )
        with pytest.raises(CrawIdentityError):
            CrawCompletionAgent(backend=_StubBackend()).build(ctx)

        class _AnonymousAgent(CrawCompletionAgent):
            allow_anonymous = True

        agent = _AnonymousAgent(backend=_StubBackend()).build(ctx)
        assert agent.identity.access_token == ""


class TestThreadIdConsistency:
    """AG-UI 事件 thread_id 与流式队列 / 取消键统一为 session_code。"""

    def test_thread_id_follows_session_code(self):
        agent = _build_agent(_StubBackend())
        assert agent.thread_id == "sess-1"

    def test_stream_events_use_session_code_as_thread_id(self):
        chunks = [{"choices": [{"delta": {"content": "hi"}}]}]
        events = []
        agent = _build_agent(_StubBackend(chunks=chunks))
        agent.event_handler = events.append
        list(agent._run_stream())
        thread_ids = {e.thread_id for e in events if hasattr(e, "thread_id")}
        # RUN_STARTED / RUN_FINISHED 与队列键（session_code）同一套会话标识
        assert thread_ids == {"sess-1"}
