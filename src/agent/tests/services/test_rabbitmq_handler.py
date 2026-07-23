import asyncio
import contextlib
import json
import multiprocessing
import os
import pickle
import threading
import time

import pytest
from ag_ui.core import EventType, TextMessageContentEvent, TextMessageStartEvent
from ag_ui.encoder import EventEncoder
from aidev_agent.core.ag_ui.types import (
    ExtendAssistantMessage,
    ExtendUserMessage,
    MessageSnapshotEventExtend,
)
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent import ChatCompletionAgent
from aidev_agent.services.messages_handler import EOD_CHUNK, GeneratorStreamingHelper
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler
from aidev_agent.utils.async_utils import async_to_sync_generator

# 标记：所有测试均需要 RabbitMQ
pytestmark = pytest.mark.skipif(
    not os.getenv("RABBITMQ_HOST"),
    reason="Live test requires RABBITMQ_HOST",
)


@pytest.fixture()
def handler():
    """创建 handler 实例"""
    return RabbitMQMessageHandler()


@pytest.fixture()
def thread_id(request, handler):
    """为每个测试生成唯一的 thread_id，测试后自动清理"""
    tid = f"test-mq-{request.node.name}-{int(time.time() * 1000) % 100000}"
    handler.clear(tid)
    yield tid
    with contextlib.suppress(Exception):
        handler.mark_completed(tid)


class DelayedPublishChannel:
    def __init__(self, channel, target_message, publish_started, allow_publish):
        self._channel = channel
        self._target_message = target_message
        self._publish_started = publish_started
        self._allow_publish = allow_publish

    def __getattr__(self, name):
        return getattr(self._channel, name)

    def basic_publish(self, *args, **kwargs):
        body = kwargs.get("body")
        if body is None and len(args) >= 3:
            body = args[2]
        try:
            is_target = pickle.loads(body) == self._target_message
        except Exception:
            is_target = False
        if is_target:
            self._publish_started.set()
            assert self._allow_publish.wait(timeout=3)
        return self._channel.basic_publish(*args, **kwargs)


def _hold_producer_lock_and_publish(env_vars, thread_id, messages, publish_event, release_event, result_queue):
    """模拟另一个 worker：持有 producer lock，收到信号后向真实 RabbitMQ 发布 replay。"""
    for key, value in env_vars.items():
        os.environ[key] = value
    RabbitMQMessageHandler._instance = None
    handler = RabbitMQMessageHandler()
    acquired = handler.acquire_producer(thread_id)
    result_queue.put(("acquired", acquired))
    if not acquired:
        return

    try:
        if not publish_event.wait(timeout=5):
            result_queue.put(("error", "publish signal timeout"))
            return
        for message in messages:
            handler.put(thread_id, message)
        handler.flush(thread_id)
        result_queue.put(("published", len(messages)))
        release_event.wait(timeout=5)
    finally:
        handler.release_producer(thread_id)


def _run_remote_producer_race(handler, thread_id, monkeypatch, head_frames, replay_frames):
    env_keys = ["RABBITMQ_HOST", "RABBITMQ_PORT", "RABBITMQ_USER", "RABBITMQ_PASSWORD", "RABBITMQ_VHOST"]
    env_vars = {key: os.environ[key] for key in env_keys if key in os.environ}
    ctx = multiprocessing.get_context("spawn")
    publish_event = ctx.Event()
    release_event = ctx.Event()
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_hold_producer_lock_and_publish,
        args=(env_vars, thread_id, replay_frames, publish_event, release_event, result_queue),
    )
    original_acquire_producer = handler.acquire_producer

    def acquire_producer_then_publish(current_thread_id):
        acquired = original_acquire_producer(current_thread_id)
        if not acquired:
            publish_event.set()
        return acquired

    monkeypatch.setattr(handler, "acquire_producer", acquire_producer_then_publish)
    process.start()
    try:
        assert result_queue.get(timeout=5) == ("acquired", True)
        assert handler.has_pending_messages(thread_id) is False
        output = list(
            GeneratorStreamingHelper(handler, thread_id).stream(
                iter(()),
                head_frames=head_frames,
                replay_head_transform=ChatCompletionAgent._dedup_snapshot_head_frames,
            )
        )
        assert result_queue.get(timeout=5) == ("published", len(replay_frames))
        return output
    finally:
        publish_event.set()
        release_event.set()
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
            raise AssertionError("remote producer process did not exit")
        assert process.exitcode == 0


