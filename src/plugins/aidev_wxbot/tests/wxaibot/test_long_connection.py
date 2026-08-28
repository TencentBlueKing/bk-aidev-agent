# -*- coding: utf-8 -*-
"""企微机器人 WebSocket 长连接服务单元测试。"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
import time
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
    from aidev_wxbot.wxaibot.constants import (
        BUSY_BY_OTHERS_REPLY,
        BUSY_REPLY,
        PREPARING_REPLY,
        STOP_NO_ACTIVE_REPLY,
        STOP_NOTICE,
        STOP_REPLY,
    )
    from aidev_wxbot.wxaibot.long_connection import (
        ActiveStream,
        LongConnectionConfigError,
        ServiceState,
        StreamMetrics,
        WxAiBotLongConnectionConfig,
        WxAiBotLongConnectionService,
        _LongConnectionViewSet,
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


class TestAgentStreamDrain:
    """收尾只排空 Agent 统一流接口，不由长连接操作消息缓存。"""

    def test_remaining_frames_are_drained(self):
        consumed = 0

        def generator():
            nonlocal consumed
            for _ in range(6):
                consumed += 1
                yield "frame"

        WxAiBotLongConnectionService._drain_stream_frames(generator(), "stream-1")

        assert consumed == 6

    def test_blocking_next_does_not_bypass_drain_timeout(self, monkeypatch):
        """即使 next() 本身阻塞，wxbot worker 也只能等待配置的上限。"""
        monkeypatch.setattr(long_connection_module, "AGENT_STREAM_DRAIN_TIMEOUT", 0.01)
        entered = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def blocking_generator():
            try:
                entered.set()
                release.wait()
                yield "frame"
            finally:
                finished.set()

        started = time.monotonic()
        WxAiBotLongConnectionService._drain_stream_frames(blocking_generator(), "stream-1")
        elapsed = time.monotonic() - started

        assert entered.is_set()
        assert elapsed < 0.2
        release.set()
        assert finished.wait(timeout=1)

    def test_drain_failure_does_not_propagate(self):
        """上游收尾异常不能再打断 wxbot worker。"""

        def exploding():
            yield "frame"
            raise RuntimeError("upstream reset")

        WxAiBotLongConnectionService._drain_stream_frames(exploding(), "stream-1")

    def test_long_connection_does_not_import_message_handler_factory(self):
        assert not hasattr(long_connection_module, "message_handler_factory")

    async def test_worker_drains_the_unified_stream_when_it_ends(self):
        """接线检查：worker 的 finally 只排空统一帧迭代器。"""
        service = _service()
        service._view._get_or_create_thread_id.return_value = "thread-1"
        strategy = MagicMock()
        strategy.open_stream.return_value = AgentStream("chat", iter(['data: {"type":"RUN_FINISHED"}\n']), "session-1")
        request = SimpleNamespace(content="q", stream_id="stream-1", username="u", group_id="group-1")

        with (
            patch.object(long_connection_module, "resolve_strategy", return_value=strategy),
            patch.object(long_connection_module, "get_agent_executor", return_value=ThreadExecutor()),
            patch.object(WxAiBotLongConnectionService, "_drain_stream_frames") as drain,
        ):
            await service._start_direct_stream({}, request)
            await service._active_streams["stream-1"].task

        drain.assert_called_once()


class TestStopCommand:
    """/stop 必须真正停掉在跑的流，而不只是回一句话。"""

    @staticmethod
    async def _wait_for_replies(client: FakeClient) -> None:
        for _ in range(100):
            if client.reply_stream_calls:
                return
            await asyncio.sleep(0.01)

    async def test_request_stop_keeps_what_was_already_delivered(self):
        """企微 stream 是全量快照，终态帧必须带上已输出内容，否则半截回答会被抹掉。"""
        service = _service()
        service._loop = asyncio.get_running_loop()
        cancel_event = threading.Event()
        task = asyncio.create_task(asyncio.sleep(60))
        active = ActiveStream({}, "group-1", "u", task, cancel_event, 0)
        active.last_content = "已经输出的半截回答"
        service._active_streams["stream-1"] = active
        service._group_streams["group-1"] = "stream-1"

        with patch.object(long_connection_module, "stream_registry") as registry:
            # 解析在 to_thread 里跑，这里同样跨线程调用，覆盖真实调用姿势
            stopped = await asyncio.to_thread(service.request_stop, "group-1", "u", reason="user_stop")
            # 取消位与 Agent 侧通知都必须在返回前完成，否则 /stop 回执发出后旧回复还会继续刷
            assert cancel_event.is_set()
            registry.cancel.assert_called_with("stream-1")
            await self._wait_for_replies(service._client)

        assert stopped is True
        assert service._client.reply_stream_calls == [(f"已经输出的半截回答\n\n{STOP_NOTICE}", True)]
        assert service._metrics.cancelled == 1

    async def test_stop_mid_stream_keeps_the_partial_answer(self):
        """端到端：推送路径必须把快照记到 ActiveStream 上，/stop 才有内容可带。

        前两个用例是直接给 last_content 赋值的，只有本用例能证明记账这一步真的接上了。
        """

        class PauseOnSecondFrameClient(FakeClient):
            def __init__(self):
                super().__init__()
                self.paused = asyncio.Event()
                self.release = asyncio.Event()

            async def reply_stream(self, frame, stream_id, content, finish):
                await super().reply_stream(frame, stream_id, content, finish)
                # 卡在第二帧：此时第一帧的发送已经返回并完成记账，正是 /stop 落下的时机。
                # 若卡在第一帧，发送尚未返回，记账那行还没执行，测不到真实场景。
                if len(self.reply_stream_calls) == 2:
                    self.paused.set()
                    await self.release.wait()

        client = PauseOnSecondFrameClient()
        service = _service(client)
        service._loop = asyncio.get_running_loop()
        service._view._get_or_create_thread_id.return_value = "thread-1"

        def generator():
            for _ in range(4):
                yield f'data: {{"type":"TEXT_MESSAGE_CONTENT","delta":"{"答" * 60}"}}\n'
            yield 'data: {"type":"RUN_FINISHED"}\n'

        strategy = MagicMock()
        strategy.open_stream.return_value = AgentStream("chat", generator(), "session-1")
        request = SimpleNamespace(content="q", stream_id="stream-1", username="u", group_id="group-1")

        with (
            patch.object(long_connection_module, "resolve_strategy", return_value=strategy),
            patch.object(long_connection_module, "get_agent_executor", return_value=ThreadExecutor()),
            # 只挡住通往 Agent 框架的那一步，注册表本身要用真的：
            # 换成 MagicMock 会让 is_cancel_requested 恒为真值，生产者一开始就退出
            patch("aidev_wxbot.wxaibot.stream_registry.GeneratorStreamingHelper.cancel", return_value=True),
        ):
            await service._start_direct_stream({}, request)
            try:
                await asyncio.wait_for(client.paused.wait(), timeout=2)
                delivered = client.reply_stream_calls[0][0]
                await asyncio.to_thread(service.request_stop, "group-1", "u", reason="user_stop")
            finally:
                client.release.set()
            for _ in range(200):
                if client.reply_stream_calls[-1][1]:
                    break
                await asyncio.sleep(0.01)

        assert delivered
        assert client.reply_stream_calls[-1] == (f"{delivered}\n\n{STOP_NOTICE}", True)

    async def test_request_stop_before_any_output_falls_back_to_a_placeholder(self):
        """一帧都没推出去就被停掉时，终态帧要有占位文案，不能只剩一个孤零零的括号。"""
        service = _service()
        service._loop = asyncio.get_running_loop()
        task = asyncio.create_task(asyncio.sleep(60))
        service._active_streams["stream-1"] = ActiveStream({}, "group-1", "u", task, threading.Event(), 0)
        service._group_streams["group-1"] = "stream-1"

        with patch.object(long_connection_module, "stream_registry"):
            await asyncio.to_thread(service.request_stop, "group-1", "u", reason="user_stop")
            await self._wait_for_replies(service._client)

        assert service._client.reply_stream_calls == [(f"{PREPARING_REPLY}\n\n{STOP_NOTICE}", True)]

    async def test_request_stop_without_active_stream(self):
        service = _service()
        service._loop = asyncio.get_running_loop()

        stopped = await asyncio.to_thread(service.request_stop, "group-1", "u", reason="user_stop")

        assert stopped is False
        assert service._client.reply_stream_calls == []

    async def test_request_stop_only_touches_its_own_group(self):
        service = _service()
        service._loop = asyncio.get_running_loop()
        other_event = threading.Event()
        other_task = asyncio.create_task(asyncio.sleep(60))
        service._active_streams["stream-other"] = ActiveStream({}, "group-other", "u", other_task, other_event, 0)
        service._group_streams["group-other"] = "stream-other"

        stopped = await asyncio.to_thread(service.request_stop, "group-1", "u", reason="user_stop")

        assert stopped is False
        assert not other_event.is_set()
        other_task.cancel()

    async def test_request_stop_refuses_to_touch_someone_elses_stream(self):
        """群里每个人的上下文各自独立，谁都能掐掉别人的回复不合理。"""
        service = _service()
        service._loop = asyncio.get_running_loop()
        cancel_event = threading.Event()
        task = asyncio.create_task(asyncio.sleep(60))
        service._active_streams["stream-1"] = ActiveStream({}, "g", "alice", task, cancel_event, 0)
        service._group_streams["g"] = "stream-1"

        stopped = await asyncio.to_thread(service.request_stop, "g", "bob", reason="user_stop")

        assert stopped is False
        assert not cancel_event.is_set()
        assert service._client.reply_stream_calls == []
        task.cancel()

    def test_viewset_reports_whether_anything_was_stopped(self):
        service = MagicMock()
        view = object.__new__(_LongConnectionViewSet)
        view._service = service

        service.request_stop.return_value = True
        assert view.stop_generation("group-1", "u", "s1")["stream"]["content"] == STOP_REPLY

        service.request_stop.return_value = False
        assert view.stop_generation("group-1", "u", "s1")["stream"]["content"] == STOP_NO_ACTIVE_REPLY


class TestSessionScope:
    """会话轮换的粒度必须和上下文的粒度对齐。

    上下文本来就是每人一份（session_code 由 username 参与哈希），但 thread_id 原先
    按群存一行，于是 /new 和 30 分钟超时都成了全群连坐。
    """

    @staticmethod
    def _view() -> _LongConnectionViewSet:
        return object.__new__(_LongConnectionViewSet)

    def test_group_members_rotate_their_sessions_independently(self):
        view = self._view()

        assert view._session_scope("chat-1", "alice") != view._session_scope("chat-1", "bob")

    def test_single_chat_scope_stays_the_bare_user_id(self):
        # 单聊的 group_id 就是发起人，再拼一次只会让升级后的老会话平白失效
        assert self._view()._session_scope("alice", "alice") == "alice"


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

        strategy.open_stream.assert_called_once_with(
            content="query",
            username="user-1",
            thread_id="thread-1",
            group_id="group-1",
            retry_strategy="sdk",
        )
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

    async def test_same_group_second_request_is_rejected_with_a_stop_hint(self):
        """同会话只允许一条流：直接拒绝并告诉用户怎么办，不排队也不抢占。"""
        service = _service()
        release = asyncio.Event()

        async def consume(*_args):
            await release.wait()

        service._consume_direct_stream = consume

        with patch.object(long_connection_module.stream_registry, "cancel", return_value=True) as cancel:
            await service._start_direct_stream(
                {}, SimpleNamespace(stream_id="active", username="u", group_id="group-1")
            )
            await service._start_direct_stream(
                {}, SimpleNamespace(stream_id="second", username="u", group_id="group-1")
            )

        # 拒绝不是抢占：正在跑的那条不能被顺手停掉
        cancel.assert_not_called()
        assert list(service._active_streams) == ["active"]
        assert service._metrics.rejected_busy == 1
        # 必须是终态帧，否则企微会一直等这条流的后续内容
        assert service._client.reply_stream_calls == [(BUSY_REPLY, True)]
        release.set()
        await service._cancel_stream_tasks()

    async def test_busy_hint_does_not_tell_you_to_stop_someone_elses_reply(self):
        """名额被别人占着时不能提示 /stop：/stop 只作用于自己，照做也停不掉。"""
        service = _service()
        release = asyncio.Event()

        async def consume(*_args):
            await release.wait()

        service._consume_direct_stream = consume
        await service._start_direct_stream({}, SimpleNamespace(stream_id="active", username="alice", group_id="g"))
        await service._start_direct_stream({}, SimpleNamespace(stream_id="second", username="bob", group_id="g"))

        assert service._client.reply_stream_calls == [(BUSY_BY_OTHERS_REPLY, True)]
        release.set()
        await service._cancel_stream_tasks()

    async def test_group_accepts_a_new_request_after_the_active_stream_ends(self):
        """拒绝模式下没有出队动作，会话占用只能靠流结束时清理，漏了就会永久锁死该会话。"""
        service = _service()
        releases = {"first": asyncio.Event(), "second": asyncio.Event()}

        async def consume(_frame, request, _cancel_event):
            await releases[request.stream_id].wait()

        service._consume_direct_stream = consume
        await service._start_direct_stream({}, SimpleNamespace(stream_id="first", username="u", group_id="group-1"))
        first_task = service._active_streams["first"].task

        releases["first"].set()
        await first_task
        await asyncio.sleep(0)  # 让 done callback 完成清理
        assert not service._group_streams

        await service._start_direct_stream({}, SimpleNamespace(stream_id="second", username="u", group_id="group-1"))

        assert list(service._active_streams) == ["second"]
        assert service._metrics.rejected_busy == 0
        assert service._client.reply_stream_calls == []
        releases["second"].set()
        await service._cancel_stream_tasks()

    async def test_different_groups_start_concurrently(self):
        service = _service()
        started = {group_id: asyncio.Event() for group_id in ("group-1", "group-2")}
        release = asyncio.Event()

        async def consume(_frame, request, _cancel_event):
            started[request.group_id].set()
            await release.wait()

        service._consume_direct_stream = consume
        for group_id in started:
            request = SimpleNamespace(stream_id=f"stream-{group_id}", username="u", group_id=group_id)
            await service._start_direct_stream({}, request)

        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started.values())), timeout=1)
        assert len(service._active_streams) == 2
        await service._cancel_stream_tasks()

    async def test_cancel_stream_tasks_on_shutdown(self):
        service = _service()
        task = asyncio.create_task(asyncio.sleep(60))
        service._active_streams["stream-1"] = ActiveStream({}, "group-1", "u", task, __import__("threading").Event(), 0)
        service._group_streams["group-1"] = "stream-1"
        service._active_streams["stream-1"].last_content = "半截回答"

        with patch.object(long_connection_module.stream_registry, "cancel", return_value=True):
            await service._cancel_stream_tasks(notice="（服务正在停机，本次回复已中断）")

        assert task.cancelled()
        # 停机同样不能抹掉用户已经看到的内容
        assert service._client.reply_stream_calls == [("半截回答\n\n（服务正在停机，本次回复已中断）", True)]


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

    def test_health_log_exposes_stream_metrics(self, caplog):
        service = _service()
        service._service_state = ServiceState.RUNNING
        service._metrics.started = 3
        service._metrics.rejected_busy = 2
        executor = SimpleNamespace(
            active=1,
            pending=0,
            max_workers=10,
            max_pending=16,
            capacity=26,
            submitted=2,
            rejected=0,
            peak_active=2,
            peak_pending=1,
        )

        with (
            patch.object(long_connection_module, "get_agent_executor_snapshot", return_value=executor),
            caplog.at_level(logging.INFO, logger=long_connection_module.__name__),
        ):
            service._log_health()

        assert "streams_started=3" in caplog.text
        # 被拒次数是判断「用户是不是一直在撞正在生成」的唯一线索
        assert "streams_rejected_busy=2" in caplog.text

    async def test_waits_for_client_disconnect_without_sdk_wait_method(self):
        service = _service()

        service._client.disconnect()
        await service._wait_for_client_disconnected()

        assert service._client.disconnected
