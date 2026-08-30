"""审批卡片操作结果保留原详情。"""

import copy
import json

import pytest
from aidev_wxbot.wxaibot.approval_cards import build_cancel_result_card, build_pending_approval_card


@pytest.mark.parametrize(
    "session_url",
    [
        "https://agent.example.com/chat-window/?session=session-1",
        "http://agent.example.com/",
        "",
        "/session/1",
        "javascript:void(0)",
    ],
)
def test_pending_card_has_separate_safe_web_session_link(approval_card_case, monkeypatch, session_url):
    case = approval_card_case
    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.approval_cards.AgentHelper.build_session_detail_url", lambda _session: session_url
    )
    card = build_pending_approval_card(
        {"outcome": {"type": "interrupt", "interrupts": case.result["interrupts"]}}, case.action.session_code
    )
    links = [row for row in card["horizontal_content_list"] if row.get("type") == 1]
    expected = [{"keyname": "会话", "value": "查看会话", "type": 1, "url": session_url}]
    assert links == (expected if session_url.startswith(("https://", "http://")) else [])
    assert card["card_action"] == case.card["card_action"]
    assert card["button_list"] == case.card["button_list"]


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
    assert card["horizontal_content_list"][-1] == {
        "keyname": "会话",
        "value": "查看会话",
        "type": 1,
        "url": "https://agent.example.com/session-1",
    }
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
