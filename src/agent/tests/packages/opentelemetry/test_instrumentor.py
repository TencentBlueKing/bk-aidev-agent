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

import contextlib
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.packages.opentelemetry.callback_handler import (
    BkAidevAgentCallbackHandler,
    BkAidevAgentInjector,
)
from aidev_agent.packages.opentelemetry.config import OTelConfig
from aidev_agent.packages.opentelemetry.instrumentor import (
    BkAidevAgentInstrumentor,
    ChatCompletionAgentGetAgentWrapper,
)
from langchain_core.messages import HumanMessage
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel, Field


# Mock ExecuteKwargs with the new definition
class ExecuteKwargs(BaseModel):
    """
    Mock ExecuteKwargs with the new fields from
    /data/workspace/bk-aidev-agent/src/agent/aidev_agent/services/pydantic_models.py
    """

    stream: bool = False
    stream_timeout: int = 30
    passthrough_input: bool = False
    run_agent: bool = False
    # 新增参数
    session_code: str | None = Field(default=None, description="调用时的会话 ID")
    executor: str | None = Field(default=None, description="执行人")
    caller_bk_app_code: str | None = Field(default=None, description="调用者BK应用ID")
    caller_bk_biz_env: str | None = Field(default=None, description="调用者BK业务环境")
    caller_bk_biz_id: int | None = Field(default=None, description="调用者BK业务ID")
    caller_executor: str | None = Field(default=None, description="调用人")
    caller_order_type: str | None = Field(default=None, description="调用AI工单类型")
    caller_trace_context: Dict[str, Any] | None = Field(default=None, description="调用链ID")


@pytest.fixture(scope="function", autouse=False)
def tracer_and_config():
    """
    创建 tracer 和配置用于测试

    注意: 此 fixture 为每个测试创建独立的 TracerProvider 实例，
    不设置全局 TracerProvider，以确保测试之间的隔离性。
    """
    # 创建内存导出器
    exporter = InMemorySpanExporter()

    # 创建 TracerProvider
    provider = TracerProvider()
    span_processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(span_processor)

    # 直接从 provider 获取 tracer，不设置全局 TracerProvider
    tracer = provider.get_tracer(__name__)

    # 创建配置
    config = OTelConfig(otel_endpoints=[])

    # 清空当前的 spans（以防之前的测试留下数据）
    exporter.clear()

    # Patch ExecuteKwargs in instrumentor module to use our mocked version
    with patch("aidev_agent.packages.opentelemetry.instrumentor.ExecuteKwargs", ExecuteKwargs):
        yield tracer, config, exporter

    # 强制刷新所有 spans
    with contextlib.suppress(Exception):
        span_processor.force_flush()

    # 清理
    exporter.clear()


def _build_mock_instance(agent_info: dict | None = None) -> MagicMock:
    """构造带 agent_info 的 mock instance"""
    mock_instance = MagicMock()
    mock_instance.agent_info = agent_info or {
        "agent_id": "test-agent",
        "agent_code": "test_code",
        "agent_name": "测试智能体",
    }
    return mock_instance


class TestBkAidevAgentInstrumentor:
    """测试 BkAidevAgentInstrumentor"""

    def test_instrumentor_requires_config(self, tracer_and_config):
        """测试 BkAidevAgentInstrumentor 必须传入 config"""
        with pytest.raises(TypeError):
            BkAidevAgentInstrumentor()


