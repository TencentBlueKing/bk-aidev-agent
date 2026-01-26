# -*- coding: utf-8 -*-
"""
测试 ReActAgentBuilder.build 中 tools 创建逻辑
"""

from typing import List
from unittest.mock import MagicMock, patch

from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.nodes.tool import ToolNodeSettings
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolNode

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


# ============================================================================
# 自定义 Middleware 用于测试
# ============================================================================


class CustomMiddlewareWithWrap(AgentMiddleware):
    """覆盖了 wrap_tool_call 的中间件"""

    def wrap_tool_call(self, request, execute):
        return execute(request)


class CustomMiddlewareWithAwrap(AgentMiddleware):
    """覆盖了 awrap_tool_call 的中间件"""

    async def awrap_tool_call(self, request, execute):
        return await execute(request)


class CustomMiddlewareWithBoth(AgentMiddleware):
    """同时覆盖了 wrap_tool_call 和 awrap_tool_call 的中间件"""

    def wrap_tool_call(self, request, execute):
        return execute(request)

    async def awrap_tool_call(self, request, execute):
        return await execute(request)


class CustomMiddlewareWithTools(AgentMiddleware):
    """带有 tools 的中间件"""

    def __init__(self, tools: List[BaseTool]):
        self.tools = tools


class CustomMiddlewareNoOverride(AgentMiddleware):
    """没有覆盖任何方法的中间件"""


# ============================================================================
# 测试用例
# ============================================================================


class TestPrepareAgentToolNode:
    """测试 _prepare_agent_tool_node 方法"""

    @patch("aidev_agent.core.graphs.react.graph.build_tool_node")
    def test_prepare_agent_tool_node_passes_all_params_to_build_tool_node(self, mock_build_tool_node):
        """
        验证 _prepare_agent_tool_node 正确传递所有参数给 build_tool_node:
        - tools 是外部传入的参数
        - node_options 中的变量是传入的参数
        - middleware_w_wrap_tool_call 中的变量是传入的参数
        - middleware_w_awrap_tool_call 中的变量是传入的参数
        """
        # 准备测试数据
        tools = [calculator, multiplier]
        node_options = ToolNodeSettings(use_timer=False, use_result_limit=True, result_limit_thrd=500)

        middleware_with_wrap = CustomMiddlewareWithWrap()
        middleware_with_awrap = CustomMiddlewareWithAwrap()
        middleware_with_both = CustomMiddlewareWithBoth()
        middleware_no_override = CustomMiddlewareNoOverride()

        langchain_middleware = [
            middleware_with_wrap,
            middleware_with_awrap,
            middleware_with_both,
            middleware_no_override,
        ]

        mock_build_tool_node.return_value = MagicMock()

        builder = ReActAgentBuilder()

        # 调用被测方法
        builder._prepare_agent_tool_node(
            tools=tools,
            name="custom_tools",
            tags=["tag1", "tag2"],
            langchain_middleware=langchain_middleware,
            node_options=node_options,
        )

        # 验证 build_tool_node 被调用
        mock_build_tool_node.assert_called_once()
        call_kwargs = mock_build_tool_node.call_args.kwargs

        # 1. 验证 tools 是外部传入的参数
        assert call_kwargs["tools"] == tools

        # 2. 验证 node_options 中的变量是传入的参数
        assert call_kwargs["node_options"] == node_options
        assert call_kwargs["node_options"].use_timer is False
        assert call_kwargs["node_options"].use_result_limit is True
        assert call_kwargs["node_options"].result_limit_thrd == 500

        # 3. 验证 name 和 tags 是传入的参数
        assert call_kwargs["name"] == "custom_tools"
        assert call_kwargs["tags"] == ["tag1", "tag2"]

        # 4. 验证 middleware_w_wrap_tool_call 正确过滤中间件
        # 条件: wrap_tool_call 或 awrap_tool_call 被覆盖
        wrappers = call_kwargs["wrappers"]
        assert middleware_with_wrap in wrappers
        assert middleware_with_awrap in wrappers
        assert middleware_with_both in wrappers
        assert middleware_no_override not in wrappers
        assert len(wrappers) == 3

        # 5. 验证 middleware_w_awrap_tool_call 正确过滤中间件
        # 条件: awrap_tool_call 或 wrap_tool_call 被覆盖
        async_wrappers = call_kwargs["async_wrappers"]
        assert middleware_with_wrap in async_wrappers
        assert middleware_with_awrap in async_wrappers
        assert middleware_with_both in async_wrappers
        assert middleware_no_override not in async_wrappers
        assert len(async_wrappers) == 3

    def test_prepare_agent_tool_node_returns_none_when_no_tools(self):
        """验证当 tools 为空时返回 None"""
        builder = ReActAgentBuilder()
        result = builder._prepare_agent_tool_node(
            tools=[],
            langchain_middleware=[CustomMiddlewareWithWrap()],
        )
        assert result is None

    def test_prepare_agent_tool_node_returns_valid_tool_node(self):
        """集成测试：验证 _prepare_agent_tool_node 返回有效的 ToolNode"""
        tools = [calculator]
        node_options = ToolNodeSettings(use_timer=True, use_result_limit=False)
        langchain_middleware = [CustomMiddlewareWithWrap(), CustomMiddlewareWithAwrap()]

        builder = ReActAgentBuilder()
        result = builder._prepare_agent_tool_node(
            tools=tools,
            name="test_tools",
            tags=["test_tag"],
            langchain_middleware=langchain_middleware,
            node_options=node_options,
        )

        assert isinstance(result, ToolNode)


