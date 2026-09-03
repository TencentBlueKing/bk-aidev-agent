# -*- coding: utf-8 -*-
"""MCP egress：配置重写、共享槽租约、按用户 token 注入。"""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import httpx
import pytest
from aidev_agent.packages.craw.mcp_egress import (
    SHARED_ID,
    McpEgress,
    persist_egress_routes,
    rewrite_openclaw_config_file,
    rewrite_openclaw_mcp_to_egress,
)
from aidev_agent.packages.craw.mcp_identity import (
    CrawLeaseError,
    bind_user_access_token,
    get_bound_user_access_token,
    mcp_identity_lease,
    normalize_access_token,
    resolve_user_access_token,
)


def test_normalize_strips_bearer_and_quotes():
    assert normalize_access_token('Bearer "abc"') == "abc"
    assert normalize_access_token("  xyz  ") == "xyz"


def test_bind_and_resolve_prefers_contextvar():
    class RM:
        def resolve_access_token(self, username):
            return "from-db"

    bind_user_access_token("from-request")
    assert get_bound_user_access_token() == "from-request"
    assert resolve_user_access_token("alice", RM()) == "from-request"
    bind_user_access_token("")
    assert resolve_user_access_token("alice", RM()) == "from-db"


def test_rewrite_openclaw_mcp_strips_baked_token():
    config = {
        "mcp": {
            "servers": {
                "log-query": {
                    "url": "https://example.invalid/mcp/",
                    "headers": {"X-Bkapi-Authorization": '{"access_token":"baked"}'},
                }
            }
        }
    }
    routes, rewritten, skipped = rewrite_openclaw_mcp_to_egress(config, egress_base="http://127.0.0.1:18787")
    assert rewritten == ["log-query"]
    assert skipped == []
    assert routes["log-query"] == "https://example.invalid/mcp/"
    spec = config["mcp"]["servers"]["log-query"]
    assert spec["url"] == f"http://127.0.0.1:18787/egress/{SHARED_ID}/log-query/"
    assert "X-Bkapi-Authorization" not in spec["headers"]
    assert spec["headers"]["X-Bkai-Egress-Key"]


