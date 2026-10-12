"""Celery owns Web agent execution; HTTP only waits or reads shared events."""

import hashlib
import json
import logging
import time
import uuid
from contextlib import nullcontext
from functools import partial

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentBuildType, AgentType, SessionsStatus
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.messages_handler import (
    ConsumerPreemptedError,
    RetryableHeartbeatTimeoutError,
    StreamCancelledError,
)
from aidev_agent.services.messages_handler.in_memory import InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.producer_execution import worker_producer
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
from aidev_agent.utils.tracing import propagated_trace_context, trace_headers
from celery import shared_task
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from aidev_bkplugin.models import WebAgentTask
from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_execution import AgentExecutor
from aidev_bkplugin.services.agent_helpers import AgentHelper
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_bkplugin.services.plugin_resource_manager import (
    PluginResourceManager,
    decode_task_resource_manager,
    encode_task_resource_manager,
)

logger = logging.getLogger(__name__)
_ACTIVE = ("queued", "running", "streaming")
_HEARTBEAT = 'data: {"type":"RAW","event":{"type":"heartbeat"}}\n\n'


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _update_task(key: str, task_id: str, **values) -> None:
    WebAgentTask.objects.filter(key=key, task_id=task_id).update(updated_at=timezone.now(), **values)


def _build_agent(payload: dict, manager: PluginResourceManager):
    session_code = payload["session_code"]
    turn_id = payload["execute"]["turn_id"]
    if payload["flow"] is not None:
        return AgentInstanceFactory.build_agent(
            agent_type=AgentType.FLOW,
            build_type=AgentBuildType.DIRECT,
            session_code=session_code,
            session_context_data=[],
            username=payload["username"],
            event_handler=AGUISessionWriter(
                session_code=session_code,
                client=AgentHelper.get_client(resource_manager=manager),
                username=payload["username"],
                turn_id=turn_id,
                task_id=str(payload["flow"].get("task_id") or ""),
            ),
            flow_resource_manager=manager,
            **payload["flow"],
        )
    return AgentBuilder(
        username=payload["username"],
        agent_code=payload["agent_code"],
        resource_manager=manager,
        turn_id=turn_id,
        model=payload["model"],
    ).by_session_code(session_code, version=payload["execute"].get("version"), channel_type=payload["channel_type"])


@shared_task(name="aidev_bkplugin.run_web_agent", queue=agent_settings.BKAI_AGENT_TASK, ignore_result=True)
def run_web_agent_task(key: str, task_id: str, payload: dict) -> None:
    """CAS prevents duplicate deliveries from executing tools twice; never auto-retry."""
    close_old_connections()
    claimed = WebAgentTask.objects.filter(key=key, task_id=task_id, status="queued").update(
        status="running", updated_at=timezone.now()
    )
    if not claimed:
        return
    session_manager = None
    try:
        if time.time() - payload["queued_at"] > float(getattr(settings, "AIDEV_WEB_TASK_WAIT_TIMEOUT", 300)):
            raise TimeoutError("Web agent task expired before worker execution")
        with propagated_trace_context(payload["trace"]):
            manager = decode_task_resource_manager(payload["resource"])
            session_manager = SessionManager(
                username=payload["username"], agent_code=payload["agent_code"], resource_manager=manager
            )
            agent = _build_agent(payload, manager)
            execute_kwargs = ExecuteKwargs.model_validate(payload["execute"])
            execute_kwargs.background_only = True
            if not execute_kwargs.input and payload["flow"] is None and not agent.chat_history:
                raise ValueError("The chat history cannot be empty. Please provide input.")
            handler = getattr(agent, "event_handler", None)
            if handler and hasattr(handler, "set_streaming_started"):
                handler.set_streaming_started()
            started = partial(_update_task, key, task_id, status="streaming")
            # No producer thread escapes the Celery execution slot. The existing
            # heartbeat/transport helpers remain independent of model execution.
            with worker_producer(payload["session_code"], started) if execute_kwargs.stream else nullcontext():
                result = AgentExecutor(session_manager).execute_with_save(
                    agent, execute_kwargs, payload["session_code"], turn_id=execute_kwargs.turn_id
                )
                if execute_kwargs.stream:
                    if execute_kwargs.legacy_streaming:
                        result = GeneratorStreamingHelper(
                            thread_id=payload["session_code"],
                            defer_cleanup_on_complete=True,
                        ).stream(result, expected_run_id=execute_kwargs.turn_id)
                    for _ in result:
                        pass
                    result = None
            _update_task(key, task_id, status="finished", result=result)
    except Exception:
        logger.exception("Web agent worker failed: task_id=%s", task_id)
        _update_task(key, task_id, status="failed", error="Agent worker failed; check worker logs with the task ID.")
        if session_manager is not None:
            session_manager.update_session_status(payload["session_code"], SessionsStatus.FAILED.value)
        raise
    finally:
        close_old_connections()


