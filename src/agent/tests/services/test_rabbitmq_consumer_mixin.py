import contextlib
import os
import time

import pytest
from aidev_agent.services.messages_handler.base import EOD_CHUNK
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler

pytestmark = pytest.mark.skipif(
    not os.getenv("RABBITMQ_HOST"),
    reason="Live test requires RABBITMQ_HOST",
)


@pytest.fixture()
def handler():
    RabbitMQMessageHandler._instance = None
    instance = RabbitMQMessageHandler()
    yield instance


@pytest.fixture()
def thread_id(request, handler):
    value = f"test-replay-{request.node.name}-{int(time.time() * 1000) % 100000}"
    yield value
    with contextlib.suppress(Exception):
        handler.mark_completed(value)


class TestReplayConsumers:
    def test_multiple_consumers_are_independent(self, handler, thread_id):
        first = handler.acquire_consumer(thread_id)
        second = handler.acquire_consumer(thread_id)

        assert first != second
        handler.check_consumer(thread_id, first)
        handler.check_consumer(thread_id, second)
        assert handler.has_active_consumer(thread_id) is True

        handler.release_consumer(thread_id, first)
        assert handler.has_active_consumer(thread_id) is True
        handler.release_consumer(thread_id, second)
        assert handler.has_active_consumer(thread_id) is False

    def test_consumers_replay_same_main_queue_log(self, handler, thread_id):
        expected = ["message-1", "message-2", EOD_CHUNK]
        for message in expected:
            handler.put(thread_id, message)
        handler.flush(thread_id)

        first_messages, first_offset = handler.get_messages_since(thread_id, offset=0, timeout=1)
        second_messages, second_offset = handler.get_messages_since(thread_id, offset=0, timeout=1)

        assert first_messages == expected
        assert second_messages == expected
        assert first_offset == second_offset == len(expected)
        assert handler.get_cached_count(thread_id) == len(expected)

    def test_restore_is_noop_and_legacy_get_is_rejected(self, handler, thread_id):
        handler.put(thread_id, "message")
        handler.flush(thread_id)

        assert handler.restore_messages(thread_id) == 0
        assert handler.get_dlq_messages(thread_id) == []
        with pytest.raises(NotImplementedError, match="competing-consumer"):
            handler.get(thread_id, timeout=1)


class TestResourceCleanup:
    @staticmethod
    def _queue_exists(handler, queue_name: str) -> bool:
        try:
            with handler._with_channel() as channel:
                channel.queue_declare(queue=queue_name, durable=True, passive=True)
                return True
        except Exception:
            return False

    @staticmethod
    def _exchange_exists(handler, exchange_name: str) -> bool:
        try:
            with handler._with_channel() as channel:
                channel.exchange_declare(exchange=exchange_name, passive=True)
                return True
        except Exception:
            return False

    @staticmethod
    def _declare_legacy_resources(handler, thread_id: str) -> None:
        dlq_name = f"aidev_agent.dlq.{thread_id}"
        exchange_name = f"aidev_agent.dlx.{thread_id}"
        with handler._with_channel() as channel:
            channel.exchange_declare(exchange=exchange_name, exchange_type="direct", durable=True)
            channel.queue_declare(queue=dlq_name, durable=True, arguments={"x-expires": handler.QUEUE_TTL_MS})
            channel.queue_bind(queue=dlq_name, exchange=exchange_name, routing_key=dlq_name)
            channel.queue_declare(
                queue=handler._get_queue_name(thread_id),
                durable=True,
                arguments={
                    "x-expires": handler.QUEUE_TTL_MS,
                    "x-dead-letter-exchange": exchange_name,
                    "x-dead-letter-routing-key": dlq_name,
                },
            )

    def test_main_queue_has_no_dead_letter_resources(self, handler, thread_id):
        handler.clear(thread_id)
        handler.put(thread_id, "message")
        handler.flush(thread_id)

        assert self._queue_exists(handler, handler._get_queue_name(thread_id))
        assert not self._queue_exists(handler, f"aidev_agent.dlq.{thread_id}")
        assert not self._exchange_exists(handler, f"aidev_agent.dlx.{thread_id}")

    def test_clear_migrates_and_deletes_legacy_dead_letter_resources(self, handler, thread_id):
        self._declare_legacy_resources(handler, thread_id)

        handler.clear(thread_id)
        handler.put(thread_id, "message")
        handler.flush(thread_id)

        assert self._queue_exists(handler, handler._get_queue_name(thread_id))
        assert not self._queue_exists(handler, f"aidev_agent.dlq.{thread_id}")
        assert not self._exchange_exists(handler, f"aidev_agent.dlx.{thread_id}")

    def test_mark_completed_deletes_main_and_control_queues(self, handler, thread_id):
        handler.clear(thread_id)
        handler.put(thread_id, "message")
        handler.flush(thread_id)
        consumer_id = handler.acquire_consumer(thread_id)

        main_queue = handler._get_queue_name(thread_id)
        active_queue = handler._get_active_consumer_queue_name(thread_id)
        assert self._queue_exists(handler, main_queue)
        assert self._queue_exists(handler, active_queue)

        handler.release_consumer(thread_id, consumer_id)
        handler.mark_completed(thread_id)

        assert not self._queue_exists(handler, main_queue)
        assert not self._queue_exists(handler, active_queue)
