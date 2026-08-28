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
