import asyncio
import os
import threading
import time

import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.services.chat import ChatCompletionAgent
from aidev_agent.services.messages_handler import EOD_CHUNK, GeneratorStreamingHelper
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler
from aidev_agent.services.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.utils.async_utils import async_to_sync_generator


class TestRabbitMQMessageHandler:
    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_live_test(self):
        """实际连接 RabbitMQ 进行测试"""
        handler = RabbitMQMessageHandler()
        thread_id = "thread-live-test"

        # 清理可能存在的旧数据
        handler.clear(thread_id)

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

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_live_chat(self):
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
        handler = RabbitMQMessageHandler()
        thread_id = "thread-live-generator-streaming"
        helper = GeneratorStreamingHelper(handler, thread_id)

        # 清理可能存在的旧数据
        handler.clear(thread_id)

        # 启动流并消费所有消息，确保生产者线程完成
        with open("text.log", "w") as fo:
            for each in helper.stream(async_to_sync_generator(stream_gen)):
                fo.write(each)

        # 验证队列已清空（流已完成）
        assert handler.is_empty(thread_id) is True

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_live_generator_streaming_with_queue(self):
        """测试流式消息的生产和消费

        验证：
        1. 流式消息可以正确生产和消费
        2. 消费完成后队列已清空
        """

        async def gen():
            for i in range(10):
                await asyncio.sleep(0.05)  # 缩短等待时间
                yield f"test_msg_{i}"

        handler = RabbitMQMessageHandler()
        thread_id = "thread-live-generator-streaming-queue"
        helper = GeneratorStreamingHelper(handler, thread_id)

        # 清理可能存在的旧数据
        handler.clear(thread_id)

        # 验证初始状态：没有未消费的消息
        assert handler.has_pending_messages(thread_id) is False

        # 启动流并消费所有消息
        all_messages = [each for each in helper.stream(async_to_sync_generator(gen()))]

        # 验证消费到了所有消息
        assert all_messages == [f"test_msg_{i}" for i in range(10)]

        # 验证流完成后队列已清空
        assert handler.is_empty(thread_id) is True

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_consumer_reconnect_with_dlq(self):
        """测试消费者断开后重连可以从死信队列恢复消息

        验证：
        1. 生产者产生消息后，消费者读取消息
        2. 消息被移动到死信队列
        3. 消费者断开后，消息仍在死信队列中
        4. 新的消费者调用 restore_messages 恢复消息
        5. 从主队列重新消费所有消息
        """
        handler = RabbitMQMessageHandler()
        thread_id = "thread-reconnect-dlq-test"

        # 清理可能存在的旧数据
        handler.clear(thread_id)

        # 模拟生产者产生消息
        for i in range(5):
            handler.put(thread_id, f"msg_{i}")
        handler.put(thread_id, EOD_CHUNK)  # 添加结束标记
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

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_dlq_mechanism(self):
        """测试死信队列机制

        验证：
        1. 消息被消费后进入死信队列
        2. restore_messages 能正确恢复消息
        3. mark_completed 能清空所有队列
        """
        handler = RabbitMQMessageHandler()
        thread_id = "thread-dlq-mechanism-test"

        # 清理
        handler.clear(thread_id)

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

    @pytest.mark.skipif(not os.getenv("RABBITMQ_HOST"), reason="Live test requires RABBITMQ_HOST")
    def test_producer_stop_request_cancel_live(self):
        """测试 request_cancel：主动停止后 producer 退出并发送 CANCELLED，队列清理"""

        async def slow_gen():
            for i in range(15):
                await asyncio.sleep(0.08)
                yield f"msg_{i}"

        handler = RabbitMQMessageHandler()
        thread_id = "thread-live-cancel-test"
        handler.clear(thread_id)

        collected = []

        def consume():
            nonlocal collected
            helper = GeneratorStreamingHelper(handler, thread_id)
            collected.extend(helper.stream(async_to_sync_generator(slow_gen())))

        t = threading.Thread(target=consume)
        t.start()
        time.sleep(0.5)
        handler.request_cancel(thread_id)
        t.join(timeout=5.0)
        assert not t.is_alive(), "Consumer thread should exit after cancel"
        assert len(collected) < 6, "message count should be less than 6"
        assert handler.is_empty(thread_id)