class TestChatCompletionAgentGetAgentWrapper:
    """测试 ChatCompletionAgentGetAgentWrapper 包装器

    新方案下 wrapper 仅做"延迟构造"：
    - 创建 ``BkAidevAgentInjector`` 实例但不立即 ``on_bk_agent_start``
    - 把 start 入参快照 + injector 都交给 ``BkAidevAgentCallbackHandler``
    - root span 的 start 与 end 都由 callback handler 在执行线程上触发
    - ``_get_agent`` 自身失败直接抛出，不会留下孤儿 root span
    """

    @pytest.mark.parametrize(
        "agent_info, expected_pop_otel",
        [
            ({"agent_id": "id1", "agent_code": "c1", "agent_name": "n1", "otel_info": "x"}, True),
            ({"agent_id": "id2", "agent_code": "c2", "agent_name": "n2"}, False),
        ],
    )
    def test_wrapper_creates_handler_with_deferred_start(self, tracer_and_config, agent_info, expected_pop_otel):
        """包装器应当：
        1. 创建 BkAidevAgentInjector 但**不**立即 on_bk_agent_start
        2. 把 injector + start 入参快照都注入到 BkAidevAgentCallbackHandler
        3. 将 callback handler 追加到 cfg.callbacks
        """
        tracer, config, _ = tracer_and_config
        mock_instance = _build_mock_instance(agent_info)
        wrapper = ChatCompletionAgentGetAgentWrapper(tracer, config)
        execute_kwargs = ExecuteKwargs(session_code="s1", caller_executor="u1")

        def mock_get_agent(*args, **kwargs):
            return MagicMock(), {}

        messages = [HumanMessage(content="问题")]
        _, cfg = wrapper(
            wrapped=mock_get_agent,
            instance=mock_instance,
            args=(messages,),
            kwargs={"execute_kwargs": execute_kwargs},
        )

        # 1. callback handler 已挂载
        assert len(cfg["callbacks"]) == 1
        handler = cfg["callbacks"][0]
        assert isinstance(handler, BkAidevAgentCallbackHandler)
        # 2. handler 持有 injector 但 root span 未创建（延迟到顶层 chain start）
        assert isinstance(handler._injector, BkAidevAgentInjector)
        assert handler._injector.root_span is None, "root span should be deferred until on_chain_start"
        # 3. start 入参快照已挂在 handler 上
        assert handler._start_inputs == "问题"
        assert handler._start_execute_kwargs is execute_kwargs
        # 4. otel_info 已剔除（防止污染 span）
        if expected_pop_otel:
            assert "otel_info" not in handler._start_agent_info
        else:
            assert handler._start_agent_info == agent_info

    def test_wrapper_preserves_existing_callbacks(self, tracer_and_config):
        """包装器需保留已有 callbacks"""
        tracer, config, _ = tracer_and_config
        mock_instance = _build_mock_instance()
        wrapper = ChatCompletionAgentGetAgentWrapper(tracer, config)
        existing_cb = MagicMock()

        def mock_get_agent(*args, **kwargs):
            return MagicMock(), {"callbacks": [existing_cb]}

        _, cfg = wrapper(
            wrapped=mock_get_agent,
            instance=mock_instance,
            args=([HumanMessage(content="hi")],),
            kwargs={"execute_kwargs": ExecuteKwargs()},
        )

        assert existing_cb in cfg["callbacks"]
        callback_handlers = [cb for cb in cfg["callbacks"] if isinstance(cb, BkAidevAgentCallbackHandler)]
        assert len(callback_handlers) == 1

    def test_wrapper_does_not_use_noncanonical_agent_identity(self, tracer_and_config):
        tracer, config, _ = tracer_and_config
        mock_instance = _build_mock_instance({"code": "fallback-code", "name": "fallback-name"})
        wrapper = ChatCompletionAgentGetAgentWrapper(tracer, config)

        _, cfg = wrapper(
            wrapped=lambda *_args, **_kwargs: (MagicMock(), {}),
            instance=mock_instance,
            args=([HumanMessage(content="hi")],),
            kwargs={"execute_kwargs": ExecuteKwargs()},
        )

        handler = cfg["callbacks"][0]
        assert handler._agent_code is None
        assert handler._agent_name is None

    def test_wrapper_propagates_get_agent_failure_without_orphan_span(self, tracer_and_config):
        """``_get_agent`` 自身失败时直接抛出，不应留下任何孤儿 ``agent.execution`` span。

        新方案下 root span 仅在顶层 chain start 时创建，``_get_agent`` 失败意味着图都没
        构造出来，本就不应该有 agent 执行 span。
        """
        tracer, config, exporter = tracer_and_config
        mock_instance = _build_mock_instance()
        wrapper = ChatCompletionAgentGetAgentWrapper(tracer, config)

        def mock_get_agent_failing(*args, **kwargs):
            raise RuntimeError("get_agent failed")

        with pytest.raises(RuntimeError, match="get_agent failed"):
            wrapper(
                wrapped=mock_get_agent_failing,
                instance=mock_instance,
                args=([HumanMessage(content="hi")],),
                kwargs={"execute_kwargs": ExecuteKwargs()},
            )

        # 没有任何 agent.execution span 被导出
        spans = exporter.get_finished_spans()
        assert not any(s.name == "agent.execution" for s in spans)

    def test_callback_handler_creates_and_ends_root_span_in_execution_thread(self, tracer_and_config):
        """新方案核心：root span 的 start 与 end **都**由 callback handler 在执行线程触发。

        - on_chain_start (顶层) → injector.on_bk_agent_start → root span 创建
        - on_chain_end (顶层) → injector.on_bk_agent_end → root span 结束
        - chain.workflow span 以 root span 为父
        """
        import asyncio
        from uuid import uuid4

        tracer, config, exporter = tracer_and_config
        mock_instance = _build_mock_instance()
        wrapper = ChatCompletionAgentGetAgentWrapper(tracer, config)

        def mock_get_agent(*args, **kwargs):
            return MagicMock(), {}

        _, cfg = wrapper(
            wrapped=mock_get_agent,
            instance=mock_instance,
            args=([HumanMessage(content="hi")],),
            kwargs={"execute_kwargs": ExecuteKwargs()},
        )
        handler = cfg["callbacks"][0]
        injector = handler._injector
        # wrap 阶段：root span 还未创建
        assert injector.root_span is None
        assert handler._injector_started is False

        # 模拟顶层 chain start/end —— 必须在同一 event loop（ContextVar 限制）
        chain_run_id = uuid4()
        captured: dict = {}

        async def _scenario():
            await handler.on_chain_start(
                serialized={"name": "agent"}, inputs={"input": "hi"}, run_id=chain_run_id, parent_run_id=None
            )
            captured["root_span_after_start"] = injector.root_span
            await handler.on_chain_end(outputs={"output": "ok"}, run_id=chain_run_id, parent_run_id=None)

        asyncio.run(_scenario())

        # 顶层 on_chain_start 应当触发了 injector.on_bk_agent_start，root span 已创建
        assert captured["root_span_after_start"] is not None
        assert handler._injector_started is True
        # on_chain_end 应当结束了 root span
        assert injector.root_span.end_time is not None
        assert handler._injector_ended is True

        # chain.workflow 应当以 root span 为父
        spans = exporter.get_finished_spans()
        chain_span = next((s for s in spans if s.name.startswith("chain.")), None)
        agent_span = next((s for s in spans if s.name == "agent.execution"), None)
        assert chain_span is not None and agent_span is not None
        assert chain_span.parent.span_id == agent_span.context.span_id

        # 幂等：再次结束不抛异常
        handler._finalize_injector()

    def test_wrapper_propagates_debug_flag_to_injector(self, tracer_and_config):
        """``OTelConfig.debug`` 必须透传给 injector，否则 ``debug.thread_id`` /
        ``debug.end_thread_id`` 不会写入 root span。
        """
        import asyncio
        from uuid import uuid4

        tracer, config, exporter = tracer_and_config
        config.debug = True  # 打开 debug

        mock_instance = _build_mock_instance()
        wrapper = ChatCompletionAgentGetAgentWrapper(tracer, config)

        def mock_get_agent(*args, **kwargs):
            return MagicMock(), {}

        _, cfg = wrapper(
            wrapped=mock_get_agent,
            instance=mock_instance,
            args=([HumanMessage(content="hi")],),
            kwargs={"execute_kwargs": ExecuteKwargs()},
        )
        handler = cfg["callbacks"][0]
        injector = handler._injector
        assert injector.debug is True

        # 通过完整的 chain start/end 流程触发 root span 的 start + end
        chain_run_id = uuid4()

        async def _scenario():
            await handler.on_chain_start(
                serialized={"name": "agent"}, inputs={"input": "hi"}, run_id=chain_run_id, parent_run_id=None
            )
            await handler.on_chain_end(outputs={"output": "ok"}, run_id=chain_run_id, parent_run_id=None)

        asyncio.run(_scenario())

        spans = exporter.get_finished_spans()
        root_spans = [s for s in spans if s.name == "agent.execution"]
        assert len(root_spans) == 1
        assert "debug.thread_id" in root_spans[0].attributes
        assert "debug.end_thread_id" in root_spans[0].attributes

    def test_external_instrumentation_span_attaches_to_root_not_chain(self, tracer_and_config):
        """模拟 ``opentelemetry.instrumentation.langchain.LangchainInstrumentor`` 行为：
        在顶层 chain 执行期间，用 ``tracer.start_span(name)`` 不显式传 context 启动一个 span。
        该 span 应当挂在 ``agent.execution`` 下，而不是被压到 ``chain.workflow`` 之下。

        这是历史层级（``agent.execution → [外部插桩 span, chain.workflow]``）的关键性质，
        本次修复通过在顶层 ``on_chain_start`` 末尾把 root span 重新 attach 为当前 active context
        来恢复该性质。
        """
        import asyncio
        from uuid import uuid4

        tracer, config, exporter = tracer_and_config
        mock_instance = _build_mock_instance()
        wrapper = ChatCompletionAgentGetAgentWrapper(tracer, config)

        def mock_get_agent(*args, **kwargs):
            return MagicMock(), {}

        _, cfg = wrapper(
            wrapped=mock_get_agent,
            instance=mock_instance,
            args=([HumanMessage(content="hi")],),
            kwargs={"execute_kwargs": ExecuteKwargs()},
        )
        handler = cfg["callbacks"][0]

        # 把 chain start / 外部插桩 span / chain end 放在同一个 event loop 里执行，
        # 避免 ``asyncio.run`` 之间 OTel context（ContextVar）跨 loop 失效。
        chain_run_id = uuid4()
        captured: dict = {}

        async def _scenario():
            await handler.on_chain_start(
                serialized={"name": "agent"}, inputs={"input": "hi"}, run_id=chain_run_id, parent_run_id=None
            )
            captured["root_span"] = handler._injector.root_span
            # 模拟外部插桩（如 LangchainInstrumentor）启动 span：
            # 不显式传 context，按 OTel 默认取当前 active context 作为父
            external_span = tracer.start_span("external.workflow")
            captured["external_parent"] = external_span.parent
            external_span.end()
            await handler.on_chain_end(outputs={"output": "ok"}, run_id=chain_run_id, parent_run_id=None)

        asyncio.run(_scenario())

        root_span = captured["root_span"]
        assert root_span is not None

        # 验证：external span 的父应当是 root span，而不是 chain.workflow
        assert captured["external_parent"] is not None, "external span should have a parent"
        assert captured["external_parent"].span_id == root_span.get_span_context().span_id, (
            "external span should attach to root (agent.execution), not chain.workflow"
        )

        # 同时验证 chain span 仍以 root 为父（保持原有结构）
        spans = exporter.get_finished_spans()
        chain_span = next((s for s in spans if s.name.startswith("chain.")), None)
        assert chain_span is not None
        assert chain_span.parent.span_id == root_span.get_span_context().span_id

        # 进而验证 LIFO 栈平衡：on_chain_end 后 _root_attach_token 已被清理
        assert handler._root_attach_token is None
