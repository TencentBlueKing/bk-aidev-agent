import contextlib
import threading
from unittest.mock import MagicMock

import pytest
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
