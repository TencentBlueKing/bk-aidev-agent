import asyncio
import contextlib
import os
import threading
import time

import pytest
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

    def test_repeated_operations_do_not_accumulate_open_channels(self, handler, thread_id):
        """Repeated RabbitMQ operations should close their temporary AMQP channels."""
        handler.put(thread_id, "seed")
        handler.flush(thread_id)

        for _ in range(20):
            assert handler.get_cached_count(thread_id) == 1

        assert self._get_open_channel_count(handler) <= 1

    def test_set_cancel_signal_falls_back_when_signal_queue_is_missing(self, handler, thread_id):
        """首次 stop 应在 passive declare 返回 404 后创建 cancel queue。"""
        run_id = "run-before-first-sse"

        assert handler.set_cancel_signal(thread_id, run_id=run_id) is True
        assert handler.check_cancel_signal(thread_id, run_id=run_id) is True

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

        # offset replay 不移动主队列消息
        messages, offset = handler.get_messages_since(thread_id, offset=0, timeout=1)
        assert messages == ["test_msg_1", "test_msg_2", "test_msg_3"]
        assert offset == 3

        # 主队列保留完整 replay 日志
        assert handler.get_cached_count(thread_id) == 3
        assert handler.has_pending_messages(thread_id) is True

        # 新消费者从 offset=0 独立 replay 同一批消息
        messages, replay_offset = handler.get_messages_since(thread_id, offset=0, timeout=1)
        assert messages == ["test_msg_1", "test_msg_2", "test_msg_3"]
        assert replay_offset == 3

        # 标记完成并清理
        handler.mark_completed(thread_id)

        # 验证所有队列已清空
        assert handler.is_empty(thread_id) is True
        assert handler.get_cached_count(thread_id) == 0

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

    def test_replay_waits_until_a_long_buffer_is_committed(self, handler, thread_id, monkeypatch):
        """Replay offset 只推进到 RabbitMQ 已提交日志，不包含本地未发布 buffer。"""
        committed_messages = [f"committed-{index}" for index in range(1_000)]
        buffered_messages = [f"buffered-{index}" for index in range(1_000)]

        handler._stop_daemon()
        monkeypatch.setattr(handler, "_ensure_daemon_alive", lambda: None)

        for message in committed_messages:
            handler.put(thread_id, message)
        handler.flush(thread_id)

        messages, offset = handler.get_messages_since(thread_id, offset=0, timeout=5)
        assert messages == committed_messages
        assert offset == 1_000

        for message in buffered_messages:
            handler.put(thread_id, message)

        with pytest.raises(TimeoutError):
            handler.get_messages_since(thread_id, offset=offset, timeout=0.1)

        handler.flush(thread_id)
        messages, next_offset = handler.get_messages_since(thread_id, offset=offset, timeout=5)

        assert messages == buffered_messages
        assert next_offset == 2_000

    def test_consumer_reconnect_replays_main_queue(self, handler, thread_id):
        """消费者断开后，新消费者从主队列开头独立 replay。"""
        # 模拟生产者产生消息
        for i in range(5):
            handler.put(thread_id, f"msg_{i}")
        handler.put(thread_id, EOD_CHUNK)
        handler.flush(thread_id)

        messages1, offset1 = handler.get_messages_since(thread_id, offset=0, timeout=1)
        assert len(messages1) == 6  # 包括 EOD_CHUNK
        assert offset1 == 6

        # 消费不会删除主队列数据
        assert handler.get_cached_count(thread_id) == 6

        # 新消费者使用独立 offset，从头 replay 全部消息
        messages2, offset2 = handler.get_messages_since(thread_id, offset=0, timeout=1)
        expected = [f"msg_{i}" for i in range(5)] + [EOD_CHUNK]
        assert messages2 == expected
        assert offset2 == 6

        # 清理
        handler.mark_completed(thread_id)
        assert handler.is_empty(thread_id) is True

    def test_replay_does_not_remove_main_queue_messages(self, handler, thread_id):
        """多次 replay 都读取同一份主队列日志。"""
        # 发送消息
        handler.put(thread_id, "msg_1")
        handler.put(thread_id, "msg_2")
        handler.flush(thread_id)

        assert handler.get_cached_count(thread_id) == 2

        messages, offset = handler.get_messages_since(thread_id, offset=0, timeout=1)
        assert messages == ["msg_1", "msg_2"]
        assert offset == 2

        # replay 后主队列仍保留消息，第二个消费者可再次读取
        assert handler.get_cached_count(thread_id) == 2
        replayed, replay_offset = handler.get_messages_since(thread_id, offset=0, timeout=1)
        assert replayed == ["msg_1", "msg_2"]
        assert replay_offset == 2

        # 标记完成
        handler.mark_completed(thread_id)

        # 所有队列都应该为空
        assert handler.get_cached_count(thread_id) == 0
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

    def test_new_run_after_cancel_starts_new_producer(self, handler, thread_id):
        """RabbitMQ 完成取消清理后，同 session 的新 run 不应重放取消结果。"""
        cancelled_helper = GeneratorStreamingHelper(handler, thread_id)
        cancelled_event = cancelled_helper.prepare_run("run-cancelled")
        assert handler.set_cancel_signal(thread_id)
        cancelled = list(
            cancelled_helper.stream(
                iter(["must-not-be-emitted"]),
                expected_run_id="run-cancelled",
                cancel_event=cancelled_event,
            )
        )
        assert "must-not-be-emitted" not in cancelled
        assert handler.is_empty(thread_id)

        next_helper = GeneratorStreamingHelper(handler, thread_id)
        next_event = next_helper.prepare_run("run-next")
        next_chunks = list(
            next_helper.stream(
                iter(["next-run-output"]),
                expected_run_id="run-next",
                cancel_event=next_event,
            )
        )
        assert "next-run-output" in next_chunks


