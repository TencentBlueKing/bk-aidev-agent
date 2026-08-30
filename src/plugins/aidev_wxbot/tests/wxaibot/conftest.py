"""企微审批卡片测试使用的脱敏平台响应与回调。"""

from types import SimpleNamespace

import pytest
from aidev_wxbot.wxaibot.approval_cards import (
    ApprovalCancelAction,
    approval_task_id,
    build_pending_approval_card,
    encode_cancel_event_key,
)


@pytest.fixture
def approval_card_case(monkeypatch):
    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.approval_cards.AgentHelper.build_session_detail_url",
        lambda _session: "https://agent.example.com/session-1",
    )
    action = ApprovalCancelAction("session-1", "int-approval-call-1-DE001")
    task_id = approval_task_id(action)
    interrupt = {
        "id": action.interrupt_id,
        "reason": "aidev:tool_approval",
        "callbackToken": "must-not-leak",
        "metadata": {
            "ticket": {
                "title": "执行工具需要审批",
                "sn": "DE001",
                "submit_time": "2026-01-01T00:00:00+00:00",
                "url": "https://approval.example.com/#/ticket?type=ticket&ticketId=123",
                "approvers": ["candidate-not-actual-approver"],
            }
        },
    }
    card = build_pending_approval_card(
        {"outcome": {"type": "interrupt", "interrupts": [interrupt]}}, action.session_code
    )
    event = {
        "msgtype": "event",
        "from": {"userid": "alice-wx"},
        "event": {
            "eventtype": "template_card_event",
            "template_card_event": {
                "event_key": encode_cancel_event_key(action),
                "task_id": task_id,
            },
        },
    }
    result = {"approve_result": "cancelled", "interrupts": [interrupt]}
    return SimpleNamespace(action=action, task_id=task_id, result=result, card=card, event=event)
