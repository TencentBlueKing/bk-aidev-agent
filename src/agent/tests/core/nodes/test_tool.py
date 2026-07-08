# -*- coding: utf-8 -*-
"""
测试 build_tool_node 功能
"""

import time
from typing import AsyncGenerator, List

import pytest
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.nodes.tool.approval_wrapper import (
    TOOL_APPROVAL_STATE_KEY,
    identify_message_approval_targets,
    is_approval_configured,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables.schema import StreamEvent
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

# ============================================================================
# 测试状态定义
# ============================================================================


class AgentState(TypedDict):
    """Agent 状态"""

    messages: Annotated[List, add_messages]


# ============================================================================
# 测试工具定义
# ============================================================================


@tool
def calculator(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def multiplier(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


@tool
def failing_tool(message: str) -> str:
    """A tool that always fails."""
    raise ValueError(f"Tool failed: {message}")


@tool
def slow_tool(duration_ms: int = 100) -> str:
    """A tool that takes some time to execute."""
    time.sleep(duration_ms / 1000)
    return f"Slept for {duration_ms}ms"


@tool
def long_text_tool(length: int = 2000) -> str:
    """Return a long text."""
    return "x" * length


# ============================================================================
# 辅助函数
# ============================================================================


def run_tool_node_in_graph(tool_node, state: dict) -> dict:
    """在图中运行 tool_node 并返回结果"""
    # 构建一个简单的图来测试 tool_node
    graph = StateGraph(AgentState)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)

    compiled = graph.compile()
    result = compiled.invoke(state)
    return result


async def arun_tool_node_in_graph(tool_node, state: dict) -> dict:
    """在图中异步运行 tool_node 并返回结果"""
    # 构建一个简单的图来测试 tool_node
    graph = StateGraph(AgentState)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)

    compiled = graph.compile()
    result = await compiled.ainvoke(state)
    return result


async def astream_event_in_graph(tool_node, state: dict) -> AsyncGenerator[StreamEvent, None]:
    """在图中异步流式运行 tool_node 并返回结果"""
    graph = StateGraph(AgentState)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile()
    async for event in compiled.astream_events(state):
        yield event


# ============================================================================
# 测试用例
# ============================================================================


class TestBuildToolNode:
    """测试 build_tool_node 函数"""

    def test_no_tool_calls(self):
        """测试1: 模型返回没有工具调用时的行为"""
        tool_node = build_tool_node(tools=[calculator])

        # 构造状态：没有工具调用
        state = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there!"),
            ]
        }

        # 执行 tool_node
        result = run_tool_node_in_graph(tool_node, state)

        # 验证：应该返回空消息列表或不改变状态
        assert isinstance(result, dict)
        assert "messages" in result
        # 没有工具调用，不应生成新的 ToolMessage
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 0

    def test_single_tool_call_success(self):
        """测试2: 模型返回一个工具调用，工具正常执行"""
        tool_node = build_tool_node(tools=[calculator])

        # 构造状态：包含一个工具调用
        state = {
            "messages": [
                HumanMessage(content="What is 2 + 3?"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 执行 tool_node
        result = run_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert tool_msg.content == "5"
        assert tool_msg.tool_call_id == "call_1"
        assert tool_msg.name == "calculator"

        # 验证元数据
        assert "duration" in tool_msg.additional_kwargs
        assert isinstance(tool_msg.additional_kwargs["duration"], int)
        assert tool_msg.additional_kwargs["duration"] >= 0

        assert "description" in tool_msg.additional_kwargs
        assert tool_msg.additional_kwargs["description"] == "Add two numbers."

    def test_timer_wrapper_can_be_disabled(self):
        """测试2++: 关闭 timer_wrapper 后不应注入元数据"""
        tool_node = build_tool_node(
            tools=[calculator],
            node_options=ToolNodeSettings(use_timer=False),
        )

        state = {
            "messages": [
                HumanMessage(content="What is 2 + 3?"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert tool_msg.content == "5"
        assert "duration" not in tool_msg.additional_kwargs
        assert "description" not in tool_msg.additional_kwargs

    def test_result_limit_wrapper_truncates_long_result(self):
        """测试2++: 开启 result_limit_wrapper 后超长结果应设置 status=error"""
        tool_node = build_tool_node(
            tools=[long_text_tool],
            node_options=ToolNodeSettings(use_result_limit=True, result_limit_thrd=10),
        )

        state = {
            "messages": [
                HumanMessage(content="Return long text"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "long_text_tool",
                            "args": {"length": 50},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert "本次工具调用返回结果超长" in tool_msg.content
        assert tool_msg.tool_call_id == "call_1"
        assert tool_msg.name == "long_text_tool"
        assert getattr(tool_msg, "status", None) == "error"

    def test_result_limit_wrapper_keeps_short_result(self):
        """测试2++: 开启 result_limit_wrapper 后短结果应保持不变"""
        tool_node = build_tool_node(
            tools=[long_text_tool],
            node_options=ToolNodeSettings(use_result_limit=True, result_limit_thrd=10),
        )

        state = {
            "messages": [
                HumanMessage(content="Return short text"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "long_text_tool",
                            "args": {"length": 5},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "x" * 5

    def test_single_tool_call_with_exception(self):
        """测试3: 模型返回一个工具调用，工具抛出异常"""
        tool_node = build_tool_node(tools=[failing_tool], handle_tool_errors=True)

        # 构造状态：包含一个会失败的工具调用
        state = {
            "messages": [
                HumanMessage(content="Test error handling"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "failing_tool",
                            "args": {"message": "test error"},
                            "id": "call_fail",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 执行 tool_node，不应抛出异常
        result = run_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert "Tool failed: test error" in tool_msg.content
        assert tool_msg.tool_call_id == "call_fail"
        assert tool_msg.status == "error"

        # 验证元数据（即使失败也应该有执行时长）
        assert "duration" in tool_msg.additional_kwargs
        assert isinstance(tool_msg.additional_kwargs["duration"], int)

    def test_multiple_tool_calls_all_success(self):
        """测试4: 模型返回多个工具调用，所有工具正常执行"""
        tool_node = build_tool_node(tools=[calculator, multiplier])

        # 构造状态：包含两个工具调用
        state = {
            "messages": [
                HumanMessage(content="Calculate 2+3 and 4*5"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        },
                        {
                            "name": "multiplier",
                            "args": {"a": 4, "b": 5},
                            "id": "call_2",
                            "type": "tool_call",
                        },
                    ],
                ),
            ]
        }

        # 执行 tool_node
        result = run_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 2

        # 验证第一个工具调用
        calc_msg = next(msg for msg in tool_messages if msg.name == "calculator")
        assert calc_msg.content == "5"
        assert calc_msg.tool_call_id == "call_1"
        assert "duration" in calc_msg.additional_kwargs
        assert "description" in calc_msg.additional_kwargs

        # 验证第二个工具调用
        mult_msg = next(msg for msg in tool_messages if msg.name == "multiplier")
        assert mult_msg.content == "20"
        assert mult_msg.tool_call_id == "call_2"
        assert "duration" in mult_msg.additional_kwargs
        assert "description" in mult_msg.additional_kwargs

    def test_multiple_tool_calls_with_failures(self):
        """测试5: 模型返回多个工具调用，部分工具抛出异常"""
        tool_node = build_tool_node(tools=[calculator, failing_tool], handle_tool_errors=True)

        # 构造状态：包含一个成功和一个失败的工具调用
        state = {
            "messages": [
                HumanMessage(content="Test mixed results"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_success",
                            "type": "tool_call",
                        },
                        {
                            "name": "failing_tool",
                            "args": {"message": "test"},
                            "id": "call_fail",
                            "type": "tool_call",
                        },
                    ],
                ),
            ]
        }

        # 执行 tool_node
        result = run_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 2

        # 验证成功的工具调用
        success_msg = next(msg for msg in tool_messages if msg.name == "calculator")
        assert success_msg.content == "5"
        assert success_msg.tool_call_id == "call_success"
        assert "duration" in success_msg.additional_kwargs

        # 验证失败的工具调用
        fail_msg = next(msg for msg in tool_messages if msg.name == "failing_tool")
        assert "Tool failed: test" in fail_msg.content
        assert fail_msg.tool_call_id == "call_fail"
        assert fail_msg.status == "error"
        assert "duration" in fail_msg.additional_kwargs

    def test_approval_state_isolated_per_tool_call(self):
        """同一工具多个 tool_call 的审批状态应按 tool_call_id 隔离。"""
        original_metadata = dict(getattr(calculator, "metadata", None) or {})
        calculator.metadata = {
            **original_metadata,
            "approval": {"approval_enabled": True},
        }
        try:
            tool_node = build_tool_node(tools=[calculator])
            state = {
                "messages": [
                    HumanMessage(content="Run two approved states"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "calculator",
                                "args": {"a": 2, "b": 3},
                                "id": "call_approved",
                                "type": "tool_call",
                            },
                            {
                                "name": "calculator",
                                "args": {"a": 4, "b": 5},
                                "id": "call_rejected",
                                "type": "tool_call",
                            },
                        ],
                        additional_kwargs={
                            TOOL_APPROVAL_STATE_KEY: {
                                "call_approved": {"status": "approved"},
                                "call_rejected": {"status": "rejected"},
                            }
                        },
                    ),
                ]
            }

            result = run_tool_node_in_graph(tool_node, state)
            tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
            assert len(tool_messages) == 2

            approved_msg = next(msg for msg in tool_messages if msg.tool_call_id == "call_approved")
            rejected_msg = next(msg for msg in tool_messages if msg.tool_call_id == "call_rejected")

            assert approved_msg.content == "5"
            assert rejected_msg.content == "工具审批未通过，已取消执行。"
            assert getattr(calculator, "metadata", {}).get("approval") == {"approval_enabled": True}
        finally:
            calculator.metadata = original_metadata

    def test_is_approval_configured_accepts_skill_metadata_without_need_approval(self):
        original_metadata = dict(getattr(calculator, "metadata", None) or {})
        calculator.metadata = {
            **original_metadata,
            "skill_name": "skill-runner",
            "approval": {
                "tool_type": "skill",
                "skill_code": "skill-runner",
                "tool_name": "Skill Runner",
                "target": {"type": "skill", "skill_name": "skill-runner", "display_name": "Skill Runner"},
            },
        }
        try:
            assert is_approval_configured(calculator) is True
        finally:
            calculator.metadata = original_metadata

    def test_is_approval_configured_accepts_mcp_metadata_without_need_approval(self):
        original_metadata = dict(getattr(calculator, "metadata", None) or {})
        calculator.metadata = {
            **original_metadata,
            "tool_code": "query-time",
            "mcp_name": "time-server",
            "approval": {
                "tool_type": "mcp",
                "mcp_code": "time-server",
                "tool_code": "query-time",
                "tool_name": "Query Time",
                "target": {"type": "mcp", "mcp_name": "time-server", "code": "query-time"},
            },
        }
        try:
            assert is_approval_configured(calculator) is True
        finally:
            calculator.metadata = original_metadata



    def test_timing_accuracy(self):
        """测试6: 验证执行时间记录的准确性"""
        tool_node = build_tool_node(tools=[slow_tool])

        # 构造状态：调用慢速工具
        state = {
            "messages": [
                HumanMessage(content="Test timing"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "slow_tool",
                            "args": {"duration_ms": 100},
                            "id": "call_slow",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 执行 tool_node
        result = run_tool_node_in_graph(tool_node, state)

        # 验证结果
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert "duration" in tool_msg.additional_kwargs

        # 执行时间应该大约是 100ms (允许一些误差)
        duration = tool_msg.additional_kwargs["duration"]
        assert duration >= 90  # 至少 90ms
        assert duration <= 200  # 最多 200ms (留一些余量)

    def test_handle_tool_errors_false(self):
        """测试7: 当 handle_tool_errors=False 时，异常应该被抛出"""
        tool_node = build_tool_node(tools=[failing_tool], handle_tool_errors=False)

        # 构造状态：包含一个会失败的工具调用
        state = {
            "messages": [
                HumanMessage(content="Test error propagation"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "failing_tool",
                            "args": {"message": "test"},
                            "id": "call_fail",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 执行 tool_node，应该抛出异常
        with pytest.raises(ValueError, match="Tool failed: test"):
            run_tool_node_in_graph(tool_node, state)

    def test_custom_wrapper(self):
        """测试8: 自定义包装器是否正常工作"""
        # 定义一个自定义包装器，用于记录工具调用
        call_log = []

        def logging_wrapper(request, execute):
            call_log.append(f"before:{request.tool_call['name']}")
            result = execute(request)
            call_log.append(f"after:{request.tool_call['name']}")
            return result

        tool_node = build_tool_node(tools=[calculator], wrappers=[logging_wrapper])

        # 构造状态
        state = {
            "messages": [
                HumanMessage(content="What is 2 + 3?"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 执行 tool_node
        result = run_tool_node_in_graph(tool_node, state)

        # 验证自定义包装器被调用
        assert len(call_log) == 2
        assert call_log[0] == "before:calculator"
        assert call_log[1] == "after:calculator"

        # 验证结果仍然正确
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "5"

        # 验证元数据仍然存在（timer_wrapper 在自定义 wrapper 之前执行）
        assert "duration" in tool_messages[0].additional_kwargs
        assert "description" in tool_messages[0].additional_kwargs

    def test_multiple_custom_wrappers(self):
        """测试8+: 多个自定义包装器的执行顺序"""
        execution_order = []

        def wrapper1(request, execute):
            execution_order.append("wrapper1_start")
            result = execute(request)
            execution_order.append("wrapper1_end")
            return result

        def wrapper2(request, execute):
            execution_order.append("wrapper2_start")
            result = execute(request)
            execution_order.append("wrapper2_end")
            return result

        tool_node = build_tool_node(tools=[calculator], wrappers=[wrapper1, wrapper2])

        # 构造状态
        state = {
            "messages": [
                HumanMessage(content="Test wrapper order"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 1, "b": 1},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 执行 tool_node
        run_tool_node_in_graph(tool_node, state)

        # 验证执行顺序：timer -> wrapper1 -> wrapper2 -> tool -> wrapper2 -> wrapper1 -> timer
        # (我们只能看到 wrapper1 和 wrapper2 的顺序)
        assert execution_order == [
            "wrapper1_start",
            "wrapper2_start",
            "wrapper2_end",
            "wrapper1_end",
        ]

    def test_wrapper_can_modify_request(self):
        """测试8++: 包装器可以修改请求"""

        def doubling_wrapper(request, execute):
            # 将参数翻倍
            modified_request = request.override(
                tool_call={
                    **request.tool_call,
                    "args": {
                        "a": request.tool_call["args"]["a"] * 2,
                        "b": request.tool_call["args"]["b"] * 2,
                    },
                }
            )
            return execute(modified_request)

        tool_node = build_tool_node(tools=[calculator], wrappers=[doubling_wrapper])

        # 构造状态：原始请求是 2 + 3
        state = {
            "messages": [
                HumanMessage(content="Test request modification"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 执行 tool_node
        result = run_tool_node_in_graph(tool_node, state)

        # 验证结果：应该是 (2*2) + (3*2) = 4 + 6 = 10
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "10"


# ============================================================================
# 异步测试
# ============================================================================


@pytest.mark.asyncio
class TestBuildToolNodeAsync:
    """测试 build_tool_node 的异步功能"""

    async def test_no_tool_calls_async(self):
        """测试1: 模型返回没有工具调用时的异步行为"""
        tool_node = build_tool_node(tools=[calculator])

        # 构造状态：没有工具调用
        state = {
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there!"),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证：应该返回空消息列表或不改变状态
        assert isinstance(result, dict)
        assert "messages" in result
        # 没有工具调用，不应生成新的 ToolMessage
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 0

    async def test_single_tool_call_success_async(self):
        """测试2: 模型返回一个工具调用，工具正常执行（异步）"""
        tool_node = build_tool_node(tools=[calculator])

        # 构造状态：包含一个工具调用
        state = {
            "messages": [
                HumanMessage(content="What is 2 + 3?"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert tool_msg.content == "5"
        assert tool_msg.tool_call_id == "call_1"
        assert tool_msg.name == "calculator"

        # 验证元数据
        assert "duration" in tool_msg.additional_kwargs
        assert isinstance(tool_msg.additional_kwargs["duration"], int)
        assert tool_msg.additional_kwargs["duration"] >= 0

        assert "description" in tool_msg.additional_kwargs
        assert tool_msg.additional_kwargs["description"] == "Add two numbers."

    async def test_timer_wrapper_can_be_disabled_async(self):
        """测试2++: 关闭 timer_wrapper 后不应注入元数据（异步）"""
        tool_node = build_tool_node(
            tools=[calculator],
            node_options=ToolNodeSettings(use_timer=False),
        )

        state = {
            "messages": [
                HumanMessage(content="What is 2 + 3?"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = await arun_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert tool_msg.content == "5"
        assert "duration" not in tool_msg.additional_kwargs
        assert "description" not in tool_msg.additional_kwargs

    async def test_result_limit_wrapper_truncates_long_result_async(self):
        """测试2++: 开启 result_limit_wrapper 后超长结果应设置 status=error（异步）"""
        tool_node = build_tool_node(
            tools=[long_text_tool],
            node_options=ToolNodeSettings(use_result_limit=True, result_limit_thrd=10),
        )

        state = {
            "messages": [
                HumanMessage(content="Return long text"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "long_text_tool",
                            "args": {"length": 50},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = await arun_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert "本次工具调用返回结果超长" in tool_msg.content
        assert tool_msg.tool_call_id == "call_1"
        assert tool_msg.name == "long_text_tool"
        assert getattr(tool_msg, "status", None) == "error"

    async def test_single_tool_call_with_exception_async(self):
        """测试3: 模型返回一个工具调用，工具抛出异常（异步）"""
        tool_node = build_tool_node(tools=[failing_tool], handle_tool_errors=True)

        # 构造状态：包含一个会失败的工具调用
        state = {
            "messages": [
                HumanMessage(content="Test error handling"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "failing_tool",
                            "args": {"message": "test error"},
                            "id": "call_fail",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node，不应抛出异常
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert "Tool failed: test error" in tool_msg.content
        assert tool_msg.tool_call_id == "call_fail"
        assert tool_msg.status == "error"

        # 验证元数据（即使失败也应该有执行时长）
        assert "duration" in tool_msg.additional_kwargs
        assert isinstance(tool_msg.additional_kwargs["duration"], int)

    async def test_multiple_tool_calls_all_success_async(self):
        """测试4: 模型返回多个工具调用，所有工具正常执行（异步）"""
        tool_node = build_tool_node(tools=[calculator, multiplier])

        # 构造状态：包含两个工具调用
        state = {
            "messages": [
                HumanMessage(content="Calculate 2+3 and 4*5"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        },
                        {
                            "name": "multiplier",
                            "args": {"a": 4, "b": 5},
                            "id": "call_2",
                            "type": "tool_call",
                        },
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 2

        # 验证第一个工具调用
        calc_msg = next(msg for msg in tool_messages if msg.name == "calculator")
        assert calc_msg.content == "5"
        assert calc_msg.tool_call_id == "call_1"
        assert "duration" in calc_msg.additional_kwargs
        assert "description" in calc_msg.additional_kwargs

        # 验证第二个工具调用
        mult_msg = next(msg for msg in tool_messages if msg.name == "multiplier")
        assert mult_msg.content == "20"
        assert mult_msg.tool_call_id == "call_2"
        assert "duration" in mult_msg.additional_kwargs
        assert "description" in mult_msg.additional_kwargs

    async def test_multiple_tool_calls_with_failures_async(self):
        """测试5: 模型返回多个工具调用，部分工具抛出异常（异步）"""
        tool_node = build_tool_node(tools=[calculator, failing_tool], handle_tool_errors=True)

        # 构造状态：包含一个成功和一个失败的工具调用
        state = {
            "messages": [
                HumanMessage(content="Test mixed results"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_success",
                            "type": "tool_call",
                        },
                        {
                            "name": "failing_tool",
                            "args": {"message": "test"},
                            "id": "call_fail",
                            "type": "tool_call",
                        },
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result

        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 2

        # 验证成功的工具调用
        success_msg = next(msg for msg in tool_messages if msg.name == "calculator")
        assert success_msg.content == "5"
        assert success_msg.tool_call_id == "call_success"
        assert "duration" in success_msg.additional_kwargs

        # 验证失败的工具调用
        fail_msg = next(msg for msg in tool_messages if msg.name == "failing_tool")
        assert "Tool failed: test" in fail_msg.content
        assert fail_msg.tool_call_id == "call_fail"
        assert fail_msg.status == "error"
        assert "duration" in fail_msg.additional_kwargs

    async def test_timing_accuracy_async(self):
        """测试6: 验证异步执行时间记录的准确性"""
        tool_node = build_tool_node(tools=[slow_tool])

        # 构造状态：调用慢速工具
        state = {
            "messages": [
                HumanMessage(content="Test timing"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "slow_tool",
                            "args": {"duration_ms": 100},
                            "id": "call_slow",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证结果
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1

        tool_msg = tool_messages[0]
        assert "duration" in tool_msg.additional_kwargs

        # 执行时间应该大约是 100ms (允许一些误差)
        duration = tool_msg.additional_kwargs["duration"]
        assert duration >= 90  # 至少 90ms
        assert duration <= 200  # 最多 200ms (留一些余量)

    async def test_handle_tool_errors_true_async(self):
        """测试7: 当 handle_tool_errors=True 时，异步异常不应该被抛出"""
        tool_node = build_tool_node(tools=[failing_tool], handle_tool_errors=True)

        # 构造状态：包含一个会失败的工具调用
        state = {
            "messages": [
                HumanMessage(content="Test error handling"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "failing_tool",
                            "args": {"message": "test"},
                            "id": "call_fail",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node，不应该抛出异常
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证结果包含错误信息但没有抛出异常
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].status == "error"
        assert "Tool failed: test" in tool_messages[0].content

    async def test_custom_async_wrapper(self):
        """测试8: 自定义异步包装器是否正常工作"""
        call_log = []

        async def async_logging_wrapper(request, execute):
            call_log.append(f"async_before:{request.tool_call['name']}")
            result = await execute(request)
            call_log.append(f"async_after:{request.tool_call['name']}")
            return result

        tool_node = build_tool_node(tools=[calculator], async_wrappers=[async_logging_wrapper])

        # 构造状态
        state = {
            "messages": [
                HumanMessage(content="Test async wrapper"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证自定义包装器被调用
        assert len(call_log) == 2
        assert call_log[0] == "async_before:calculator"
        assert call_log[1] == "async_after:calculator"

        # 验证结果仍然正确
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "5"

        # 验证元数据仍然存在（timer_wrapper 在自定义 wrapper 之前执行）
        assert "duration" in tool_messages[0].additional_kwargs
        assert "description" in tool_messages[0].additional_kwargs

    async def test_multiple_custom_async_wrappers(self):
        """测试8+: 多个自定义异步包装器的执行顺序"""
        execution_order = []

        async def async_wrapper1(request, execute):
            execution_order.append("async_wrapper1_start")
            result = await execute(request)
            execution_order.append("async_wrapper1_end")
            return result

        async def async_wrapper2(request, execute):
            execution_order.append("async_wrapper2_start")
            result = await execute(request)
            execution_order.append("async_wrapper2_end")
            return result

        tool_node = build_tool_node(tools=[calculator], async_wrappers=[async_wrapper1, async_wrapper2])

        # 构造状态
        state = {
            "messages": [
                HumanMessage(content="Test async wrapper order"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 1, "b": 1},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        await arun_tool_node_in_graph(tool_node, state)

        # 验证执行顺序：timer -> wrapper1 -> wrapper2 -> tool -> wrapper2 -> wrapper1 -> timer
        # (我们只能看到 wrapper1 和 wrapper2 的顺序)
        assert execution_order == [
            "async_wrapper1_start",
            "async_wrapper2_start",
            "async_wrapper2_end",
            "async_wrapper1_end",
        ]

    async def test_async_wrapper_can_modify_request(self):
        """测试8++: 异步包装器可以修改请求"""

        async def async_doubling_wrapper(request, execute):
            # 将参数翻倍
            modified_request = request.override(
                tool_call={
                    **request.tool_call,
                    "args": {
                        "a": request.tool_call["args"]["a"] * 2,
                        "b": request.tool_call["args"]["b"] * 2,
                    },
                }
            )
            return await execute(modified_request)

        tool_node = build_tool_node(tools=[calculator], async_wrappers=[async_doubling_wrapper])

        # 构造状态：原始请求是 2 + 3
        state = {
            "messages": [
                HumanMessage(content="Test request modification"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证结果：应该是 (2*2) + (3*2) = 4 + 6 = 10
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "10"

    async def test_mixed_sync_async_wrappers_async(self):
        """测试9: 同时有同步和异步包装器时，异步执行应该只使用异步包装器"""
        sync_call_log = []
        async_call_log = []

        def sync_wrapper(request, execute):
            sync_call_log.append(f"sync:{request.tool_call['name']}")
            return execute(request)

        async def async_wrapper(request, execute):
            async_call_log.append(f"async:{request.tool_call['name']}")
            result = await execute(request)
            return result

        tool_node = build_tool_node(tools=[calculator], wrappers=[sync_wrapper], async_wrappers=[async_wrapper])

        # 构造状态
        state = {
            "messages": [
                HumanMessage(content="Test mixed wrappers"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        # 异步执行 tool_node
        result = await arun_tool_node_in_graph(tool_node, state)

        # 验证：异步执行时，只有异步包装器被调用
        assert len(async_call_log) == 1
        assert async_call_log[0] == "async:calculator"
        assert len(sync_call_log) == 0  # 同步包装器不应该被调用

        # 验证结果仍然正确
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        assert tool_messages[0].content == "5"

    async def test_stream_event_in_graph_async(self):
        """测试10: 流式运行 tool_node 并返回结果"""
        tool_node = build_tool_node(tools=[calculator])

        # 构造状态
        state = {
            "messages": [
                HumanMessage(content="Test stream event"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "calculator",
                            "args": {"a": 2, "b": 3},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }
        async for event in astream_event_in_graph(tool_node, state):
            if event["event"] == "on_tool_end":
                output_message = event["data"]["output"]
                assert isinstance(output_message, ToolMessage)


# ============================================================================
# 边界条件和覆盖缺口测试
# ============================================================================


class TestDefaultToolCallHandler:
    """测试 default_tool_call_handler 函数"""

    def test_empty_exception_message_with_args(self):
        """测试空异常消息时回退到 args"""
        from aidev_agent.core.nodes.tool.node import default_tool_call_handler

        # 创建一个异常，str(error) 为空但有 args
        class EmptyStrException(Exception):
            def __str__(self):
                return ""

        error = EmptyStrException("fallback message")
        result = default_tool_call_handler(error)
        assert result == "fallback message"

    def test_empty_exception_message_with_multiple_args(self):
        """测试空异常消息时回退到多个 args"""
        from aidev_agent.core.nodes.tool.node import default_tool_call_handler

        class EmptyStrException(Exception):
            def __str__(self):
                return ""

        error = EmptyStrException("arg1", "arg2")
        result = default_tool_call_handler(error)
        assert result == "('arg1', 'arg2')"

    def test_exception_without_args(self):
        """测试无 args 异常返回通用错误消息"""
        from aidev_agent.core.nodes.tool.node import default_tool_call_handler

        class EmptyException(Exception):
            def __str__(self):
                return ""

        error = EmptyException()
        result = default_tool_call_handler(error)
        assert result == "工具执行失败"

    def test_graph_bubble_up_is_reraised(self):
        """GraphBubbleUp（GraphInterrupt 基类）必须重新抛出，不能被转为 error 字符串。

        这是 interrupt() 正常工作的核心保障：ToolNode 的 _arun_one 用 except Exception
        捕获中间件链异常并调用 default_tool_call_handler，如果 GraphBubbleUp 被转为
        字符串而非抛出，interrupt() 会被吞掉，图不会暂停。
        """
        from langgraph.errors import GraphBubbleUp

        from aidev_agent.core.nodes.tool.node import default_tool_call_handler

        error = GraphBubbleUp("interrupt value")
        with pytest.raises(GraphBubbleUp):
            default_tool_call_handler(error)

    def test_graph_interrupt_subclass_is_reraised(self):
        """GraphInterrupt（GraphBubbleUp 子类）也必须重新抛出。"""
        from langgraph.errors import GraphInterrupt

        from aidev_agent.core.nodes.tool.node import default_tool_call_handler

        error = GraphInterrupt("interrupt payload")
        with pytest.raises(GraphInterrupt):
            default_tool_call_handler(error)

    def test_non_bubbleup_exception_returns_string(self):
        """普通异常仍返回字符串，不受 GraphBubbleUp 判断影响。"""
        from aidev_agent.core.nodes.tool.node import default_tool_call_handler

        error = ValueError("something went wrong")
        result = default_tool_call_handler(error)
        assert result == "something went wrong"


class TestWrapperChaining:
    """测试 wrapper 链式组合函数"""

    def test_empty_wrapper_list_returns_none(self):
        """测试空 wrapper 列表返回 None"""
        from aidev_agent.core.nodes.tool.node import _chain_tool_call_wrappers

        result = _chain_tool_call_wrappers([])
        assert result is None

    def test_single_wrapper_returns_original(self):
        """测试单个 wrapper 直接返回原 wrapper"""
        from aidev_agent.core.nodes.tool.node import _chain_tool_call_wrappers

        def my_wrapper(request, execute):
            return execute(request)

        result = _chain_tool_call_wrappers([my_wrapper])
        assert result is my_wrapper

    def test_empty_async_wrapper_list_returns_none(self):
        """测试空异步 wrapper 列表返回 None"""
        from aidev_agent.core.nodes.tool.node import _chain_async_tool_call_wrappers

        result = _chain_async_tool_call_wrappers([])
        assert result is None

    def test_single_async_wrapper_returns_original(self):
        """测试单个异步 wrapper 直接返回原 wrapper"""
        from aidev_agent.core.nodes.tool.node import _chain_async_tool_call_wrappers

        async def my_async_wrapper(request, execute):
            return await execute(request)

        result = _chain_async_tool_call_wrappers([my_async_wrapper])
        assert result is my_async_wrapper


class TestResultLimitBoundary:
    """测试结果长度限制的边界条件"""

    def test_result_limit_at_exact_threshold(self):
        """测试长度恰好等于阈值时不应被替换"""
        tool_node = build_tool_node(
            tools=[long_text_tool],
            node_options=ToolNodeSettings(use_result_limit=True, result_limit_thrd=10),
        )

        state = {
            "messages": [
                HumanMessage(content="Return text at exact threshold"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "long_text_tool",
                            "args": {"length": 10},  # 恰好等于阈值
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        # 长度等于阈值，不应被替换
        assert tool_messages[0].content == "x" * 10

    def test_result_limit_one_over_threshold(self):
        """测试长度超过阈值 1 时应被替换"""
        tool_node = build_tool_node(
            tools=[long_text_tool],
            node_options=ToolNodeSettings(use_result_limit=True, result_limit_thrd=10),
        )

        state = {
            "messages": [
                HumanMessage(content="Return text one over threshold"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "long_text_tool",
                            "args": {"length": 11},  # 超过阈值 1
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        assert len(tool_messages) == 1
        # 长度超过阈值，应被替换
        assert tool_messages[0].content == "本次工具调用返回结果超长，请重新调整调用参数"

    @pytest.mark.parametrize(
        "length,should_truncate",
        [
            (5, False),  # 低于阈值
            (10, False),  # 等于阈值
            (11, True),  # 超过阈值
        ],
    )
    def test_result_limit_parametrized(self, length, should_truncate):
        """参数化测试结果长度限制边界条件"""
        tool_node = build_tool_node(
            tools=[long_text_tool],
            node_options=ToolNodeSettings(use_result_limit=True, result_limit_thrd=10),
        )

        state = {
            "messages": [
                HumanMessage(content="Test parametrized"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "long_text_tool",
                            "args": {"length": length},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }

        result = run_tool_node_in_graph(tool_node, state)
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]

        if should_truncate:
            assert tool_messages[0].content == "本次工具调用返回结果超长，请重新调整调用参数"
        else:
            assert tool_messages[0].content == "x" * length


class TestToolMsgContentLen:
    """测试 _tool_msg_content_len 函数"""

    def test_content_none_via_getattr(self):
        """测试 getattr 获取 content 为 None 的情况"""
        from unittest.mock import MagicMock

        from aidev_agent.core.nodes.tool.result_limit_wrapper import _tool_msg_content_len

        # 使用 MagicMock 模拟一个 content 为 None 的消息对象
        msg = MagicMock()
        msg.content = None
        result = _tool_msg_content_len(msg)
        assert result == 0

    def test_content_string(self):
        """测试 content 为字符串的情况"""
        from aidev_agent.core.nodes.tool.result_limit_wrapper import _tool_msg_content_len

        msg = ToolMessage(content="hello", tool_call_id="test")
        result = _tool_msg_content_len(msg)
        assert result == 5

    def test_content_non_string(self):
        """测试 content 为非字符串的情况"""
        from aidev_agent.core.nodes.tool.result_limit_wrapper import _tool_msg_content_len

        msg = ToolMessage(content=12345, tool_call_id="test")
        result = _tool_msg_content_len(msg)
        assert result == 5  # str(12345) = "12345"


class TestToolApprovalCreatePayload:
    def test_create_approval_payload_includes_resource_fields(self):
        from unittest.mock import MagicMock, patch

        from aidev_agent.core.nodes.tool.approval_wrapper import ApprovalTarget, _create_approval_from_target

        target = ApprovalTarget(
            target_type="mcp",
            target_id="call_1",
            target_name="Query Time",
            target_code="query-time",
            args={"timezone": "Asia/Shanghai"},
            approval={"mcp_code": "time-server", "approvers": ["admin"]},
            tool=None,
        )
        mock_client = MagicMock()
        mock_client.api.create_tool_approval.return_value = {"data": {"callback_token": "token", "ticket": {}}}

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.BKAidevApi.get_client",
            return_value=mock_client,
        ):
            _create_approval_from_target(target, None)

        payload = mock_client.api.create_tool_approval.call_args.kwargs["json"]
        assert payload["tool_name"] == "Query Time"
        assert payload["tool_code"] == "query-time"
        assert payload["mcp_name"] == "time-server"
        assert payload["tool_args"] == {"timezone": "Asia/Shanghai"}

    def test_create_approval_payload_resolves_mcp_name_from_binding(self):
        from unittest.mock import MagicMock, patch

        from aidev_agent.core.nodes.tool.approval_wrapper import ApprovalTarget, _create_approval_from_target

        target = ApprovalTarget(
            target_type="mcp",
            target_id="call_1",
            target_name="get_ticket_info",
            target_code="get_ticket_info",
            args={"query_param": {"sn": "DE2026070600000005"}},
            approval={"mcp_name": "itsm-mcp", "approvers": ["admin"]},
            tool=None,
        )
        mock_client = MagicMock()
        mock_client.api.create_tool_approval.return_value = {"data": {"callback_token": "token", "ticket": {}}}

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.BKAidevApi.get_client",
            return_value=mock_client,
        ):
            _create_approval_from_target(target, None)

        payload = mock_client.api.create_tool_approval.call_args.kwargs["json"]
        assert payload["mcp_name"] == "itsm-mcp"
