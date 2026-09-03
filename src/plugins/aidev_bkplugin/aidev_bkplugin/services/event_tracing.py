"""Durable event spans without message bodies, recipient identities or baggage."""

from contextlib import contextmanager

from aidev_agent.utils.tracing import get_agent_tracer, propagated_trace_context

try:
    from opentelemetry.trace import SpanKind, StatusCode
except ImportError:
    SpanKind = StatusCode = None


@contextmanager
def event_span(name: str, envelope: dict, *, producer: bool = False, attributes: dict | None = None):
    value = envelope.get("value") or {}
    with propagated_trace_context(value.get("traceContext")):
        tracer = get_agent_tracer(__name__)
        if tracer is None:
            yield None
            return
        options = {
            "attributes": {
                "messaging.system": "database",
                "event.name": envelope.get("name", ""),
                **(attributes or {}),
            },
            "record_exception": False,
            "set_status_on_exception": False,
        }
        if SpanKind is not None:
            options["kind"] = SpanKind.PRODUCER if producer else SpanKind.CONSUMER
        with tracer.start_as_current_span(name, **options) as span:
            try:
                yield span
            except Exception as error:
                span.set_attribute("error.type", type(error).__name__)
                if StatusCode is not None:
                    span.set_status(StatusCode.ERROR)
                raise
