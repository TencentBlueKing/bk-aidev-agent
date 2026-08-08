# -*- coding: utf-8 -*-
"""企微机器人 WebSocket 长连接服务单元测试。"""

from __future__ import annotations

import asyncio
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aidev_wxbot.settings")

try:
    import django
    from django.conf import settings

    settings.SECRET_KEY = "test-secret-key"
    settings.AIDEV_AGENT = "aidev_agent.services.common_agent.CommonQAAgent"
    settings.INSTALLED_APPS = [*settings.INSTALLED_APPS, "aidev_bkplugin"]
    django.setup()

    # long_connection 只需持有 ViewSet；将重量级业务视图替换为测试桩，避免加载
    # bk-plugin-framework 和真实 Agent 执行链。
    views_stub = types.ModuleType("aidev_wxbot.wxaibot.views")
    views_stub.WxAiBotViewSet = type("WxAiBotViewSet", (), {})
    sys.modules["aidev_wxbot.wxaibot.views"] = views_stub
    from aidev_wxbot.wxaibot import long_connection as long_connection_module
    from aidev_wxbot.wxaibot.long_connection import (
        LongConnectionConfigError,
        ServiceState,
        WxAiBotLongConnectionConfig,
        WxAiBotLongConnectionService,
    )

    sys.modules.pop("aidev_wxbot.wxaibot.views", None)

    _wxbot_available = True
except (ImportError, ModuleNotFoundError, RuntimeError):
    _wxbot_available = False


pytestmark = pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")


class FakeClient:
    def __init__(self, failures: int = 0):
        self.is_connected = True
        self.failures = failures
        self.reply_stream_calls: list[tuple[str, bool]] = []
        self.disconnected = False

    async def reply_stream(self, _frame, _stream_id, content, finish):
        self.reply_stream_calls.append((content, finish))
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary websocket failure")

    def disconnect(self):
        self.disconnected = True

    async def wait_for_complete(self):
        return None


def _service(client: FakeClient | None = None) -> WxAiBotLongConnectionService:
    service = object.__new__(WxAiBotLongConnectionService)
    service._client = client or FakeClient()
    service._config = SimpleNamespace(shutdown_grace_period_sec=1)
    service._shutdown_requested = False
    service._accepting_messages = True
    service._loop = None
    service._stream_tasks = {}
    return service


class TestLongConnectionConfig:
    def test_validates_required_credentials(self):
        with pytest.raises(LongConnectionConfigError, match="BKAPP_WXAIBOT_WS_BOT_ID"):
            WxAiBotLongConnectionConfig(bot_id="", secret="secret").validate()

        with pytest.raises(LongConnectionConfigError, match="BKAPP_WXAIBOT_WS_SECRET"):
            WxAiBotLongConnectionConfig(bot_id="bot", secret="").validate()

    @pytest.mark.parametrize(
        "field",
        [
            "reconnect_interval_ms",
            "heartbeat_interval_ms",
            "request_timeout_ms",
            "startup_timeout_sec",
            "shutdown_grace_period_sec",
        ],
    )
    def test_rejects_non_positive_timing_values(self, field):
        config = WxAiBotLongConnectionConfig(bot_id="bot", secret="secret")
        setattr(config, field, 0)

        with pytest.raises(LongConnectionConfigError):
            config.validate()


@pytest.mark.asyncio
class TestLongConnectionStreaming:
    async def test_retries_stream_reply_after_temporary_failure(self, monkeypatch):
        client = FakeClient(failures=1)
        service = _service(client)
        monkeypatch.setattr(long_connection_module.asyncio, "sleep", AsyncMock())

        await service._send_stream_reply({}, "stream-1", "answer", True)

        assert client.reply_stream_calls == [("answer", True), ("answer", True)]

    async def test_waits_for_reconnection_before_stream_reply(self, monkeypatch):
        client = FakeClient()
        client.is_connected = False
        service = _service(client)

        async def reconnect(_delay):
            client.is_connected = True

        monkeypatch.setattr(long_connection_module.asyncio, "sleep", reconnect)

        await service._send_stream_reply({}, "stream-1", "answer", False)

        assert client.reply_stream_calls == [("answer", False)]

    async def test_forwarder_sends_new_snapshots_and_stops_on_finish(self, monkeypatch):
        service = _service()
        responses = iter(
            [
                {"stream": {"content": "partial", "finish": False}},
                {"stream": {"content": "partial", "finish": False}},
                {"stream": {"content": "complete", "finish": True}},
            ]
        )
        sent = AsyncMock()
        service._poll_stream_response = lambda _stream_id: next(responses)
        service._send_stream_reply = sent
        monkeypatch.setattr(long_connection_module.asyncio, "sleep", AsyncMock())

        await service._forward_stream_replies({}, "stream-1")

        assert sent.await_args_list == [
            (({}, "stream-1", "partial", False),),
            (({}, "stream-1", "complete", True),),
        ]

    async def test_does_not_create_duplicate_forwarders_for_same_stream(self):
        service = _service()
        started = asyncio.Event()
        release = asyncio.Event()

        async def forward(_frame, _stream_id):
            started.set()
            await release.wait()

        service._forward_stream_replies = forward
        service._start_stream_forwarder({}, "stream-1")
        await started.wait()
        first_task = service._stream_tasks["stream-1"]

        service._start_stream_forwarder({}, "stream-1")

        assert service._stream_tasks["stream-1"] is first_task
        release.set()
        await first_task

    async def test_cancel_stream_tasks_on_shutdown(self):
        service = _service()
        task = asyncio.create_task(asyncio.sleep(60))
        service._stream_tasks["stream-1"] = task

        await service._cancel_stream_tasks()

        assert task.cancelled()


class TestLongConnectionLifecycle:
    def test_shutdown_request_stops_accepting_messages_and_disconnects(self):
        service = _service()
        service._service_state = ServiceState.RUNNING
        service._state_lock = __import__("threading").Lock()

        service._request_shutdown("test")

        assert service._client.disconnected
        assert service._shutdown_requested
        assert not service._accepting_messages
        assert service._service_state == ServiceState.STOPPING
