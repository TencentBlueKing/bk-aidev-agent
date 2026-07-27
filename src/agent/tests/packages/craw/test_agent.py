# -*- coding: utf-8 -*-
"""CrawCompletionAgent：消息装配 / 非流式 / 流式事件翻译 / 身份 fail-closed / 取消中断（后端打桩，无真实 HTTP）。"""

import json

import pytest

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw import (
    CrawCompletionAgent,
    CrawIdentityError,
    CrawStreamProtocolError,
    CrawUpstreamError,
    OpenClawBackend,
)
from aidev_agent.packages.craw.agent import build_openai_messages
from aidev_agent.services.agent.registry import AgentBuildContext
from aidev_agent.utils.event import RunId


class _FakeStream:
    """打桩流句柄：与 ``CrawChatStream`` 同语义（close 后迭代静默结束）。"""

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.closed = False
        self._finished = False

    @property
    def interrupted(self):
        return self.closed and not self._finished

    def close(self):
        self.closed = True

    def __iter__(self):
        for chunk in self.chunks:
            if self.closed:
                return
            yield chunk
        self._finished = True


class _StubBackend(OpenClawBackend):
    """打桩后端：记录调用参数，回放预置的 chunk / 响应。"""

    def __init__(self, chunks=None, body=None):
        super().__init__(api_url="http://stub", api_key="stub-key")
        self.chunks = chunks or []
        self.body = body or {}
        self.calls = []
        self.streams = []

    def open_chat_stream(self, messages, identity=None, session_code=None):
        self.calls.append({"messages": messages, "identity": identity, "session_code": session_code})
        stream = _FakeStream(self.chunks)
        self.streams.append(stream)
        return stream

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


def _build_agent(
    backend,
    session_context=None,
    resource_manager=_DEFAULT_RM,
    agent_cls=CrawCompletionAgent,
    session_code="sess-1",
):
    ctx = AgentBuildContext(
        agent_code="demo-agent",
        agent_type=AgentType.CHAT,
        resource_manager=_StubResourceManager() if resource_manager is _DEFAULT_RM else resource_manager,
        session_code=session_code,
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
            def open_chat_stream(self, messages, identity=None, session_code=None):
                raise RuntimeError("boom")

        events = []
        agent = _build_agent(_BoomBackend())
        agent.event_handler = events.append
        payload = list(agent._run_stream())
        assert any(e.type.value == "RUN_ERROR" for e in events)
        assert any("RUN_FINISHED" in line for line in payload if isinstance(line, str))

    def test_iter_sse_chunks_stops_at_done(self):
        lines = ["data: " + json.dumps({"choices": []}), "data: [DONE]", 'data: {"x":1}']
        assert len(list(OpenClawBackend.iter_sse_chunks(iter(lines)))) == 1


class TestRunErrorSanitized:
    """RUN_ERROR 只给脱敏消息：上游响应详情 / 异常细节留服务端日志，不出客户端。"""

    def _run_and_get_error(self, backend):
        events = []
        agent = _build_agent(backend)
        agent.event_handler = events.append
        list(agent._run_stream())
        errors = [e for e in events if e.type.value == "RUN_ERROR"]
        assert len(errors) == 1
        return errors[0].message

    def test_upstream_error_detail_not_in_client_message(self):
        class _UpstreamBoom(_StubBackend):
            def open_chat_stream(self, messages, identity=None, session_code=None):
                raise CrawUpstreamError("openclaw", 502, "<html>internal error page secret-detail</html>")

        message = self._run_and_get_error(_UpstreamBoom())
        assert message == "craw backend openclaw upstream 502"
        assert "secret-detail" not in message

    def test_stream_protocol_error_detail_not_in_client_message(self):
        class _ProtocolBoom(_StubBackend):
            def open_chat_stream(self, messages, identity=None, session_code=None):
                raise CrawStreamProtocolError("openclaw", "SSE data 行不是合法 JSON: 'secret-fragment'")

        message = self._run_and_get_error(_ProtocolBoom())
        assert "secret-fragment" not in message

    def test_generic_error_only_exposes_type_name(self):
        class _GenericBoom(_StubBackend):
            def open_chat_stream(self, messages, identity=None, session_code=None):
                raise RuntimeError("secret internal state dump")

        message = self._run_and_get_error(_GenericBoom())
        assert "secret" not in message
        assert "RuntimeError" in message


class TestStopInterruptsStream:
    """stop() 主动关闭本进程活跃流：阻塞中的上游读立即中断，走取消收尾。"""

    def test_mid_stream_close_ends_with_cancelled_finish(self):
        chunks = [{"choices": [{"delta": {"content": piece}}]} for piece in ("a", "b", "c")]
        events = []
        agent = _build_agent(_StubBackend(chunks=chunks), session_code="sess-close-mid")
        agent.event_handler = events.append
        gen = agent._run_stream()
        # 消费到首个文本增量后模拟 stop：关闭该会话的活跃流句柄
        while not any(e.type.value == "TEXT_MESSAGE_CONTENT" for e in events):
            next(gen)
        CrawCompletionAgent._close_streams("sess-close-mid")
        list(gen)
        types = [e.type.value for e in events]
        finished = [e for e in events if e.type.value == "RUN_FINISHED"]
        assert types[-2:] == ["TEXT_MESSAGE_END", "RUN_FINISHED"]
        assert finished[-1].run_id == RunId.CANCELLED
        assert "RUN_ERROR" not in types  # 取消不是错误

    def test_stop_closes_tracked_stream_and_sets_cancel(self, monkeypatch):
        from aidev_agent.packages.craw import agent as agent_module

        cancelled = []
        monkeypatch.setattr(
            agent_module.GeneratorStreamingHelper, "cancel", classmethod(lambda cls, key: cancelled.append(key))
        )
        stream = _FakeStream([])
        CrawCompletionAgent._track_stream("sess-stop-1", stream)
        try:
            agent = _build_agent(_StubBackend(), session_code="sess-stop-1")
            agent.stop()
        finally:
            CrawCompletionAgent._untrack_stream("sess-stop-1", stream)
        assert cancelled == ["sess-stop-1"]
        assert stream.closed is True

    def test_stream_untracked_after_run(self):
        chunks = [{"choices": [{"delta": {"content": "x"}}]}]
        agent = _build_agent(_StubBackend(chunks=chunks), session_code="sess-untrack")
        list(agent._run_stream())
        assert "sess-untrack" not in CrawCompletionAgent._active_streams


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


class TestHostConsumedContract:
    """宿主（aidev_bkplugin chat 视图）消费面契约：chat_history 与 ChatCompletionAgent 对齐。"""

    def test_chat_history_built_from_session_context(self):
        context = [{"role": "user", "content": "hi"}, {"role": "ai", "content": "ok"}]
        agent = _build_agent(_StubBackend(), session_context=context)
        assert agent.chat_history == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "ok"},
        ]

    def test_chat_history_empty_for_empty_context(self):
        agent = _build_agent(_StubBackend(), session_context=[{"role": "activity", "content": "x"}])
        assert agent.chat_history == []
