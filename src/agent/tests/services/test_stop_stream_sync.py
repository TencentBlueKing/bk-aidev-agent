"""测试 stop 接口与 SSE 流的同步机制

核心验证：
1. Consumer 仅在收到取消终态/EOD 或 producer 已退出后发送取消通知
2. 普通正常结束不会发送取消通知
3. stop 接口 cancel → wait → 超时降级 的完整流程
4. 端到端：cancel 后流正确终止并通知
5. 完整停止时序：stop → cancel → Agent cancel_checker → RUN_FINISHED →
   EOD → Consumer notify → stop wait → 调用平台 API
"""

import threading
import time

import aidev_agent.services.messages_handler.streaming_helper as streaming_helper_module
import pytest
from aidev_agent.services.messages_handler import (
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
)
from aidev_agent.services.messages_handler.constants import TimeoutConfig
from aidev_agent.utils.event import RunId, emit_run_finished_event


class TestConsumerNotifyOnCancel:
    """验证 Consumer 仅在 cancel/stop 相关场景下发送 notify_consumer_cancelled"""

    @pytest.fixture
    def handler(self):
        handler = InMemoryQueueMessageHandler()
        yield handler
        for thread_id in handler.list_thread_ids():
            handler.clear(thread_id)
        handler._stopped_sessions.clear()
        handler._consumer_cancelled_events.clear()

    def test_cancel_triggers_notify(self, handler):
        """cancel 后 Consumer 退出时应触发 notify_consumer_cancelled

        注意：当 generator 自行检测到 cancel 并退出时，Producer 发的是 EOD_CHUNK（正常结束），
        Consumer 走正常结束路径，不会 yield STOPPED_CHUNK。核心验证点是 notify 是否被触发。
        """
        tid = "test_sync_cancel_notify"
        collected = []
        stream_started = threading.Event()
        completion_order = []
        original_mark_completed = handler.mark_completed
        original_notify = handler.notify_consumer_cancelled

        def mark_completed(thread_id):
            completion_order.append("cleanup")
            return original_mark_completed(thread_id)

        def notify_consumer_cancelled(thread_id, run_id=None):
            completion_order.append("notify")
            return original_notify(thread_id, run_id=run_id)

        handler.mark_completed = mark_completed
        handler.notify_consumer_cancelled = notify_consumer_cancelled

        def slow_gen():
            for i in range(20):
                stream_started.set()
                if GeneratorStreamingHelper.is_cancelled(tid, handler):
                    return
                time.sleep(0.05)
                yield f"chunk_{i}"

        def consume():
            helper = GeneratorStreamingHelper(handler, thread_id=tid)
            collected.extend(helper.stream(slow_gen()))

        t = threading.Thread(target=consume)
        t.start()
        stream_started.wait(timeout=2.0)
        time.sleep(0.1)

        # 发送取消信号
        GeneratorStreamingHelper.cancel(tid, handler)

        # 核心断言：等待 Consumer 退出通知
        notified = handler.wait_for_consumer_cancelled(tid, timeout=5.0)
        t.join(timeout=3.0)

        assert notified, "Consumer 退出后应发送 notify"
        assert len(collected) < 20, "应只收到部分 chunk"
        assert not t.is_alive()
        assert completion_order[-2:] == ["cleanup", "notify"]

    def test_normal_finish_does_not_trigger_notify(self, handler):
        """普通正常结束（无 cancel/stop）时不应触发 notify"""
        tid = "test_sync_eod_notify"

        def short_gen():
            yield "chunk_0"
            yield "chunk_1"

        helper = GeneratorStreamingHelper(handler, thread_id=tid)
        result = list(helper.stream(short_gen()))

        assert result == ["chunk_0", "chunk_1"]
        # 普通完成不属于 stop/cancel 流程，不应发取消通知
        assert not handler.wait_for_consumer_cancelled(tid, timeout=0.2)

    def test_non_cooperative_generator_triggers_notify(self, handler, monkeypatch):
        """generator 不主动检查 cancel 时，producer 仍输出标准取消终态并通知。"""
        tid = "test_sync_drain_timeout_notify"
        collected = []

        # 缩短 drain 超时为 0.5 秒
        monkeypatch.setattr(GeneratorStreamingHelper, "CANCEL_DRAIN_TIMEOUT", 0.5)
        # 缩短心跳
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 0.05)
        monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 10.0)

        gen_started = threading.Event()

        def hanging_gen():
            """模拟一个取消后不退出的 generator（不检查 cancel 状态）"""
            for i in range(200):
                gen_started.set()
                time.sleep(0.05)
                yield f"chunk_{i}"

        def consume():
            helper = GeneratorStreamingHelper(handler, thread_id=tid)
            collected.extend(helper.stream(hanging_gen()))

        t = threading.Thread(target=consume)
        t.start()
        gen_started.wait(timeout=2.0)
        time.sleep(0.2)  # 让一些 chunk 产出

        GeneratorStreamingHelper.cancel(tid, handler)

        # 核心断言：producer 输出取消终态和 EOD 后，notify 被触发
        notified = handler.wait_for_consumer_cancelled(tid, timeout=10.0)
        t.join(timeout=10.0)

        assert notified, "producer 取消完成后应发送 notify"
        assert not t.is_alive()


