from aidev_agent.utils import tracing
from aidev_bkplugin.services.event_tracing import event_span
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_event_span_uses_application_service_name(monkeypatch):
    agent_exporter = InMemorySpanExporter()
    module_exporter = InMemorySpanExporter()
    agent_provider = TracerProvider(resource=Resource.create({"service.name": "ai-skill-stag"}))
    module_provider = TracerProvider(resource=Resource.create({"service.name": "ai-skill-stag-default"}))
    agent_provider.add_span_processor(SimpleSpanProcessor(agent_exporter))
    module_provider.add_span_processor(SimpleSpanProcessor(module_exporter))
    monkeypatch.setattr(tracing, "_agent_tracer", agent_provider.get_tracer("agent"))
    monkeypatch.setattr(tracing.trace, "get_tracer", lambda _: module_provider.get_tracer("module"))
    try:
        with event_span("database_event.publish", {"name": "AIDEV_CHAT_RESUME_READY"}, producer=True):
            pass
        published = module_exporter.get_finished_spans()[0]
        assert published.name == "database_event.publish"
        assert published.resource.attributes["service.name"] == "ai-skill-stag-default"
        assert not agent_exporter.get_finished_spans()
    finally:
        agent_provider.shutdown()
        module_provider.shutdown()
