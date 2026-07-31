"""测试 InMemoryQueueMessageHandler 的基本功能"""

import contextlib
import json
import threading
import time

import pytest

import aidev_agent.services.messages_handler.streaming_helper as streaming_helper_module
from aidev_agent.enums import MessageHandlerType
from aidev_agent.services.messages_handler import (
    CANCELLED_CHUNK,
    EOD_CHUNK,
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
    message_handler_factory,
)
from aidev_agent.services.messages_handler.config import MessageHandlerConfig
from aidev_agent.services.messages_handler.constants import EnvVarNames
from aidev_agent.services.messages_handler.factory import _create_handler
from aidev_agent.utils.event import RunId, emit_run_finished_event


def _make_run_finished_chunk(thread_id: str, run_id: str) -> str:
    """生成 RUN_FINISHED SSE 字符串，用于测试期望值对比。"""
    return emit_run_finished_event(thread_id=thread_id, run_id=run_id)


def _make_replay_segment_marker(segment_id: str) -> str:
    return f": aidev-replay-segment {segment_id}\n\n"


def _make_mixed_runtime_frames(count: int) -> list[str]:
    event_types = ("TEXT_MESSAGE_CONTENT", "TOOL_CALL_ARGS", "STATE_DELTA")
    return [
        f"data: {json.dumps({'type': event_types[index % len(event_types)], 'sequence': index})}\n\n"
        for index in range(count)
    ]


def _consume_replay_concurrently(handler, thread_id, prelude_extractor):
    results = []
    errors = []

    def consume():
        try:
            helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
            results.append(list(helper.stream(iter(()), prelude_extractor=prelude_extractor)))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=consume) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    return results, errors, threads


