# -*- coding: utf-8 -*-
"""craw 后端：env 装配链 / 请求头 / 身份隔离。"""

import httpx
import pytest

from aidev_agent.packages.craw import (
    CrawIdentity,
    CrawStreamProtocolError,
    CrawUpstreamError,
    CrawUpstreamRunError,
    HermesBackend,
    OpenClawBackend,
    get_backend,
)
from aidev_agent.packages.craw.base import IDENTITY_HEADER


class TestCrawIdentity:
    def test_identity_id_hash_and_repr_no_token(self):
        identity = CrawIdentity(username="demo-user", access_token="fake-token-xyz")
        assert len(identity.identity_id) == 16
        assert "fake-token-xyz" not in repr(identity)

    @pytest.mark.parametrize(
        "username, token, expect_empty",
        [("", "", True), ("demo-user", "", False)],
    )
    def test_identity_id_fallback(self, username, token, expect_empty):
        identity = CrawIdentity(username=username, access_token=token)
        assert (identity.identity_id == "") is expect_empty


class TestBackendEnvAssembly:
    @pytest.mark.parametrize(
        "backend_cls, unified, legacy, expected_when_both",
        [
            (
                OpenClawBackend,
                {"BKAI_CRAW_API_URL": "http://u:1/"},
                {"BKAI_OPENCLAW_GATEWAY_URL": "http://l:2"},
                "http://u:1",
            ),
            (HermesBackend, {}, {"BKAI_HERMES_API_URL": "http://l:3/"}, "http://l:3"),
        ],
    )
    def test_api_url_precedence(self, monkeypatch, backend_cls, unified, legacy, expected_when_both):
        for key, value in {**unified, **legacy}.items():
            monkeypatch.setenv(key, value)
        assert backend_cls().api_url == expected_when_both

    def test_defaults_without_env(self, monkeypatch):
        for key in ("BKAI_CRAW_API_URL", "BKAI_OPENCLAW_GATEWAY_URL", "OPENCLAW_GATEWAY_TOKEN"):
            monkeypatch.delenv(key, raising=False)
        backend = OpenClawBackend()
        assert backend.api_url == "http://127.0.0.1:18789"
        assert backend.model == "openclaw"
        assert backend.timeout == 300.0

    def test_get_backend_by_env(self, monkeypatch):
        monkeypatch.setenv("BKAI_CRAW_BACKEND", "hermes")
        assert isinstance(get_backend(), HermesBackend)

    def test_get_backend_unknown_raises(self):
        with pytest.raises(RuntimeError):
            get_backend("no-such-kernel")


class TestBackendHeaders:
    def test_openclaw_headers_bearer_and_identity(self):
        backend = OpenClawBackend(api_url="http://x", api_key="gw-token")
        identity = CrawIdentity(username="demo-user", access_token="fake-token-xyz")
        headers = backend.build_headers(identity=identity, session_code="sess-1")
        assert headers["Authorization"] == "Bearer gw-token"
        assert headers[IDENTITY_HEADER] == "fake-token-xyz"

    @pytest.mark.parametrize(
        "api_key, expect_session_key",
        [("srv-key", True), ("", False)],
    )
    def test_hermes_session_headers(self, api_key, expect_session_key):
        backend = HermesBackend(api_url="http://x", api_key=api_key)
        identity = CrawIdentity(username="demo-user")
        headers = backend.build_headers(identity=identity, session_code="sess-1")
        assert headers["X-Hermes-Session-Id"] == "sess-1"
        assert ("X-Hermes-Session-Key" in headers) is expect_session_key


class TestStrictSseParsing:
    """SSE 严格校验：畸形 data 行 / 未见 [DONE] 即 EOF 都不能静默当成功。"""

    def test_malformed_data_line_raises(self):
        lines = ["data: {not-json", "data: [DONE]"]
        with pytest.raises(CrawStreamProtocolError):
            list(OpenClawBackend.iter_sse_chunks(iter(lines), backend="openclaw"))

    @pytest.mark.parametrize("lines", [[], ['data: {"choices":[]}'], ["event: ping", ""]])
    def test_eof_without_done_raises(self, lines):
        with pytest.raises(CrawStreamProtocolError):
            list(OpenClawBackend.iter_sse_chunks(iter(lines), backend="openclaw"))

    def test_done_terminated_stream_ok(self):
        lines = ['data: {"choices":[{"delta":{"content":"hi"}}]}', "data: [DONE]"]
        chunks = list(OpenClawBackend.iter_sse_chunks(iter(lines), backend="openclaw"))
        assert len(chunks) == 1


