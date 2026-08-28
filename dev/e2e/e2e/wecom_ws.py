"""Minimal local WeCom WebSocket endpoint used by the E2E suite.

Only the remote wire protocol is simulated. The official SDK and the wxbot
long-connection service remain the system under test.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import socket
import struct
import threading
import time
import uuid
from typing import Any


class WeComWebSocketMock:
    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((host, port))
        self._listener.listen(1)
        self._listener.settimeout(0.5)
        self.port = int(self._listener.getsockname()[1])
        self.url = f"ws://{host}:{self.port}"
        self._client: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._condition = threading.Condition()
        self._closed = threading.Event()
        self._authenticated = False
        self.auth_frame: dict[str, Any] | None = None
        self.heartbeat_frames: list[dict[str, Any]] = []
        self.callback_frames: dict[str, dict[str, Any]] = {}
        self.reply_frames: dict[str, list[dict[str, Any]]] = {}
        self.error = ""
        self.thread = threading.Thread(target=self._serve, name="e2e-wecom-ws-mock", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self._closed.set()
        if self._client:
            with contextlib.suppress(OSError):
                self._client.shutdown(socket.SHUT_RDWR)
            self._client.close()
        self._listener.close()
        self.thread.join(timeout=3)

    def wait_authenticated(self, timeout: float = 15) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self._authenticated and not self.error and time.monotonic() < deadline:
                self._condition.wait(max(0.01, deadline - time.monotonic()))
            if self.error:
                raise AssertionError(f"WeCom WebSocket mock failed: {self.error}")
            if not self._authenticated or self.auth_frame is None:
                raise AssertionError("WeCom long connection did not authenticate")
            return self.auth_frame

    def wait_heartbeat(self, timeout: float = 5) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while not self.heartbeat_frames and not self.error and time.monotonic() < deadline:
                self._condition.wait(max(0.01, deadline - time.monotonic()))
            if self.error:
                raise AssertionError(f"WeCom WebSocket mock failed: {self.error}")
            if not self.heartbeat_frames:
                raise AssertionError("WeCom SDK heartbeat was not observed")
            return self.heartbeat_frames[-1]

    def send_text(self, content: str, *, userid: str = "e2e-user") -> tuple[str, dict[str, Any]]:
        self.wait_authenticated()
        req_id = f"e2e-callback-{uuid.uuid4().hex}"
        body = {
            "msgid": f"e2e-msg-{uuid.uuid4().hex}",
            "aibotid": "e2e-bot",
            "chattype": "single",
            "from": {"userid": userid},
            "msgtype": "text",
            "text": {"content": content},
        }
        frame = {"cmd": "aibot_msg_callback", "headers": {"req_id": req_id}, "body": body}
        with self._condition:
            self.callback_frames[req_id] = frame
            self.reply_frames[req_id] = []
        self._send_json(frame)
        return req_id, frame

    def wait_replies(
        self,
        req_id: str,
        *,
        min_count: int = 1,
        until_finish: bool = False,
        timeout: float = 45,
    ) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while time.monotonic() < deadline:
                replies = list(self.reply_frames.get(req_id, []))
                finished = any(bool((reply.get("body", {}).get("stream") or {}).get("finish")) for reply in replies)
                if len(replies) >= min_count and (finished or not until_finish):
                    return replies
                if self.error:
                    raise AssertionError(f"WeCom WebSocket mock failed: {self.error}")
                self._condition.wait(max(0.01, deadline - time.monotonic()))
        replies = list(self.reply_frames.get(req_id, []))
        raise AssertionError(
            f"timed out waiting for WeCom replies: req_id={req_id}, count={len(replies)}, until_finish={until_finish}"
        )

    def _serve(self) -> None:
        try:
            while not self._closed.is_set():
                try:
                    client, _address = self._listener.accept()
                except socket.timeout:
                    continue
                self._client = client
                client.settimeout(0.5)
                self._handshake(client)
                self._read_messages(client)
                if not self._closed.is_set():
                    with self._condition:
                        self._authenticated = False
                        self._condition.notify_all()
        except OSError as error:
            if not self._closed.is_set():
                self._set_error(str(error))
        except Exception as error:  # pragma: no cover - diagnostic guard for protocol failures
            self._set_error(str(error))

    def _handshake(self, client: socket.socket) -> None:
        request = bytearray()
        deadline = time.monotonic() + 5
        while b"\r\n\r\n" not in request:
            if time.monotonic() >= deadline:
                raise TimeoutError("WebSocket HTTP upgrade timed out")
            try:
                request.extend(client.recv(4096))
            except socket.timeout:
                continue
        headers: dict[str, str] = {}
        for line in request.decode("latin-1").split("\r\n")[1:]:
            key, separator, value = line.partition(":")
            if separator:
                headers[key.strip().lower()] = value.strip()
        websocket_key = headers.get("sec-websocket-key", "")
        if not websocket_key:
            raise ValueError("missing Sec-WebSocket-Key")
        accept = base64.b64encode(
            hashlib.sha1((websocket_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        client.sendall(response.encode("ascii"))

    def _read_messages(self, client: socket.socket) -> None:
        while not self._closed.is_set():
            try:
                opcode, payload = self._read_frame(client)
            except socket.timeout:
                continue
            except (ConnectionError, OSError):
                return
            if opcode == 0x8:
                return
            if opcode == 0x9:
                self._send_frame(payload, opcode=0xA)
                continue
            if opcode != 0x1:
                continue
            frame = json.loads(payload.decode("utf-8"))
            self._handle_json(frame)

    def _handle_json(self, frame: dict[str, Any]) -> None:
        cmd = frame.get("cmd", "")
        req_id = (frame.get("headers") or {}).get("req_id", "")
        if cmd == "aibot_subscribe":
            self.auth_frame = frame
            self._send_json({"headers": {"req_id": req_id}, "errcode": 0, "errmsg": "ok"})
            with self._condition:
                self._authenticated = True
                self._condition.notify_all()
            return
        if cmd == "ping":
            with self._condition:
                self.heartbeat_frames.append(frame)
                self._condition.notify_all()
            self._send_json({"headers": {"req_id": req_id}, "errcode": 0, "errmsg": "ok"})
            return
        if cmd.startswith("aibot_respond"):
            with self._condition:
                self.reply_frames.setdefault(req_id, []).append(frame)
                self._condition.notify_all()
            self._send_json({"headers": {"req_id": req_id}, "errcode": 0, "errmsg": "ok"})

    @staticmethod
    def _read_exact(client: socket.socket, length: int) -> bytes:
        output = bytearray()
        while len(output) < length:
            chunk = client.recv(length - len(output))
            if not chunk:
                raise ConnectionError("WebSocket connection closed")
            output.extend(chunk)
        return bytes(output)

    def _read_frame(self, client: socket.socket) -> tuple[int, bytes]:
        first, second = self._read_exact(client, 2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(client, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(client, 8))[0]
        mask = self._read_exact(client, 4) if masked else b""
        payload = self._read_exact(client, length)
        if mask:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return opcode, payload

    def _send_json(self, value: dict[str, Any]) -> None:
        self._send_frame(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def _send_frame(self, payload: bytes, *, opcode: int = 0x1) -> None:
        if not self._client:
            raise ConnectionError("WebSocket client is not connected")
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(length)
        elif length < 65536:
            header.extend([126])
            header.extend(struct.pack("!H", length))
        else:
            header.extend([127])
            header.extend(struct.pack("!Q", length))
        with self._send_lock:
            self._client.sendall(bytes(header) + payload)

    def _set_error(self, error: str) -> None:
        with self._condition:
            self.error = error
            self._condition.notify_all()
