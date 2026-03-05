"""测试 InMemoryQueueMessageHandler 的基本功能"""

import pytest
from aidev_agent.services.messages_handler import (
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
    message_handler_factory,
)


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

    def test_factory(self):
        """测试工厂方法"""
        memory_handler = message_handler_factory.get()
        assert isinstance(memory_handler, InMemoryQueueMessageHandler)
        memory_handler2 = message_handler_factory.get()
        assert memory_handler is memory_handler2
