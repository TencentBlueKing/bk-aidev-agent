import contextlib
import pickle
import threading
from unittest.mock import MagicMock

import pytest
from aidev_agent.services.messages_handler.constants import EOD_CHUNK
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler


def _make_handler(message_count: int, messages: list[str]) -> tuple[RabbitMQMessageHandler, MagicMock]:
    handler = object.__new__(RabbitMQMessageHandler)
    channel = MagicMock()
    channel.queue_declare.return_value.method.message_count = message_count

    handler._get_flush_peek_lock = MagicMock(return_value=threading.Lock())
    handler._with_replay_lock = MagicMock(return_value=contextlib.nullcontext(channel))
    handler._ensure_queue = MagicMock(return_value="replay-queue")
    handler._peek_queue_messages = MagicMock(return_value=messages)
    handler._get_dlq_count = MagicMock(return_value=0)
    handler._restore_from_dlq = MagicMock(return_value=0)
    return handler, channel


def test_get_messages_since_skips_full_peek_without_new_messages():
    handler, channel = _make_handler(message_count=835, messages=[])

    with pytest.raises(TimeoutError, match="No message available within timeout"):
        handler.get_messages_since("thread-id", offset=835, timeout=0)

    channel.queue_declare.assert_called_once_with(queue="replay-queue", durable=True, passive=True)
    handler._peek_queue_messages.assert_not_called()


def test_get_messages_since_peeks_when_queue_has_new_messages():
    messages = [f"message-{index}" for index in range(836)]
    handler, channel = _make_handler(message_count=836, messages=messages)

    new_messages, next_offset = handler.get_messages_since("thread-id", offset=835, timeout=0)

    assert new_messages == ["message-835"]
    assert next_offset == 836
    handler._peek_queue_messages.assert_called_once_with(channel, "replay-queue")


def test_get_messages_since_preserves_legacy_dlq_restore():
    handler, channel = _make_handler(message_count=0, messages=["restored-message"])
    channel.queue_declare.side_effect = [
        MagicMock(method=MagicMock(message_count=0)),
        MagicMock(method=MagicMock(message_count=1)),
    ]
    handler._get_dlq_count.return_value = 1
    handler._restore_from_dlq.return_value = 1

    messages, next_offset = handler.get_messages_since("thread-id", offset=0, timeout=0)

    assert messages == ["restored-message"]
    assert next_offset == 1
    handler._restore_from_dlq.assert_called_once_with("thread-id")
    handler._peek_queue_messages.assert_called_once_with(channel, "replay-queue")


def test_eod_commit_event_is_notified_only_after_eod_publish():
    handler = object.__new__(RabbitMQMessageHandler)
    handler._eod_commit_events = {}
    handler._eod_commit_events_lock = threading.Lock()
    event = threading.Event()

    handler.register_eod_commit_event("thread-id", event)
    handler._notify_eod_committed("thread-id", ["chunk"])
    assert not event.is_set()

    handler._notify_eod_committed("thread-id", [EOD_CHUNK])
    assert event.is_set()
    assert "thread-id" not in handler._eod_commit_events


def test_coalesce_sse_messages_preserves_mixed_order_and_eod():
    first = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"a"}\n\n'
    second = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"b"}\n\n'
    third = 'data: {"type":"RUN_FINISHED"}\n\n'

    messages = RabbitMQMessageHandler._coalesce_sse_messages([first, second, "legacy-message", third, EOD_CHUNK])

    assert messages == [first + second, "legacy-message", third, EOD_CHUNK]


def test_expand_sse_messages_restores_original_frames():
    first = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"a"}\n\n'
    second = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"b"}\n\n'

    messages = RabbitMQMessageHandler._expand_sse_messages([first + second, "legacy-message", EOD_CHUNK])

    assert messages == [first, second, "legacy-message", EOD_CHUNK]


def test_coalesce_sse_messages_splits_by_utf8_bytes(monkeypatch):
    first = "data: 一\n\n"
    second = "data: 二\n\n"
    monkeypatch.setattr(RabbitMQMessageHandler, "SSE_PUBLISH_CHUNK_MAX_BYTES", len(first.encode("utf-8")))

    messages = RabbitMQMessageHandler._coalesce_sse_messages([first, second])

    assert messages == [first, second]


