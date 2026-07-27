"""RabbitMQ handler 进程内 buffer 状态机测试。

与 ``test_rabbitmq_handler.py`` 不同，这里不连接真实 broker，因此在没有
``RABBITMQ_HOST`` 的 CI 上同样执行，用于守住 flush / in-flight 的并发语义。
"""

import contextlib
import pickle
import threading
from typing import Any

import pytest
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler

THREAD_ID = "buffer-state-thread"


@pytest.fixture()
def handler(monkeypatch):
    """构造不连接 broker 的 handler，只保留进程内 buffer 行为。"""
    monkeypatch.setattr(RabbitMQMessageHandler, "_instance", None)
    monkeypatch.setattr(RabbitMQMessageHandler, "_start_daemon", lambda self: None)
    monkeypatch.setattr(RabbitMQMessageHandler, "_ensure_daemon_alive", lambda self: None)
    return RabbitMQMessageHandler()


def _install_fake_channel(handler, monkeypatch, fail: bool = False) -> list[Any]:
    """把 publish 路径换成内存记录，返回已发布消息列表。"""
    published: list[Any] = []

    class _FakeChannel:
        def basic_publish(self, exchange, routing_key, body, properties=None):  # noqa: ARG002
            if fail:
                raise RuntimeError("publish failed")
            published.append(pickle.loads(body))

    @contextlib.contextmanager
    def fake_with_channel():
        yield _FakeChannel()

    monkeypatch.setattr(handler, "_with_channel", fake_with_channel)
    monkeypatch.setattr(handler, "_ensure_queue", lambda channel, thread_id: f"queue-{thread_id}")
    return published


def _trace_take_entry(handler, monkeypatch) -> threading.Event:
    """在 flush 真正尝试取 buffer 时置位，避免用 sleep 猜测线程进度。"""
    entered = threading.Event()
    original = handler._take_thread_buffer_for_flush

    def traced(thread_id, wait_for_in_flight=None):
        entered.set()
        return original(thread_id, wait_for_in_flight=wait_for_in_flight)

    monkeypatch.setattr(handler, "_take_thread_buffer_for_flush", traced)
    return entered


class TestFlushInFlightSemantics:
    def test_explicit_flush_waits_for_in_flight_batch(self, handler, monkeypatch):
        """daemon 批次在途时，显式 flush 必须等它结束并把后到的消息发出去。

        直接跳过会让 producer 收尾投递的 EOD_CHUNK 滞留在 buffer。
        """
        published = _install_fake_channel(handler, monkeypatch)
        handler.put(THREAD_ID, "msg_0")
        assert handler._take_thread_buffer_for_flush(THREAD_ID) == ["msg_0"]

        handler.put(THREAD_ID, "msg_1")
        entered = _trace_take_entry(handler, monkeypatch)
        flush_thread = threading.Thread(target=handler.flush, args=(THREAD_ID,), daemon=True)
        flush_thread.start()

        assert entered.wait(timeout=3)
        handler._finish_thread_flush(THREAD_ID)
        flush_thread.join(timeout=3)

        assert not flush_thread.is_alive()
        assert published == ["msg_1"]

    def test_explicit_flush_gives_up_after_wait_timeout(self, handler, monkeypatch):
        """in-flight 迟迟不结束时，显式 flush 超时放弃而不是无限期挂住调用方。"""
        _install_fake_channel(handler, monkeypatch)
        monkeypatch.setattr(RabbitMQMessageHandler, "FLUSH_IN_FLIGHT_WAIT_SEC", 0.1)
        handler.put(THREAD_ID, "msg_0")
        handler._take_thread_buffer_for_flush(THREAD_ID)
        handler.put(THREAD_ID, "msg_1")

        handler.flush(THREAD_ID)

        with handler._buffer_lock:
            assert handler._message_buffer[THREAD_ID] == ["msg_1"]

    def test_daemon_flush_skips_thread_with_in_flight_batch(self, handler, monkeypatch):
        """daemon 轮询遇到 in-flight 直接跳过，不阻塞其它 thread 的推送。"""
        published = _install_fake_channel(handler, monkeypatch)
        handler.put(THREAD_ID, "msg_0")
        handler._take_thread_buffer_for_flush(THREAD_ID)
        handler.put(THREAD_ID, "msg_1")
        handler.put("other-thread", "other_0")

        handler._flush_messages()

        assert published == ["other_0"]

    def test_in_flight_batch_counts_as_pending(self, handler):
        """消息已从 buffer 取走但尚未 publish 时仍属于 pending。"""
        handler.put(THREAD_ID, "msg_0")
        handler._take_thread_buffer_for_flush(THREAD_ID)

        assert handler.has_pending_messages(THREAD_ID) is True

    def test_failed_flush_restores_batch_ahead_of_later_messages(self, handler, monkeypatch):
        """publish 失败要把本批放回 buffer 头部，保持会话日志顺序。"""
        _install_fake_channel(handler, monkeypatch, fail=True)
        handler.put(THREAD_ID, "msg_0")

        def put_later_message(*args, **kwargs):  # noqa: ARG001
            handler.put(THREAD_ID, "msg_1")
            return f"queue-{THREAD_ID}"

        monkeypatch.setattr(handler, "_ensure_queue", put_later_message)

        with pytest.raises(RuntimeError):
            handler.flush(THREAD_ID)

        with handler._buffer_lock:
            assert handler._message_buffer[THREAD_ID] == ["msg_0", "msg_1"]
            assert THREAD_ID not in handler._flushing_threads
