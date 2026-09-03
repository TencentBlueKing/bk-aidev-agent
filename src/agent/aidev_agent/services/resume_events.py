"""Producer-owned resume lifecycle, independent of Runtime and channel transports.

The terminal envelope carries only this execution's display events, not prompts,
state snapshots or the session history. A slow/offline subscriber can render the
same result without sharing the stream cache or executing the agent again.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

from ag_ui.core import CustomEvent

from aidev_agent.events import AIDEV_CHAT_RESUME_FAILED, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_READY

try:
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    TraceContextTextMapPropagator = None

logger = logging.getLogger(__name__)
DISPLAY_EVENTS = frozenset(
    {
        "RUN_STARTED",
        "RUN_FINISHED",
        "RUN_ERROR",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "TOOL_CALL_RESULT",
        "THINKING_TEXT_MESSAGE_START",
        "THINKING_TEXT_MESSAGE_CONTENT",
        "THINKING_TEXT_MESSAGE_END",
    }
)


class ResumeEvents:
    def __init__(self, resource_manager, *, session_code: str, thread_id: str, turn_id: str, resume: list):
        self.resource_manager = resource_manager
        self.enabled = True
        self._events = []
        self._ready = None
        self._ready_published = False
        self._completed = False
        self._value = {
            "schemaVersion": 1,
            "appCode": resource_manager.get_agent_code(),
            "sessionCode": session_code,
            "threadId": thread_id,
            "turnId": turn_id,
            "interruptIds": sorted({str(item["interruptId"]) for item in resume if item.get("interruptId")}),
        }
        if TraceContextTextMapPropagator is not None:
            carrier = {}
            TraceContextTextMapPropagator().inject(carrier)
            self._value["traceContext"] = carrier

    def on_chunk(self, chunk) -> None:
        if not self.enabled or not isinstance(chunk, str) or not chunk.startswith("data:"):
            return
        try:
            event = json.loads(chunk[5:].strip())
        except (ValueError, TypeError):
            return
        if not isinstance(event, dict):
            return
        event_type = event.get("type")
        if event_type == "RUN_STARTED" and self._ready is None:
            self._value["runId"] = event.get("runId") or event.get("run_id")
            self._ready = self._envelope(AIDEV_CHAT_RESUME_READY)
            try:
                self.resource_manager.publish_event(self._ready)
                self._ready_published = True
            except Exception as error:
                # Let the producer finish; retry the identical notification at completion.
                logger.error("event=resume_ready_publish_failed error_type=%s", type(error).__name__)
        if self._ready is not None and (
            event_type in DISPLAY_EVENTS or (event_type == "CUSTOM" and "documents" in event)
        ):
            # Coalesce adjacent text deltas in the result snapshot.
            if (
                event_type == "TEXT_MESSAGE_CONTENT"
                and self._events
                and self._events[-1].get("type") == event_type
                and self._events[-1].get("messageId") == event.get("messageId")
            ):
                self._events[-1]["delta"] += event.get("delta", "")
            else:
                self._events.append(event)

    def _envelope(self, name: str, **extra) -> CustomEvent:
        identity = json.dumps(
            [self._value[key] for key in ("appCode", "sessionCode", "threadId", "runId", "interruptIds")] + [name],
            sort_keys=True,
            separators=(",", ":"),
        )
        return CustomEvent(
            name=name,
            value={
                **self._value,
                "eventId": hashlib.sha256(identity.encode()).hexdigest(),
                "occurredAt": datetime.now(timezone.utc).isoformat(),
                **extra,
            },
        )

    def on_complete(self, error: Exception | None = None) -> None:
        if not self.enabled or self._ready is None or self._completed:
            return
        if not self._ready_published:
            self.resource_manager.publish_event(self._ready)
            self._ready_published = True
        failed = error is not None or any(e.get("type") == "RUN_ERROR" for e in self._events)
        name = AIDEV_CHAT_RESUME_FAILED if failed else AIDEV_CHAT_RESUME_FINISHED
        self.resource_manager.publish_event(self._envelope(name, events=self._events, persisted=error is None))
        self._completed = True


def resume_events_for(resource_manager, **kwargs) -> ResumeEvents | None:
    enabled = getattr(resource_manager, "event_publishing_enabled", None)
    if callable(enabled) and enabled() is True and kwargs.get("session_code") and kwargs.get("resume"):
        return ResumeEvents(resource_manager, **kwargs)
    return None


def uses_resume_event_stream(resource_manager, execute_kwargs) -> bool:
    enabled = getattr(resource_manager, "event_publishing_enabled", None)
    return bool(
        execute_kwargs.resume and not execute_kwargs.legacy_streaming and callable(enabled) and enabled() is True
    )
