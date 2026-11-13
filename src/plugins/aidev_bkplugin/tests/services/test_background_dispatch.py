"""Serializable scheduling and trace scope at the worker boundary."""

import json
from unittest.mock import Mock

import pytest
from aidev_bkplugin.services import agent_bkplugin, background_dispatch
from opentelemetry import context, trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags


def test_dispatch_serializes_trace_and_routes_to_worker(monkeypatch):
    task = Mock()
    monkeypatch.setattr(agent_bkplugin, "run_bkplugin_background_agent_task", task)
    runner = agent_bkplugin.BkpluginChat(chat_history=[], execute_kwargs={}, username="user")
    span = NonRecordingSpan(SpanContext(1, 2, False, TraceFlags(1)))
    with trace.use_span(span):
        runner._enqueue_background("session", "turn", {"stream": True})
    kwargs = task.delay.call_args.kwargs
    assert json.loads(json.dumps(kwargs)) == kwargs
    assert kwargs["trace_context"]["traceparent"].endswith("0000000000000002-01")
    task.delay.assert_called_once()


@pytest.mark.parametrize("carrier", [{}, {"traceparent": "00-00000000000000000000000000000001-0000000000000002-01"}])
def test_worker_trace_scope_restores_previous_context(carrier):
    before = context.get_current()
    token = background_dispatch.attach_trace_context(carrier)
    try:
        assert trace.get_current_span().get_span_context().trace_id == (1 if carrier else 0)
    finally:
        background_dispatch.detach_trace_context(token)
    assert context.get_current() == before


def test_legacy_task_keeps_existing_instrumentation_span():
    span = NonRecordingSpan(SpanContext(3, 4, False, TraceFlags(1)))
    with trace.use_span(span):
        token = background_dispatch.attach_trace_context(None)
        try:
            assert trace.get_current_span() is span
        finally:
            background_dispatch.detach_trace_context(token)
