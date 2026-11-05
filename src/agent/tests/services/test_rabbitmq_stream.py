import asyncio
import contextlib
import os
import queue
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aidev_agent.services.messages_handler.rabbitmq_stream as rabbitmq_stream_module
import pytest
from aidev_agent.services.messages_handler.constants import EOD_CHUNK
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler
from aidev_agent.services.messages_handler.rabbitmq_stream import (
    RabbitMQStreamMessageHandler,
    _RabbitMQStreamRuntime,
    _StreamSubscription,
)
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
from rstream import ConsumerOffsetSpecification, OffsetType, OnClosedErrorInfo
from rstream.connection import ConnectionClosed


def _make_handler() -> RabbitMQStreamMessageHandler:
    handler = object.__new__(RabbitMQStreamMessageHandler)
    handler._buffer_lock = threading.Lock()
    handler._message_buffer = {}
    handler._stream_count_lock = threading.Lock()
    handler._stream_counts = {}
    handler._stream_runtime = MagicMock()
    handler._get_flush_peek_lock = MagicMock(return_value=threading.Lock())
    handler._notify_eod_committed = MagicMock()
    handler._notify_replay_waiters = MagicMock()
    return handler


class _FakeClock:
    """只替换被测模块的 time.monotonic，不影响 asyncio 和锁的真实计时。"""

    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def monotonic(self) -> float:
        return self.now


def _use_fake_clock(monkeypatch) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr(rabbitmq_stream_module, "time", SimpleNamespace(monotonic=clock.monotonic))
    return clock


def _make_runtime(submit_results: list, on_submit=None) -> tuple[_RabbitMQStreamRuntime, list]:
    """构造不连接 RabbitMQ 的 runtime，按顺序模拟每次 _submit 的结果。

    on_submit(name, timeout) 可用来记录超时参数或推进假时钟。
    """
    runtime = object.__new__(_RabbitMQStreamRuntime)
    runtime._operation_timeout = 1.0
    runtime._producer_generation = 1
    runtime._producer_stale = False
    runtime._reconnect_lock = threading.Lock()
    runtime._background_closes = set()
    submitted: list = []
    results = iter(submit_results)

    def submit(coro, timeout=None):
        submitted.append(coro.__qualname__)
        coro.close()
        if on_submit is not None:
            on_submit(coro.__qualname__.rsplit(".", 1)[-1], timeout)
        result = next(results)
        if isinstance(result, BaseException):
            raise result
        if coro.__qualname__.endswith("_restart_producer"):
            runtime._producer_generation += 1
            runtime._producer_stale = False
        return result

    runtime._submit = submit
    return runtime, submitted


def _make_subscription_runtime(monkeypatch, subscribe_side_effect=None) -> tuple[_RabbitMQStreamRuntime, list[dict]]:
    """构造订阅侧 runtime，Consumer 替换为可断言的假对象。"""
    runtime, _ = _make_runtime([])
    runtime._connection_kwargs = {}
    runtime._max_age_seconds = 1
    runtime._known_streams = {"stream"}
    runtime._subscriptions = {}
    runtime._producer = MagicMock(stream_exists=AsyncMock(return_value=True))
    created: list[dict] = []

    def consumer_factory(**kwargs):
        consumer = MagicMock(
            start=AsyncMock(),
            subscribe=AsyncMock(return_value=7, side_effect=subscribe_side_effect),
            close=AsyncMock(),
        )
        created.append({"consumer": consumer, "kwargs": kwargs})
        return consumer

    monkeypatch.setattr(rabbitmq_stream_module, "Consumer", consumer_factory)
    return runtime, created


async def _hang_forever(*args, **kwargs) -> None:
    await asyncio.Event().wait()


def _submitted_names(submitted: list) -> list[str]:
    return [name.rsplit(".", 1)[-1] for name in submitted]


def test_stream_handler_inherits_rabbitmq_control_plane():
    assert issubclass(RabbitMQStreamMessageHandler, RabbitMQMessageHandler)


def test_stream_subscription_reads_arrived_batch_and_advances_offset():
    subscription = _StreamSubscription(MagicMock(), 1, "stream", next_offset=4)
    subscription.messages.put((4, "first"))
    subscription.messages.put((5, "second"))

    messages, next_offset = subscription.read(offset=4, timeout=0)

    assert messages == ["first", "second"]
    assert next_offset == 6


