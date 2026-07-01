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

from unittest.mock import Mock, patch

import httpx
import pytest
from aidev_agent.core.nodes.model.model_chain import _build_effective_chain, _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import (
    ModelChainConfig,
    ModelChainState,
    ProcessorContext,
)
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSequence
from langchain_core.tools import BaseTool
from openai import RateLimitError

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_rate_limit_error() -> RateLimitError:
    """创建一个 mock RateLimitError，需要提供 httpx.Response"""
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def _make_response_queue_llm(responses):
    """创建按顺序返回响应的 mock LLM（同步版本，独立测试使用）。

    每个测试构建独立的 mock LLM，用于 _build_model_chain 的 .invoke() 调用。
    """
    queue = list(responses)
    invoke_counter = [0]

    def invoke_fn(input, config=None, **kwargs):
        invoke_counter[0] += 1
        return queue.pop(0) if queue else AIMessage(content="")

    llm = RunnableLambda(invoke_fn)
    llm.bind_tools = Mock(return_value=llm)
    llm._invoke_count = invoke_counter
    return llm


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


class TestModelChain:
    """测试 _build_model_chain 生成的 LCEL 链（独立于 build_model_node）"""

    @pytest.fixture
    def mock_context_assembly(self):
        """Mock ContextAssembly。

        _render_messages 现在是链头（plan 04），会调用
        get_chat_prompt_template(ctx).invoke(vars, config).to_messages()
        覆盖 ctx.messages。此 fixture 默认让该链返回空列表；测试可通过
        设置 ca.get_chat_prompt_template().invoke().to_messages.return_value
        覆盖期望的消息（plan 04 后 _render_messages 主动渲染而非透传入口 messages）。
        """
        ca = Mock()
        ca.get_choice_tools = Mock(return_value=[])
        ca.get_chat_prompt_variables = Mock(return_value={})
        # 默认让 _render_messages 渲染出空消息列表
        ca.get_chat_prompt_template = Mock(
            return_value=Mock(invoke=Mock(return_value=Mock(to_messages=Mock(return_value=[]))))
        )
        return ca

    @staticmethod
    def _set_rendered_messages(ca: Mock, messages: list):
        """让 _render_messages（链头）渲染出指定 messages 列表。"""
        ca.get_chat_prompt_template().invoke().to_messages.return_value = messages

    def test_normal_completion_first_try(self, mock_context_assembly):
        """测试正常完成：LLM 返回有效内容 → 不重试，直接返回"""
        mock_llm = _make_response_queue_llm([AIMessage(content="Hello, world!")])
        model_chain_config = ModelChainConfig(max_empty_retries=3)
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            model_chain_config=model_chain_config,
            quality_gate=QualityGate(enable_judgment_llm=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_empty_retries=3),
            response=None,
        )

        result = chain.invoke(initial_ctx)
        assert result.response.content == "Hello, world!"
        assert mock_llm._invoke_count[0] == 1

    def test_empty_then_success_after_retry(self, mock_context_assembly):
        """测试空内容重试后成功：首次空 → retry → 第二次有内容"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),  # 空 → RecoveryRetryError
                AIMessage(content="重试后成功"),
            ]
        )
        model_chain_config = ModelChainConfig(max_empty_retries=3)
        # plan 04 后 _render_messages 是链头，覆盖 ctx.messages——设置渲染输出
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            model_chain_config=model_chain_config,
            quality_gate=QualityGate(enable_judgment_llm=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_empty_retries=3),
            response=None,
        )

        result = chain.invoke(initial_ctx)
        assert result.response.content == "重试后成功"
        assert mock_llm._invoke_count[0] == 2

    def test_all_retries_exhausted_returns_last(self, mock_context_assembly):
        """测试重试耗尽：全部空内容 → 返回最后一个空响应，不抛异常"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
                AIMessage(content="", tool_calls=[]),
            ]
        )
        model_chain_config = ModelChainConfig(max_empty_retries=3)
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            model_chain_config=model_chain_config,
            quality_gate=QualityGate(enable_judgment_llm=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_empty_retries=3),
            response=None,
        )

        result = chain.invoke(initial_ctx)
        assert result.response.content == ""
        assert mock_llm._invoke_count[0] == 4

    def test_rate_limit_error_retried(self, mock_context_assembly):
        """测试 RateLimitError 被捕获 → sleep → 重试 → 成功"""
        invoke_counter = [0]

        def invoke_fn(input, config=None, **kwargs):
            invoke_counter[0] += 1
            if invoke_counter[0] == 1:
                raise _make_rate_limit_error()
            return AIMessage(content="限流后重试成功")

        mock_llm = RunnableLambda(invoke_fn)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_llm._invoke_count = invoke_counter

        model_chain_config = ModelChainConfig(max_empty_retries=3)
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        with (
            patch("aidev_agent.core.nodes.model.model_chain.settings.LLM_RETRY_STRATEGY", "sdk"),
            patch("time.sleep", return_value=None),
        ):
            chain = _build_model_chain(
                llm=mock_llm,
                context_assembly=mock_context_assembly,
                model_chain_config=model_chain_config,
                quality_gate=QualityGate(enable_judgment_llm=False),
                use_structured_response=False,
                enable_parallel_tool_calls=False,
                use_tool_call_promotion=False,
            )

            initial_ctx = ProcessorContext(
                state={"messages": []},
                config=RunnableConfig(),
                store=Mock(),
                messages=[],
                model_chain_state=ModelChainState(max_empty_retries=3),
                response=None,
            )

            result = chain.invoke(initial_ctx)
            assert result.response.content == "限流后重试成功"
            assert invoke_counter[0] == 2

    def test_tool_calls_passthrough(self, mock_context_assembly):
        """测试工具调用：返回 TOOL_EXECUTION → 不重试，原样返回"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[{"name": "search", "args": {"q": "test"}, "id": "1"}]),
            ]
        )
        model_chain_config = ModelChainConfig(max_empty_retries=3)
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            model_chain_config=model_chain_config,
            quality_gate=QualityGate(enable_judgment_llm=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_empty_retries=3),
            response=None,
        )

        result = chain.invoke(initial_ctx)
        assert len(result.response.tool_calls) == 1
        assert result.response.tool_calls[0]["name"] == "search"
        assert mock_llm._invoke_count[0] == 1

    def test_post_tool_nudge_retried(self, mock_context_assembly):
        """测试工具后空响应 → RECOVERY_NUDGE → 重试成功"""
        tool_msg = ToolMessage(content="工具结果", tool_call_id="1")
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),  # 工具后空 → nudge
                AIMessage(content="处理完成"),
            ]
        )
        model_chain_config = ModelChainConfig(max_empty_retries=3)
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test"), tool_msg])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            model_chain_config=model_chain_config,
            quality_gate=QualityGate(enable_judgment_llm=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_empty_retries=3),
            response=None,
        )

        result = chain.invoke(initial_ctx)
        assert result.response.content == "处理完成"
        assert mock_llm._invoke_count[0] == 2


# ---------------------------------------------------------------------------
# _build_effective_chain 单元测试（D-09~D-12 重构 + promotion bug 修复）
# ---------------------------------------------------------------------------


def _make_chainable_llm():
    """创建支持 | 运算符和 bind/bind_tools 的 mock LLM。

    bind/bind_tools 均返回自身（RunnableLambda），使 chain 可拼接。
    记录 bind 调用参数以便断言 max_tokens 是否前置。
    """
    llm = RunnableLambda(lambda x, **kw: AIMessage(content="ok"))
    llm.bind_tools = Mock(return_value=llm)
    llm.bind = Mock(return_value=llm)
    return llm


def _make_mock_tool(name: str = "search") -> BaseTool:
    """创建带 name 属性的 mock BaseTool。"""
    t = Mock(spec=BaseTool)
    t.name = name
    return t


class TestBuildEffectiveChain:
    """测试 _build_effective_chain 的 4 步结构（D-09~D-12）。"""

    @pytest.mark.parametrize(
        "use_structured_response,expected_steps",
        [(False, 2), (True, 3)],
    )
    def test_promotion_applied_when_enabled_and_tools_nonempty(self, use_structured_response, expected_steps):
        """tools 非空 + use_tool_call_promotion=True → chain 末尾含 promotion（两分支统一）

        use_structured_response=True 是 bug 修复——旧代码 structured 分支无 promotion
        （旧代码 structured 分支 steps=2，重构后 steps=3，末尾多一个 promotion）。
        """
        llm = _make_chainable_llm()
        tools = [_make_mock_tool("search")]
        with patch("aidev_agent.core.nodes.model.model_chain.StructuredOutputToToolMessageParser") as mock_parser_cls:
            mock_parser_cls.return_value = RunnableLambda(lambda x: x)
            chain = _build_effective_chain(
                llm=llm,
                tools=tools,
                use_structured_response=use_structured_response,
                enable_parallel_tool_calls=False,
                use_tool_call_promotion=True,
            )
        # chain 应为 RunnableSequence，末尾步骤是 promotion 的 RunnableLambda
        assert isinstance(chain, RunnableSequence)
        assert len(chain.steps) == expected_steps
        last_step = chain.steps[-1]
        assert isinstance(last_step, RunnableLambda)

    @pytest.mark.parametrize(
        "use_structured_response",
        [False, True],
    )
    def test_no_promotion_when_disabled(self, use_structured_response):
        """use_tool_call_promotion=False → 两分支均不追加 promotion。"""
        llm = _make_chainable_llm()
        tools = [_make_mock_tool("search")]
        with patch("aidev_agent.core.nodes.model.model_chain.StructuredOutputToToolMessageParser") as mock_parser_cls:
            mock_parser_cls.return_value = RunnableLambda(lambda x: x)
            chain = _build_effective_chain(
                llm=llm,
                tools=tools,
                use_structured_response=use_structured_response,
                enable_parallel_tool_calls=False,
                use_tool_call_promotion=False,
            )
        if use_structured_response:
            # structured 无 promotion → llm | parser（2 步）
            assert isinstance(chain, RunnableSequence)
            assert len(chain.steps) == 2
        else:
            # 非 structured 无 promotion → 直接返回 llm.bind_tools()（即 llm，非 Sequence）
            assert chain is llm

    @pytest.mark.parametrize(
        "use_structured_response",
        [False, True],
    )
    def test_empty_tools_returns_llm_directly(self, use_structured_response):
        """tools=[] → 提前返回 llm，不追加 promotion，不挂 parser。

        无论 use_structured_response 取值如何，无工具时
        StructuredOutputToToolMessageParser 无意义（其作用是把 JSON
        输出解析为 tool_calls），直接返回 llm。
        """
        llm = _make_chainable_llm()
        chain = _build_effective_chain(
            llm=llm,
            tools=[],
            use_structured_response=use_structured_response,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=True,
        )
        assert chain is llm

    @pytest.mark.parametrize(
        "use_structured_response",
        [False, True],
    )
    def test_max_tokens_override_binds_llm(self, use_structured_response):
        """max_tokens_override=16384 → llm 被 bind(max_tokens=16384)（两分支均生效）。"""
        llm = _make_chainable_llm()
        tools = [_make_mock_tool("search")]
        with patch("aidev_agent.core.nodes.model.model_chain.StructuredOutputToToolMessageParser") as mock_parser_cls:
            mock_parser_cls.return_value = RunnableLambda(lambda x: x)
            _build_effective_chain(
                llm=llm,
                tools=tools,
                use_structured_response=use_structured_response,
                enable_parallel_tool_calls=False,
                use_tool_call_promotion=False,
                max_tokens_override=16384,
            )
        llm.bind.assert_called_once_with(max_tokens=16384)

    @pytest.mark.parametrize(
        "use_structured_response",
        [False, True],
    )
    def test_no_max_tokens_when_override_none(self, use_structured_response):
        """max_tokens_override=None → llm 不被 bind(max_tokens=...)。"""
        llm = _make_chainable_llm()
        tools = [_make_mock_tool("search")]
        with patch("aidev_agent.core.nodes.model.model_chain.StructuredOutputToToolMessageParser") as mock_parser_cls:
            mock_parser_cls.return_value = RunnableLambda(lambda x: x)
            _build_effective_chain(
                llm=llm,
                tools=tools,
                use_structured_response=use_structured_response,
                enable_parallel_tool_calls=False,
                use_tool_call_promotion=False,
                max_tokens_override=None,
            )
        llm.bind.assert_not_called()
