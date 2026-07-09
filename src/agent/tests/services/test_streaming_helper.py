"""GeneratorStreamingHelper 队列生命周期相关的单元测试。

这些用例全部使用 mock handler，不依赖真实 RabbitMQ，覆盖“队列过多”修复引入的
新逻辑：活跃 producer 探测（``_has_active_producer``）与延迟清理的 defer 决策
（仍有活跃 producer / consumer 时不回收会话日志，避免误删进行中的会话）。
"""

import threading
import time
from unittest.mock import MagicMock

from aidev_agent.services.messages_handler import EOD_CHUNK, GeneratorStreamingHelper
from aidev_agent.services.messages_handler.base import ReplayGapError


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


class TestReplayGapRecovery:
    """队列头部被 prune、消费者游标落到被删段之前时，消费循环重拉快照补齐再续。"""

    def _make_handler(self, get_side_effect) -> MagicMock:
        handler = MagicMock()
        handler.supports_replay_from_start.return_value = True
        handler.check_cancel_signal.return_value = False
        handler.is_cancel_requested.return_value = False
        handler.get_messages_since.side_effect = get_side_effect
        return handler

    def test_consumer_resyncs_snapshot_on_replay_gap(self):
        handler = self._make_handler(
            [
                ReplayGapError(thread_id="t", since_seq=1, min_seq=4),
                ([EOD_CHUNK], 4),
            ]
        )
        helper = GeneratorStreamingHelper(handler, "t")

        snapshot_calls = []

        def _provider():
            snapshot_calls.append(1)
            return ["data: SNAPSHOT\n\n"]

        gen = helper._consume_stream_messages(
            consumer_id="c",
            cancel_event=threading.Event(),
            is_resuming=True,
            enable_heartbeat_check=False,
            snapshot_provider=_provider,
        )
        out = list(gen)

        # gap 时重拉了一次快照并 yield 给下游
        assert snapshot_calls == [1]
        assert "data: SNAPSHOT\n\n" in out
        # 第二次读取用重置后的游标 min_seq-1=3
        assert handler.get_messages_since.call_count == 2
        second_call = handler.get_messages_since.call_args_list[1]
        assert second_call.args[1] == 3

    def test_replay_gap_without_provider_skips_segment(self):
        """无 snapshot_provider 时不崩溃：跳过被删段、游标重置后继续。"""
        handler = self._make_handler(
            [
                ReplayGapError(thread_id="t", since_seq=1, min_seq=4),
                ([EOD_CHUNK], 4),
            ]
        )
        helper = GeneratorStreamingHelper(handler, "t")

        gen = helper._consume_stream_messages(
            consumer_id="c",
            cancel_event=threading.Event(),
            is_resuming=True,
            enable_heartbeat_check=False,
            snapshot_provider=None,
        )
        out = list(gen)

        assert out == []  # 无快照可补，但不抛异常
        assert handler.get_messages_since.call_count == 2
        assert handler.get_messages_since.call_args_list[1].args[1] == 3
