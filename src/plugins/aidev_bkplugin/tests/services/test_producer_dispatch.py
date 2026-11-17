from datetime import timedelta
from unittest.mock import Mock

import pytest
from aidev_agent.services.messages_handler.producer import ProducerOnlyRunner
from aidev_bkplugin.chat_tasks import execute_chat_producer, mark_chat_started, run_chat_producer
from aidev_bkplugin.models import ChatExecution
from aidev_bkplugin.services import producer_dispatch
from aidev_bkplugin.services.producer_dispatch import CeleryChatRunner, ChatExecutionSpec, cancel_chat_execution
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def spec():
    return ChatExecutionSpec(
        app_code="test-app",
        tenant_id="test-tenant",
        username="alice",
        agent_code="test-agent",
        session_code="test-session",
        turn_id="turn-1",
        execute_kwargs={"stream": True},
    )


@pytest.fixture
def dispatch(monkeypatch):
    sender = Mock()
    monkeypatch.setattr(producer_dispatch.current_app, "send_task", sender)
    return sender


def test_submission_is_serializable_and_duplicate_does_not_enqueue(spec, dispatch):
    runner = CeleryChatRunner(spec)
    first = runner._submit(spec)
    second = runner._submit(spec)
    assert first.task_id == second.task_id
    dispatch.assert_called_once()
    assert dispatch.call_args.kwargs["queue"] == "bkai_agent_task"
    assert dispatch.call_args.kwargs["kwargs"]["spec"]["tenant_id"] == "test-tenant"


def test_parallel_turn_cannot_replace_active_task(spec, dispatch):
    runner = CeleryChatRunner(spec)
    first = runner._submit(spec)
    spec.turn_id = "turn-2"
    with pytest.raises(RuntimeError, match="already active"):
        runner._submit(spec)
    assert ChatExecution.objects.get(scope=spec.scope).task_id == first.task_id


def test_failed_publish_is_visible(spec, dispatch):
    dispatch.side_effect = RuntimeError("broker unavailable")
    with pytest.raises(RuntimeError, match="broker unavailable"):
        CeleryChatRunner(spec)._submit(spec)
    assert ChatExecution.objects.get(scope=spec.scope).status == "failed"


def test_queue_timeout_fences_late_worker(spec, dispatch, monkeypatch):
    execution = CeleryChatRunner(spec)._submit(spec)
    ChatExecution.objects.filter(pk=execution.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(RuntimeError, match="queue wait expired"):
        CeleryChatRunner._wait(execution, ready=True)
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.agent_settings.APP_CODE", spec.app_code)
    execute = Mock()
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.execute_chat_producer", execute)
    run_chat_producer(spec.scope, execution.task_id, spec.model_dump(mode="json"))
    execute.assert_not_called()


def test_queued_cancellation_prevents_execution(spec, dispatch, monkeypatch):
    execution = CeleryChatRunner(spec)._submit(spec)
    cancel_chat_execution(spec.app_code, spec.tenant_id, spec.session_code)
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.agent_settings.APP_CODE", spec.app_code)
    execute = Mock()
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.execute_chat_producer", execute)
    run_chat_producer(spec.scope, execution.task_id, spec.model_dump(mode="json"))
    execute.assert_not_called()
    execution.refresh_from_db()
    assert execution.cancelled and execution.status == "failed"


def test_worker_claim_is_not_repeated(spec, dispatch, monkeypatch):
    execution = CeleryChatRunner(spec)._submit(spec)
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.agent_settings.APP_CODE", spec.app_code)
    execute = Mock(return_value={"answer": "done"})
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.execute_chat_producer", execute)
    for _ in range(2):
        run_chat_producer(spec.scope, execution.task_id, spec.model_dump(mode="json"))
    execute.assert_called_once()
    assert CeleryChatRunner._wait(execution, ready=False).result == {"answer": "done"}


def test_started_callback_requires_owned_uncancelled_task(spec, dispatch):
    execution = CeleryChatRunner(spec)._submit(spec)
    ChatExecution.objects.filter(pk=execution.pk).update(status="building")
    mark_chat_started(spec.scope, execution.task_id, spec.session_code, "run-1")
    execution.refresh_from_db()
    assert (execution.status, execution.run_id) == ("running", "run-1")
    with pytest.raises(RuntimeError, match="no longer owned"):
        mark_chat_started(spec.scope, "stale-task", spec.session_code, "run-2")


def test_tenant_scope_isolation(spec, dispatch):
    first = CeleryChatRunner(spec)._submit(spec)
    another = spec.model_copy(update={"tenant_id": "another-tenant"})
    second = CeleryChatRunner(another)._submit(another)
    cancel_chat_execution(spec.app_code, spec.tenant_id, spec.session_code)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.cancelled and not second.cancelled


def test_stale_stop_does_not_cancel_new_run(spec, dispatch):
    execution = CeleryChatRunner(spec)._submit(spec)
    ChatExecution.objects.filter(pk=execution.pk).update(status="running", run_id="current-run")
    cancel_chat_execution(spec.app_code, spec.tenant_id, spec.session_code, run_id="old-run")
    execution.refresh_from_db()
    assert not execution.cancelled
    cancel_chat_execution(spec.app_code, spec.tenant_id, spec.session_code, run_id="current-run")
    execution.refresh_from_db()
    assert execution.cancelled


@pytest.mark.parametrize("failure", [ValueError("invalid configuration"), RuntimeError("private upstream detail")])
def test_worker_failure_is_terminal_and_sanitized(spec, dispatch, monkeypatch, failure):
    execution = CeleryChatRunner(spec)._submit(spec)
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.agent_settings.APP_CODE", spec.app_code)
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.execute_chat_producer", Mock(side_effect=failure))
    with pytest.raises(type(failure)):
        run_chat_producer(spec.scope, execution.task_id, spec.model_dump(mode="json"))
    execution.refresh_from_db()
    assert execution.status == "failed"
    assert execution.error == type(failure).__name__


def test_worker_rebuilds_identity_options_and_producer_only(spec, monkeypatch, settings):
    factory = Mock()
    settings.BKAI_CHAT_RESOURCE_MANAGER_FACTORY = factory
    builder = Mock()
    builder_cls = Mock(return_value=builder)
    executor = Mock()
    executor.execute_with_save.return_value = iter(())
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.AgentBuilder", builder_cls)
    monkeypatch.setattr("aidev_bkplugin.chat_tasks.AgentExecutor", Mock(return_value=executor))
    spec.model = "selected-model"
    spec.version = "v1"
    spec.temperature = 0.2
    execute_chat_producer(spec, "task-id")
    factory.assert_called_once_with(username="alice", model="selected-model", tenant_id="test-tenant")
    assert builder_cls.call_args.kwargs["remote_execution"] is False
    assert builder_cls.call_args.kwargs["temperature"] == 0.2
    builder.by_session_code.assert_called_once_with("test-session", version="v1", channel_type=None)
    agent = builder.by_session_code.return_value
    assert isinstance(agent.resource_manager.get_producer_runner(), ProducerOnlyRunner)
    assert executor.execute_with_save.call_args.args[1].background_only is True
