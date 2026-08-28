# -*- coding: utf-8 -*-
"""企微机器人 WebSocket 长连接服务单元测试。"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
    views_stub.WxBotAgentRequest = type("WxBotAgentRequest", (), {})
    sys.modules["aidev_wxbot.wxaibot.views"] = views_stub
    from aidev_wxbot.wxaibot import long_connection as long_connection_module
    from aidev_wxbot.wxaibot.long_connection import (
        ActiveStream,
        LongConnectionConfigError,
        ServiceState,
        StreamMetrics,
        WxAiBotLongConnectionConfig,
        WxAiBotLongConnectionService,
    )

    sys.modules.pop("aidev_wxbot.wxaibot.views", None)

    _wxbot_available = True
except (ImportError, ModuleNotFoundError, RuntimeError):
    _wxbot_available = False


pytestmark = pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")

if _wxbot_available:
    from aidev_wxbot.wxaibot.direct_stream import AgentStream


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
        self.is_connected = False


class ThreadExecutor:
    def submit(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()
        return True


def _service(client: FakeClient | None = None) -> WxAiBotLongConnectionService:
    service = object.__new__(WxAiBotLongConnectionService)
    service._client = client or FakeClient()
    service._config = SimpleNamespace(shutdown_grace_period_sec=1)
    service._shutdown_requested = False
    service._accepting_messages = True
    service._loop = None
    service._active_streams = {}
    service._group_streams = {}
    service._metrics = StreamMetrics()
    service._view = MagicMock()
    service._frame_semaphore = asyncio.Semaphore(16)
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
    async def test_chat_sse_is_pushed_directly_without_legacy_execute(self):
        service = _service()
        service._view._get_or_create_thread_id.return_value = "thread-1"
        strategy = MagicMock()
        strategy.open_stream.return_value = AgentStream(
            kind="chat",
            session_code="session-1",
            generator=iter(
                [
                    f'data: {{"type":"TEXT_MESSAGE_CONTENT","delta":"{"a" * 50}"}}\n',
                    'data: {"type":"RUN_FINISHED","run_id":"run-1"}\n',
                ]
            ),
        )
        request = SimpleNamespace(
            content="query",
            stream_id="stream-direct",
            username="user-1",
            group_id="group-1",
        )

        with (
            patch.object(long_connection_module, "resolve_strategy", return_value=strategy),
            patch.object(long_connection_module, "get_agent_executor", return_value=ThreadExecutor()),
        ):
            await service._start_direct_stream({}, request)
            task = service._active_streams["stream-direct"].task
            await task

        strategy.open_stream.assert_called_once()
        strategy.execute.assert_not_called()
        assert service._client.reply_stream_calls == [("a" * 50, False), ("a" * 50, True)]

    async def test_agent_run_error_is_counted_as_failed_stream(self):
        service = _service()
        service._view._get_or_create_thread_id.return_value = "thread-1"
        strategy = MagicMock()
        strategy.open_stream.return_value = AgentStream(
            kind="chat",
            session_code="session-1",
            generator=iter(['data: {"type":"RUN_ERROR","message":"upstream timeout"}\n']),
        )
        request = SimpleNamespace(
            content="query",
            stream_id="stream-error",
            username="user-1",
            group_id="group-1",
        )

        with (
            patch.object(long_connection_module, "resolve_strategy", return_value=strategy),
            patch.object(long_connection_module, "get_agent_executor", return_value=ThreadExecutor()),
        ):
            await service._start_direct_stream({}, request)
            await service._active_streams["stream-error"].task

        assert service._client.reply_stream_calls == [("处理请求时发生错误: upstream timeout", True)]
        assert service._metrics.failed == 1
        assert service._metrics.completed == 0

    async def test_slow_wecom_sender_applies_bounded_backpressure(self, monkeypatch):
        class SlowClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.sending = asyncio.Event()
                self.release = asyncio.Event()

            async def reply_stream(self, _frame, _stream_id, content, finish):
                self.reply_stream_calls.append((content, finish))
                self.sending.set()
                await self.release.wait()

        client = SlowClient()
        service = _service(client)
        service._view._get_or_create_thread_id.return_value = "thread-1"
        yielded = 0

        def generator():
            nonlocal yielded
            for index in range(20):
                yielded += 1
                yield f'data: {{"type":"TEXT_MESSAGE_CONTENT","delta":"{index:02d}{"x" * 48}"}}\n'
            yield 'data: {"type":"RUN_FINISHED"}\n'

        strategy = MagicMock()
        strategy.open_stream.return_value = AgentStream("chat", generator(), "session-1")
        request = SimpleNamespace(content="query", stream_id="slow", username="user-1", group_id="group-1")
        monkeypatch.setattr(long_connection_module.settings, "WXAIBOT_WS_STREAM_BUFFER_SIZE", 1)

        with (
            patch.object(long_connection_module, "resolve_strategy", return_value=strategy),
            patch.object(long_connection_module, "get_agent_executor", return_value=ThreadExecutor()),
        ):
            await service._start_direct_stream({}, request)
            task = service._active_streams["slow"].task
            try:
                await client.sending.wait()
                await asyncio.sleep(0.05)
                assert yielded < 20
            finally:
                client.release.set()
                await task

        assert service._metrics.completed == 1

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

    async def test_long_connection_does_not_poll_legacy_rabbitmq_stream(self):
        service = _service()
        sent = AsyncMock()
        service._send_stream_reply = sent

        frame = {"body": {"msgtype": "stream", "stream": {"id": "stream-1"}}}
        await service._handle_frame(frame)

        service._view._reply_wxaibot.assert_not_called()
        sent.assert_awaited_once_with(frame, "stream-1", "长连接模式无需轮询流式结果", True)

    async def test_same_session_preemption_cancels_old_stream_and_sends_terminal(self):
        service = _service()
        old_task = asyncio.create_task(asyncio.sleep(60))
        service._active_streams["old"] = ActiveStream({}, "group-1", old_task, __import__("threading").Event(), 0)
        service._group_streams["group-1"] = "old"
        release = asyncio.Event()

        async def consume(*_args):
            await release.wait()

        service._consume_direct_stream = consume
        request = SimpleNamespace(stream_id="new", group_id="group-1")

        with patch.object(long_connection_module.stream_registry, "cancel", return_value=True) as cancel:
            await service._start_direct_stream({"frame": "new"}, request)

        cancel.assert_called_once_with("old")
        assert old_task.cancelled()
        assert ("当前会话已有新请求，原请求已结束", True) in service._client.reply_stream_calls
        assert service._group_streams["group-1"] == "new"
        release.set()
        await service._active_streams["new"].task

    async def test_cancel_stream_tasks_on_shutdown(self):
        service = _service()
        task = asyncio.create_task(asyncio.sleep(60))
        service._active_streams["stream-1"] = ActiveStream({}, "group-1", task, __import__("threading").Event(), 0)
        service._group_streams["group-1"] = "stream-1"

        with patch.object(long_connection_module.stream_registry, "cancel", return_value=True):
            await service._cancel_stream_tasks(terminal_content="服务正在停机，当前请求已取消")

        assert task.cancelled()
        assert ("服务正在停机，当前请求已取消", True) in service._client.reply_stream_calls


class TestLongConnectionLifecycle:
    @staticmethod
    def _service_with_registered_callbacks():
        class CallbackClient:
            def __init__(self):
                self.handlers = {}

            def on(self, event_name):
                def decorator(callback):
                    self.handlers[event_name] = callback
                    return callback

                return decorator

        service = object.__new__(WxAiBotLongConnectionService)
        service._client = CallbackClient()
        service._authenticated_event = MagicMock()
        service._authenticated_event.is_set.return_value = False
        service._mark_startup_failure = MagicMock()
        service._set_service_state = MagicMock()
        service._set_async_event = MagicMock()
        service._ensure_health_task = MagicMock()
        service._handle_frame = AsyncMock()
        service._register_handlers()
        return service

    def test_transient_startup_error_keeps_sdk_reconnect_alive(self):
        service = self._service_with_registered_callbacks()

        service._client.handlers["error"](RuntimeError("temporary websocket failure"))

        service._mark_startup_failure.assert_not_called()
        service._set_service_state.assert_called_once_with(
            ServiceState.RECONNECTING,
            "transient_startup_error=temporary websocket failure",
        )

    @pytest.mark.parametrize("message", ["Authentication failed: bad secret", "Max reconnect attempts exceeded"])
    def test_terminal_sdk_error_marks_startup_failure(self, message):
        service = self._service_with_registered_callbacks()

        service._client.handlers["error"](RuntimeError(message))

        service._mark_startup_failure.assert_called_once()

    def test_shutdown_request_stops_accepting_messages_and_disconnects(self):
        service = _service()
        service._service_state = ServiceState.RUNNING
        service._state_lock = __import__("threading").Lock()
        service._health_task = None

        service._request_shutdown("test")

        assert service._client.disconnected
        assert service._shutdown_requested
        assert not service._accepting_messages
        assert service._service_state == ServiceState.STOPPING

    async def test_waits_for_client_disconnect_without_sdk_wait_method(self):
        service = _service()

        service._client.disconnect()
        await service._wait_for_client_disconnected()

        assert service._client.disconnected
