"""测试 InMemoryQueueMessageHandler 的基本功能"""

import contextlib
import json
import threading
import time

import aidev_agent.services.messages_handler.streaming_helper as streaming_helper_module
import pytest
from ag_ui.core import EventType
from aidev_agent.enums import MessageHandlerType
from aidev_agent.services.messages_handler import (
    CANCELLED_CHUNK,
    EOD_CHUNK,
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
    RetryableHeartbeatTimeoutError,
    StreamAttachUnavailableError,
    message_handler_factory,
)
from aidev_agent.services.messages_handler.config import MessageHandlerConfig
from aidev_agent.services.messages_handler.constants import EnvVarNames
from aidev_agent.services.messages_handler.factory import _create_handler, _init_factory
from aidev_agent.utils.event import RunId, emit_run_finished_event


def _make_run_finished_chunk(thread_id: str, run_id: str) -> str:
    """生成 RUN_FINISHED SSE 字符串，用于测试期望值对比。"""
    return emit_run_finished_event(thread_id=thread_id, run_id=run_id)


def _event_types(chunks: list[str]) -> list[str]:
    return [json.loads(chunk.removeprefix("data: "))["type"] for chunk in chunks if chunk.startswith("data: ")]


class ReplayFromStartHandler:
    """测试用 replay handler：模拟 RabbitMQ 的非破坏性会话日志读取。"""

    CONSUMER_HEARTBEAT_TIMEOUT = 60.0

    def __init__(self):
        self.messages: dict[str, list] = {}
        self.active_consumers: set[tuple[str, str]] = set()
        self.producer_locks: set[str] = set()
        self.completed_threads: list[str] = []
        self.consumer_checks: list[tuple[str, str]] = []
        self._consumer_seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    def supports_replay_from_start(self) -> bool:
        return True

    def bind_replay_run(self, thread_id, run_id):
        pass

    def arm_completed_replay_expiry(self, thread_id):
        return False

    def put(self, thread_id, message):
        with self._condition:
            self.messages.setdefault(thread_id, []).append(message)
            self._condition.notify_all()

    def flush(self, thread_id):
        pass

    def get_messages_since(self, thread_id, offset, timeout=None):
        start = time.time()
        with self._condition:
            while True:
                current = list(self.messages.get(thread_id, []))
                if len(current) > offset:
                    return current[offset:], len(current)
                if timeout is not None:
                    remaining = timeout - (time.time() - start)
                    if remaining <= 0:
                        raise TimeoutError("No message available within timeout")
                    self._condition.wait(timeout=remaining)
                else:
                    self._condition.wait()

    def has_pending_messages(self, thread_id):
        with self._lock:
            return bool(self.messages.get(thread_id))

    def acquire_producer(self, thread_id):
        with self._lock:
            if thread_id in self.producer_locks:
                return False
            self.producer_locks.add(thread_id)
            return True

    def release_producer(self, thread_id):
        with self._lock:
            self.producer_locks.discard(thread_id)

    def has_active_producer(self, thread_id):
        with self._lock:
            return thread_id in self.producer_locks

    def acquire_consumer(self, thread_id):
        with self._lock:
            consumer_id = f"consumer-{self._consumer_seq}"
            self._consumer_seq += 1
            self.active_consumers.add((thread_id, consumer_id))
        return consumer_id

    def wait_for_previous_consumer(self, thread_id, timeout=3.0):
        return True

    def check_consumer(self, thread_id, consumer_id):
        self.consumer_checks.append((thread_id, consumer_id))

    def release_consumer(self, thread_id, consumer_id):
        with self._lock:
            self.active_consumers.discard((thread_id, consumer_id))

    def has_active_consumer(self, thread_id):
        with self._lock:
            return any(tid == thread_id for tid, _ in self.active_consumers)

    def is_stopped(self, thread_id):
        return False

    def clear_stopped(self, thread_id):
        pass

    def mark_completed(self, thread_id):
        with self._condition:
            self.completed_threads.append(thread_id)
            self.messages.pop(thread_id, None)
            self._condition.notify_all()

    def clear(self, thread_id):
        with self._condition:
            self.messages.pop(thread_id, None)
            self._condition.notify_all()

    def clear_cancel_signal(self, thread_id, run_id=None):
        pass

    def check_cancel_signal(self, thread_id, run_id=None):
        return False

    def set_cancel_signal(self, thread_id, run_id=None):
        return False

    def notify_consumer_cancelled(self, thread_id, run_id=None):
        return True


class BarrierReplayFromStartHandler(ReplayFromStartHandler):
    """测试用 replay handler：等待多个 consumer 同时注册后再开始消费。"""

    def __init__(self, parties: int):
        super().__init__()
        self._barrier = threading.Barrier(parties)

    def acquire_consumer(self, thread_id):
        consumer_id = super().acquire_consumer(thread_id)
        try:
            self._barrier.wait(timeout=2)
        except threading.BrokenBarrierError as exc:
            raise AssertionError("Timed out waiting for concurrent replay consumers to register") from exc
        return consumer_id


