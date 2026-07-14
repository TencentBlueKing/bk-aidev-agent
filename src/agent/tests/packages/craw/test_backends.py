# -*- coding: utf-8 -*-
"""craw 后端：env 装配链 / 请求头 / 身份隔离。"""

import pytest

from aidev_agent.packages.craw import CrawIdentity, HermesBackend, OpenClawBackend, get_backend
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
            (OpenClawBackend, {"BKAI_CRAW_API_URL": "http://u:1/"}, {"BKAI_OPENCLAW_GATEWAY_URL": "http://l:2"}, "http://u:1"),
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
