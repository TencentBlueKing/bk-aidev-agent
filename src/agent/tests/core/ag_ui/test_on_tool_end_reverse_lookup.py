# -*- coding: utf-8 -*-
"""D-08（根因 D）：OnToolEnd 补发的 TOOL_CALL_START 其 parent_message_id 反查测试。

OnToolEnd 补发分支（``has_function_streaming=False``）原用 ToolMessage.id 作为
parent_message_id，导致 tool_call 挂到错误的父消息。本测试验证修正后从
``active_run["current_graph_state"]["messages"]`` 反查该 tool_call 所属 AIMessage.id，
未命中时回退原 id（防御）。
"""

import asyncio

from ag_ui.core import EventType
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command


def _collect_events(agent: AidevAGUIAgent, event: dict) -> list:
    """异步迭代 _handle_on_tool_end_event 收集全部产出事件。"""
    return asyncio.run(_async_collect(agent, event))


async def _async_collect(agent: AidevAGUIAgent, event: dict) -> list:
    return [ev async for ev in agent._handle_on_tool_end_event(event)]


class _StubGraph:
    """构造用 graph 桩（仅存储不遍历）。"""


_STUB_GRAPH = _StubGraph()


def _make_agent(messages: list) -> AidevAGUIAgent:
    """构造 AidevAGUIAgent 实例，手动装配 active_run 供 OnToolEnd 反查。"""
    agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
    agent.active_run = {
        "has_function_streaming": False,
        "current_graph_state": {"messages": messages},
    }
    return agent


def _on_tool_end_event_with_command(tool_msg: ToolMessage) -> dict:
    """构造 OnToolEnd 原始事件（Command 分支：output 为 Command 携带 ToolMessage）。"""
    command = Command(update={"messages": [tool_msg]})
    return {"data": {"output": command, "input": {}}}


def _on_tool_end_event_with_output(tool_msg: ToolMessage) -> dict:
    """构造 OnToolEnd 原始事件（非 Command 分支：output 直接为 ToolMessage）。"""
    return {"data": {"output": tool_msg, "input": {}}}


class TestOnToolEndReverseLookup:
    def test_command_path_parent_message_id_is_aimessage_id(self):
        """Command 分支：补发 TOOL_CALL_START 的 parent_message_id 反查为 AIMessage.id。"""
        ai_msg = AIMessage(content="", tool_calls=[{"id": "call_t1", "name": "tool1", "args": {}}], id="assist-1")
        tool_msg = ToolMessage(content="ok", tool_call_id="call_t1", id="tool-msg-1", name="tool1")
        agent = _make_agent([ai_msg])

        events = _collect_events(agent, _on_tool_end_event_with_command(tool_msg))
        start = next(ev for ev in events if ev.type == EventType.TOOL_CALL_START)
        assert start.parent_message_id == "assist-1", (
            f"parent_message_id 应为 AIMessage.id，而非 ToolMessage.id，实际={start.parent_message_id}"
        )
        assert start.tool_call_id == "call_t1"
        assert start.tool_call_name == "tool1"

    def test_output_path_parent_message_id_is_aimessage_id(self):
        """非 Command 分支：output 直接为 ToolMessage，parent_message_id 反查为 AIMessage.id。"""
        ai_msg = AIMessage(content="", tool_calls=[{"id": "call_t2", "name": "tool2", "args": {}}], id="assist-2")
        tool_msg = ToolMessage(content="ok", tool_call_id="call_t2", id="tool-msg-2", name="tool2")
        agent = _make_agent([ai_msg])

        events = _collect_events(agent, _on_tool_end_event_with_output(tool_msg))
        start = next(ev for ev in events if ev.type == EventType.TOOL_CALL_START)
        assert start.parent_message_id == "assist-2", (
            f"parent_message_id 应为 AIMessage.id，实际={start.parent_message_id}"
        )

    def test_no_matching_aimessage_falls_back_to_tool_msg_id(self):
        """无匹配 AIMessage（current_graph_state 缺失/空）→ 回退原 tool_msg.id（防御，不抛错）。"""
        tool_msg = ToolMessage(content="ok", tool_call_id="call_t3", id="tool-msg-3", name="tool3")
        # current_graph_state 完全缺失
        agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
        agent.active_run = {"has_function_streaming": False}

        events = _collect_events(agent, _on_tool_end_event_with_command(tool_msg))
        start = next(ev for ev in events if ev.type == EventType.TOOL_CALL_START)
        assert start.parent_message_id == "tool-msg-3", "未命中反查应回退原 tool_msg.id"

    def test_absent_graph_state_messages_does_not_raise(self):
        """current_graph_state.messages 为空/缺失时 helper 返回 None（不抛错）。"""
        agent = _make_agent([])
        tool_msg = ToolMessage(content="ok", tool_call_id="call_t4", id="tool-msg-4", name="tool4")
        events = _collect_events(agent, _on_tool_end_event_with_output(tool_msg))
        start = next(ev for ev in events if ev.type == EventType.TOOL_CALL_START)
        assert start.parent_message_id == "tool-msg-4"

    def test_has_function_streaming_true_skips_replay(self):
        """流式路径（has_function_streaming=True）不补发 TOOL_CALL_START（保持现状）。"""
        agent = _make_agent([])
        agent.active_run["has_function_streaming"] = True
        tool_msg = ToolMessage(content="ok", tool_call_id="call_t5", id="tool-msg-5", name="tool5")
        events = _collect_events(agent, _on_tool_end_event_with_output(tool_msg))
        assert not any(ev.type == EventType.TOOL_CALL_START for ev in events)
