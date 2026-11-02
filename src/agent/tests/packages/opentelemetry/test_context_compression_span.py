# -*- coding: utf-8 -*-
"""压缩调用 span（context.compression.generate）的验收测试。

覆盖 REQ-6：每次压缩 LLM 调用一条 span、父级为装配 span、并发 N 条、
失败置 ERROR 且装配 span 不写压缩汇总、混元特例 output_chars 等于输入长度。
"""

from unittest.mock import patch

import pytest
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor, ToolOutputCompressor
from aidev_agent.packages.langchain_core.retrievers.utils import HUNYUAN_SPECIFIC_RESPONSE
from aidev_agent.packages.opentelemetry.callback_handler import BkAidevAgentCallbackHandler
from aidev_agent.packages.opentelemetry.context_obs import observe_assembly, observe_compression_call
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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


def _ctx(callbacks) -> ProcessorContext:
    return ProcessorContext(
        state={"messages": []},
        config={"callbacks": callbacks},
        messages=[HumanMessage(content="hi")],
        variables={"query": "hi"},
    )


class _CompressorLLM:
    """压缩专用假模型：返回固定摘要，可携带 usage。"""

    model_name = "compress-model"

    def __init__(self, content: str, usage=None, error: Exception | None = None):
        self._content = content
        self._usage = usage
        self._error = error
        self.call_count = 0

    def invoke(self, messages):
        self.call_count += 1
        if self._error is not None:
            raise self._error
        return AIMessage(content=self._content, usage_metadata=self._usage)


