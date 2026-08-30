"""Runtime-independent, process-local integration events (AG-UI envelopes)."""

from collections.abc import Callable
from threading import RLock
from typing import Protocol

from ag_ui.core import BaseEvent, CustomEvent

AIDEV_CHAT_RESUME_READY = "AIDEV_CHAT_RESUME_READY"
EventHandler = Callable[[BaseEvent], None]


def event_key(event: BaseEvent) -> str:
    return event.name if isinstance(event, CustomEvent) else str(getattr(event.type, "value", event.type))


class EventPublisher(Protocol):
    def publish(self, event: BaseEvent) -> None:
        """Dispatch/accept an event; this does not acknowledge channel delivery."""
        ...


class EventBus(EventPublisher, Protocol):
    def subscribe(self, name: str, handler: EventHandler) -> Callable[[], None]: ...


class LocalEventBus:
    """Synchronous listeners; no global singleton, network I/O or persistence.

    Registration is thread-safe. Publishing snapshots listeners, releases the
    lock and invokes each with its own event copy. Failures reach the publisher;
    callers decide whether a listener is observational or delivery-critical.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, dict[object, EventHandler]] = {}
        self._lock = RLock()

    def subscribe(self, name: str, handler: EventHandler) -> Callable[[], None]:
        token = object()
        with self._lock:
            self._handlers.setdefault(name, {})[token] = handler

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._handlers.get(name, {})
                handlers.pop(token, None)
                if not handlers:
                    self._handlers.pop(name, None)

        return unsubscribe

    def publish(self, event: BaseEvent) -> None:
        with self._lock:
            handlers = tuple(self._handlers.get(event_key(event), {}).values())
        errors = []
        for handler in handlers:
            try:
                handler(event.model_copy(deep=True))
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("Event listeners failed", errors)
