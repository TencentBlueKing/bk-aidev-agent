from unittest.mock import Mock

import pytest
from aidev_agent.utils import tracing
from aidev_bkplugin.services.producer import routing
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode


@pytest.mark.parametrize(("started", "backend"), [(True, "local"), (False, "celery")])
def test_dispatch_span_records_selected_backend(monkeypatch, started, backend):
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing.trace, "get_tracer", provider.get_tracer)
    monkeypatch.setattr(routing.local, "try_start_local_producer", lambda payload: started)
    enqueue = Mock()
    monkeypatch.setattr(routing.celery, "enqueue", enqueue)
    with provider.get_tracer("test").start_as_current_span("request") as request:
        routing.submit({}, 30)
    span, _ = exporter.get_finished_spans()
    assert span.parent.span_id == request.get_span_context().span_id
    assert span.name == "bkplugin.chat.producer.dispatch"
    assert span.attributes["bkplugin.chat.producer.backend"] == backend
    assert enqueue.called == (backend == "celery")
    provider.shutdown()


def test_failed_celery_dispatch_marks_span_without_exception_details(monkeypatch):
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing.trace, "get_tracer", provider.get_tracer)
    monkeypatch.setattr(routing.local, "try_start_local_producer", lambda payload: False)
    monkeypatch.setattr(routing.celery, "enqueue", Mock(side_effect=ConnectionError("broker details")))
    with pytest.raises(ConnectionError):
        routing.submit({}, 30)
    (span,) = exporter.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description is None
    assert span.attributes["error.type"] == "ConnectionError"
    assert span.attributes["bkplugin.chat.producer.backend"] == "celery"
    assert not span.events
    provider.shutdown()
