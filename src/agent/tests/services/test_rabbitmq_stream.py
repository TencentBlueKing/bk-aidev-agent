import contextlib
import os
import queue
import threading
import time
from unittest.mock import MagicMock

import pytest
from aidev_agent.services.messages_handler.constants import EOD_CHUNK
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler
from aidev_agent.services.messages_handler.rabbitmq_stream import (
    RabbitMQStreamMessageHandler,
    _StreamSubscription,
)
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper


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


def test_flush_publishes_coalesced_messages_with_confirm():
    handler = _make_handler()
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
