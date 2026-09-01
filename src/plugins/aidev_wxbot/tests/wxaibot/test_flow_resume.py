"""Flow 节点重试/跳过后续流：只执行一次、沿用原会话、用主动消息投递终态。"""

from unittest.mock import MagicMock

import pytest
from aidev_wxbot.wxaibot.flow_cards import FlowNodeAction


@pytest.fixture
def flow_resume_case(monkeypatch):
    from aidev_wxbot.wxaibot import flow_resume as mod

    action = FlowNodeAction("session-1", "42", "n2", "skip", "HTTP请求", "alice-wx")
    manager = MagicMock()
    manager.retrieve_session.return_value = {
        "session_code": "session-1",
        "session_property": {"flow_info": {"task_id": "42"}},
    }
    strategy = MagicMock()
    agent_stream = MagicMock()
    agent_stream.session_code = "session-1"
    agent_stream.generator = iter(())
    strategy.open_stream.return_value = agent_stream
    executor = MagicMock()
    executor.submit.return_value = True
    monkeypatch.setattr(mod, "SessionManager", MagicMock(return_value=manager))
    monkeypatch.setattr(mod, "FlowAgentStrategy", MagicMock(return_value=strategy))
    monkeypatch.setattr(mod, "get_agent_executor", MagicMock(return_value=executor))
    monkeypatch.setattr(mod, "close_old_connections", MagicMock())
    case = type(
        "Case",
        (),
        {
            "module": mod,
            "action": action,
            "manager": manager,
            "strategy": strategy,
            "agent_stream": agent_stream,
            "executor": executor,
        },
    )()
    case.module._pending.clear()
    yield case
    case.module._pending.clear()


def test_resume_binds_signed_session_and_consumes_flow_kind(flow_resume_case):
    case = flow_resume_case
    delivery = MagicMock()
    case.module._resume_worker(case.action, "alice", delivery)
    case.strategy.open_stream.assert_called_once()
    kwargs = case.strategy.open_stream.call_args.kwargs
    assert kwargs["session_code"] == "session-1"
    assert kwargs["task_id"] == "42"
    assert kwargs["resume_from_node"] == "skip"
    assert kwargs["content"] == ""
    delivery.consume.assert_called_once()
    assert delivery.consume.call_args.kwargs["kind"] == "flow"
    delivery.finish.assert_called_once()


def test_duplicate_click_closes_unused_delivery(flow_resume_case):
    case = flow_resume_case
    delivery = MagicMock()
    case.module._pending.add(case.action)
    assert case.module.submit_flow_node_resume(case.action, "alice", delivery)
    case.executor.submit.assert_not_called()
    delivery.finish.assert_called_once()


def test_task_mismatch_does_not_open_stream(flow_resume_case):
    case = flow_resume_case
    case.manager.retrieve_session.return_value = {
        "session_code": "session-1",
        "session_property": {"flow_info": {"task_id": "99"}},
    }
    delivery = MagicMock()
    case.module._resume_worker(case.action, "alice", delivery)
    case.strategy.open_stream.assert_not_called()
    delivery.failed.assert_called_once()
    delivery.finish.assert_called_once()


def test_missing_session_does_not_open_stream(flow_resume_case):
    case = flow_resume_case
    case.manager.retrieve_session.return_value = {}
    delivery = MagicMock()
    case.module._resume_worker(case.action, "alice", delivery)
    case.strategy.open_stream.assert_not_called()
    delivery.failed.assert_called_once()


@pytest.mark.parametrize("raises", [False, True])
def test_failed_submission_releases_dedup_entry(flow_resume_case, raises):
    case = flow_resume_case
    case.executor.submit.return_value = False
    if raises:
        case.executor.submit.side_effect = RuntimeError("executor unavailable")
        with pytest.raises(RuntimeError):
            case.module.submit_flow_node_resume(case.action, "alice")
    else:
        assert not case.module.submit_flow_node_resume(case.action, "alice")
    assert not case.module._pending


def test_resume_failure_is_sanitized_and_releases_worker_state(flow_resume_case, caplog):
    case = flow_resume_case
    case.strategy.open_stream.side_effect = RuntimeError("secret-in-upstream-error")
    case.module._pending.add(case.action)
    delivery = MagicMock()
    case.module._resume_worker(case.action, "alice", delivery)
    assert "secret-in-upstream-error" not in caplog.text
    assert "wxbot_flow_resume_failed" in caplog.text
    assert not case.module._pending
    delivery.failed.assert_called_once()
    delivery.finish.assert_called_once()
