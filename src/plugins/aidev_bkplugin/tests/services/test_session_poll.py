from unittest.mock import Mock

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_bkplugin.enums import PluginPollTaskState
from aidev_bkplugin.models import SessionPollTurn
from aidev_bkplugin.services import chat_tasks, producer_dispatch
from aidev_bkplugin.services.producer_dispatch import ChatDispatcher, ChatExecutionSpec
from aidev_bkplugin.services.session_poll import (
    PollSessionBusy,
    PollSubmissionFailed,
    execute_poll_turn,
    poll_turn_result,
    reserve_poll_turn,
)
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager():
    manager = Mock(agent_code="agent", resource_manager=Mock(tenant_id="tenant"))
    session = {"status": "finished"}
    manager.retrieve_session.return_value = session
    manager.update_session_status.side_effect = lambda code, status: session.update(status=status)
    manager.save_stream_failure.side_effect = lambda *args, **kwargs: session.update(status="failed")
    manager.list_session_contents.return_value = []
    return manager


@pytest.mark.parametrize("chat_context", [None, [{"role": "user", "content": "plugin input"}]])
def test_dispatch_execute_and_poll(manager, monkeypatch, chat_context):
    spec = ChatExecutionSpec(
        app_code="app", agent_code="agent", session_code="s", turn_id="t", username="alice", tenant_id="tenant"
    )
    monkeypatch.setattr(chat_tasks, "close_old_connections", Mock())
    submit = Mock()
    monkeypatch.setattr(producer_dispatch.current_app, "send_task", submit)
    monkeypatch.setattr(chat_tasks.agent_settings, "APP_CODE", "app")
    backend = Mock(side_effect=AssertionError("poll should not touch the stream backend"))
    monkeypatch.setattr(producer_dispatch.message_handler_factory, "get", backend)
    builder = Mock(session_manager=manager)
    monkeypatch.setattr(chat_tasks, "_chat_builder", Mock(return_value=builder))
    plugin_build = Mock()
    monkeypatch.setattr(chat_tasks, "build_chat_agent_for_session", plugin_build)
    agent = builder.by_session_code.return_value if chat_context is None else plugin_build.return_value
    result = {"choices": [{"delta": {"content": "answer"}}]}
    agent.execute.return_value = result
    with reserve_poll_turn(manager, "s", "t", None) as ticket:
        ChatDispatcher(spec).submit_poll(ExecuteKwargs(input="question"), ticket, chat_context=chat_context)
    assert poll_turn_result(manager, "s", "t") == (PluginPollTaskState.RUNNING, "")
    with pytest.raises(PollSessionBusy), reserve_poll_turn(manager, "s", "other", None):
        pytest.fail("overlapping turn was admitted")
    assert submit.call_args.args == (chat_tasks.POLL_CHAT_TASK_NAME,)
    payload = submit.call_args.kwargs["kwargs"]
    chat_tasks.run_poll_chat.run(**payload)
    chat_tasks.run_poll_chat.run(**payload)
    if chat_context is not None:
        builder.by_session_code.assert_not_called()
        assert plugin_build.call_args.kwargs["chat_context"] == chat_context
    assert agent.execute.call_count == 1
    assert not agent.execute.call_args.args[0].stream
    manager.save_ai_response.assert_called_once_with("s", result, turn_id="t", persist_empty=True)
    assert manager.retrieve_session("s")["status"] == "finished"
    manager.list_session_contents.return_value = [
        {"role": "ai", "status": "success", "property": {"turn_id": "t"}, "content": "answer"},
        {"role": "ai", "status": "success", "property": {"turn_id": "other"}, "content": "other answer"},
    ]
    assert poll_turn_result(manager, "s", "t") == (PluginPollTaskState.SUCCESS, "answer")
    backend.assert_not_called()


def test_publish_failure_releases_turn(manager):
    with pytest.raises(PollSubmissionFailed, match="broker"), reserve_poll_turn(manager, "s", "t", None):
        raise OSError("broker")
    assert manager.retrieve_session("s")["status"] == "failed"
    assert not SessionPollTurn.objects.exists()


def test_cancel_during_execution_keeps_cancelled(manager):
    with reserve_poll_turn(manager, "s", "t", None) as ticket:
        pass
    execute_poll_turn(manager, "s", "t", ticket, lambda: manager.update_session_status("s", "cancelled"))
    manager.save_ai_response.assert_not_called()
    assert manager.retrieve_session("s")["status"] == "cancelled"


def test_missing_worker_converges_on_poll(manager):
    with reserve_poll_turn(manager, "s", "t", None) as ticket:
        pass
    SessionPollTurn.objects.filter(ticket=ticket).update(expires_at=timezone.now())
    assert poll_turn_result(manager, "s", "t")[0] == PluginPollTaskState.FAILED
    execute_poll_turn(manager, "s", "t", ticket, Mock(side_effect=AssertionError("expired")))
    assert not SessionPollTurn.objects.exists()


def test_failure_is_persisted_for_this_turn(manager):
    with reserve_poll_turn(manager, "s", "t", None) as ticket:
        pass
    with pytest.raises(ValueError, match="model error"):
        execute_poll_turn(manager, "s", "t", ticket, Mock(side_effect=ValueError("model error")))
    manager.save_stream_failure.assert_called_once_with("s", "model error", turn_id="t")
