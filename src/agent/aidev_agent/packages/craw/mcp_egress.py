# -*- coding: utf-8 -*-
"""本机 MCP 出口网关：按身份注入用户 access_token，盘上零真 token。

单内核形态用共享槽 ``shared``：对话侧 ``/internal/acquire`` 租约串行写入
当前用户 token，OpenClaw 的 MCP URL 被重写为 ``/egress/shared/<slug>/``，
转发时注入 ``X-Bkapi-Authorization: {"access_token": <用户 token>}``。

隔离语义（fail-closed）：
- acquire 返回独立的 leaseId，release 必须携带同一 ID 才生效——迟到/重复
  释放不会清掉下一任持有者；
- TTL 到期不代表旧运行已停止：立即清空凭据（旧运行的迟到 MCP 请求得到
  401 而不是下一任身份），并进入隔离状态，禁止新用户接管；隔离只能由
  持有者的迟到 release（证明其运行已结束）解除，恢复前再经过短暂
  drain 窗口排空残留请求；
- 持有者永不释放（进程级故障）时保持不可用，由运维从日志取隔离的
  leaseId 调 ``/internal/release`` 做受控恢复，或重建实例。

只绑 127.0.0.1。凭证纯内存。日志只打 leaseId / slug / 状态码。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from aidev_agent.packages.craw.mcp_identity import SHARED_IDENTITY_ID, normalize_access_token

_logger = logging.getLogger(__name__)

EGRESS_KEY_HEADER = "x-bkai-egress-key"
SHARED_ID = SHARED_IDENTITY_ID


def identity_id_for(token: str) -> str:
    seed = normalize_access_token(token)
    if not seed:
        return ""
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _iter_mcp_servers(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """兼容 openclaw.json 的 mcp / mcpServers 两种容器。"""
    found: list[tuple[str, dict[str, Any]]] = []
    for key in ("mcpServers", "mcp"):
        node = config.get(key)
        servers = node.get("servers") if isinstance(node, dict) and "servers" in node else node
        if not isinstance(servers, dict):
            continue
        for slug, spec in servers.items():
            if isinstance(spec, dict):
                found.append((slug, spec))
    return found


def rewrite_openclaw_mcp_to_egress(
    config: dict[str, Any],
    *,
    egress_base: str,
    identity_id: str = SHARED_ID,
    egress_key: str = "",
) -> tuple[dict[str, str], list[str], list[str]]:
    """把 HTTP MCP 的真实 URL 抽到返回值，配置改写为 egress 地址。

    :return: (slug→真实 URL, 已重写 slug, 跳过 slug)
    """
    routes: dict[str, str] = {}
    rewritten: list[str] = []
    skipped: list[str] = []
    key = egress_key or f"bkai-egress-{secrets.token_hex(18)}"
    base = egress_base.rstrip("/")
    for slug, spec in _iter_mcp_servers(config):
        url = spec.get("url")
        if not url or spec.get("command"):
            continue
        url = str(url)
        if "/egress/" in url:
            skipped.append(slug)
            continue
        routes[slug] = url
        spec["url"] = f"{base}/egress/{identity_id}/{slug}/"
        headers = spec.get("headers") if isinstance(spec.get("headers"), dict) else {}
        cleaned = {name: value for name, value in headers.items() if str(name).lower() != "x-bkapi-authorization"}
        cleaned["X-Bkai-Egress-Key"] = key
        spec["headers"] = cleaned
        rewritten.append(slug)
    return routes, rewritten, skipped


def rewrite_openclaw_config_file(path: str, egress_base: str, *, identity_id: str = SHARED_ID) -> dict[str, Any]:
    """读盘改写 MCP，权限 0600。返回 {rewritten, skipped, routes}（routes 仅 slug，不含 token）。"""
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    routes, rewritten, skipped = rewrite_openclaw_mcp_to_egress(
        config, egress_base=egress_base, identity_id=identity_id
    )
    tmp = f"{path}.craw-egress-tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
    with suppress(OSError):
        os.chmod(path, 0o600)
    persist_egress_routes(routes)
    _logger.warning("[CRAW] MCP 已改写到 egress identity=%s rewritten=%s skipped=%s", identity_id, rewritten, skipped)
    return {"rewritten": rewritten, "skipped": skipped, "routes": routes}


def persist_egress_routes(routes: dict[str, str], path: str = "") -> str:
    """把 slug→真实 URL 写到 ``BKAI_MCP_EGRESS_ROUTES``，权限 0600。不含 token。"""
    dest = path or os.getenv("BKAI_MCP_EGRESS_ROUTES") or "/tmp/craw-mcp-routes.json"
    tmp = f"{dest}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(routes, handle, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, dest)
    with suppress(OSError):
        os.chmod(dest, 0o600)
    return dest


class McpEgress:
    """loopback MCP 出口：共享槽租约 + 按路径注入用户 token。"""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        request_open: Optional[Callable[..., Any]] = None,
        lease_ttl: float = 3600.0,
        drain_seconds: float = 5.0,
    ):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("MCP egress 只允许绑定 loopback")
        self.host = host
        self.port = int(port)
        self._request_open = request_open or urlopen
        self.lease_ttl = lease_ttl
        self.drain_seconds = max(0.0, float(drain_seconds))
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._lease_id = ""
        self._token = ""
        self._leased_at = 0.0
        self._drain_until = 0.0
        # 非空表示槽位处于隔离态（TTL 过期且旧运行未交接），值为过期租约 ID
        self._quarantine_lease_id = ""
        self._key = f"bkai-egress-{secrets.token_hex(18)}"
        self._routes: dict[str, str] = {}
        self._routes_file = os.getenv("BKAI_MCP_EGRESS_ROUTES") or ""
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def _merged_routes(self) -> dict[str, str]:
        routes = dict(self._routes)
        path = self._routes_file
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    extra = json.load(handle)
                if isinstance(extra, dict):
                    routes.update({str(key): str(value) for key, value in extra.items()})
            except (OSError, json.JSONDecodeError):
                pass
        return routes

    @property
    def bound_port(self) -> int:
        if self._server is None:
            return self.port
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.bound_port}"

    def register_routes(self, routes: dict[str, str]) -> str:
        with self._lock:
            for slug, url in routes.items():
                self._routes[slug] = str(url)
            return self._key

    def _expire_if_needed_locked(self) -> None:
        if not self._lease_id or self.lease_ttl <= 0:
            return
        if (time.monotonic() - self._leased_at) < self.lease_ttl:
            return
        _logger.warning("[egress] lease %s 过期，清空凭据并进入隔离，等待持有者交接", self._lease_id)
        self._quarantine_lease_id = self._lease_id
        self._lease_id = ""
        self._token = ""
        self._leased_at = 0.0
        self._cond.notify_all()

    def acquire(self, token: str, timeout: float = 30.0) -> str:
        """占用共享槽并返回本次租约 ID；被占用、隔离中或超时返回空串。"""
        token = normalize_access_token(token)
        if not token:
            return ""
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                self._expire_if_needed_locked()
                now = time.monotonic()
                remaining = deadline - now
                if remaining <= 0:
                    return ""
                if not self._lease_id and not self._quarantine_lease_id and now >= self._drain_until:
                    self._lease_id = secrets.token_hex(16)
                    self._token = token
                    self._leased_at = now
                    self._cond.notify_all()
                    return self._lease_id
                if self._lease_id:
                    wait_for = remaining
                    if self.lease_ttl > 0 and self._leased_at:
                        wait_for = min(wait_for, max(0.05, self.lease_ttl - (now - self._leased_at)))
                elif self._quarantine_lease_id:
                    # 隔离态只能等持有者交接；周期唤醒以便及时响应超时
                    wait_for = min(remaining, 0.5)
                else:
                    wait_for = min(remaining, max(0.05, self._drain_until - now))
                self._cond.wait(timeout=wait_for)

    def release(self, lease_id: str = "") -> bool:
        """释放租约。仅持有者可释放；过期持有者的迟到 release 用于解除隔离。"""
        with self._cond:
            if lease_id and lease_id == self._lease_id:
                self._lease_id = ""
                self._token = ""
                self._leased_at = 0.0
                self._drain_until = time.monotonic() + self.drain_seconds
                self._cond.notify_all()
                return True
            if lease_id and lease_id == self._quarantine_lease_id:
                self._quarantine_lease_id = ""
                self._drain_until = time.monotonic() + self.drain_seconds
                self._cond.notify_all()
                return True
            return False

    def current_token(self) -> str:
        with self._cond:
            self._expire_if_needed_locked()
            return self._token

    def start(self) -> "McpEgress":
        egress = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                _logger.info("[egress] " + fmt, *args)

            def _json(self, code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    data = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    return {}
                return data if isinstance(data, dict) else {}

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/internal/acquire":
                    token = normalize_access_token((self._read_json().get("token") or ""))
                    lease_id = egress.acquire(token)
                    if lease_id:
                        self._json(200, {"ok": True, "identityId": SHARED_ID, "leaseId": lease_id})
                    else:
                        self._json(503, {"ok": False, "error": "MCP 身份租约忙碌、隔离中或 token 为空"})
                    return
                if parsed.path == "/internal/release":
                    lease_id = str(self._read_json().get("leaseId") or "")
                    if egress.release(lease_id):
                        self._json(200, {"ok": True})
                    else:
                        self._json(409, {"ok": False, "error": "租约不存在或不属于本次获取"})
                    return
                self._proxy(parsed)

            def do_GET(self) -> None:  # noqa: N802
                self._proxy(urlparse(self.path))

            def do_HEAD(self) -> None:  # noqa: N802
                self._proxy(urlparse(self.path))

            def do_DELETE(self) -> None:  # noqa: N802
                self._proxy(urlparse(self.path))

            def _proxy(self, parsed) -> None:
                parts = [item for item in parsed.path.split("/") if item]
                if len(parts) < 3 or parts[0] != "egress":
                    self._json(404, {"ok": False, "error": "不是 /egress/<id>/<slug>/ 路径"})
                    return
                _identity, slug = parts[1], parts[2]
                target = egress._merged_routes().get(slug)
                if not target:
                    self._json(404, {"ok": False, "error": f"未知 MCP slug: {slug}"})
                    return
                token = egress.current_token()
                if not token:
                    self._json(
                        401,
                        {"ok": False, "error": "该身份暂无 MCP 凭证:对话需带用户 access_token"},
                    )
                    return
                try:
                    upstream = urlparse(target)
                except ValueError:
                    self._json(502, {"ok": False, "error": "upstream url 无效"})
                    return
                headers = {name: value for name, value in self.headers.items() if name.lower() != EGRESS_KEY_HEADER}
                headers.pop("Host", None)
                headers.pop("host", None)
                headers["Host"] = upstream.netloc
                headers["X-Bkapi-Authorization"] = json.dumps({"access_token": token})
                query = parsed.query
                up_query = upstream.query
                if up_query and query:
                    search = f"?{up_query}&{query}"
                elif up_query or query:
                    search = f"?{up_query or query}"
                else:
                    search = ""
                body = b""
                if self.command != "GET" and self.command != "HEAD":
                    length = int(self.headers.get("Content-Length") or 0)
                    body = self.rfile.read(length) if length else b""
                req = Request(
                    f"{upstream.scheme}://{upstream.netloc}{upstream.path}{search}",
                    data=body or None,
                    headers=headers,
                    method=self.command,
                )
                try:
                    with egress._request_open(req, timeout=60) as resp:
                        payload = resp.read()
                        self.send_response(getattr(resp, "status", 200))
                        for name, value in resp.headers.items():
                            if name.lower() in {"transfer-encoding", "connection", "content-length"}:
                                continue
                            self.send_header(name, value)
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        if self.command != "HEAD":
                            self.wfile.write(payload)
                        _logger.info(
                            "[egress] %s id=%s slug=%s %s", getattr(resp, "status", 200), SHARED_ID, slug, self.command
                        )
                except HTTPError as exc:
                    payload = exc.read() if exc.fp else b""
                    self.send_response(exc.code)
                    self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(payload)
                    _logger.info("[egress] %s id=%s slug=%s %s", exc.code, SHARED_ID, slug, self.command)
                except (URLError, TimeoutError, OSError) as exc:
                    self._json(502, {"ok": False, "error": f"上游不可达: {exc}"})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self.port = self.bound_port
        self._thread = threading.Thread(target=self._server.serve_forever, name="craw-mcp-egress", daemon=True)
        self._thread.start()
        _logger.warning("[CRAW] MCP egress 就绪 %s（loopback，凭证纯内存）", self.base_url)
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        with self._cond:
            self._lease_id = ""
            self._token = ""
            self._leased_at = 0.0
            self._drain_until = 0.0
            self._quarantine_lease_id = ""
            self._cond.notify_all()
        self._routes.clear()


def serve_forever(host: str = "127.0.0.1", port: int = 18787, config_path: str = "") -> None:
    egress = McpEgress(
        host=host,
        port=port,
        lease_ttl=float(os.getenv("BKAI_MCP_EGRESS_LEASE_TTL") or 3600),
        drain_seconds=float(os.getenv("BKAI_MCP_EGRESS_DRAIN_SECONDS") or 5),
    ).start()
    if config_path and os.path.isfile(config_path):
        result = rewrite_openclaw_config_file(config_path, egress.base_url)
        egress.register_routes(result["routes"])
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        egress.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="craw MCP egress")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("BKAI_MCP_EGRESS_PORT") or 18787))
    parser.add_argument("--config", default=os.getenv("OPENCLAW_CONFIG_PATH") or "")
    parser.add_argument("--rewrite-only", action="store_true")
    args = parser.parse_args()
    base = f"http://{args.host}:{args.port}"
    if args.rewrite_only:
        if not args.config:
            raise SystemExit("rewrite-only 需要 --config")
        rewrite_openclaw_config_file(args.config, base)
        raise SystemExit(0)
    logging.basicConfig(level=logging.INFO)
    serve_forever(host=args.host, port=args.port, config_path=args.config)