def _mock_backend(monkeypatch, handler):
    """把 httpx.Client 换成 MockTransport 工厂，返回打好桩的 OpenClawBackend。"""
    real_client = httpx.Client

    def fake_client(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    return OpenClawBackend(api_url="http://stub", api_key="stub-key")


class TestStrictHttpStatus:
    """仅 2xx 视为成功：3xx（未预期重定向）与 4xx/5xx 一律拒绝。"""

    @pytest.mark.parametrize("status", [301, 302, 404, 502])
    def test_open_chat_stream_rejects_non_2xx(self, monkeypatch, status):
        backend = _mock_backend(monkeypatch, lambda request: httpx.Response(status, text="err-page"))
        with pytest.raises(CrawUpstreamError) as excinfo:
            backend.open_chat_stream([{"role": "user", "content": "hi"}])
        assert excinfo.value.status_code == status

    @pytest.mark.parametrize("status", [302, 500])
    def test_chat_completions_rejects_non_2xx(self, monkeypatch, status):
        backend = _mock_backend(monkeypatch, lambda request: httpx.Response(status, text="err-page"))
        with pytest.raises(CrawUpstreamError):
            backend.chat_completions([{"role": "user", "content": "hi"}])

    def test_upstream_error_client_message_excludes_detail(self):
        error = CrawUpstreamError("openclaw", 502, "<html>secret internals</html>")
        assert "secret" not in error.client_message
        assert "502" in error.client_message


class TestCrawChatStream:
    """流句柄：正常走完 / 截断报错 / close 后静默结束（取消语义）。"""

    @staticmethod
    def _sse_handler(body: str):
        return lambda request: httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    def test_stream_yields_chunks_until_done(self, monkeypatch):
        body = 'data: {"choices":[{"delta":{"content":"he"}}]}\n\ndata: {"choices":[{"delta":{"content":"llo"}}]}\n\ndata: [DONE]\n\n'
        backend = _mock_backend(monkeypatch, self._sse_handler(body))
        with backend.open_chat_stream([{"role": "user", "content": "hi"}]) as stream:
            chunks = list(stream)
        assert [backend.delta_text(c) for c in chunks] == ["he", "llo"]
        assert stream.interrupted is False

    def test_truncated_stream_raises(self, monkeypatch):
        body = 'data: {"choices":[{"delta":{"content":"he"}}]}\n\n'  # 无 [DONE] 即 EOF
        backend = _mock_backend(monkeypatch, self._sse_handler(body))
        stream = backend.open_chat_stream([{"role": "user", "content": "hi"}])
        with pytest.raises(CrawStreamProtocolError):
            list(stream)

    def test_empty_stream_raises(self, monkeypatch):
        backend = _mock_backend(monkeypatch, self._sse_handler(""))
        stream = backend.open_chat_stream([{"role": "user", "content": "hi"}])
        with pytest.raises(CrawStreamProtocolError):
            list(stream)

    def test_closed_stream_iterates_silently(self, monkeypatch):
        body = 'data: {"choices":[{"delta":{"content":"he"}}]}\n\n'
        backend = _mock_backend(monkeypatch, self._sse_handler(body))
        stream = backend.open_chat_stream([{"role": "user", "content": "hi"}])
        stream.close()  # 模拟 stop()：关闭后迭代不得报截断错
        assert list(stream) == []
        assert stream.interrupted is True

    def test_close_is_idempotent(self, monkeypatch):
        backend = _mock_backend(monkeypatch, self._sse_handler("data: [DONE]\n\n"))
        stream = backend.open_chat_stream([{"role": "user", "content": "hi"}])
        stream.close()
        stream.close()

    def test_chat_completions_stream_wrapper_still_works(self, monkeypatch):
        body = 'data: {"choices":[{"delta":{"content":"x"}}]}\n\ndata: [DONE]\n\n'
        backend = _mock_backend(monkeypatch, self._sse_handler(body))
        chunks = list(backend.chat_completions_stream([{"role": "user", "content": "hi"}]))
        assert len(chunks) == 1


class TestStreamErrorChunk:
    """流内 {"error": ...} 事件：HTTP 200 + 正常 [DONE]，但语义是运行失败——不得静默当成功。"""

    _ERROR_LINE = (
        'data: {"error":{"message":"upstream model ended with an incomplete terminal response",'
        '"type":"invalid_request_error","code":"incomplete_result"}}'
    )

    def test_iter_raises_on_error_chunk(self):
        lines = [self._ERROR_LINE, "data: [DONE]"]
        with pytest.raises(CrawUpstreamRunError) as excinfo:
            list(OpenClawBackend.iter_sse_chunks(iter(lines), backend="openclaw"))
        assert "incomplete_result" in excinfo.value.detail

    def test_stream_yields_text_then_raises_on_error_chunk(self, monkeypatch):
        body = 'data: {"choices":[{"delta":{"content":"前半段"}}]}\n\n' + self._ERROR_LINE + "\n\ndata: [DONE]\n\n"
        backend = _mock_backend(monkeypatch, lambda request: httpx.Response(200, text=body))
        iterator = iter(backend.open_chat_stream([{"role": "user", "content": "hi"}]))
        assert backend.delta_text(next(iterator)) == "前半段"
        with pytest.raises(CrawUpstreamRunError):
            next(iterator)

    def test_non_stream_body_error_raises(self, monkeypatch):
        backend = _mock_backend(
            monkeypatch, lambda request: httpx.Response(200, json={"error": {"code": "incomplete_result"}})
        )
        with pytest.raises(CrawUpstreamRunError):
            backend.chat_completions([{"role": "user", "content": "hi"}])

    def test_client_message_excludes_detail(self):
        error = CrawUpstreamRunError("openclaw", '{"message":"secret internal detail"}')
        assert "secret" not in error.client_message
        assert "openclaw" in error.client_message


class TestOpenClawSessionSticky:
    """OpenClaw 会话粘滞：session_code → x-openclaw-session-key（内核状态跨轮保留的前提）。"""

    def test_session_key_header_present_with_session_code(self):
        backend = OpenClawBackend(api_url="http://x", api_key="gw-token")
        headers = backend.build_headers(session_code="sess-1")
        assert headers["x-openclaw-session-key"] == "sess-1"

    def test_no_session_key_header_without_session_code(self):
        backend = OpenClawBackend(api_url="http://x", api_key="gw-token")
        assert "x-openclaw-session-key" not in backend.build_headers()