def test_rewrite_config_file_persists_routes(tmp_path, monkeypatch):
    config_path = tmp_path / "openclaw.json"
    routes_path = tmp_path / "routes.json"
    monkeypatch.setenv("BKAI_MCP_EGRESS_ROUTES", str(routes_path))
    config_path.write_text(
        json.dumps(
            {
                "mcp": {
                    "servers": {
                        "log-query": {
                            "url": "https://example.invalid/mcp/",
                            "headers": {"X-Bkapi-Authorization": '{"access_token":"baked"}'},
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    result = rewrite_openclaw_config_file(str(config_path), "http://127.0.0.1:18787")
    assert result["rewritten"] == ["log-query"]
    dumped = json.loads(config_path.read_text(encoding="utf-8"))
    assert "X-Bkapi-Authorization" not in dumped["mcp"]["servers"]["log-query"]["headers"]
    assert json.loads(routes_path.read_text(encoding="utf-8"))["log-query"] == "https://example.invalid/mcp/"
    persist_egress_routes({"other": "https://example.invalid/other/"}, str(routes_path))
    assert json.loads(routes_path.read_text(encoding="utf-8"))["other"] == "https://example.invalid/other/"


class _Upstream(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.seen.append({"method": "POST", "auth": self.headers.get("X-Bkapi-Authorization"), "body": body})
        payload = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_DELETE(self):
        self.seen.append({"method": "DELETE", "auth": self.headers.get("X-Bkapi-Authorization"), "body": b""})
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def upstream():
    _Upstream.seen = []
    server = HTTPServer(("127.0.0.1", 0), _Upstream)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/mcp/"
    server.shutdown()


def test_egress_injects_leased_user_token(upstream):
    egress = McpEgress(port=0, drain_seconds=0).start()
    try:
        egress.register_routes({"log-query": upstream})
        lease_id = egress.acquire("user-token-aaa")
        assert lease_id
        url = f"{egress.base_url}/egress/{SHARED_ID}/log-query/"
        response = httpx.post(url, json={"method": "initialize"})
        assert response.status_code == 200
        assert response.headers.get_list("content-length") == [str(len(response.content))]
        assert json.loads(_Upstream.seen[-1]["auth"]) == {"access_token": "user-token-aaa"}
    finally:
        egress.release(lease_id)
        egress.stop()


def test_egress_proxies_delete_for_session_cleanup(upstream):
    egress = McpEgress(port=0, drain_seconds=0).start()
    try:
        egress.register_routes({"log-query": upstream})
        lease_id = egress.acquire("user-token-delete")
        assert lease_id
        url = f"{egress.base_url}/egress/{SHARED_ID}/log-query/"
        response = httpx.delete(url)
        assert response.status_code == 204
        assert _Upstream.seen[-1]["method"] == "DELETE"
        assert json.loads(_Upstream.seen[-1]["auth"]) == {"access_token": "user-token-delete"}
    finally:
        egress.release(lease_id)
        egress.stop()


def test_egress_without_lease_is_401(upstream):
    egress = McpEgress(port=0).start()
    try:
        egress.register_routes({"log-query": upstream})
        url = f"{egress.base_url}/egress/{SHARED_ID}/log-query/"
        response = httpx.post(url, json={"method": "initialize"})
        assert response.status_code == 401
        assert _Upstream.seen == []
    finally:
        egress.stop()


def test_identity_lease_roundtrip(monkeypatch, upstream):
    egress = McpEgress(port=0).start()
    monkeypatch.setenv("BKAI_MCP_EGRESS_URL", egress.base_url)
    egress.register_routes({"log-query": upstream})
    try:
        with mcp_identity_lease("user-token-bbb"):
            response = httpx.post(f"{egress.base_url}/egress/{SHARED_ID}/log-query/", json={})
            assert response.status_code == 200
            assert json.loads(_Upstream.seen[-1]["auth"])["access_token"] == "user-token-bbb"
        response = httpx.post(f"{egress.base_url}/egress/{SHARED_ID}/log-query/", json={})
        assert response.status_code == 401
    finally:
        egress.stop()


def test_stuck_lease_expires_into_quarantine(upstream):
    """TTL 到期：清凭据 + 隔离，禁止下任接管，直到持有者迟到 release 交接。"""
    egress = McpEgress(port=0, lease_ttl=0.05, drain_seconds=0.05).start()
    try:
        egress.register_routes({"log-query": upstream})
        old_lease = egress.acquire("old-token")
        assert old_lease
        time.sleep(0.08)
        # 过期后凭据立即清空：旧运行的迟到请求是 401，而不会拿到下任身份
        assert egress.current_token() == ""
        response = httpx.post(f"{egress.base_url}/egress/{SHARED_ID}/log-query/", json={})
        assert response.status_code == 401
        # 隔离态禁止新用户接管（超时快速失败）
        assert egress.acquire("new-token", timeout=0.2) == ""
        assert egress.current_token() == ""
        # 持有者迟到 release（其运行已结束）解除隔离并进入 drain
        assert egress.release(old_lease) is True
        # drain 窗口内 acquire 会等待排空；超时短于窗口则失败
        assert egress.acquire("new-token", timeout=0.01) == ""
        time.sleep(0.08)
        new_lease = egress.acquire("new-token")
        assert new_lease
        response = httpx.post(f"{egress.base_url}/egress/{SHARED_ID}/log-query/", json={})
        assert response.status_code == 200
        assert json.loads(_Upstream.seen[-1]["auth"])["access_token"] == "new-token"
        # 旧租约的再次迟到 release 不能清掉新持有者
        assert egress.release(old_lease) is False
        assert egress.current_token() == "new-token"
    finally:
        egress.stop()


def test_release_requires_ownership(upstream):
    """release 必须携带本次租约 ID；错误 ID 不清槽。"""
    egress = McpEgress(port=0, drain_seconds=0).start()
    try:
        egress.register_routes({"log-query": upstream})
        lease_id = egress.acquire("user-token-owner")
        assert lease_id
        assert egress.release("") is False
        assert egress.release("not-the-lease") is False
        assert egress.current_token() == "user-token-owner"
        assert egress.release(lease_id) is True
        assert egress.current_token() == ""
        # 重复释放不生效
        assert egress.release(lease_id) is False
        other = egress.acquire("user-token-next")
        assert other and other != lease_id
        assert egress.release(lease_id) is False
        assert egress.current_token() == "user-token-next"
    finally:
        egress.stop()


def test_lease_fail_closed_when_slot_busy(monkeypatch, upstream):
    """租约获取失败必须终止运行（CrawLeaseError），不能沿用共享槽里的上一身份。"""
    egress = McpEgress(port=0, drain_seconds=0).start()
    monkeypatch.setenv("BKAI_MCP_EGRESS_URL", egress.base_url)
    monkeypatch.setenv("BKAI_MCP_EGRESS_LEASE_TIMEOUT", "0.2")
    egress.register_routes({"log-query": upstream})
    holder = egress.acquire("user-token-holder")
    assert holder
    try:
        with pytest.raises(CrawLeaseError), mcp_identity_lease("user-token-waiting"):
            pass
        # 失败方未获得租约，持有者身份原样保留
        assert egress.current_token() == "user-token-holder"
    finally:
        egress.stop()


def test_release_enters_drain_window(upstream):
    """正常 release 后经过短暂 drain 才允许下一任接管，排空旧运行的残留请求。"""
    egress = McpEgress(port=0, drain_seconds=0.1).start()
    try:
        egress.register_routes({"log-query": upstream})
        lease_id = egress.acquire("user-token-a")
        assert lease_id
        assert egress.release(lease_id) is True
        # drain 窗口内：无凭据（残留请求 401），也不可接管
        assert egress.current_token() == ""
        response = httpx.post(f"{egress.base_url}/egress/{SHARED_ID}/log-query/", json={})
        assert response.status_code == 401
        assert egress.acquire("user-token-b", timeout=0.02) == ""
        time.sleep(0.12)
        assert egress.acquire("user-token-b")
    finally:
        egress.stop()
