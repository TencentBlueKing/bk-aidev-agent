# -*- coding: utf-8 -*-
"""``ChatCompletionViewSet._handle_flow_agent`` 续流判别契约。

前端恒不回传 task_id，续流完全由 ``flow_info.resume_pending`` 标记驱动：
- resume_pending=True 且 flow_info 有 task_id → 续流该任务，并一次性清除标记；
- resume_pending=True 但无 task_id → 回落起新任务（task_id=None），仍清除标记；
- 无标记 → 起新任务（task_id=None），不触碰标记。

通过捕获 Celery 投递参数中的 task_id 断言分支结果。
"""

import sys
from unittest.mock import MagicMock

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs

_bk_plugin_framework = MagicMock()
_bk_plugin_framework.kit.decorators.inject_user_token = lambda func: func
sys.modules.setdefault("bk_plugin_framework", _bk_plugin_framework)
sys.modules.setdefault("bk_plugin_framework.kit", _bk_plugin_framework.kit)
sys.modules.setdefault("bk_plugin_framework.kit.decorators", _bk_plugin_framework.kit.decorators)


from aidev_bkplugin.views import chat as mod  # noqa: E402 - framework test shim must exist first


@pytest.fixture
def flow_agent_env(monkeypatch):
    """隔离 _handle_flow_agent 的外部依赖，返回 (view, build_agent_mock, session_manager_mock)。"""

    session_manager = MagicMock()
    monkeypatch.setattr(mod, "SessionManager", lambda **kwargs: session_manager)

    build_agent = MagicMock(return_value=iter(()))
    monkeypatch.setattr(mod, "dispatch_web_agent", build_agent)

    writer_cls = MagicMock()
    monkeypatch.setattr(mod, "AGUISessionWriter", writer_cls)
    # 不再 patch PluginResourceManager：flow 路径已复用注入的 rm，不会自行构造
    monkeypatch.setattr(mod.AgentHelper, "get_client", staticmethod(lambda *args, **kwargs: MagicMock()))

    view = mod.ChatCompletionViewSet()
    monkeypatch.setattr(view, "streaming_response", lambda generator, session_code="": "STREAM")

    return view, build_agent, session_manager, writer_cls


def _data():
    return {
        "flow_start_params": {},
        "poll_interval": 0.5,
        "poll_timeout": 30.0,
        "execute_kwargs": ExecuteKwargs(stream=True),
    }


def test_resume_pending_hit_resumes_task_and_clears_marker(flow_agent_env):
    view, build_agent, sm, writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {"task_id": "t1", "resume_pending": True}

    view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1", resource_manager=MagicMock())

    assert build_agent.call_args.kwargs["flow"]["task_id"] == "t1"
    writer_cls.assert_not_called()
    sm.set_flow_resume_pending.assert_called_once_with("sc-1", False)


def test_resume_pending_without_task_id_starts_new_but_clears_marker(flow_agent_env):
    view, build_agent, sm, _writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {"task_id": "", "resume_pending": True}

    view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1", resource_manager=MagicMock())

    assert build_agent.call_args.kwargs["flow"]["task_id"] is None
    sm.set_flow_resume_pending.assert_called_once_with("sc-1", False)


def test_no_marker_starts_new_task_without_touching_marker(flow_agent_env):
    view, build_agent, sm, _writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {"task_id": "t1"}  # 无 resume_pending

    view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1", resource_manager=MagicMock())

    assert build_agent.call_args.kwargs["flow"]["task_id"] is None
    sm.set_flow_resume_pending.assert_not_called()


def test_flow_agent_reuses_injected_resource_manager(flow_agent_env):
    """Flow 路径必须把注入的 rm 交给 FlowAgentCompletionAgent。

    此处曾另建 PluginResourceManager(username=...)，会丢掉子类自定义的凭证与 agent_code，
    使 start/poll 退回主应用配置，pre-request RM 在 Flow 路径失效。
    """
    view, build_agent, sm, _writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {}
    rm = MagicMock()

    view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1", resource_manager=rm)

    assert build_agent.call_args.kwargs["resource_manager"] is rm


def test_flow_http_does_not_install_second_terminal_status_writer(flow_agent_env):
    view, _build_agent, sm, writer_cls = flow_agent_env
    sm.get_flow_info.return_value = {}
    view._wrap_streaming_with_status = MagicMock(side_effect=AssertionError("duplicate terminal writer"))

    result = view._handle_flow_agent(_data(), "sc-1", "alice", turn_id="turn-1", resource_manager=MagicMock())

    assert result == "STREAM"
    writer_cls.assert_not_called()
    view._wrap_streaming_with_status.assert_not_called()


@pytest.mark.parametrize("stream", [True, False])
def test_chat_http_dispatches_without_building_agent(monkeypatch, stream):
    view = mod.ChatCompletionViewSet()
    rm = MagicMock()
    monkeypatch.setattr(view, "get_username", lambda: "alice")
    monkeypatch.setattr(view, "get_resource_manager", lambda: rm)
    monkeypatch.setattr(view, "_resolve_chat_turn_id", lambda *args: "turn")
    monkeypatch.setattr(view, "streaming_response", lambda result, **kwargs: result)
    builder = MagicMock(side_effect=AssertionError("Web must not construct the agent"))
    monkeypatch.setattr(mod, "AgentBuilder", builder)
    dispatch = MagicMock(return_value={"reply": "answer"})
    monkeypatch.setattr(mod, "dispatch_web_agent", dispatch)
    execute = ExecuteKwargs(stream=stream)
    data = dict(
        execute_kwargs=execute,
        session_code="session",
        input="hello",
        chat_history=[],
        agent_type=mod.AgentType.CHAT.value,
        thread_id="",
    )
    serializer = MagicMock()
    serializer.validated_data = data
    monkeypatch.setattr(mod, "ChatCompletionRequestSerializer", lambda **kwargs: serializer)
    request = MagicMock()
    request.headers = {}
    view.create(request)
    assert dispatch.call_args.kwargs["execute_kwargs"].input == "hello"
    assert dispatch.call_args.kwargs["execute_kwargs"].turn_id == "turn"
    assert dispatch.call_args.kwargs["resource_manager"] is rm
    builder.assert_not_called()
