"""Celery 边界的 Trace 上下文捕获与恢复。"""

from typing import Any

try:
    from opentelemetry import context, propagate
except ImportError:  # OTel is optional.
    context = propagate = None


def capture_trace_context() -> dict[str, str]:
    carrier: dict[str, str] = {}
    if propagate is not None:
        propagate.inject(carrier)
    return carrier


def attach_trace_context(carrier: dict[str, str] | None) -> Any:
    if not carrier or context is None or propagate is None:
        return None
    return context.attach(propagate.extract(carrier))


def detach_trace_context(token: Any) -> None:
    if context is not None and token is not None:
        context.detach(token)
