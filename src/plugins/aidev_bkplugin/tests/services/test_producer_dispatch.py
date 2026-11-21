import json
import time
from unittest.mock import ANY, Mock

import pytest
from aidev_agent.enums import SessionsStatus
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.messages_handler.producer import ProducerOnlyRunner
from aidev_agent.services.messages_handler.rabbitmq_stream import StreamReadError
from aidev_agent.utils import tracing
from aidev_bkplugin.services import producer_dispatch
from aidev_bkplugin.services.chat_tasks import execute_chat_producer, mark_chat_started, run_chat_producer
from aidev_bkplugin.services.producer import celery
from aidev_bkplugin.services.producer_dispatch import ChatDispatcher, ChatExecutionSpec
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from rstream.client import BrokerResolutionMaxRetryError
from rstream.connection import ConnectionClosed


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
def handler(monkeypatch):
    backend = Mock()
    backend.check_cancel_signal.return_value = False
    backend.acquire_producer.return_value = True
    monkeypatch.setattr(producer_dispatch.message_handler_factory, "get", Mock(return_value=backend))
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.close_old_connections", Mock())
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.agent_settings.APP_CODE", "test-app")
    return backend


@pytest.fixture
def worker_executor(monkeypatch, settings):
    settings.BKAI_CHAT_RESOURCE_MANAGER_FACTORY = Mock()
    builder = Mock()
    builder.by_session_code.return_value.resource_manager.event_publishing_enabled.return_value = False
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.AgentBuilder", Mock(return_value=builder))
    executor = Mock()
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.AgentExecutor", Mock(return_value=executor))
    return executor


def test_submission_has_queue_expiry_and_no_database(spec, monkeypatch):
    monkeypatch.setenv("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", "0")
    sender = Mock()
    monkeypatch.setattr(celery.current_app, "send_task", sender)
    task_id = ChatDispatcher(spec)._submit(spec)
    payload = sender.call_args.kwargs
    assert payload["queue"] == "bkai_agent_task"
    assert payload["task_id"] == task_id
    assert payload["kwargs"]["spec"]["tenant_id"] == "test-tenant"
    assert payload["kwargs"]["expires_at"] > time.time()


def test_publish_failure_reaches_web(spec, monkeypatch):
    monkeypatch.setenv("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", "0")
    monkeypatch.setattr(celery.current_app, "send_task", Mock(side_effect=RuntimeError("broker unavailable")))
    with pytest.raises(RuntimeError, match="broker unavailable"):
        ChatDispatcher(spec)._submit(spec)


def test_worker_spans_continue_from_enqueue_span(spec, handler, worker_executor, monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(tracing.trace, "get_tracer", lambda _: tracer)
    sender = Mock()
    monkeypatch.setenv("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", "0")
    monkeypatch.setattr(celery.current_app, "send_task", sender)
    spec.execute_kwargs = {"stream": False}
    worker_executor.execute_with_save = Mock(return_value={"answer": "done"})

    with tracer.start_as_current_span("request") as request:
        spec.execute_kwargs["caller_trace_context"] = tracing.trace_headers()
        ChatDispatcher(spec)._submit(spec)
    reply_contexts = []
    handler.put.side_effect = lambda *_: reply_contexts.append(tracing.trace.get_current_span().get_span_context())
    run_chat_producer(**sender.call_args.kwargs["kwargs"])

    spans = {span.name: span for span in exporter.get_finished_spans()}
    enqueue, worker = spans["bkplugin.chat.enqueue"], spans["bkplugin.chat.worker"]
    for span in (spans["request"], enqueue, spans["bkplugin.chat.producer.dispatch"], worker):
        assert span.attributes["producer_backend"] == "celery"
    agent_context = worker_executor.execute_with_save.call_args.args[1].caller_trace_context
    assert agent_context["traceparent"].split("-")[2] == format(worker.context.span_id, "016x")
    assert enqueue.parent.span_id == request.get_span_context().span_id
    assert enqueue.kind == SpanKind.PRODUCER
    assert reply_contexts == [worker.context]
    assert worker.kind == SpanKind.CONSUMER
    assert worker.context.trace_id == enqueue.context.trace_id
    assert worker.parent.span_id == enqueue.context.span_id
    assert spans["bkplugin.chat.worker.build_agent"].parent.span_id == worker.context.span_id
    payload = sender.call_args.kwargs["kwargs"]
    with pytest.raises(TimeoutError):
        run_chat_producer(**{**payload, "expires_at": time.time() - 1})
    expired = exporter.get_finished_spans()[-1]
    assert expired.name == "bkplugin.chat.worker"
    assert expired.parent.span_id == enqueue.context.span_id
    assert expired.status.status_code == StatusCode.ERROR
    assert reply_contexts[-1] == expired.context
    provider.shutdown()


def test_reply_channel_isolated_by_tenant_and_task(spec):
    other = spec.model_copy(update={"tenant_id": "another-tenant"})
    assert len({spec.reply_channel("one"), spec.reply_channel("two"), other.reply_channel("one")}) == 3


def test_expired_task_never_executes(spec, handler, monkeypatch):
    execute = Mock()
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.execute_chat_producer", execute)
    with pytest.raises(TimeoutError):
        run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() - 1)
    execute.assert_not_called()
    handler.put.assert_called_with(spec.reply_channel("task-id"), {"kind": "error", "error": "TimeoutError"})


