"""GeneratorStreamingHelper 队列生命周期相关的单元测试。

这些用例全部使用 mock handler，不依赖真实 RabbitMQ，覆盖“队列过多”修复引入的
新逻辑：活跃 producer 探测（``_has_active_producer``）与延迟清理的 defer 决策
（仍有活跃 producer / consumer 时不回收会话日志，避免误删进行中的会话）。
"""

import time
from unittest.mock import MagicMock

from aidev_agent.services.messages_handler import GeneratorStreamingHelper


class _HandlerWithoutProducerAPI:
    """不实现 has_active_producer 的旧 handler 替身。"""


class TestHasActiveProducer:
    def test_returns_false_when_handler_lacks_method(self):
        """handler 不支持探测时按“无活跃 producer”处理，沿用旧行为。"""
        helper = GeneratorStreamingHelper(_HandlerWithoutProducerAPI(), "tid")
        assert helper._has_active_producer() is False

    def test_delegates_to_handler_result(self):
        handler = MagicMock()
        handler.has_active_producer.return_value = True
        helper = GeneratorStreamingHelper(handler, "tid")
        assert helper._has_active_producer() is True
        handler.has_active_producer.assert_called_once_with("tid")

        handler.has_active_producer.return_value = False
        assert helper._has_active_producer() is False

    def test_conservative_true_on_exception(self):
        """探测抛异常时保守返回 True，宁可交由 TTL 兜底也不误删。"""
        handler = MagicMock()
        handler.has_active_producer.side_effect = RuntimeError("broker down")
        helper = GeneratorStreamingHelper(handler, "tid")
        assert helper._has_active_producer() is True


def _make_cleanup_helper(handler: MagicMock) -> GeneratorStreamingHelper:
    helper = GeneratorStreamingHelper(handler, "tid")
    # 缩短延迟清理窗口，保证测试快速且确定性
    helper._PRODUCER_CLEANUP_DELAY = 0.1
    helper._DONE_ORPHAN_CLEANUP_GRACE = 0.1
    helper._ORPHAN_CLEANUP_POLL_INTERVAL = 0.02
    return helper


def _wait(predicate, timeout: float = 1.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class TestOrphanCleanupGuard:
    def test_defers_cleanup_while_producer_active(self):
        """到达清理时机但仍有活跃 producer 时，不得回收会话日志。"""
        handler = MagicMock()
        handler.has_pending_messages.return_value = True
        handler.has_active_consumer.return_value = False
        handler.has_active_producer.return_value = True

        helper = _make_cleanup_helper(handler)
        helper._schedule_session_cleanup(done_event_seen=False)

        # 等待超过延迟窗口后，仍不应触发 mark_completed
        time.sleep(0.4)
        handler.mark_completed.assert_not_called()

    def test_defers_cleanup_while_consumer_active(self):
        """仍有活跃 consumer 时同样不回收，交由消费者完成/断开时的清理路径兜底。"""
        handler = MagicMock()
        handler.has_pending_messages.return_value = True
        handler.has_active_consumer.return_value = True
        handler.has_active_producer.return_value = False

        helper = _make_cleanup_helper(handler)
        helper._schedule_session_cleanup(done_event_seen=False)

        time.sleep(0.4)
        handler.mark_completed.assert_not_called()

    def test_cleans_up_when_orphaned(self):
        """确实孤立（无活跃 consumer、无活跃 producer）时才回收会话日志。"""
        handler = MagicMock()
        handler.has_pending_messages.return_value = True
        handler.has_active_consumer.return_value = False
        handler.has_active_producer.return_value = False

        helper = _make_cleanup_helper(handler)
        helper._schedule_session_cleanup(done_event_seen=False)

        assert _wait(lambda: handler.mark_completed.called, timeout=1.0)
        handler.mark_completed.assert_called_once_with("tid")

    def test_skips_when_no_pending_messages(self):
        """会话已无 pending 消息时直接跳过，不做任何清理动作。"""
        handler = MagicMock()
        handler.has_pending_messages.return_value = False

        helper = _make_cleanup_helper(handler)
        helper._schedule_session_cleanup(done_event_seen=False)

        time.sleep(0.3)
        handler.mark_completed.assert_not_called()
