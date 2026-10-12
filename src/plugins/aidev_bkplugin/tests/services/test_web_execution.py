"""Queue admission and worker ownership tests without external service calls."""

import logging
import threading
import time
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.messages_handler.producer_execution import get_producer_started
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
from aidev_agent.utils.event import emit_run_finished_event
from aidev_bkplugin.models import WebAgentTask
from aidev_bkplugin.services import plugin_resource_manager as resource_mod
from aidev_bkplugin.services import web_execution as mod
from celery import Celery
from celery.contrib.testing.worker import start_worker


@pytest.fixture
def execution(monkeypatch):
    helper = MagicMock()
    monkeypatch.setattr(mod, "GeneratorStreamingHelper", lambda **kwargs: helper)
    publish = MagicMock()
    monkeypatch.setattr(mod.run_web_agent_task, "delay", publish)
    args = dict(
        session_code="session",
        username="alice",
        channel_type="popup",
        execute_kwargs=ExecuteKwargs(stream=True, input="hello", turn_id="turn"),
        resource_manager=mod.PluginResourceManager(username="alice"),
    )
    return args, publish, helper


@pytest.mark.django_db(transaction=True)
class TestWebExecution:
    def test_duplicate_request_publishes_once(self, execution):
        args, publish, _ = execution
        mod.dispatch_web_agent(**args)
        mod.dispatch_web_agent(**args)
        assert publish.call_count == 1
        assert WebAgentTask.objects.count() == 1
        payload = publish.call_args.args[2]
        assert payload["username"] == "alice"
        assert payload["execute"]["turn_id"] == "turn"
        assert set(payload["resource"]["options"]) == {"username", "model"}

    def test_active_session_rejects_another_turn(self, execution):
        args, publish, _ = execution
        mod.dispatch_web_agent(**args)
        args["execute_kwargs"].turn_id = "another-turn"
        with pytest.raises(ValueError, match="already queued"):
            mod.dispatch_web_agent(**args)
        assert publish.call_count == 1

    def test_publish_failure_is_recorded(self, execution):
        args, publish, _ = execution
        publish.side_effect = RuntimeError("broker unavailable")
        with pytest.raises(RuntimeError, match="broker unavailable"):
            mod.dispatch_web_agent(**args)
        assert WebAgentTask.objects.get().status == "failed"

    def test_queue_timeout_prevents_late_execution(self, execution, settings):
        args, publish, _ = execution
        mod.dispatch_web_agent(**args)
        key, task_id, payload = publish.call_args.args
        settings.AIDEV_WEB_TASK_WAIT_TIMEOUT = 0
        with pytest.raises(TimeoutError):
            list(mod._wait_task(key, task_id, streaming=True))
        mod.run_web_agent_task(key, task_id, payload)
        assert WebAgentTask.objects.get().status == "failed"

    def test_worker_claims_once_and_holds_producer_context(self, execution, monkeypatch):
        args, publish, _ = execution
        mod.dispatch_web_agent(**args)
        key, task_id, payload = publish.call_args.args
        agent = MagicMock()
        monkeypatch.setattr(mod, "_build_agent", lambda *args: agent)
        manager = MagicMock()
        monkeypatch.setattr(mod, "SessionManager", lambda **kwargs: manager)
        executor = MagicMock()
        calls = []

        def produce(*args, **kwargs):
            calls.append(get_producer_started("session"))
            calls[-1]()
            assert WebAgentTask.objects.get().status == "streaming"
            yield from ()

        executor.execute_with_save.side_effect = produce
        monkeypatch.setattr(mod, "AgentExecutor", lambda *args: executor)
        mod.run_web_agent_task(key, task_id, payload)
        mod.run_web_agent_task(key, task_id, payload)
        assert len(calls) == 1
        assert WebAgentTask.objects.get().status == "finished"
        assert get_producer_started("session") is None

    def test_expired_delivery_never_builds_agent(self, execution, monkeypatch):
        args, publish, _ = execution
        mod.dispatch_web_agent(**args)
        key, task_id, payload = publish.call_args.args
        payload["queued_at"] = time.time() - 1000
        build = MagicMock()
        monkeypatch.setattr(mod, "_build_agent", build)
        with pytest.raises(TimeoutError):
            mod.run_web_agent_task(key, task_id, payload)
        build.assert_not_called()
        assert WebAgentTask.objects.get().status == "failed"


@pytest.fixture
def worker_logging():
    loggers = [logging.getLogger(), *logging.Logger.manager.loggerDict.values()]
    snapshot = [
        (logger, list(logger.handlers), logger.level, logger.propagate, logger.disabled)
        for logger in loggers
        if isinstance(logger, logging.Logger)
    ]
    yield
    for logger, handlers, level, propagate, disabled in snapshot:
        logger.handlers, logger.propagate, logger.disabled = handlers, propagate, disabled
        logger.setLevel(level)