def test_queued_stop_uses_existing_signal(spec, handler, monkeypatch):
    handler.check_cancel_signal.return_value = True
    execute = Mock()
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.execute_chat_producer", execute)
    with pytest.raises(RuntimeError, match="cancelled"):
        run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() + 30)
    execute.assert_not_called()
    handler.check_cancel_signal.assert_called_once_with(spec.session_code, run_id="task-id")
    handler.clear_cancel_signal.assert_called_once_with(spec.session_code, run_id="task-id")


@pytest.mark.parametrize("error", [None, ValueError("private upstream detail")])
def test_sync_uses_producer_lock_and_reply_backend(spec, handler, worker_executor, error):
    spec.execute_kwargs = {"stream": False}
    worker_executor.execute_with_save = Mock(return_value={"answer": "done"}, side_effect=error)
    if error:
        with pytest.raises(ValueError):
            run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() + 30)
        expected = {"kind": "error", "error": "ValueError"}
    else:
        run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() + 30)
        expected = {"kind": "result", "result": {"answer": "done"}}
    handler.acquire_producer.assert_called_once_with(spec.session_code)
    handler.release_producer.assert_called_once_with(spec.session_code)
    handler.put.assert_called_once_with(spec.reply_channel("task-id"), expected)
    handler.flush.assert_called_once_with(spec.reply_channel("task-id"))
    handler.mark_completed.assert_not_called()


def test_sync_lock_conflict_does_not_execute_or_release_other_owner(spec, handler, worker_executor):
    spec.execute_kwargs = {"stream": False}
    handler.acquire_producer.return_value = False
    with pytest.raises(RuntimeError, match="already active"):
        run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() + 30)
    worker_executor.execute_with_save.assert_not_called()
    handler.release_producer.assert_not_called()


def test_started_receipt_contains_actual_run_id(spec, handler):
    mark_chat_started(spec, "task-id", time.time() + 30, spec.session_code, "actual-run")
    handler.put.assert_called_once_with(spec.reply_channel("task-id"), {"kind": "started", "run_id": "actual-run"})


def test_startup_error_supersedes_buffered_started_in_same_batch(spec, handler):
    handler.get_messages_since.return_value = (
        [{"kind": "started", "run_id": "run"}, {"kind": "error", "error": "TimeoutError"}],
        2,
    )
    with pytest.raises(RuntimeError, match="TimeoutError"):
        ChatDispatcher._wait_reply(spec.reply_channel("task"), handler, expected_kind="started", timeout=10)
    handler.mark_completed.assert_called_once_with(spec.reply_channel("task"))


def test_started_after_expiry_does_not_publish_ready(spec, handler):
    with pytest.raises(TimeoutError):
        mark_chat_started(spec, "task-id", time.time() - 1, spec.session_code, "actual-run")
    handler.put.assert_not_called()


def test_wait_ignores_poll_timeout_and_returns_result(spec, handler):
    handler.get_messages_since.side_effect = [TimeoutError(), ([{"kind": "result", "result": "done"}], 1)]
    assert (
        ChatDispatcher._wait_reply(spec.reply_channel("task-id"), handler, expected_kind="result", timeout=30)["result"]
        == "done"
    )
    handler.mark_completed.assert_called_once_with(spec.reply_channel("task-id"))


def test_worker_error_during_startup_reaches_web(spec, handler):
    handler.get_messages_since.return_value = ([{"kind": "error", "error": "ValueError"}], 1)
    with pytest.raises(RuntimeError, match="ValueError"):
        ChatDispatcher._wait_reply(spec.reply_channel("task-id"), handler, expected_kind="started", timeout=30)


