"""Dispatch Web execution to Celery and replay the existing shared event stream."""

import json
import logging
import time

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
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
from aidev_agent.utils.tracing import propagated_trace_context, trace_headers
from celery import shared_task
from celery.backends.base import DisabledBackend
from django.conf import settings
from django.db import close_old_connections

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
_HEARTBEAT = 'data: {"type":"RAW","event":{"type":"heartbeat"}}\n\n'


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


@shared_task(name="aidev_bkplugin.run_web_agent", queue=agent_settings.BKAI_AGENT_TASK, ignore_result=False)
def run_web_agent_task(payload: dict):
    """Reuse SDK execution inside the worker; do not retry side-effecting tools."""
    close_old_connections()
    session_manager = None
    try:
        if time.time() - payload["queued_at"] > _wait_timeout():
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
            if execute_kwargs.stream and handler and hasattr(handler, "set_streaming_started"):
                handler.set_streaming_started()
            result = AgentExecutor(session_manager).execute_with_save(
                agent, execute_kwargs, payload["session_code"], turn_id=execute_kwargs.turn_id
            )
            if execute_kwargs.stream:
                if execute_kwargs.legacy_streaming:
                    result = GeneratorStreamingHelper(
                        thread_id=payload["session_code"], defer_cleanup_on_complete=True
                    ).stream(result, expected_run_id=execute_kwargs.turn_id)
                for _ in result:
                    pass
                return None
            return result
    except Exception:
        logger.exception("Web agent worker failed: session_code=%s", payload["session_code"])
        if session_manager is not None:
            session_manager.update_session_status(payload["session_code"], SessionsStatus.FAILED.value)
        raise
    finally:
        close_old_connections()


def _wait_timeout() -> float:
    return float(getattr(settings, "AIDEV_WEB_TASK_WAIT_TIMEOUT", 300))


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
    helper = GeneratorStreamingHelper(thread_id=session_code, defer_cleanup_on_complete=True)
    if execute_kwargs.stream and not helper.message_handler.supports_replay_from_start():
        raise ValueError("Web Celery streaming requires a shared Redis or RabbitMQ replay backend")
    if execute_kwargs.stream_mode == "attach":
        return helper.stream(iter(()), attach_only=True, expected_run_id=execute_kwargs.turn_id)
    if isinstance(run_web_agent_task.backend, DisabledBackend):
        raise ValueError("Web Celery execution requires a configured Celery result backend")
    payload = {
        "session_code": session_code,
        "username": username,
        "execute": execute_kwargs.model_dump(mode="json"),
        "agent_code": resource_manager.get_agent_code(),
        "channel_type": channel_type,
        "model": model,
        "flow": flow,
        "trace": trace_headers(),
        "queued_at": time.time(),
        "resource": encode_task_resource_manager(resource_manager),
    }
    json.dumps(payload)
    task = run_web_agent_task.delay(payload)
    if execute_kwargs.stream:
        return _stream_task(task, helper, execute_kwargs.turn_id)
    return task.get(timeout=_wait_timeout())


def _stream_task(task, helper: GeneratorStreamingHelper, turn_id: str):
    deadline = time.monotonic() + _wait_timeout()
    handler = helper.message_handler
    try:
        # Wait for this turn's first event, not a cached event from the previous turn.
        while not (
            handler.has_pending_messages(helper.thread_id) and handler.replay_belongs_to_run(helper.thread_id, turn_id)
        ):
            if task.ready():
                task.get()  # Propagate worker failures before a producer has started.
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for the agent worker")
            yield _HEARTBEAT
            time.sleep(1)
        yield from helper.stream(iter(()), attach_only=True, expected_run_id=turn_id)
    except (ConsumerPreemptedError, RetryableHeartbeatTimeoutError, StreamCancelledError):
        raise
    except Exception:
        logger.exception("Web agent stream failed: task_id=%s", task.id)
        yield from helper._emit_terminal_error_events("Agent worker failed; check worker logs with the task ID.")
