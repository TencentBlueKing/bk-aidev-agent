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


def test_ensure_queue_does_not_declare_dead_letter_resources():
    handler = object.__new__(RabbitMQMessageHandler)
    channel = MagicMock()

    queue_name = handler._ensure_queue(channel, "thread-id")

    assert queue_name == "aidev_agent.thread.thread-id"
    channel.queue_declare.assert_called_once_with(
        queue=queue_name,
        durable=True,
        arguments={"x-expires": handler.QUEUE_TTL_MS},
    )
    channel.exchange_declare.assert_not_called()
    channel.queue_bind.assert_not_called()


def test_legacy_get_is_not_supported():
    handler = object.__new__(RabbitMQMessageHandler)

    with pytest.raises(NotImplementedError, match="competing-consumer"):
        handler.get("thread-id", timeout=1)


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


def test_cancel_signal_reuses_rolling_release_queue_without_redeclare():
    handler = object.__new__(RabbitMQMessageHandler)
    channel = MagicMock()
    handler._with_channel = MagicMock(return_value=contextlib.nullcontext(channel))

    assert handler.set_cancel_signal("thread-id", run_id="run-current")

    channel.queue_declare.assert_called_once_with(queue="aidev_agent.cancel.thread-id", passive=True)
    channel.basic_publish.assert_called_once()


def test_cancel_signal_reads_legacy_unscoped_payload():
    handler = object.__new__(RabbitMQMessageHandler)
    channel = MagicMock()
    method_frame = MagicMock(delivery_tag=1)
    channel.basic_get.return_value = (method_frame, None, b"1")
    handler._with_channel = MagicMock(return_value=contextlib.nullcontext(channel))

    assert handler.check_cancel_signal("thread-id", run_id="run-current")
    channel.basic_reject.assert_called_once_with(delivery_tag=1, requeue=True)


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


def test_flush_publishes_coalesced_sse_and_eod():
    handler = object.__new__(RabbitMQMessageHandler)
    first = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"a"}\n\n'
    second = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"b"}\n\n'
    channel = MagicMock()
    handler._buffer_lock = threading.Lock()
    handler._message_buffer = {"thread-id": [first, second, EOD_CHUNK]}
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
