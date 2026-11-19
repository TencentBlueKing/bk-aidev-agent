"""Serializable Chat dispatch; streamed events remain in the shared message backend."""

import hashlib
import json
import time
import uuid

from ag_ui.core import EventType, RawEvent
from ag_ui.encoder import EventEncoder
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.factory import message_handler_factory
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field

from .background_dispatch import capture_trace_context
from .producer.routing import submit


WORKER_HEARTBEAT_INTERVAL = 5


class ChatExecutionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: int = 2
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


class ChatDispatcher:
    """Dispatch a prepared session; Web never constructs or serializes an Agent."""

    def __init__(self, spec: ChatExecutionSpec):
        self.spec = spec

    def execute(self, execute_kwargs):
        handler = message_handler_factory.get()
        if isinstance(handler, InMemoryQueueMessageHandler) or not handler.supports_replay_from_start():
            raise ValueError("Celery Chat requires a shared replay message backend")
        spec = self.spec.model_copy(deep=True)
        spec.execute_kwargs = execute_kwargs.model_dump(mode="json")
        spec.trace_context = capture_trace_context()
        if execute_kwargs.stream_mode == "attach":
            return self._consume(spec, handler)
        task_id = self._submit(spec)
        if execute_kwargs.stream:
            return self._consume(spec, handler, task_id)
        return self._wait_reply(
            spec.reply_channel(task_id),
            handler,
            expected_kind="result",
            timeout=getattr(settings, "BKAI_CHAT_WAIT_TIMEOUT", 1800),
        )["result"]

    def _submit(self, spec: ChatExecutionSpec) -> str:
        task_id = uuid.uuid4().hex
        queue_timeout = getattr(settings, "BKAI_CHAT_QUEUE_TIMEOUT", 300)
        payload = {
            "task_id": task_id,
            "spec": spec.model_dump(mode="json"),
            "expires_at": time.time() + queue_timeout,
        }
        submit(payload, queue_timeout)
        return task_id

    @classmethod
    def _wait_reply(cls, channel: str, handler, *, expected_kind: str, timeout: float) -> dict:
        polls = cls._poll_reply(channel, handler, expected_kind=expected_kind, timeout=timeout)
        return next(reply for reply in polls if reply is not None)

    @staticmethod
    def _poll_reply(channel: str, handler, *, expected_kind: str, timeout: float):
        deadline = time.monotonic() + timeout
        offset = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Chat worker wait timed out")
            try:
                replies, offset = handler.get_messages_since(channel, offset, timeout=min(1, remaining))
            except TimeoutError:
                replies = ()
            for reply in replies:
                if reply["kind"] not in ("error", expected_kind):
                    continue
                handler.mark_completed(channel)
                if reply["kind"] == "error":
                    raise RuntimeError(reply["error"])
                yield reply
                return
            yield None

    def _consume(self, spec: ChatExecutionSpec, handler, task_id: str | None = None):
        # Flush the HTTP SSE response before waiting for worker startup.
        heartbeat = EventEncoder().encode(
            RawEvent(type=EventType.RAW, event={"type": "heartbeat", "message": "waiting for worker"})
        )
        next_heartbeat = time.monotonic() + WORKER_HEARTBEAT_INTERVAL
        yield heartbeat

        def waiting_heartbeat():
            nonlocal next_heartbeat
            now = time.monotonic()
            if now >= next_heartbeat:
                next_heartbeat = now + WORKER_HEARTBEAT_INTERVAL
                return heartbeat
            return None

        timeout = getattr(settings, "BKAI_CHAT_QUEUE_TIMEOUT", 300)
        run_id = None
        helper = GeneratorStreamingHelper(handler, thread_id=spec.session_code, defer_cleanup_on_complete=True)
        try:
            if task_id:
                for reply in self._poll_reply(
                    spec.reply_channel(task_id), handler, expected_kind="started", timeout=timeout
                ):
                    if reply is not None:
                        run_id = reply["run_id"] or None
                        break
                    if chunk := waiting_heartbeat():
                        yield chunk
            else:
                deadline = time.monotonic() + timeout
                while not handler.has_active_producer(spec.session_code) and not handler.has_pending_messages(
                    spec.session_code
                ):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Chat stream did not become available")
                    if chunk := waiting_heartbeat():
                        yield chunk
                    time.sleep(0.1)
        except (TimeoutError, RuntimeError) as exc:
            yield from helper._emit_terminal_error_events(type(exc).__name__)
            return
        yield from helper.stream(
            iter(()), expected_run_id=run_id, attach_only=True, before_first_chunk=waiting_heartbeat
        )
