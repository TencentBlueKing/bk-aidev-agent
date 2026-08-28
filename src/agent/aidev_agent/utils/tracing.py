# -*- coding: utf-8 -*-
"""Optional OpenTelemetry helpers shared by Agent SDK integrations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

try:
    from opentelemetry import context as context_api
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Tracer
except ImportError:  # OpenTelemetry is an optional Agent SDK extra.
    context_api = None
    trace = None
    SpanKind = None
    Tracer = Any

_agent_tracer: Tracer | None = None
CLIENT_SPAN_KIND = SpanKind.CLIENT if SpanKind is not None else None


class _NoOpSpan:
    """Minimal span surface used when the OpenTelemetry extra is absent."""

    @staticmethod
    def is_recording() -> bool:
        return False

    @staticmethod
    def set_attribute(name: str, value: Any) -> None:
        return None


def set_agent_tracer(tracer: Tracer | None) -> None:
    """Register the tracer owned by ``BkAidevAgentInstrumentor``.

    The agent exporter intentionally uses a private ``TracerProvider``. Code
    outside the LangChain callback therefore cannot rely on the global tracer
    provider when it needs to create a child span.
    """

    global _agent_tracer
    _agent_tracer = tracer


def get_agent_tracer(name: str) -> Tracer | None:
    """Return the agent tracer, falling back to the global no-op capable API."""

    return _agent_tracer or (trace.get_tracer(name) if trace is not None else None)


def get_current_trace_id() -> str | None:
    """Return the active OpenTelemetry trace ID without requiring the OTel extra."""

    if trace is None:
        return None
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.trace_id else None


@contextmanager
def recording_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    kind: Any = None,
    root: bool = False,
) -> Iterator[Any]:
    """Create a span with the Agent tracer, or safely no-op without OTel.

    ``root=True`` starts a new trace even when the caller happens to have an
    active context. This is intended for protocol entrypoints that represent a
    new inbound request rather than a child operation of a long-lived client.
    """

    tracer = get_agent_tracer(__name__)
    if tracer is None:
        yield _NoOpSpan()
        return

    start_kwargs: dict[str, Any] = {"attributes": attributes or {}}
    if kind is not None:
        start_kwargs["kind"] = kind
    if root and context_api is not None:
        start_kwargs["context"] = context_api.Context()
    with tracer.start_as_current_span(name, **start_kwargs) as span:
        yield span
