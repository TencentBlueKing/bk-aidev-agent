# -*- coding: utf-8 -*-
"""context_obs 单元测试：字符度量、模块归因、属性缺省与装配 span 生命周期。"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.packages.opentelemetry.callback_handler import BkAidevAgentCallbackHandler
from aidev_agent.packages.opentelemetry.context_obs import (
    AssemblyObservation,
    ContextChars,
    measure_context,
    observe_assembly,
    observe_compression_call,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode


@pytest.fixture
def tracer_and_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    span_processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
    tracer = provider.get_tracer(__name__)
    yield tracer, exporter
    span_processor.force_flush()
    exporter.clear()


def _ctx(*, messages=None, variables=None, tools=None, callbacks=None, assembly_cache=None) -> ProcessorContext:
    return ProcessorContext(
        state={"messages": []},
        config={"callbacks": callbacks or []},
        messages=list(messages or []),
        variables=dict(variables or {}),
        tools=list(tools or []),
        assembly_cache=assembly_cache,
    )


def _search_tool() -> StructuredTool:
    def search(query: str) -> str:
        """搜索知识库。"""
        return query

    return StructuredTool.from_function(search, name="search", description="搜索知识库")


class TestMeasureContext:
    """字符度量与六模块归因（D-4）。"""

    def test_module_chars_sum_equals_total(self):
        """六项之和恒等于 total，且均非负。"""
        messages = [
            SystemMessage(content="系统提示词"),
            HumanMessage(content="用户问题"),
            ToolMessage(content="工具输出", tool_call_id="c1"),
        ]
        variables = {
            "chat_history": [HumanMessage(content="历史"), AIMessage(content="回答")],
            "agent_scratchpad": "工具中间结果",
            "context": "知识库内容",
            "query": "用户问题",
        }
        chars = measure_context(_ctx(messages=messages, variables=variables), query_text="用户问题")

        assert chars is not None
        attributed = (
            chars.system_prompt
            + chars.conversation_history
            + chars.agent_scratchpad
            + chars.knowledge
            + chars.user_query
            + chars.tool_definitions
        )
        assert attributed == chars.total
        assert (
            min(
                chars.system_prompt,
                chars.conversation_history,
                chars.agent_scratchpad,
                chars.knowledge,
                chars.user_query,
                chars.tool_definitions,
            )
            >= 0
        )

    def test_chars_are_code_points_not_bytes(self):
        """字符数按 Unicode 码点计（与 len(str) 一致），不是字节数。"""
        chars = measure_context(_ctx(messages=[HumanMessage(content="中文abc")]), query_text="中文abc")
        assert chars.total == len("中文abc") == 5
        # 字节数是 11（中文 3 字节 x2 + 3），码点数才是 5
        assert chars.user_query == 5

    def test_image_counted_separately(self):
        """图片字符单列：不计入 total，只体现在 context.chars.image。"""
        url = "https://example.com/a.png"
        content = [
            {"type": "text", "text": "看图"},
            {"type": "image_url", "image_url": {"url": url}},
        ]
        messages = [HumanMessage(content=content)]
        chars = measure_context(_ctx(messages=messages, variables={"query": "看图"}), query_text="看图")

        assert chars.total == len("看图")
        assert chars.image_chars == len(url)

    @pytest.mark.parametrize(
        "block, expected",
        [
            ({"type": "reasoning", "reasoning": "abc"}, 0),
            ({"type": "tool_use", "name": "search", "input": {"query": "q"}}, 0),
            ({"type": "unknown", "url": "abc"}, 0),
            ({"type": "image_url", "image_url": {"url": "abc"}}, 3),
            ({"type": "image", "source": {"type": "base64", "data": "abcd"}}, 4),
            ({"type": "image", "base64": "abc"}, 3),
            ({"type": "input_image", "image_url": "abc"}, 3),
            ({"type": "image", "id": "missing-payload"}, 0),
        ],
    )
    def test_only_image_payload_contributes_image_chars(self, block, expected):
        chars = measure_context(_ctx(messages=[HumanMessage(content=[{"type": "text", "text": "hi"}, block])]))
        assert chars.image_chars == expected
        assert chars.total == 2

    def test_negative_residual_deducts_knowledge(self):
        """残差为负时从 knowledge 扣减，保证非负且和等于 total。"""
        # 渲染后只剩一条短消息，但变量侧的 knowledge 远大于 total
        messages = [HumanMessage(content="hi")]
        variables = {"context": "x" * 100, "query": "hi"}
        chars = measure_context(_ctx(messages=messages, variables=variables), query_text="hi")

        assert chars.total == len("hi")
        assert chars.knowledge == 0
        assert chars.system_prompt == 0
        assert (
            chars.system_prompt
            + chars.conversation_history
            + chars.agent_scratchpad
            + chars.knowledge
            + chars.user_query
            + chars.tool_definitions
            == chars.total
        )

    def test_tool_definitions_and_cache(self):
        """工具 schema 计入 total；序列化结果按工具名缓存在 assembly_cache。"""
        cache: dict = {}
        ctx = _ctx(messages=[HumanMessage(content="hi")], tools=[_search_tool()], assembly_cache=cache)

        with patch(
            "langchain_core.utils.function_calling.convert_to_openai_tool",
            wraps=__import__(
                "langchain_core.utils.function_calling", fromlist=["convert_to_openai_tool"]
            ).convert_to_openai_tool,
        ) as convert:
            first = measure_context(ctx, query_text="hi")
            second = measure_context(ctx, query_text="hi")

        assert first.tool_definitions > 0
        assert second.tool_definitions == first.tool_definitions
        # 第二次命中缓存，不再重复序列化
        assert convert.call_count == 1

    def test_assistant_tool_calls_counted(self):
        """assistant 消息的 tool_calls 参数 JSON 计入 total。"""
        message = AIMessage(
            content="",
            tool_calls=[{"name": "search", "args": {"query": "蓝鲸"}, "id": "call-1", "type": "tool_call"}],
        )
        chars = measure_context(_ctx(messages=[message]), query_text=None)
        assert chars.total == len('{"query": "蓝鲸"}')

    def test_no_optional_modules_write_zero(self):
        """未出现的模块上报 0（不省略）。"""
        chars = measure_context(_ctx(messages=[HumanMessage(content="hi")]), query_text="hi")
        assert chars.conversation_history == 0
        assert chars.agent_scratchpad == 0
        assert chars.knowledge == 0
        assert chars.tool_definitions == 0

    def test_measure_is_fail_open(self):
        """统计异常时返回 None，不向上抛出。"""

        class _Broken:
            messages = None
            variables = None
            tools = None
            assembly_cache = None

        with patch("aidev_agent.packages.opentelemetry.context_obs._measure_context", side_effect=RuntimeError("boom")):
            assert measure_context(_Broken()) is None


class TestAssemblyObservationAttributes:
    """装配 span 属性聚合与缺省规则（REQ-2/3/4/5）。"""

    @pytest.mark.parametrize("token_limit", [None, 1000])
    def test_defaults_without_compression(self, token_limit):
        obs = AssemblyObservation(token_limit=token_limit)
        obs.record_chars(ContextChars(total=10, system_prompt=10))
        attrs = obs.build_attributes()

        assert attrs["context.chars.total"] == 10
        assert attrs["context.chars.system_prompt"] == 10
        assert not any(key.startswith("context.compression.") for key in attrs)
        if token_limit is None:
            assert "context.budget.token_limit" not in attrs
        else:
            assert attrs["context.budget.token_limit"] == token_limit
        assert "context.budget.token_margin" not in attrs

    def test_context_source_names_replace_ambiguous_keys(self):
        obs = AssemblyObservation()
        obs.record_chars(ContextChars(total=7, conversation_history=3, agent_scratchpad=4))
        attrs = obs.build_attributes()
        assert attrs["context.chars.conversation_history"] == 3
        assert attrs["context.chars.agent_scratchpad"] == 4
        assert "context.chars.history" not in attrs
        assert "context.chars.tool_messages" not in attrs

    def test_budget_reported_when_configured(self):
        obs = AssemblyObservation(token_limit=128000, token_margin=100)
        obs.record_chars(ContextChars(total=10, system_prompt=10))
        attrs = obs.build_attributes()

        assert attrs["context.budget.token_limit"] == 128000
        assert attrs["context.budget.token_margin"] == 100


class TestObserveAssembly:
    """装配 span 的产生、层级与状态。"""

    def test_yields_none_without_handler(self):
        ctx = _ctx(messages=[HumanMessage(content="hi")])
        with observe_assembly(ctx) as observation:
            assert observation is None

    def test_span_written_with_attributes(self, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        ctx = _ctx(messages=[HumanMessage(content="hi")], variables={"query": "hi"}, callbacks=[handler])

        with observe_assembly(ctx, token_limit=1000, token_margin=100) as observation:
            observation.record_chars(measure_context(ctx, query_text="hi"))

        spans = exporter.get_finished_spans()
        assert [span.name for span in spans] == ["context.assembly"]
        span = spans[0]
        assert span.status.status_code == StatusCode.OK
        assert span.attributes["context.chars.total"] == 2
        assert span.attributes["context.budget.token_limit"] == 1000
        assert not any(key.startswith("context.compression.") for key in span.attributes)
        # 新增 span 不写 gen_ai.operation.name（不扩充既有值域）
        assert "gen_ai.operation.name" not in span.attributes

    def test_error_marks_span_error_without_compression_summary(self, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        ctx = _ctx(messages=[HumanMessage(content="hi")], callbacks=[handler])

        with pytest.raises(RuntimeError), observe_assembly(ctx, token_limit=1000) as observation:
            observation.record_chars(measure_context(ctx, query_text="hi"))
            raise RuntimeError("token 超限")

        span = exporter.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR
        assert not any(key.startswith("context.compression.") for key in span.attributes)
        assert len(span.events) == 1

    def test_tracing_disabled_builds_no_span(self, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, enabled=False)
        ctx = _ctx(messages=[HumanMessage(content="hi")], callbacks=[handler])

        with observe_assembly(ctx) as observation:
            assert observation is None
        assert exporter.get_finished_spans() == ()


class TestContextObservationRefactor:
    @pytest.mark.parametrize("variable", ["chat_history", "agent_scratchpad"])
    def test_text_attribution_skips_image_payload(self, variable):
        message = HumanMessage(content=[{"type": "text", "text": "abc"}, {"type": "image_url", "data": "large"}])
        ctx = _ctx(messages=[HumanMessage(content="abc")], variables={variable: [message]})
        with patch("aidev_agent.packages.opentelemetry.context_obs._block_payload_text", side_effect=AssertionError):
            chars = measure_context(ctx)
        assert chars is not None
        assert chars.total == 3
        assert (chars.conversation_history if variable == "chat_history" else chars.agent_scratchpad) == 3

    @pytest.mark.parametrize(
        "content, expected",
        [("abc", (3, 0)), (["ab", {"type": "text", "text": "c"}, {"type": "binary", "data": "xyz"}], (3, 0))],
    )
    def test_final_content_chars(self, content, expected):
        ctx = SimpleNamespace(messages=[SimpleNamespace(content=content)], variables={}, tools=[])
        chars = measure_context(ctx)
        assert (chars.total, chars.image_chars) == expected

    @pytest.mark.parametrize("failure", ["set_status", "record_exception", "set_attribute"])
    @pytest.mark.parametrize("business_error", [False, True])
    def test_span_faults_end_and_preserve_business_error(self, failure, business_error, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        error = RuntimeError("business failure")
        with observe_assembly(_ctx(callbacks=[handler])):
            original = handler._create_span

            def broken_span(**kwargs):
                span = original(**kwargs)
                setattr(span, failure, Mock(side_effect=ValueError("telemetry failure")))
                return span

            with patch.object(handler, "_create_span", side_effect=broken_span):
                if business_error:
                    with pytest.raises(RuntimeError) as raised, observe_compression_call(module="knowledge"):
                        raise error
                    assert raised.value is error
                else:
                    with observe_compression_call(module="knowledge") as call:
                        call.set_output(5)
        assert len(exporter.get_finished_spans()) == 2
        assert not handler.spans

    @pytest.mark.parametrize("target", ["_create_span", "_end_span"])
    def test_lifecycle_failure_does_not_replace_business_exception(self, target, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        error = RuntimeError("business failure")
        with (
            patch.object(handler, target, Mock(side_effect=ValueError("telemetry failure"))),
            pytest.raises(RuntimeError) as raised,
            observe_assembly(_ctx(callbacks=[handler])) as observation,
        ):
            assert (observation is None) == (target == "_create_span")
            raise error
        assert raised.value is error

    @pytest.mark.parametrize("fault", ["set_status", "record_exception", "_end_span"])
    def test_custom_span_preserves_business_exception(self, fault, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        error = RuntimeError("business failure")
        with patch.object(handler, "_end_span", wraps=handler._end_span) as end:
            with pytest.raises(RuntimeError) as raised, handler.create_custom_span("custom") as span:
                target = handler if fault == "_end_span" else span
                setattr(target, fault, Mock(side_effect=ValueError("telemetry failure")))
                raise error
            if fault != "_end_span":
                assert end.call_count == 1
        assert raised.value is error

    @pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
    def test_attribute_aggregation_failure_still_ends_span(self, error_type, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        error = error_type("business failure")
        with (
            patch.object(AssemblyObservation, "build_attributes", side_effect=ValueError("telemetry failure")),
            pytest.raises(error_type) as raised,
            observe_assembly(_ctx(callbacks=[handler])),
        ):
            raise error
        assert raised.value is error
        assert len(exporter.get_finished_spans()) == 1
        assert not handler.spans
