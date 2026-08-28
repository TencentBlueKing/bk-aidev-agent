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

from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest
from aidev_agent.core.nodes.model.model_chain import (
    _build_model_chain,
    _extract_query_text_and_images,
    build_llm_with_tools,
)
from aidev_agent.core.nodes.model.pydantic_models import (
    ModelChainState,
    ProcessorContext,
)
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableBinding, RunnableConfig, RunnableLambda, RunnableSequence
from langchain_core.tools import BaseTool, StructuredTool
from langchain_openai import ChatOpenAI
from openai import RateLimitError
from pydantic import PrivateAttr

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
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_retries=3),
            response=None,
        )

        result = chain.invoke(initial_ctx)
        assert result.response.content == "Hello, world!"
        assert mock_llm._invoke_count[0] == 1
        """测试空内容重试后成功：首次空 → retry → 第二次有内容"""
        mock_llm = _make_response_queue_llm(
            [
                AIMessage(content="", tool_calls=[]),  # 空 → RecoveryRetryError
                AIMessage(content="重试后成功"),
            ]
        )
        # plan 04 后 _render_messages 是链头，覆盖 ctx.messages——设置渲染输出
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_retries=3),
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
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_retries=3),
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
        mock_llm.retry_strategy = "sdk"

        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        with (
            patch("aidev_agent.core.nodes.model.model_chain.settings.LLM_RETRY_STRATEGY", "llm_gw"),
            patch("time.sleep", return_value=None),
        ):
            chain = _build_model_chain(
                llm=mock_llm,
                context_assembly=mock_context_assembly,
                max_retries=3,
                quality_gate=QualityGate(enable_judge_response=False),
                use_structured_response=False,
                enable_parallel_tool_calls=False,
                use_tool_call_promotion=False,
            )

            initial_ctx = ProcessorContext(
                state={"messages": []},
                config=RunnableConfig(),
                store=Mock(),
                messages=[],
                model_chain_state=ModelChainState(max_retries=3),
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
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test")])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_retries=3),
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
        self._set_rendered_messages(mock_context_assembly, [HumanMessage(content="test"), tool_msg])

        chain = _build_model_chain(
            llm=mock_llm,
            context_assembly=mock_context_assembly,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        initial_ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(),
            store=Mock(),
            messages=[],
            model_chain_state=ModelChainState(max_retries=3),
            response=None,
        )

        result = chain.invoke(initial_ctx)
        assert result.response.content == "处理完成"
        # post_tool_empty_retried 仅由 RECOVERY_NUDGE 分支置 True（quality_gate.py:375）。
        # 若 has_prior_tool_results 误排末尾 ToolMessage，会走 RECOVERY_RETRY，
        # 此标志保持 False，断言失败——从而捕获路由错误。
        assert result.model_chain_state.post_tool_empty_retried is True
        assert mock_llm._invoke_count[0] == 2


# ---------------------------------------------------------------------------
# build_llm_with_tools 单元测试（D-09~D-12 重构 + promotion bug 修复）
# ---------------------------------------------------------------------------


def _make_chainable_llm():
    """创建支持 | 运算符和 bind/bind_tools 的 mock LLM。

    bind/bind_tools 均返回自身（RunnableLambda），使 chain 可拼接。
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


# ---------------------------------------------------------------------------
# max_tokens / tools 回归测试辅助函数
# ---------------------------------------------------------------------------


def _make_real_llm() -> ChatOpenAI:
    """构造一个真实 ChatOpenAI 实例（不打网络，只用于 bind/bind_tools 检查）。"""
    return ChatOpenAI(model="gpt-4o-mini", api_key="sk-test-no-network")


def _make_real_tool() -> StructuredTool:
    """构造一个真实的 StructuredTool，避免 mock。"""

    def _search(q: str) -> str:
        """search tool."""
        return f"result for {q}"

    return StructuredTool.from_function(_search, name="search")


def _collect_binding_kwargs(runnable: Any) -> dict[str, Any]:
    """从 Runnable / RunnableBinding / RunnableSequence 中收集 binding kwargs。

    - RunnableBinding：返回自身 kwargs + 递归 bound
    - RunnableSequence：合并所有 step 的 binding kwargs
    """
    merged: dict[str, Any] = {}

    steps = getattr(runnable, "steps", None)
    if steps is not None:
        for step in steps:
            merged.update(_collect_binding_kwargs(step))
        return merged

    if isinstance(runnable, RunnableBinding):
        merged.update(runnable.kwargs)
        merged.update(_collect_binding_kwargs(runnable.bound))
        return merged

    return merged


def _make_openai_response_dict() -> dict[str, Any]:
    """构造一个合法的 OpenAI chat completion 响应 dict。

    结构需被 ``_create_chat_result`` 接受：含 ``choices``，每个 choice 含
    ``message``（role + content）和 ``finish_reason``。
    """
    return {
        "id": "chatcmpl-test",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "done"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class CapturingChatOpenAI(ChatOpenAI):
    """继承 ChatOpenAI，注入 mock client 捕获 create 调用的 payload。

    不打网络：同步路径走 ``self.client.with_raw_response.create(**payload).parse()``，
    异步路径走 ``await self.async_client.with_raw_response.create(**payload).parse()``。
    两条路径的 payload 都被捕获到 ``_captured_payloads``，用于断言 max_tokens 与
    tools 是否同时到达底层 API 调用。
    """

    _captured_payloads: list = PrivateAttr(default_factory=list)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._captured_payloads = []
        response_dict = _make_openai_response_dict()

        self.client = Mock(spec=["with_raw_response", "create"])
        self.client.with_raw_response = Mock(spec=["create"])

        self.root_client = Mock(spec=["chat", "responses"])
        self.root_client.chat = Mock(spec=["completions"])
        self.root_client.chat.completions = self.client
        self.root_client.responses = Mock(spec=["with_raw_response"])
        self.root_client.responses.with_raw_response = Mock(spec=["create", "parse"])

        self.async_client = Mock(spec=["with_raw_response", "create"])
        self.async_client.with_raw_response = Mock(spec=["create"])

        self.root_async_client = Mock(spec=["chat", "responses"])
        self.root_async_client.chat = Mock(spec=["completions"])
        self.root_async_client.chat.completions = self.async_client
        self.root_async_client.responses = Mock(spec=["with_raw_response"])
        self.root_async_client.responses.with_raw_response = Mock(spec=["create", "parse"])

        def _capture_sync(**payload: Any) -> Any:
            self._captured_payloads.append(payload)
            return Mock(parse=Mock(return_value=response_dict))

        async def _capture_async(**payload: Any) -> Any:
            self._captured_payloads.append(payload)
            return Mock(parse=Mock(return_value=response_dict))

        self.client.with_raw_response.create = _capture_sync
        self.async_client.with_raw_response.create = _capture_async


def _make_context_assembly_with_tools(tools: list[StructuredTool]) -> Mock:
    """构造 mock ContextAssembly，返回指定 tools 与单条 HumanMessage。"""
    ca = Mock()
    ca.get_choice_tools = Mock(return_value=tools)
    ca.get_chat_prompt_variables = Mock(return_value={})
    ca.get_chat_prompt_template = Mock(
        return_value=Mock(invoke=Mock(return_value=Mock(to_messages=Mock(return_value=[HumanMessage(content="hi")]))))
    )
    return ca


def _make_ctx_with_override(max_tokens_override: int | None) -> ProcessorContext:
    return ProcessorContext(
        state={"messages": []},
        config=RunnableConfig(),
        store=Mock(),
        messages=[],
        model_chain_state=ModelChainState(max_retries=3, max_tokens_override=max_tokens_override),
        response=None,
    )


class TestBuildLlmWithTools:
    """测试 build_llm_with_tools 的结构（D-09~D-12）。"""

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
            chain = build_llm_with_tools(
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
            chain = build_llm_with_tools(
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
        chain = build_llm_with_tools(
            llm=llm,
            tools=[],
            use_structured_response=use_structured_response,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=True,
        )
        assert chain is llm


# ---------------------------------------------------------------------------
# max_tokens / tools 回归测试
# ---------------------------------------------------------------------------
# 背景：``llm.bind(max_tokens=...)`` 返回 ``RunnableBinding``，再对它调用
# ``.bind_tools()`` 会经 ``RunnableBinding.__getattr__`` 代理到底层 ChatModel 的
# ``bind_tools``，而 ``bind_tools`` 内部 ``super().bind(tools=...)`` 在底层
# ChatModel 上创建全新的 ``RunnableBinding``，kwargs 只有 tools，max_tokens 被丢弃。
#
# 修复：``build_llm_with_tools`` 不再绑定 max_tokens，改由 ``_call_llm`` /
# ``_acall_llm`` 在 ``invoke`` / ``ainvoke`` 时按 ``max_tokens_override`` 传入，
# 利用 ``RunnableBinding.invoke`` 的 ``{**self.kwargs, **kwargs}`` 合并语义确保
# max_tokens 与 tools 同时到达底层 API 调用。


class TestMaxTokensNotLostInBindToolsBranch:
    """build_llm_with_tools 不绑定 max_tokens，改在 invoke 时传。"""

    @pytest.mark.xfail(
        reason="RunnableBinding.bind_tools 经 __getattr__ 代理到底层 ChatModel，"
        "绕开 RunnableBinding.bind 的 kwargs 合并；新设计在 invoke 时传 max_tokens 规避"
    )
    def test_max_tokens_lost_when_bind_before_bind_tools(self):
        """``llm.bind(max_tokens=...).bind_tools([...])`` 会丢失 max_tokens。

        ``RunnableBinding`` 未重写 ``bind_tools``，属性查找经 ``__getattr__``
        代理到底层 ChatModel 的 ``bind_tools``；``bind_tools`` 内部
        ``super().bind(tools=...)`` 在底层 ChatModel 上创建全新 binding，
        原 binding 的 max_tokens 被丢弃。
        """
        llm = _make_real_llm()
        bound_with_max = llm.bind(max_tokens=16384)
        chain = bound_with_max.bind_tools([_make_real_tool()])

        kwargs = _collect_binding_kwargs(chain)
        assert "tools" in kwargs, "tools 应被绑定"
        assert "max_tokens" in kwargs, (
            f"max_tokens 被丢失！实际 kwargs keys: {sorted(kwargs.keys())}。"
            "RunnableBinding.bind_tools 不会合并已有 kwargs。"
        )
        assert kwargs["max_tokens"] == 16384

    def test_llm_with_tools_does_not_bind_max_tokens_non_structured(self):
        """build_llm_with_tools 在非 structured 分支不绑定 max_tokens。

        新设计移除了 ``llm.bind(max_tokens=...)`` 调用，bind_tools 分支的
        binding kwargs 只含 tools，不含 max_tokens。invoke-time 传参由
        ``TestCallLlmInvokeTimePayload`` 验证。
        """
        llm = _make_real_llm()
        tool = _make_real_tool()
        chain = build_llm_with_tools(
            llm=llm,
            tools=[tool],
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )
        kwargs = _collect_binding_kwargs(chain)
        assert "tools" in kwargs, "tools 应被绑定"
        assert "max_tokens" not in kwargs, "build_llm_with_tools 不应绑定 max_tokens"

    def test_bind_tools_then_bind_preserves_both(self):
        """``llm.bind_tools(tools).bind(max_tokens=...)`` 两者都在。

        ``RunnableBinding.bind`` 被 ``@override`` 重写，内部
        ``kwargs={**self.kwargs, **kwargs}`` 合并；而 ``bind_tools`` 经
        ``__getattr__`` 代理到底层（绕开合并）。顺序决定结果：
        - ``bind(max_tokens)`` → ``bind_tools(tools)``：丢失 max_tokens
        - ``bind_tools(tools)`` → ``bind(max_tokens)``：两者都在
        """
        llm = _make_real_llm()
        tool = _make_real_tool()
        chain = llm.bind_tools([tool]).bind(max_tokens=16384)

        kwargs = _collect_binding_kwargs(chain)
        assert "tools" in kwargs, f"tools 不应丢失！kwargs keys: {sorted(kwargs.keys())}"
        assert "max_tokens" in kwargs, f"max_tokens 应保留！kwargs keys: {sorted(kwargs.keys())}"
        assert kwargs["max_tokens"] == 16384

    def test_llm_with_tools_does_not_bind_max_tokens_structured(self):
        """structured 分支同样不绑定 max_tokens。"""
        llm = _make_real_llm()
        tool = _make_real_tool()
        chain = build_llm_with_tools(
            llm=llm,
            tools=[tool],
            use_structured_response=True,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )
        kwargs = _collect_binding_kwargs(chain)
        assert "max_tokens" not in kwargs, "structured 分支也不应绑定 max_tokens"


class TestCallLlmInvokeTimePayload:
    """验证 _call_llm / _acall_llm 在 invoke / ainvoke 时传入 max_tokens。

    通过继承 ``ChatOpenAI`` 注入 mock client，跑完整的 ``_build_model_chain``
    链路。底层 ``client.create`` 收到的 payload 应同时含 ``max_tokens`` 与
    ``tools``——这证明 ``RunnableBinding.invoke`` 的 ``{**self.kwargs, **kwargs}``
    合并语义把 invoke-time max_tokens 与 binding 的 tools 正确合并到底层 API 调用。
    """

    def test_sync_call_llm_passes_max_tokens_and_tools(self):
        """_call_llm：max_tokens_override 设置时，client.create payload 同时含 max_tokens 与 tools。"""
        llm = CapturingChatOpenAI(model="gpt-4o-mini", api_key="sk-test-no-network")
        tool = _make_real_tool()
        ca = _make_context_assembly_with_tools([tool])

        chain = _build_model_chain(
            llm=llm,
            context_assembly=ca,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        ctx = _make_ctx_with_override(max_tokens_override=16384)
        chain.invoke(ctx)

        assert len(llm._captured_payloads) == 1, f"应只调用一次 client.create，实际 {len(llm._captured_payloads)}"
        payload = llm._captured_payloads[0]
        # langchain_openai 的 ChatOpenAI._get_request_payload 会把 max_tokens
        # 标准化为 max_completion_tokens（OpenAI 2024-09 起的字段名）
        assert payload.get("max_completion_tokens") == 16384, (
            f"max_completion_tokens 应为 16384，实际 payload: {payload.get('max_completion_tokens')}"
        )
        assert "tools" in payload, "payload 应含 tools"
        assert len(payload["tools"]) == 1, f"tools 应有 1 个，实际 {len(payload['tools'])}"
        assert payload["tools"][0]["function"]["name"] == "search", f"tool name 应为 search，实际 {payload['tools'][0]}"

    @pytest.mark.asyncio
    async def test_async_call_llm_passes_max_tokens_and_tools(self):
        """_acall_llm：max_tokens_override 设置时，async_client.create payload 同时含 max_tokens 与 tools。"""
        llm = CapturingChatOpenAI(model="gpt-4o-mini", api_key="sk-test-no-network")
        tool = _make_real_tool()
        ca = _make_context_assembly_with_tools([tool])

        chain = _build_model_chain(
            llm=llm,
            context_assembly=ca,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        ctx = _make_ctx_with_override(max_tokens_override=24576)
        await chain.ainvoke(ctx)

        assert len(llm._captured_payloads) == 1, f"应只调用一次 async_client.create，实际 {len(llm._captured_payloads)}"
        payload = llm._captured_payloads[0]
        assert payload.get("max_completion_tokens") == 24576, (
            f"max_completion_tokens 应为 24576，实际 payload: {payload.get('max_completion_tokens')}"
        )
        assert "tools" in payload, "payload 应含 tools"
        assert len(payload["tools"]) == 1, f"tools 应有 1 个，实际 {len(payload['tools'])}"
        assert payload["tools"][0]["function"]["name"] == "search", f"tool name 应为 search，实际 {payload['tools'][0]}"

    def test_sync_call_llm_no_max_tokens_when_override_none(self):
        """_call_llm：max_tokens_override=None 时，payload 不含 max_tokens，但仍含 tools。"""
        llm = CapturingChatOpenAI(model="gpt-4o-mini", api_key="sk-test-no-network")
        tool = _make_real_tool()
        ca = _make_context_assembly_with_tools([tool])

        chain = _build_model_chain(
            llm=llm,
            context_assembly=ca,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        ctx = _make_ctx_with_override(max_tokens_override=None)
        chain.invoke(ctx)

        assert len(llm._captured_payloads) == 1
        payload = llm._captured_payloads[0]
        assert "max_tokens" not in payload and "max_completion_tokens" not in payload, (
            f"max_tokens_override=None 时不应传 max_tokens，实际 payload keys: {sorted(payload.keys())}"
        )
        assert "tools" in payload, "tools 应始终被绑定"

    @pytest.mark.asyncio
    async def test_async_call_llm_no_max_tokens_when_override_none(self):
        """_acall_llm：max_tokens_override=None 时，payload 不含 max_tokens，但仍含 tools。"""
        llm = CapturingChatOpenAI(model="gpt-4o-mini", api_key="sk-test-no-network")
        tool = _make_real_tool()
        ca = _make_context_assembly_with_tools([tool])

        chain = _build_model_chain(
            llm=llm,
            context_assembly=ca,
            max_retries=3,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )

        ctx = _make_ctx_with_override(max_tokens_override=None)
        await chain.ainvoke(ctx)

        assert len(llm._captured_payloads) == 1
        payload = llm._captured_payloads[0]
        assert "max_tokens" not in payload and "max_completion_tokens" not in payload, (
            f"max_tokens_override=None 时不应传 max_tokens，实际 payload keys: {sorted(payload.keys())}"
        )
        assert "tools" in payload, "tools 应始终被绑定"


class TestExtractQueryTextAndImages:
    """当前轮 query 的 multimodal 提取：只剥离挂载，转换复用 llm_gateway。"""

    def test_extracts_binary_image_as_is_with_text(self):
        binary = {
            "filename": "a.jpeg",
            "mime_type": "image/jpeg",
            "type": "binary",
            "url": "https://example.com/a.jpeg",
        }
        text, images = _extract_query_text_and_images([binary, {"type": "text", "text": "图片内容是啥呀"}])
        assert text == "图片内容是啥呀"
        assert images == [binary]

    def test_keeps_image_url_and_ignores_non_image_binary(self):
        query = [
            {"type": "image_url", "image_url": {"url": "https://example.com/old.png"}},
            {"type": "binary", "mime_type": "application/pdf", "url": "https://example.com/a.pdf"},
            {"type": "text", "text": "看这张"},
        ]
        text, images = _extract_query_text_and_images(query)
        assert text == "看这张"
        assert images == [{"type": "image_url", "image_url": {"url": "https://example.com/old.png"}}]

    def test_render_attaches_binary_image_to_last_human_message(self):
        """_render_messages：binary 图片从 query 剥离后原样挂到最后一条 HumanMessage。"""
        binary = {
            "type": "binary",
            "mime_type": "image/jpeg",
            "url": "https://example.com/curr.jpeg",
        }
        ca = Mock()
        ca.get_choice_tools = Mock(return_value=[])
        ca.get_chat_prompt_variables = Mock(
            return_value={"query": [binary, {"type": "text", "text": "图片内容是啥呀"}]}
        )
        template = Mock()
        template.invoke = Mock(
            return_value=Mock(
                to_messages=Mock(
                    return_value=[
                        HumanMessage(content="history"),
                        HumanMessage(content="以下是用户最新提问内容：图片内容是啥呀"),
                    ]
                )
            )
        )
        ca.get_chat_prompt_template = Mock(return_value=template)

        captured: list[Any] = []

        def invoke_fn(messages, config=None, **kwargs):
            captured.extend(messages)
            return AIMessage(content="ok")

        llm = RunnableLambda(invoke_fn)
        llm.bind_tools = Mock(return_value=llm)
        chain = _build_model_chain(
            llm=llm,
            context_assembly=ca,
            max_retries=0,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )
        chain.invoke(
            ProcessorContext(
                state={"messages": []},
                config=RunnableConfig(),
                store=Mock(),
                messages=[],
                model_chain_state=ModelChainState(max_retries=0),
                response=None,
            )
        )

        assert template.invoke.call_args.args[0]["query"] == "图片内容是啥呀"
        last = captured[-1]
        assert isinstance(last.content, list)
        assert {"type": "text", "text": "以下是用户最新提问内容：图片内容是啥呀"} in last.content
        assert binary in last.content
