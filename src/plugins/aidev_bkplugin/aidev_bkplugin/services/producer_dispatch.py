"""Serializable Chat dispatch; streamed events remain in the shared message backend."""

import hashlib
import json
import time
import uuid

from ag_ui.core import EventType, RawEvent
from ag_ui.encoder import EventEncoder
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.factory import message_handler_factory
from aidev_agent.services.messages_handler.rabbitmq_stream import RabbitMQStreamMessageHandler, StreamReadError
from aidev_agent.utils.tracing import propagated_trace_context, recording_span
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field

from .background_dispatch import capture_trace_context
from .producer.routing import submit

try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, StatusCode
except ImportError:
    trace = SpanKind = StatusCode = None


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


def send_started_reply(spec: ChatExecutionSpec, task_id: str, run_id: str, *, expires_at: float) -> None:
    if time.time() >= expires_at:
        raise TimeoutError("Chat queue wait expired")
    handler = message_handler_factory.get()
    reply = {"kind": "started", "run_id": run_id}
    if isinstance(handler, RabbitMQStreamMessageHandler):
        handler.publish_receipt(spec.reply_channel(task_id), reply, expires_at=expires_at)
    else:
        send_chat_reply(spec, task_id, **reply)


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
        request_span = trace.get_current_span() if trace is not None else None
        with recording_span(
            "bkplugin.chat.enqueue",
            attributes={"bkplugin.chat.task_id": task_id, "agent.session.code": spec.session_code},
            kind=SpanKind.PRODUCER if SpanKind else None,
            use_global_tracer=True,
        ) as enqueue_span:
            # Both producer backends continue from the enqueue span.
            spec.trace_context = capture_trace_context()
            payload = {
                "task_id": task_id,
                "spec": spec.model_dump(mode="json"),
                "expires_at": time.time() + queue_timeout,
            }
            backend = submit(payload, queue_timeout)
            enqueue_span.set_attribute("bkplugin.chat.producer.backend", backend)
            if request_span is not None:
                request_span.set_attribute("bkplugin.chat.producer.backend", backend)
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
            accepted = [reply for reply in replies if reply["kind"] in ("error", expected_kind)]
            if accepted:
                reply = accepted[0]
                if expected_kind == "started":
                    reply = next((item for item in accepted if item["kind"] == "error"), reply)
                handler.mark_completed(channel)
                if reply["kind"] == "error":
                    raise RuntimeError(reply["error"])
                yield reply
                return
            yield None

    @staticmethod
    def _record_startup_receipt(
        spec: ChatExecutionSpec, task_id: str, outcome: str, error_type: str | None = None
    ) -> None:
        with (
            propagated_trace_context(spec.trace_context),
            recording_span(
                "bkplugin.chat.web.startup_receipt",
                attributes={"bkplugin.chat.task_id": task_id, "bkplugin.chat.receipt": outcome},
                use_global_tracer=True,
            ) as span,
        ):
            if error_type:
                span.set_attribute("error.type", error_type)
                if StatusCode is not None and span.is_recording():
                    span.set_status(StatusCode.ERROR)

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
                        self._record_startup_receipt(spec, task_id, "started")
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
            error_type = type(exc.cause if isinstance(exc, StreamReadError) else exc).__name__
            if task_id:
                outcome = "timeout" if isinstance(exc, TimeoutError) else "error"
                self._record_startup_receipt(spec, task_id, outcome, error_type)
            yield from helper._emit_terminal_error_events(error_type)
            return
        yield from helper.stream(
            iter(()), expected_run_id=run_id, attach_only=True, before_first_chunk=waiting_heartbeat
        )
