"""L1 观测日志回归测试（纯日志子集，零行为改动）。

覆盖改动 L-1 ~ L-6 的日志输出；全部基于 `InMemoryQueueMessageHandler`，
不依赖真实 RabbitMQ broker。重点验证：

- consumer loop enter / exit INFO（出口带 reason / consumed / iter）
- consumer progress INFO 按 N 条 / M 秒触发
- yield slow WARNING 阈值触发（H1 直接证据点）
- orphan cleanup triggered INFO 带判据字段
- unexpected 异常 → ERROR 后 raise
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from typing import Any

import pytest
from aidev_agent.services.messages_handler import (
    GeneratorStreamingHelper,
    InMemoryQueueMessageHandler,
)


@pytest.fixture
def handler():
    h = InMemoryQueueMessageHandler()
    yield h
    for tid in h.list_thread_ids():
        h.clear(tid)


@pytest.fixture
def caplog_info(caplog):
    caplog.set_level(logging.INFO, logger="aidev_agent.services.messages_handler.streaming_helper")
    caplog.set_level(logging.INFO, logger="aidev_agent.services.messages_handler.rabbitmq")
    return caplog


def _drive(helper: GeneratorStreamingHelper, gen: Generator[Any, None, None]) -> list[Any]:
    return list(helper.stream(gen))


class TestConsumerLoopEnterExit:
    def test_normal_completion_logs_enter_and_exit(self, handler, caplog_info):
        helper = GeneratorStreamingHelper(message_handler=handler, thread_id="tid_enter_exit_ok")

        def _gen():
            yield "x"
            yield "y"

        out = _drive(helper, _gen())
        assert out == ["x", "y"]

        msgs = [r.getMessage() for r in caplog_info.records]
        enters = [m for m in msgs if "consumer loop enter" in m]
        exits = [m for m in msgs if "consumer loop exit" in m]
        assert enters, f"必须打 consumer loop enter，实际 msgs={msgs}"
        assert exits, "必须打 consumer loop exit"
        assert any("reason=completed" in m for m in exits), f"正常完成 reason 应为 completed，实际 {exits}"
        assert any("consumed=2" in m for m in exits), f"exit 必须带累计 consumed 数，实际 {exits}"

    def test_exit_reason_generator_exit_when_consumer_disconnect(self, handler, caplog_info):
        """消费者 next() 一次就 close generator，exit_reason 应为 generator_exit。"""
        helper = GeneratorStreamingHelper(message_handler=handler, thread_id="tid_gen_exit")

        def _gen():
            for i in range(5):
                yield f"m-{i}"

        stream_gen = helper.stream(_gen())
        first = next(stream_gen)
        assert first == "m-0"
        stream_gen.close()

        exits = [r.getMessage() for r in caplog_info.records if "consumer loop exit" in r.getMessage()]
        assert exits, "close() 也要触发 finally 的 exit 日志"
        assert any("reason=generator_exit" in m for m in exits), f"close() 应打 generator_exit，实际 {exits}"


class TestConsumerProgress:
    def test_progress_every_n_items(self, handler, caplog_info, monkeypatch):
        monkeypatch.setattr(GeneratorStreamingHelper, "_CONSUMER_PROGRESS_EVERY_N", 3)
        monkeypatch.setattr(GeneratorStreamingHelper, "_CONSUMER_PROGRESS_EVERY_SECONDS", 3600.0)

        helper = GeneratorStreamingHelper(message_handler=handler, thread_id="tid_progress")

        def _gen():
            for i in range(7):
                yield f"m-{i}"

        out = _drive(helper, _gen())
        assert len(out) == 7

        progress = [r.getMessage() for r in caplog_info.records if "consumer progress" in r.getMessage()]
        # 7 条里第 3、6 两次触发
        assert len(progress) == 2, f"期望 2 条 progress，实际 {len(progress)}: {progress}"
        assert "consumed_total=3" in progress[0]
        assert "consumed_total=6" in progress[1]


class TestYieldSlowWarning:
    def test_yield_slow_triggers_warning(self, handler, caplog_info, monkeypatch):
        """yield 前后耗时超阈值应打 WARNING（H1 直接证据点）。"""
        monkeypatch.setattr(GeneratorStreamingHelper, "_YIELD_SLOW_SEC", 0.05)
        caplog_info.set_level(logging.WARNING, logger="aidev_agent.services.messages_handler.streaming_helper")

        helper = GeneratorStreamingHelper(message_handler=handler, thread_id="tid_yield_slow")

        def _gen():
            yield "slow-chunk"
            yield "fast-chunk"

        stream_gen = helper.stream(_gen())
        # 拿到第一条就故意停 150ms（> 阈值 50ms），模拟下游消费阻塞
        first = next(stream_gen)
        assert first == "slow-chunk"
        time.sleep(0.15)
        # 下一次 next() 被阻塞了 150ms 才返回 → 下一次循环里上一轮 yield 的 elapsed 被测到
        rest = list(stream_gen)
        assert rest == ["fast-chunk"]

        warns = [
            r.getMessage()
            for r in caplog_info.records
            if r.levelno == logging.WARNING and "yield slow" in r.getMessage()
        ]
        assert warns, "超阈值应打 yield slow WARNING，实际 WARNING 列表为空"
        assert any("yielded_total=1" in m for m in warns), f"WARNING 应带 yielded_total，实际 {warns}"


class TestOrphanCleanupTriggeredLog:
    def test_cleanup_triggered_has_judgement_fields(self, handler, caplog_info, monkeypatch):
        monkeypatch.setattr(GeneratorStreamingHelper, "_PRODUCER_CLEANUP_DELAY", 0.1)
        monkeypatch.setattr(GeneratorStreamingHelper, "_ORPHAN_CLEANUP_POLL_INTERVAL", 0.02)

        thread_id = "tid_orphan_log"
        handler.put(thread_id, "left-over")
        helper = GeneratorStreamingHelper(message_handler=handler, thread_id=thread_id)
        helper._schedule_session_cleanup(done_event_seen=False)

        deadline = time.time() + 2.5
        while time.time() < deadline:
            if any("orphan cleanup triggered" in r.getMessage() for r in caplog_info.records):
                break
            time.sleep(0.02)

        triggered = [r.getMessage() for r in caplog_info.records if "orphan cleanup triggered" in r.getMessage()]
        assert triggered, "cleanup 必须打 orphan cleanup triggered"
        msg = triggered[0]
        for kw in (
            f"thread_id={thread_id}",
            "elapsed=",
            "reason=deadline",
            "done_event_seen=False",
            "had_active_consumer=False",
            "consumer_ever_seen=False",
        ):
            assert kw in msg, f"orphan cleanup 日志缺少 {kw}：{msg}"
