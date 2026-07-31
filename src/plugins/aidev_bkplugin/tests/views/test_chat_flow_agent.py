# -*- coding: utf-8 -*-
"""``ChatCompletionViewSet._handle_flow_agent`` 续流判别契约。

前端恒不回传 task_id，续流完全由 ``flow_info.resume_pending`` 标记驱动：
- resume_pending=True 且 flow_info 有 task_id → 续流该任务，并一次性清除标记；
- resume_pending=True 但无 task_id → 回落起新任务（task_id=None），仍清除标记；
- 无标记 → 起新任务（task_id=None），不触碰标记。

通过捕获 ``AgentInstanceFactory.build_agent`` 收到的 ``task_id`` kwarg 断言分支结果。
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def flow_agent_env(monkeypatch):
    """隔离 _handle_flow_agent 的外部依赖，返回 (view, build_agent_mock, session_manager_mock)。"""
    from aidev_bkplugin.views import chat as mod

    session_manager = MagicMock()
    monkeypatch.setattr(mod, "SessionManager", lambda username: session_manager)

    # build_agent 返回 execute() 产出空流的 agent，便于走完后续分支而不真正轮询
    agent_instance = MagicMock()
    agent_instance.execute.return_value = iter([])
    build_agent = MagicMock(return_value=agent_instance)
    monkeypatch.setattr(mod.AgentInstanceFactory, "build_agent", staticmethod(build_agent))

    writer_cls = MagicMock()
    monkeypatch.setattr(mod, "AGUISessionWriter", writer_cls)
    monkeypatch.setattr(mod, "PluginResourceManager", lambda username: MagicMock())
    monkeypatch.setattr(mod.AgentHelper, "get_client", staticmethod(lambda: MagicMock()))

    view = mod.ChatCompletionViewSet()
    monkeypatch.setattr(view, "streaming_response", lambda generator, session_code="": "STREAM")

    return view, build_agent, session_manager, writer_cls


def _data():
    return {"flow_start_params": {}, "poll_interval": 0.5, "poll_timeout": 30.0}


def test_resume_pending_hit_resumes_task_and_clears_marker(flow_agent_env):
    view, build_agent, sm, writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {"task_id": "t1", "resume_pending": True}

    view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1")

    assert build_agent.call_args.kwargs["task_id"] == "t1"
    assert writer_cls.call_args.kwargs["task_id"] == "t1"
    sm.set_flow_resume_pending.assert_called_once_with("sc-1", False)


def test_resume_pending_without_task_id_starts_new_but_clears_marker(flow_agent_env):
    view, build_agent, sm, _writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {"task_id": "", "resume_pending": True}

    view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1")

    assert build_agent.call_args.kwargs["task_id"] is None
    sm.set_flow_resume_pending.assert_called_once_with("sc-1", False)


def test_no_marker_starts_new_task_without_touching_marker(flow_agent_env):
    view, build_agent, sm, _writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {"task_id": "t1"}  # 无 resume_pending

    view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1")

    assert build_agent.call_args.kwargs["task_id"] is None
    sm.set_flow_resume_pending.assert_not_called()


def test_flow_http_does_not_install_second_terminal_status_writer(flow_agent_env):
    view, _build_agent, sm, writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {}
    view._wrap_streaming_with_status = MagicMock(side_effect=AssertionError("duplicate terminal writer"))

    result = view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1")

    assert result == "STREAM"
    writer_cls.return_value.set_streaming_started.assert_called_once_with()
    view._wrap_streaming_with_status.assert_not_called()
