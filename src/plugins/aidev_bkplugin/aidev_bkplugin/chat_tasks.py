"""Worker-side Chat reconstruction. No live Agent object crosses the broker."""

import time
from functools import partial

from aidev_agent.config import settings as agent_settings
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs, KnowledgeSettings
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.messages_handler.factory import message_handler_factory
from aidev_agent.services.messages_handler.producer import ProducerOnlyRunner
from celery import shared_task
from django.conf import settings
from django.db import close_old_connections

from aidev_bkplugin.services.agent_builder import AgentBuilder, LLMOverrideResourceManager
from aidev_bkplugin.services.agent_execution import AgentExecutor
from aidev_bkplugin.services.background_dispatch import attach_trace_context, detach_trace_context
from aidev_bkplugin.services.producer_dispatch import (
    CHAT_TASK_NAME,
    ChatExecutionSpec,
    DispatchResourceManager,
    send_chat_reply,
)


def mark_chat_started(spec: ChatExecutionSpec, task_id: str, expires_at: float, thread_id: str, run_id: str) -> None:
    if time.time() >= expires_at:
        raise TimeoutError("Chat queue wait expired")
    send_chat_reply(spec, task_id, kind="started", run_id=run_id)


@shared_task(name=CHAT_TASK_NAME, ignore_result=True, queue=agent_settings.BKAI_AGENT_TASK)
def run_chat_producer(task_id: str, spec: dict, expires_at: float) -> None:
    close_old_connections()
    token = None
    execution_spec = None
    handler = message_handler_factory.get()
    sync_lock = False
    try:
        execution_spec = ChatExecutionSpec.model_validate(spec)
        if execution_spec.protocol_version != 1:
            raise ValueError("Invalid Chat execution protocol")
        if execution_spec.app_code != agent_settings.APP_CODE:
            raise ValueError("Chat execution belongs to another application")
        if time.time() >= expires_at:
            raise TimeoutError("Chat queue wait expired")
        # Preserve the existing run-scoped signal: a stop for an old run must
        # not cancel a newly queued task. Session-wide stops bind to this task.
        if handler.check_cancel_signal(execution_spec.session_code, run_id=task_id):
            handler.clear_cancel_signal(execution_spec.session_code, run_id=task_id)
            raise RuntimeError("Chat execution cancelled")
        if not execution_spec.execute_kwargs.get("stream", False):
            sync_lock = handler.acquire_producer(execution_spec.session_code)
            if not sync_lock:
                raise RuntimeError("A Chat producer is already active")
        token = attach_trace_context(execution_spec.trace_context)
        result = execute_chat_producer(execution_spec, task_id, expires_at)
        if not execution_spec.execute_kwargs.get("stream", False):
            send_chat_reply(execution_spec, task_id, kind="result", result=result)
    except Exception as exc:
        if execution_spec is not None:
            send_chat_reply(execution_spec, task_id, kind="error", error=type(exc).__name__)
        raise
    finally:
        if sync_lock:
            handler.release_producer(execution_spec.session_code)
        detach_trace_context(token)
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
        remote_execution=False,
    )
    agent = builder.by_session_code(spec.session_code, version=spec.version, channel_type=spec.channel_type)
    agent.chat_history = [ChatPrompt.model_validate(prompt) for prompt in spec.chat_history]
    agent.knowledge_query_options = KnowledgeSettings.model_validate(spec.knowledge_query_options)
    runner = ProducerOnlyRunner(partial(mark_chat_started, spec, task_id, expires_at))
    agent.resource_manager = DispatchResourceManager(agent.resource_manager, runner)
    execute_kwargs = ExecuteKwargs.model_validate(spec.execute_kwargs)
    execute_kwargs.background_only = True
    executor = AgentExecutor(builder.session_manager)
    if time.time() >= expires_at:
        raise TimeoutError("Chat queue wait expired")
    output = executor.execute_with_save(agent, execute_kwargs, spec.session_code, turn_id=spec.turn_id)
    if not execute_kwargs.stream:
        return output
    if execute_kwargs.legacy_streaming:
        helper = GeneratorStreamingHelper(thread_id=spec.session_code, resource_manager=agent.resource_manager)
        output = helper.stream(output, expected_run_id=task_id)
    for _ in output:
        pass
    return None
