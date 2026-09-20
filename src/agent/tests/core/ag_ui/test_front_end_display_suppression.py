# -*- coding: utf-8 -*-
"""消费端 front_end_display 抑制回归。

生产侧 read_image 在视觉模型调用期间派发 ``front_end_display=False``，
本测试直接驱动 ``_handle_on_chat_model_end_event``，锁定该标志位在消费端
真的抑制落库载荷（ChatModelEnd CustomEvent）——即「派发序列正确」等价于
「落库路径被抑制」的直接证据。
"""

import asyncio

from aidev_agent.core.ag_ui.agent import LangGraphAgent
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from langchain_core.messages import AIMessage


def _make_agent(front_end_display: bool) -> LangGraphAgent:
    """构造最小可运行 _handle_on_chat_model_end_event 的 agent（__new__ + 显式属性）。"""
    agent = LangGraphAgent.__new__(LangGraphAgent)
    agent.front_end_display = front_end_display
    agent.messages_in_process = {"run-1": None}
    agent.active_run = {"id": "run-1", "thread_id": "t-1", "has_function_streaming": False, "has_text_output": False}
    agent._tool_mapping = {}
    return agent


def _end_event() -> dict:
    """构造 OnChatModelEnd 原始事件（output 为视觉模型风格的单条 AIMessage）。"""
    return {"event": "on_chat_model_end", "data": {"output": AIMessage(content="识别结果")}}


async def _async_collect(agent: LangGraphAgent, event: dict) -> list:
    return [ev async for ev in agent._handle_on_chat_model_end_event(event)]


def _chat_model_end_events(events: list) -> list:
    """筛出 name 为 ChatModelEnd 的 CustomEvent。"""
    return [e for e in events if getattr(e, "name", None) == SessionPersistenceEventNames.ChatModelEnd.value]


def test_end_event_produces_nothing_when_display_disabled():
    """front_end_display=False 时 OnChatModelEnd 零产出（落库载荷被抑制）。"""
    events = asyncio.run(_async_collect(_make_agent(front_end_display=False), _end_event()))
    assert events == []


def test_end_event_emits_chat_model_end_when_display_restored():
    """恢复 front_end_display=True 后同一事件产出 ChatModelEnd CustomEvent。"""
    events = asyncio.run(_async_collect(_make_agent(front_end_display=True), _end_event()))
    assert len(_chat_model_end_events(events)) == 1


def test_same_event_suppressed_then_emitted_after_flag_toggle():
    """同一 event 在标志位翻转前后分别零产出与产出，证明抑制来源于该标志位。"""
    suppressed = asyncio.run(_async_collect(_make_agent(front_end_display=False), _end_event()))
    emitted = asyncio.run(_async_collect(_make_agent(front_end_display=True), _end_event()))

    assert _chat_model_end_events(suppressed) == []
    assert len(_chat_model_end_events(emitted)) == 1
