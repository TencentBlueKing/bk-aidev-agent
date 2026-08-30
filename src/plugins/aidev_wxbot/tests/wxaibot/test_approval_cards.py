"""审批卡片操作结果保留原详情。"""

import copy
import json

import pytest
from aidev_wxbot.wxaibot.approval_cards import build_cancel_result_card


@pytest.mark.parametrize(
    ("status", "label"), [("cancelled", "已取消"), ("approved", "审批已通过"), ("rejected", "审批已拒绝")]
)
def test_result_only_replaces_action_area(approval_card_case, status, label):
    case = approval_card_case
    case.result["approve_result"] = status
    original = copy.deepcopy(case.result)
    card = build_cancel_result_card(case.action, case.task_id, result=case.result)
    expected = {key: value for key, value in case.card.items() if key != "button_list"}
    expected.update(card_type="text_notice", jump_list=[{"type": 0, "title": label}])
    assert card == expected
    assert case.result == original
    assert "must-not-leak" not in json.dumps(card)
    assert "candidate-not-actual-approver" not in json.dumps(card)


@pytest.mark.parametrize("result", [None, [], {}, {"approve_result": []}, {"approve_result": "pending"}])
def test_unknown_result_does_not_replace_original(approval_card_case, result):
    case = approval_card_case
    assert build_cancel_result_card(case.action, case.task_id, result=result) is None


@pytest.mark.parametrize("invalid_part", ["task", "interrupt", "reason", "ticket", "interrupts"])
def test_missing_or_mismatched_details_do_not_replace_original(approval_card_case, invalid_part):
    case = approval_card_case
    interrupt = case.result["interrupts"][0]
    if invalid_part == "task":
        case.task_id = "other-task"
    elif invalid_part == "interrupt":
        interrupt["id"] = "other-approval"
    elif invalid_part == "reason":
        interrupt["reason"] = "other-reason"
    elif invalid_part == "ticket":
        interrupt["metadata"].pop("ticket")
    else:
        case.result["interrupts"] = {}
    assert build_cancel_result_card(case.action, case.task_id, result=case.result) is None
