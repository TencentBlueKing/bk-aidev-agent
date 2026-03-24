# -*- coding: utf-8 -*-
"""
测试 json_repair_wrapper 功能
"""

from typing import List
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.nodes.tool.json_repair_wrapper import (
    _is_validation_error,
    _repair_args,
    _try_parse_json_string,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict


class AgentState(TypedDict):
    messages: Annotated[List, add_messages]


@tool
def greet_tool(name: str) -> str:
    """Greet by name."""
    return f"Hello, {name}!"


@tool
def struct_tool(config: dict) -> str:
    """Accept a config dict and return its string representation."""
    return str(config)


def run_tool_node(tool_node, state: dict) -> dict:
    graph = StateGraph(AgentState)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile()
    return compiled.invoke(state)


async def arun_tool_node(tool_node, state: dict) -> dict:
    graph = StateGraph(AgentState)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile()
    return await compiled.ainvoke(state)


# ============================================================================
# 单元测试：_try_parse_json_string
# ============================================================================


class TestTryParseJsonString:
    @pytest.mark.parametrize(
        "value,expect_ok,expect_type",
        [
            ('{"key": "value"}', True, dict),
            ('["a", "b"]', True, list),
            ('{"key": "value"', True, dict),  # 损坏的 JSON 对象
            ("[1, 2, 3", True, list),  # 损坏的 JSON 数组
            ("{not_json_at_all!!!", False, None),  # 非 JSON，类型不一致
        ],
    )
    def test_parse(self, value, expect_ok, expect_type):
        ok, result = _try_parse_json_string(value)
        assert ok is expect_ok
        if expect_ok:
            assert isinstance(result, expect_type)


# ============================================================================
# 单元测试：_repair_args
# ============================================================================


class TestRepairArgs:
    @pytest.mark.parametrize(
        "args,expected",
        [
            # 非字符串值不修改
            ({"a": 1, "b": True}, {"a": 1, "b": True}),
            # 不以 { / [ 开头的字符串不修改
            ({"name": "Alice"}, {"name": "Alice"}),
            # 合法 JSON 对象字符串 → dict
            ({"data": '{"key": "value"}'}, {"data": {"key": "value"}}),
            # 合法 JSON 数组字符串 → list
            ({"items": '["a", "b"]'}, {"items": ["a", "b"]}),
            # 损坏的 JSON 字符串经修复 → dict
            ({"data": '{"key": "value"'}, {"data": {"key": "value"}}),
            # 混合场景：部分修复
            ({"name": "Alice", "cfg": '{"x": 1}'}, {"name": "Alice", "cfg": {"x": 1}}),
            # 以 { 开头但无法解析为结构化数据 → 保持原样
            ({"tpl": "{not_json_at_all!!!"}, {"tpl": "{not_json_at_all!!!"}),
        ],
    )
    def test_repair_args(self, args, expected):
        assert _repair_args(args) == expected

    def test_no_change_returns_same_object(self):
        """无需修复时应返回原 dict 对象"""
        args = {"a": 1, "b": "hello"}
        assert _repair_args(args) is args

    def test_empty_args(self):
        assert _repair_args({}) == {}


# ============================================================================
# 单元测试：_is_validation_error
# ============================================================================


class TestIsValidationError:
    def test_detects_validation_error_message(self):
        msg = ToolMessage(content="The input is not valid. Function schema is ...", tool_call_id="x")
        assert _is_validation_error(msg) is True

    def test_ignores_normal_message(self):
        msg = ToolMessage(content="success result", tool_call_id="x")
        assert _is_validation_error(msg) is False

    def test_ignores_non_tool_message(self):
        from langgraph.types import Command

        assert _is_validation_error(MagicMock(spec=Command)) is False


# ============================================================================
# 集成测试：响应式修复（use_json_repair_on_error）
# ============================================================================


class TestJsonRepairOnError:
    def test_default_is_enabled(self):
        """默认开启响应式修复"""
        assert ToolNodeSettings().use_json_repair_on_error is True

    def test_retry_fixes_json_string_arg(self):
        """工具参数校验失败时，自动修复 JSON 字符串参数并重试成功"""
        tool_node = build_tool_node(tools=[struct_tool])

        state = {
            "messages": [
                HumanMessage(content="test"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "struct_tool",
                            "args": {"config": '{"key": "value"}'},  # LLM 错误地传了 JSON 字符串
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node(tool_node, state)
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_messages) == 1
        assert "key" in tool_messages[0].content
        assert "value" in tool_messages[0].content

    def test_no_retry_on_normal_execution(self):
        """工具正常执行时不触发响应式修复"""
        tool_node = build_tool_node(tools=[greet_tool])

        state = {
            "messages": [
                HumanMessage(content="test"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "greet_tool",
                            "args": {"name": "Dave"},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node(tool_node, state)
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert tool_messages[0].content == "Hello, Dave!"

    def test_can_be_disabled(self):
        """可以显式关闭响应式修复"""
        settings = ToolNodeSettings(use_json_repair_on_error=False)
        assert settings.use_json_repair_on_error is False


@pytest.mark.asyncio
class TestJsonRepairOnErrorAsync:
    async def test_retry_fixes_json_string_arg_async(self):
        """异步场景：参数校验失败时自动修复并重试"""
        tool_node = build_tool_node(tools=[struct_tool])

        state = {
            "messages": [
                HumanMessage(content="test"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "struct_tool",
                            "args": {"config": '{"async_key": "async_val"}'},
                            "id": "call_async",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = await arun_tool_node(tool_node, state)
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert len(tool_messages) == 1
        assert "async_key" in tool_messages[0].content

    async def test_no_retry_on_normal_execution_async(self):
        """异步场景：工具正常执行时不触发响应式修复"""
        tool_node = build_tool_node(tools=[greet_tool])

        state = {
            "messages": [
                HumanMessage(content="test"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "greet_tool",
                            "args": {"name": "Eve"},
                            "id": "call_async",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = await arun_tool_node(tool_node, state)
        tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert tool_messages[0].content == "Hello, Eve!"
