"""release_producer 容错单测：连接被对端重置时不应抛异常。

复现 celery 日志中 _producer 线程 release_producer → connection.channel()
抛 StreamLostError 导致 "Exception in thread" 的问题。
"""
import threading

from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler


def _make_handler():
    # 绕过单例 __new__ 与 _init_rabbitmq（后者需要真实 RabbitMQ 连接）
    handler = object.__new__(RabbitMQMessageHandler)
    handler._producer_lock_connections = {}
    handler._producer_lock_guard = threading.Lock()
    return handler


class _FakeConnection:
    """模拟已被对端重置的 RabbitMQ 连接：本地状态仍认为 open，但底层 stream 已断。"""

    def __init__(self, channel_error):
        self.is_open = True
        self._channel_error = channel_error
        self.closed = False

    def channel(self):
        raise self._channel_error

    def close(self):
        self.closed = True
        self.is_open = False


def test_release_producer_tolerates_stream_lost_error():
    """connection.channel() 抛 StreamLostError 时，release_producer 不应抛异常。"""
    from pika.exceptions import StreamLostError

    handler = _make_handler()
    thread_id = "test-stream-lost"
    conn = _FakeConnection(StreamLostError("Stream connection lost"))
    handler._producer_lock_connections[thread_id] = conn

    handler.release_producer(thread_id)  # 不应抛异常

    assert thread_id not in handler._producer_lock_connections
    assert conn.closed is True


def test_release_producer_tolerates_connection_reset_error():
    """connection.channel() 抛 ConnectionResetError 时，release_producer 不应抛异常。"""
    handler = _make_handler()
    thread_id = "test-conn-reset"
    conn = _FakeConnection(ConnectionResetError(104, "Connection reset by peer"))
    handler._producer_lock_connections[thread_id] = conn

    handler.release_producer(thread_id)

    assert thread_id not in handler._producer_lock_connections
    assert conn.closed is True


def test_release_producer_no_connection_is_safe():
    """没有待释放的连接时，release_producer 应安全返回。"""
    handler = _make_handler()
    handler.release_producer("nonexistent-thread")  # 不应抛异常
