"""测试 stop 接口与 SSE 流的同步机制

核心验证：
1. Consumer 在三条退出路径（CANCELLED / EOD / drain 超时）都会发送取消通知
2. stop 接口 cancel → wait → 超时降级 的完整流程
3. 端到端：cancel 后流正确终止并通知
4. 完整停止时序：stop → cancel → Agent cancel_checker → RUN_FINISHED →
   EOD → Consumer notify → stop wait → 调用平台 API
"""

import threading
import time

import aidev_agent.services.messages_handler.streaming_helper as streaming_helper_module
import pytest
from aidev_agent.services.messages_handler import (
    STOPPED_CHUNK,
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
)
from aidev_agent.services.messages_handler.constants import TimeoutConfig


class TestConsumerNotifyOnCancel:
    """验证 Consumer 在取消场景下发送 notify_consumer_cancelled"""

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

    def test_normal_finish_triggers_notify(self, handler):
        """正常结束（EOD_CHUNK）时也应触发 notify"""
        tid = "test_sync_eod_notify"

        def short_gen():
            yield "chunk_0"
            yield "chunk_1"

        helper = GeneratorStreamingHelper(handler, thread_id=tid)
        result = list(helper.stream(short_gen()))

        assert result == ["chunk_0", "chunk_1"]
        # 正常结束后 notify 应已发出，wait 应立即返回
        assert handler.wait_for_consumer_cancelled(tid, timeout=1.0)

    def test_drain_timeout_triggers_notify(self, handler, monkeypatch):
        """Consumer drain 超时时也应触发 notify

        场景：generator 不检查 cancel，cancel 后 Producer 进入 drain 模式并超时退出，
        然后发 EOD_CHUNK。Consumer 检测到 cancel 后进入 drain 等待 EOD_CHUNK/RUN_FINISHED，
        如果 Consumer 自己也 drain 超时则触发 STOPPED_CHUNK。

        本测试验证：无论哪条路径退出，notify 都会被触发。
        """
        tid = "test_sync_drain_timeout_notify"
        collected = []

        # 缩短 drain 超时为 0.5 秒
        monkeypatch.setattr(GeneratorStreamingHelper, "CANCEL_DRAIN_TIMEOUT", 0.5)
        # 缩短心跳
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 0.05)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_TIMEOUT", 10.0)

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

        # 核心断言：不管哪条路径退出，notify 都应被触发
        notified = handler.wait_for_consumer_cancelled(tid, timeout=10.0)
        t.join(timeout=10.0)

        assert notified, "drain 超时后应发送 notify"
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
        assert STOPPED_CHUNK in collected
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
            monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_TIMEOUT", 10.0)

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

        # 复刻 stop() 4 步
        timeline["cancel_sent"] = time.time()
        GeneratorStreamingHelper.cancel(tid, handler)  # 步骤1
        stream_finished = handler.wait_for_consumer_cancelled(  # 步骤2
            tid,
            timeout=TimeoutConfig.STOP_WAIT_STREAM_FINISH_TIMEOUT,
        )
        if not stream_finished:  # 步骤3
            handler.mark_stopped(tid)
        handler.clear_cancelled_signal(tid)  # 步骤4
        timeline["api_called"] = time.time()

        t.join(timeout=10.0)
        assert not t.is_alive()
        return collected, stream_finished, timeline

    def test_cooperative_agent_full_sequence(self, handler, monkeypatch):
        """正常链路：Agent 配合取消 → RUN_FINISHED → stop 等到通知 → 调 API

        验证时序严格递增：cancel → Agent 检测 → RUN_FINISHED → Consumer 退出 → API 调用
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
        assert "RUN_FINISHED_EVENT" in collected
        assert 0 < sum(1 for c in collected if c.startswith("chunk_")) < 50
        # 时序验证
        assert tl["agent_detected"] >= tl["cancel_sent"]
        assert tl["consumer_exited"] >= tl["agent_detected"]
        assert tl["api_called"] >= tl["consumer_exited"]
        assert handler.is_empty(tid)

    def test_producer_drain_timeout_force_exit(self, handler, monkeypatch):
        """Agent 不配合：generator 不退出 → Producer drain 超时 → EOD → Consumer 退出"""
        tid = "full_stop_drain_timeout"

        def gen_factory(started, tl):
            def gen():
                for i in range(500):
                    started.set()
                    time.sleep(0.05)
                    yield f"chunk_{i}"

            return gen()

        collected, finished, tl = self._run_stop_flow(
            handler,
            tid,
            gen_factory,
            monkeypatch,
            drain_timeout=0.3,
        )

        assert finished, "drain 超时后 Consumer 也应退出并通知"

    def test_consumer_drain_timeout_yields_stopped(self, handler, monkeypatch):
        """Producer 卡住 → Consumer drain 先超时 → yield STOPPED_CHUNK

        generator yield 间隔远大于 drain 超时，Producer 卡在 next() 上，
        Consumer drain 先超时走 STOPPED 路径。
        """
        tid = "full_stop_consumer_drain"

        def gen_factory(started, tl):
            def gen():
                started.set()
                yield "first_chunk"
                time.sleep(5.0)  # 远超 drain 超时，Producer 卡在 next()
                yield "never_reached"

            return gen()

        collected, finished, tl = self._run_stop_flow(
            handler,
            tid,
            gen_factory,
            monkeypatch,
            drain_timeout=0.5,
        )

        assert finished
        assert STOPPED_CHUNK in collected

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
