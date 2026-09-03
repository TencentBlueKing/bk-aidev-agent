"""企微审批卡片测试使用的脱敏平台响应与回调。"""

import copy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_wxbot.wxaibot.approval_cards import (
    ApprovalCancelAction,
    approval_task_id,
    build_pending_approval_card,
    encode_cancel_event_key,
)


@pytest.fixture(scope="session", autouse=True)
def card_signing_settings():
    """Card signature tests must not depend on a developer's local .env."""
    from django.conf import settings

    settings.SECRET_KEY = "wxbot-test-only-signing-key"


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
def approval_notification_case(approval_card_case, monkeypatch):
    from aidev_wxbot.wxaibot import approval_notifications as module

    case = approval_card_case
    case.record = {
        "role": "interrupt",
        "session_code": case.action.session_code,
        "property": {"builtin_property": {"approve_result": "approved"}},
        "content": {"outcome": {"type": "success", "interrupts": case.result["interrupts"]}},
    }
    case.history = MagicMock(return_value=[case.record])
    manager = MagicMock()
    manager.return_value.list_session_contents = case.history
    monkeypatch.setattr(module, "SessionManager", manager)
    case.messages = lambda: module.approval_result_messages(
        case.action.session_code, [case.action.interrupt_id], "alice"
    )
    return case


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
    case.manager.return_value.list_session_contents.return_value = [
        {
            "role": "interrupt",
            "property": {"turn_id": "turn-1"},
            "content": {"outcome": {"type": "success", "interrupts": case.result["interrupts"]}},
        }
    ]
    case.real_run = mod.AgentExecutor.run_agent_to_completion
    case.run = MagicMock()
    monkeypatch.setattr(mod.AgentExecutor, "run_agent_to_completion", case.run)
    case.executor = MagicMock()
    case.executor.submit.return_value = True
    monkeypatch.setattr(mod, "get_agent_executor", lambda: case.executor)
    case.cleanup = MagicMock()
    monkeypatch.setattr(mod, "close_old_connections", case.cleanup)
    monkeypatch.setattr(mod, "_claimed", mod.BoundedOnceRegistry(16))
    case.module, case.handler = mod, handler
    return case


@pytest.fixture
def persisted_approval_case(approval_resume_case, monkeypatch):
    """Use real state readers with the platform's persisted-content contract."""
    from aidev_agent.services.agent.approval import ApprovalStateHandler

    case = approval_resume_case
    case.record = {
        "id": 1,
        "role": "interrupt",
        "property": {
            "turn_id": "turn-1",
            "builtin_property": {
                "approve_result": "cancelled",
                "graph_thread_id": "graph-1",
            },
        },
        "content": {"outcome": {"type": "success", "interrupts": case.result["interrupts"]}},
    }
    case.api = MagicMock()
    # ChatSessionProperty does not expose pending_interrupt on older platforms.
    case.api.retrieve_chat_session.return_value = {"data": {"session_property": {"labels": []}}}
    case.api.get_chat_session_contents.return_value = {"data": [case.record]}
    monkeypatch.setattr(ApprovalStateHandler, "_get_client", lambda _: SimpleNamespace(api=case.api))
    monkeypatch.setattr(case.module, "ApprovalStateHandler", ApprovalStateHandler)
    case.manager.return_value.list_session_contents.return_value = [case.record]
    return case


@pytest.fixture
def question_case(monkeypatch):
    from aidev_wxbot.wxaibot.question_cards import QuestionAction, questions_digest

    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.question_cards.AgentHelper.build_session_detail_url",
        lambda session_code: f"https://agent.example.com/chat-window/?session={session_code}",
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


@pytest.fixture(params=["single", "multi", "three_single"])
def native_question_case(question_case, request):
    """The three supported native layouts with non-default user selections."""
    from aidev_wxbot.wxaibot.question_cards import questions_digest

    case = question_case
    questions = case.interrupt["metadata"]["questions"]
    questions[0]["multiSelect"] = request.param == "multi"
    if request.param == "three_single":
        questions[:] = [copy.deepcopy(questions[0]) for _ in range(3)]
        for index, question in enumerate(questions, 1):
            question["question"] = f"请选择区域{index}"
    case.selected = {
        "selected_item": [
            {"question_key": f"q{i}", "option_ids": {"option_id": ["1", "0"] if q["multiSelect"] else ["1"]}}
            for i, q in enumerate(questions)
        ]
    }
    case.action = replace(case.action, digest=questions_digest(questions))
    return case


@pytest.fixture(params=[(1, False, 20), (1, True, 20), (2, False, 10), (3, False, 10)])
def protocol_question_case(question_case, request):
    """Native capacity boundaries, with text beyond the old byte-length guards."""
    count, multi, options = request.param
    case = question_case
    case.interrupt["metadata"]["questions"] = [
        {
            "question": f"问题{i}：" + "完整题干" * 30,
            "multiSelect": multi,
            "options": [{"label": f"选项{j}：" + "完整选项" * 10} for j in range(options)],
        }
        for i in range(count)
    ]
    case.selected = {
        "selected_item": [
            {"question_key": f"q{i}", "option_ids": {"option_id": [str(options - 1)]}} for i in range(count)
        ]
    }
    return case