def test_stream_subscription_times_out_without_message():
    subscription = _StreamSubscription(MagicMock(), 1, "stream", next_offset=0)

    with pytest.raises(TimeoutError, match="No message available"):
        subscription.read(offset=0, timeout=0)


def test_flush_publishes_coalesced_messages_with_confirm(monkeypatch):
    handler = _make_handler()
    publish_metric = MagicMock()
    monkeypatch.setattr(rabbitmq_stream_module, "record_message_publish_metrics", publish_metric)
    first = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"a"}\n\n'
    second = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"b"}\n\n'
    handler._message_buffer = {"thread-id": [first, second, EOD_CHUNK]}
    handler._stream_runtime.publish.return_value = [0, 1]

    handler.flush("thread-id")

    published = handler._stream_runtime.publish.call_args.kwargs
    assert published["stream"] == "aidev_agent.stream.thread-id"
    assert len(published["payloads"]) == 2
    assert handler.get_cached_count("thread-id") == 2
    handler._notify_eod_committed.assert_called_once_with("thread-id", [first, second, EOD_CHUNK])
    metric_call = publish_metric.call_args.kwargs
    assert metric_call["handler_type"] == "rabbitmq_stream"
    assert metric_call["messaging_system"] == "rabbitmq"
    assert metric_call["event_count"] == 3
    assert len(metric_call["message_sizes"]) == 2


def test_get_messages_since_uses_native_stream_offset_and_expands_sse():
    handler = _make_handler()
    handler._stream_runtime.get_messages_since.return_value = (
        ['data: {"type":"A"}\n\ndata: {"type":"B"}\n\n'],
        8,
    )

    messages, next_offset = handler.get_messages_since("thread-id", offset=7, timeout=0.5)

    assert messages == ['data: {"type":"A"}\n\n', 'data: {"type":"B"}\n\n']
    assert next_offset == 8
    assert handler._stream_runtime.get_messages_since.call_args.kwargs["offset"] == 7


def test_has_pending_messages_checks_stream_without_history_scan():
    handler = _make_handler()
    handler._stream_runtime.stream_exists.return_value = True

    assert handler.has_pending_messages("thread-id") is True
    handler._stream_runtime.stream_exists.assert_called_once_with("aidev_agent.stream.thread-id")


def test_has_pending_messages_falls_back_when_stream_check_fails():
    handler = _make_handler()
    handler._stream_runtime.stream_exists.side_effect = TimeoutError()

    assert handler.has_pending_messages("thread-id") is False


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionError(), ConnectionClosed()])
def test_stream_exists_reconnects_and_retries_once(error):
    runtime, submitted = _make_runtime([error, None, True])

    assert runtime.stream_exists("stream") is True
    assert _submitted_names(submitted) == ["check", "_restart_producer", "check"]
    assert runtime._producer_generation == 2


def test_stream_exists_raises_when_retry_still_fails():
    runtime, submitted = _make_runtime([TimeoutError(), None, TimeoutError()])

    with pytest.raises(TimeoutError):
        runtime.stream_exists("stream")
    assert len(submitted) == 3


def test_publish_marks_producer_stale_without_retry():
    runtime, submitted = _make_runtime([TimeoutError()])

    with pytest.raises(TimeoutError):
        runtime.publish("stream", [b"payload"], publisher_name="stream", max_age_seconds=1)
    assert len(submitted) == 1
    assert runtime._producer_stale is True


def test_stale_producer_reconnects_before_next_operation():
    runtime, submitted = _make_runtime([None, None])
    runtime._producer_stale = True

    runtime.delete_stream("stream")

    assert _submitted_names(submitted) == ["_restart_producer", "_delete_stream"]


def test_reconnect_skips_when_other_thread_already_rebuilt():
    runtime, submitted = _make_runtime([])

    runtime._reconnect(failed_generation=0)

    assert submitted == []


