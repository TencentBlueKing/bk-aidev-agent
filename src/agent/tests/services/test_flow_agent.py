# -*- coding: utf-8 -*-
"""FlowAgentCompletionAgent 核心单元测试

聚焦两个主流程：
1. 主流程：start 启动 → SSE 流式输出 → 轮询到终态
2. stop 终止：轮询中触发取消信号 → 正确终止 bkflow 任务
"""

import json
import time
from unittest.mock import MagicMock, patch

from ag_ui.core import EventType
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.services.agent import FlowAgentCompletionAgent
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


class MockResourceManager:
    """实现 ResourceManagerProtocol 的 Mock，同时覆盖 flow agent 所需方法"""

    def __init__(self, start_result=None, start_error=None, task_info_sequence=None, error_on_call=None):
        self._start_result = start_result or {"task_id": "12345"}
        self._start_error = start_error
        self._sequence = task_info_sequence or [
            {"task_state": "RUNNING", "nodes": {}},
            {"task_state": "FINISHED", "task_outputs": [{"key": "result", "value": "done"}]},
        ]
        self._error_on_call = error_on_call or {}
        self._poll_call_count = 0

    def start_flow_agent(self, data: dict, **kwargs) -> dict:
        if self._start_error:
            raise self._start_error
        return self._start_result

    def get_flow_agent_task_info(self, task_id: str, **kwargs) -> dict:
        idx = self._poll_call_count
        self._poll_call_count += 1
        if idx in self._error_on_call:
            raise self._error_on_call[idx]
        if idx < len(self._sequence):
            return self._sequence[idx]
        return self._sequence[-1]

    # 以下为 ResourceManagerProtocol 其他方法的 stub，FlowAgent 不使用
    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict: ...
    def retrieve_knowledge(self, id: int, **kwargs) -> dict: ...
    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]: ...
    def retrieve_agent_config(self, agent_code: str, version=None, **kwargs) -> dict: ...
    def retrieve_skill(self, skill_id: str, version: str, **kwargs) -> dict: ...
    def construct_tool(self, tool_code: str, **kwargs): ...
    def knowledge_query(self, data: dict, **kwargs) -> dict: ...
    def retry_flow_agent_node(self, session_code: str, node_id: str, **kwargs) -> dict:
        return {}

    def skip_flow_agent_node(self, session_code: str, node_id: str, **kwargs) -> dict:
        return {}

    def stop_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        return {}

    def pause_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        return {}

    def resume_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        return {}

    def get_flow_agent_task_node_info(self, task_id: str, node_id: str, **kwargs) -> dict:
        return {}


class TestFlowAgentCompletion:
    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_background_execute_updates_session_after_flow_completion(self, mock_cancelled):
        event_handler = MagicMock()
        agent = FlowAgentCompletionAgent(
            resource_manager=MockResourceManager(),
            flow_start_params={"session_code": "flow-session"},
            poll_interval=0.01,
            poll_timeout=10.0,
            session_code="flow-session",
            event_handler=event_handler,
        )

        list(agent.execute(MagicMock(background_only=True)))

        event_handler.set_streaming_finished.assert_called_once_with()