class TestRabbitMQMessageHandler:
    def _get_open_channel_count(self, handler: RabbitMQMessageHandler) -> int:
        """Return open AMQP channels held by one pooled connection."""
        connection = handler._connection_pool.get_connection()
        try:
            channels = getattr(getattr(connection, "_impl", None), "_channels", {})
            return len(channels)
        finally:
            handler._connection_pool.release_connection(connection)

    def _wait_until_empty(self, handler: RabbitMQMessageHandler, thread_id: str, timeout: float = 2.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if handler.is_empty(thread_id):
                return
            time.sleep(0.1)
        assert handler.is_empty(thread_id) is True

    def _consume_since_offset(self, handler, thread_id, offset, result, error):
        try:
            result.append(handler.get_messages_since(thread_id, offset, timeout=1))
        except Exception as exc:
            error.append(exc)

    def _patch_delayed_publish(self, monkeypatch, handler, target_message):
        publish_started = threading.Event()
        allow_publish = threading.Event()

        def wrap_context(context_factory):
            @contextlib.contextmanager
            def wrapped(*args, **kwargs):
                with context_factory(*args, **kwargs) as channel:
                    yield DelayedPublishChannel(channel, target_message, publish_started, allow_publish)

            return wrapped

        monkeypatch.setattr(handler, "_with_channel", wrap_context(handler._with_channel))
        monkeypatch.setattr(handler, "_with_replay_lock", wrap_context(handler._with_replay_lock))
        return publish_started, allow_publish

    def test_repeated_operations_do_not_accumulate_open_channels(self, handler, thread_id):
        """Repeated RabbitMQ operations should close their temporary AMQP channels."""
        handler.put(thread_id, "seed")
        handler.flush(thread_id)

        for _ in range(20):
            assert handler.get_cached_count(thread_id) == 1

        assert self._get_open_channel_count(handler) <= 1

    def test_live_test(self, handler, thread_id):
        """实际连接 RabbitMQ 进行测试"""
        # 发送 3 条消息
        handler.put(thread_id, "test_msg_1")
        handler.put(thread_id, "test_msg_2")
        handler.put(thread_id, "test_msg_3")

        # 立即推送到 RabbitMQ（测试需要）
        handler.flush(thread_id)

        # 验证消息数量（主队列）
        assert handler.get_cached_count(thread_id) == 3

        # 验证有未消费的消息
        assert handler.has_pending_messages(thread_id) is True

        # 获取消息（消息会被移动到死信队列）
        messages = handler.get(thread_id, timeout=1)
        assert messages == ["test_msg_1", "test_msg_2", "test_msg_3"]

        # 主队列应该为空，消息已移动到死信队列
        assert handler.get_cached_count(thread_id) == 0
        assert handler._get_dlq_count(thread_id) == 3

        # 仍然有未消费的消息（在死信队列中）
        assert handler.has_pending_messages(thread_id) is True

        # 恢复消息到主队列（模拟断点续传）
        restored = handler.restore_messages(thread_id)
        assert restored == 3

        # 消息已恢复到主队列
        assert handler.get_cached_count(thread_id) == 3
        assert handler._get_dlq_count(thread_id) == 0

        # 再次获取消息
        messages = handler.get(thread_id, timeout=1)
        assert messages == ["test_msg_1", "test_msg_2", "test_msg_3"]

        # 标记完成并清理
        handler.mark_completed(thread_id)

        # 验证所有队列已清空
        assert handler.is_empty(thread_id) is True
        assert handler.get_cached_count(thread_id) == 0
        assert handler._get_dlq_count(thread_id) == 0

    def test_live_chat(self, handler):
        """实际连接 LLM + RabbitMQ 的端到端流式测试"""
        llm = ChatModel.get_setup_instance(model="qwen3")
        agent = ChatCompletionAgent(
            chat_model=llm,
            chat_history=[
                ChatPrompt(
                    role="system",
                    content="You are a professional translator, please help translate the user input to English.",
                ),
                ChatPrompt(role="user", content="안녕하세요"),
            ],
        )
        stream_gen = agent.execute(ExecuteKwargs(stream=True))
        thread_id = "thread-live-generator-streaming"
        helper = GeneratorStreamingHelper(handler, thread_id)

        # 清理可能存在的旧数据
        handler.clear(thread_id)

        try:
            # 启动流并消费所有消息，确保生产者线程完成
            with open("text.log", "w") as fo:
                for each in helper.stream(async_to_sync_generator(stream_gen)):
                    fo.write(each)

            # 验证队列已清空（流已完成）
            assert handler.is_empty(thread_id) is True
        finally:
            with contextlib.suppress(Exception):
                handler.mark_completed(thread_id)

    def test_live_generator_streaming_with_queue(self, handler, thread_id):
        """测试流式消息的生产和消费

        验证：
        1. 流式消息可以正确生产和消费
        2. 生产者完成后由延迟清理回收队列
        """

        async def gen():
            for i in range(10):
                await asyncio.sleep(0.05)
                yield f"test_msg_{i}"

        helper = GeneratorStreamingHelper(handler, thread_id)

        # 验证初始状态：没有未消费的消息
        assert handler.has_pending_messages(thread_id) is False

        # 启动流并消费所有消息
        all_messages = list(helper.stream(async_to_sync_generator(gen())))

        # 验证消费到了所有消息（排除可能的 STOPPED 控制标记）
        business_messages = [m for m in all_messages if not m.startswith("<")]
        assert business_messages == [f"test_msg_{i}" for i in range(10)]

        # replay 模式下消费者读到 EOD 后先释放 active consumer；
        # 资源由最后一个完成的 consumer 或 producer 兜底清理线程回收。
        self._wait_until_empty(handler, thread_id)

    def test_concurrent_stream_consumers_replay_same_cached_messages(self, handler, thread_id, monkeypatch):
        """多个真实 RabbitMQ consumer 可以并发 replay 同一批缓存消息。"""
        expected = [f"replay_msg_{i}" for i in range(5)]
        for message in expected:
            handler.put(thread_id, message)
        handler.put(thread_id, EOD_CHUNK)
        handler.flush(thread_id)

        original_acquire_consumer = handler.acquire_consumer
        registered_barrier = threading.Barrier(2)
        results: list[list[str]] = []
        errors: list[Exception] = []

        def acquire_consumer_after_peer_registered(current_thread_id: str) -> str:
            consumer_id = original_acquire_consumer(current_thread_id)
            registered_barrier.wait(timeout=3)
            return consumer_id

        def consume() -> None:
            try:
                stream = GeneratorStreamingHelper(handler, thread_id).stream(iter(()))
                results.append(list(stream))
            except Exception as e:
                errors.append(e)

        monkeypatch.setattr(handler, "acquire_consumer", acquire_consumer_after_peer_registered)

        threads = [threading.Thread(target=consume) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert errors == []
        assert all(not thread.is_alive() for thread in threads)
        assert len(results) == 2
        assert all(result == expected for result in results)

        self._wait_until_empty(handler, thread_id)

    def test_pr672_empty_queue_remote_producer_replay_dedups_snapshot(self, handler, thread_id, monkeypatch):
        """PR #672：远端 producer 持锁但队列尚空时，第二连接仍不能输出重复 messageId。"""
        encoder = EventEncoder()
        snapshot = encoder.encode(
            MessageSnapshotEventExtend(
                type=EventType.MESSAGES_SNAPSHOT,
                messages=[
                    ExtendUserMessage(id="u1", role="user", content="问题"),
                    ExtendAssistantMessage(id="mid", role="assistant", content="半截", status="streaming"),
                ],
            )
        )
        replay_frames = [
            encoder.encode(
                TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id="mid", role="assistant")
            ),
            encoder.encode(
                TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id="mid", delta="完整回答")
            ),
            EOD_CHUNK,
        ]

        output = _run_remote_producer_race(handler, thread_id, monkeypatch, [snapshot], replay_frames)
        payloads = [json.loads(frame.removeprefix("data: ")) for frame in output]
        snapshot_ids = {message.get("messageId") or message.get("id") for message in payloads[0]["messages"]}
        replay_ids = {
            payload.get("messageId") for payload in payloads if payload["type"] == EventType.TEXT_MESSAGE_START
        }

        assert snapshot_ids == {"u1"}
        assert replay_ids == {"mid"}
        assert snapshot_ids.isdisjoint(replay_ids)

    def test_single_consumer_waits_for_in_flight_flush_before_later_buffer(self, handler, thread_id, monkeypatch):
        """单个 consumer 不应在旧 flush 批次发布完成前先吐出后续未提交消息。"""
        handler.put(thread_id, "msg_0")
        handler.flush(thread_id)
        first_messages, offset = handler.get_messages_since(thread_id, 0, timeout=1)
        assert first_messages == ["msg_0"]

        handler._stop_daemon()
        monkeypatch.setattr(handler, "_ensure_daemon_alive", lambda: None)
        try:
            handler.put(thread_id, "msg_1")
            publish_started, allow_publish = self._patch_delayed_publish(monkeypatch, handler, "msg_1")
            result: list[tuple[list[str], int]] = []
            error: list[Exception] = []
            flush_thread = threading.Thread(target=handler.flush, args=(thread_id,), daemon=True)
            consumer_thread = threading.Thread(
                target=self._consume_since_offset, args=(handler, thread_id, offset, result, error), daemon=True
            )
            flush_thread.start()
            assert publish_started.wait(timeout=3)
            handler.put(thread_id, "msg_2")
            consumer_thread.start()
            try:
                consumer_thread.join(timeout=0.3)
                assert consumer_thread.is_alive(), f"consumer returned too early: result={result}, error={error}"
            finally:
                allow_publish.set()
                flush_thread.join(timeout=3)
                consumer_thread.join(timeout=3)

            assert error == []
            assert result == [(["msg_1"], 2)]

            handler.flush(thread_id)
            second_messages, next_offset = handler.get_messages_since(thread_id, 2, timeout=1)

            assert second_messages == ["msg_2"]
            assert next_offset == 3
        finally:
            handler._start_daemon()

    def test_replay_reads_only_rabbitmq_committed_messages(self, handler, thread_id, monkeypatch):
        """Replay 只能读取 RabbitMQ 已提交日志，不能读取本进程未 flush 的 buffer。"""
        handler._stop_daemon()
        monkeypatch.setattr(handler, "_ensure_daemon_alive", lambda: None)

        try:
            handler.put(thread_id, "buffered_only")

            with pytest.raises(TimeoutError):
                handler.get_messages_since(thread_id, 0, timeout=0.2)

            handler.flush(thread_id)
            messages, offset = handler.get_messages_since(thread_id, 0, timeout=1)

            assert messages == ["buffered_only"]
            assert offset == 1
        finally:
            with handler._buffer_lock:
                handler._message_buffer.pop(thread_id, None)
            handler._start_daemon()

    def test_has_pending_messages_includes_in_flight_flush(self, handler, thread_id):
        """本批消息从 buffer 取走但尚未 publish 时，仍应被视为 pending。"""
        handler._stop_daemon()
        try:
            with handler._buffer_lock:
                handler._message_buffer[thread_id] = ["in_flight_msg"]

            messages_to_flush = handler._take_thread_buffer_for_flush(thread_id)
            try:
                assert messages_to_flush == ["in_flight_msg"]
                assert handler.has_pending_messages(thread_id) is True
            finally:
                handler._finish_thread_flush(thread_id, messages_to_restore=messages_to_flush)
        finally:
            handler._start_daemon()

    def test_replay_reader_does_not_block_producer_flush(self, handler, thread_id, monkeypatch):
        """正在等待增量的 replay consumer 不应阻塞 producer flush 新消息。"""
        handler.put(thread_id, "seed")
        handler.flush(thread_id)
        _, offset = handler.get_messages_since(thread_id, 0, timeout=1)

        original_peek = handler._peek_queue_messages
        reader_holding_snapshot = threading.Event()
        release_reader_snapshot = threading.Event()

        def slow_peek(channel, queue_name):
            reader_holding_snapshot.set()
            assert release_reader_snapshot.wait(timeout=3)
            return original_peek(channel, queue_name)

        monkeypatch.setattr(handler, "_peek_queue_messages", slow_peek)

        reader_result: list[tuple[list[str], int]] = []
        reader_error: list[Exception] = []
        reader_thread = threading.Thread(
            target=self._consume_since_offset,
            args=(handler, thread_id, offset, reader_result, reader_error),
            daemon=True,
        )
        reader_thread.start()
        assert reader_holding_snapshot.wait(timeout=3)

        handler.put(thread_id, "msg_after_refresh")
        flush_thread = threading.Thread(target=handler.flush, args=(thread_id,), daemon=True)
        flush_thread.start()

        try:
            flush_thread.join(timeout=0.3)
            assert not flush_thread.is_alive(), "producer flush was blocked by a replay reader snapshot"
        finally:
            release_reader_snapshot.set()
            flush_thread.join(timeout=3)
            reader_thread.join(timeout=3)

        assert reader_error == []
        assert reader_result == [(["msg_after_refresh"], offset + 1)]

    def test_consumer_reconnect_with_dlq(self, handler, thread_id):
        """测试消费者断开后重连可以从死信队列恢复消息

        验证：
        1. 生产者产生消息后，消费者读取消息
        2. 消息被移动到死信队列
        3. 消费者断开后，消息仍在死信队列中
        4. 新的消费者调用 restore_messages 恢复消息
        5. 从主队列重新消费所有消息
        """
        # 模拟生产者产生消息
        for i in range(5):
            handler.put(thread_id, f"msg_{i}")
        handler.put(thread_id, EOD_CHUNK)
        handler.flush(thread_id)

        # 第一个消费者读取部分消息
        messages1 = handler.get(thread_id, timeout=1)
        assert len(messages1) == 6  # 包括 EOD_CHUNK

        # 主队列为空，消息在死信队列
        assert handler.get_cached_count(thread_id) == 0
        assert handler._get_dlq_count(thread_id) == 6

        # 模拟消费者断开（不调用 mark_completed）

        # 新的消费者重连，恢复消息
        restored = handler.restore_messages(thread_id)
        assert restored == 6

        # 消息已恢复到主队列
        assert handler.get_cached_count(thread_id) == 6
        assert handler._get_dlq_count(thread_id) == 0

        # 重新消费所有消息
        messages2 = handler.get(thread_id, timeout=1)
        expected = [f"msg_{i}" for i in range(5)] + [EOD_CHUNK]
        assert messages2 == expected

        # 清理
        handler.mark_completed(thread_id)
        assert handler.is_empty(thread_id) is True

    def test_dlq_mechanism(self, handler, thread_id):
        """测试死信队列机制

        验证：
        1. 消息被消费后进入死信队列
        2. restore_messages 能正确恢复消息
        3. mark_completed 能清空所有队列
        """
        # 发送消息
        handler.put(thread_id, "msg_1")
        handler.put(thread_id, "msg_2")
        handler.flush(thread_id)

        # 初始状态：主队列有消息，死信队列为空
        assert handler.get_cached_count(thread_id) == 2
        assert handler._get_dlq_count(thread_id) == 0

        # 消费消息
        messages = handler.get(thread_id, timeout=1)
        assert messages == ["msg_1", "msg_2"]

        # 消费后：主队列为空，死信队列有消息
        assert handler.get_cached_count(thread_id) == 0
        assert handler._get_dlq_count(thread_id) == 2

        # 恢复消息
        handler.restore_messages(thread_id)

        # 恢复后：主队列有消息，死信队列为空
        assert handler.get_cached_count(thread_id) == 2
        assert handler._get_dlq_count(thread_id) == 0

        # 再次消费
        messages = handler.get(thread_id, timeout=1)
        assert messages == ["msg_1", "msg_2"]

        # 标记完成
        handler.mark_completed(thread_id)

        # 所有队列都应该为空
        assert handler.get_cached_count(thread_id) == 0
        assert handler._get_dlq_count(thread_id) == 0
        assert handler.is_empty(thread_id) is True

    def test_producer_stop_request_cancel_live(self, handler, thread_id):
        """测试 request_cancel：主动停止后 producer 进入 drain 模式，最终正常退出

        注意：cancel 后生产者和消费者都进入 drain 模式（等待 CANCEL_DRAIN_TIMEOUT 秒），
        在 drain 期间会继续消费消息，直到收到 EOD_CHUNK 或超时。因此消息数量取决于
        generator 的产出速度和 drain 超时时间，不一定少于总量。
        核心验证点：线程正常退出、队列最终清空。
        """

        async def slow_gen():
            for i in range(15):
                await asyncio.sleep(0.08)
                yield f"msg_{i}"

        collected = []

        def consume():
            nonlocal collected
            helper = GeneratorStreamingHelper(handler, thread_id)
            collected.extend(helper.stream(async_to_sync_generator(slow_gen())))

        t = threading.Thread(target=consume)
        t.start()
        time.sleep(0.5)
        handler.request_cancel(thread_id)
        t.join(timeout=10.0)
        assert not t.is_alive(), "Consumer thread should exit after cancel"
        # cancel 后由于 drain 机制，消息数量不超过总量即可
        assert len(collected) <= 15, f"message count should be <= 15, got {len(collected)}"
        assert handler.is_empty(thread_id)