def test_wait_has_bounded_timeout(spec, handler):
    with pytest.raises(TimeoutError):
        ChatDispatcher._wait_reply(spec.reply_channel("task-id"), handler, expected_kind="started", timeout=0)
    handler.get_messages_since.assert_not_called()


def test_attach_never_submits(spec, handler, monkeypatch):
    sender = Mock()
    monkeypatch.setattr(celery.current_app, "send_task", sender)
    consume = Mock(return_value=iter(["replay"]))
    monkeypatch.setattr(ChatDispatcher, "_consume", consume)
    result = ChatDispatcher(spec).execute(ExecuteKwargs(stream=True, stream_mode="attach"))
    assert list(result) == ["replay"]
    sender.assert_not_called()


def test_stream_attaches_only_after_actual_run_receipt(spec, handler, monkeypatch):
    handler.get_messages_since.side_effect = [TimeoutError(), ([{"kind": "started", "run_id": "worker-run"}], 1)]
    helper = Mock()
    helper.stream.return_value = iter(["live-event"])
    monkeypatch.setattr(producer_dispatch, "GeneratorStreamingHelper", Mock(return_value=helper))
    chunks = list(ChatDispatcher(spec)._consume(spec, handler, "task-id"))
    assert json.loads(chunks[0][6:])["event"] == {"type": "heartbeat", "message": "waiting for worker"}
    assert chunks[1:] == ["live-event"]
    assert helper.stream.call_args.kwargs == {
        "expected_run_id": "worker-run",
        "attach_only": True,
        "before_first_chunk": ANY,
    }


@pytest.mark.parametrize("task_id", ["task-id", None])
def test_waiting_heartbeat_until_first_chunk(spec, handler, monkeypatch, task_id):
    clock = 0.0
    monkeypatch.setattr(time, "monotonic", lambda: clock)
    handler.is_stopped.return_value = False
    handler.acquire_consumer.return_value = "consumer"
    handler.CONSUMER_HEARTBEAT_TIMEOUT = 60
    handler.has_pending_messages.side_effect = lambda _: clock >= 7
    handler.has_active_producer.side_effect = lambda _: clock >= 7

    def advance(seconds):
        nonlocal clock
        clock = round(clock + seconds, 2)

    def poll(channel, offset, timeout):
        advance(timeout)
        if channel != spec.session_code and clock >= 7:
            return [{"kind": "started", "run_id": "worker-run"}], 1
        if channel == spec.session_code and clock >= (12 if offset == 0 else 20):
            return [f"chunk-{offset}"], offset + 1
        raise TimeoutError

    monkeypatch.setattr(time, "sleep", advance)
    handler.get_messages_since.side_effect = poll
    stream = ChatDispatcher(spec)._consume(spec, handler, task_id)
    heartbeat = next(stream)
    assert [(next(stream), clock) for _ in range(4)] == [
        (heartbeat, 5),
        (heartbeat, 10),
        ("chunk-0", 12),
        ("chunk-1", 20),
    ]
    stream.close()


def test_replayed_delivery_is_not_persistent_deduplication(spec, handler, monkeypatch):
    spec.execute_kwargs = {"stream": False}
    execute = Mock(return_value="done")
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.execute_chat_producer", execute)
    for _ in range(2):
        run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() + 30)
    assert execute.call_count == 2
    handler.acquire_producer.assert_not_called()


def test_worker_rebuilds_identity_options_and_producer_only(spec, monkeypatch, settings):
    factory = Mock()
    settings.BKAI_CHAT_RESOURCE_MANAGER_FACTORY = factory
    builder = Mock()
    builder_cls = Mock(return_value=builder)
    executor = Mock()
    executor.execute_with_save.return_value = iter(())
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.AgentBuilder", builder_cls)
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.AgentExecutor", Mock(return_value=executor))
    spec.model = "selected-model"
    spec.version = "v1"
    spec.temperature = 0.2
    execute_chat_producer(spec, "task-id", time.time() + 30)
    factory.assert_called_once_with(username="alice", model="selected-model", tenant_id="test-tenant")
    assert builder_cls.call_args.kwargs["temperature"] == 0.2
    builder.by_session_code.assert_called_once_with("test-session", version="v1", channel_type=None)
    agent = builder.by_session_code.return_value
    assert isinstance(agent.resource_manager.get_producer_runner(), ProducerOnlyRunner)
    assert executor.execute_with_save.call_args.args[1].background_only is True