class TestBuildToolCreation:
    """测试通过 build() 构造 ReAct 时参数是否正确传递"""

    @patch("aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph")
    @patch("aidev_agent.core.graphs.react.graph.ReActAgentBuilder._prepare_agent_model_node")
    @patch("aidev_agent.core.graphs.react.graph.ReActAgentBuilder._prepare_agent_tool_node")
    @patch("aidev_agent.core.graphs.react.graph.ReActAgentBuilder._prepare_agent_tools")
    def test_build_passes_all_tool_params_correctly(
        self,
        mock_prepare_tools,
        mock_prepare_tool_node,
        mock_prepare_model_node,
        mock_build_graph,
    ):
        """
        验证 get_agent_executor 正确传递所有工具相关参数:
        - extra_tools 传递给 _prepare_agent_tools
        - langchain_middleware 传递给 _prepare_agent_tools 和 _prepare_agent_tool_node
        - tool_node_options 传递给 _prepare_agent_tool_node
        - _prepare_agent_tools 的返回值传递给 _prepare_agent_tool_node
        """
        # 准备测试数据
        mock_llm = MagicMock()
        mock_llm.model_name = "test-model"
        extra_tools = [calculator, multiplier]
        prepared_tools = [calculator, multiplier]
        middleware = [CustomMiddlewareWithWrap(), CustomMiddlewareWithAwrap()]
        tool_node_options = ToolNodeSettings(use_timer=False, use_result_limit=True, result_limit_thrd=999)

        mock_prepare_tools.return_value = prepared_tools
        mock_prepare_tool_node.return_value = MagicMock()
        mock_build_graph.return_value = (MagicMock(), MagicMock())

        mock_prepare_model_node.return_value = MagicMock()

        # 调用被测方法
        builder = (
            ReActAgentBuilder()
            .set_llm(mock_llm)
            .set_knowledge_llm(mock_llm)
            .set_tools(extra_tools)
            .set_langchain_middleware(middleware)
            .set_tool_node_options(tool_node_options)
        )
        builder.build()

        # 1. 验证 _prepare_agent_tools 接收到正确的参数
        mock_prepare_tools.assert_called_once()
        prepare_tools_kwargs = mock_prepare_tools.call_args.kwargs
        assert prepare_tools_kwargs["extra_tools"] == extra_tools
        assert prepare_tools_kwargs["langchain_middleware"] == middleware

        # 2. 验证 _prepare_agent_tool_node 接收到正确的参数
        mock_prepare_tool_node.assert_called_once()
        prepare_tool_node_args = mock_prepare_tool_node.call_args
        # 第一个位置参数是 tools（来自 _prepare_agent_tools 的返回值）
        assert prepare_tool_node_args.args[0] == prepared_tools
        # kwargs 中的参数
        assert prepare_tool_node_args.kwargs["langchain_middleware"] == middleware
        assert prepare_tool_node_args.kwargs["node_options"] == tool_node_options
