"""Durable event spans without message bodies, recipient identities or baggage."""

from contextlib import contextmanager

from aidev_agent.utils.tracing import propagated_trace_context, recording_span

try:
    from opentelemetry.trace import SpanKind, StatusCode
except ImportError:
    SpanKind = StatusCode = None


@contextmanager
def event_span(name: str, envelope: dict, *, producer: bool = False, attributes: dict | None = None):
    value = envelope.get("value") or {}
    kind = None
    if SpanKind is not None:
        kind = SpanKind.PRODUCER if producer else SpanKind.CONSUMER
    with (
        propagated_trace_context(value.get("traceContext")),
        recording_span(
            name,
            kind=kind,
            use_global_tracer=True,
            record_exception=False,
            attributes={
                "messaging.system": "database",
                "event.name": envelope.get("name", ""),
                **(attributes or {}),
            },
        ) as span,
    ):
        try:
            yield span
        except Exception as error:
            span.set_attribute("error.type", type(error).__name__)
            if StatusCode is not None:
                span.set_status(StatusCode.ERROR)
            raise
