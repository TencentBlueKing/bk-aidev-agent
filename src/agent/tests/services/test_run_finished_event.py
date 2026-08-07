# -*- coding: utf-8 -*-
"""
测试 MQ 多进程场景下 Draining 时正确发送 RUN_FINISHED 事件

核心验证：
1. 跨进程取消信号检测（Producer/Consumer）
2. Consumer drain 超时时发送 RUN_FINISHED 事件
3. 收到 CANCELLED_CHUNK 时发送 RUN_FINISHED 事件
4. 停止会话时发送 RUN_FINISHED 事件
"""

import json
import threading
import time

import pytest
from aidev_agent.services.messages_handler import (
    CANCELLED_CHUNK,
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
)
from aidev_agent.services.messages_handler.constants import TimeoutConfig
from aidev_agent.utils.event import RunId


def parse_sse_event(sse_str: str) -> dict:
    """解析 SSE 格式的事件

    Args:
        sse_str: SSE 格式字符串，如 "data: {...}\\n\\n"

    Returns:
        解析后的 JSON 字典
    """
    assert sse_str.startswith("data: "), f"Expected SSE format, got: {sse_str}"
    json_str = sse_str.replace("data: ", "", 1).strip()
    return json.loads(json_str)


def extract_run_finished_events(events: list[str]) -> list[dict]:
    """从事件列表中提取所有 RUN_FINISHED 事件

    Args:
        events: SSE 事件列表

    Returns:
        RUN_FINISHED 事件列表
    """
    run_finished_events = []
    for event in events:
        if event.startswith("data: "):
            try:
                data = parse_sse_event(event)
                if data.get("type") == "RUN_FINISHED":
                    run_finished_events.append(data)
            except (json.JSONDecodeError, KeyError):
                pass
    return run_finished_events


def verify_run_finished_event(event: dict, thread_id: str, expected_run_id: str) -> None:
    """验证 RUN_FINISHED 事件格式

    Args:
        event: RUN_FINISHED 事件字典
        thread_id: 预期的线程 ID
        expected_run_id: 预期的 run_id（RunId.CANCELLED 或 RunId.STOPPED）
    """
    assert event["type"] == "RUN_FINISHED"
    assert event["threadId"] == thread_id
    assert event["runId"] == expected_run_id, f"Expected runId={expected_run_id}, got {event['runId']}"


class MockMQHandler(InMemoryQueueMessageHandler):
    """模拟 MQ Handler（支持跨进程取消信号）

    继承 InMemoryQueueMessageHandler，添加跨进程取消信号的模拟：
    - _cancel_signals: 存储取消信号（模拟 RabbitMQ 队列）
    - set_cancel_signal(): 设置跨进程取消信号
    - check_cancel_signal(): 检查跨进程取消信号（peek 模式，不消费）
    - clear_cancel_signal(): 清除跨进程取消信号

    注意：重写 __new__ 禁用单例模式，每个测试用例独立实例
    """

    def __new__(cls):
        instance = object.__new__(cls)
        instance._init_queues()
        # 初始化跨进程取消信号队列
        instance._cancel_signals: dict[str, bool] = {}
        instance._cancel_signal_lock = threading.Lock()
        instance._initialized = True
        return instance

    def __init__(self):
        # 不调用 super().__init__()，因为 __new__ 已经初始化
        pass

    def set_cancel_signal(self, thread_id: str) -> bool:
        """设置跨进程取消信号（模拟 RabbitMQ 队列）

        可以从任意进程调用，生产者/消费者会通过 check_cancel_signal() 检测到取消。
        """
        with self._cancel_signal_lock:
            self._cancel_signals[thread_id] = True
            print(f"[MockMQ] Set cancel signal for thread_id={thread_id}")
        return True

    def check_cancel_signal(self, thread_id: str) -> bool:
        """检查跨进程取消信号（peek 模式，不消费）

        用于生产者/消费者定期检查是否需要停止。
        """
        with self._cancel_signal_lock:
            result = self._cancel_signals.get(thread_id, False)
            print(f"[MockMQ] Check cancel signal for thread_id={thread_id}: {result}")
            return result

    def clear_cancel_signal(self, thread_id: str) -> None:
        """清除跨进程取消信号（在流结束后调用）"""
        with self._cancel_signal_lock:
            self._cancel_signals.pop(thread_id, None)
            print(f"[MockMQ] Clear cancel signal for thread_id={thread_id}")


