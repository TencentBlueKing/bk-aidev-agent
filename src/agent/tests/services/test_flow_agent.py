# -*- coding: utf-8 -*-
"""FlowAgentCompletionAgent 核心单元测试

聚焦两个主流程：
1. 主流程：start 启动 → SSE 流式输出 → 轮询到终态
2. stop 终止：轮询中触发取消信号 → 正确终止 bkflow 任务
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from ag_ui.core import EventType
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.services.flow_agent import FlowAgentCompletionAgent
from aidev_agent.services.messages_handler import GeneratorStreamingHelper



def _parse_sse_events(generator) -> list[dict]:
    """消费 SSE 生成器，解析所有事件为 dict 列表"""
    results = []
    for chunk in generator:
        if chunk.startswith("data: "):
            try:
                results.append(json.loads(chunk[6:]))
            except json.JSONDecodeError:
                results.append({"raw": chunk})
        else:
            results.append({"raw": chunk})
    return results


def _find_events_by_type(events: list[dict], event_type) -> list[dict]:
    type_val = event_type.value if hasattr(event_type, "value") else event_type
    return [e for e in events if e.get("type") == type_val]


def _find_custom_events(events: list[dict], name: str) -> list[dict]:
    return [e for e in events if e.get("type") == EventType.CUSTOM and e.get("name") == name]

class MockFlowAgentClient:
    """实现 FlowAgentClient 协议的 Mock"""

    def __init__(self, start_result=None, start_error=None):
        self._start_result = start_result or {"task_id": "12345"}
        self._start_error = start_error

    def start_flow_agent(self, data: dict, **kwargs) -> dict:
        if self._start_error:
            raise self._start_error
        return self._start_result


class MockPollClient:
    """实现 FlowAgentPollClient 协议的 Mock

    按顺序返回预设的 task_info 列表，支持指定在第 N 次调用时抛出异常。
    """

    def __init__(self, task_info_sequence: list[dict] | None = None, error_on_call: dict | None = None):
        self._sequence = task_info_sequence or [
            {"task_state": "RUNNING", "nodes": {}},
            {"task_state": "FINISHED", "task_outputs": [{"key": "result", "value": "done"}]},
        ]
        self._error_on_call = error_on_call or {}
        self._call_count = 0

    def get_flow_agent_task_info(self, task_id: str, **kwargs) -> dict:
        idx = self._call_count
        self._call_count += 1
        if idx in self._error_on_call:
            raise self._error_on_call[idx]
        if idx < len(self._sequence):
            return self._sequence[idx]
        return self._sequence[-1]


class TestFlowAgentMainFlow:
    """主流程：start → SSE 流式输出 → 轮询到终态"""

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_start_poll_finished(self, mock_api, mock_cancelled):
        """完整主流程：调 start 拿 task_id → 轮询 RUNNING → FINISHED
        验证 SSE 事件序列：RUN_STARTED → flow_agent_start → flow_agent_result×N → flow_agent_end → RUN_FINISHED
        """
        mock_start_client = MockFlowAgentClient(start_result={"task_id": "99999"})
        mock_poll_client = MockPollClient(
            task_info_sequence=[
                {"task_state": "RUNNING", "nodes": {"n1": {"status": "running"}}},
                {"task_state": "RUNNING", "nodes": {"n1": {"status": "completed"}, "n2": {"status": "running"}}},
                {"task_state": "FINISHED", "task_outputs": [{"key": "output", "value": "ok"}]},
            ]
        )
        mock_api.get_client.return_value = mock_poll_client

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_start_client,
            flow_start_params={"session_code": "s1", "flow_id": "f001"},
            poll_interval=0.01,
            poll_timeout=10.0,
        )

        events = _parse_sse_events(agent._run_flow())

        # 1) 第一个事件必须是 RUN_STARTED
        assert events[0]["type"] == EventType.RUN_STARTED

        # 2) 紧跟 flow_agent_start，携带 task_id
        start_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_START.value)
        assert len(start_events) == 1
        assert start_events[0]["value"]["task_id"] == "99999"

        # 3) 3 次轮询产生 3 个 flow_agent_result（RUNNING, RUNNING, FINISHED）
        result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESULT.value)
        assert len(result_events) == 3

        # 4) flow_agent_end 携带 task_outputs，无 error
        end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
        assert len(end_events) == 1
        assert end_events[0]["value"]["task_id"] == "99999"
        assert end_events[0]["value"]["task_outputs"] == [{"key": "output", "value": "ok"}]
        assert "error" not in end_events[0]["value"]

        # 5) 最后一个事件是 RUN_FINISHED
        assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_task_failed_has_error_flag(self, mock_api, mock_cancelled):
        """任务以 FAILED 终态结束，flow_agent_end 应携带 error=True 和 state=FAILED"""
        mock_start_client = MockFlowAgentClient(start_result={"task_id": "88888"})
        mock_poll_client = MockPollClient(
            task_info_sequence=[
                {"task_state": "RUNNING", "nodes": {}},
                {"task_state": "FAILED", "task_outputs": []},
            ]
        )
        mock_api.get_client.return_value = mock_poll_client

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_start_client,
            flow_start_params={"session_code": "s2"},
            poll_interval=0.01,
            poll_timeout=10.0,
        )

        events = _parse_sse_events(agent._run_flow())

        end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
        assert len(end_events) == 1
        assert end_events[0]["value"]["error"] is True
        assert end_events[0]["value"]["state"] == "FAILED"

        # 仍然有完整的 RUN_STARTED → RUN_FINISHED 事件对
        assert events[0]["type"] == EventType.RUN_STARTED
        assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_start_error_emits_run_error(self, mock_api, mock_cancelled):
        """start 接口异常时，应产出 RUN_ERROR + RUN_FINISHED，流程不崩溃"""
        mock_start_client = MockFlowAgentClient(start_error=ConnectionError("Gateway timeout"))

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_start_client,
            flow_start_params={},
            poll_interval=0.01,
            poll_timeout=10.0,
        )

        events = _parse_sse_events(agent._run_flow())

        # 有 RUN_STARTED（在 start 调用之前就 yield 了）
        assert events[0]["type"] == EventType.RUN_STARTED

        # 有 RUN_ERROR，包含错误信息
        error_events = _find_events_by_type(events, EventType.RUN_ERROR)
        assert len(error_events) == 1
        assert "Gateway timeout" in error_events[0]["message"]

        # 有 RUN_FINISHED（确保前端收到结束信号）
        assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_poll_timeout_emits_error(self, mock_api, mock_cancelled):
        """轮询超时后应产出 RUN_ERROR + RUN_FINISHED"""
        never_finish = MockPollClient(
            task_info_sequence=[{"task_state": "RUNNING"}]
        )
        mock_api.get_client.return_value = never_finish

        agent = FlowAgentCompletionAgent(
            resource_manager=MockFlowAgentClient(start_result={"task_id": "timeout_task"}),
            flow_start_params={},
            poll_interval=0.01,
            poll_timeout=0.05,
        )

        events = _parse_sse_events(agent._run_flow())

        error_events = _find_events_by_type(events, EventType.RUN_ERROR)
        assert len(error_events) == 1
        assert "timeout" in error_events[0]["message"].lower()
        assert events[-1]["type"] == EventType.RUN_FINISHED


class TestFlowAgentStop:
    """stop 终止流程：验证取消信号能正确终止轮询"""

    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_cancel_stops_polling(self, mock_api):
        """轮询中触发取消信号 → 停止轮询并发出 RUN_FINISHED

        模拟场景：用户点击「停止」，前端调 stop() → GeneratorStreamingHelper.cancel()
        → _poll_task 下一次循环检测到 is_cancelled=True → 停止轮询
        """
        poll_count = {"n": 0}

        def mock_is_cancelled(thread_id, **kwargs):
            # 让前 2 次检查返回 False（正常轮询），第 3 次返回 True（模拟用户点停止）
            poll_count["n"] += 1
            return poll_count["n"] >= 3

        mock_poll_client = MockPollClient(
            task_info_sequence=[{"task_state": "RUNNING"}] * 10
        )
        mock_api.get_client.return_value = mock_poll_client

        agent = FlowAgentCompletionAgent(
            resource_manager=MockFlowAgentClient(start_result={"task_id": "cancel_task"}),
            flow_start_params={},
            poll_interval=0.01,
            poll_timeout=60.0,
            session_code="stop_session",
        )

        with patch.object(GeneratorStreamingHelper, "is_cancelled", side_effect=mock_is_cancelled):
            events = _parse_sse_events(agent._run_flow())

        # 有 RUN_STARTED
        assert events[0]["type"] == EventType.RUN_STARTED

        # 有 flow_agent_start（start 接口成功了）
        start_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_START.value)
        assert len(start_events) == 1

        # 有部分 flow_agent_result（取消前的轮询结果）
        result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESULT.value)
        assert len(result_events) >= 1

        # 没有 flow_agent_end（任务没有自然结束，是被取消的）
        end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
        assert len(end_events) == 0

        # 最后一个事件是 RUN_FINISHED（确保前端收到结束信号）
        assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_stop_method_calls_cancel(self, mock_api):
        """stop() 方法应调用 GeneratorStreamingHelper.cancel() 来终止流"""
        agent = FlowAgentCompletionAgent(
            session_code="stop_test_session",
        )

        with patch.object(GeneratorStreamingHelper, "cancel") as mock_cancel:
            agent.stop()
            mock_cancel.assert_called_once_with("stop_test_session")

    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_stop_uses_thread_id_when_no_session_code(self, mock_api):
        """没有 session_code 时，stop() 使用 thread_id"""
        agent = FlowAgentCompletionAgent(
            thread_id="my_thread_123",
        )

        with patch.object(GeneratorStreamingHelper, "cancel") as mock_cancel:
            agent.stop()
            mock_cancel.assert_called_once_with("my_thread_123")

    @patch("aidev_agent.services.flow_agent.BKAidevApi")
    def test_cancel_during_interruptible_sleep(self, mock_api):
        """取消信号能快速中断 _interruptible_sleep，不会卡在长等待中"""
        call_count = {"n": 0}

        def mock_is_cancelled(thread_id, **kwargs):
            call_count["n"] += 1
            return call_count["n"] >= 2  # 第二次检查即取消

        with patch.object(GeneratorStreamingHelper, "is_cancelled", side_effect=mock_is_cancelled):
            start = time.time()
            FlowAgentCompletionAgent._interruptible_sleep(5.0, "thread_cancel")
            elapsed = time.time() - start

        # 应在远小于 5 秒内退出（0.2 秒内足够）
        assert elapsed < 1.0
