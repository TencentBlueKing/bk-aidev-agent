"""Serializable Chat dispatch; streamed events remain in the shared message backend."""

import hashlib
import json
import time
import uuid

from aidev_agent.config import settings as agent_settings
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.factory import message_handler_factory
from aidev_agent.services.messages_handler.producer import RemoteProducerRunner
from celery import current_app
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field

from .background_dispatch import capture_trace_context

CHAT_TASK_NAME = "aidev_bkplugin.run_chat_producer"


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

    def reply_channel(self, task_id: str) -> str:
        identity = [self.app_code, self.tenant_id, self.session_code, task_id]
        return "chat-reply-" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def send_chat_reply(spec: ChatExecutionSpec, task_id: str, **reply) -> None:
    """Short-lived transport receipts, using the existing message backend and TTL."""
    handler = message_handler_factory.get()
    channel = spec.reply_channel(task_id)
    handler.put(channel, reply)
    handler.flush(channel)


class CeleryChatRunner(RemoteProducerRunner):
    def __init__(self, spec: ChatExecutionSpec):
        self.spec = spec

    def execute_chat(self, agent, execute_kwargs):
        handler = message_handler_factory.get()
        if isinstance(handler, InMemoryQueueMessageHandler) or not handler.supports_replay_from_start():
            raise ValueError("Celery Chat requires a shared replay message backend")
        spec = self.spec.model_copy(deep=True)
        spec.execute_kwargs = execute_kwargs.model_dump(mode="json")
        spec.chat_history = [prompt.model_dump(mode="json") for prompt in agent.chat_history]
        spec.knowledge_query_options = agent.knowledge_query_options.model_dump(mode="json")
        spec.trace_context = capture_trace_context()
        if execute_kwargs.stream_mode == "attach":
            return self._consume_existing(spec.session_code, handler)
        task_id = self._submit(spec)
        if execute_kwargs.stream:
            return self._consume(task_id, spec, handler)
        return self._wait_reply(task_id, spec, handler, ready=False)["result"]

    def _submit(self, spec: ChatExecutionSpec) -> str:
        task_id = uuid.uuid4().hex
        queue_timeout = getattr(settings, "BKAI_CHAT_QUEUE_TIMEOUT", 300)
        current_app.send_task(
            CHAT_TASK_NAME,
            kwargs={
                "task_id": task_id,
                "spec": spec.model_dump(mode="json"),
                "expires_at": time.time() + queue_timeout,
            },
            task_id=task_id,
            queue=agent_settings.BKAI_AGENT_TASK,
            expires=queue_timeout,
        )
        return task_id

    @staticmethod
    def _wait_reply(task_id: str, spec: ChatExecutionSpec, handler, *, ready: bool) -> dict:
        timeout = (
            getattr(settings, "BKAI_CHAT_QUEUE_TIMEOUT", 300)
            if ready
            else getattr(settings, "BKAI_CHAT_WAIT_TIMEOUT", 1800)
        )
        deadline = time.monotonic() + timeout
        offset = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Chat worker wait timed out")
            try:
                replies, offset = handler.get_messages_since(
                    spec.reply_channel(task_id), offset, timeout=min(1, remaining)
                )
            except TimeoutError:
                continue
            for reply in replies:
                if reply["kind"] == "error":
                    handler.mark_completed(spec.reply_channel(task_id))
                    raise RuntimeError(reply["error"])
                if reply["kind"] == ("started" if ready else "result"):
                    handler.mark_completed(spec.reply_channel(task_id))
                    return reply

    def _consume(self, task_id: str, spec: ChatExecutionSpec, handler):
        reply = self._wait_reply(task_id, spec, handler, ready=True)
        helper = GeneratorStreamingHelper(handler, thread_id=spec.session_code, defer_cleanup_on_complete=True)
        yield from helper.stream(iter(()), expected_run_id=reply["run_id"] or None, attach_only=True)

    @staticmethod
    def _consume_existing(session_code: str, handler):
        deadline = time.monotonic() + getattr(settings, "BKAI_CHAT_QUEUE_TIMEOUT", 300)
        while not handler.has_active_producer(session_code) and not handler.has_pending_messages(session_code):
            if time.monotonic() >= deadline:
                raise TimeoutError("Chat stream did not become available")
            time.sleep(0.1)
        helper = GeneratorStreamingHelper(handler, thread_id=session_code, defer_cleanup_on_complete=True)
        yield from helper.stream(iter(()), attach_only=True)


class DispatchResourceManager:
    def __init__(self, resources, runner):
        self._resources = resources
        self._runner = runner

    def get_producer_runner(self):
        return self._runner

    def __getattr__(self, name):
        return getattr(self._resources, name)