class TestCompressionSpan:
    def test_single_call_creates_child_span(self, tracer_and_exporter):
        """一次知识库压缩调用产生一条 span，父级为装配 span。"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        ctx = _ctx([handler])
        compressor = KnowledgeCompressor(
            _CompressorLLM("摘要", usage={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15})
        )

        with observe_assembly(ctx):
            results = compressor([], "问题", ["一段需要被压缩的知识库原文"])

        assert results == ["摘要"]
        spans = exporter.get_finished_spans()
        names = [span.name for span in spans]
        assert names.count("context.compression.generate") == 1
        compression_span = next(span for span in spans if span.name == "context.compression.generate")
        assembly_span = next(span for span in spans if span.name == "context.assembly")

        assert compression_span.parent.span_id == assembly_span.context.span_id
        attrs = compression_span.attributes
        assert attrs["gen_ai.request.model"] == "compress-model"
        assert attrs["context.compression.module"] == "knowledge"
        assert attrs["context.compression.input_chars"] == len("一段需要被压缩的知识库原文")
        assert attrs["context.compression.output_chars"] == len("摘要")
        assert attrs["gen_ai.usage.input_tokens"] == 12
        assert attrs["gen_ai.usage.output_tokens"] == 3
        # 新增 span 不写 gen_ai.operation.name
        assert "gen_ai.operation.name" not in attrs
        assert compression_span.status.status_code == StatusCode.OK

    def test_parallel_calls_create_one_span_each(self, tracer_and_exporter):
        """并发压缩 N 次产生 N 条 span，父级均正确（跨线程不丢 trace）。"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        ctx = _ctx([handler])
        compressor = ToolOutputCompressor(_CompressorLLM("摘要"))
        tool_positions = [
            (0, ToolMessage(content="工具输出一" * 10, tool_call_id="c1", name="search")),
            (1, ToolMessage(content="工具输出二" * 10, tool_call_id="c2", name="search")),
            (2, ToolMessage(content="工具输出三" * 10, tool_call_id="c3", name="search")),
        ]

        with observe_assembly(ctx):
            results = compressor.llm_intermediate_step_compressor_parallel([], "问题", tool_positions)

        assert results == ["摘要", "摘要", "摘要"]
        spans = exporter.get_finished_spans()
        assembly_span = next(span for span in spans if span.name == "context.assembly")
        compression_spans = [span for span in spans if span.name == "context.compression.generate"]
        assert len(compression_spans) == 3
        for span in compression_spans:
            assert span.parent.span_id == assembly_span.context.span_id
            assert span.attributes["context.compression.module"] == "tool_output"
            assert span.context.trace_id == assembly_span.context.trace_id

    def test_failure_marks_span_error_without_summary(self, tracer_and_exporter):
        """压缩调用失败：span ERROR 记录异常，装配 span 无压缩汇总，业务回退原文。"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        ctx = _ctx([handler])
        compressor = KnowledgeCompressor(_CompressorLLM("", error=RuntimeError("model down")))

        with observe_assembly(ctx):
            results = compressor([], "问题", ["原文"])

        # 既有降级语义：失败时返回原文，不抛异常
        assert results == ["原文"]
        spans = exporter.get_finished_spans()
        compression_span = next(span for span in spans if span.name == "context.compression.generate")
        assert compression_span.status.status_code == StatusCode.ERROR
        assert len(compression_span.events) == 1

    def test_hunyuan_specific_response_output_equals_input(self, tracer_and_exporter):
        """混元特例不压缩时，output_chars 等于输入长度。"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        ctx = _ctx([handler])
        original = "这是一段不会被压缩的原文"
        compressor = KnowledgeCompressor(_CompressorLLM(HUNYUAN_SPECIFIC_RESPONSE))

        with observe_assembly(ctx):
            results = compressor([], "问题", [original])

        assert results == [original]
        compression_span = next(
            span for span in exporter.get_finished_spans() if span.name == "context.compression.generate"
        )
        assert compression_span.attributes["context.compression.output_chars"] == len(original)
        assert compression_span.status.status_code == StatusCode.OK

    def test_no_span_without_assembly_observation(self, tracer_and_exporter):
        """未开启 tracing（无装配观测器）时不建压缩 span，业务行为不变。"""
        _tracer, exporter = tracer_and_exporter
        compressor = KnowledgeCompressor(_CompressorLLM("摘要"))

        assert compressor([], "问题", ["原文"]) == ["摘要"]
        assert exporter.get_finished_spans() == ()

    def test_tool_output_records_within_assembly(self, tracer_and_exporter):
        """工具输出压缩同样一条调用一条 span，不产生任何装配压缩汇总。"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        ctx = _ctx([handler])
        compressor = ToolOutputCompressor(_CompressorLLM("abc"))

        with observe_assembly(ctx):
            results = compressor([], "问题", [(0, ToolMessage(content="abcdefghij", tool_call_id="c1", name="t"))])

        assert results == ["abc"]
        compression_span = next(
            span for span in exporter.get_finished_spans() if span.name == "context.compression.generate"
        )
        assert compression_span.attributes["context.compression.input_chars"] == len("abcdefghij")
        assert compression_span.attributes["context.compression.output_chars"] == len("abc")


class TestCompressionContextIsolation:
    @pytest.mark.parametrize("module", ["knowledge", "tool_output"])
    def test_parallel_calls_use_current_parent(self, module, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        with observe_assembly(_ctx([handler])), tracer.start_as_current_span("current-parent") as parent:
            if module == "knowledge":
                results = KnowledgeCompressor(_CompressorLLM("short"))([], "q", ["a", "b"])
            else:
                positions = [(i, ToolMessage(content="long", tool_call_id=str(i))) for i in range(2)]
                results = ToolOutputCompressor(_CompressorLLM("short"))([], "q", positions)
        assert results == ["short", "short"]
        spans = exporter.get_finished_spans()
        calls = [span for span in spans if span.name == "context.compression.generate"]
        assert len(calls) == 2
        assert all(span.parent.span_id == parent.get_span_context().span_id for span in calls)
        assert all(span.context.trace_id == parent.get_span_context().trace_id for span in calls)
        assembly = next(span for span in spans if span.name == "context.assembly")
        assert not any(key.startswith("context.compression.") for key in assembly.attributes)

    @pytest.mark.parametrize("inner_enabled", [False, True])
    def test_nested_handler_restored_after_error(self, inner_enabled, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        outer = BkAidevAgentCallbackHandler(tracer=tracer)
        inner = BkAidevAgentCallbackHandler(tracer=tracer, enabled=inner_enabled)
        with (
            patch.object(outer, "create_custom_span", wraps=outer.create_custom_span) as outer_create,
            patch.object(inner, "create_custom_span", wraps=inner.create_custom_span) as inner_create,
        ):
            with observe_assembly(_ctx([outer])) as assembly:
                with (
                    pytest.raises(RuntimeError),
                    observe_assembly(_ctx([inner])),
                    observe_compression_call(module="knowledge"),
                ):
                    raise RuntimeError("business error")
                with observe_compression_call(module="tool_output"):
                    pass
            with observe_compression_call(module="knowledge"):
                pass
        assert outer_create.call_count == 2
        assert inner_create.call_count == (2 if inner_enabled else 0)
        calls = [span for span in exporter.get_finished_spans() if span.name == "context.compression.generate"]
        assert len(calls) == (2 if inner_enabled else 1)
        restored = next(span for span in calls if span.attributes["context.compression.module"] == "tool_output")
        assert restored.parent.span_id == assembly.span.get_span_context().span_id
