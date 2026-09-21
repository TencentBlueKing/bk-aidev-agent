# -*- coding: utf-8 -*-
"""MCP egress：配置重写、共享槽租约、按用户 token 注入。"""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread

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
    EGRESS_KEY_ENV,
    EGRESS_KEY_HEADER,
    CrawLeaseError,
    bind_user_access_token,
    get_bound_user_access_token,
    mcp_identity_lease,
    normalize_access_token,
    resolve_user_access_token,
)


def _egress_headers(egress: McpEgress) -> dict[str, str]:
    return {EGRESS_KEY_HEADER: egress.egress_key}


def test_normalize_strips_bearer_and_quotes():
    assert normalize_access_token('Bearer "abc"') == "abc"
    assert normalize_access_token("  xyz  ") == "xyz"
    assert normalize_access_token("Bearer ") == ""


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
    routes, rewritten, skipped = rewrite_openclaw_mcp_to_egress(
        config,
        egress_base="http://127.0.0.1:18787",
        egress_key="test-egress-key",
    )
    assert rewritten == ["log-query"]
    assert skipped == []
    assert routes["log-query"] == "https://example.invalid/mcp/"
    spec = config["mcp"]["servers"]["log-query"]
    assert spec["url"] == f"http://127.0.0.1:18787/egress/{SHARED_ID}/log-query/"
    assert "X-Bkapi-Authorization" not in spec["headers"]
    assert spec["headers"][EGRESS_KEY_HEADER] == "test-egress-key"


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
    result = rewrite_openclaw_config_file(
        str(config_path),
        "http://127.0.0.1:18787",
        egress_key="test-egress-key",
    )
    assert result["rewritten"] == ["log-query"]
    dumped = json.loads(config_path.read_text(encoding="utf-8"))
    headers = dumped["mcp"]["servers"]["log-query"]["headers"]
    assert "X-Bkapi-Authorization" not in headers
    assert headers[EGRESS_KEY_HEADER] == "test-egress-key"
    assert json.loads(routes_path.read_text(encoding="utf-8"))["log-query"] == "https://example.invalid/mcp/"
    # 重入改写不得用空映射覆盖第一次保存的真实上游。
    second = rewrite_openclaw_config_file(
        str(config_path),
        "http://127.0.0.1:18787",
        egress_key="test-egress-key",
    )
    assert second["rewritten"] == []
    assert second["skipped"] == ["log-query"]
    assert second["routes"] == {"log-query": "https://example.invalid/mcp/"}
    assert json.loads(routes_path.read_text(encoding="utf-8")) == second["routes"]

    persist_egress_routes({"other": "https://example.invalid/other/"}, str(routes_path))
    assert json.loads(routes_path.read_text(encoding="utf-8"))["other"] == "https://example.invalid/other/"


