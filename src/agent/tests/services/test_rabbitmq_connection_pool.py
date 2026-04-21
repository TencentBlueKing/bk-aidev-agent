"""单元测试：RabbitMQConnectionPool 连接池契约 + channel 零泄漏回归

对应 `.local/docs/202604/rabbitmq.md`：
- 阶段 A：`connection()` 不再跨 yield 重试，NoFreeChannels 等业务异常原样上抛；
  StreamLost 等「连接本身损坏」异常关连接、不归还、`_created_count` 递减。
- 阶段 B：`MultiProcessMixin._channel()` 是获取 channel 的唯一入口，保证 close 被调用。

这些测试全部基于 mock，不依赖真实 RabbitMQ。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pika
import pytest
from aidev_agent.services.messages_handler.multi_process_mixin import MultiProcessMixin
from aidev_agent.services.messages_handler.rabbitmq import (
    RabbitMQConnectionPool,
    RabbitMQMessageHandler,
)

# ==================== Fixtures ====================


@pytest.fixture()
def fake_connection_factory():
    """返回一个可控的 BlockingConnection 工厂：
    - is_open 默认 True
    - process_data_events 不抛（保证 _is_connection_valid 判真）
    - channel() 每次返回一个新的计数 channel（is_open=True / close() 记录一次）
    """

    def _factory() -> MagicMock:
        conn = MagicMock(name="BlockingConnection")
        conn.is_open = True
        conn.process_data_events = MagicMock(return_value=None)

        def _new_channel() -> MagicMock:
            ch = MagicMock(name="Channel")
            ch.is_open = True

            def _close() -> None:
                ch.is_open = False

            ch.close.side_effect = _close
            return ch

        conn.channel = MagicMock(side_effect=_new_channel)
        conn.close = MagicMock()
        return conn

    return _factory


@pytest.fixture()
def pool(fake_connection_factory):
    """用 fake connection 替换 _create_connection 的连接池实例"""
    p = RabbitMQConnectionPool(rabbitmq_url="amqp://fake", pool_size=2, connection_timeout=1.0)
    with patch.object(p, "_create_connection", side_effect=fake_connection_factory) as _:
        yield p


# ==================== 连接池契约 ====================


class TestConnectionPoolContract:
    """验证 `connection()` 上下文管理器的契约（根因 2 修复回归）"""

    def test_normal_flow_returns_connection_to_pool(self, pool):
        """正常 yield 完成，连接归还到池，_created_count 不漂移"""
        with pool.connection() as conn:
            assert conn.is_open
        # 归还后池中应有 1 条可用连接
        assert pool.available_count == 1
        assert pool.created_count == 1

    def test_nofreechannels_raised_as_is_not_masked_by_runtime_error(self, pool):
        """yield 内抛 NoFreeChannels，必须原样上抛；
        禁止出现 `RuntimeError: generator didn't stop after throw()`。
        """
        with pytest.raises(pika.exceptions.NoFreeChannels), pool.connection() as conn:
            assert conn.is_open
            raise pika.exceptions.NoFreeChannels()

    def test_nofreechannels_connection_returned_to_pool(self, pool):
        """NoFreeChannels 并非连接损坏，连接应当归还而非关闭"""
        with pytest.raises(pika.exceptions.NoFreeChannels), pool.connection():
            raise pika.exceptions.NoFreeChannels()
        # 连接仍在池中，_created_count 不变
        assert pool.available_count == 1
        assert pool.created_count == 1

    @pytest.mark.parametrize(
        "exc",
        [
            pika.exceptions.StreamLostError("stream lost"),
            pika.exceptions.ConnectionClosedByBroker(reply_code=320, reply_text="broker"),
            pika.exceptions.ConnectionWrongStateError("wrong state"),
            ConnectionResetError("conn reset"),
            BrokenPipeError("broken pipe"),
        ],
    )
    def test_broken_connection_is_closed_and_created_count_decremented(self, pool, exc):
        """yield 内抛「连接本身损坏」异常：
        - 关闭连接
        - _created_count 递减
        - 异常原样上抛
        """
        captured_conn: list = []
        with pytest.raises(type(exc)), pool.connection() as conn:
            captured_conn.append(conn)
            raise exc

        assert len(captured_conn) == 1
        captured_conn[0].close.assert_called_once()
        # 连接已关闭，不应归还到池
        assert pool.available_count == 0
        assert pool.created_count == 0

    def test_amqp_channel_error_is_not_caught_connection_returned(self, pool):
        """AMQPChannelError 不应被连接池 catch，连接仍可用应归还"""
        with pytest.raises(pika.exceptions.AMQPChannelError), pool.connection():
            raise pika.exceptions.AMQPChannelError("channel-level error")
        assert pool.available_count == 1
        assert pool.created_count == 1

    def test_create_connection_retries_on_acquire_failure(self, fake_connection_factory):
        """get_connection 内部对创建失败做有限重试（最多 3 次）"""
        p = RabbitMQConnectionPool(rabbitmq_url="amqp://fake", pool_size=1, connection_timeout=1.0)
        # 前两次失败、第三次成功
        attempts = {"n": 0}

        def _flaky_create():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise pika.exceptions.AMQPConnectionError("temporary")
            return fake_connection_factory()

        with patch.object(p, "_create_connection", side_effect=_flaky_create), p.connection() as conn:
            assert conn.is_open
        assert attempts["n"] == 3


# ==================== _channel() 契约 ====================


class _DummyMixinHost(MultiProcessMixin):
    """最小宿主类：仅用于测试 _channel() 方法"""


class TestChannelContextManager:
    """验证 MultiProcessMixin._channel() 保证 channel 被关闭"""

    def test_normal_exit_closes_channel(self, fake_connection_factory):
        host = _DummyMixinHost()
        conn = fake_connection_factory()
        with host._channel(conn) as ch:
            assert ch.is_open
        ch.close.assert_called_once()

    def test_exception_exit_still_closes_channel(self, fake_connection_factory):
        host = _DummyMixinHost()
        conn = fake_connection_factory()
        captured = []
        with pytest.raises(RuntimeError), host._channel(conn) as ch:
            captured.append(ch)
            raise RuntimeError("boom")
        assert len(captured) == 1
        captured[0].close.assert_called_once()

    def test_close_failure_is_suppressed(self, fake_connection_factory):
        """channel.close() 抛异常不得向上扩散（避免掩盖业务异常）"""
        host = _DummyMixinHost()
        conn = fake_connection_factory()

        ch = MagicMock(name="Channel")
        ch.is_open = True
        ch.close.side_effect = RuntimeError("close failed")
        conn.channel = MagicMock(return_value=ch)

        with host._channel(conn) as channel:
            assert channel is ch
        ch.close.assert_called_once()


# ==================== RabbitMQMessageHandler 热点函数零泄漏 ====================


class _CountingConnection:
    """mock connection：统计 channel() 与 close() 次数"""

    def __init__(self):
        self.is_open = True
        self.created: list = []

    def channel(self):
        ch = MagicMock(name=f"Channel#{len(self.created)}")
        ch.is_open = True
        # queue_declare 默认返回含 message_count=0 的 frame
        method = MagicMock()
        method.method.message_count = 0
        ch.queue_declare.return_value = method
        # basic_get 默认无消息
        ch.basic_get.return_value = (None, None, None)

        def _close() -> None:
            ch.is_open = False

        ch.close.side_effect = _close
        self.created.append(ch)
        return ch

    def process_data_events(self, time_limit=0):
        return None

    def close(self):
        self.is_open = False

    @property
    def channel_count(self) -> int:
        return len(self.created)

    @property
    def close_count(self) -> int:
        return sum(1 for ch in self.created if not ch.is_open)


@pytest.fixture()
def handler_with_counting_conn(monkeypatch):
    """构造一个 RabbitMQMessageHandler 实例，其连接池使用 _CountingConnection"""
    # 重置单例
    RabbitMQMessageHandler._instance = None

    # 避免构造函数真的起 daemon 线程
    monkeypatch.setattr(RabbitMQMessageHandler, "_start_daemon", lambda self: None)
    # 构造时 _get_rabbitmq_url 需要可用（不实际连接）
    monkeypatch.setenv("RABBITMQ_HOST", "fake-host")

    handler = RabbitMQMessageHandler()

    counting_conn = _CountingConnection()

    # 替换 _with_connection：直接 yield 计数 connection
    import contextlib

    @contextlib.contextmanager
    def _fake_with_connection(_self=handler):
        yield counting_conn

    monkeypatch.setattr(handler, "_with_connection", _fake_with_connection)

    yield handler, counting_conn

    RabbitMQMessageHandler._instance = None


class TestChannelLeakRegression:
    """验证关键热点函数调用一次后：channel 开启数 == 关闭数（零泄漏）"""

    def test_check_consumer_no_leak(self, handler_with_counting_conn):
        handler, conn = handler_with_counting_conn
        # 让 consumer queue 被动声明通过、basic_get 无消息 → 认为通过
        handler.check_consumer("tid-1", "consumer-123")
        assert conn.channel_count >= 1
        assert conn.channel_count == conn.close_count

    def test_get_available_messages_no_leak(self, handler_with_counting_conn):
        handler, conn = handler_with_counting_conn
        result = handler._get_available_messages("tid-2")
        assert result == []
        assert conn.channel_count >= 1
        assert conn.channel_count == conn.close_count

    def test_has_pending_messages_no_leak_uses_independent_channels(self, handler_with_counting_conn):
        """has_pending_messages 对主队列和 DLQ 使用独立 channel，两处都要关"""
        handler, conn = handler_with_counting_conn
        handler.has_pending_messages("tid-3")
        # 至少使用了 2 个 channel（主队列 + DLQ）
        assert conn.channel_count >= 2
        assert conn.channel_count == conn.close_count

    def test_flush_messages_no_leak(self, handler_with_counting_conn):
        handler, conn = handler_with_counting_conn
        # 放 1 条消息到 buffer，再手动触发 flush
        handler._message_buffer["tid-4"] = ["payload-1"]
        handler._flush_messages()
        assert conn.channel_count >= 1
        assert conn.channel_count == conn.close_count

    def test_many_iterations_no_channel_leak_accumulation(self, handler_with_counting_conn):
        """模拟 SSE 消费主循环：连续 50 次 check_consumer，channel 应被全部关闭"""
        handler, conn = handler_with_counting_conn
        for _ in range(50):
            handler.check_consumer("tid-loop", "consumer-xyz")
        assert conn.channel_count == 50
        assert conn.close_count == 50
