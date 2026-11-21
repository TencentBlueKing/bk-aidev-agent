"""Worker-side Chat reconstruction. No live Agent object crosses the broker."""

import time
from functools import partial
from logging import getLogger

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import SessionsStatus
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.messages_handler.factory import message_handler_factory
from aidev_agent.services.messages_handler.producer import ProducerOnlyRunner, run_producer_inline
from aidev_agent.services.resume_events import uses_resume_event_stream
from aidev_agent.utils.tracing import recording_span, trace_headers
from celery import shared_task
from django.conf import settings
from django.db import close_old_connections

from aidev_bkplugin.services.agent_builder import AgentBuilder, LLMOverrideResourceManager
from aidev_bkplugin.services.agent_execution import AgentExecutor
from aidev_bkplugin.services.background_dispatch import restored_trace_context
from aidev_bkplugin.services.producer.celery import CHAT_TASK_NAME
from aidev_bkplugin.services.producer_dispatch import (
    ChatExecutionSpec,
    send_chat_reply,
    send_started_reply,
)
from aidev_bkplugin.services.producer_resources import ProducerResourceManager

try:
    from opentelemetry.trace import SpanKind
except ImportError:
    SpanKind = None

logger = getLogger(__name__)


def mark_chat_started(spec: ChatExecutionSpec, task_id: str, expires_at: float, thread_id: str, run_id: str) -> None:
    with recording_span("bkplugin.chat.worker.started", use_global_tracer=True):
        send_started_reply(spec, task_id, run_id, expires_at=expires_at)


@shared_task(name=CHAT_TASK_NAME, ignore_result=True, queue=agent_settings.BKAI_AGENT_TASK)
def run_chat_producer(task_id: str, spec: dict, expires_at: float) -> None:
    run_chat(task_id, spec, expires_at, backend="celery")


def _validate_chat_start(spec: ChatExecutionSpec, task_id: str, expires_at: float) -> None:
    if spec.protocol_version != 2:
        raise ValueError("Invalid Chat execution protocol")
    if spec.app_code != agent_settings.APP_CODE:
        raise ValueError("Chat execution belongs to another application")
    if time.time() >= expires_at:
        raise TimeoutError("Chat queue wait expired")
    # Preserve the existing run-scoped signal: a stop for an old run must
    # not cancel a newly queued task. Session-wide stops bind to this task.
    handler = message_handler_factory.get()
    if handler.check_cancel_signal(spec.session_code, run_id=task_id):
        handler.clear_cancel_signal(spec.session_code, run_id=task_id)
        raise RuntimeError("Chat execution cancelled")


def run_chat(task_id: str, spec: dict, expires_at: float, *, backend: str) -> None:
    close_old_connections()
    try:
        execution_spec = ChatExecutionSpec.model_validate(spec)
        with (
            restored_trace_context(execution_spec.trace_context),
            recording_span(
                "worker_run",
                attributes={
                    "bkplugin.chat.task_id": task_id,
                    "bkplugin.chat.producer.backend": backend,
                    "agent.session.code": execution_spec.session_code,
                },
                kind=SpanKind.CONSUMER if SpanKind else None,
                use_global_tracer=True,
            ),
        ):
            try:
                _validate_chat_start(execution_spec, task_id, expires_at)
                result = execute_chat_producer(execution_spec, task_id, expires_at)
                if not execution_spec.execute_kwargs.get("stream", False):
                    send_chat_reply(execution_spec, task_id, kind="result", result=result)
            except Exception as exc:
                send_chat_reply(execution_spec, task_id, kind="error", error=type(exc).__name__)
                raise
    finally:
        close_old_connections()


def execute_chat_producer(spec: ChatExecutionSpec, task_id: str, expires_at: float):
    factory = getattr(settings, "BKAI_CHAT_RESOURCE_MANAGER_FACTORY", LLMOverrideResourceManager)
    resources = factory(username=spec.username, model=spec.model, tenant_id=spec.tenant_id)
    builder = AgentBuilder(
        username=spec.username,
        agent_code=spec.agent_code,
        resource_manager=resources,
        turn_id=spec.turn_id,
        model=spec.model,
        temperature=spec.temperature,
        retry_strategy=spec.retry_strategy,
        reasoning_effort=spec.reasoning_effort,
    )
    try:
        with recording_span("bkplugin.chat.worker.build_agent", use_global_tracer=True):
            agent = builder.by_session_code(spec.session_code, version=spec.version, channel_type=spec.channel_type)
    except Exception:
        # Serialize failure finalization with producers so another active run is not overwritten.
        try:
            handler = message_handler_factory.get()
            if handler.acquire_producer(spec.session_code):
                try:
                    builder.session_manager.update_session_status(spec.session_code, SessionsStatus.FAILED.value)
                finally:
                    handler.release_producer(spec.session_code)
        except Exception:
            logger.exception("Failed to finalize session after Agent build failure")
        raise
    execute_kwargs = ExecuteKwargs.model_validate(spec.execute_kwargs)
    if worker_context := trace_headers():
        execute_kwargs.caller_trace_context = worker_context
    if not execute_kwargs.input and not agent.chat_history:
        raise ValueError("The chat history cannot be empty. Please provide input.")
    # Only an HTTP stream has a separate Web consumer. Synchronous resume
    # consumes its internal AG-UI stream here to aggregate the response.
    runner = (
        ProducerOnlyRunner(partial(mark_chat_started, spec, task_id, expires_at))
        if execute_kwargs.stream
        else run_producer_inline
    )
    agent.resource_manager = ProducerResourceManager(agent.resource_manager, runner)
    execute_kwargs.background_only = True
    executor = AgentExecutor(builder.session_manager)
    if time.time() >= expires_at:
        raise TimeoutError("Chat queue wait expired")
    if not execute_kwargs.stream:
        # The internal stream owns its lock; only plain invoke needs one here.
        if uses_resume_event_stream(agent.resource_manager, execute_kwargs):
            return executor.execute_with_save(agent, execute_kwargs, spec.session_code, turn_id=spec.turn_id)
        handler = message_handler_factory.get()
        if not handler.acquire_producer(spec.session_code):
            raise RuntimeError("A Chat producer is already active")
        try:
            return executor.execute_with_save(agent, execute_kwargs, spec.session_code, turn_id=spec.turn_id)
        finally:
            handler.release_producer(spec.session_code)
    # Prepare constructs the stream. Iteration below triggers the started receipt.
    with recording_span("bkplugin.chat.worker.prepare", use_global_tracer=True):
        event_handler = getattr(agent, "event_handler", None)
        if event_handler and hasattr(event_handler, "set_streaming_started"):
            event_handler.set_streaming_started()
        output = executor.execute_with_save(agent, execute_kwargs, spec.session_code, turn_id=spec.turn_id)
    if execute_kwargs.legacy_streaming:
        helper = GeneratorStreamingHelper(thread_id=spec.session_code, resource_manager=agent.resource_manager)
        output = helper.stream(output, expected_run_id=task_id)
    for _ in output:
        pass
    return None
