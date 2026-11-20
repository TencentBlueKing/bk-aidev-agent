"""在真实 broker 上验证 Stream 异常回收，每个用例使用独立票据队列。"""

import multiprocessing
import os
import threading
import time
import uuid

import pytest
from aidev_agent.services.messages_handler.rabbitmq_stream import RabbitMQStreamMessageHandler
from aidev_agent.services.messages_handler.stream_cleanup import StreamCleanupQueue
from pika.exceptions import ChannelClosedByBroker

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not os.getenv("RABBITMQ_STREAM_PORT"), reason="requires live Stream broker"),
]


class _Handler(RabbitMQStreamMessageHandler):
    _instance = None
    QUEUE_TTL_MS = 2000


def _start(queue):
    StreamCleanupQueue.NAME = queue
    StreamCleanupQueue.POLL_SECONDS = 0.15
    return _Handler()


def _worker(pipe, queue, session, role):
    h = _start(queue)
    if role == "producer":
        assert h.acquire_producer(session)
        h.put(session, "before crash")
        h.flush(session)
    else:
        h.acquire_consumer(session)
        h.get_messages_since(session, 0, 5)
    pipe.send(True)
    pipe.recv()


def _kill_participant(queue, session, role):
    ctx = multiprocessing.get_context("spawn")
    recv, send = ctx.Pipe()
    worker = ctx.Process(target=_worker, args=(send, queue, session, role))
    worker.start()
    send.close()
    try:
        assert recv.poll(20) and recv.recv()
    finally:
        worker.kill()
        worker.join(10)
        recv.close()
    assert worker.exitcode


def _until(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "timed out waiting for broker state"
        time.sleep(0.1)


@pytest.fixture
def recovery(monkeypatch):
    queue = "test.stream.cleanup." + uuid.uuid4().hex
    monkeypatch.setattr(StreamCleanupQueue, "NAME", queue)
    monkeypatch.setattr(StreamCleanupQueue, "POLL_SECONDS", 0.15)
    yield queue
    h = _Handler._instance
    if h:
        h._cleanup.stop_event.set()
        h._cleanup.thread.join(10)
        h._stop_daemon()
        with h._with_channel() as channel:
            channel.queue_delete(queue)
        h._stream_runtime.close()
        _Handler._instance = None


def test_crashed_reader_reaped_while_other_reader_and_producer_live(recovery):
    h = _Handler()
    dead, live, read_only = (uuid.uuid4().hex for _ in range(3))
    assert h.acquire_producer(live)
    for session in (dead, live, read_only):
        h.put(session, "first")
        h.flush(session)
    consumer = h.acquire_consumer(read_only)
    try:
        _kill_participant(recovery, dead, "consumer")
        _until(lambda: not h._stream_runtime.stream_exists(h._get_stream_name(dead)))
        assert h._stream_runtime.stream_exists(h._get_stream_name(live))
        assert h.get_messages_since(read_only, 0, 5)[0] == ["first"]
        h.put(live, "second")
        h.flush(live)
        messages, offset = h.get_messages_since(live, 0, 5)
        if messages == ["first"]:
            messages += h.get_messages_since(live, offset, 5)[0]
        assert messages == ["first", "second"]
    finally:
        h.release_consumer(read_only, consumer)
        h.release_producer(live)
        h.mark_completed(live)
        h.mark_completed(read_only)


def test_new_worker_reclaims_stream_without_eod(recovery):
    session = uuid.uuid4().hex
    _kill_participant(recovery, session, "producer")
    h = _Handler()
    stream = h._get_stream_name(session)
    assert h._stream_runtime.stream_exists(stream)
    _until(lambda: not h._stream_runtime.stream_exists(stream))


def test_broker_check_failure_retains_ticket(recovery, monkeypatch):
    h = _Handler()
    session = uuid.uuid4().hex
    h.put(session, "data")
    h.flush(session)
    stream = h._get_stream_name(session)
    failed = threading.Event()
    reap = h._reap_if_idle

    def observe(*args, **kwargs):
        try:
            return reap(*args, **kwargs)
        except ChannelClosedByBroker as error:
            if error.reply_code == 405:
                failed.set()
            raise

    monkeypatch.setattr(h, "_reap_if_idle", observe)
    connection = h._create_dedicated_connection()
    try:
        connection.channel().queue_declare(h._get_active_consumer_queue_name(session), exclusive=True)
        assert failed.wait(15)
        assert h._stream_runtime.stream_exists(stream)
    finally:
        connection.close()
    _until(lambda: not h._stream_runtime.stream_exists(stream))


def test_backfill_preexisting_stream(recovery):
    h = _Handler()
    session = uuid.uuid4().hex
    stream = h._get_stream_name(session)
    with h._with_channel() as channel:
        channel.queue_declare(stream, durable=True, arguments={"x-queue-type": "stream"})
    assert h._stream_runtime.stream_exists(stream)
    h.schedule_orphan_check(session)
    _until(lambda: not h._stream_runtime.stream_exists(stream))


def test_foreign_worker_cleanup_preserves_other_publisher(recovery):
    h = _Handler()
    h._cleanup.stop_event.set()
    h._cleanup.thread.join(10)
    finished, live = uuid.uuid4().hex, uuid.uuid4().hex
    for session in (finished, live):
        assert h.acquire_producer(session)
        h.put(session, "first")
        h.flush(session)
    h.release_producer(finished)
    ctx = multiprocessing.get_context("spawn")
    recv, send = ctx.Pipe()
    worker = ctx.Process(target=_worker, args=(send, recovery, live, "consumer"))
    worker.start()
    send.close()
    try:
        assert recv.poll(20) and recv.recv()
        _until(lambda: not h._stream_runtime.stream_exists(h._get_stream_name(finished)))
        h.put(live, "second")
        h.flush(live)
        messages, cursor = h.get_messages_since(live, 0, 5)
        if messages == ["first"]:
            messages += h.get_messages_since(live, cursor, 5)[0]
        assert messages == ["first", "second"]
    finally:
        worker.kill()
        worker.join(10)
        recv.close()
        h.release_producer(live)
        h.clear(live)