class ReplayFromStartHandler:
    """测试用 replay handler：模拟 RabbitMQ 的非破坏性会话日志读取。"""

    def __init__(self):
        self.messages: dict[str, list] = {}
        self.baselines: dict[tuple[str, str], list] = {}
        self.active_consumers: set[tuple[str, str]] = set()
        self.producer_locks: set[str] = set()
        self.completed_threads: list[str] = []
        self.saved_baselines: list[tuple[str, str, list]] = []
        self.put_calls: list[tuple[str, object]] = []
        self.operations: list[tuple[str, object]] = []
        self.fail_publish_baseline = False
        self.fail_publish_marker = False
        self.fail_flush = False
        self.on_producer_acquired = None
        self.message_wait_started = threading.Event()
        self.stopped_threads: set[str] = set()
        self._consumer_seq = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    def supports_replay_from_start(self) -> bool:
        return True

    def put(self, thread_id, message):
        with self._condition:
            self.messages.setdefault(thread_id, []).append(message)
            self.put_calls.append((thread_id, message))
            self.operations.append(("put", message))
            self._condition.notify_all()

    def flush(self, thread_id):
        if self.fail_flush:
            raise RuntimeError("marker flush failed")

    def publish_replay_segment_start(self, thread_id, segment_id, head_frames, segment_marker):
        self.operations.append(("publish_baseline", segment_id))
        if self.fail_publish_baseline:
            raise RuntimeError("baseline publish failed")
        frames = list(head_frames)
        with self._lock:
            self.baselines[(thread_id, segment_id)] = frames
            self.saved_baselines.append((thread_id, segment_id, frames))
        if self.fail_publish_marker:
            raise RuntimeError("marker publish failed")
        self.put(thread_id, segment_marker)
        self.operations.append(("publish_segment", segment_id))

    def get_replay_baseline(self, thread_id, segment_id):
        with self._lock:
            frames = self.baselines.get((thread_id, segment_id))
            return list(frames) if frames is not None else None

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
                    self.message_wait_started.set()
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
        if self.on_producer_acquired:
            self.on_producer_acquired()
        return True

    def release_producer(self, thread_id):
        with self._lock:
            self.producer_locks.discard(thread_id)

    def acquire_consumer(self, thread_id):
        with self._lock:
            consumer_id = f"consumer-{self._consumer_seq}"
            self._consumer_seq += 1
            self.active_consumers.add((thread_id, consumer_id))
        return consumer_id

    def wait_for_previous_consumer(self, thread_id, timeout=3.0):
        return True

    def check_consumer(self, thread_id, consumer_id):
        pass

    def release_consumer(self, thread_id, consumer_id):
        with self._lock:
            self.active_consumers.discard((thread_id, consumer_id))

    def has_active_consumer(self, thread_id):
        with self._lock:
            return any(tid == thread_id for tid, _ in self.active_consumers)

    def is_stopped(self, thread_id):
        with self._lock:
            return thread_id in self.stopped_threads

    def clear_stopped(self, thread_id):
        with self._lock:
            self.stopped_threads.discard(thread_id)

    def mark_completed(self, thread_id):
        with self._condition:
            self.completed_threads.append(thread_id)
            self.messages.pop(thread_id, None)
            self.baselines = {key: frames for key, frames in self.baselines.items() if key[0] != thread_id}
            self._condition.notify_all()

    def clear(self, thread_id):
        with self._condition:
            self.messages.pop(thread_id, None)
            self.baselines = {key: frames for key, frames in self.baselines.items() if key[0] != thread_id}
            self._condition.notify_all()

    def clear_cancel_signal(self, thread_id):
        pass

    def check_cancel_signal(self, thread_id):
        return False

    def set_cancel_signal(self, thread_id):
        return False

    def notify_consumer_cancelled(self, thread_id):
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
    def test_new_producer_persists_segment_baseline_before_starting_runtime(self):
        thread_id = "test_new_segment_baseline"
        handler = ReplayFromStartHandler()

        def runtime():
            handler.operations.append(("generator_started", thread_id))
            yield "runtime"

        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                runtime(),
                prelude_extractor=lambda generator: (["head"], generator),
            )
        )

        saved_thread_id, segment_id, baseline = handler.saved_baselines[0]
        marker = _make_replay_segment_marker(segment_id)
        operation_names = [name for name, _ in handler.operations]
        assert (saved_thread_id, baseline) == (thread_id, ["head"])
        assert result == ["head", "runtime"]
        assert (thread_id, marker) in handler.put_calls
        marker_index = handler.operations.index(("put", marker))
        assert operation_names.index("publish_baseline") < marker_index
        assert marker_index < operation_names.index("publish_segment") < operation_names.index("generator_started")

    def test_cached_segment_replays_saved_baseline_without_local_extraction(self):
        thread_id = "test_cached_segment_baseline"
        segment_id = "segment-cached"
        handler = ReplayFromStartHandler()
        handler.publish_replay_segment_start(
            thread_id,
            segment_id,
            ["saved-head"],
            _make_replay_segment_marker(segment_id),
        )
        handler.put(thread_id, "runtime")
        handler.put(thread_id, EOD_CHUNK)

        def reject_local_extraction(_generator):
            pytest.fail("cached segment must not extract a connection-local baseline")

        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(()),
                prelude_extractor=reject_local_extraction,
            )
        )

        assert result == ["saved-head", "runtime"]

    def test_large_mixed_segment_replays_identically_to_two_concurrent_consumers(self):
        thread_id = "test_large_mixed_segment"
        segment_id = "segment-large"
        handler = BarrierReplayFromStartHandler(parties=2)
        baseline = ["snapshot-head-0", "snapshot-head-1"]
        runtime_frames = _make_mixed_runtime_frames(1537)
        handler.publish_replay_segment_start(
            thread_id,
            segment_id,
            baseline,
            _make_replay_segment_marker(segment_id),
        )
        for frame in runtime_frames:
            handler.put(thread_id, frame)
        handler.put(thread_id, EOD_CHUNK)

        def reject_local_extraction(_generator):
            pytest.fail("new-format replay must use the producer baseline")

        results, errors, threads = _consume_replay_concurrently(handler, thread_id, reject_local_extraction)
        expected = baseline + runtime_frames
        assert errors == []
        assert all(not thread.is_alive() for thread in threads)
        assert results == [expected, expected]

    def test_active_producer_without_marker_waits_for_saved_segment_baseline(self):
        thread_id = "test_wait_for_active_producer_marker"
        segment_id = "segment-delayed"
        handler = ReplayFromStartHandler()
        handler.producer_locks.add(thread_id)

        def publish_segment():
            handler.message_wait_started.wait(timeout=1)
            handler.publish_replay_segment_start(
                thread_id,
                segment_id,
                ["saved-head"],
                _make_replay_segment_marker(segment_id),
            )
            handler.put(thread_id, "runtime")
            handler.put(thread_id, EOD_CHUNK)
            handler.release_producer(thread_id)

        publisher = threading.Thread(target=publish_segment)
        publisher.start()
        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(()),
                prelude_extractor=lambda _generator: pytest.fail("must wait for the producer marker"),
            )
        )
        publisher.join(timeout=2)
        assert handler.message_wait_started.is_set()
        assert not publisher.is_alive()
        assert result == ["saved-head", "runtime"]

    def test_segment_marker_without_baseline_fails_instead_of_local_fallback(self):
        thread_id = "test_missing_segment_baseline"
        segment_id = "segment-missing"
        handler = ReplayFromStartHandler()
        handler.put(thread_id, _make_replay_segment_marker(segment_id))
        handler.put(thread_id, EOD_CHUNK)

        stream = GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
            iter(()),
            prelude_extractor=lambda _generator: pytest.fail("missing baseline must not use local state"),
        )

        with pytest.raises(RuntimeError, match="replay baseline missing"):
            list(stream)

    def test_legacy_replay_without_segment_marker_uses_local_baseline(self):
        thread_id = "test_legacy_replay_baseline"
        handler = ReplayFromStartHandler()
        handler.put(thread_id, "legacy-runtime")
        handler.put(thread_id, EOD_CHUNK)
        extracted = []

        def extract_local_baseline(generator):
            extracted.append(True)
            return ["local-head"], generator

        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(()),
                prelude_extractor=extract_local_baseline,
            )
        )

        assert extracted == [True]
        assert result == ["local-head", "legacy-runtime"]

    def test_pending_segment_after_producer_lock_is_replayed_without_clear(self):
        thread_id = "test_pending_after_producer_lock"
        segment_id = "segment-raced"
        handler = ReplayFromStartHandler()

        def publish_previous_segment():
            handler.publish_replay_segment_start(
                thread_id,
                segment_id,
                ["saved-head"],
                _make_replay_segment_marker(segment_id),
            )
            handler.put(thread_id, "runtime")
            handler.put(thread_id, EOD_CHUNK)

        handler.on_producer_acquired = publish_previous_segment
        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(()),
                prelude_extractor=lambda _generator: pytest.fail("must replay the raced segment"),
            )
        )

        assert result == ["saved-head", "runtime"]

    def test_stopped_new_segment_replays_saved_baseline_then_one_stopped_terminal(self):
        thread_id = "test_stopped_segment_baseline"
        segment_id = "segment-stopped"
        handler = ReplayFromStartHandler()
        handler.stopped_threads.add(thread_id)
        handler.publish_replay_segment_start(
            thread_id,
            segment_id,
            ["saved-head"],
            _make_replay_segment_marker(segment_id),
        )
        handler.put(thread_id, "runtime")
        handler.put(thread_id, EOD_CHUNK)

        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(()),
                prelude_extractor=lambda _generator: pytest.fail("stopped segment must use saved baseline"),
            )
        )

        stopped_terminal = _make_run_finished_chunk(thread_id, RunId.STOPPED)
        assert result == ["saved-head", "runtime", stopped_terminal]
        assert result.count(stopped_terminal) == 1
        assert thread_id not in handler.stopped_threads

    def test_new_segment_replay_preserves_flow_agent_start(self):
        thread_id = "test_segment_flow_agent_start"
        segment_id = "segment-flow-agent"
        flow_agent_start = 'data: {"type":"CUSTOM","name":"flow_agent_start","value":{}}\n\n'
        handler = ReplayFromStartHandler()
        handler.publish_replay_segment_start(
            thread_id,
            segment_id,
            ["saved-head"],
            _make_replay_segment_marker(segment_id),
        )
        handler.put(thread_id, flow_agent_start)
        handler.put(thread_id, EOD_CHUNK)

        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(()),
                prelude_extractor=lambda _generator: pytest.fail("new segment must use saved baseline"),
            )
        )

        assert result == ["saved-head", flow_agent_start]

    @pytest.mark.parametrize(
        ("failure_attribute", "error_message"),
        [
            ("fail_publish_baseline", "baseline publish failed"),
            ("fail_publish_marker", "marker publish failed"),
        ],
    )
    def test_segment_initialization_failure_does_not_start_runtime(self, failure_attribute, error_message):
        thread_id = f"test_segment_init_{failure_attribute}"
        handler = ReplayFromStartHandler()
        setattr(handler, failure_attribute, True)
        runtime_started = threading.Event()

        def runtime():
            runtime_started.set()
            yield "runtime"

        stream = GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
            runtime(),
            prelude_extractor=lambda generator: (["head"], generator),
        )

        with pytest.raises(RuntimeError, match=error_message):
            list(stream)
        assert not runtime_started.is_set()
        assert thread_id not in handler.producer_locks

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
        assert thread_id not in handler.messages
        assert handler.completed_threads == [thread_id]

    def test_replay_mode_runs_on_complete_in_producer_once(self):
        thread_id = "test_replay_on_complete_once"
        handler = ReplayFromStartHandler()
        completed = []

        result = list(
            GeneratorStreamingHelper(handler, thread_id=thread_id).stream(
                iter(["chunk_0"]),
                on_complete=lambda: completed.append(True),
            )
        )

        assert result == ["chunk_0"]
        assert completed == [True]
        assert thread_id not in handler.producer_locks


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
        # 使用 GeneratorStreamingHelper.cancel() 而不是 handler.request_cancel()
        GeneratorStreamingHelper.cancel(thread_id, handler)
        GeneratorStreamingHelper.cancel(thread_id, handler)
        GeneratorStreamingHelper.cancel(thread_id, handler)

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

    def test_stream_on_complete_exception_is_swallowed(self, handler):
        """on_complete 抛异常时不影响流返回和队列清理。"""
        thread_id = "test_stream_on_complete_error"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        callback_called = []

        def broken_on_complete():
            callback_called.append(True)
            raise RuntimeError("boom")

        result = list(helper.stream(iter(["chunk_0"]), on_complete=broken_on_complete))

        assert result == ["chunk_0"]
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

    def test_stream_keeps_alive_when_generator_blocked(self, handler, monkeypatch):
        """generator 长时间无产出时，独立心跳应维持连接且不超时。"""
        thread_id = "test_stream_heartbeat_keepalive"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 0.05)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_TIMEOUT", 0.2)
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
        assert result == ["late_chunk"]
        assert heartbeat_count > 0

    def test_stream_raises_when_heartbeat_timeout(self, handler, monkeypatch):
        """心跳发送慢于超时阈值时，消费者应抛出心跳超时异常。"""
        thread_id = "test_stream_heartbeat_timeout"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_INTERVAL", 1.0)
        monkeypatch.setattr(streaming_helper_module, "HEARTBEAT_TIMEOUT", 0.2)

        def slow_first_chunk():
            time.sleep(0.8)
            yield "late_chunk"

        with pytest.raises(RuntimeError, match="心跳超时"):
            list(helper.stream(slow_first_chunk()))


