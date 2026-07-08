# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Protocol, runtime_checkable

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command


@runtime_checkable
class InterruptionStrategy(Protocol):
    """单方法中断策略协议。

    每个策略封装一种中断的完整生命周期（触发检测 → payload 构造 →
    interrupt 调用 → 续流解析 → 后处理）在 ``interrupt`` 一个方法内。

    ``make_interrupt_node`` 在按顺序调用
    ``strategy.interrupt(state, config)``，None 表示无中断继续下一个，
    Command 表示短路返回。

    策略实例在 ``interrupt`` 方法内使用局部变量承载所有中间状态，
    不通过实例属性缓存跨调用数据（D-09）。
    """

    reason: str
    """中断 reason 字符串（如 ``aidev:tool_approval``、``aidev:user_question``）。"""

    def interrupt(self, state: dict, config: RunnableConfig) -> Command | None:
        """单方法中断策略。

        Args:
            state: 当前图状态（``make_interrupt_node`` 已做前置检查，
                ``state["messages"]`` 非空且末尾为含 tool_calls 的 AIMessage）。
            config: RunnableConfig。

        Returns:
            ``None``：策略无中断可做（如 approval 无 pending target、
            ask_user_question 无匹配 tool_call），``make_interrupt_node``
            继续下一个策略。
            ``Command``：策略处理完续流后续，``make_interrupt_node`` 短路返回。

        Raises:
            GraphInterrupt: 策略检测到需要中断时，通过调用 LangGraph
                ``interrupt(payload)`` 函数间接抛出，图暂停。
        """
        ...


__all__ = ["InterruptionStrategy"]
