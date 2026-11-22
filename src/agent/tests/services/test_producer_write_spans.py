from unittest.mock import Mock

import pytest
from aidev_agent.services.messages_handler import EOD_CHUNK, GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.utils import tracing
from rstream.client import BrokerResolutionMaxRetryError

TracerProvider = pytest.importorskip("opentelemetry.sdk.trace").TracerProvider
SimpleSpanProcessor = pytest.importorskip("opentelemetry.sdk.trace.export").SimpleSpanProcessor
InMemorySpanExporter = pytest.importorskip(
    "opentelemetry.sdk.trace.export.in_memory_span_exporter"
).InMemorySpanExporter
StatusCode = pytest.importorskip("opentelemetry.trace").StatusCode


@pytest.mark.parametrize("failure", [None, "write", "eod"])
def test_producer_write_spans(monkeypatch, failure):
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)
    monkeypatch.setattr(tracing, "_agent_tracer", tracer)
    handler = InMemoryQueueMessageHandler()
    helper = GeneratorStreamingHelper(handler, thread_id="producer-write")
    monkeypatch.setattr(helper, "_schedule_session_cleanup", Mock())
    put = handler.put

    def write(thread_id, chunk):
        if (failure == "write" and chunk == "hello") or (failure == "eod" and chunk == EOD_CHUNK):
            raise BrokerResolutionMaxRetryError("broker unavailable")
        put(thread_id, chunk)

    monkeypatch.setattr(handler, "put", write)
    with tracer.start_as_current_span("request") as request:
        helper._run_producer(generator=iter(["hello"]))
    start, end, _ = exporter.get_finished_spans()
    assert [start.name, end.name] == ["bkplugin.chat.producer.write.start", "bkplugin.chat.producer.write.end"]
    assert start.parent == end.parent == request.get_span_context()
    assert end.status.status_code == (StatusCode.ERROR if failure else StatusCode.UNSET)
    if failure == "write":
        assert start.status.status_code == StatusCode.ERROR
        assert end.attributes["producer_error_type"] == "BrokerResolutionMaxRetryError"
    if failure == "eod":
        assert end.events[0].name == "exception"