def test_operation_stops_retrying_when_budget_is_exhausted(monkeypatch):
    clock = _use_fake_clock(monkeypatch)

    def spend_full_timeout(name, timeout):
        clock.now += timeout

    runtime, submitted = _make_runtime([TimeoutError(), None], on_submit=spend_full_timeout)

    with pytest.raises(TimeoutError, match="budget exhausted"):
        runtime.stream_exists("stream")

    # 首次操作和重建各用满一倍超时后不再重试，总耗时不超过两倍操作超时。
    assert _submitted_names(submitted) == ["check", "_restart_producer"]
    assert clock.now - 100.0 == pytest.approx(2.0)


def test_retry_uses_remaining_budget(monkeypatch):
    clock = _use_fake_clock(monkeypatch)
    timeouts: list[tuple[str, float]] = []
    elapsed = iter([0.5, 0.7, 0.0])

    def record(name, timeout):
        timeouts.append((name, timeout))
        clock.now += next(elapsed)

    runtime, _ = _make_runtime([ConnectionError(), None, True], on_submit=record)

    assert runtime.stream_exists("stream") is True
    assert [name for name, _ in timeouts] == ["check", "_restart_producer", "check"]
    assert [timeout for _, timeout in timeouts] == pytest.approx([1.0, 1.0, 0.8])


def test_stale_reconnect_shares_operation_budget(monkeypatch):
    clock = _use_fake_clock(monkeypatch)
    timeouts: list[float] = []

    def record(name, timeout):
        timeouts.append(timeout)
        clock.now += 0.6

    runtime, _ = _make_runtime([None, True], on_submit=record)
    runtime._producer_stale = True

    assert runtime.stream_exists("stream") is True
    assert timeouts == pytest.approx([1.0, 1.0])
    assert clock.now - 100.0 <= 2.0


def test_reconnect_times_out_when_lock_is_busy():
    runtime, submitted = _make_runtime([])
    runtime._operation_timeout = 0.05
    runtime._reconnect_lock.acquire()
    try:
        with pytest.raises(TimeoutError, match="waiting for RabbitMQ Stream reconnect"):
            runtime._reconnect(failed_generation=1)
    finally:
        runtime._reconnect_lock.release()
    assert submitted == []


@pytest.mark.parametrize(("reason", "stale"), [("Metadata Update", False), ("Heartbeats missing", True)])
def test_producer_close_handler_marks_stale_on_disconnect(reason, stale):
    runtime, _ = _make_runtime([])
    producer = MagicMock()
    runtime._producer = producer

    asyncio.run(runtime._on_producer_closed(producer, OnClosedErrorInfo(reason, ["stream"])))

    assert runtime._producer_stale is stale


def test_producer_close_handler_ignores_replaced_producer():
    runtime, _ = _make_runtime([])
    runtime._producer = MagicMock()

    asyncio.run(runtime._on_producer_closed(MagicMock(), OnClosedErrorInfo("Heartbeats missing", [])))

    assert runtime._producer_stale is False


def test_restart_producer_replaces_connection_and_clears_stream_cache(monkeypatch):
    runtime, _ = _make_runtime([])
    runtime._connection_kwargs = {"host": "localhost"}
    runtime._known_streams = {"stream"}
    old_producer = MagicMock(close=AsyncMock(side_effect=ConnectionClosed()))
    new_producer = MagicMock(start=AsyncMock())
    runtime._producer = old_producer
    monkeypatch.setattr(rabbitmq_stream_module, "Producer", MagicMock(return_value=new_producer))

    async def restart() -> None:
        await runtime._restart_producer()
        await asyncio.gather(*runtime._background_closes)

    asyncio.run(restart())

    old_producer.close.assert_awaited_once()
    new_producer.start.assert_awaited_once()
    assert runtime._producer is new_producer
    assert runtime._known_streams == set()
    assert (runtime._producer_generation, runtime._producer_stale) == (2, False)
    assert runtime._background_closes == set()


def test_restart_producer_does_not_wait_for_stuck_old_connection(monkeypatch):
    runtime, _ = _make_runtime([])
    runtime._connection_kwargs = {}
    runtime._known_streams = set()
    old_producer = MagicMock(close=AsyncMock(side_effect=_hang_forever))
    runtime._producer = old_producer
    monkeypatch.setattr(rabbitmq_stream_module, "Producer", MagicMock(return_value=MagicMock(start=AsyncMock())))
    monkeypatch.setattr(rabbitmq_stream_module, "_STALE_CLIENT_CLOSE_TIMEOUT", 0.05)

    async def restart() -> int:
        await asyncio.wait_for(runtime._restart_producer(), timeout=0.02)
        pending = len(runtime._background_closes)
        # 后台关闭有自己的上限，到时只记录告警，不向外抛异常。
        await asyncio.gather(*runtime._background_closes)
        return pending

    assert asyncio.run(restart()) == 1
    old_producer.close.assert_awaited_once()
    assert runtime._background_closes == set()


