"""共享 stream 的真实 broker 测试，需要本机 Stream、AMQP 和 Redis 配置。"""

import multiprocessing
import os
import time
import uuid

import pytest
from aidev_agent.services.messages_handler.rabbitmq_stream import RabbitMQStreamMessageHandler
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper


class _LiveHandler(RabbitMQStreamMessageHandler):
    _instance = None


def _read(handler, session, cursor, count):
    received = []
    deadline = time.monotonic() + 10
    while len(received) < count:
        remaining = deadline - time.monotonic()
        assert remaining > 0
        batch, cursor = handler.get_messages_since(session, cursor, remaining)
        received.extend(batch)
    return received, cursor


def _reader(pipe, session, cursor, count):
    handler = _LiveHandler()
    pipe.send(_read(handler, session, cursor, count))
    pipe.recv()


def _read_then_disconnect(session, cursor, count):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    worker = context.Process(target=_reader, args=(child, session, cursor, count))
    worker.start()
    child.close()
    try:
        assert parent.poll(30), "reader did not return before deadline"
        return parent.recv()
    finally:
        worker.kill()
        worker.join(10)
        parent.close()


@pytest.mark.e2e
@pytest.mark.skipif(
    not all(os.getenv(name) for name in ("RABBITMQ_STREAM_PORT", "MESSAGE_REDIS_URL")),
    reason="requires a real stream broker and Redis",
)
def test_shared_stream_worker_resume_and_cleanup(monkeypatch):
    group = uuid.uuid4().hex
    monkeypatch.setenv("RABBITMQ_STREAM_SHARED_GROUP", group)
    monkeypatch.delenv("RABBITMQ_STREAM_SHARED_SHARDS", raising=False)
    handler = _LiveHandler()
    a, b = f"{group}-a", f"{group}-b"
    stream = handler._get_stream_name(a)
    assert stream == handler._get_stream_name(b)

    def publish(session, message):
        handler.put(session, message)
        handler.flush(session)

    try:
        publish(b, "b1")
        publish(a, "a1")
        first, cursor = _read_then_disconnect(a, 0, 1)
        assert first == ["a1"]
        publish(b, "b2")
        publish(a, "a2")
        publish(b, "b3")
        publish(a, "a3")
        resumed, end = _read_then_disconnect(a, cursor, 2)
        assert resumed == ["a2", "a3"]
        assert end > cursor + 2
        history, b_cursor = _read(handler, b, 0, 3)
        assert history == ["b1", "b2", "b3"]
        assert handler.get_cached_count(a) == handler.get_cached_count(b) == 3

        for finish in (handler.mark_completed, handler.clear):
            finish(a)
            assert handler._stream_runtime.stream_exists(stream)
            assert not handler.has_pending_messages(a)
            assert handler.has_pending_messages(b)
            publish(b, "still-live")
            batch, b_cursor = _read(handler, b, b_cursor, 1)
            assert batch == ["still-live"]
            publish(a, "new-run")
            assert _read(handler, a, 0, 1)[0] == ["new-run"]
        assert _read_then_disconnect(b, 0, 5)[0] == ["b1", "b2", "b3", "still-live", "still-live"]
        helper = GeneratorStreamingHelper(handler, f"{group}-helper")
        assert list(helper.stream(iter(["hello", "world"]))) == ["hello", "world"]
    finally:
        for session in (a, b, f"{group}-helper"):
            handler.mark_completed(session)
        handler._stream_runtime.delete_stream(stream)
        handler._stop_daemon()
        handler._stream_runtime.close()
        handler._sessions.close()
        _LiveHandler._instance = None
