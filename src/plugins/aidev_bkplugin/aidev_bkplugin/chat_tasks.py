"""Worker-side Chat reconstruction. No live Agent object crosses the broker."""

from functools import partial

from aidev_agent.config import settings as agent_settings
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs, KnowledgeSettings
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.messages_handler.producer import ProducerOnlyRunner
from celery import shared_task
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from aidev_bkplugin.models import ChatExecution
from aidev_bkplugin.services.agent_builder import AgentBuilder, LLMOverrideResourceManager
from aidev_bkplugin.services.agent_execution import AgentExecutor
from aidev_bkplugin.services.background_dispatch import attach_trace_context, detach_trace_context
from aidev_bkplugin.services.producer_dispatch import CHAT_TASK_NAME, ChatExecutionSpec, DispatchResourceManager


def mark_chat_started(scope: str, task_id: str, thread_id: str, run_id: str) -> None:
    changed = ChatExecution.objects.filter(scope=scope, task_id=task_id, status="building", cancelled=False).update(
        status="running", run_id=run_id
    )
    if not changed:
        raise RuntimeError("Chat execution cancelled or no longer owned")


@shared_task(name=CHAT_TASK_NAME, ignore_result=True, queue=agent_settings.BKAI_AGENT_TASK)
def run_chat_producer(scope: str, task_id: str, spec: dict) -> None:
    close_old_connections()
    owned = ChatExecution.objects.filter(scope=scope, task_id=task_id)
    claimed = owned.filter(status="queued", cancelled=False, expires_at__gt=timezone.now()).update(status="building")
    if not claimed:
        owned.filter(status="queued", cancelled=True).update(status="failed", error="Chat execution cancelled")
        return
    token = None
    try:
        execution_spec = ChatExecutionSpec.model_validate(spec)
        if execution_spec.protocol_version != 1 or execution_spec.scope != scope:
            raise ValueError("Invalid Chat execution protocol or scope")
        if execution_spec.app_code != agent_settings.APP_CODE:
            raise ValueError("Chat execution belongs to another application")
        token = attach_trace_context(execution_spec.trace_context)
        result = execute_chat_producer(execution_spec, task_id)
        owned.filter(status__in=("building", "running")).update(status="completed", result=result)
    except Exception as exc:
        owned.filter(status__in=("building", "running")).update(status="failed", error=type(exc).__name__)
        raise
    finally:
        detach_trace_context(token)
        close_old_connections()


def execute_chat_producer(spec: ChatExecutionSpec, task_id: str):
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
    runner = ProducerOnlyRunner(partial(mark_chat_started, spec.scope, task_id))
    agent.resource_manager = DispatchResourceManager(agent.resource_manager, runner)
    execute_kwargs = ExecuteKwargs.model_validate(spec.execute_kwargs)
    execute_kwargs.background_only = True
    executor = AgentExecutor(builder.session_manager)
    output = executor.execute_with_save(agent, execute_kwargs, spec.session_code, turn_id=spec.turn_id)
    if not execute_kwargs.stream:
        return output
    if execute_kwargs.legacy_streaming:
        helper = GeneratorStreamingHelper(thread_id=spec.session_code, resource_manager=agent.resource_manager)
        output = helper.stream(output, expected_run_id=task_id)
    for _ in output:
        pass
    return None
