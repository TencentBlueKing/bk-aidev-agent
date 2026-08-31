import copy
import json
from unittest.mock import patch

import pytest
from aidev_wxbot.wxaibot.approval_cards import build_approval_result_card


@pytest.mark.parametrize("status,label", [("approved", "审批已通过"), ("rejected", "审批已拒绝")])
@pytest.mark.parametrize("flattened", [False, True])
def test_notice_and_old_card_use_identical_result(approval_notification_case, status, label, flattened):
    case = approval_notification_case
    case.record["property"]["builtin_property"]["approve_result"] = status
    if flattened:
        case.record.update(case.record.pop("property")["builtin_property"])
    case.result["approve_result"] = status
    updated = build_approval_result_card(case.action, case.task_id, result=case.result)
    updated.pop("task_id")
    assert case.messages() == [{"msgtype": "template_card", "template_card": updated}]
    assert updated["jump_list"] == [{"type": 0, "title": label}]
    assert "button_list" not in updated
    assert "candidate-not-actual-approver" not in json.dumps(updated)
    assert "must-not-leak" not in json.dumps(updated)


def test_delayed_event_uses_original_approval_not_latest_question(approval_notification_case):
    case = approval_notification_case
    later = copy.deepcopy(case.record)
    later["content"]["outcome"]["interrupts"][0]["id"] = "other-interrupt"
    later["property"]["builtin_property"]["approve_result"] = "rejected"
    case.history.return_value.append(later)
    assert case.messages()[0]["template_card"]["jump_list"][0]["title"] == "审批已通过"


@pytest.mark.parametrize("skip", ["cancelled", "question"])
def test_unrelated_or_cancelled_record_sends_no_approval_notice(approval_notification_case, skip):
    case = approval_notification_case
    interrupt = case.record["content"]["outcome"]["interrupts"][0]
    if skip == "cancelled":
        case.record["property"]["builtin_property"]["approve_result"] = "cancelled"
    elif skip == "question":
        interrupt["reason"] = "aidev:user_question"
    assert case.messages() == []


@pytest.mark.parametrize("missing", ["other_session", "other_interrupt", "user", "empty"])
def test_missing_original_history_is_retried(approval_notification_case, missing):
    case = approval_notification_case
    if missing == "other_session":
        case.record["session_code"] = "other-session"
    elif missing == "other_interrupt":
        case.record["content"]["outcome"]["interrupts"][0]["id"] = "other-interrupt"
    elif missing == "user":
        case.record["role"] = "user"
    else:
        case.history.return_value = []
    with pytest.raises(ValueError, match="history"):
        case.messages()


@pytest.mark.parametrize("invalid", ["pending", "conflict", "ticket", "history"])
def test_invalid_decision_is_not_acknowledged_as_approved(approval_notification_case, invalid):
    case = approval_notification_case
    if invalid == "pending":
        case.record["property"]["builtin_property"]["approve_result"] = "pending"
    elif invalid == "conflict":
        conflict = copy.deepcopy(case.record)
        conflict["property"]["builtin_property"]["approve_result"] = "rejected"
        case.history.return_value.append(conflict)
    elif invalid == "ticket":
        case.record["content"]["outcome"]["interrupts"][0]["metadata"].pop("ticket")
    else:
        case.history.return_value = {"unexpected": "history"}
    with pytest.raises(ValueError):
        case.messages()


def test_notice_lookup_forwards_original_user_without_creating_session(approval_notification_case):
    from aidev_wxbot.wxaibot.approval_notifications import approval_result_messages

    case = approval_notification_case
    with patch("aidev_wxbot.wxaibot.approval_notifications.SessionManager") as manager:
        manager.return_value.list_session_contents.return_value = [case.record]
        assert approval_result_messages("session-1", [case.action.interrupt_id], "alice")
    manager.assert_called_once_with(username="alice")
    manager.return_value.list_session_contents.assert_called_once_with("session-1")
    manager.return_value.get_or_create_by_session_code.assert_not_called()