class TestStopWaitStreamFinish:
    """验证 stop 接口的等待逻辑（模拟 builtin.py 中的 stop 方法）"""

    @pytest.fixture
    def handler(self):
        handler = InMemoryQueueMessageHandler()
        yield handler
        for thread_id in handler.list_thread_ids():
            handler.clear(thread_id)
        handler._stopped_sessions.clear()
        handler._consumer_cancelled_events.clear()

    def test_stop_waits_for_stream_finish(self, handler):
        """stop 逻辑应等待 Consumer 退出后再继续"""
        tid = "test_stop_wait_1"
        stream_started = threading.Event()

        def slow_gen():
            for i in range(20):
                stream_started.set()
                if GeneratorStreamingHelper.is_cancelled(tid, handler):
                    return
                time.sleep(0.05)
                yield f"chunk_{i}"

        # 启动流
        def consume():
            helper = GeneratorStreamingHelper(handler, thread_id=tid)
            list(helper.stream(slow_gen()))

        t = threading.Thread(target=consume)
        t.start()
        stream_started.wait(timeout=2.0)
        time.sleep(0.1)

        # 模拟 stop 接口逻辑
        GeneratorStreamingHelper.cancel(tid, handler)
        stream_finished = handler.wait_for_consumer_cancelled(
            tid, timeout=TimeoutConfig.STOP_WAIT_STREAM_FINISH_TIMEOUT
        )

        assert stream_finished, "stop 应成功等到流结束"
        t.join(timeout=3.0)
        assert not t.is_alive()

    def test_stop_timeout_fallback(self, handler):
        """无 Consumer 时 stop 的 wait 应超时并降级"""
        tid = "test_stop_timeout_fallback"

        # 没有启动任何流，直接模拟 stop 逻辑
        GeneratorStreamingHelper.cancel(tid, handler)
        stream_finished = handler.wait_for_consumer_cancelled(tid, timeout=0.3)

        assert not stream_finished, "无 Consumer 时应超时"

        # 降级：手动 mark_stopped
        if not stream_finished:
            handler.mark_stopped(tid)
        assert handler.is_stopped(tid)

    def test_current_run_can_be_cancelled_before_head_frames(self, handler):
        """当前 run 在 head frames 前注册后，stop 不会错过取消窗口。"""
        tid = "test_stop_before_stream_registration"
        run_id = "run-current"
        handled_events = []
        completed = []

        helper = GeneratorStreamingHelper(handler, thread_id=tid)
        cancel_event = helper.prepare_run(run_id)
        assert GeneratorStreamingHelper.cancel(tid, handler, run_id=run_id)
        result = list(
            helper.stream(
                iter(["must_not_be_emitted"]),
                on_complete=lambda: completed.append(True),
                event_handler=handled_events.append,
                expected_run_id=run_id,
                cancel_event=cancel_event,
            )
        )

        assert "must_not_be_emitted" not in result
        assert any('"type":"RUN_ERROR"' in event for event in result)
        assert any('"type":"RUN_FINISHED"' in event for event in result)
        assert handled_events[0].message == RunId.CANCELLED_MESSAGE
        assert completed == [True]

    def test_cancel_for_previous_run_does_not_cancel_current_run(self, handler):
        """旧 run 的 Stop 不得误伤同一 session 的新 run。"""
        tid = "test_stale_run_cancel"
        helper = GeneratorStreamingHelper(handler, thread_id=tid)
        cancel_event = helper.prepare_run("run-current")

        assert not GeneratorStreamingHelper.cancel(tid, handler, run_id="run-previous")

        result = list(
            helper.stream(
                iter(["current-run-output"]),
                expected_run_id="run-current",
                cancel_event=cancel_event,
            )
        )

        assert result[0] == "current-run-output"
        assert all('"type":"RUN_ERROR"' not in event for event in result)
        assert any('"type":"RUN_FINISHED"' in event for event in result)

    def test_stop_clears_cancelled_signal(self, handler):
        """stop 完成后应清理 cancelled 信号"""
        tid = "test_stop_clear_signal"

        # 预先发送通知
        handler.notify_consumer_cancelled(tid)
        handler.wait_for_consumer_cancelled(tid, timeout=1.0)

        # 清理
        handler.clear_cancelled_signal(tid)

        # 清理后再等应超时
        assert not handler.wait_for_consumer_cancelled(tid, timeout=0.2)