class TestMessageHandlerConfig:
    """测试 Config 解析 + 工厂 + RabbitMQ 降级"""

    @pytest.mark.parametrize(
        ("env_handler_type", "env_rabbitmq_host", "expected_type"),
        [
            ("", "", MessageHandlerType.INMEMORY),  # 无配置 → InMemory
            ("inmemory", "", MessageHandlerType.INMEMORY),  # 显式 inmemory
            ("rabbitmq", "", MessageHandlerType.RABBITMQ),  # 显式 rabbitmq
            ("", "localhost", MessageHandlerType.RABBITMQ),  # 有 MQ 配置 → 自动 RabbitMQ
            ("inmemory", "localhost", MessageHandlerType.INMEMORY),  # 显式覆盖 MQ 配置
        ],
    )
    def test_resolve_handler_type(self, monkeypatch, env_handler_type, env_rabbitmq_host, expected_type):
        """Config.resolve_handler_type 在不同环境变量组合下的行为"""
        monkeypatch.setenv(EnvVarNames.HANDLER_TYPE, env_handler_type)
        monkeypatch.setenv(EnvVarNames.RABBITMQ_HOST, env_rabbitmq_host)
        assert MessageHandlerConfig.resolve_handler_type() == expected_type

    def test_create_handler_rabbitmq_fallback(self, monkeypatch):
        """_create_handler 传入 RABBITMQ 但无 MQ 配置时应降级为 InMemory"""
        monkeypatch.setenv(EnvVarNames.RABBITMQ_HOST, "")
        handler = _create_handler(MessageHandlerType.RABBITMQ)
        assert isinstance(handler, InMemoryQueueMessageHandler)

    def test_factory_returns_singleton_by_type(self):
        """工厂按类型 get() 返回单例"""
        h1 = message_handler_factory.get(MessageHandlerType.INMEMORY.value)
        h2 = message_handler_factory.get(MessageHandlerType.INMEMORY.value)
        assert h1 is h2
        assert isinstance(h1, InMemoryQueueMessageHandler)
