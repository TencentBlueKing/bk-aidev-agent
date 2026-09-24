# -*- coding: utf-8 -*-
"""OpenClaw WebSocket 握手与生命周期终态。"""

import json

import pytest
import websocket

from aidev_agent.packages.craw.openclaw_ws import OpenClawWSError, OpenClawWSSession, _is_loopback_url


def test_unauthenticated_fallback_requires_loopback(monkeypatch):
    session = OpenClawWSSession("wss://example.com/", "token")
    handshakes = iter([[], ["operator.write"]])
    monkeypatch.setattr(session, "_handshake", lambda **_kwargs: next(handshakes))

    with pytest.raises(OpenClawWSError, match="loopback"):
        session.connect()


@pytest.mark.parametrize("url", ["ws://127.0.0.1:18789/", "ws://[::1]:18789/", "ws://localhost:18789/"])
def test_loopback_url_detection(url):
    assert _is_loopback_url(url) is True
    assert _is_loopback_url("wss://example.com/") is False


def test_handshake_uses_bounded_timeout(monkeypatch):
    class FakeWS:
        def __init__(self):
            self.messages = [
                json.dumps({"event": "connect.challenge"}),
                json.dumps({"type": "res", "ok": True, "payload": {"auth": {"scopes": ["operator.write"]}}}),
            ]
            self.timeouts = []

        def recv(self):
            return self.messages.pop(0)

        def send(self, _payload):
            return None

        def settimeout(self, value):
            self.timeouts.append(value)

    fake = FakeWS()
    captured = {}

    def create_connection(*_args, **kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(websocket, "create_connection", create_connection)
    session = OpenClawWSSession("ws://127.0.0.1:18789/", "token", timeout=300)

    assert session._handshake(with_auth=True) == ["operator.write"]
    assert captured["timeout"] == 20
    assert fake.timeouts[-1] == 300


def test_lifecycle_failure_is_not_reported_as_done():
    session = OpenClawWSSession("ws://127.0.0.1:18789/", "token")

    failed = session._translate({"stream": "lifecycle", "data": {"phase": "end", "stopReason": "error"}})
    done = session._translate({"stream": "lifecycle", "data": {"phase": "end", "stopReason": "stop"}})
    cancelled = session._translate({"stream": "lifecycle", "data": {"phase": "end", "stopReason": "aborted"}})

    assert failed.kind == "error"
    assert done.kind == "done"
    assert cancelled.kind == "cancelled"


def test_events_marks_lifecycle_end_as_confirmed_termination():
    class FakeWS:
        def recv(self):
            return json.dumps(
                {
                    "event": "agent",
                    "payload": {"stream": "lifecycle", "data": {"phase": "end", "stopReason": "aborted"}},
                }
            )

    session = OpenClawWSSession("ws://127.0.0.1:18789/", "token")
    session._ws = FakeWS()

    assert [event.kind for event in session.events()] == ["cancelled"]
    assert session.terminated is True


def test_cancel_sends_chat_abort_without_closing_transport():
    class FakeWS:
        def __init__(self):
            self.sent = []
            self.timeouts = []
            self.closed = False

        def send(self, payload):
            self.sent.append(json.loads(payload))

        def settimeout(self, value):
            self.timeouts.append(value)

        def close(self):
            self.closed = True

    session = OpenClawWSSession("ws://127.0.0.1:18789/", "token", timeout=300)
    session._ws = FakeWS()
    session.send_chat("session-1", "hello")

    assert session.cancel("session-1") is True
    assert session.cancel_requested is True
    assert session._ws.sent[-1]["method"] == "chat.abort"
    assert session._ws.sent[-1]["params"]["sessionKey"] == "session-1"
    assert session._ws.timeouts[-1] == 10
    assert session._ws.closed is False