class TestEndToEndStopAndResume:
    """端到端：stop → 新请求恢复的完整流程"""

    @pytest.fixture
    def handler(self):
        handler = InMemoryQueueMessageHandler()
        yield handler
        for thread_id in handler.list_thread_ids():
            handler.clear(thread_id)
        handler._stopped_sessions.clear()
        handler._consumer_cancelled_events.clear()

    def test_stop_then_resume_shows_cached_content(self, handler):
        """stop 后手动标记 stopped 并有缓存内容时，再次进入应展示缓存并返回 STOPPED_CHUNK

        模拟真实场景：Agent 产出部分内容后被 stop，缓存中还有内容待展示。
        """
        tid = "test_stop_resume"

        # 模拟：stop 后队列中还有缓存的 chunk
        handler.put(tid, "chunk_0")
        handler.put(tid, "chunk_1")
        handler.mark_stopped(tid)

        # 再次进入 stream，应展示缓存内容 + STOPPED_CHUNK
        helper = GeneratorStreamingHelper(handler, thread_id=tid)
        collected = list(helper.stream(iter([])))

        assert "chunk_0" in collected
        assert "chunk_1" in collected
        # _consume_stopped_session 耗尽消息后 yield RUN_FINISHED SSE，而非 STOPPED_CHUNK
        expected_run_finished = emit_run_finished_event(thread_id=tid, run_id=RunId.STOPPED)
        assert expected_run_finished in collected
        assert not handler.is_stopped(tid), "恢复后 stopped 标记应清除"

    def test_stop_no_cache_restarts_generator(self, handler):
        """stop 后但无缓存时，应清除 stopped 并正常走新流程"""
        tid = "test_stop_no_cache"

        handler.mark_stopped(tid)

        helper = GeneratorStreamingHelper(handler, thread_id=tid)
        collected = list(helper.stream(iter(["new_chunk"])))

        assert collected == ["new_chunk"]
        assert not handler.is_stopped(tid)


