import pytest
from aidev_agent.utils import tracing
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(tracing, "_agent_tracer", tracer)
    monkeypatch.setattr(tracing.trace, "get_tracer", lambda _: tracer)
    yield exporter
    provider.shutdown()


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
