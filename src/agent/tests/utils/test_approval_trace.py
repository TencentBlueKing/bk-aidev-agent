from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("opentelemetry.sdk")

from aidev_agent.core.nodes.tool.approval_wrapper import ApprovalTarget, _create_approval_from_target
from aidev_agent.utils import tracing
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "_agent_tracer", provider.get_tracer("test"))
    yield exporter
    provider.shutdown()


def test_sdk_approval_request_injects_client_parent(spans, monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("aidev_agent.core.nodes.tool.approval_wrapper.BKAidevApi.get_client", lambda: client)
    target = ApprovalTarget("tool", "call", "query", "query", {}, {})
    with tracing.recording_span("entry") as entry:
        _create_approval_from_target(target, SimpleNamespace(executor="test-user"))
    headers = client.api.create_tool_approval.call_args.kwargs["headers"]
    created = next(span for span in spans.get_finished_spans() if span.name == "agent.approval.create")
    assert created.parent.span_id == entry.get_span_context().span_id
    assert headers["traceparent"].split("-")[1:3] == [
        format(created.context.trace_id, "032x"),
        format(created.context.span_id, "016x"),
    ]
    assert headers["X-BKAIDEV-USER"] == "test-user"
    assert "baggage" not in headers


@pytest.mark.parametrize("carrier", [{}, None, {"traceparent": "invalid"}, {"baggage": "private=value"}])
def test_invalid_durable_parent_does_not_adopt_worker_trace(spans, carrier):
    with tracing.recording_span("unrelated-worker") as worker:
        with tracing.propagated_trace_context(carrier):
            assert not trace.get_current_span().get_span_context().is_valid
        assert trace.get_current_span() is worker


def test_context_helpers_noop_without_otel(monkeypatch):
    monkeypatch.setattr(tracing, "TraceContextTextMapPropagator", None)
    assert tracing.trace_headers() == {}
    with tracing.propagated_trace_context({"traceparent": "invalid"}):
        pass
