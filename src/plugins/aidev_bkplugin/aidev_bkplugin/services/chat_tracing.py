"""Chat entry context must exist before constructing a lazy resume stream."""

from contextlib import nullcontext
from functools import wraps

from aidev_agent.utils.tracing import propagated_trace_context, recording_span, trace_headers

try:
    from opentelemetry.trace import SpanKind
except ImportError:
    SpanKind = None


def chat_request_span(function):
    @wraps(function)
    def wrapped(self, request, *args, **kwargs):
        # Keep an existing HTTP middleware span. When middleware is absent, use
        # the W3C header rather than allowing the later producer to start a root.
        headers = getattr(request, "headers", {})
        parent = nullcontext()
        if not trace_headers():
            parent = propagated_trace_context({key: headers.get(key) for key in ("traceparent", "tracestate")})
        with (
            parent,
            recording_span(
                "bkplugin.chat.request",
                kind=SpanKind.INTERNAL if SpanKind else None,
                record_exception=False,
            ),
        ):
            return function(self, request, *args, **kwargs)

    return wrapped
