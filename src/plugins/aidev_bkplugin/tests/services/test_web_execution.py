"""Celery dispatch and shared replay regression tests."""

import logging
import threading
import time
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_bkplugin.services import plugin_resource_manager as resource_mod
from aidev_bkplugin.services import web_execution as mod
from celery import Celery
from celery.backends.base import DisabledBackend
from celery.contrib.testing.worker import start_worker


@pytest.fixture
def execution(monkeypatch):
    helper = MagicMock(thread_id="session")
    monkeypatch.setattr(mod, "GeneratorStreamingHelper", lambda **kwargs: helper)
    task = MagicMock()
    monkeypatch.setattr(mod, "run_web_agent_task", task)
    args = dict(
        session_code="session",
        username="alice",
        channel_type="popup",
        execute_kwargs=ExecuteKwargs(stream=True, input="hello", turn_id="turn"),
        resource_manager=mod.PluginResourceManager(username="alice"),
    )
    return args, task, helper


def test_dispatch_serializes_identity_without_credentials(execution):
    args, task, _ = execution
    mod.dispatch_web_agent(**args)
    payload = task.delay.call_args.args[0]
    assert payload["username"] == "alice"
    assert payload["execute"]["turn_id"] == "turn"
    assert set(payload["resource"]["options"]) == {"username", "model"}


def test_nonstream_returns_celery_result(execution):
    args, task, _ = execution
    args["execute_kwargs"].stream = False
    task.delay.return_value.get.return_value = {"answer": "hello"}
    assert mod.dispatch_web_agent(**args) == {"answer": "hello"}
    task.delay.return_value.get.assert_called_once_with(timeout=300)


def test_attach_does_not_publish(execution):
    args, task, helper = execution
    args["execute_kwargs"].stream_mode = "attach"
    assert mod.dispatch_web_agent(**args) is helper.stream.return_value
    task.delay.assert_not_called()
    assert helper.stream.call_args.kwargs == {"attach_only": True, "expected_run_id": "turn"}


def test_broker_failure_propagates(execution):
    args, task, _ = execution
    task.delay.side_effect = RuntimeError("broker unavailable")
    with pytest.raises(RuntimeError, match="broker unavailable"):
        mod.dispatch_web_agent(**args)


def test_missing_result_backend_rejected(execution):
    args, task, _ = execution
    task.backend = MagicMock(spec=DisabledBackend)
    with pytest.raises(ValueError, match="result backend"):
        mod.dispatch_web_agent(**args)
    task.delay.assert_not_called()


def test_competing_stream_backend_rejected(execution):
    args, task, helper = execution
    helper.message_handler.supports_replay_from_start.return_value = False
    with pytest.raises(ValueError, match="replay backend"):
        mod.dispatch_web_agent(**args)
    task.delay.assert_not_called()


def test_stream_waits_for_current_turn(execution, monkeypatch):
    _, task, helper = execution
    task.ready.return_value = False
    helper.message_handler.replay_belongs_to_run.side_effect = [False, True]
    helper.stream.return_value = iter(["answer"])
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    assert list(mod._stream_task(task, helper, "turn")) == [mod._HEARTBEAT, "answer"]
    assert helper.stream.call_args.kwargs["expected_run_id"] == "turn"


def test_worker_failure_before_first_event_terminates_stream(execution):
    _, task, helper = execution
    helper.message_handler.has_pending_messages.return_value = False
    task.get.side_effect = ValueError("worker initialization failed")
    helper._emit_terminal_error_events.return_value = iter(["error", "finished"])
    assert list(mod._stream_task(task, helper, "turn")) == ["error", "finished"]
    helper.stream.assert_not_called()


def test_queue_wait_is_bounded(execution, settings):
    _, task, helper = execution
    helper.message_handler.has_pending_messages.return_value = False
    task.ready.return_value = False
    settings.AIDEV_WEB_TASK_WAIT_TIMEOUT = 0
    helper._emit_terminal_error_events.return_value = iter(["timeout"])
    assert list(mod._stream_task(task, helper, "turn")) == ["timeout"]
    helper.stream.assert_not_called()