def test_sse_headers_can_flush_before_worker_receipt(spec, handler):
    stream = ChatDispatcher(spec)._consume(spec, handler, "task-id")
    chunk = next(stream)
    assert chunk.startswith("data: ") and chunk.endswith("\n\n")
    assert json.loads(chunk[6:]) == {"type": "RAW", "event": {"type": "heartbeat", "message": "waiting for worker"}}
    handler.get_messages_since.assert_not_called()
    stream.close()


def test_startup_failure_is_encoded_as_sse(spec, handler):
    handler.get_messages_since.return_value = ([{"kind": "error", "error": "ValueError"}], 1)
    chunks = list(ChatDispatcher(spec)._consume(spec, handler, "task-id"))
    events = [json.loads(chunk[6:]) for chunk in chunks if chunk.startswith("data: ")]
    assert [event["type"] for event in events] == ["RAW", "RUN_ERROR", "RUN_FINISHED"]
    assert events[-1]["type"] == "RUN_FINISHED"


@pytest.mark.parametrize(
    "failure", [ConnectionResetError, ConnectionClosed, BrokerResolutionMaxRetryError, TimeoutError]
)
def test_receipt_reader_transport_failure_ends_sse_and_continues_enqueue_trace(spec, handler, monkeypatch, failure):
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(tracing.trace, "get_tracer", provider.get_tracer)
    with tracer.start_as_current_span("bkplugin.chat.enqueue") as enqueue:
        spec.trace_context = tracing.trace_headers()

    handler.get_messages_since.side_effect = StreamReadError(failure("broker details"))
    chunks = list(ChatDispatcher(spec)._consume(spec, handler, "task-id"))
    events = [json.loads(chunk[6:]) for chunk in chunks]
    assert [event["type"] for event in events] == ["RAW", "RUN_ERROR", "RUN_FINISHED"]
    assert events[1]["message"] == failure.__name__
    _, receipt = exporter.get_finished_spans()
    assert receipt.name == "bkplugin.chat.web.startup_receipt"
    assert receipt.parent.span_id == enqueue.get_span_context().span_id
    assert receipt.context.trace_id == enqueue.get_span_context().trace_id
    assert receipt.status.status_code == StatusCode.ERROR
    assert receipt.attributes["receipt"] == "error"
    assert receipt.attributes["error_type"] == failure.__name__
    handler.mark_completed.assert_not_called()
    provider.shutdown()


def test_worker_keeps_session_history_instead_of_overwriting(spec, monkeypatch, settings):
    settings.BKAI_CHAT_RESOURCE_MANAGER_FACTORY = Mock()
    history = [{"role": "assistant", "content": "persisted interrupt"}]
    agent = Mock(chat_history=history)
    builder = Mock()
    builder.by_session_code.return_value = agent
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.AgentBuilder", Mock(return_value=builder))
    executor = Mock()
    executor.execute_with_save.return_value = iter(())
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.AgentExecutor", Mock(return_value=executor))
    execute_chat_producer(spec, "task-id", time.time() + 30)
    builder.by_session_code.assert_called_once()
    assert agent.chat_history is history
    assert executor.execute_with_save.call_args.args[0] is agent


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("lock_available,write_fails", [(True, False), (True, True), (False, False)])
def test_build_failure_finalizes_session_without_overwriting_active_run(
    spec, handler, monkeypatch, settings, stream, lock_available, write_fails
):
    spec.execute_kwargs = {"stream": stream}
    builder = Mock()
    failure = ValueError("build failed")
    builder.by_session_code.side_effect = failure
    if write_fails:
        builder.session_manager.update_session_status.side_effect = RuntimeError("status unavailable")
    settings.BKAI_CHAT_RESOURCE_MANAGER_FACTORY = Mock()
    monkeypatch.setattr("aidev_bkplugin.services.chat_tasks.AgentBuilder", Mock(return_value=builder))
    handler.acquire_producer.return_value = lock_available
    with pytest.raises(ValueError) as caught:
        run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() + 30)
    assert caught.value is failure
    handler.acquire_producer.assert_called_once_with(spec.session_code)
    if lock_available:
        builder.session_manager.update_session_status.assert_called_once_with(
            spec.session_code, SessionsStatus.FAILED.value
        )
        handler.release_producer.assert_called_once_with(spec.session_code)
    else:
        builder.session_manager.update_session_status.assert_not_called()
        handler.release_producer.assert_not_called()
    handler.put.assert_called_once_with(spec.reply_channel("task-id"), {"kind": "error", "error": "ValueError"})