@pytest.fixture
def celery_execution(execution, monkeypatch, settings, worker_logging):
    urls = ModuleType("web_execution_test_urls")
    urls.urlpatterns = []
    settings.ROOT_URLCONF = urls
    settings.AIDEV_WEB_TASK_WAIT_TIMEOUT = 10
    args, publish, _ = execution
    mod.dispatch_web_agent(**args)
    app = Celery("web-execution-test", broker="memory://", backend="cache+memory://", set_as_current=False)
    app.conf.update(
        task_default_queue="bkai_agent_task",
        broker_connection_retry_on_startup=False,
        worker_hijack_root_logger=False,
        worker_redirect_stdouts=False,
    )
    monkeypatch.setattr(mod, "_build_agent", lambda *args: MagicMock())
    monkeypatch.setattr(mod, "SessionManager", lambda **kwargs: MagicMock())
    helper = GeneratorStreamingHelper(thread_id="session")
    helper._schedule_session_cleanup = MagicMock()
    executing_threads = []

    def source():
        executing_threads.append(threading.get_ident())
        yield 'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"message","delta":"hello"}\n\n'
        yield emit_run_finished_event(thread_id="session", run_id="run")

    executor = MagicMock()
    executor.execute_with_save.side_effect = lambda *a, **kw: helper.stream(source(), expected_run_id="run")
    monkeypatch.setattr(mod, "AgentExecutor", lambda *args: executor)
    yield app, publish.call_args.args, helper, executing_threads
    app.close()


@pytest.mark.django_db(transaction=True)
def test_real_celery_delivery_publishes_stream_in_worker_slot(celery_execution):
    app, arguments, helper, executing_threads = celery_execution
    with start_worker(app, pool="solo", concurrency=1, perform_ping_check=False, queues=["bkai_agent_task"]):
        app.tasks["aidev_bkplugin.run_web_agent"].delay(*arguments)
        chunks = list(mod._stream_task(arguments[0], arguments[1], helper))
    assert any('"delta":"hello"' in chunk for chunk in chunks)
    assert executing_threads and executing_threads[0] != threading.get_ident()
    assert WebAgentTask.objects.get().status == "finished"


def test_custom_resource_manager_round_trip(monkeypatch):
    monkeypatch.setattr(resource_mod, "_task_codecs", {})
    monkeypatch.setattr(resource_mod, "_task_loaders", {})
    resource_mod.register_task_resource_manager(
        "custom", dict, lambda manager: {"scope": manager["scope"]}, lambda options: dict(options)
    )
    context = resource_mod.encode_task_resource_manager({"scope": "child-agent"})
    assert resource_mod.decode_task_resource_manager(context) == {"scope": "child-agent"}


def test_default_codec_rejects_request_credentials():
    manager = mod.PluginResourceManager(username="alice")
    manager.access_token = "test-request-token"
    with pytest.raises(ValueError, match="worker-local"):
        resource_mod.encode_task_resource_manager(manager)


@pytest.mark.django_db(transaction=True)
def test_nonstream_worker_keeps_response_payload(execution, monkeypatch):
    args, publish, _ = execution
    mod.dispatch_web_agent(**args)
    key, task_id, payload = publish.call_args.args
    payload["execute"]["stream"] = False
    monkeypatch.setattr(mod, "_build_agent", lambda *args: MagicMock())
    monkeypatch.setattr(mod, "SessionManager", lambda **kwargs: MagicMock())
    executor = MagicMock()
    executor.execute_with_save.return_value = {"choices": [{"delta": {"content": "answer"}}]}
    monkeypatch.setattr(mod, "AgentExecutor", lambda *args: executor)
    mod.run_web_agent_task(key, task_id, payload)
    assert WebAgentTask.objects.get().result == executor.execute_with_save.return_value
    assert list(mod._wait_task(key, task_id, streaming=False)) == []


@pytest.mark.parametrize(
    "error_type", [mod.ConsumerPreemptedError, mod.RetryableHeartbeatTimeoutError, mod.StreamCancelledError]
)
def test_consumer_handoff_does_not_emit_terminal_failure(monkeypatch, error_type):
    monkeypatch.setattr(mod, "_wait_task", lambda *args, **kwargs: iter(()))
    helper = MagicMock()
    helper.stream.side_effect = error_type("handoff")
    with pytest.raises(error_type):
        list(mod._stream_task("key", "task", helper))
    helper._emit_terminal_error_events.assert_not_called()
