from unittest.mock import MagicMock

import pytest
from aidev_wxbot.wxaibot import question_resume as mod


@pytest.fixture
def resume_case(question_case, monkeypatch):
    case = question_case
    case.manager = MagicMock()
    case.pending = {"graph_thread_id": "graph-1", "interrupts": [case.interrupt]}
    case.manager.retrieve_session.return_value = {"session_property": {"pending_interrupt": case.pending}}
    case.manager.list_session_contents.return_value = [
        {"role": "interrupt", "property": {"turn_id": "turn-1"}, "content": {"interrupts": [case.interrupt]}}
    ]
    monkeypatch.setattr(mod, "SessionManager", lambda **_: case.manager)
    case.cache = MagicMock()
    case.cache.add.return_value = True
    monkeypatch.setattr(mod, "cache", case.cache)
    case.executor = MagicMock()
    case.executor.submit.return_value = True
    monkeypatch.setattr(mod, "get_agent_executor", lambda: case.executor)
    case.builder, case.run, case.delivery = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(mod, "AgentBuilder", case.builder)
    monkeypatch.setattr(mod.AgentExecutor, "run_agent_to_completion", case.run)
    return case


def test_user_submission_preserves_original_session_thread_turn(resume_case):
    case = resume_case
    submission = mod.prepare_question_submission(case.action, "alice", case.selected)
    assert mod.submit_question_resume(submission, case.delivery) == "accepted"
    callback, *args = case.executor.submit.call_args.args
    callback(*args)
    _, kwargs, session_code, _ = case.run.call_args.args
    assert session_code == kwargs.session_code == "session-1"
    assert kwargs.thread_id == "graph-1" and kwargs.turn_id == "turn-1" and not kwargs.input
    assert kwargs.resume[0]["payload"]["answers"][0]["answer"] == [{"label": "华南"}]
    assert kwargs.resume[0]["interruptId"] == "question-1"
    case.builder.assert_called_once_with(username="alice", turn_id="turn-1")
    case.delivery.finish.assert_called_once()


@pytest.mark.parametrize("change", ["id", "reason", "status", "questions", "expired", "turn", "thread"])
def test_stale_or_expired_question_is_rejected(resume_case, change):
    case = resume_case
    if change in {"id", "reason"}:
        case.interrupt[change] = "different"
    elif change in {"status", "questions"}:
        case.interrupt["metadata"][change] = "resolved" if change == "status" else []
    elif change == "expired":
        case.interrupt["expiresAt"] = "2020-01-01T00:00:00Z"
    elif change == "turn":
        case.manager.list_session_contents.return_value = []
    else:
        case.pending["graph_thread_id"] = ""
    with pytest.raises(ValueError):
        mod.prepare_question_submission(case.action, "alice", case.selected)
    case.executor.submit.assert_not_called()


def test_duplicate_does_not_schedule_another_resume(resume_case):
    case = resume_case
    submission = mod.prepare_question_submission(case.action, "alice", case.selected)
    case.cache.add.return_value = False
    assert mod.submit_question_resume(submission, case.delivery) == "duplicate"
    case.executor.submit.assert_not_called()


def test_capacity_failure_allows_explicit_resubmission(resume_case):
    case = resume_case
    submission = mod.prepare_question_submission(case.action, "alice", case.selected)
    case.executor.submit.return_value = False
    assert mod.submit_question_resume(submission, case.delivery) == "busy"
    case.cache.delete.assert_called_once()


def test_worker_revalidates_pending_and_keeps_uncertain_claim(resume_case, caplog):
    case = resume_case
    submission = mod.prepare_question_submission(case.action, "alice", case.selected)
    case.interrupt["id"] = "another-question"
    mod._question_worker(submission, case.delivery, "test-claim")
    case.builder.assert_not_called()
    case.delivery.failed.assert_called_once()
    case.delivery.finish.assert_called_once()
    case.cache.delete.assert_not_called()


def test_permission_failure_does_not_accept_answers(resume_case):
    case = resume_case
    case.manager.retrieve_session.side_effect = PermissionError("denied")
    with pytest.raises(PermissionError):
        mod.prepare_question_submission(case.action, "alice", case.selected)
    case.executor.submit.assert_not_called()


@pytest.mark.parametrize("flattened", [False, True])
def test_native_card_submission_without_pending_session_property(resume_case, flattened):
    case = resume_case
    case.manager.retrieve_session.return_value = {"session_property": {}}
    record = case.manager.list_session_contents.return_value[0]
    record["content"] = {"outcome": {"type": "interrupt", "interrupts": [case.interrupt]}}
    if flattened:
        record["graph_thread_id"] = "graph-1"
    else:
        record["property"]["builtin_property"] = {"graph_thread_id": "graph-1"}
    submission = mod.prepare_question_submission(case.action, "alice", case.selected)
    mod._question_worker(submission, case.delivery, "test-claim")
    kwargs = case.run.call_args.args[1]
    assert kwargs.thread_id == "graph-1" and kwargs.turn_id == "turn-1"
    assert kwargs.resume[0]["payload"]["answers"][0]["answer"] == [{"label": "华南"}]
    case.delivery.failed.assert_not_called()


@pytest.mark.parametrize("changed", ["resolved", "thread", "new_user"])
def test_native_card_fallback_rejects_finalized_or_superseded_question(resume_case, changed):
    case = resume_case
    case.manager.retrieve_session.return_value = {"session_property": {}}
    records = case.manager.list_session_contents.return_value
    records[0]["content"] = {"outcome": {"type": "interrupt", "interrupts": [case.interrupt]}}
    records[0]["graph_thread_id"] = "graph-1"
    if changed == "resolved":
        records[0]["content"]["outcome"]["type"] = "success"
    elif changed == "thread":
        records[0].pop("graph_thread_id")
    else:
        records.append({"role": "user"})
    with pytest.raises(ValueError):
        mod.prepare_question_submission(case.action, "alice", case.selected)
    case.executor.submit.assert_not_called()
