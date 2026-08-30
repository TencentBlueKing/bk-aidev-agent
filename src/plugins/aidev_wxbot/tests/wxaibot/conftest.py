"""企微审批卡片测试使用的脱敏平台响应与回调。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

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
    action = ApprovalCancelAction("session-1", "int-approval-call-1-DE001", "alice-wx")
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
    envelope = {
        "ok": True,
        "result": result,
        "next": {
            "endpoint": "chat_completion",
            "payload": {"session_code": action.session_code, "execute_kwargs": {"stream": True}},
        },
    }
    return SimpleNamespace(action=action, task_id=task_id, result=result, card=card, event=event, envelope=envelope)


@pytest.fixture
def approval_resume_case(approval_card_case, monkeypatch):
    from aidev_wxbot.wxaibot import approval_resume as mod

    case = approval_card_case
    real_hydrate = mod.ApprovalStateHandler.hydrate_resume_payload
    handler_type = MagicMock()
    handler = handler_type.return_value
    handler.hydrate_resume_payload.side_effect = real_hydrate
    handler.get_pending_interrupt_context.return_value = {
        "graph_thread_id": "graph-1",
        "interrupts": case.result["interrupts"],
    }
    handler.fetch_approve_result.return_value = case.result
    monkeypatch.setattr(mod, "ApprovalStateHandler", handler_type)
    case.builder = MagicMock()
    monkeypatch.setattr(mod, "AgentBuilder", case.builder)
    case.manager = MagicMock()
    monkeypatch.setattr(mod, "SessionManager", case.manager)
    case.real_run = mod.AgentExecutor.run_agent_to_completion
    case.run = MagicMock()
    monkeypatch.setattr(mod.AgentExecutor, "run_agent_to_completion", case.run)
    case.executor = MagicMock()
    case.executor.submit.return_value = True
    monkeypatch.setattr(mod, "get_agent_executor", lambda: case.executor)
    case.cleanup = MagicMock()
    monkeypatch.setattr(mod, "close_old_connections", case.cleanup)
    monkeypatch.setattr(mod, "_pending", set())
    case.module, case.handler = mod, handler
    return case


@pytest.fixture
def question_case(monkeypatch):
    from aidev_wxbot.wxaibot.question_cards import QuestionAction, questions_digest

    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.question_cards.AgentHelper.build_session_detail_url",
        lambda session: f"https://agent.example.com/{session}",
    )
    questions = [
        {
            "header": "区域",
            "question": "请选择区域",
            "multiSelect": False,
            "options": [{"label": "华南"}, {"label": "华东"}],
        }
    ]
    interrupt = {
        "id": "question-1",
        "reason": "aidev:user_question",
        "metadata": {"status": "pending", "type": "ask_user_question", "questions": questions},
    }
    action = QuestionAction("session-1", "question-1", questions_digest(questions), "alice-wx")
    return SimpleNamespace(
        interrupt=interrupt,
        action=action,
        event={"type": "RUN_FINISHED", "outcome": {"type": "interrupt", "interrupts": [interrupt]}},
        selected={"selected_item": [{"question_key": "q0", "option_ids": {"option_id": ["0"]}}]},
    )
