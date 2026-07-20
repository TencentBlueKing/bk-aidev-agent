# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt

from aidev_agent.core.ag_ui.ask_user_question import (
    ASK_USER_QUESTION_REASON,
    AskUserQuestionHandler,
    parse_resume_answers,
)
from aidev_agent.core.ag_ui.types import LangGraphEventTypes

logger = logging.getLogger(__name__)

ASK_USER_QUESTION_TOOL_NAME = "ask_user_question"


class UserQuestionStrategy:
    """ask_user_question 中断策略 —— 封装「向用户提问」的中断全流程。

    中断从 tools 节点 wrapper 移到 ``approval_check`` 节点统一处理（D-02）。
    续流后写 state 返回 ``Command(goto="pv_node")``，让 ToolNode 执行
    ask_user_question 工具函数产生工具返回值（D-06 + D-08）。

    策略实例无 ``__init__``，所有中间变量为 ``interrupt`` 方法内局部变量（D-09）。
    """

    reason = ASK_USER_QUESTION_REASON  # "aidev:user_question"

    def interrupt(self, state: dict, config: RunnableConfig) -> Command | None:
        """ask_user_question 中断策略主入口。

        ``make_interrupt_node`` 已做 D-04 前置检查（messages 非空且末尾
        为含 tool_calls 的 AIMessage）。

        Returns:
            ``None``：无 ask_user_question tool_call（让下一个策略或
            ``make_interrupt_node`` 处理）。
            ``Command``：续流后写 state 返回
            ``Command(update={"ask_user_question_answers": {tool_call_id:
            resolved_answer}}, goto="pv_node")``。

        Raises:
            GraphInterrupt: 首次检测到 ask_user_question tool_call 时，
                通过调用 LangGraph ``interrupt(payload)`` 抛出，图暂停。
        """
        last_message = state["messages"][-1]  # make_interrupt_node 已做前置检查

        # 提取 ask_user_question tool_call（局部变量）
        ask_tool_call = None
        for tc in last_message.tool_calls:
            if tc.get("name") == ASK_USER_QUESTION_TOOL_NAME:
                ask_tool_call = tc
                break
        if not ask_tool_call:
            return None  # 无 ask_user_question，让下一个策略尝试

        # 构造 payload（复刻原 _build_interrupt_payload）
        args = ask_tool_call.get("args") or {}
        questions = args.get("questions") or []
        tool_call_id = ask_tool_call.get("id") or ""
        payload = AskUserQuestionHandler().build_payload(questions=questions, tool_call_id=tool_call_id)

        # dispatch_custom_event + interrupt()（复刻原 _resolve_ask_user_question）
        try:
            dispatch_custom_event(LangGraphEventTypes.OnInterrupt.value, payload, config=config)
        except Exception:
            logger.exception("[AskUserQuestion] dispatch_custom_event failed")

        logger.info(
            "[AskUserQuestion] interrupt() 调用: tool_call_id=%s, questions=%s",
            tool_call_id,
            str(payload.get("metadata", {}).get("questions", ""))[:100],
        )

        answer = interrupt(payload)  # 首次抛 GraphInterrupt，续流返回 answer

        resolved_answer = parse_resume_answers(answer)
        logger.info(
            "[AskUserQuestion] interrupt() 返回: tool_call_id=%s, answer=%s",
            tool_call_id,
            str(resolved_answer)[:200] if resolved_answer else "None",
        )

        # D-07：写入 state 供 ask_user_question 工具函数读取（不再直接返回工具消息，D-06）
        return Command(
            update={"ask_user_question_answers": {tool_call_id: resolved_answer}},
            goto="pv_node",  # D-06：走 pv_node → tools 让 ToolNode 执行工具函数入库
        )


__all__ = ["UserQuestionStrategy", "ASK_USER_QUESTION_TOOL_NAME"]