class TestResourceCleanup:
    """测试 mark_completed 后的资源清理逻辑
    验证：
    1. mark_completed 后队列被真正删除（而非仅清空）
    2. _delete_all_resources 对不存在的资源不报错
    3. 活跃消费者与信号队列（active/cancelled/stopped）也会被清理
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

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_mark_completed_deletes_main_queue(self):
        """mark_completed 后主队列被真正删除。"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-delete-test"

        handler.clear(thread_id)

        # 发送消息以确保主队列被创建
        handler.put(thread_id, "msg_1")
        handler.put(thread_id, "msg_2")
        handler.flush(thread_id)

        main_queue = handler._get_queue_name(thread_id)
        assert self._queue_exists(handler, main_queue), "主队列应该存在"

        handler.mark_completed(thread_id)

        assert not self._queue_exists(handler, main_queue), "主队列应该被删除"

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_mark_completed_deletes_signal_queues(self):
        """mark_completed 后活跃消费者与信号队列也被删除。"""
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
        consumer_queue = handler._get_active_consumer_queue_name(thread_id)
        cancelled_queue = handler._get_cancelled_queue_name(thread_id)
        stopped_queue = handler._get_stopped_queue_name(thread_id)

        # 确认信号队列存在
        assert self._queue_exists(handler, consumer_queue), "消费者控制队列应该存在"
        assert self._queue_exists(handler, cancelled_queue), "取消完成通知队列应该存在"
        assert self._queue_exists(handler, stopped_queue), "停止状态队列应该存在"

        # 先释放消费者，再 mark_completed。
        handler.release_consumer(thread_id, consumer_id)
        handler.mark_completed(thread_id)

        # 验证信号队列已被删除
        assert not self._queue_exists(handler, consumer_queue), "消费者控制队列应该被删除"
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

        consumer_queue = handler._get_active_consumer_queue_name(thread_id)
        cancelled_queue = handler._get_cancelled_queue_name(thread_id)

        helper = GeneratorStreamingHelper(handler, thread_id)
        business_messages = [msg for msg in helper.stream(async_to_sync_generator(gen())) if not msg.startswith("<")]

        assert business_messages == ["msg_1"]

        assert not self._queue_exists(handler, consumer_queue), "完成后不应重建消费者控制队列"
        assert not self._queue_exists(handler, cancelled_queue), "完成后不应重建取消完成通知队列"

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_delete_nonexistent_resources_no_error(self):
        """对不存在的队列执行删除不会报错"""
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

        # 确认队列存在
        assert self._queue_exists(handler, main_queue), "主队列应该存在"

        # 执行 clear
        handler.clear(thread_id)

        # 验证队列仍然存在（只是消息被清空了）
        assert self._queue_exists(handler, main_queue), "clear 后主队列应该仍然存在"
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

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_has_pending_messages_independent_channel(self):
        """主队列不存在时，has_pending_messages 返回 False。"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-cleanup-pending-check-test"

        handler.clear(thread_id)

        # 发送消息后手动删除主队列
        handler.put(thread_id, "msg_1")
        handler.flush(thread_id)

        # 手动删除主队列，模拟主队列不存在的场景
        with handler._with_connection() as connection:
            channel = connection.channel()
            channel.queue_delete(queue=handler._get_queue_name(thread_id))

        # 确认主队列已被删除
        assert not self._queue_exists(handler, handler._get_queue_name(thread_id)), "主队列应该已被删除"

        assert handler.has_pending_messages(thread_id) is False

        # 清理
        handler.mark_completed(thread_id)