def test_close_async_cancels_pending_background_closes():
    runtime, _ = _make_runtime([])
    runtime._subscriptions = {}
    runtime._producer = None
    stuck_client = MagicMock(close=AsyncMock(side_effect=_hang_forever))

    async def close() -> None:
        runtime._close_in_background(stuck_client)
        await asyncio.wait_for(runtime._close_async(), timeout=0.5)

    asyncio.run(close())

    assert runtime._background_closes == set()


@pytest.mark.parametrize(
    ("state", "reason", "broken"),
    [
        ({}, None, False),
        ({"connection_closed": True}, "connection_closed", True),
        ({"idle_seconds": 11}, "idle", True),
        ({"idle_seconds": 11, "queued": True}, None, False),
        ({"stream_changed": True, "connection_closed": True, "idle_seconds": 11}, None, True),
    ],
)
def test_subscription_rebuild_reason(monkeypatch, state, reason, broken):
    clock = _use_fake_clock(monkeypatch)
    subscription = _StreamSubscription(
        MagicMock(),
        1,
        "stream",
        next_offset=0,
        connection_closed=state.get("connection_closed", False),
        stream_changed=state.get("stream_changed", False),
        last_delivery_at=clock.now - state.get("idle_seconds", 1),
    )
    if state.get("queued"):
        subscription.messages.put((0, "message"))

    assert subscription.rebuild_reason() == reason
    assert subscription.may_be_broken() is broken


def test_consumer_callbacks_track_connection_and_delivery(monkeypatch):
    clock = _use_fake_clock(monkeypatch)
    runtime, created = _make_subscription_runtime(monkeypatch)

    async def exercise() -> _StreamSubscription:
        subscription = await runtime._create_subscription((1, "thread"), "stream", 3)
        on_close = created[0]["kwargs"]["on_close_handler"]
        on_message = created[0]["consumer"].subscribe.call_args.args[1]

        await on_close(OnClosedErrorInfo("Metadata Update", ["stream"]))
        assert (subscription.stream_changed, subscription.connection_closed) == (True, False)
        await on_close(OnClosedErrorInfo("Heartbeats missing", ["stream"]))
        assert subscription.connection_closed is True

        clock.now += 30
        await on_message("payload", SimpleNamespace(offset=3))
        return subscription

    subscription = asyncio.run(exercise())

    assert subscription.subscriber_id == 7
    assert subscription.last_delivery_at == clock.now
    assert subscription.messages.get_nowait() == (3, "payload")
    assert runtime._subscriptions == {(1, "thread"): subscription}


@pytest.mark.parametrize(
    ("subscribe_side_effect", "expected_error"),
    [
        (ConnectionClosed(), ConnectionClosed),
        # 模拟 _submit 超时后取消任务，半建立的 consumer 也要关闭。
        (_hang_forever, TimeoutError),
    ],
)
def test_failed_subscribe_closes_consumer_in_background(monkeypatch, subscribe_side_effect, expected_error):
    runtime, created = _make_subscription_runtime(monkeypatch, subscribe_side_effect)

    async def exercise() -> None:
        with pytest.raises(expected_error):
            await asyncio.wait_for(runtime._create_subscription((1, "thread"), "stream", 0), timeout=0.05)
        await asyncio.gather(*runtime._background_closes)

    asyncio.run(exercise())

    created[0]["consumer"].close.assert_awaited_once()
    assert runtime._subscriptions == {}


@pytest.mark.parametrize("broken", [False, True])
def test_discard_subscription_closes_broken_consumer_in_background(broken):
    runtime, _ = _make_runtime([])
    consumer = MagicMock(close=AsyncMock(side_effect=_hang_forever if broken else None))
    subscription = _StreamSubscription(consumer, 1, "stream", next_offset=0, connection_closed=broken)

    async def discard() -> int:
        await asyncio.wait_for(runtime._discard_subscription(subscription), timeout=0.05)
        pending = len(runtime._background_closes)
        for task in runtime._background_closes:
            task.cancel()
        await asyncio.gather(*runtime._background_closes, return_exceptions=True)
        return pending

    assert asyncio.run(discard()) == int(broken)
    consumer.close.assert_awaited_once()


