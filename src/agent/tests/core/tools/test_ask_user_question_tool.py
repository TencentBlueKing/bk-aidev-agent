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


# ---------- 脏 questions 兜底（复刻 2.2.1 a14fe8a7：工具层提前归一化 + 空跳过） ----------


def test_tool_skips_when_questions_normalize_to_empty(monkeypatch):
    """LLM 传 None / 空白 str 等归一化后为空 → 直接返回跳过文案，不触发 interrupt。"""
    called = {"interrupt": False}

    def _interrupt(value):
        called["interrupt"] = True
        return []

    monkeypatch.setattr(tool_mod, "interrupt", _interrupt)

    for dirty in (None, "   ", [], [None, 123]):
        result = tool_mod._ask_user_question(questions=dirty)
        assert result == ASK_USER_QUESTION_SKIPPED_CONTENT
    # 归一化后为空时不应进入 interrupt
    assert called["interrupt"] is False


def test_tool_normalizes_str_questions_without_crash(monkeypatch):
    """LLM 把 questions 传成纯字符串 → 归一化成合法 dict 后正常构造 target，不再 500。"""
    captured = {}

    def _interrupt(value):
        captured["value"] = value
        # 模拟用户答复
        return [{"interruptId": "x", "status": "resolved", "payload": {"answers": [{"question": "天气", "answer": []}]}}]

    monkeypatch.setattr(tool_mod, "interrupt", _interrupt)

    result = tool_mod._ask_user_question(questions="今天天气怎么样？")

    # 归一化后的 questions 进入了 interrupt target
    normalized = captured["value"]["questions"]
    assert len(normalized) == 1
    assert normalized[0]["question"] == "今天天气怎么样？"
    # 正常拿到答案返回值
    assert result == [{"question": "天气", "answer": []}]
