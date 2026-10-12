"""Run a stream producer inside a caller-owned worker slot."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

producer_started: ContextVar[tuple[str, Callable[[], None]] | None] = ContextVar("producer_started", default=None)


@contextmanager
def worker_producer(thread_id: str, on_started: Callable[[], None]) -> Iterator[None]:
    """The worker publishes events; HTTP consumers attach independently."""
    token = producer_started.set((thread_id, on_started))
    try:
        yield
    finally:
        producer_started.reset(token)


def get_producer_started(thread_id: str) -> Callable[[], None] | None:
    execution = producer_started.get()
    return execution[1] if execution is not None and execution[0] == thread_id else None