def test_rewrite_rejects_already_rewritten_config_without_original_route(tmp_path, monkeypatch):
    config_path = tmp_path / "openclaw.json"
    routes_path = tmp_path / "missing-routes.json"
    monkeypatch.setenv("BKAI_MCP_EGRESS_ROUTES", str(routes_path))
    config_path.write_text(
        json.dumps(
            {
                "mcp": {
                    "servers": {
                        "demo": {
                            "url": f"http://127.0.0.1:18787/egress/{SHARED_ID}/demo/",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="缺少原始路由"):
        rewrite_openclaw_config_file(str(config_path), "http://127.0.0.1:18787", egress_key="test-key")


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


class _StreamingUpstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    first_sent = Event()
    finish = Event()

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        frame = b"data: first\n\n"
        self.wfile.write(f"{len(frame):X}\r\n".encode() + frame + b"\r\n")
        self.wfile.flush()
        self.first_sent.set()
        self.finish.wait(timeout=3)
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


def test_egress_streams_first_sse_frame_before_upstream_eof():
    _StreamingUpstream.first_sent = Event()
    _StreamingUpstream.finish = Event()
    upstream_server = HTTPServer(("127.0.0.1", 0), _StreamingUpstream)
    upstream_thread = Thread(target=upstream_server.serve_forever, daemon=True)
    upstream_thread.start()
    egress = McpEgress(port=0, drain_seconds=0).start()
    lease_id = ""
    received = []
    received_first = Event()

    def read_downstream():
        with httpx.stream(
            "GET",
            f"{egress.base_url}/egress/{SHARED_ID}/stream/",
            headers=_egress_headers(egress),
            timeout=3,
        ) as response:
            response.raise_for_status()
            received.append(next(response.iter_raw()))
            received_first.set()

    try:
        target = f"http://127.0.0.1:{upstream_server.server_address[1]}/mcp/"
        egress.register_routes({"stream": target})
        lease_id = egress.acquire("stream-user")
        client_thread = Thread(target=read_downstream, daemon=True)
        client_thread.start()
        assert _StreamingUpstream.first_sent.wait(timeout=1)
        assert received_first.wait(timeout=1), "首帧不应等待上游 EOF"
        assert b"data: first" in received[0]
        assert _StreamingUpstream.finish.is_set() is False
    finally:
        _StreamingUpstream.finish.set()
        if lease_id:
            egress.release(lease_id)
        egress.stop()
        upstream_server.shutdown()


def test_egress_injects_leased_user_token(upstream):
    egress = McpEgress(port=0, drain_seconds=0).start()
    try:
        egress.register_routes({"log-query": upstream})
        lease_id = egress.acquire("user-token-aaa")
        assert lease_id
        url = f"{egress.base_url}/egress/{SHARED_ID}/log-query/"
        response = httpx.post(url, json={"method": "initialize"}, headers=_egress_headers(egress))
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
        response = httpx.delete(url, headers=_egress_headers(egress))
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
        response = httpx.post(url, json={"method": "initialize"}, headers=_egress_headers(egress))
        assert response.status_code == 401
        assert _Upstream.seen == []
    finally:
        egress.stop()


def test_egress_rejects_missing_internal_key(upstream):
    egress = McpEgress(port=0).start()
    try:
        egress.register_routes({"log-query": upstream})
        response = httpx.post(f"{egress.base_url}/egress/{SHARED_ID}/log-query/", json={})
        assert response.status_code == 403
        assert _Upstream.seen == []
    finally:
        egress.stop()


def test_identity_lease_requires_internal_key(monkeypatch):
    monkeypatch.setenv("BKAI_MCP_EGRESS_URL", "http://127.0.0.1:18787")
    monkeypatch.delenv(EGRESS_KEY_ENV, raising=False)

    with pytest.raises(CrawLeaseError, match="鉴权 key"), mcp_identity_lease("user-token"):
        pass


def test_identity_lease_quarantine_blocks_handoff(monkeypatch, upstream):
    egress = McpEgress(port=0, drain_seconds=0).start()
    monkeypatch.setenv("BKAI_MCP_EGRESS_URL", egress.base_url)
    monkeypatch.setenv(EGRESS_KEY_ENV, egress.egress_key)
    try:
        with mcp_identity_lease("user-token-quarantine") as lease:
            assert lease.lease_id
            lease.quarantine()
        assert egress.current_token() == ""
        assert egress.acquire("next-user", timeout=0.05) == ""
        # 只有原持有者或运维按租约 ID 做受控恢复，才解除隔离。
        assert egress.release(lease.lease_id) is True
        assert egress.acquire("next-user", timeout=0.2)
    finally:
        egress.stop()


def test_identity_lease_roundtrip(monkeypatch, upstream):
    egress = McpEgress(port=0).start()
    monkeypatch.setenv("BKAI_MCP_EGRESS_URL", egress.base_url)
    monkeypatch.setenv(EGRESS_KEY_ENV, egress.egress_key)
    egress.register_routes({"log-query": upstream})
    try:
        with mcp_identity_lease("user-token-bbb"):
            response = httpx.post(
                f"{egress.base_url}/egress/{SHARED_ID}/log-query/",
                json={},
                headers=_egress_headers(egress),
            )
            assert response.status_code == 200
            assert json.loads(_Upstream.seen[-1]["auth"])["access_token"] == "user-token-bbb"
        response = httpx.post(
            f"{egress.base_url}/egress/{SHARED_ID}/log-query/",
            json={},
            headers=_egress_headers(egress),
        )
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
        response = httpx.post(
            f"{egress.base_url}/egress/{SHARED_ID}/log-query/",
            json={},
            headers=_egress_headers(egress),
        )
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
        response = httpx.post(
            f"{egress.base_url}/egress/{SHARED_ID}/log-query/",
            json={},
            headers=_egress_headers(egress),
        )
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
    monkeypatch.setenv(EGRESS_KEY_ENV, egress.egress_key)
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
        response = httpx.post(
            f"{egress.base_url}/egress/{SHARED_ID}/log-query/",
            json={},
            headers=_egress_headers(egress),
        )
        assert response.status_code == 401
        assert egress.acquire("user-token-b", timeout=0.02) == ""
        time.sleep(0.12)
        assert egress.acquire("user-token-b")
    finally:
        egress.stop()