class TestResourceCleanup:
    """测试 mark_completed 后的资源清理逻辑
    验证：
    1. mark_completed 后队列和交换机被真正删除（而非仅清空）
    2. _delete_all_resources 对不存在的资源不报错
    3. 信号队列（consumer/exit/cancelled/stopped）也会被清理
    4. clear() 不会删除队列（只清空消息，因为后续还要重建）
    """

    def _queue_exists(self, handler, queue_name: str) -> bool:
        """辅助方法：通过 passive declare 检查队列是否存在"""
        try:
            with handler._with_connection() as connection:
                channel = connection.channel()
                channel.queue_declare(queue=queue_name, durable=True, passive=True)
                return True
        except Exception:
            return False

    def _exchange_exists(self, handler, exchange_name: str) -> bool:
        """辅助方法：通过 passive declare 检查交换机是否存在"""
        try:
            with handler._with_connection() as connection:
                channel = connection.channel()
                channel.exchange_declare(exchange=exchange_name, passive=True)
                return True
        except Exception:
            return False

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_mark_completed_deletes_queues_and_exchange(self):
        """mark_completed 后主队列、死信队列、死信交换机被真正删除"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-delete-test"

        handler.clear(thread_id)

        # 发送消息以确保队列和交换机被创建
        handler.put(thread_id, "msg_1")
        handler.put(thread_id, "msg_2")
        handler.flush(thread_id)

        # 消费消息使其进入死信队列
        handler.get(thread_id, timeout=1)

        # 确认队列和交换机存在
        main_queue = handler._get_queue_name(thread_id)
        dlq_name = handler._get_dlq_name(thread_id)
        dlx_exchange = handler._get_dlx_exchange_name(thread_id)

        assert self._queue_exists(handler, main_queue), "主队列应该存在"
        assert self._queue_exists(handler, dlq_name), "死信队列应该存在"
        assert self._exchange_exists(handler, dlx_exchange), "死信交换机应该存在"

        # 执行 mark_completed
        handler.mark_completed(thread_id)

        # 验证队列和交换机已被删除
        assert not self._queue_exists(handler, main_queue), "主队列应该被删除"
        assert not self._queue_exists(handler, dlq_name), "死信队列应该被删除"
        assert not self._exchange_exists(handler, dlx_exchange), "死信交换机应该被删除"

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_mark_completed_deletes_signal_queues(self):
        """mark_completed 后信号队列（consumer/exit/cancelled/stopped）也被删除"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-signal-test"

        handler.clear(thread_id)

        # 创建消息队列
        handler.put(thread_id, "msg_1")
        handler.flush(thread_id)

        # 触发信号队列创建
        consumer_id = handler.acquire_consumer(thread_id)
        handler.mark_stopped(thread_id)
        handler.notify_consumer_cancelled(thread_id)

        # 获取信号队列名称
        consumer_queue = handler._get_consumer_queue_name(thread_id)
        exit_queue = handler._get_consumer_exit_queue_name(thread_id)
        cancelled_queue = handler._get_cancelled_queue_name(thread_id)
        stopped_queue = handler._get_stopped_queue_name(thread_id)

        # 确认信号队列存在
        assert self._queue_exists(handler, consumer_queue), "消费者控制队列应该存在"
        assert self._queue_exists(handler, exit_queue), "退出通知队列应该存在"
        assert self._queue_exists(handler, cancelled_queue), "取消完成通知队列应该存在"
        assert self._queue_exists(handler, stopped_queue), "停止状态队列应该存在"

        # 消费消息
        handler.get(thread_id, timeout=1)

        # 先释放消费者，再 mark_completed（避免 release_consumer 内部
        # _ensure_consumer_queues 重新创建已删除的 consumer/exit 队列）
        handler.release_consumer(thread_id, consumer_id)
        handler.mark_completed(thread_id)

        # 验证信号队列已被删除
        assert not self._queue_exists(handler, consumer_queue), "消费者控制队列应该被删除"
        assert not self._queue_exists(handler, exit_queue), "退出通知队列应该被删除"
        assert not self._queue_exists(handler, cancelled_queue), "取消完成通知队列应该被删除"
        assert not self._queue_exists(handler, stopped_queue), "停止状态队列应该被删除"

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_post_completion_cleanup_does_not_recreate_signal_queues(self):
        """正常完成流后，不应残留 consumer/cancelled 信号队列"""
        handler = RabbitMQMessageHandler()
        thread_id = f"thread-post-completion-cleanup-{int(time.time() * 1000) % 100000}"

        handler.clear(thread_id)

        async def gen():
            yield "msg_1"

        consumer_queue = handler._get_consumer_queue_name(thread_id)
        exit_queue = handler._get_consumer_exit_queue_name(thread_id)
        cancelled_queue = handler._get_cancelled_queue_name(thread_id)

        helper = GeneratorStreamingHelper(handler, thread_id)
        business_messages = [msg for msg in helper.stream(async_to_sync_generator(gen())) if not msg.startswith("<")]

        assert business_messages == ["msg_1"]

        assert not self._queue_exists(handler, consumer_queue), "完成后不应重建消费者控制队列"
        assert not self._queue_exists(handler, exit_queue), "完成后不应重建退出通知队列"
        assert not self._queue_exists(handler, cancelled_queue), "完成后不应重建取消完成通知队列"

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_delete_nonexistent_resources_no_error(self):
        """对不存在的队列/交换机执行删除不会报错"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-nonexist-test"

        # 确保资源不存在
        handler.clear(thread_id)
        handler.mark_completed(thread_id)

        # 再次执行删除，不应该报错
        handler._delete_all_resources(thread_id)

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_clear_does_not_delete_queues(self):
        """clear() 只清空消息，不删除队列（因为后续 put 会重新使用）"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-clear-test"

        # 创建队列并发送消息
        handler.put(thread_id, "msg_1")
        handler.flush(thread_id)

        main_queue = handler._get_queue_name(thread_id)
        dlq_name = handler._get_dlq_name(thread_id)

        # 确认队列存在
        assert self._queue_exists(handler, main_queue), "主队列应该存在"
        assert self._queue_exists(handler, dlq_name), "死信队列应该存在"

        # 执行 clear
        handler.clear(thread_id)

        # 验证队列仍然存在（只是消息被清空了）
        assert self._queue_exists(handler, main_queue), "clear 后主队列应该仍然存在"
        assert self._queue_exists(handler, dlq_name), "clear 后死信队列应该仍然存在"
        assert handler.get_cached_count(thread_id) == 0, "主队列消息应该被清空"

        # 最终清理
        handler.mark_completed(thread_id)

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_mark_completed_deletes_cancel_queue(self):
        """mark_completed 后取消请求队列也被删除"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-cancel-queue-test"

        handler.clear(thread_id)

        # 发送消息并触发取消请求队列创建
        handler.put(thread_id, "msg_1")
        handler.flush(thread_id)
        handler.request_cancel(thread_id)

        cancel_queue = handler._get_cancel_queue_name(thread_id)
        assert self._queue_exists(handler, cancel_queue), "取消请求队列应该存在"

        # 消费并完成
        handler.get(thread_id, timeout=1)
        handler.mark_completed(thread_id)

        # 验证取消请求队列已被删除
        assert not self._queue_exists(handler, cancel_queue), "取消请求队列应该被删除"

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_mark_completed_clears_buffer_before_delete(self):
        """mark_completed 先清理本地缓冲区，防止守护线程 flush 残留消息到已删除的队列"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-buffer-test"

        handler.clear(thread_id)

        # 向缓冲区写入消息但不 flush，模拟守护线程尚未来得及推送
        handler.put(thread_id, "buffered_msg_1")
        handler.put(thread_id, "buffered_msg_2")

        # 确认消息在本地缓冲区中
        with handler._buffer_lock:
            assert thread_id in handler._message_buffer
            assert len(handler._message_buffer[thread_id]) == 2

        # 执行 mark_completed
        handler.mark_completed(thread_id)

        # 验证本地缓冲区已被清理
        with handler._buffer_lock:
            assert thread_id not in handler._message_buffer, "mark_completed 应该清理本地缓冲区"

        # 验证 RabbitMQ 中也没有残留消息（守护线程不应该 flush 已清理的消息）
        assert handler.get_cached_count(thread_id) == 0, "主队列不应该有残留消息"
        assert handler._get_dlq_count(thread_id) == 0, "死信队列不应该有残留消息"

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_has_pending_messages_independent_channel(self):
        """主队列不存在时，has_pending_messages 仍能正确检查死信队列（独立 channel 隔离性）"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-pending-check-test"

        handler.clear(thread_id)

        # 发送消息并消费，让消息进入死信队列
        handler.put(thread_id, "msg_1")
        handler.flush(thread_id)
        handler.get(thread_id, timeout=1)

        # 确认消息在死信队列中
        assert handler._get_dlq_count(thread_id) == 1, "死信队列应该有 1 条消息"

        # 手动删除主队列，模拟主队列不存在的场景
        with handler._with_connection() as connection:
            channel = connection.channel()
            channel.queue_delete(queue=handler._get_queue_name(thread_id))

        # 确认主队列已被删除
        assert not self._queue_exists(handler, handler._get_queue_name(thread_id)), "主队列应该已被删除"

        # 核心验证：即使主队列不存在（passive declare 触发 404），
        # has_pending_messages 仍能正确检查死信队列并返回 True
        assert handler.has_pending_messages(thread_id) is True, (
            "主队列不存在时，has_pending_messages 应该仍能检查到死信队列中的消息"
        )

        # 清理
        handler.mark_completed(thread_id)