def dispatch_web_agent(
    *,
    session_code: str,
    username: str,
    execute_kwargs: ExecuteKwargs,
    resource_manager: PluginResourceManager,
    channel_type: str,
    model: str = "",
    flow: dict | None = None,
):
    resource_context = encode_task_resource_manager(resource_manager)
    helper = GeneratorStreamingHelper(thread_id=session_code)
    if isinstance(helper.message_handler, InMemoryQueueMessageHandler):
        raise ValueError("Web Celery execution requires a shared Redis or RabbitMQ message handler")
    key = _digest([resource_manager.get_agent_code(), session_code])
    if execute_kwargs.stream_mode == "attach":
        current = WebAgentTask.objects.filter(key=key, status__in=_ACTIVE).first()
        if current is not None:
            return _stream_task(key, current.task_id, helper)
        return helper.stream(iter(()), attach_only=True)
    execute = execute_kwargs.model_dump(mode="json")
    payload = {
        "session_code": session_code,
        "username": username,
        "execute": execute,
        "agent_code": resource_manager.get_agent_code(),
        "channel_type": channel_type,
        "model": model,
        "flow": flow,
        "trace": trace_headers(),
        "queued_at": time.time(),
        "resource": resource_context,
    }
    key = _digest([payload["agent_code"], session_code])
    request_key = _digest([username, execute, model, flow, channel_type])
    # Materialize the queue payload before committing a queued state.
    json.dumps(payload)
    with transaction.atomic():
        task, created = WebAgentTask.objects.get_or_create(
            key=key, defaults={"task_id": uuid.uuid4().hex, "request_key": request_key}
        )
        task = WebAgentTask.objects.select_for_update().get(key=key)
        if not created and task.status in _ACTIVE and task.request_key != request_key:
            raise ValueError("An agent task is already queued or running for this session")
        publish = created or task.request_key != request_key
        if publish and not created:
            task.task_id, task.request_key = uuid.uuid4().hex, request_key
            task.status, task.result, task.error = "queued", None, ""
            task.save()
        if publish:
            transaction.on_commit(partial(_publish, key, task.task_id, payload))
    if execute_kwargs.stream:
        return _stream_task(key, task.task_id, helper)
    for _ in _wait_task(key, task.task_id, streaming=False):
        pass
    return WebAgentTask.objects.get(key=key, task_id=task.task_id).result


def _publish(key: str, task_id: str, payload: dict) -> None:
    try:
        run_web_agent_task.delay(key, task_id, payload)
    except Exception:
        _update_task(key, task_id, status="failed", error="Could not submit agent task to Celery.")
        raise


def _wait_task(key: str, task_id: str, *, streaming: bool):
    deadline = time.monotonic() + float(getattr(settings, "AIDEV_WEB_TASK_WAIT_TIMEOUT", 300))
    while True:
        task = WebAgentTask.objects.get(key=key)
        if task.task_id != task_id:
            raise RuntimeError("The session has moved to another execution")
        if task.status == "failed":
            raise RuntimeError(f"{task.error} Task: {task_id}")
        if task.status == "finished" or (streaming and task.status == "streaming"):
            return
        if time.monotonic() >= deadline:
            WebAgentTask.objects.filter(key=key, task_id=task_id, status="queued").update(
                status="failed", error="Timed out waiting for a Celery worker", updated_at=timezone.now()
            )
            raise TimeoutError("Timed out waiting for the agent worker; reconnect to check the current execution")
        yield _HEARTBEAT
        time.sleep(1)


def _stream_task(key: str, task_id: str, helper: GeneratorStreamingHelper):
    try:
        yield from _wait_task(key, task_id, streaming=True)
        yield from helper.stream(iter(()), attach_only=True)
    except (ConsumerPreemptedError, RetryableHeartbeatTimeoutError, StreamCancelledError):
        raise
    except Exception as exc:
        logger.exception("Web agent stream failed: task_id=%s", task_id)
        yield from helper._emit_terminal_error_events(str(exc))
