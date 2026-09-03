from unittest.mock import MagicMock

import pytest
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


# ---------------------------------------------------------------------- #
# propagated_trace_context / trace_headers（原 test_approval_trace.py 并入；
# 其 test 1 依赖的 _create_approval_from_target 已随 43-04 建单迁移删除，
# X-BKAIDEV-USER 头注入由 test_approval_methods.py 覆盖）
# ---------------------------------------------------------------------- #


def _install_memory_tracer(monkeypatch):
    """安装真实 SDK tracer（需 opentelemetry.sdk），返回 (exporter, provider)。"""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "_agent_tracer", provider.get_tracer("test"))
    return provider


@pytest.mark.parametrize("carrier", [{}, None, {"traceparent": "invalid"}, {"baggage": "private=value"}])
def test_invalid_durable_parent_does_not_adopt_worker_trace(monkeypatch, carrier):
    """无效/缺失 durable parent 不采纳上下文，退出 propagated 块后回到 worker span。"""
    provider = _install_memory_tracer(monkeypatch)
    try:
        with tracing.recording_span("unrelated-worker") as worker:
            with tracing.propagated_trace_context(carrier):
                assert not tracing.trace.get_current_span().get_span_context().is_valid
            assert tracing.trace.get_current_span() is worker
    finally:
        provider.shutdown()


def test_trace_headers_noop_without_otel(monkeypatch):
    """无 OTel propagator 时 trace_headers 返回空 dict，propagated_trace_context 安全 no-op。"""
    monkeypatch.setattr(tracing, "TraceContextTextMapPropagator", None)
    assert tracing.trace_headers() == {}
    with tracing.propagated_trace_context({"traceparent": "invalid"}):
        pass