@pytest.fixture
def mq_handler():
    """提供支持跨进程取消信号的 Mock MQ Handler"""
    handler = MockMQHandler()
    yield handler

    # 清理
    for thread_id in handler.list_thread_ids():
        handler.clear(thread_id)
    if hasattr(handler, "_stopped_sessions"):
        handler._stopped_sessions.clear()
    if hasattr(handler, "_consumer_cancelled_events"):
        handler._consumer_cancelled_events.clear()
    if hasattr(handler, "_cancel_signals"):
        handler._cancel_signals.clear()


class TestCrossProcessCancelSignal:
    """验证 MQ 跨进程取消信号场景"""

    def test_cross_process_cancel_signal_persistence(self, mq_handler):
        """跨进程取消信号持久性验证（peek 模式）

        验证：
        - check_cancel_signal() 是 peek 模式，不消费消息
        - 多次调用都能检测到取消信号
        - clear_cancel_signal() 后信号消失
        """
        tid = "test_cancel_signal_persistence"

        # 设置取消信号
        mq_handler.set_cancel_signal(tid)

        # 多次检查都能检测到（peek 模式，不消费）
        assert mq_handler.check_cancel_signal(tid) is True
        assert mq_handler.check_cancel_signal(tid) is True
        assert mq_handler.check_cancel_signal(tid) is True

        # 清除取消信号
        mq_handler.clear_cancel_signal(tid)

        # 清除后检测不到
        assert mq_handler.check_cancel_signal(tid) is False

    def test_cross_process_cancel_signal_detected_by_producer(self, mq_handler, monkeypatch):
        """Producer 检测到跨进程取消信号后进入 drain 模式

        场景：
        1. Producer 运行在进程 A
        2. 用户在进程 B 调用 set_cancel_signal()（模拟 stop 接口）
        3. Producer 检测到跨进程取消信号
        4. Producer 设置进程内 cancel_event（同步）
        5. Producer 进入 drain 模式

        验证：
        - Producer 检测到跨进程取消信号
        - 进程内 cancel_event 被同步设置
        - Producer 进入 drain 模式（继续处理 generator）
        """
        tid = "test_cross_process_cancel_producer"
        collected = []
        stream_started = threading.Event()
        cancel_detected = threading.Event()

        # 缩短 drain 超时时间
        monkeypatch.setattr(TimeoutConfig, "CANCEL_DRAIN_TIMEOUT", 1.0)

        def slow_gen():
            """慢速 generator，每 0.2 秒产生一个 chunk"""
            stream_started.set()
            for i in range(20):
                # 模拟 Agent 检查取消信号（会同时检查进程内和跨进程信号）
                if GeneratorStreamingHelper.is_cancelled(tid, mq_handler):
                    cancel_detected.set()
                    yield CANCELLED_CHUNK
                    return
                time.sleep(0.2)
                yield f"chunk_{i}"

        def consume():
            helper = GeneratorStreamingHelper(mq_handler, thread_id=tid)
            collected.extend(helper.stream(slow_gen()))

        # 消费者线程
        t = threading.Thread(target=consume)
        t.start()
        stream_started.wait(timeout=2.0)

        # 等待 Producer 产生几个 chunk
        time.sleep(0.3)

        # 模拟跨进程取消：直接设置跨进程取消信号（不设置进程内事件）
        mq_handler.set_cancel_signal(tid)

        # 等待 Producer 检测到取消
        cancel_detected.wait(timeout=3.0)

        # 等待 Consumer 退出
        t.join(timeout=5.0)

        # 验证结果
        assert not t.is_alive(), "Consumer 应已退出"

        # 验证跨进程取消信号被检测到
        assert cancel_detected.is_set(), "Producer 应检测到跨进程取消信号"

        # 验证 RUN_FINISHED 事件
        run_finished_events = []
        for event in collected:
            if event.startswith("data: "):
                try:
                    data = parse_sse_event(event)
                    if data.get("type") == "RUN_FINISHED":
                        run_finished_events.append(data)
                except (json.JSONDecodeError, KeyError):
                    pass

        assert len(run_finished_events) > 0, f"应包含 RUN_FINISHED 事件，实际收到: {collected}"
        assert run_finished_events[-1]["runId"] == RunId.CANCELLED

    def test_cross_process_cancel_signal_detected_by_consumer(self, mq_handler, monkeypatch):
        """Consumer 检测到跨进程取消信号后进入 drain 模式

        场景：
        1. Consumer 运行在进程 A
        2. 用户在进程 B 调用 set_cancel_signal()
        3. Consumer 检测到跨进程取消信号
        4. Consumer 同步设置进程内 cancel_event
        5. Consumer 进入 drain 模式

        验证：
        - Consumer 检测到跨进程取消信号
        - 进程内 cancel_event 被同步设置
        - Consumer 进入 drain 模式
        """
        tid = "test_cross_process_cancel_consumer"
        collected = []
        stream_started = threading.Event()

        # 缩短 drain 超时时间
        monkeypatch.setattr(TimeoutConfig, "CANCEL_DRAIN_TIMEOUT", 1.0)

        def stubborn_gen():
            """不检查 cancel 的 generator，模拟长时间阻塞"""
            stream_started.set()
            time.sleep(5.0)  # 长时间阻塞，触发 drain 超时
            yield "chunk_0"

        def consume():
            helper = GeneratorStreamingHelper(mq_handler, thread_id=tid)
            collected.extend(helper.stream(stubborn_gen()))

        t = threading.Thread(target=consume)
        t.start()
        stream_started.wait(timeout=2.0)
        time.sleep(0.1)

        # 模拟跨进程取消：只设置跨进程信号（不设置进程内事件）
        mq_handler.set_cancel_signal(tid)

        # 等待 Consumer 退出
        t.join(timeout=5.0)

        # 验证结果
        assert not t.is_alive(), "Consumer 应已退出"
        assert len(collected) >= 1, f"应至少收到 1 个事件，实际收到 {len(collected)}"

        # 验证 RUN_FINISHED 事件（消费者 drain 超时后直接 yield RUN_FINISHED SSE，无 STOPPED_CHUNK）
        run_finished_events = extract_run_finished_events(collected)
        assert len(run_finished_events) > 0, f"应包含 RUN_FINISHED 事件，实际收到: {collected}"
        assert run_finished_events[-1]["runId"] == RunId.CANCELLED

    def test_cross_process_cancel_with_cancelled_chunk(self, mq_handler):
        """跨进程取消信号 + Agent yield CANCELLED_CHUNK 的完整流程

        场景：
        1. Producer/Consumer 运行在进程 A
        2. 用户在进程 B 调用 set_cancel_signal()
        3. Producer 检测到跨进程取消信号，进入 drain 模式
        4. Agent 检测到取消，yield CANCELLED_CHUNK
        5. Consumer 收到 CANCELLED_CHUNK，发送 RUN_FINISHED

        验证：
        - 完整的跨进程取消流程
        - RUN_FINISHED 事件正确发送
        """
        tid = "test_cross_process_cancel_full_flow"
        collected = []
        stream_started = threading.Event()

        def cancel_aware_gen():
            """检查取消的 generator"""
            stream_started.set()
            for i in range(10):
                # Agent 检查取消信号（会同时检查进程内和跨进程信号）
                if GeneratorStreamingHelper.is_cancelled(tid, mq_handler):
                    yield CANCELLED_CHUNK
                    return
                time.sleep(0.1)
                yield f"chunk_{i}"

        def consume():
            helper = GeneratorStreamingHelper(mq_handler, thread_id=tid)
            collected.extend(helper.stream(cancel_aware_gen()))

        t = threading.Thread(target=consume)
        t.start()
        stream_started.wait(timeout=2.0)
        time.sleep(0.1)

        # 模拟跨进程取消
        mq_handler.set_cancel_signal(tid)

        # 等待 Consumer 退出
        t.join(timeout=5.0)

        # 验证结果
        assert not t.is_alive(), "Consumer 应已退出"

        # 验证 RUN_FINISHED 事件
        run_finished_events = []
        for event in collected:
            if event.startswith("data: "):
                try:
                    data = parse_sse_event(event)
                    if data.get("type") == "RUN_FINISHED":
                        run_finished_events.append(data)
                except (json.JSONDecodeError, KeyError):
                    pass

        assert len(run_finished_events) > 0, f"应包含 RUN_FINISHED 事件，实际收到: {collected}"
        assert run_finished_events[-1]["runId"] == RunId.CANCELLED

    def test_cross_process_cancel_before_stream_start_is_preserved(self, mq_handler):
        """流注册前到达的跨进程取消信号不能被启动清理吞掉

        场景：
        1. 用户先点击停止，取消信号已进入队列
        2. producer/consumer 随后才完成注册

        验证：
        - 本轮 generator 不再继续执行
        - 输出 RUN_FINISHED(cancelled)
        """
        tid = "test_cancel_clear_on_start"

        # 模拟 stop 早于流注册
        mq_handler.set_cancel_signal(tid)
        assert mq_handler.check_cancel_signal(tid) is True

        # 启动新流
        collected = []
        stream_completed = threading.Event()

        def simple_gen():
            for i in range(5):
                time.sleep(0.05)
                yield f"chunk_{i}"
            stream_completed.set()

        def consume():
            helper = GeneratorStreamingHelper(mq_handler, thread_id=tid)
            collected.extend(helper.stream(simple_gen()))

        t = threading.Thread(target=consume)
        t.start()
        t.join(timeout=5.0)

        assert not stream_completed.is_set(), "注册前的 stop 应中断本轮 generator"
        run_finished_events = [
            parse_sse_event(event) for event in collected if isinstance(event, str) and "RUN_FINISHED" in event
        ]
        assert run_finished_events
        assert run_finished_events[-1]["runId"] == RunId.CANCELLED

    def test_stopped_session_sends_run_finished_event(self, mq_handler):
        """停止会话时应发送 RUN_FINISHED 事件

        场景：
        1. 会话被标记为已停止
        2. Consumer 消费停止的会话
        3. 发送 RUN_FINISHED 事件（不发送 STOPPED_CHUNK）

        验证：
        - RUN_FINISHED 事件格式正确
        - run_id 为 "stopped"
        """
        tid = "test_stopped_session_finished"

        # 标记会话为已停止
        mq_handler.mark_stopped(tid)

        # 添加一些消息到队列
        mq_handler.put(tid, "final_message")

        # 创建 helper 并消费（传入空 generator，但会话已被停止）
        helper = GeneratorStreamingHelper(mq_handler, thread_id=tid)
        result = list(helper.stream(iter([])))  # 空 generator

        # 验证结果
        assert len(result) >= 1, f"应至少收到 1 个事件（RUN_FINISHED），实际收到 {len(result)}"

        # 查找 RUN_FINISHED 事件
        run_finished_events = []
        for event in result:
            if event.startswith("data: "):
                try:
                    data = parse_sse_event(event)
                    if data.get("type") == "RUN_FINISHED":
                        run_finished_events.append(data)
                except (json.JSONDecodeError, KeyError):
                    pass

        # 验证至少有一个 RUN_FINISHED 事件
        assert len(run_finished_events) > 0, f"应包含 RUN_FINISHED 事件，实际收到: {result}"

        # 验证 RUN_FINISHED 事件格式
        last_run_finished = run_finished_events[-1]
        assert last_run_finished["type"] == "RUN_FINISHED"
        assert last_run_finished["threadId"] == tid
        assert last_run_finished["runId"] == RunId.STOPPED, (
            f"Expected runId={RunId.STOPPED}, got {last_run_finished['runId']}"
        )
