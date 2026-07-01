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

import httpx
import pytest
from aidev_agent.core.nodes.model import ModelChainConfig, ModelNodeSettings, ModelState, build_model_node
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate, ResponseRoute
from aidev_agent.enums import Decision
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import tool
from langgraph._internal._runnable import RunnableCallable
from openai import RateLimitError


class TestModelState:
    """测试 ModelState TypedDict 定义"""

    def test_model_state_structure(self):
        """测试 ModelState 的结构"""
        state: ModelState = {"messages": [HumanMessage(content="test")]}
        assert "messages" in state
        assert len(state["messages"]) == 1


def _make_mock_llm(invoke_return=None, ainvoke_return=None):
    """创建支持 Runnable 链式操作的 mock LLM。

    用 RunnableLambda 包装 mock 函数，确保 | 运算符正常工作。
    """
    invoke_fn = Mock(return_value=invoke_return or AIMessage(content="Mocked response"))
    ainvoke_fn = AsyncMock(return_value=ainvoke_return or AIMessage(content="Mocked async response"))

    llm = RunnableLambda(invoke_fn, afunc=ainvoke_fn)
    llm.bind_tools = Mock(return_value=llm)

    # 暴露内部 mock 以便断言调用次数
    llm._invoke_fn = invoke_fn
    llm._ainvoke_fn = ainvoke_fn
    return llm


class TestBuildModelNode:
    """测试 build_model_node 函数（使用 Mock）"""

    @pytest.fixture
    def mock_llm(self):
        return _make_mock_llm()

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
    def mock_prompt_setup(self):
        """Mock prompt template 和 variables"""
        mock_template = Mock()
        prompt_value = Mock()
        prompt_value.to_messages.return_value = [HumanMessage(content="test")]
        mock_template.invoke = Mock(return_value=prompt_value)

        variables = {"input": "test", "chat_history": [], "agent_scratchpad": []}
        return mock_template, variables

    def test_build_model_node_returns_runnable_callable(self, mock_llm, sample_tools):
        """测试 build_model_node 返回 RunnableCallable"""
        node = build_model_node(
            llm=mock_llm,
            tools=sample_tools,
        )
        assert isinstance(node, RunnableCallable)

    def test_model_node_sync_with_tool_calling(self, mock_llm, sample_tools, mock_store, mock_prompt_setup):
        """测试同步模型节点（tool_calling 模式）"""
        mock_template, variables = mock_prompt_setup

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

    def test_model_node_sync_with_structured_response(self, mock_llm, sample_tools, mock_store, mock_prompt_setup):
        """测试同步模型节点（structured_response 模式）"""
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.model_chain.StructuredOutputToToolMessageParser") as mock_parser_class,
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
            # mock parser 也需要支持 Runnable 链
            mock_parser = _make_mock_llm(invoke_return=AIMessage(content="Structured response"))
            mock_parser_class.return_value = mock_parser

            node = build_model_node(
                llm=mock_llm,
                tools=sample_tools,
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
    async def test_model_node_async_with_tool_calling(self, mock_llm, sample_tools, mock_store, mock_prompt_setup):
        """测试异步模型节点（tool_calling 模式）"""
        mock_template, variables = mock_prompt_setup

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
    async def test_model_node_async_with_structured_response(
        self, mock_llm, sample_tools, mock_store, mock_prompt_setup
    ):
        """测试异步模型节点（structured_response 模式）"""
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.model_chain.StructuredOutputToToolMessageParser") as mock_parser_class,
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
            mock_parser = _make_mock_llm(ainvoke_return=AIMessage(content="Structured async response"))
            mock_parser_class.return_value = mock_parser

            node = build_model_node(
                llm=mock_llm,
                tools=sample_tools,
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

    def test_model_node_without_tools(self, mock_llm, mock_store, mock_prompt_setup):
        """测试没有工具的情况"""
        mock_template, variables = mock_prompt_setup

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

    def test_model_node_with_parallel_tool_calls_enabled(self, mock_llm, sample_tools, mock_store, mock_prompt_setup):
        """测试启用并行工具调用"""
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.model_chain.StructuredOutputToToolMessageParser") as mock_parser_class,
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
                return_value=variables,
            ),
        ):
            mock_parser = _make_mock_llm(invoke_return=AIMessage(content="Response with parallel calls"))
            mock_parser_class.return_value = mock_parser

            node = build_model_node(
                llm=mock_llm,
                tools=sample_tools,
                node_options=ModelNodeSettings(use_structured_response=True),
            )

            state: ModelState = {
                "messages": [HumanMessage(content="test query")],
            }
            config = RunnableConfig()

            node.invoke(state, config=config, store=mock_store)

            call_kwargs = mock_parser_class.call_args[1]
            assert call_kwargs["enable_parallel_tool_calls"] is True

    def test_model_node_state_with_decision(self, mock_llm, sample_tools, mock_store, mock_prompt_setup):
        """测试 state 中包含 decision 的情况"""
        mock_template, variables = mock_prompt_setup

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

    def test_model_node_context_variables_integration(self, mock_llm, sample_tools, mock_store, mock_prompt_setup):
        """测试上下文变量的集成"""
        mock_template, _variables = mock_prompt_setup

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

    def test_model_node_extracts_image_from_query_list(self, mock_llm, sample_tools, mock_store):
        mock_template = Mock()
        prompt_value = Mock()
        prompt_value.to_messages.return_value = [
            HumanMessage(content="以下是用户最新提问内容：```这张图片有什么内容?```")
        ]
        mock_template.invoke.return_value = prompt_value
        image_item = {"type": "image_url", "image_url": {"url": "https://example.com/test.png"}}
        variables = {"query": [image_item, {"type": "text", "text": "这张图片有什么内容?"}]}

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=sample_tools),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=sample_tools)
            node.invoke(
                {"messages": [HumanMessage(content=variables["query"])]}, config=RunnableConfig(), store=mock_store
            )

        rendered_messages = mock_llm._invoke_fn.call_args[0][0]
        assert isinstance(rendered_messages[-1], HumanMessage)
        assert rendered_messages[-1].content[0]["type"] == "text"
        assert rendered_messages[-1].content[1] == image_item


