"""Polling resumes use the callback's durable parent, including lazy execution."""

from unittest.mock import MagicMock

import pytest
from aidev_agent.services.agent.approval import ApprovalStateHandler
from aidev_agent.utils import tracing
from aidev_bkplugin.services import approval_resume
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def resume_case(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "_agent_tracer", provider.get_tracer("test"))
    monkeypatch.setattr(ApprovalStateHandler, "check_resume", lambda *_: True)
    monkeypatch.setattr(approval_resume, "AgentBuilder", MagicMock())
    executor = MagicMock()
    monkeypatch.setattr(approval_resume, "AgentExecutor", executor)
    seen = []

    def delayed(*args):
        seen.extend([tracing.trace_headers(), args[1].caller_trace_context])
        yield "done"

    executor.return_value.execute_with_save.side_effect = delayed
    yield exporter, seen
    provider.shutdown()


@pytest.mark.parametrize("result", ["approved", "rejected"])
@pytest.mark.parametrize("valid", [True, False])
def test_polling_restores_callback_parent_through_lazy_drain(resume_case, monkeypatch, result, valid):
    exporter, seen = resume_case
    carrier = {"traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01"} if valid else {}
    record = {"property": {"builtin_property": {"approve_result": result, "approval_trace_context": carrier}}}
    monkeypatch.setattr(ApprovalStateHandler, "_get_latest_interrupt_record", lambda *_: record)
    with tracing.recording_span("unrelated-worker") as worker:
        approval_resume._approval_resume_worker("session", "author", "thread", [{"id": "approval"}])
        assert tracing.get_current_trace_id() == format(worker.get_span_context().trace_id, "032x")
    resumed = next(s for s in exporter.get_finished_spans() if s.name == "bkplugin.approval.resume")
    assert resumed.context.trace_id != worker.get_span_context().trace_id
    assert (resumed.parent.span_id if resumed.parent else None) == (int("2" * 16, 16) if valid else None)
    assert seen == [{"traceparent": f"00-{resumed.context.trace_id:032x}-{resumed.context.span_id:016x}-01"}] * 2


@pytest.mark.parametrize("nested", [True, False])
def test_approval_reader_keeps_callback_context_from_same_record(monkeypatch, nested):
    fields = {"approve_result": "approved", "approval_trace_context": {"traceparent": "stored-parent"}}
    record = {"property": {"builtin_property": fields}} if nested else fields
    monkeypatch.setattr(ApprovalStateHandler, "_get_latest_interrupt_record", lambda *_: record)
    assert (
        ApprovalStateHandler().fetch_approve_result("session")["approval_trace_context"]
        == fields["approval_trace_context"]
    )
