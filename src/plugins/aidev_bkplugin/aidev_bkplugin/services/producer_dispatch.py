"""Serializable Chat dispatch; streamed events remain in the shared message backend."""

import hashlib
import json
import time
import uuid
from datetime import timedelta

from aidev_agent.config import settings as agent_settings
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.factory import message_handler_factory
from aidev_agent.services.messages_handler.producer import RemoteProducerRunner
from celery import current_app
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pydantic import BaseModel, ConfigDict, Field

from aidev_bkplugin.models import ChatExecution

from .background_dispatch import capture_trace_context

CHAT_TASK_NAME = "aidev_bkplugin.run_chat_producer"
ACTIVE_STATUSES = ("queued", "building", "running")


class ChatExecutionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: int = 1
    app_code: str
    tenant_id: str
    username: str
    agent_code: str
    session_code: str
    turn_id: str = ""
    model: str = ""
    temperature: float | None = None
    retry_strategy: str | None = None
    reasoning_effort: str | None = None
    version: str | None = None
    channel_type: str | None = None
    execute_kwargs: dict = Field(default_factory=dict)
    chat_history: list[dict] = Field(default_factory=list)
    knowledge_query_options: dict = Field(default_factory=dict)
    trace_context: dict[str, str] = Field(default_factory=dict)

    @property
    def scope(self) -> str:
        return execution_scope(self.app_code, self.tenant_id, self.session_code)


def execution_scope(app_code: str, tenant_id: str, session_code: str) -> str:
    return hashlib.sha256(json.dumps([app_code, tenant_id, session_code]).encode()).hexdigest()


def cancel_chat_execution(app_code: str, tenant_id: str, session_code: str, run_id: str | None = None) -> None:
    executions = ChatExecution.objects.filter(
        scope=execution_scope(app_code, tenant_id, session_code), status__in=ACTIVE_STATUSES
    )
    if run_id:
        executions = executions.filter(run_id=run_id)
    executions.update(cancelled=True)
    executions.filter(status="queued", cancelled=True).update(status="failed", error="Chat execution cancelled")


class CeleryChatRunner(RemoteProducerRunner):
    def __init__(self, spec: ChatExecutionSpec):
        self.spec = spec

    def execute_chat(self, agent, execute_kwargs):
        handler = message_handler_factory.get()
        if isinstance(handler, InMemoryQueueMessageHandler):
            raise ValueError("Celery Chat requires a shared message backend")
        spec = self.spec.model_copy(deep=True)
        spec.execute_kwargs = execute_kwargs.model_dump(mode="json")
        spec.chat_history = [prompt.model_dump(mode="json") for prompt in agent.chat_history]
        spec.knowledge_query_options = agent.knowledge_query_options.model_dump(mode="json")
        spec.trace_context = capture_trace_context()
        if execute_kwargs.stream_mode == "attach":
            execution = ChatExecution.objects.get(scope=spec.scope)
        else:
            execution = self._submit(spec)
        if execute_kwargs.stream:
            return self._consume(execution, spec.session_code, handler)
        execution = self._wait(execution, ready=False)
        return execution.result

    def _submit(self, spec: ChatExecutionSpec) -> ChatExecution:
        payload = spec.model_dump(mode="json")
        identity = {key: value for key, value in payload.items() if key not in ("trace_context", "chat_history")}
        identity["execute_kwargs"] = {
            key: value for key, value in spec.execute_kwargs.items() if key != "caller_trace_context"
        }
        request_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        queue_timeout = getattr(settings, "BKAI_CHAT_QUEUE_TIMEOUT", 300)
        defaults = {
            "task_id": uuid.uuid4().hex,
            "request_key": request_key,
            "expires_at": timezone.now() + timedelta(seconds=queue_timeout),
        }
        with transaction.atomic():
            execution, created = ChatExecution.objects.select_for_update().get_or_create(
                scope=spec.scope, defaults=defaults
            )
            if not created:
                if execution.status == "queued" and execution.expires_at <= timezone.now():
                    execution.status = "failed"
                    execution.error = "Chat queue wait expired"
                    execution.save(update_fields=["status", "error", "updated_at"])
                if execution.request_key == request_key:
                    return execution
                if execution.status in ACTIVE_STATUSES:
                    raise RuntimeError("A Chat execution is already active for this session")
                for key, value in defaults.items():
                    setattr(execution, key, value)
                execution.status, execution.run_id, execution.error = "queued", "", ""
                execution.cancelled, execution.result = False, None
                execution.save()
        try:
            current_app.send_task(
                CHAT_TASK_NAME,
                kwargs={"scope": execution.scope, "task_id": execution.task_id, "spec": payload},
                task_id=execution.task_id,
                queue=agent_settings.BKAI_AGENT_TASK,
                expires=queue_timeout,
            )
        except Exception:
            ChatExecution.objects.filter(scope=execution.scope, task_id=execution.task_id, status="queued").update(
                status="failed", error="Task submission failed"
            )
            raise
        return execution

    @staticmethod
    def _wait(execution: ChatExecution, *, ready: bool) -> ChatExecution:
        deadline = time.monotonic() + getattr(settings, "BKAI_CHAT_WAIT_TIMEOUT", 1800)
        task_id = execution.task_id
        while True:
            execution.refresh_from_db()
            if execution.task_id != task_id:
                raise RuntimeError("Chat execution was superseded")
            if execution.cancelled:
                raise RuntimeError("Chat execution cancelled")
            if execution.status == "failed":
                raise RuntimeError(execution.error or "Chat execution failed")
            if execution.status == "completed" or (ready and execution.status == "running"):
                return execution
            if execution.status == "queued" and execution.expires_at <= timezone.now():
                ChatExecution.objects.filter(pk=execution.pk, task_id=task_id, status="queued").update(
                    status="failed", error="Chat queue wait expired"
                )
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError("Chat worker wait timed out")
            time.sleep(0.1)

    def _consume(self, execution: ChatExecution, session_code: str, handler):
        execution = self._wait(execution, ready=True)
        helper = GeneratorStreamingHelper(handler, thread_id=session_code, defer_cleanup_on_complete=True)
        yield from helper.stream(iter(()), expected_run_id=execution.run_id or None, attach_only=True)


class DispatchResourceManager:
    def __init__(self, resources, runner):
        self._resources = resources
        self._runner = runner

    def get_producer_runner(self):
        return self._runner

    def __getattr__(self, name):
        return getattr(self._resources, name)