class TestReplayFromStartStreamingHelper:
    def test_attach_active_stream_never_starts_or_iterates_producer(self):
        thread_id = "test_attach_active_stream"
        handler = ReplayFromStartHandler()
        handler.producer_locks.add(thread_id)
        producer_iterated = []

        def producer():
            producer_iterated.append(True)
            yield "must-not-run"

        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        producer_thread, is_resuming, enable_heartbeat_check = helper._start_or_resume_stream(
            generator=producer(),
            cancel_event=threading.Event(),
            has_pending=False,
            attach_only=True,
        )

        assert producer_thread is None
        assert is_resuming is True
        assert enable_heartbeat_check is True
        assert producer_iterated == []

    def test_attach_cached_stream_ignores_new_request_run_id(self):
        thread_id = "test_attach_cached_stream"
        handler = ReplayFromStartHandler()
        handler.put(thread_id, "cached")
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        helper.run_id = "new-request-run"
        handler.replay_belongs_to_run = lambda *_args: False

        assert helper._recheck_pending_after_waiting_consumer(True, attach_only=True) is True

    def test_attach_without_active_or_cached_stream_fails_without_producer(self):
        handler = ReplayFromStartHandler()
        helper = GeneratorStreamingHelper(handler, thread_id="test_attach_missing")

        with pytest.raises(StreamAttachUnavailableError, match="No active or replayable stream"):
            helper._start_or_resume_stream(
                generator=iter(["must-not-run"]),
                cancel_event=threading.Event(),
                has_pending=False,
                attach_only=True,
            )

        assert handler.producer_locks == set()

    def test_concurrent_consumers_replay_same_cached_stream_without_draining_each_other(self):
        thread_id = "test_replay_multi_consumer"
        handler = BarrierReplayFromStartHandler(parties=2)
        handler.put(thread_id, "chunk_0")
        handler.put(thread_id, "chunk_1")
        handler.put(thread_id, EOD_CHUNK)

        results = []
        errors = []

        def consume():
            try:
                results.append(list(GeneratorStreamingHelper(handler, thread_id=thread_id).stream(iter(()))))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=consume) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        assert errors == []
        assert all(not thread.is_alive() for thread in threads)
        assert results == [["chunk_0", "chunk_1"], ["chunk_0", "chunk_1"]]
        assert len(handler.consumer_checks) == 2
        assert thread_id not in handler.messages
        assert handler.completed_threads == [thread_id]

    def test_replay_mode_runs_on_complete_in_producer_once(self):
        thread_id = "test_replay_on_complete_once"
        handler = ReplayFromStartHandler()
        lifecycle = []
        handler.flush = lambda _thread_id: lifecycle.append("flush")

        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(["chunk_0"]),
                on_complete=lambda: lifecycle.append("complete"),
            )
        )

        assert result == ["chunk_0"]
        assert lifecycle == ["flush", "complete"]
        assert thread_id not in handler.producer_locks

    def test_replay_mode_propagates_on_complete_failure(self):
        handler = ReplayFromStartHandler()
        helper = GeneratorStreamingHelper(handler, thread_id="test_replay_complete_failure")

        with pytest.raises(RuntimeError, match="status update failed"):
            list(
                helper.stream(
                    iter(["chunk_0"]),
                    on_complete=lambda: (_ for _ in ()).throw(RuntimeError("status update failed")),
                )
            )

    def test_normal_agui_stream_emits_run_finished_fallback_before_eod(self):
        handler = ReplayFromStartHandler()
        dispatched = []

        result = list(
            GeneratorStreamingHelper(handler, thread_id="thread-1").stream(
                iter(["chunk_0"]),
                event_handler=dispatched.append,
                expected_run_id="run-1",
            )
        )

        assert result[0] == "chunk_0"
        assert _event_types(result[1:]) == [EventType.RUN_FINISHED]
        assert [event.type for event in dispatched] == [EventType.RUN_FINISHED]

    def test_normal_agui_stream_does_not_duplicate_existing_run_finished(self):
        handler = ReplayFromStartHandler()
        finished = emit_run_finished_event(thread_id="thread-1", run_id="run-1")

        result = list(
            GeneratorStreamingHelper(handler, thread_id="thread-1").stream(
                iter([finished]),
                expected_run_id="run-1",
            )
        )

        assert result == [finished]

    def test_run_finished_finalizes_session_then_closes_generator_before_eod(self, monkeypatch):
        handler = ReplayFromStartHandler()
        helper = GeneratorStreamingHelper(handler, thread_id="thread-1")
        finished = emit_run_finished_event(thread_id="thread-1", run_id="run-1")
        lifecycle = []

        def terminal_generator():
            try:
                yield finished
                raise AssertionError("producer read after RUN_FINISHED")
            finally:
                lifecycle.append("close")

        original_put = handler.put

        def track_eod(thread_id, message):
            if message == EOD_CHUNK:
                lifecycle.append("eod")
            original_put(thread_id, message)

        monkeypatch.setattr(handler, "put", track_eod)
        assert list(helper.stream(terminal_generator(), on_complete=lambda: lifecycle.append("complete"))) == [finished]
        assert lifecycle == ["complete", "close", "eod"]