@pytest.mark.parametrize(
    "error_type", [mod.ConsumerPreemptedError, mod.RetryableHeartbeatTimeoutError, mod.StreamCancelledError]
)
def test_handoff_does_not_emit_failure(execution, error_type):
    _, task, helper = execution
    helper.stream.side_effect = error_type("handoff")
    with pytest.raises(error_type):
        list(mod._stream_task(task, helper, "turn"))
    helper._emit_terminal_error_events.assert_not_called()


@pytest.fixture
def worker_payload():
    return {
        "session_code": "session",
        "username": "alice",
        "agent_code": "agent",
        "flow": None,
        "execute": ExecuteKwargs(stream=False, input="hello", turn_id="turn").model_dump(mode="json"),
        "queued_at": time.time(),
        "trace": {},
        "resource": resource_mod.encode_task_resource_manager(mod.PluginResourceManager(username="alice")),
    }


def test_expired_task_does_not_build_agent(worker_payload, monkeypatch):
    worker_payload["queued_at"] -= 1000
    build = MagicMock()
    monkeypatch.setattr(mod, "_build_agent", build)
    with pytest.raises(TimeoutError):
        mod.run_web_agent_task(worker_payload)
    build.assert_not_called()


@pytest.fixture
def worker_logging():
    loggers = [logging.getLogger(), *logging.Logger.manager.loggerDict.values()]
    snapshot = [
        (x, list(x.handlers), x.level, x.propagate, x.disabled) for x in loggers if isinstance(x, logging.Logger)
    ]
    yield
    for logger, handlers, level, propagate, disabled in snapshot:
        logger.handlers, logger.propagate, logger.disabled = handlers, propagate, disabled
        logger.setLevel(level)


@pytest.fixture
def celery_execution(worker_payload, monkeypatch, settings, worker_logging):
    urls = ModuleType("web_execution_test_urls")
    urls.urlpatterns = []
    settings.ROOT_URLCONF = urls
    app = Celery("web-execution-test", broker="memory://", backend="cache+memory://", set_as_current=False)
    app.conf.update(
        broker_connection_retry_on_startup=False, worker_hijack_root_logger=False, worker_redirect_stdouts=False
    )
    monkeypatch.setattr(mod, "_build_agent", lambda *args: MagicMock())
    monkeypatch.setattr(mod, "SessionManager", lambda **kwargs: MagicMock())
    executor = MagicMock()
    monkeypatch.setattr(mod, "AgentExecutor", lambda *args: executor)
    yield app, worker_payload, executor
    app.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("stream", [False, True])
def test_real_celery_runs_agent_and_drains_stream(celery_execution, stream):
    app, payload, executor = celery_execution
    payload["execute"]["stream"] = stream
    executing_threads = []
    consumed = []

    def chunks():
        consumed.append("drained")
        yield "answer"

    def execute(*args, **kwargs):
        executing_threads.append(threading.get_ident())
        return chunks() if stream else {"answer": "hello"}

    executor.execute_with_save.side_effect = execute
    with start_worker(
        app, pool="solo", concurrency=1, perform_ping_check=False, queues=[mod.agent_settings.BKAI_AGENT_TASK]
    ):
        task = app.tasks["aidev_bkplugin.run_web_agent"].delay(payload)
        assert task.get(timeout=10) == (None if stream else {"answer": "hello"})
    assert executing_threads and executing_threads[0] != threading.get_ident()
    assert consumed == (["drained"] if stream else [])


def test_custom_resource_manager_round_trip(monkeypatch):
    monkeypatch.setattr(resource_mod, "_task_codecs", {})
    monkeypatch.setattr(resource_mod, "_task_loaders", {})
    resource_mod.register_task_resource_manager(
        "custom", dict, lambda manager: dict(manager), lambda options: dict(options)
    )
    context = resource_mod.encode_task_resource_manager({"scope": "child-agent"})
    assert resource_mod.decode_task_resource_manager(context) == {"scope": "child-agent"}


def test_default_codec_rejects_request_credentials():
    manager = mod.PluginResourceManager(username="alice")
    manager.access_token = "test-request-token"
    with pytest.raises(ValueError, match="worker-local"):
        resource_mod.encode_task_resource_manager(manager)
