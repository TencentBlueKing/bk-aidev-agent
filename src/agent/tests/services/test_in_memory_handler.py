"""测试 InMemoryQueueMessageHandler 的基本功能"""

import contextlib
import threading
import time

import aidev_agent.services.messages_handler.streaming_helper as streaming_helper_module
import pytest
from aidev_agent.enums import MessageHandlerType
from aidev_agent.services.messages_handler import (
    CANCELLED_CHUNK,
    STOPPED_CHUNK,
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
    message_handler_factory,
)
from aidev_agent.services.messages_handler.config import MessageHandlerConfig
from aidev_agent.services.messages_handler.constants import EnvVarNames
from aidev_agent.services.messages_handler.factory import _create_handler


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
        """已停止且有缓存内容时，只回放内容并返回 STOPPED_CHUNK。"""
        thread_id = "test_stream_stopped_pending"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        clear_stopped_called = []

        handler.put(thread_id, "chunk_0")
        handler.put(thread_id, "chunk_1")
        monkeypatch.setattr(handler, "is_stopped", lambda _tid: True)
        monkeypatch.setattr(handler, "clear_stopped", lambda _tid: clear_stopped_called.append(True))

        result = list(helper.stream(iter(())))

        assert result == ["chunk_0", "chunk_1", STOPPED_CHUNK]
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
        ("gen_items", "expected"),
        [
            ([CANCELLED_CHUNK], [STOPPED_CHUNK]),
            (["chunk_0"], ["chunk_0"]),
        ],
    )
    def test_stream_handles_control_and_data_messages(self, handler, gen_items, expected):
        """验证 CANCELLED_CHUNK 与普通数据在消费侧的处理行为。"""
        thread_id = f"test_stream_control_{len(gen_items)}_{expected[0]}"
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)

        result = list(helper.stream(iter(gen_items)))

        assert result == expected

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
