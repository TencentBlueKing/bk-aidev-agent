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

    assert failed.kind == "error"
    assert done.kind == "done"