def test_put_requests_flush_after_one_thread_reaches_event_limit():
    handler = object.__new__(RabbitMQMessageHandler)
    handler._message_buffer = {}
    handler._buffer_flush_requests = set()
    handler._buffer_lock = threading.Lock()
    handler._buffer_flush_event = threading.Event()
    handler._ensure_daemon_alive = MagicMock()
    handler._notify_replay_waiters = MagicMock()

    for index in range(handler.SSE_BUFFER_MAX_EVENTS - 1):
        handler.put("busy-thread", f"data: {index}\n\n")
    handler.put("idle-thread", "data: idle\n\n")
    assert not handler._buffer_flush_event.is_set()

    handler.put("busy-thread", "data: threshold\n\n")
    assert handler._buffer_flush_event.is_set()
    assert handler._buffer_flush_requests == {"busy-thread"}


def test_threshold_flush_does_not_flush_other_threads():
    handler = object.__new__(RabbitMQMessageHandler)
    channel = MagicMock()
    handler._message_buffer = {"busy-thread": ["data: busy\n\n"], "idle-thread": ["data: idle\n\n"]}
    handler._buffer_flush_requests = {"busy-thread", "idle-thread"}
    handler._buffer_lock = threading.Lock()
    handler._get_flush_peek_lock = MagicMock(return_value=threading.Lock())
    handler._with_channel = MagicMock(return_value=contextlib.nullcontext(channel))
    handler._ensure_queue = MagicMock(return_value="replay-queue")
    handler._notify_eod_committed = MagicMock()
    handler._notify_replay_waiters = MagicMock()

    handler._flush_messages({"busy-thread"})

    published = [pickle.loads(call.kwargs["body"]) for call in channel.basic_publish.call_args_list]
    assert published == ["data: busy\n\n"]
    assert handler._message_buffer == {"idle-thread": ["data: idle\n\n"]}
    assert handler._buffer_flush_requests == {"idle-thread"}


def test_threshold_wakeup_does_not_postpone_periodic_flush(monkeypatch):
    handler = object.__new__(RabbitMQMessageHandler)
    handler._daemon_running = True
    handler._daemon_stop_event = threading.Event()
    handler._buffer_flush_event = MagicMock()
    handler._buffer_flush_event.wait.side_effect = [True, False]
    handler._buffer_flush_requests = {"busy-thread"}
    handler._buffer_lock = threading.Lock()
    flush_calls = []

    def flush(thread_ids=None):
        flush_calls.append(thread_ids)
        if len(flush_calls) == 2:
            handler._daemon_running = False

    handler._flush_messages = flush
    monotonic = MagicMock(side_effect=[0.0, 0.1, 0.1, 0.4, 0.5])
    monkeypatch.setattr("aidev_agent.services.messages_handler.rabbitmq.time.monotonic", monotonic)

    handler._daemon_worker()

    wait_timeouts = [call.kwargs["timeout"] for call in handler._buffer_flush_event.wait.call_args_list]
    assert wait_timeouts == pytest.approx([0.4, 0.1])
    assert flush_calls == [{"busy-thread"}, None, None]


def test_flush_publishes_coalesced_sse_and_eod():
    handler = object.__new__(RabbitMQMessageHandler)
    first = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"a"}\n\n'
    second = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"b"}\n\n'
    channel = MagicMock()
    handler._buffer_lock = threading.Lock()
    handler._message_buffer = {"thread-id": [first, second, EOD_CHUNK]}
    handler._buffer_flush_requests = set()
    handler._get_flush_peek_lock = MagicMock(return_value=threading.Lock())
    handler._with_channel = MagicMock(return_value=contextlib.nullcontext(channel))
    handler._ensure_queue = MagicMock(return_value="replay-queue")
    handler._notify_eod_committed = MagicMock()
    handler._notify_replay_waiters = MagicMock()

    handler.flush("thread-id")

    published = [pickle.loads(call.kwargs["body"]) for call in channel.basic_publish.call_args_list]
    assert published == [first + second, EOD_CHUNK]
    handler._notify_eod_committed.assert_called_once_with("thread-id", [first, second, EOD_CHUNK])


def test_get_messages_since_replays_mixed_physical_messages():
    first = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"a"}\n\n'
    second = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"b"}\n\n'
    stored_messages = ["legacy-message", first + second, EOD_CHUNK]
    handler, _ = _make_handler(message_count=3, messages=stored_messages)

    messages, next_offset = handler.get_messages_since("thread-id", offset=1, timeout=0)

    assert messages == [first, second, EOD_CHUNK]
    assert next_offset == 3
