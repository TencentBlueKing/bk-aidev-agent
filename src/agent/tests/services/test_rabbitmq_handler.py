import asyncio
import contextlib
import os
import threading
import time

import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.services.agent import ChatCompletionAgent
from aidev_agent.services.messages_handler import EOD_CHUNK, GeneratorStreamingHelper
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler
from aidev_agent.services.pydantic_models import ChatPrompt, ExecuteKwargs
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
        2. 消费完成后队列已清空
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

        # 验证流完成后队列已清空
        assert handler.is_empty(thread_id) is True

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
