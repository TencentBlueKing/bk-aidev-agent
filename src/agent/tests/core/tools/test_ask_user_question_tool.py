# -*- coding: utf-8 -*-
"""ask_user_question 工具跳过返回回归（2026-09-02）。

续流重跑时 ask_user 工具会再次流出 TOOL_CALL_RESULT（AidevAGUIAgent 仅抑制
ask_user 的 TOOL_CALL_START/ARGS/END，RESULT 放行），前端分组对同 toolCallId
的工具消息后写覆盖：跳过（cancelled + 空 answers）若返回空列表，会把装配层
skip 派发的 SKIPPED_CONTENT 工具卡片内容顶成 "[]"（跳过+input 工具样式/内容
丢失）。工具必须对空答案返回跳过文案，与 skip 派发的落库记录保持一致。
"""

from aidev_agent.core.tools import ask_user_question as tool_mod
from aidev_agent.packages.interrupt_manager import ASK_USER_QUESTION_SKIPPED_CONTENT


def test_tool_returns_skip_content_on_cancelled_resume(monkeypatch):
    """cancelled resume（空 answers）→ 工具返回 SKIPPED_CONTENT 而非 []。"""
    cancelled = [{"interruptId": "x", "status": "cancelled", "payload": {"answers": []}}]
    monkeypatch.setattr(tool_mod, "interrupt", lambda value: cancelled)

    result = tool_mod._ask_user_question(questions=[{"header": "h", "question": "q"}])

    assert result == ASK_USER_QUESTION_SKIPPED_CONTENT


def test_tool_returns_parsed_answers_on_resolved_resume(monkeypatch):
    """resolved resume → 工具照常返回解析后的用户答案。"""
    answers = [{"question": "q", "multiSelect": False, "answer": [{"label": "A", "description": "a"}]}]
    resolved = [{"interruptId": "x", "status": "resolved", "payload": {"answers": answers}}]
    monkeypatch.setattr(tool_mod, "interrupt", lambda value: resolved)

    result = tool_mod._ask_user_question(questions=[{"header": "h", "question": "q"}])

    assert result == answers
