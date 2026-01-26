# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aidev_agent.core.nodes.model import ModelNodeSettings, ModelState, build_model_node
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph._internal._runnable import RunnableCallable


class TestModelState:
    """测试 ModelState TypedDict 定义"""

    def test_model_state_structure(self):
        """测试 ModelState 的结构"""
        state: ModelState = {"messages": [HumanMessage(content="test")]}
        assert "messages" in state
        assert len(state["messages"]) == 1


class TestBuildModelNode:
    """测试 build_model_node 函数（使用 Mock）"""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM"""
        llm = Mock()

        llm.invoke = Mock(return_value=AIMessage(content="Mocked response"))
        llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked async response"))

        # Mock bind_tools to return a mock that also has invoke/ainvoke
        bound_llm = Mock()
        bound_llm.invoke = Mock(return_value=AIMessage(content="Mocked response"))
        bound_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked async response"))

        # Support for chaining with | operator
        llm.__or__ = Mock(return_value=llm)
        bound_llm.__or__ = Mock(return_value=bound_llm)

        llm.bind_tools = Mock(return_value=bound_llm)
        return llm

    @pytest.fixture
    def sample_tools(self):
        """示例工具列表"""

        @tool
        def search_tool(query: str) -> str:
            """Search for information"""
            return f"Search results for: {query}"

        @tool
        def calculator(expression: str) -> str:
            """Calculate mathematical expression"""
            return f"Result: {expression}"

        return [search_tool, calculator]

    @pytest.fixture
    def mock_store(self):
        """Mock BaseStore"""
        return Mock()

    @pytest.fixture
    def tool_calling_prompt_chain(self):
        """Mock prompt template and chain for tool_calling mode."""
        mock_template = Mock()

        mock_chain = Mock()
        mock_chain.invoke = Mock(return_value=AIMessage(content="Mocked response"))
        mock_chain.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked async response"))

        mock_template.__or__ = Mock(return_value=mock_chain)
        mock_template.input_variables = ["input", "chat_history", "agent_scratchpad"]

        variables = {
            "input": "test query",
            "chat_history": [],
            "agent_scratchpad": [],
        }
        return mock_template, mock_chain, variables

    def test_build_model_node_returns_runnable_callable(self, mock_llm, sample_tools):
        """测试 build_model_node 返回 RunnableCallable"""
        node = build_model_node(
            llm=mock_llm,
            tools=sample_tools,
        )
        assert isinstance(node, RunnableCallable)

    def test_model_node_sync_with_tool_calling(self, mock_llm, sample_tools, mock_store, tool_calling_prompt_chain):
        """测试同步模型节点（tool_calling 模式）"""
        mock_template, _mock_chain, variables = tool_calling_prompt_chain

        with (
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=sample_tools,
            ) as p_tools,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ) as p_template,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ) as p_vars,
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=sample_tools,
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
            }
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert "messages" in result
            assert len(result["messages"]) == 1
            assert isinstance(result["messages"][0], AIMessage)
            assert result["messages"][0].content == "Mocked response"

            p_tools.assert_called_once()
            p_template.assert_called_once()
            p_vars.assert_called_once()
            mock_llm.bind_tools.assert_called_once()

    def test_model_node_sync_with_structured_response(self, mock_llm, mock_store):
        """测试同步模型节点（structured_response 模式）"""
        mock_template = Mock()
        mock_parser = Mock()

        mock_chain_step1 = Mock()  # template | llm
        mock_chain_final = Mock()  # (template | llm) | parser
        mock_chain_final.invoke = Mock(return_value=AIMessage(content="Structured response"))

        mock_template.__or__ = Mock(return_value=mock_chain_step1)
        mock_chain_step1.__or__ = Mock(return_value=mock_chain_final)
        mock_template.input_variables = ["input", "chat_history", "agent_scratchpad"]

        variables = {
            "input": "test query",
            "chat_history": [],
            "agent_scratchpad": [],
        }

        with (
            patch("aidev_agent.core.nodes.model.node.StructuredOutputToToolMessageParser") as mock_parser_class,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=[],
            ) as p_tools,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ) as p_template,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ) as p_vars,
        ):
            mock_parser_class.return_value = mock_parser

            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(use_structured_response=True),
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
            }
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert "messages" in result
            assert len(result["messages"]) == 1

            mock_parser_class.assert_called_once()
            call_kwargs = mock_parser_class.call_args[1]
            assert call_kwargs["llm"] == mock_llm
            assert call_kwargs["enable_parallel_tool_calls"] is True

            # structured_response 模式不使用 bind_tools
            mock_llm.bind_tools.assert_not_called()

            p_tools.assert_called_once()
            p_template.assert_called_once()
            p_vars.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_node_async_with_tool_calling(
        self, mock_llm, sample_tools, mock_store, tool_calling_prompt_chain
    ):
        """测试异步模型节点（tool_calling 模式）"""
        mock_template, _mock_chain, variables = tool_calling_prompt_chain

        with (
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=sample_tools,
            ) as p_tools,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ) as p_template,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ) as p_vars,
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=sample_tools,
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
            }
            config = RunnableConfig()

            result = await node.ainvoke(state, config=config, store=mock_store)

            assert "messages" in result
            assert len(result["messages"]) == 1
            assert isinstance(result["messages"][0], AIMessage)
            assert result["messages"][0].content == "Mocked async response"

            p_tools.assert_called_once()
            p_template.assert_called_once()
            p_vars.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_node_async_with_structured_response(self, mock_llm, mock_store):
        """测试异步模型节点（structured_response 模式）"""
        mock_template = Mock()
        mock_parser = Mock()

        mock_chain_step1 = Mock()  # template | llm
        mock_chain_final = Mock()  # (template | llm) | parser
        mock_chain_final.ainvoke = AsyncMock(return_value=AIMessage(content="Structured async response"))

        mock_template.__or__ = Mock(return_value=mock_chain_step1)
        mock_chain_step1.__or__ = Mock(return_value=mock_chain_final)
        mock_template.input_variables = ["input", "chat_history", "agent_scratchpad"]

        variables = {
            "input": "test query",
            "chat_history": [],
            "agent_scratchpad": [],
        }

        with (
            patch("aidev_agent.core.nodes.model.node.StructuredOutputToToolMessageParser") as mock_parser_class,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=[],
            ) as p_tools,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ) as p_template,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ) as p_vars,
        ):
            mock_parser_class.return_value = mock_parser

            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(use_structured_response=True),
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
            }
            config = RunnableConfig()

            result = await node.ainvoke(state, config=config, store=mock_store)

            assert "messages" in result
            assert len(result["messages"]) == 1

            mock_parser_class.assert_called()
            call_kwargs = mock_parser_class.call_args[1]
            assert call_kwargs["enable_parallel_tool_calls"] is True

            p_tools.assert_called_once()
            p_template.assert_called_once()
            p_vars.assert_called_once()

    def test_model_node_without_tools(self, mock_llm, mock_store, tool_calling_prompt_chain):
        """测试没有工具的情况"""
        mock_template, _mock_chain, variables = tool_calling_prompt_chain

        with (
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=[],
            ) as p_tools,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ) as p_template,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ) as p_vars,
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=[],
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
            }
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert "messages" in result
            assert len(result["messages"]) == 1

            mock_llm.bind_tools.assert_not_called()
            p_tools.assert_called_once()
            p_template.assert_called_once()
            p_vars.assert_called_once()

    def test_model_node_with_parallel_tool_calls_enabled(self, mock_llm, mock_store):
        """测试启用并行工具调用"""
        mock_template = Mock()
        mock_parser = Mock()

        mock_chain_step1 = Mock()
        mock_chain_final = Mock()
        mock_chain_final.invoke = Mock(return_value=AIMessage(content="Response with parallel calls"))

        mock_template.__or__ = Mock(return_value=mock_chain_step1)
        mock_chain_step1.__or__ = Mock(return_value=mock_chain_final)
        mock_template.input_variables = ["input", "chat_history", "agent_scratchpad"]

        variables = {
            "input": "test query",
            "chat_history": [],
            "agent_scratchpad": [],
        }

        with (
            patch("aidev_agent.core.nodes.model.node.StructuredOutputToToolMessageParser") as mock_parser_class,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=[],
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ),
        ):
            mock_parser_class.return_value = mock_parser

            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(use_structured_response=True),
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
            }
            config = RunnableConfig()

            node.invoke(state, config=config, store=mock_store)

            call_kwargs = mock_parser_class.call_args[1]
            assert call_kwargs["enable_parallel_tool_calls"] is True

    def test_model_node_state_with_decision(self, mock_llm, sample_tools, mock_store, tool_calling_prompt_chain):
        """测试 state 中包含 decision 的情况"""
        from aidev_agent.enums import Decision

        mock_template, _mock_chain, variables = tool_calling_prompt_chain

        with (
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=sample_tools,
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ) as p_template,
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ),
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=sample_tools,
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
                "decision": Decision.PRIVATE_QA,  # type: ignore
            }
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            # state 透传到 get_chat_prompt_template
            call_args = p_template.call_args[0]
            passed_ctx = call_args[0]
            assert passed_ctx.state["decision"] == Decision.PRIVATE_QA

            assert "messages" in result
            assert len(result["messages"]) == 1

    def test_model_node_context_variables_integration(
        self, mock_llm, sample_tools, mock_store, tool_calling_prompt_chain
    ):
        """测试上下文变量的集成"""
        mock_template, _mock_chain, _variables = tool_calling_prompt_chain

        enriched = {
            "input": "test query",
            "chat_history": [HumanMessage(content="previous question")],
            "agent_scratchpad": [],
            "context": "Some knowledge base content",
            "beijing_now": "2025-01-08 12:00:00",
        }

        with (
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
                return_value=sample_tools,
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=enriched,
            ) as p_vars,
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=sample_tools,
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
                "knowledge_content": "Some knowledge base content",
            }
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            p_vars.assert_called_once()
            assert "messages" in result
