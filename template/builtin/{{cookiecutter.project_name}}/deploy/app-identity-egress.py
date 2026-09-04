#!/usr/bin/env python3
"""Loopback AIDEV proxy using the current PaaS app identity.

Besides injecting the application identity, this proxy temporarily retains the
legacy AIDEV stream normalization for the first OpenClaw v2026.8.1 stage rollout.
The new kernel handles clean ``[DONE]`` streams without ``finish_reason`` itself;
remove this normalization after the real stage tool-call regression passes.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx

LOOPBACK = "127.0.0.1"
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _loads(text: str) -> Any:
    # Some compatible gateways return unescaped control characters in JSON.
    return json.loads(text, strict=False)


def _has_tool_calls(container: Any) -> bool:
    if not isinstance(container, dict):
        return False
    calls = container.get("tool_calls")
    return isinstance(calls, list) and bool(calls)


def _fix_non_stream(body: bytes) -> bytes:
    try:
        payload = _loads(body.decode("utf-8", "replace"))
    except Exception:
        return body
    if not isinstance(payload, dict):
        return body

    changed = False
    for choice in payload.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        if _has_tool_calls(choice.get("message")) and choice.get("finish_reason") != "tool_calls":
            choice["finish_reason"] = "tool_calls"
            changed = True
    if not changed:
        return body
    print("[app-identity-egress] normalized non-stream tool_calls finish_reason", file=sys.stderr)
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _response_headers(
        self,
        response: httpx.Response,
        *,
        decoded: bool = False,
        content_length: int | None = None,
    ) -> None:
        excluded = HOP_BY_HOP | {"content-length"}
        if decoded:
            excluded.add("content-encoding")
        for key, value in response.headers.items():
            if key.lower() not in excluded:
                self.send_header(key, value)
        if content_length is not None:
            self.send_header("Content-Length", str(content_length))
        self.send_header("Connection", "close")
        self.end_headers()

    @staticmethod
    def _wants_stream(body: bytes) -> bool:
        try:
            payload = _loads(body.decode("utf-8", "replace"))
        except Exception:
            return False
        return isinstance(payload, dict) and bool(payload.get("stream"))

    def _relay_chat_stream(self, response: httpx.Response) -> None:
        saw_finish = False
        saw_tool_call = False
        template: dict[str, Any] | None = None
        pending_done = False

        def emit(chunk: bytes) -> None:
            if chunk:
                self.wfile.write(chunk)
                self.wfile.flush()

        for line in response.iter_lines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data == "[DONE]":
                    pending_done = True
                    continue
                try:
                    event = _loads(data)
                except Exception:
                    event = None
                if isinstance(event, dict):
                    template = template or event
                    for choice in event.get("choices") or []:
                        if not isinstance(choice, dict):
                            continue
                        if choice.get("finish_reason") is not None:
                            saw_finish = True
                        if _has_tool_calls(choice.get("delta")):
                            saw_tool_call = True
            emit((line + "\n").encode("utf-8"))

        if not pending_done:
            return
        if not saw_finish:
            reason = "tool_calls" if saw_tool_call else "stop"
            closing = {
                "id": (template or {}).get("id", "chatcmpl-egress"),
                "object": "chat.completion.chunk",
                "created": (template or {}).get("created", 0),
                "model": (template or {}).get("model", ""),
                "choices": [{"index": 0, "delta": {}, "finish_reason": reason}],
            }
            emit(("data: " + json.dumps(closing, ensure_ascii=False) + "\n\n").encode("utf-8"))
            print(f"[app-identity-egress] added terminal finish_reason={reason}", file=sys.stderr)
        emit(b"data: [DONE]\n\n")

    def _proxy(self) -> None:
        app_code = os.getenv("BKPAAS_APP_ID", "")
        app_secret = os.getenv("BKPAAS_APP_SECRET", "")
        if not app_code or not app_secret:
            self.send_error(503, "PaaS application identity is unavailable")
            return

        origin = os.getenv("BKAI_AIDEV_APP_UPSTREAM_ORIGIN", "").rstrip("/")
        if not origin:
            self.send_error(503, "AIDEV upstream origin is unavailable")
            return
        target = f"{origin}{self.path}"
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(content_length) if content_length else b""
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP | {"host", "content-length", "authorization", "x-bkapi-authorization"}
        }
        headers["X-Bkapi-Authorization"] = json.dumps(
            {"bk_app_code": app_code, "bk_app_secret": app_secret}, separators=(",", ":")
        )

        path = self.path.partition("?")[0].rstrip("/")
        is_chat = path.endswith("/chat/completions")
        wants_stream = is_chat and self._wants_stream(body)

        try:
            with (
                httpx.Client(timeout=None, follow_redirects=False) as client,
                client.stream(self.command, target, headers=headers, content=body) as response,
            ):
                self.send_response(response.status_code)
                if response.status_code == 200 and wants_stream:
                    self._response_headers(response, decoded=True)
                    self._relay_chat_stream(response)
                elif response.status_code == 200 and is_chat:
                    payload = _fix_non_stream(response.read())
                    self._response_headers(response, decoded=True, content_length=len(payload))
                    self.wfile.write(payload)
                else:
                    self._response_headers(response)
                    for chunk in response.iter_raw():
                        if chunk:
                            self.wfile.write(chunk)
                            self.wfile.flush()
        except Exception:
            self.send_error(502, "AIDEV upstream request failed")
        finally:
            self.close_connection = True

    do_GET = _proxy
    do_POST = _proxy
    do_PUT = _proxy
    do_PATCH = _proxy
    do_DELETE = _proxy

    def log_message(self, _format: str, *_args) -> None:
        return


def main() -> None:
    port = int(os.getenv("BKAI_APP_IDENTITY_EGRESS_PORT", "18790"))
    server = ThreadingHTTPServer((LOOPBACK, port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
