# -*- coding: utf-8 -*-
"""ask_user_question 可执行工具函数

工具函数本体**直接调用 LangGraph 原生 ``interrupt()``**（D-12，工具内直调）：
构造 ``AskUserQuestionTarget`` → ``interrupt(target.model_dump())`` 暂停图 →
用户回答后续流恢复 → ``parse_resume_answers(answer)`` 把用户答案直接作为
工具返回值。ToolNode 执行此函数后将返回值包装为工具消息入库。

设计要点：
- ``questions`` 是 LLM 可见 schema 参数（位置参数第一个），通过 ``Annotated``
  附带描述；不显式传 ``args_schema`` —— ``StructuredTool.from_function`` 自动
  推断 schema 时会排除 ``ToolRuntime`` 类型参数，仅保留 ``questions`` 暴露给 LLM
- ``runtime`` 是注入参数（不暴露给 LLM），由 ToolNode 自动注入
- ``tool_call_id`` 从 ``runtime.tool_call_id`` 获取，用于构造 ``AskUserQuestionTarget``
- **interrupt() 前零副作用**（Pitfall 3）：只构造 target，答案全在返回后处理，
  由 ToolNode 统一包装入库，保证续流重执行非幂等副作用不重复发生
- 依赖方向：工具层（core/tools）只 import packages/interrupt_manager（packages 红线）；
  interrupt 用 langgraph 原生实现，不 import core 类型
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, List

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt

from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_REASON,
    ASK_USER_QUESTION_SKIPPED_CONTENT,
)
from aidev_agent.packages.interrupt_manager.ask_user_question import (
    AskUserQuestionTarget,
    parse_resume_answers,
)


def _ask_user_question(  # nosemgrep: aidev-no-bare-any  (返回值为用户提交的任意答案结构)
    questions: Annotated[
        List[dict],
        '问题数组，每项为 {"header": str, "multiSelect": bool, "question": str, "options": [{"label": str, "description": str?}]}。',
    ],
    runtime: ToolRuntime = None,
) -> Any:
    """向用户提问并等待回答。答案由 interrupt() 续流后直接作为工具返回值。

    工具函数在 ToolNode 内运行：首次调用构造 ``AskUserQuestionTarget`` 并
    ``interrupt(target.model_dump())`` 暂停图；用户回答后续流恢复，本函数从头
    重执行，``interrupt()`` 返回用户答案，经 ``parse_resume_answers`` 处理后
    直接作为工具返回值（由 ToolNode 包装为工具消息入库）。

    Args:
        questions: 问题数组（LLM 可见参数）。
        runtime: 工具运行时，提供当前 ``tool_call_id``。

    Returns:
        用户答案（经 ``parse_resume_answers`` 提取）；跳过/取消（空答案）时返回
        ``ASK_USER_QUESTION_SKIPPED_CONTENT`` 文案，供 LLM 继续推理。
    """
    tool_call_id = runtime.tool_call_id if runtime else ""
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    target = AskUserQuestionTarget(
        questions=questions,
        message="请求用户回答以下问题",
        toolCallId=tool_call_id,
        expiresAt=expires_at,
    )
    # 首次 GraphInterrupt 暂停图；续流工具函数从头重执行并拿到用户答案
    answer = interrupt(target.model_dump())
    answers = parse_resume_answers(answer)
    if not answers:
        # 跳过/取消（cancelled + 空 answers）：返回跳过文案而非空列表。
        # 续流重跑会为该 tool_call 再次流出 TOOL_CALL_RESULT（ask_user 仅抑制
        # START/ARGS/END，RESULT 放行），前端分组对同 toolCallId 的工具消息
        # 后写覆盖——返回空列表会把装配层 skip 派发的 SKIPPED_CONTENT 工具
        # 卡片内容顶成 "[]"（工具样式/内容丢失）；返回跳过文案则两处一致，
        # 且 LLM 能拿到有意义的跳过上下文（2026-09-02 跳过路径回归）。
        return ASK_USER_QUESTION_SKIPPED_CONTENT
    # 答案直接作为工具返回值（ToolNode 包装为 ToolMessage 入库）
    return answers


ask_user_question = StructuredTool.from_function(
    func=_ask_user_question,
    name="ask_user_question",
    description=(
        "向用户提问并等待回答。当 Agent 需要用户澄清或做出选择时调用此工具。"
        "工具内部通过 interrupt() 暂停图执行，用户回答后续流恢复。"
        "续流时返回的用户答案会作为工具返回值返回给 LLM。"
    ),
)


__all__ = ["ask_user_question", "ASK_USER_QUESTION_REASON"]