class TestInMemoryQueueMessageHandler:
    """测试 InMemoryQueueMessageHandler"""

    @pytest.fixture
    def handler(self):
        """创建 handler 实例"""
        handler = InMemoryQueueMessageHandler()
        yield handler
        # 清理所有队列
        for thread_id in handler.list_thread_ids():
            handler.clear(thread_id)

    def test_singleton(self):
        """测试单例模式"""
        handler1 = InMemoryQueueMessageHandler()
        handler2 = InMemoryQueueMessageHandler()
        assert handler1 is handler2

    def test_put_and_get(self, handler):
        """测试基本的 put 和 get 操作"""
        thread_id = "test_thread_1"

        # 添加消息
        handler.put(thread_id, "message1")
        handler.put(thread_id, "message2")
        handler.put(thread_id, "message3")

        # 获取消息
        messages = handler.get(thread_id, timeout=1.0)
        assert len(messages) == 3
        assert messages == ["message1", "message2", "message3"]

    def test_get_timeout(self, handler):
        """测试 get 超时"""
        thread_id = "test_thread_2"

        # 队列为空时获取消息应该超时
        with pytest.raises(TimeoutError):
            handler.get(thread_id, timeout=0.5)

    def test_has_pending_messages(self, handler):
        """测试 has_pending_messages"""
        thread_id = "test_thread_3"

        # 初始状态：无消息
        assert not handler.has_pending_messages(thread_id)

        # 添加消息后：有消息
        handler.put(thread_id, "message1")
        assert handler.has_pending_messages(thread_id)

        # 获取消息后：消息在死信队列中，仍然有消息
        handler.get(thread_id, timeout=1.0)
        assert handler.has_pending_messages(thread_id)

        # 标记完成后：无消息
        handler.mark_completed(thread_id)
        assert not handler.has_pending_messages(thread_id)

    def test_restore_messages(self, handler):
        """测试死信队列恢复"""
        thread_id = "test_thread_4"

        # 添加并获取消息（消息进入死信队列）
        handler.put(thread_id, "message1")
        handler.put(thread_id, "message2")
        messages = handler.get(thread_id, timeout=1.0)
        assert len(messages) == 2

        # 主队列应该为空
        assert handler.get_cached_count(thread_id) == 0

        # 恢复消息
        restored_count = handler.restore_messages(thread_id)
        assert restored_count == 2

        # 主队列应该有 2 条消息
        assert handler.get_cached_count(thread_id) == 2

        # 再次获取消息
        messages = handler.get(thread_id, timeout=1.0)
        assert len(messages) == 2
        assert messages == ["message1", "message2"]

    def test_mark_completed(self, handler):
        """测试 mark_completed"""
        thread_id = "test_thread_5"

        # 添加并获取消息
        handler.put(thread_id, "message1")
        handler.put(thread_id, "message2")
        handler.get(thread_id, timeout=1.0)

        # 标记完成
        handler.mark_completed(thread_id)

        # 主队列和死信队列都应该为空
        assert handler.get_cached_count(thread_id) == 0
        assert handler.get_total_count(thread_id) == 0
        assert handler.is_empty(thread_id)

    def test_clear(self, handler):
        """测试 clear"""
        thread_id = "test_thread_6"

        # 添加消息
        handler.put(thread_id, "message1")
        handler.put(thread_id, "message2")

        # 清空队列
        handler.clear(thread_id)

        # 队列应该为空
        assert handler.is_empty(thread_id)

    def test_get_counts(self, handler):
        """测试各种计数方法"""
        thread_id = "test_thread_7"

        # 初始状态
        assert handler.get_cached_count(thread_id) == 0
        assert handler.get_total_count(thread_id) == 0
        assert handler.size(thread_id) == 0

        # 添加 3 条消息
        handler.put(thread_id, "message1")
        handler.put(thread_id, "message2")
        handler.put(thread_id, "message3")

        assert handler.get_cached_count(thread_id) == 3
        assert handler.get_total_count(thread_id) == 3
        assert handler.size(thread_id) == 3

        # 获取 3 条消息（进入死信队列）
        handler.get(thread_id, timeout=1.0)

        assert handler.get_cached_count(thread_id) == 0
        assert handler.get_total_count(thread_id) == 3  # 死信队列中有 3 条

    def test_list_thread_ids(self, handler):
        """测试 list_thread_ids"""
        # 添加消息到不同的 thread_id
        handler.put("thread1", "message1")
        handler.put("thread2", "message2")
        handler.put("thread3", "message3")

        # 获取所有 thread_id
        thread_ids = handler.list_thread_ids()
        # 由于单例模式，可能包含其他测试的 thread_id，只检查我们添加的是否存在
        assert "thread1" in thread_ids
        assert "thread2" in thread_ids
        assert "thread3" in thread_ids

    def test_streaming_helper_basic(self, handler):
        """测试 GeneratorStreamingHelper 基本功能"""

        def data_generator():
            for i in range(5):
                yield f"chunk_{i}"

        helper = GeneratorStreamingHelper(handler, thread_id="test_stream_1")
        result = list(helper.stream(data_generator()))

        assert len(result) == 5
        assert result == ["chunk_0", "chunk_1", "chunk_2", "chunk_3", "chunk_4"]

    def test_streaming_helper_resume(self, handler):
        """测试 GeneratorStreamingHelper 断点续传"""

        def data_generator():
            for i in range(5):
                yield f"chunk_{i}"

        thread_id = "test_stream_2"

        # 第一次流式处理：只消费部分数据
        helper1 = GeneratorStreamingHelper(handler, thread_id=thread_id)
        stream1 = helper1.stream(data_generator())
        chunk1 = next(stream1)
        chunk2 = next(stream1)
        assert chunk1 == "chunk_0"
        assert chunk2 == "chunk_1"
        # 模拟断开连接（不继续消费），显式关闭避免第二次消费等待抢占超时
        stream1.close()
        # 此时 chunk_0 和 chunk_1 在死信队列中，chunk_2, chunk_3, chunk_4 和 EOD_CHUNK 在主队列中

        # 第二次流式处理：应该从头开始消费（因为会恢复死信队列）
        helper2 = GeneratorStreamingHelper(handler, thread_id=thread_id)

        def empty_generator():
            # 不产生新数据，只消费已有数据
            return
            yield  # 使其成为生成器

        result = list(helper2.stream(empty_generator()))

        # 应该包含所有数据（从死信队列恢复 + 主队列剩余）
        # 死信队列有 chunk_0, chunk_1
        # 主队列有 chunk_2, chunk_3, chunk_4
        # 恢复后主队列有 chunk_0, chunk_1, chunk_2, chunk_3, chunk_4
        assert len(result) == 5
        assert result == ["chunk_0", "chunk_1", "chunk_2", "chunk_3", "chunk_4"]

    def test_producer_stop_request_cancel(self, handler):
        """主动停止：cancel 后 producer 检测到取消并退出，消费者正常结束并清理队列"""
        thread_id = "test_stream_cancel"
        collected = []
        stream_started = threading.Event()

        def slow_generator():
            """模拟一个能检测取消信号的 generator（类似实际 Agent 行为）"""
            for i in range(20):
                stream_started.set()
                # 检查取消状态（实际 Agent 会通过 cancel_checker 检查）
                if GeneratorStreamingHelper.is_cancelled(thread_id, handler):
                    return  # 检测到取消，提前退出
                time.sleep(0.05)
                yield f"chunk_{i}"

        def consume():
            helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
            collected.extend(helper.stream(slow_generator()))

        t = threading.Thread(target=consume)
        t.start()
        stream_started.wait(timeout=2.0)
        time.sleep(0.1)
        # 使用 GeneratorStreamingHelper.cancel() 设置取消信号
        GeneratorStreamingHelper.cancel(thread_id, handler)
        t.join(timeout=3.0)
        assert not t.is_alive()
        # 应收到部分 chunk 且队列已清理
        assert len(collected) < 20
        assert handler.is_empty(thread_id)

    def test_producer_stop_then_reconnect(self, handler):
        """停止后重连：cancel 后消费者断开，重连后恢复并读到 EOD_CHUNK 后清理"""
        thread_id = "test_stream_cancel_reconnect"

        def slow_generator():
            """模拟一个能检测取消信号的 generator"""
            for i in range(10):
                if GeneratorStreamingHelper.is_cancelled(thread_id, handler):
                    return  # 检测到取消，提前退出
                time.sleep(0.05)
                yield f"chunk_{i}"

        helper1 = GeneratorStreamingHelper(handler, thread_id=thread_id)
        stream1 = helper1.stream(slow_generator())
        next(stream1)
        next(stream1)
        # 使用 GeneratorStreamingHelper.cancel()
        GeneratorStreamingHelper.cancel(thread_id, handler)
        # 不继续消费，关闭生成器（模拟断开）
        with contextlib.suppress(GeneratorExit):
            stream1.close()
        time.sleep(0.5)

        # 重连：有 pending（含 EOD_CHUNK），恢复后消费应得到 EOD_CHUNK 并结束
        helper2 = GeneratorStreamingHelper(handler, thread_id=thread_id)
        result = list(helper2.stream(iter([])))
        # 恢复后主队列里是已产生的 chunk + EOD_CHUNK，应收到到 EOD_CHUNK 之前的所有 chunk
        assert "chunk_0" in result and "chunk_1" in result
        assert handler.is_empty(thread_id)

    def test_request_cancel_idempotent(self, handler):
        """重复 cancel 幂等：多次调用不报错，producer 仍能正常停止"""
        thread_id = "test_stream_cancel_idempotent"
        handler.request_cancel(thread_id)
        handler.request_cancel(thread_id)
        handler.request_cancel(thread_id)

        # 兼容接口与统一取消信号使用同一份状态，并且检查不消费信号。
        assert handler.is_cancel_requested(thread_id)
        assert handler.is_cancel_requested(thread_id)

        def gen():
            yield "a"
            yield "b"

        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        result = list(helper.stream(gen()))
        # 可能收到 0、1 或 2 条后因取消而结束
        assert len(result) <= 2
        assert handler.is_empty(thread_id)

    def test_stream_stopped_session_with_pending_messages(self, handler, monkeypatch):
        """已停止且有缓存内容时，只回放内容并在末尾发送 RUN_FINISHED 事件。"""
        thread_id = "test_stream_stopped_pending"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        clear_stopped_called = []

        handler.put(thread_id, "chunk_0")
        handler.put(thread_id, "chunk_1")
        monkeypatch.setattr(handler, "is_stopped", lambda _tid: True)
        monkeypatch.setattr(handler, "clear_stopped", lambda _tid: clear_stopped_called.append(True))

        result = list(helper.stream(iter(())))

        expected_run_finished = emit_run_finished_event(thread_id=thread_id, run_id=RunId.STOPPED)
        assert result == ["chunk_0", "chunk_1", expected_run_finished]
        assert clear_stopped_called
        assert handler.is_empty(thread_id)

    def test_stream_stopped_session_without_messages_starts_new_producer(self, handler, monkeypatch):
        """已停止但无缓存内容时，清理 stopped 状态并进入重新生成流程。"""
        thread_id = "test_stream_stopped_empty"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        clear_stopped_called = []

        monkeypatch.setattr(handler, "is_stopped", lambda _tid: True)
        monkeypatch.setattr(handler, "restore_messages", lambda _tid: 0)
        monkeypatch.setattr(handler, "get_cached_count", lambda _tid: 0)
        monkeypatch.setattr(handler, "clear_stopped", lambda _tid: clear_stopped_called.append(True))

        result = list(helper.stream(iter(["new_chunk"])))

        assert result == ["new_chunk"]
        assert clear_stopped_called

    @pytest.mark.parametrize(
        "gen_items",
        [
            [CANCELLED_CHUNK],
            ["chunk_0"],
        ],
    )
    def test_stream_handles_control_and_data_messages(self, handler, gen_items):
        """验证 CANCELLED_CHUNK 与普通数据在消费侧的处理行为。"""
        thread_id = f"test_stream_control_{len(gen_items)}_{gen_items[0]}"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)

        result = list(helper.stream(iter(gen_items)))

        if gen_items == [CANCELLED_CHUNK]:
            # CANCELLED_CHUNK 被消费后，消费者 yield RUN_FINISHED SSE 字符串
            expected = [_make_run_finished_chunk(thread_id=thread_id, run_id=RunId.CANCELLED)]
            assert result == expected
        else:
            assert result == gen_items

    def test_stream_on_complete_exception_is_propagated(self, handler):
        """终态回写失败必须向上传播，不能留下 running 会话。"""
        thread_id = "test_stream_on_complete_error"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        callback_called = []

        def broken_on_complete():
            callback_called.append(True)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            list(helper.stream(iter(["chunk_0"]), on_complete=broken_on_complete))

        assert callback_called
        assert handler.is_empty(thread_id)

    def test_orphaned_cleanup_after_done_does_not_wait_full_delay_without_consumer(self, handler, monkeypatch):
        """生产者已发出 done 后若无活跃消费者，应尽快清理而不是始终等满延迟窗口。"""
        thread_id = "test_stream_orphan_cleanup_fast"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        cleanup_called = threading.Event()

        handler.put(thread_id, "chunk_0")

        original_mark_completed = handler.mark_completed

        def mark_completed_and_signal(tid):
            original_mark_completed(tid)
            if tid == thread_id:
                cleanup_called.set()

        monkeypatch.setattr(helper, "_PRODUCER_CLEANUP_DELAY", 1.0)
        monkeypatch.setattr(helper, "_DONE_ORPHAN_CLEANUP_GRACE", 0.05)
        monkeypatch.setattr(handler, "mark_completed", mark_completed_and_signal)

        helper._schedule_session_cleanup(done_event_seen=True)

        assert cleanup_called.wait(timeout=0.3), "done orphaned cleanup should happen promptly without active consumer"
        assert handler.is_empty(thread_id)

    def test_backend_managed_replay_expiry_skips_polling_cleanup(self, handler, monkeypatch):
        thread_id = "test_backend_managed_replay_expiry"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        armed = []

        monkeypatch.setattr(handler, "arm_completed_replay_expiry", lambda tid: armed.append(tid) or True)
        monkeypatch.setattr(
            handler,
            "has_pending_messages",
            lambda tid: pytest.fail("backend-managed expiry must not start a polling cleanup thread"),
        )

        helper._schedule_session_cleanup(done_event_seen=True)

        assert armed == [thread_id]

    def test_orphaned_cleanup_waits_for_active_replay_consumer(self, monkeypatch):
        """replay consumer 曾活跃时，应保留队列到完整 deadline。"""
        thread_id = "test_stream_active_replay_cleanup"
        handler = ReplayFromStartHandler()
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        assert helper._PRODUCER_CLEANUP_DELAY == 90.0
        handler.put(thread_id, "chunk_0")
        consumer_id = handler.acquire_consumer(thread_id)
        monkeypatch.setattr(helper, "_PRODUCER_CLEANUP_DELAY", 0.15)
        monkeypatch.setattr(helper, "_DONE_ORPHAN_CLEANUP_GRACE", 0.02)
        monkeypatch.setattr(helper, "_ORPHAN_CLEANUP_POLL_INTERVAL", 0.01)

        helper._schedule_session_cleanup(done_event_seen=True)
        time.sleep(0.05)
        assert handler.has_pending_messages(thread_id)

        handler.release_consumer(thread_id, consumer_id)
        time.sleep(0.05)
        assert handler.has_pending_messages(thread_id)

        deadline = time.time() + 0.3
        while handler.has_pending_messages(thread_id) and time.time() < deadline:
            time.sleep(0.01)
        assert not handler.has_pending_messages(thread_id)

    def test_stream_keeps_alive_when_generator_blocked(self, handler, monkeypatch):
        """generator 长时间无产出时，独立心跳应通过 RAW 事件维持 SSE 连接。"""
        thread_id = "test_stream_heartbeat_keepalive"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 0.05)
        monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 0.2)
        heartbeat_count = 0

        original_put = handler.put

        def put_with_count(tid, message):
            nonlocal heartbeat_count
            if tid == thread_id and message == streaming_helper_module.HEARTBEAT_CHUNK:
                heartbeat_count += 1
            original_put(tid, message)

        monkeypatch.setattr(handler, "put", put_with_count)

        def slow_first_chunk():
            time.sleep(0.8)
            yield "late_chunk"

        result = list(helper.stream(slow_first_chunk()))
        heartbeat_events = [
            json.loads(chunk.removeprefix("data: "))
            for chunk in result
            if isinstance(chunk, str) and chunk.startswith("data: ") and '"type":"RAW"' in chunk
        ]

        assert result[-1] == "late_chunk"
        assert heartbeat_events
        assert all(event == {"type": "RAW", "event": {"type": "heartbeat"}} for event in heartbeat_events)
        assert heartbeat_count > 0

    def test_stream_emits_raw_then_raises_when_heartbeat_timeout(self, handler, monkeypatch):
        """心跳超时先输出 RAW，再中断 SSE 触发前端重试。"""
        thread_id = "test_stream_heartbeat_timeout"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 1.0)
        monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 0.2)
        monkeypatch.setattr(helper, "_HEARTBEAT_TIMEOUT_GRACE", 0.05)
        dispatched = []
        original_put = handler.put

        def drop_heartbeat(tid, message):
            if message != streaming_helper_module.HEARTBEAT_CHUNK:
                original_put(tid, message)

        monkeypatch.setattr(handler, "put", drop_heartbeat)

        def slow_first_chunk():
            time.sleep(1.2)
            yield "late_chunk"

        stream = helper.stream(slow_first_chunk(), event_handler=dispatched.append)
        error_chunk = next(stream)

        assert _event_types([error_chunk]) == ["RAW"]
        assert json.loads(error_chunk.removeprefix("data: "))["event"] == {
            "type": "error",
            "message": helper._HEARTBEAT_TIMEOUT_MESSAGE,
        }
        assert [event.type for event in dispatched] == [EventType.RAW]
        with pytest.raises(RetryableHeartbeatTimeoutError, match="生产者心跳超时"):
            next(stream)

    def test_replay_stream_uses_handler_heartbeat_timeout(self, monkeypatch):
        """RabbitMQ replay 使用独立的较长心跳窗口，不受通用 15 秒阈值影响。"""
        handler = ReplayFromStartHandler()
        helper = GeneratorStreamingHelper(handler, thread_id="test_replay_heartbeat_timeout")
        assert handler.CONSUMER_HEARTBEAT_TIMEOUT == 60.0
        producer_thread = threading.Thread(target=lambda: None)
        producer_thread.start()
        producer_thread.join()
        calls = 0

        def delayed_eod(*, timeout, replay_offset):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise TimeoutError
            return [EOD_CHUNK], replay_offset + 1

        monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 0.2)
        monkeypatch.setattr(helper, "_get_consumer_messages", delayed_eod)
        stream = helper._consume_stream_messages(
            handler.acquire_consumer(helper.thread_id), threading.Event(), False, True, producer_thread=producer_thread
        )

        assert (list(stream), calls) == ([], 3)

    def test_background_stream_keeps_running_during_heartbeat_recovery(self, handler, monkeypatch):
        """后台 schedule 无前端可接管，producer 存活时心跳超时应继续消费。"""
        thread_id = "test_background_heartbeat_recovery"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id, defer_cleanup_on_complete=True)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 1.0)
        monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 0.1)
        monkeypatch.setattr(helper, "_HEARTBEAT_TIMEOUT_GRACE", 0.02)
        monkeypatch.setattr(helper, "_BACKGROUND_HEARTBEAT_RECOVERY_TIMEOUT", 2.0)
        original_put = handler.put

        def drop_heartbeat(tid, message):
            if message != streaming_helper_module.HEARTBEAT_CHUNK:
                original_put(tid, message)

        monkeypatch.setattr(handler, "put", drop_heartbeat)

        def delayed_chunk():
            time.sleep(1.2)
            yield "late_chunk"

        result = list(helper.stream(delayed_chunk()))

        assert result == ["late_chunk"]

    def test_background_stream_waits_for_delayed_eod_after_producer_finished(self, handler, monkeypatch):
        """producer 已结束但 EOD 暂不可见时，后台消费者不应立即误报失败。"""
        helper = GeneratorStreamingHelper(handler, thread_id="test_delayed_eod", defer_cleanup_on_complete=True)
        producer_thread = threading.Thread(target=lambda: None)
        producer_thread.start()
        producer_thread.join()
        calls = 0

        def delayed_eod(*, timeout, replay_offset):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise TimeoutError
            return [streaming_helper_module.EOD_CHUNK], replay_offset + 1

        monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 0.0)
        monkeypatch.setattr(helper, "_HEARTBEAT_TIMEOUT_GRACE", 0.0)
        monkeypatch.setattr(helper, "_BACKGROUND_HEARTBEAT_RECOVERY_TIMEOUT", 1.0)
        monkeypatch.setattr(helper, "_get_consumer_messages", delayed_eod)

        stream = helper._consume_stream_messages(
            handler.acquire_consumer(helper.thread_id), threading.Event(), False, True, producer_thread=producer_thread
        )

        assert (list(stream), calls) == ([], 3)

    def test_resumed_consumer_waits_for_remote_producer_eod_after_cancel(self, handler, monkeypatch):
        """跨 Worker 时本地无 producer_thread，消费者也不能自行伪造取消终态。"""
        helper = GeneratorStreamingHelper(handler, thread_id="test_remote_producer_cancel")
        cancel_event = threading.Event()
        cancel_event.set()
        calls = 0
        notified = []

        def delayed_remote_eod(*, timeout, replay_offset):
            nonlocal calls
            calls += 1
            if calls < 4:
                time.sleep(0.03)
                raise TimeoutError
            return [streaming_helper_module.EOD_CHUNK], replay_offset + 1

        monkeypatch.setattr(helper, "CANCEL_DRAIN_TIMEOUT", 0.05)
        monkeypatch.setattr(helper, "_get_consumer_messages", delayed_remote_eod)
        monkeypatch.setattr(helper, "_notify_consumer_cancelled_safely", lambda: notified.append(True))
        consumer_id = handler.acquire_consumer(helper.thread_id)

        stream = helper._consume_stream_messages(
            consumer_id,
            cancel_event,
            False,
            False,
            producer_thread=None,
        )

        assert list(stream) == []
        assert calls == 4
        assert notified == []
        handler.release_consumer(helper.thread_id, consumer_id)

    def test_producer_error_emits_terminal_events(self, handler):
        """producer 异常应形成完整终止事件对并同步分发。"""
        helper = GeneratorStreamingHelper(handler, thread_id="test_producer_error")
        dispatched = []
        completed = []

        def broken_generator():
            yield "chunk"
            raise RuntimeError("producer failed")

        result = list(
            helper.stream(
                broken_generator(),
                event_handler=dispatched.append,
                on_complete=lambda: completed.append(True),
            )
        )

        assert result[0] == "chunk"
        assert _event_types(result[1:]) == ["RUN_ERROR", "RUN_FINISHED"]
        assert [event.type for event in dispatched] == [EventType.RUN_ERROR, EventType.RUN_FINISHED]
        assert completed == [True]

    def test_cancel_terminal_events_retry_after_partial_queue_failure(self, handler, monkeypatch):
        """取消终态第二帧首次入队失败时，只重试缺失帧且完成回调仅执行一次。"""
        thread_id = "test_cancel_partial_queue_failure"
        run_id = "run-cancel-partial"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        cancel_event = helper.prepare_run(run_id)
        original_put = handler.put
        failed_once = False
        dispatched = []
        completed = []

        def fail_first_run_finished(tid, message):
            nonlocal failed_once
            if not failed_once and isinstance(message, str) and '"type":"RUN_FINISHED"' in message:
                failed_once = True
                raise RuntimeError("transient queue failure")
            original_put(tid, message)

        monkeypatch.setattr(handler, "put", fail_first_run_finished)
        assert GeneratorStreamingHelper.cancel(thread_id, handler, run_id=run_id)

        result = list(
            helper.stream(
                iter(["must_not_be_emitted"]),
                event_handler=dispatched.append,
                on_complete=lambda: completed.append(True),
                expected_run_id=run_id,
                cancel_event=cancel_event,
            )
        )

        assert failed_once
        assert _event_types(result) == ["RUN_ERROR", "RUN_FINISHED"]
        assert [event.type for event in dispatched] == [EventType.RUN_ERROR, EventType.RUN_FINISHED]
        assert completed == [True]

    def test_consumer_registration_failure_releases_prepared_cancel_event(self, handler, monkeypatch):
        """消费者注册失败时不得残留 Run 级取消事件。"""
        thread_id = "test_consumer_registration_failure"
        run_id = "run-registration-failure"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        cancel_event = helper.prepare_run(run_id)

        def fail_acquire(_thread_id):
            raise RuntimeError("consumer registration failed")

        monkeypatch.setattr(handler, "acquire_consumer", fail_acquire)

        with pytest.raises(RuntimeError, match="consumer registration failed"):
            list(helper.stream(iter([]), expected_run_id=run_id, cancel_event=cancel_event))

        assert not GeneratorStreamingHelper.is_registered(thread_id, handler, run_id=run_id)

    def test_producer_releases_lock_when_eod_flush_fails(self, handler, monkeypatch):
        thread_id = "test_producer_flush_failure"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        assert handler.acquire_producer(thread_id)

        def fail_flush(thread_id):
            raise RuntimeError("flush failed")

        monkeypatch.setattr(handler, "flush", fail_flush)

        with pytest.raises(RuntimeError, match="flush failed"):
            helper._producer(
                iter(["chunk"]),
                release_producer=True,
            )

        assert handler.acquire_producer(thread_id)

    def test_producer_waits_for_background_eod_commit_before_completion(self, monkeypatch):
        handler = ReplayFromStartHandler()
        helper = GeneratorStreamingHelper(handler, thread_id="test_eod_recovery")
        committed_event = None
        lifecycle = []

        def register(_thread_id, event):
            nonlocal committed_event
            committed_event = event

        monkeypatch.setattr(handler, "register_eod_commit_event", register, raising=False)
        monkeypatch.setattr(handler, "unregister_eod_commit_event", lambda *_args: None, raising=False)

        def fail_after_background_commit(_thread_id):
            committed_event.set()
            raise RuntimeError("sync flush failed")

        monkeypatch.setattr(handler, "flush", fail_after_background_commit)
        helper._producer(iter(["chunk"]), on_complete=lambda: lifecycle.append("complete"))

        assert lifecycle == ["complete"]

    def test_stream_treats_missing_eod_as_error(self, handler, monkeypatch):
        """即使 producer 标记成功，未消费到 EOD 也不能静默判定完成。"""
        thread_id = "test_stream_finished_without_eod"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        consumer_id = handler.acquire_consumer(thread_id)
        completed_threads = []

        def timeout_without_messages(*, timeout, replay_offset):
            raise TimeoutError

        producer_thread = threading.Thread(target=lambda: None)
        producer_thread.start()
        producer_thread.join()

        monkeypatch.setattr(handler, "CONSUMER_HEARTBEAT_TIMEOUT", 0.0)
        monkeypatch.setattr(helper, "_get_consumer_messages", timeout_without_messages)
        monkeypatch.setattr(handler, "mark_completed", completed_threads.append)

        stream = helper._consume_stream_messages(
            consumer_id=consumer_id,
            cancel_event=threading.Event(),
            is_resuming=False,
            enable_heartbeat_check=True,
            producer_thread=producer_thread,
        )

        error_chunk = next(stream)
        assert _event_types([error_chunk]) == ["RAW"]
        with pytest.raises(RuntimeError, match="生产者心跳超时"):
            next(stream)
        assert completed_threads == []


