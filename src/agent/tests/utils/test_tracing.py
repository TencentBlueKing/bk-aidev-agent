from unittest.mock import MagicMock

from aidev_agent.utils import tracing


def test_get_current_trace_id_returns_active_trace_id(monkeypatch):
    context = MagicMock(trace_id=int("a" * 32, 16))
    span = MagicMock()
    span.get_span_context.return_value = context
    trace_api = MagicMock()
    trace_api.get_current_span.return_value = span
    monkeypatch.setattr(tracing, "trace", trace_api)

    assert tracing.get_current_trace_id() == "a" * 32


def test_get_current_trace_id_without_otel(monkeypatch):
    monkeypatch.setattr(tracing, "trace", None)

    assert tracing.get_current_trace_id() is None


def test_recording_span_can_force_a_new_root(monkeypatch):
    tracer = MagicMock()
    monkeypatch.setattr(tracing, "_agent_tracer", tracer)
    context = MagicMock()
    context_api = MagicMock()
    context_api.Context.return_value = context
    monkeypatch.setattr(tracing, "context_api", context_api)

    with tracing.recording_span("entrypoint", root=True):
        pass

    tracer.start_as_current_span.assert_called_once_with("entrypoint", attributes={}, context=context)