@pytest.mark.parametrize("broken_state", [{"connection_closed": True}, {"idle_seconds": 11}])
def test_get_subscription_rebuilds_broken_subscription_from_same_offset(monkeypatch, broken_state):
    clock = _use_fake_clock(monkeypatch)
    runtime, created = _make_subscription_runtime(monkeypatch)
    key = (1, "thread")
    old_consumer = MagicMock(close=AsyncMock())
    old_subscription = _StreamSubscription(
        old_consumer,
        1,
        "stream",
        next_offset=5,
        connection_closed=broken_state.get("connection_closed", False),
        last_delivery_at=clock.now - broken_state.get("idle_seconds", 1),
    )
    runtime._subscriptions = {key: old_subscription}

    async def exercise() -> _StreamSubscription:
        subscription = await runtime._get_subscription(key, "stream", 5)
        await asyncio.gather(*runtime._background_closes)
        return subscription

    subscription = asyncio.run(exercise())

    assert subscription is not old_subscription
    assert runtime._subscriptions[key] is subscription
    assert subscription.next_offset == 5
    assert created[0]["consumer"].subscribe.call_args.kwargs["offset_specification"] == ConsumerOffsetSpecification(
        OffsetType.OFFSET, 5
    )
    runtime._producer.stream_exists.assert_awaited_once_with("stream")
    old_consumer.close.assert_awaited_once()


def test_get_subscription_keeps_subscription_when_stream_was_deleted(monkeypatch):
    runtime, created = _make_subscription_runtime(monkeypatch)
    runtime._producer.stream_exists.return_value = False
    key = (1, "thread")
    subscription = _StreamSubscription(MagicMock(), 1, "stream", next_offset=5, connection_closed=True)
    runtime._subscriptions = {key: subscription}

    async def exercise() -> tuple[_StreamSubscription, _StreamSubscription]:
        first = await runtime._get_subscription(key, "stream", 5)
        second = await runtime._get_subscription(key, "stream", 5)
        return first, second

    assert asyncio.run(exercise()) == (subscription, subscription)
    # stream 已删除时不重建，也不重复检查，避免接到新一轮同名 stream。
    assert subscription.stream_changed is True
    runtime._producer.stream_exists.assert_awaited_once_with("stream")
    assert created == []


def test_get_subscription_reuses_healthy_subscription(monkeypatch):
    runtime, created = _make_subscription_runtime(monkeypatch)
    key = (1, "thread")
    subscription = _StreamSubscription(MagicMock(), 1, "stream", next_offset=5)
    runtime._subscriptions = {key: subscription}

    assert asyncio.run(runtime._get_subscription(key, "stream", 5)) is subscription
    runtime._producer.stream_exists.assert_not_awaited()
    assert created == []


def test_subscription_queue_is_thread_safe():
    subscription = _StreamSubscription(MagicMock(), 1, "stream", next_offset=0, messages=queue.Queue())

    threading.Thread(target=lambda: subscription.messages.put((0, "message"))).start()

    assert subscription.read(offset=0, timeout=1) == (["message"], 1)


@pytest.mark.e2e
@pytest.mark.skipif(
    not os.getenv("RABBITMQ_STREAM_PORT"),
    reason="Live test requires RABBITMQ_STREAM_PORT",
)
def test_live_stream_replays_ordered_messages_to_two_consumers():
    handler = RabbitMQStreamMessageHandler()
    thread_id = f"test-rabbitmq-stream-{time.time_ns()}"
    expected = [f"message-{index}" for index in range(20)]
    barrier = threading.Barrier(2)
    results: list[list[str]] = []

    def consume() -> None:
        barrier.wait(timeout=3)
        results.append(list(GeneratorStreamingHelper(handler, thread_id).stream(iter(expected))))

    threads = [threading.Thread(target=consume) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert all(not thread.is_alive() for thread in threads)
        assert results == [expected, expected]
    finally:
        with contextlib.suppress(Exception):
            handler.mark_completed(thread_id)