class TestMessageHandlerConfig:
    """测试 Config 解析 + 工厂 + RabbitMQ 降级"""

    @pytest.mark.parametrize(
        ("env_handler_type", "env_rabbitmq_host", "env_redis_url", "expected_type"),
        [
            ("", "", "", MessageHandlerType.INMEMORY),  # 无配置 → InMemory
            ("auto", "", "", MessageHandlerType.INMEMORY),  # 显式 auto → 自动检测
            ("inmemory", "", "", MessageHandlerType.INMEMORY),  # 显式 inmemory
            ("rabbitmq", "", "", MessageHandlerType.RABBITMQ),  # 显式 rabbitmq
            ("redis", "", "", MessageHandlerType.REDIS),  # 显式 redis
            ("", "localhost", "", MessageHandlerType.RABBITMQ),  # 有 MQ 配置 → 自动 RabbitMQ
            ("", "localhost", "redis://localhost", MessageHandlerType.REDIS),  # Redis 专用配置优先
            ("inmemory", "localhost", "redis://localhost", MessageHandlerType.INMEMORY),  # 显式覆盖配置
            ("", " ", " ", MessageHandlerType.INMEMORY),  # 纯空白不视为有效配置
        ],
    )
    def test_resolve_handler_type(self, monkeypatch, env_handler_type, env_rabbitmq_host, env_redis_url, expected_type):
        """Config.resolve_handler_type 在不同环境变量组合下的行为"""
        monkeypatch.setenv(EnvVarNames.HANDLER_TYPE, env_handler_type)
        monkeypatch.setenv(EnvVarNames.RABBITMQ_HOST, env_rabbitmq_host)
        monkeypatch.setenv(EnvVarNames.RABBITMQ_STREAM_PORT, "")
        monkeypatch.setenv(EnvVarNames.REDIS_URL, env_redis_url)
        assert MessageHandlerConfig.resolve_handler_type() == expected_type

    def test_invalid_explicit_handler_type_fails_fast(self, monkeypatch):
        monkeypatch.setenv(EnvVarNames.HANDLER_TYPE, "redsi")

        with pytest.raises(RuntimeError, match="Invalid MESSAGE_HANDLER_TYPE"):
            MessageHandlerConfig.resolve_handler_type()

    def test_create_handler_rabbitmq_fallback(self, monkeypatch):
        """_create_handler 传入 RABBITMQ 但无 MQ 配置时应降级为 InMemory"""
        monkeypatch.setenv(EnvVarNames.RABBITMQ_HOST, "")
        monkeypatch.setenv(EnvVarNames.RABBITMQ_STREAM_PORT, "")
        handler = _create_handler(MessageHandlerType.RABBITMQ)
        assert isinstance(handler, InMemoryQueueMessageHandler)

    def test_create_handler_redis_without_url_fails(self, monkeypatch):
        monkeypatch.setenv(EnvVarNames.REDIS_URL, "")
        with pytest.raises(RuntimeError, match="MESSAGE_REDIS_URL"):
            _create_handler(MessageHandlerType.REDIS)

    def test_create_handler_selects_rabbitmq_stream_when_port_is_configured(self, monkeypatch):
        selected_handler = InMemoryQueueMessageHandler()
        monkeypatch.setenv(EnvVarNames.RABBITMQ_HOST, "rabbitmq.local")
        monkeypatch.setenv(EnvVarNames.RABBITMQ_STREAM_PORT, "5552")
        monkeypatch.setattr(
            "aidev_agent.services.messages_handler.factory.RabbitMQStreamMessageHandler",
            lambda: selected_handler,
        )

        assert _create_handler(MessageHandlerType.RABBITMQ) is selected_handler

    def test_create_handler_stream_port_without_host_fails_fast(self, monkeypatch):
        monkeypatch.setenv(EnvVarNames.RABBITMQ_HOST, "")
        monkeypatch.setenv(EnvVarNames.RABBITMQ_STREAM_PORT, "5552")

        with pytest.raises(RuntimeError, match="RABBITMQ_HOST and RABBITMQ_STREAM_PORT"):
            _create_handler(MessageHandlerType.RABBITMQ)

    def test_factory_returns_singleton_by_type(self):
        """工厂按类型 get() 返回单例"""
        h1 = message_handler_factory.get(MessageHandlerType.INMEMORY.value)
        h2 = message_handler_factory.get(MessageHandlerType.INMEMORY.value)
        assert h1 is h2
        assert isinstance(h1, InMemoryQueueMessageHandler)

    def test_factory_only_creates_selected_external_backend(self, monkeypatch):
        """未选中的外部 backend 不应在模块初始化时建立连接。"""
        selected_handler = InMemoryQueueMessageHandler()
        created_types = []

        monkeypatch.setattr(MessageHandlerConfig, "resolve_handler_type", lambda: MessageHandlerType.REDIS)

        def create_handler(handler_type):
            created_types.append(handler_type)
            return selected_handler

        monkeypatch.setattr("aidev_agent.services.messages_handler.factory._create_handler", create_handler)

        factory = _init_factory()

        assert created_types == [MessageHandlerType.REDIS]
        assert factory.get() is selected_handler
        assert factory.get(MessageHandlerType.REDIS.value) is selected_handler
        assert isinstance(factory.get(MessageHandlerType.INMEMORY.value), InMemoryQueueMessageHandler)