class TestFullStopSequence:
    """完整停止时序测试

    覆盖核心链路：
    stop 接口 cancel → Consumer drain → Agent cancel_checker →
    RUN_FINISHED → EOD → Consumer notify → stop wait → 调用平台 API
    """

    @pytest.fixture
    def handler(self):
        handler = InMemoryQueueMessageHandler()
        yield handler
        for thread_id in handler.list_thread_ids():
            handler.clear(thread_id)
        handler._stopped_sessions.clear()
        handler._consumer_cancelled_events.clear()

    def _run_stop_flow(self, handler, tid, gen_factory, monkeypatch=None, drain_timeout=None):
        """通用的 stop 流程执行器，复刻 builtin.py stop() 的 4 步逻辑。

        Returns: (collected, stream_finished, timeline)
        """
        if drain_timeout and monkeypatch:
            monkeypatch.setattr(GeneratorStreamingHelper, "CANCEL_DRAIN_TIMEOUT", drain_timeout)
            monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 0.05)
            monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 10.0)

        collected = []
        timeline = {}
        stream_started = threading.Event()

        def consume():
            helper = GeneratorStreamingHelper(handler, thread_id=tid)
            collected.extend(helper.stream(gen_factory(stream_started, timeline)))
            timeline["consumer_exited"] = time.time()

        t = threading.Thread(target=consume)
        t.start()
        stream_started.wait(timeout=2.0)
        time.sleep(0.15)

        # 复刻 stop()：先清上一轮通知，再 cancel → wait → 超时标记 stopped
        timeline["cancel_sent"] = time.time()
        handler.clear_cancelled_signal(tid)
        GeneratorStreamingHelper.cancel(tid, handler)  # 步骤1
        stream_finished = handler.wait_for_consumer_cancelled(  # 步骤2
            tid,
            timeout=TimeoutConfig.STOP_WAIT_STREAM_FINISH_TIMEOUT,
        )
        if not stream_finished:  # 步骤3
            handler.mark_stopped(tid)
        timeline["api_called"] = time.time()

        t.join(timeout=10.0)
        assert not t.is_alive()
        return collected, stream_finished, timeline

    def test_cooperative_agent_full_sequence(self, handler, monkeypatch):
        """正常链路：producer 收敛取消终态 → Consumer 通知 → stop 调平台 API

        验证时序严格递增：cancel → Consumer 退出 → API 调用。
        """
        tid = "full_stop_cooperative"

        def gen_factory(started, tl):
            def gen():
                for i in range(50):
                    started.set()
                    if GeneratorStreamingHelper.is_cancelled(tid, handler):
                        tl["agent_detected"] = time.time()
                        yield "RUN_FINISHED_EVENT"
                        return
                    time.sleep(0.05)
                    yield f"chunk_{i}"

            return gen()

        collected, finished, tl = self._run_stop_flow(handler, tid, gen_factory)

        assert finished, "stop 应成功等到流结束"
        expected_run_finished = emit_run_finished_event(thread_id=tid, run_id=RunId.CANCELLED)
        assert expected_run_finished in collected
        assert 0 < sum(1 for c in collected if c.startswith("chunk_")) < 50
        # 时序验证
        assert tl["consumer_exited"] >= tl["cancel_sent"]
        assert tl["api_called"] >= tl["cancel_sent"]
        assert abs(tl["api_called"] - tl["consumer_exited"]) < 0.1
        assert handler.is_empty(tid)

    def test_non_cooperative_producer_is_closed_after_cancel(self, handler):
        """Agent 不主动检查 cancel 时，producer 仍主动关闭 generator 并发送 EOD。"""
        tid = "full_stop_drain_timeout"

        def gen_factory(started, tl):
            def gen():
                for i in range(500):
                    started.set()
                    time.sleep(0.05)
                    yield f"chunk_{i}"

            return gen()

        collected, finished, tl = self._run_stop_flow(handler, tid, gen_factory)

        assert finished, "producer 主动收敛取消终态后 Consumer 应退出并通知"
        assert emit_run_finished_event(thread_id=tid, run_id=RunId.CANCELLED) in collected

    def test_consumer_waits_for_live_producer_before_notify(self, handler, monkeypatch):
        """工具仍执行时不能提前通知 stop 已完成，producer 结束后再确认。"""
        tid = "full_stop_consumer_drain"
        monkeypatch.setattr(GeneratorStreamingHelper, "CANCEL_DRAIN_TIMEOUT", 0.2)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 0.05)
        collected = []
        first_chunk_sent = threading.Event()

        def blocked_tool_gen():
            yield "first_chunk"
            first_chunk_sent.set()
            time.sleep(0.8)
            yield "tool_result_after_stop"

        def consume():
            helper = GeneratorStreamingHelper(handler, thread_id=tid)
            collected.extend(helper.stream(blocked_tool_gen()))

        thread = threading.Thread(target=consume)
        thread.start()
        first_chunk_sent.wait(timeout=1.0)
        handler.clear_cancelled_signal(tid)
        GeneratorStreamingHelper.cancel(tid, handler)

        assert not handler.wait_for_consumer_cancelled(tid, timeout=0.35)
        assert thread.is_alive(), "producer 仍执行工具时，consumer 不应提前宣告停止完成"

        thread.join(timeout=3.0)
        assert not thread.is_alive()
        assert handler.wait_for_consumer_cancelled(tid, timeout=0.5)
        assert "tool_result_after_stop" not in collected
        expected_run_finished = emit_run_finished_event(thread_id=tid, run_id=RunId.CANCELLED)
        assert expected_run_finished in collected

    def test_stop_timeout_degradation_no_consumer(self, handler):
        """无 Consumer 场景：stop wait 超时 → 降级 mark_stopped → 调 API"""
        tid = "full_stop_no_consumer"

        GeneratorStreamingHelper.cancel(tid, handler)
        stream_finished = handler.wait_for_consumer_cancelled(tid, timeout=0.3)

        assert not stream_finished
        handler.mark_stopped(tid)
        assert handler.is_stopped(tid)
        handler.clear_cancelled_signal(tid)
        assert not handler.wait_for_consumer_cancelled(tid, timeout=0.1)