class TestFlowAgentMainFlow:
    """主流程：start → SSE 流式输出 → 轮询到终态"""

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_start_poll_finished(self, mock_cancelled):
        """完整主流程：调 start 拿 task_id → 轮询 RUNNING → FINISHED
        验证 SSE 事件序列：RUN_STARTED → flow_agent_start → flow_agent_result×N → flow_agent_end → RUN_FINISHED
        """
        mock_rm = MockResourceManager(
            start_result={"task_id": "99999"},
            task_info_sequence=[
                {"task_state": "RUNNING", "nodes": {"n1": {"status": "running"}}},
                {"task_state": "RUNNING", "nodes": {"n1": {"status": "completed"}, "n2": {"status": "running"}}},
                {"task_state": "FINISHED", "task_outputs": [{"key": "output", "value": "ok"}]},
            ],
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={"session_code": "s1", "flow_id": "f001"},
            poll_interval=0.01,
            poll_timeout=10.0,
        )

        events = _parse_sse_events(agent._run_flow())

        # 1) 第一个事件必须是 RUN_STARTED
        assert events[0]["type"] == EventType.RUN_STARTED

        # 2) 紧跟 flow_agent_start，携带 task_id（数组格式）
        start_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_START.value)
        assert len(start_events) == 1
        assert start_events[0]["value"][0]["task_id"] == "99999"

        # 3) 3 次轮询产生 3 个 flow_agent_result（RUNNING, RUNNING, FINISHED）
        result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESULT.value)
        assert len(result_events) == 3

        # 4) flow_agent_end 携带 task_outputs，无 error（数组格式）
        end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
        assert len(end_events) == 1
        assert end_events[0]["value"][0]["task_id"] == "99999"
        assert end_events[0]["value"][0]["task_outputs"] == [{"key": "output", "value": "ok"}]
        assert "error" not in end_events[0]["value"][0]

        # 5) 最后一个事件是 RUN_FINISHED
        assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_task_failed_has_error_flag(self, mock_cancelled):
        """任务以 FAILED 终态结束，flow_agent_end 应携带 error=True 和 state=FAILED"""
        mock_rm = MockResourceManager(
            start_result={"task_id": "88888"},
            task_info_sequence=[
                {"task_state": "RUNNING", "nodes": {}},
                {"task_state": "FAILED", "task_outputs": []},
            ],
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={"session_code": "s2"},
            poll_interval=0.01,
            poll_timeout=10.0,
        )

        events = _parse_sse_events(agent._run_flow())

        end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
        assert len(end_events) == 1
        assert end_events[0]["value"][0]["error"] is True
        assert end_events[0]["value"][0]["state"] == "FAILED"

        # 仍然有完整的 RUN_STARTED → RUN_FINISHED 事件对
        assert events[0]["type"] == EventType.RUN_STARTED
        assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_start_error_emits_run_error(self, mock_cancelled):
        """start 接口异常时，应产出 RUN_ERROR + RUN_FINISHED，流程不崩溃"""
        mock_rm = MockResourceManager(start_error=ConnectionError("Gateway timeout"))

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
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
    def test_poll_timeout_emits_error(self, mock_cancelled):
        """轮询超时后应产出 RUN_ERROR + RUN_FINISHED"""
        never_finish = MockResourceManager(
            start_result={"task_id": "timeout_task"},
            task_info_sequence=[{"task_state": "RUNNING"}],
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=never_finish,
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
    """stop 终止流程：验证取消信号能正确终止轮询

    核心场景：
    - 任务已启动（flow_agent_start 已发送）→ RUN_FINISHED(runId="cancelled")
    - 任务未启动（start_flow_agent 之前取消）→ RUN_ERROR(message="用户已取消")
    """

    def test_cancel_after_task_started_emits_run_finished(self):
        """任务已启动后取消 → 手动构造 revoke flow_agent_result + RUN_FINISHED(runId="cancelled")

        模拟场景：flow_agent_start 已发送，轮询中检测到取消信号。
        _task_started=True → 基于 last_task_info 手动构造 revoke 事件，再发 RUN_FINISHED(cancelled)。
        """
        poll_count = {"n": 0}

        def mock_is_cancelled(thread_id, **kwargs):
            poll_count["n"] += 1
            # is_cancelled 会在 _run_flow 起始检查、每次循环开头、_interruptible_sleep 中被调用
            # 让第 4 次检查时触发取消（此时已完成 1 次正常轮询 + 1 次 sleep 检查）
            return poll_count["n"] >= 4

        mock_rm = MockResourceManager(
            start_result={"task_id": "cancel_task"},
            task_info_sequence=[{"task_state": "RUNNING"}] * 10,
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={},
            poll_interval=0.01,
            poll_timeout=60.0,
            session_code="stop_session",
        )

        with patch.object(GeneratorStreamingHelper, "is_cancelled", side_effect=mock_is_cancelled):
            events = _parse_sse_events(agent._run_flow())

        assert events[0]["type"] == EventType.RUN_STARTED
        assert len(_find_custom_events(events, CustomMessageType.FLOW_AGENT_START.value)) == 1
        assert len(_find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)) == 0

        # 最后一个 flow_agent_result 应是 revoke 状态（手动构造）
        result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESULT.value)
        assert result_events[-1]["value"][0]["task_state"] == "REVOKED"

        # 任务已启动后取消 → RUN_FINISHED(runId="cancelled")
        finished_events = _find_events_by_type(events, EventType.RUN_FINISHED)
        assert len(finished_events) >= 1
        assert finished_events[0].get("runId") == "cancelled"

    def test_cancel_emits_revoke_result_with_nodes(self):
        """任务已启动后取消 → 基于 last_task_info 手动构造 revoke 事件

        验证：
        - revoke 事件的 task_state 为 REVOKED
        - RUNNING 节点改为 REVOKED
        - FINISHED 节点保持不变
        - statistics 同步更新
        """
        poll_count = {"n": 0}

        def mock_is_cancelled(thread_id, **kwargs):
            poll_count["n"] += 1
            return poll_count["n"] >= 4

        running_data = {
            "task_state": "RUNNING",
            "task_id": 999,
            "task_name": "test_task",
            "nodes": {
                "n1": {"id": "n1", "name": "消息展示", "type": "ServiceActivity", "state": "FINISHED"},
                "n2": {"id": "n2", "name": "知识库", "type": "ServiceActivity", "state": "RUNNING"},
                "n3": {"id": "n3", "name": "待执行节点", "type": "ServiceActivity", "state": "PENDING"},
            },
            "statistics": {"total": 3, "state_counts": {"FINISHED": 1, "RUNNING": 1, "PENDING": 1}},
        }
        mock_rm = MockResourceManager(
            start_result={"task_id": "999"},
            task_info_sequence=[running_data] * 10,
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={},
            poll_interval=0.01,
            poll_timeout=60.0,
            session_code="revoke_session",
        )

        with patch.object(GeneratorStreamingHelper, "is_cancelled", side_effect=mock_is_cancelled):
            events = _parse_sse_events(agent._run_flow())

        result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESULT.value)
        # 最后一个 flow_agent_result 应该是 revoke 状态
        revoke_event = result_events[-1]
        # value 是 list，取第一个元素
        revoke_value = revoke_event["value"][0]
        assert revoke_value["task_state"] == "REVOKED"

        # nodes 是 dict，RUNNING 节点手动改为 REVOKED
        assert revoke_value["nodes"]["n2"]["state"] == "REVOKED"
        # FINISHED 节点保持不变
        assert revoke_value["nodes"]["n1"]["state"] == "FINISHED"
        # PENDING 节点保持不变
        assert revoke_value["nodes"]["n3"]["state"] == "PENDING"

        # statistics 更新
        stats = revoke_value["statistics"]
        assert stats["total"] == 3
        assert stats["state_counts"]["REVOKED"] == 1
        assert stats["state_counts"]["FINISHED"] == 1
        assert stats["state_counts"]["PENDING"] == 1

    def test_cancel_before_task_started_emits_run_error(self):
        """任务未启动时取消 → 发 RUN_ERROR(message="用户已取消")

        模拟场景：start_flow_agent 调用前就已检测到取消信号。
        _task_started=False → 发 RUN_ERROR(message="用户已取消")。
        """

        def mock_is_cancelled_true(thread_id, **kwargs):
            return True  # 一开始就取消

        mock_rm = MockResourceManager(start_result={"task_id": "pre_cancel"})

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={},
            poll_interval=0.01,
            poll_timeout=60.0,
            session_code="pre_cancel_session",
        )

        with patch.object(GeneratorStreamingHelper, "is_cancelled", side_effect=mock_is_cancelled_true):
            events = _parse_sse_events(agent._run_flow())

        # 没有 flow_agent_start（任务未启动就被取消）
        assert len(_find_custom_events(events, CustomMessageType.FLOW_AGENT_START.value)) == 0

        # 任务未启动取消 → RUN_ERROR(message="用户已取消")
        error_events = _find_events_by_type(events, EventType.RUN_ERROR)
        assert len(error_events) >= 1
        from aidev_agent.utils.event import RunId

        assert error_events[0].get("message") == RunId.CANCELLED_MESSAGE

    def test_cancel_before_start_api_call(self):
        """在 start_flow_agent 调用前就取消 → 直接发 RUN_ERROR，不调用 start API"""

        def mock_is_cancelled_true(thread_id, **kwargs):
            return True

        mock_rm = MockResourceManager()
        mock_rm.start_flow_agent = MagicMock(return_value={"task_id": "should_not_be_called"})

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={},
            poll_interval=0.01,
            poll_timeout=60.0,
            session_code="cancel_before_api",
        )

        with patch.object(GeneratorStreamingHelper, "is_cancelled", side_effect=mock_is_cancelled_true):
            events = _parse_sse_events(agent._run_flow())

        # start_flow_agent 不应被调用
        mock_rm.start_flow_agent.assert_not_called()

        # 应有 RUN_ERROR
        error_events = _find_events_by_type(events, EventType.RUN_ERROR)
        assert len(error_events) >= 1

    def test_stop_method_calls_cancel(self):
        """stop() 方法应调用 GeneratorStreamingHelper.cancel() 来终止流"""
        agent = FlowAgentCompletionAgent(
            session_code="stop_test_session",
        )

        with patch.object(GeneratorStreamingHelper, "cancel") as mock_cancel:
            agent.stop()
            mock_cancel.assert_called_once_with("stop_test_session")

    def test_stop_uses_thread_id_when_no_session_code(self):
        """没有 session_code 时，stop() 使用 thread_id"""
        agent = FlowAgentCompletionAgent(
            thread_id="my_thread_123",
        )

        with patch.object(GeneratorStreamingHelper, "cancel") as mock_cancel:
            agent.stop()
            mock_cancel.assert_called_once_with("my_thread_123")

    def test_cancel_during_interruptible_sleep(self):
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


