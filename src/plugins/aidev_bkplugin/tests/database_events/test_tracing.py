import asyncio

import pytest
from aidev_agent.utils import tracing
from aidev_bkplugin.models import EventDelivery
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


def test_publish_claim_consume_share_entry_trace(wx_delivery_case, spans):
    case = wx_delivery_case
    with tracing.recording_span("web.entry") as entry:
        case.event.value["traceContext"] = tracing.trace_headers()
    original = dict(case.event.value["traceContext"])
    with tracing.recording_span("unrelated-worker"):
        case.bus.publish(case.event)
        case.bus.publish(case.event)  # tracing must not break idempotent publishing
        asyncio.run(case.consumer.consume_once())
    recorded = [
        s
        for s in spans.get_finished_spans()
        if s.name in ("database_event.publish", "database_event.claim", "wxbot.event.consume")
    ]
    assert len(recorded) == 4
    assert all(s.context.trace_id == entry.get_span_context().trace_id for s in recorded)
    claim = next(s for s in recorded if s.name == "database_event.claim")
    assert claim.attributes["messaging.message.age_ms"] >= 0
    assert claim.attributes["messaging.receive.lookup.duration_ms"] >= 0
    assert claim.attributes["messaging.delivery.attempt"] == 1
    delivery = EventDelivery.objects.get()
    assert delivery.status == "delivered" and delivery.envelope["value"]["traceContext"] == original


def test_empty_poll_does_not_create_unbounded_spans(event_case, spans):
    assert event_case.bus.claim("wxbot:test") is None
    assert not spans.get_finished_spans()


def test_publish_failure_records_type_not_payload(event_case, spans):
    case = event_case
    case.bus.publish(case.event)
    case.event.value["secret"] = "private-value"
    with pytest.raises(ValueError):
        case.bus.publish(case.event)
    failed = spans.get_finished_spans()[-1]
    assert failed.attributes["error.type"] == "ValueError"
    assert failed.events == ()
    assert "private-value" not in str(dict(failed.attributes))
