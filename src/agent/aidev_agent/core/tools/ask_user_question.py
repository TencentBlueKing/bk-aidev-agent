# -*- coding: utf-8 -*-
"""ask_user_question 可执行工具函数

工具函数通过 ``InjectedState`` 读取 ``UserQuestionStrategy.interrupt`` 写入的
答案，通过 ``ToolRuntime`` 获取当前 ``tool_call_id``，返回答案作为
工具返回值。ToolNode 执行此函数后将返回值包装为工具消息入库（修复 12.1
绕过 ToolNode 的 DB 入库断裂）。

设计要点：
- ``questions`` 是 LLM 可见 schema 参数（位置参数第一个），通过 ``Annotated``
  附带描述；不显式传 ``args_schema`` —— ``StructuredTool.from_function`` 自动
  推断 schema 时会排除 ``Annotated[dict, InjectedState]`` 和 ``ToolRuntime``
  类型参数，仅保留 ``questions`` 暴露给 LLM
- ``state`` 和 ``runtime`` 是注入参数（不暴露给 LLM），由 ToolNode 自动注入
- ``tool_call_id`` 从 ``runtime.tool_call_id`` 获取，与
  ``UserQuestionStrategy.interrupt`` 写入 state 的 key
  （``ask_tool_call["id"]``）一致 —— 都来自 ``last_message.tool_calls[i]["id"]``
"""

from __future__ import annotations

from typing import Annotated, Any, List

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import InjectedState, ToolRuntime

from aidev_agent.core.ag_ui.ask_user_question import ASK_USER_QUESTION_REASON


def _ask_user_question(
    questions: Annotated[
        List[dict],
        '问题数组，每项为 {"header": str, "multiSelect": bool, "question": str, "options": [{"label": str, "description": str?}]}。',
    ],
    state: Annotated[dict, InjectedState] = None,
    runtime: ToolRuntime = None,
) -> Any:
    """向用户提问并等待回答。答案由 UserQuestionStrategy.interrupt 写入 state。

    工具函数在续流后由 ToolNode 调用：``UserQuestionStrategy.interrupt``
    已在续流时把用户答案写入 ``state["ask_user_question_answers"][tool_call_id]``，
    本函数读取该答案并返回，ToolNode 将返回值包装为工具消息入库。

    Args:
        questions: 问题数组（LLM 可见参数，已由中断策略处理，此处不使用）。
        state: 注入的图状态，含 ``ask_user_question_answers`` 字段。
        runtime: 工具运行时，提供当前 ``tool_call_id``。

    Returns:
        当前 ``tool_call_id`` 对应的用户答案；无答案时返回空字符串。
    """
    tool_call_id = runtime.tool_call_id if runtime else ""
    answers = (state or {}).get("ask_user_question_answers", {})
    return answers.get(tool_call_id, "")


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