def _make_response_queue_llm(responses, aresponses=None):
    """创建按顺序返回响应的 mock LLM，支持 Runnable 链操作。

    Args:
        responses: 同步响应列表，按 pop(0) 顺序消耗
        aresponses: 异步响应列表，如不提供则复用 responses
    """
    queue = list(responses)
    aqueue = list(aresponses) if aresponses else list(responses)
    invoke_counter = [0]
    ainvoke_counter = [0]

    def invoke_fn(input, config=None, **kwargs):
        invoke_counter[0] += 1
        return queue.pop(0) if queue else AIMessage(content="")

    async def ainvoke_fn(input, config=None, **kwargs):
        ainvoke_counter[0] += 1
        return aqueue.pop(0) if aqueue else AIMessage(content="")

    llm = RunnableLambda(invoke_fn, afunc=ainvoke_fn)
    llm.bind_tools = Mock(return_value=llm)
    llm._invoke_count = invoke_counter
    llm._ainvoke_count = ainvoke_counter
    return llm


class TestModelNodeRecoveryLoop:
    """测试 model_node 内部 recovery 循环逻辑"""

    @pytest.fixture
    def mock_store(self):
        """Mock BaseStore"""
        return Mock()

    @pytest.fixture
    def mock_prompt_setup(self):
        """Mock prompt template 和 variables"""
        mock_template = Mock()
        prompt_value = Mock()
        prompt_value.to_messages.return_value = [HumanMessage(content="test")]
        mock_template.invoke = Mock(return_value=prompt_value)

        variables = {"input": "test", "chat_history": [], "agent_scratchpad": []}
        return mock_template, variables

    def test_first_call_success_no_retry(self, mock_store, mock_prompt_setup):
        """测试首次调用成功 → 不重试"""
        mock_llm = _make_response_queue_llm([AIMessage(content="Success response")])
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success response"
            assert mock_llm._invoke_count[0] == 1

    def test_empty_then_success(self, mock_store, mock_prompt_setup):
        """测试首次返回空内容，第二次成功 → recovery 循环重试"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),  # 空 → recovery_retry
                AIMessage(content="Success after retry"),
            ]
        )
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success after retry"
            assert mock_llm._invoke_count[0] == 2

    def test_multiple_empty_then_success(self, mock_store, mock_prompt_setup):
        """测试多次空内容，最终成功 → recovery 循环多次重试"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="Success after 2 retries"),
            ]
        )
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success after 2 retries"
            assert mock_llm._invoke_count[0] == 3

    def test_all_empty_exhausted_returns_last(self, mock_store, mock_prompt_setup):
        """测试全部返回空内容 → 重试耗尽后返回最后一个空响应（不抛异常）

        max_empty_retries=3 表示允许 3 次重试（共 4 次调用）：
        调用1→空(retry1)→调用2→空(retry2)→调用3→空(retry3)→调用4→空(exhausted→end)
        """
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
            ]
        )
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(model_chain_config=ModelChainConfig(max_empty_retries=3)),
            )

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            # recovery 循环耗尽后返回最后一个空响应，不抛异常
            assert result["messages"][0].content == ""
            assert mock_llm._invoke_count[0] == 4

    def test_exception_not_retried(self, mock_store, mock_prompt_setup):
        """测试调用抛出普通异常 → 不重试，直接抛出"""
        invoke_counter = [0]

        def invoke_fn(input, config=None, **kwargs):
            invoke_counter[0] += 1
            raise Exception("Model invocation failed")

        mock_llm = RunnableLambda(invoke_fn)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_llm._invoke_count = invoke_counter
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            with pytest.raises(Exception, match="Model invocation failed"):
                node.invoke(state, config=config, store=mock_store)

            assert mock_llm._invoke_count[0] == 1

    def test_retry_with_tool_calls_eventually_valid(self, mock_store, mock_prompt_setup):
        """测试重试后最终返回有效 tool_calls → 成功"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "search", "args": {"query": "test"}, "id": "1"}],
                ),
            ]
        )
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert len(result["messages"][0].tool_calls) == 1
            assert result["messages"][0].tool_calls[0]["name"] == "search"
            assert mock_llm._invoke_count[0] == 2

    def test_truncated_tool_call_rebuilds_chain(self, mock_store, mock_prompt_setup):
        """测试截断的工具调用触发 chain 重建（max_tokens 提升）

        第一次调用返回截断的 tool_call 响应（finish_reason="length"），
        触发 RECOVERY_TRUNCATION → 工具调用截断分支 → 重建 chain 并重试。
        验证：LLM 被调用两次，最终成功。
        """
        mock_template, variables = mock_prompt_setup

        mock_llm = _make_response_queue_llm(
            [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "search", "args": {"query": "test"}, "id": "1"}],
                    response_metadata={"finish_reason": "length"},
                ),
                AIMessage(content="chain 重建后成功"),
            ]
        )
        # 为 mock LLM 添加 .bind() 支持，因为截断恢复路径会调用 .bind(max_tokens=...)
        mock_llm.bind = Mock(return_value=mock_llm)

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
                return_value=mock_template,
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
                return_value=variables,
            ),
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(
                    model_chain_config=ModelChainConfig(
                        max_empty_retries=3,
                        max_truncated_tool_call_retries=3,
                    )
                ),
            )

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            # 验证最终成功返回
            assert result["messages"][0].content == "chain 重建后成功"
            # 验证 LLM 被调用了两次（初始 + 重建 chain 后重试）
            assert mock_llm._invoke_count[0] == 2


class TestAModelNodeRecoveryLoop:
    """测试 amodel_node 异步 recovery 循环逻辑"""

    @pytest.fixture
    def mock_store(self):
        """Mock BaseStore"""
        return Mock()

    @pytest.fixture
    def mock_prompt_setup(self):
        """Mock prompt template 和 variables"""
        mock_template = Mock()
        prompt_value = Mock()
        prompt_value.to_messages.return_value = [HumanMessage(content="test")]
        mock_template.invoke = Mock(return_value=prompt_value)

        variables = {"input": "test", "chat_history": [], "agent_scratchpad": []}
        return mock_template, variables

    @pytest.mark.asyncio
    async def test_first_call_success_no_retry(self, mock_store, mock_prompt_setup):
        """测试首次调用成功 → 不重试"""
        mock_llm = _make_response_queue_llm([AIMessage(content="Success response")])
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = await node.ainvoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success response"
            assert mock_llm._ainvoke_count[0] == 1

    @pytest.mark.asyncio
    async def test_empty_then_success(self, mock_store, mock_prompt_setup):
        """测试首次返回空内容，第二次成功 → recovery 循环重试"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="Success after retry"),
            ]
        )
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = await node.ainvoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success after retry"
            assert mock_llm._ainvoke_count[0] == 2

    @pytest.mark.asyncio
    async def test_multiple_empty_then_success(self, mock_store, mock_prompt_setup):
        """测试多次空内容，最终成功 → recovery 循环多次重试"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="Success after 2 retries"),
            ]
        )
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = await node.ainvoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success after 2 retries"
            assert mock_llm._ainvoke_count[0] == 3

    @pytest.mark.asyncio
    async def test_all_empty_exhausted_returns_last(self, mock_store, mock_prompt_setup):
        """测试全部返回空内容 → 重试耗尽后返回最后一个空响应（不抛异常）

        max_empty_retries=3 表示允许 3 次重试（共 4 次调用）：
        调用1→空(retry1)→调用2→空(retry2)→调用3→空(retry3)→调用4→空(exhausted→end)
        """
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
            ]
        )
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(model_chain_config=ModelChainConfig(max_empty_retries=3)),
            )

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = await node.ainvoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == ""
            assert mock_llm._ainvoke_count[0] == 4

    @pytest.mark.asyncio
    async def test_exception_not_retried(self, mock_store, mock_prompt_setup):
        """测试调用抛出普通异常 → 不重试，直接抛出"""
        ainvoke_counter = [0]

        async def ainvoke_fn(input, config=None, **kwargs):
            ainvoke_counter[0] += 1
            raise Exception("Model invocation failed")

        mock_llm = RunnableLambda(lambda x, **kw: AIMessage(content=""), afunc=ainvoke_fn)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_llm._ainvoke_count = ainvoke_counter
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            with pytest.raises(Exception, match="Model invocation failed"):
                await node.ainvoke(state, config=config, store=mock_store)

            assert mock_llm._ainvoke_count[0] == 1


def _make_ctx(response, messages=None, model_chain_state=None):
    """构造测试用 ProcessorContext。"""
    if messages is None:
        messages = []
    if model_chain_state is None:
        model_chain_state = ModelChainState()
    return ProcessorContext(
        state={"messages": messages},
        config=RunnableConfig(),
        messages=messages,
        model_chain_state=model_chain_state,
        response=response,
    )


class TestValidateResponse:
    """测试 validate_response 函数"""

    def _make_gate(self, *, enable_judgment_llm: bool = False) -> QualityGate:
        """构造测试用 QualityGate。默认关闭 judgment LLM 避免 test 触发真实 LLM 构造。"""
        return QualityGate(enable_judgment_llm=enable_judgment_llm)

    def test_tool_calls_returns_pv_node(self):
        msg = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}])
        ctx = _make_ctx(msg)
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.TOOL_EXECUTION

    def test_content_returns_end(self):
        msg = AIMessage(content="hello")
        ctx = _make_ctx(msg)
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.NORMAL_COMPLETION

    @pytest.mark.parametrize(
        "content",
        [
            [{"type": "text", "text": "hello"}],
            [{"type": "image_url", "image_url": {"url": "http://example.com"}}],
        ],
    )
    def test_list_content_returns_end(self, content):
        msg = AIMessage(content=content)
        ctx = _make_ctx(msg)
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.NORMAL_COMPLETION

    def test_content_no_finish_reason_returns_normal_completion(self):
        """测试有 content + 无 tool_calls + 无 finish_reason → 正常完成

        参照 hermes-agent 的 map_finish_reason(None) → "stop" 行为：
        当模型输出有内容但没有 finish_reason 时，视为正常完成。
        """
        msg = AIMessage(content="hello")
        assert not msg.response_metadata.get("finish_reason")
        ctx = _make_ctx(msg)
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.NORMAL_COMPLETION

    def test_empty_after_tools_nudge(self):
        tool_msg = ToolMessage(content="result", tool_call_id="1")
        msg = AIMessage(content="")
        ctx = _make_ctx(msg, [tool_msg, msg])
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.RECOVERY_NUDGE

    def test_thinking_only_prefill(self):
        msg = AIMessage(content="<think>reasoning</think>", reasoning_content="deep thought")
        ctx = _make_ctx(msg)
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.RECOVERY_PREFILL

    def test_truncated_response(self):
        msg = AIMessage(content="", response_metadata={"finish_reason": "length"})
        ctx = _make_ctx(msg, model_chain_state=ModelChainState(post_tool_empty_retried=True))
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.RECOVERY_TRUNCATION

    def test_empty_retry(self):
        msg = AIMessage(content="")
        ctx = _make_ctx(msg, model_chain_state=ModelChainState(post_tool_empty_retried=True))
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.RECOVERY_RETRY

    def test_exhausted_retries_returns_end(self):
        msg = AIMessage(content="")
        rs = ModelChainState(
            empty_content_retries=3,
            post_tool_empty_retried=True,
            thinking_prefill_retries=2,
            length_continue_retries=3,
        )
        ctx = _make_ctx(msg, model_chain_state=rs)
        result = self._make_gate().validate_response(ctx)
        assert result == ResponseRoute.NORMAL_COMPLETION


class TestModelNodeRateLimit:
    """测试 model_node 对 RateLimitError 的捕获和重试逻辑"""

    @staticmethod
    def _make_rate_limit_error() -> RateLimitError:
        """创建一个 mock RateLimitError，需要提供 httpx.Response"""
        request = httpx.Request("POST", "https://example.com/v1/chat/completions")
        response = httpx.Response(429, request=request)
        return RateLimitError("rate limited", response=response, body=None)

    @pytest.fixture
    def mock_store(self):
        """Mock BaseStore"""
        return Mock()

    @pytest.fixture
    def mock_prompt_setup(self):
        """Mock prompt template 和 variables"""
        mock_template = Mock()
        prompt_value = Mock()
        prompt_value.to_messages.return_value = [HumanMessage(content="test")]
        mock_template.invoke = Mock(return_value=prompt_value)

        variables = {"input": "test", "chat_history": [], "agent_scratchpad": []}
        return mock_template, variables

    def test_rate_limit_error_retried(self, mock_store, mock_prompt_setup):
        """测试 RateLimitError 后被重试并成功

        模拟 1 次 RateLimitError → 重试 → 成功返回，验证调用次数为 2。
        """
        invoke_counter = [0]

        def invoke_fn(input, config=None, **kwargs):
            invoke_counter[0] += 1
            if invoke_counter[0] == 1:
                raise self._make_rate_limit_error()
            return AIMessage(content="Success after rate limit")

        mock_llm = RunnableLambda(invoke_fn)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_llm._invoke_count = invoke_counter
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
            patch("aidev_agent.config.settings.LLM_RETRY_STRATEGY", "sdk"),
            patch("time.sleep", return_value=None),  # 跳过实际等待
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = node.invoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success after rate limit"
            assert invoke_counter[0] == 2

    def test_rate_limit_error_exhausted(self, mock_store, mock_prompt_setup):
        """测试 RateLimitError 连续发生 → 重试耗尽后抛出异常

        max_empty_retries=3 意味着允许 3 次重试（共 4 次调用），
        第 4 次 RateLimitError 时不再重试，直接抛出。
        """
        invoke_counter = [0]

        def invoke_fn(input, config=None, **kwargs):
            invoke_counter[0] += 1
            raise self._make_rate_limit_error()

        mock_llm = RunnableLambda(invoke_fn)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_llm._invoke_count = invoke_counter
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
            patch("aidev_agent.config.settings.LLM_RETRY_STRATEGY", "sdk"),
            patch("time.sleep", return_value=None),
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(model_chain_config=ModelChainConfig(max_empty_retries=3)),
            )

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            with pytest.raises(RateLimitError):
                node.invoke(state, config=config, store=mock_store)

            # 第 1 次 invoke + 3 次重试 = 4 次调用，第 4 次触发耗尽抛出
            assert invoke_counter[0] == 4

    @pytest.mark.asyncio
    async def test_rate_limit_error_async_retried(self, mock_store, mock_prompt_setup):
        """测试异步 RateLimitError 后被重试并成功"""
        ainvoke_counter = [0]

        async def ainvoke_fn(input, config=None, **kwargs):
            ainvoke_counter[0] += 1
            if ainvoke_counter[0] == 1:
                raise self._make_rate_limit_error()
            return AIMessage(content="Success after rate limit")

        mock_llm = RunnableLambda(lambda x, **kw: AIMessage(content=""), afunc=ainvoke_fn)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_llm._ainvoke_count = ainvoke_counter
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
            patch("aidev_agent.config.settings.LLM_RETRY_STRATEGY", "sdk"),
            patch("asyncio.sleep", AsyncMock(return_value=None)),
        ):
            node = build_model_node(llm=mock_llm, tools=[])

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            result = await node.ainvoke(state, config=config, store=mock_store)

            assert result["messages"][0].content == "Success after rate limit"
            assert ainvoke_counter[0] == 2

    @pytest.mark.asyncio
    async def test_rate_limit_error_async_exhausted(self, mock_store, mock_prompt_setup):
        """测试异步 RateLimitError 连续发生 → 重试耗尽后抛出异常"""
        ainvoke_counter = [0]

        async def ainvoke_fn(input, config=None, **kwargs):
            ainvoke_counter[0] += 1
            raise self._make_rate_limit_error()

        mock_llm = RunnableLambda(lambda x, **kw: AIMessage(content=""), afunc=ainvoke_fn)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_llm._ainvoke_count = ainvoke_counter
        mock_template, variables = mock_prompt_setup

        with (
            patch("aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools", return_value=[]),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template", return_value=mock_template
            ),
            patch(
                "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables", return_value=variables
            ),
            patch("aidev_agent.config.settings.LLM_RETRY_STRATEGY", "sdk"),
            patch("asyncio.sleep", AsyncMock(return_value=None)),
        ):
            node = build_model_node(
                llm=mock_llm,
                tools=[],
                node_options=ModelNodeSettings(model_chain_config=ModelChainConfig(max_empty_retries=3)),
            )

            state: ModelState = {"messages": [HumanMessage(content="test")]}
            config = RunnableConfig()

            with pytest.raises(RateLimitError):
                await node.ainvoke(state, config=config, store=mock_store)

            assert ainvoke_counter[0] == 4