class TestFlowAgentRetrySkip:
    """节点重试/跳过流程：已有 task_id + resume_from_node 时恢复轮询

    核心场景：
    - retry：发送 FLOW_AGENT_RESTART(action="retry")，跳过 start API
    - skip：发送 FLOW_AGENT_RESTART(action="skip")，跳过 start API
    - resume 后正常轮询到终态
    - resume 后轮询到 FAILED
    - cancel 在 resume 后生效
    """

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_resume_emits_node_resumed_event(self, mock_cancelled):
        """retry/skip 场景应发送 FLOW_AGENT_RESTART 事件而非 FLOW_AGENT_START

        验证：
        - 不发送 flow_agent_start
        - 发送 flow_agent_restart，携带 task_id 和 action
        - 正常轮询到 FINISHED
        - 完整事件序列：RUN_STARTED → flow_agent_restart → flow_agent_result×N → flow_agent_end → RUN_FINISHED
        """
        for action in ("retry", "skip"):
            mock_rm = MockResourceManager(
                task_info_sequence=[
                    {"task_state": "RUNNING", "nodes": {"n1": {"id": "n1", "state": "RUNNING"}}},
                    {"task_state": "FINISHED", "task_outputs": [{"key": "result", "value": "ok"}]},
                ],
            )

            agent = FlowAgentCompletionAgent(
                resource_manager=mock_rm,
                flow_start_params={"session_code": "s_resume"},
                task_id="existing_task_001",
                resume_from_node=action,
                poll_interval=0.01,
                poll_timeout=10.0,
            )

            events = _parse_sse_events(agent._run_flow())

            # 1) 不发送 flow_agent_start
            start_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_START.value)
            assert len(start_events) == 0

            # 2) 发送 flow_agent_restart，携带 task_id 和 action
            resumed_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESTART.value)
            assert len(resumed_events) == 1
            assert resumed_events[0]["value"][0]["task_id"] == "existing_task_001"
            assert resumed_events[0]["value"][0]["action"] == action

            # 3) resume 场景轮询通过 flow_agent_update 事件推送给前端
            result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_UPDATE.value)
            assert len(result_events) == 2  # RUNNING + FINISHED

            # 4) flow_agent_end 正常
            end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
            assert len(end_events) == 1
            assert end_events[0]["value"][0]["task_id"] == "existing_task_001"
            assert "error" not in end_events[0]["value"][0]

            # 5) 完整事件序列
            assert events[0]["type"] == EventType.RUN_STARTED
            assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_resume_skips_start_api_call(self, mock_cancelled):
        """retry/skip 场景不应调用 start_flow_agent API

        已有 task_id 时，应跳过 start 接口调用，直接进入轮询。
        """
        for action in ("retry", "skip"):
            mock_rm = MockResourceManager(
                task_info_sequence=[
                    {"task_state": "FINISHED", "task_outputs": []},
                ],
            )
            mock_rm.start_flow_agent = MagicMock(return_value={"task_id": "should_not_be_called"})

            agent = FlowAgentCompletionAgent(
                resource_manager=mock_rm,
                flow_start_params={"session_code": "s_skip_start"},
                task_id="existing_task_002",
                resume_from_node=action,
                poll_interval=0.01,
                poll_timeout=10.0,
            )

            events = _parse_sse_events(agent._run_flow())

            # start_flow_agent 不应被调用
            mock_rm.start_flow_agent.assert_not_called()

            # 仍然有完整的事件序列
            assert events[0]["type"] == EventType.RUN_STARTED
            assert events[-1]["type"] == EventType.RUN_FINISHED

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_retry_poll_to_failed(self, mock_cancelled):
        """retry 后轮询到 FAILED 终态，flow_agent_end 应携带 error=True 和 state=FAILED"""
        mock_rm = MockResourceManager(
            task_info_sequence=[
                {"task_state": "RUNNING", "nodes": {"n1": {"id": "n1", "state": "RUNNING"}}},
                {"task_state": "FAILED", "task_outputs": []},
            ],
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={"session_code": "s_retry_fail"},
            task_id="retry_fail_task",
            resume_from_node="retry",
            poll_interval=0.01,
            poll_timeout=10.0,
        )

        events = _parse_sse_events(agent._run_flow())

        end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
        assert len(end_events) == 1
        assert end_events[0]["value"][0]["error"] is True
        assert end_events[0]["value"][0]["state"] == "FAILED"
        assert events[-1]["type"] == EventType.RUN_FINISHED

    def test_cancel_after_resume_emits_revoke(self):
        """retry 后取消应正确发送 revoke 状态的 flow_agent_result + RUN_FINISHED(cancelled)

        验证：
        - flow_agent_restart 已发送
        - 取消后最后一个 flow_agent_result 的 task_state 为 REVOKED
        - RUN_FINISHED 的 runId 为 cancelled
        """
        poll_count = {"n": 0}

        def mock_is_cancelled(thread_id, **kwargs):
            poll_count["n"] += 1
            return poll_count["n"] >= 4

        running_data = {
            "task_state": "RUNNING",
            "task_id": "cancel_resume_task",
            "nodes": {
                "n1": {"id": "n1", "name": "重试节点", "type": "ServiceActivity", "state": "RUNNING"},
                "n2": {"id": "n2", "name": "已完成节点", "type": "ServiceActivity", "state": "FINISHED"},
            },
            "statistics": {"total": 2, "state_counts": {"RUNNING": 1, "FINISHED": 1}},
        }
        mock_rm = MockResourceManager(
            start_result={"task_id": "cancel_resume_task"},
            task_info_sequence=[running_data] * 10,
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={"session_code": "s_cancel_resume"},
            task_id="cancel_resume_task",
            resume_from_node="retry",
            poll_interval=0.01,
            poll_timeout=60.0,
            session_code="cancel_resume_session",
        )

        with patch.object(GeneratorStreamingHelper, "is_cancelled", side_effect=mock_is_cancelled):
            events = _parse_sse_events(agent._run_flow())

        # 应有 flow_agent_restart 事件
        resumed_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESTART.value)
        assert len(resumed_events) == 1
        assert resumed_events[0]["value"][0]["action"] == "retry"

        # 最后一个 flow_agent_result 应是 REVOKED
        result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESULT.value)
        revoke_value = result_events[-1]["value"][0]
        assert revoke_value["task_state"] == "REVOKED"

        # RUNNING 节点被改为 REVOKED
        assert revoke_value["nodes"]["n1"]["state"] == "REVOKED"
        # FINISHED 节点保持不变
        assert revoke_value["nodes"]["n2"]["state"] == "FINISHED"

        # RUN_FINISHED(runId="cancelled")
        finished_events = _find_events_by_type(events, EventType.RUN_FINISHED)
        assert len(finished_events) >= 1
        assert finished_events[0].get("runId") == "cancelled"

    @patch.object(GeneratorStreamingHelper, "is_cancelled", return_value=False)
    def test_existing_task_id_without_resume_skips_start_event(self, mock_cancelled):
        """已有 task_id 但无 resume_from_node 时，跳过所有启动事件直接轮询

        验证：
        - 不发送 flow_agent_start
        - 不发送 flow_agent_restart
        - 直接进入轮询
        """
        mock_rm = MockResourceManager(
            task_info_sequence=[
                {"task_state": "RUNNING", "nodes": {}},
                {"task_state": "FINISHED", "task_outputs": []},
            ],
        )

        agent = FlowAgentCompletionAgent(
            resource_manager=mock_rm,
            flow_start_params={"session_code": "s_existing"},
            task_id="existing_task_003",
            poll_interval=0.01,
            poll_timeout=10.0,
        )

        events = _parse_sse_events(agent._run_flow())

        # 不发送 flow_agent_start
        start_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_START.value)
        assert len(start_events) == 0

        # 不发送 flow_agent_restart
        resumed_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESTART.value)
        assert len(resumed_events) == 0

        # 正常轮询和结束
        result_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_RESULT.value)
        assert len(result_events) == 2
        end_events = _find_custom_events(events, CustomMessageType.FLOW_AGENT_END.value)
        assert len(end_events) == 1
        assert events[0]["type"] == EventType.RUN_STARTED
        assert events[-1]["type"] == EventType.RUN_FINISHED
