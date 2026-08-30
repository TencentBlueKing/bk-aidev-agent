"""取消审批后续流：只执行一次、沿用原会话、后台写回，不重复执行工具。"""

from contextvars import ContextVar
from unittest.mock import MagicMock

import pytest


def test_cancel_resume_wires_delivery_without_creating_new_turn(approval_resume_case):
    case = approval_resume_case
    case.manager.return_value.list_session_contents.return_value = [
        {"role": "interrupt", "property": {"turn_id": "turn-1"}, "content": {"interrupts": case.result["interrupts"]}}
    ]
    delivery = MagicMock()
    case.module._resume_worker(case.action, "alice", delivery)
    consumer = case.run.call_args.kwargs["consume_stream"]
    output = iter(())
    consumer(output)
    delivery.consume.assert_called_once_with(
        output, "session-1", case.action.interrupt_id, "turn-1", thread_id="graph-1"
    )
    assert case.run.call_args.args[1].turn_id == "turn-1"
    delivery.finish.assert_called_once()


def test_duplicate_cancel_closes_unused_delivery(approval_resume_case):
    case = approval_resume_case
    delivery = MagicMock()
    case.module._pending.add(case.action)
    assert case.module.submit_cancelled_approval_resume(case.action, "alice", case.envelope, delivery)
    case.executor.submit.assert_not_called()
    delivery.finish.assert_called_once()


@pytest.mark.parametrize(
    "invalid", ["failed", "approved", "already_finalized", "endpoint", "session", "next", "result"]
)
def test_only_successful_cancel_can_schedule(approval_resume_case, invalid):
    case = approval_resume_case
    if invalid == "failed":
        case.envelope["ok"] = False
    elif invalid == "approved":
        case.result["approve_result"] = "approved"
    elif invalid == "already_finalized":
        case.result["already_finalized"] = True
    elif invalid == "endpoint":
        case.envelope["next"]["endpoint"] = "https://untrusted.example.com"
    elif invalid == "session":
        case.envelope["next"]["payload"]["session_code"] = "other-session"
    else:
        case.envelope[invalid] = None
    assert not case.module.submit_cancelled_approval_resume(case.action, "alice", case.envelope)
    case.executor.submit.assert_not_called()


def test_repeated_callback_is_deduplicated_until_worker_finishes(approval_resume_case):
    case = approval_resume_case
    for _ in range(2):
        assert case.module.submit_cancelled_approval_resume(case.action, "alice", case.envelope)
    case.executor.submit.assert_called_once()
    callback, *args = case.executor.submit.call_args.args
    callback(*args)
    case.run.assert_called_once()
    assert not case.module._pending
    assert case.cleanup.call_count == 2


@pytest.mark.parametrize("raises", [False, True])
def test_failed_submission_releases_dedup_entry(approval_resume_case, raises):
    case = approval_resume_case
    case.executor.submit.return_value = False
    if raises:
        case.executor.submit.side_effect = RuntimeError("executor unavailable")
        with pytest.raises(RuntimeError):
            case.module.submit_cancelled_approval_resume(case.action, "alice", case.envelope)
    else:
        assert not case.module.submit_cancelled_approval_resume(case.action, "alice", case.envelope)
    assert not case.module._pending


def test_resume_uses_original_session_and_denies_cancelled_tool(approval_resume_case):
    case = approval_resume_case
    case.module._resume_worker(case.action, "alice")
    case.builder.assert_called_once_with(username="alice")
    case.builder.return_value.by_session_code.assert_called_once_with("session-1", channel_type="rtx")
    _, kwargs, session_code, _ = case.run.call_args.args
    assert session_code == kwargs.session_code == "session-1"
    assert kwargs.thread_id == "graph-1"
    assert kwargs.stream and not kwargs.input
    assert kwargs.executor == "alice"
    assert kwargs.resume == [
        {"interruptId": case.action.interrupt_id, "status": "cancelled", "payload": {"approved": False}}
    ]


def test_background_execution_consumes_stream_and_saves_reply(approval_resume_case):
    case = approval_resume_case
    agent = case.builder.return_value.by_session_code.return_value
    agent.event_handler = None
    agent.execute.return_value = iter(['data: {"event":"text","content":"已跳过取消的工具，继续处理。"}\n'])
    case.run.side_effect = case.real_run
    case.module._resume_worker(case.action, "alice")
    assert agent.execute.call_args.args[0].background_only
    case.manager.return_value.save_content.assert_called_once()
    saved = case.manager.return_value.save_content.call_args.kwargs
    assert saved["session_code"] == "session-1"
    assert saved["content"] == "已跳过取消的工具，继续处理。"


@pytest.mark.parametrize("changed", ["pending", "thread", "interrupt", "approved", "result"])
def test_worker_does_not_replay_old_approval(approval_resume_case, changed):
    case = approval_resume_case
    pending = case.handler.get_pending_interrupt_context.return_value
    if changed == "pending":
        pending.clear()
    elif changed == "thread":
        pending["graph_thread_id"] = ""
    elif changed == "interrupt":
        pending["interrupts"] = [{"id": "another", "reason": "aidev:tool_approval"}]
    elif changed == "approved":
        case.result["approve_result"] = "approved"
    else:
        case.handler.fetch_approve_result.return_value = None
    case.module._resume_worker(case.action, "alice")
    case.builder.assert_not_called()
    assert case.cleanup.call_count == 2


def test_resume_failure_is_sanitized_and_releases_worker_state(approval_resume_case, caplog):
    case = approval_resume_case
    case.run.side_effect = RuntimeError("secret-in-upstream-error")
    case.module._pending.add(case.action)
    case.module._resume_worker(case.action, "alice")
    assert "secret-in-upstream-error" not in caplog.text
    assert "wxbot_approval_resume_failed" in caplog.text
    assert not case.module._pending
    assert case.cleanup.call_count == 2


def test_submission_propagates_context_to_worker(approval_resume_case, monkeypatch):
    case = approval_resume_case
    trace = ContextVar("test_approval_trace", default="")
    observed = []
    monkeypatch.setattr(case.module, "_resume_cancelled_approval", lambda *_: observed.append(trace.get()))
    token = trace.set("callback-trace")
    try:
        case.module.submit_cancelled_approval_resume(case.action, "alice", case.envelope)
    finally:
        trace.reset(token)
    callback, *args = case.executor.submit.call_args.args
    callback(*args)
    assert observed == ["callback-trace"]


def test_resume_span_and_agent_traceparent_follow_callback(approval_resume_case, wxbot_spans):
    from aidev_wxbot.wxaibot.tracing import received_message_span

    case = approval_resume_case
    with received_message_span({"body": {"msgtype": "event"}}):
        case.module.submit_cancelled_approval_resume(case.action, "alice", case.envelope)
    callback, *args = case.executor.submit.call_args.args
    callback(*args)
    spans = {span.name: span for span in wxbot_spans.get_finished_spans()}
    parent = spans["wxbot.message.receive"]
    resumed = spans["wxbot.approval.resume"]
    assert resumed.parent.span_id == parent.context.span_id
    assert resumed.context.trace_id == parent.context.trace_id
    kwargs = case.run.call_args.args[1]
    assert kwargs.caller_trace_context["traceparent"].split("-")[1] == f"{parent.context.trace_id:032x}"
    assert "alice" not in resumed.to_json()
