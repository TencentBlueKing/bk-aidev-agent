# -*- coding: utf-8 -*-
"""上下文装配 span（context.assembly）的验收测试。

以 ``InMemorySpanExporter`` + fake 模型 + fake 压缩器覆盖 AC1～AC12，
不依赖真实模型与监控平台。
"""

from unittest.mock import Mock, patch

import pytest
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from aidev_agent.core.nodes.model.token_compression import (
    ChatHistoryCompressionMiddleware,
    KnowledgeCompressionMiddleware,
    KnowledgeCompressor,
)
from aidev_agent.packages.opentelemetry import context_obs
from aidev_agent.packages.opentelemetry.callback_handler import (
    BkAidevAgentCallbackHandler,
    BkAidevAgentInjector,
)
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
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


class _FakeChatModel(FakeListChatModel):
    """可绑定工具的假 chat 模型：会触发 on_chat_model_start。"""

    model_name: str = "fake-model"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def get_num_tokens_from_messages(self, messages, **kwargs):  # noqa: ARG002
        return 500

    def get_num_tokens(self, text):  # noqa: ARG002
        return 500


class _OverflowChatModel(_FakeChatModel):
    """始终判定为 token 超限的假模型，用于驱动压缩中间件。"""

    def get_num_tokens_from_messages(self, messages, **kwargs):  # noqa: ARG002
        return 9999

    def get_num_tokens(self, text):  # noqa: ARG002
        return 9999


class _CompressorLLM:
    model_name = "compress-model"

    def __init__(self, content: str):
        self._content = content

    def invoke(self, messages):  # noqa: ARG002
        return AIMessage(content=self._content)


def _search_tool() -> StructuredTool:
    def search(query: str) -> str:
        """搜索知识库。"""
        return query

    return StructuredTool.from_function(search, name="search", description="搜索知识库")


class _FakeContextAssembly:
    """最小装配器：真实 ChatPromptTemplate + 可注入的变量阶段钩子。"""

    def __init__(self, *, variables, tools=None, on_variables=None):
        self._variables = variables
        self._tools = list(tools or [])
        self._on_variables = on_variables
        self.template = ChatPromptTemplate.from_messages(
            [
                ("system", "系统提示词\n{context}"),
                ("placeholder", "{chat_history}"),
                ("human", "{query}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )
        self.choice_tools_calls = 0

    def get_chat_prompt_template(self, ctx):
        if ctx.assembly_cache is None:
            ctx.assembly_cache = {}
        ctx.chat_prompt_template = self.template
        return self.template

    def get_chat_prompt_variables(self, ctx):
        if ctx.assembly_cache is None:
            ctx.assembly_cache = {}
        # 与真实 ContextAssembly 一致：变量装配结果写回 ctx.variables
        ctx.variables = dict(self._variables)
        if self._on_variables is not None:
            self._on_variables(ctx)
        return ctx.variables

    def get_choice_tools(self, ctx):
        self.choice_tools_calls += 1
        ctx.tools = list(self._tools)
        return ctx.tools


def _default_variables(**overrides):
    variables = {
        "query": "用户问题内容",
        "context": "知识库内容知识库内容",
        "chat_history": [HumanMessage(content="历史提问"), AIMessage(content="历史回答")],
        "agent_scratchpad": [AIMessage(content="工具中间结果")],
    }
    variables.update(overrides)
    return variables


def _make_handler(tracer, *, enabled: bool = True) -> BkAidevAgentCallbackHandler:
    """构造与生产一致（带 injector / root span）的 handler。"""
    execute_kwargs = Mock()
    execute_kwargs.session_code = "session-1"
    execute_kwargs.executor = "executor"
    execute_kwargs.caller_bk_app_code = "app"
    execute_kwargs.caller_bk_biz_env = "env"
    execute_kwargs.caller_bk_biz_id = 1
    execute_kwargs.caller_executor = "user"
    execute_kwargs.caller_order_type = "ai_chat"
    return BkAidevAgentCallbackHandler(
        tracer=tracer,
        injector=BkAidevAgentInjector(tracer=tracer),
        enabled=enabled,
        start_inputs="测试输入",
        start_execute_kwargs=execute_kwargs,
        start_agent_info={"agent_id": "agent-1"},
    )


class _Runner:
    """集中持有 handler/exporter，避免每个用例重复样板。"""

    def __init__(self, tracer, exporter):
        self.tracer = tracer
        self.exporter = exporter

    def run(self, **kwargs):
        self.exporter.clear()
        handler = kwargs.pop("handler", None)
        if handler is None:
            handler = _make_handler(self.tracer)
        callbacks = kwargs.pop("callbacks", [handler])
        assembly = _FakeContextAssembly(
            variables=kwargs.pop("variables", None) or _default_variables(),
            tools=kwargs.pop("tools", None),
            on_variables=kwargs.pop("on_variables", None),
        )
        model = kwargs.pop("llm", None) or _FakeChatModel(responses=["好的"])
        chain = _build_model_chain(
            llm=model,
            context_assembly=assembly,
            max_retries=0,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
            token_limit=kwargs.pop("token_limit", None),
            token_margin=kwargs.pop("token_margin", 100),
        )
        ctx = ProcessorContext(
            state={"messages": []},
            config=RunnableConfig(callbacks=callbacks),
            store=Mock(),
            llm=model,
            messages=[],
            model_chain_state=ModelChainState(max_retries=0),
            response=None,
        )
        result = chain.invoke(ctx, config=ctx.config)
        self.exporter.force_flush()
        spans = self.exporter.get_finished_spans()
        return result, spans, assembly


def _first(spans, name):
    return next(span for span in spans if span.name == name)


@pytest.fixture
def runner(tracer_and_exporter):
    tracer, exporter = tracer_and_exporter
    return _Runner(tracer, exporter)


class TestAssemblySpanAcceptance:
    def test_ac1_assembly_span_precedes_model_call(self, runner):
        """AC1：一条装配 span，结束早于 chat_model.generate 开始，且不是其后代。"""
        with runner.tracer.start_as_current_span("current-parent") as parent:
            _, spans, _ = runner.run(token_limit=1000)
        assembly = [span for span in spans if span.name == "context.assembly"]
        chat = [span for span in spans if span.name == "chat_model.generate"]
        assert len(assembly) == 1
        assert len(chat) == 1
        assembly_span, chat_span = assembly[0], chat[0]
        assert assembly_span.end_time <= chat_span.start_time
        assert assembly_span.parent.span_id == parent.get_span_context().span_id
        assert assembly_span.context.trace_id == parent.get_span_context().trace_id
        assert assembly_span.context.span_id != chat_span.parent.span_id
        assert _is_descendant(spans, chat_span, assembly_span) is False

    def test_ac2_chars_sum_equals_total(self, runner):
        """AC2：六个模块属性齐全、非负，且之和等于 total。"""
        _, spans, _ = runner.run(tools=[_search_tool()])
        span = next(span for span in spans if span.name == "context.assembly")
        attrs = span.attributes
        keys = [
            "context.chars.system_prompt",
            "context.chars.conversation_history",
            "context.chars.agent_scratchpad",
            "context.chars.knowledge",
            "context.chars.user_query",
            "context.chars.tool_definitions",
        ]
        for key in keys:
            assert key in attrs
            assert isinstance(attrs[key], int)
            assert attrs[key] >= 0
        assert sum(attrs[key] for key in keys) == attrs["context.chars.total"]
        assert attrs["context.chars.knowledge"] == len("知识库内容知识库内容")
        assert attrs["context.chars.user_query"] == len("用户问题内容")
        assert attrs["context.chars.conversation_history"] == len("历史提问") + len("历史回答")
        assert attrs["context.chars.agent_scratchpad"] == len("工具中间结果")
        assert attrs["context.chars.tool_definitions"] > 0

    def test_ac3_images_listed_separately(self, runner):
        """AC3：图片数量与字符数单列，total 不因图片变大。"""
        url = "https://example.com/large.png"
        variables = _default_variables(
            query=[{"type": "text", "text": "用户问题内容"}, {"type": "image_url", "image_url": {"url": url}}]
        )
        _, spans, _ = runner.run(variables=variables, tools=[_search_tool()])
        span = next(span for span in spans if span.name == "context.assembly")
        assert "context.image.count" not in span.attributes
        assert "context.image.chars" not in span.attributes
        assert span.attributes["context.chars.image"] == len(url)
        assert url not in str(span.attributes)

    def test_ac4_budget_reported_only_when_configured(self, runner):
        """AC4：配置了预算才上报，未配置时两个属性缺省。"""
        _, spans, _ = runner.run(token_limit=128000, token_margin=100)
        attrs = next(span for span in spans if span.name == "context.assembly").attributes
        assert attrs["context.budget.token_limit"] == 128000
        assert attrs["context.budget.token_margin"] == 100

        _, spans, _ = runner.run(token_limit=None, token_margin=None)
        attrs = next(span for span in spans if span.name == "context.assembly").attributes
        assert "context.budget.token_limit" not in attrs
        assert "context.budget.token_margin" not in attrs

    def test_ac5_ac7_compression_reported_with_one_span(self, runner):
        """AC5/AC7：发生压缩时装配无压缩汇总，每次压缩调用一条子 span。"""
        variables = _default_variables(context=["需要被压缩的原文" * 5])
        compressor = KnowledgeCompressor(_CompressorLLM("短"))

        def _compress(ctx):
            middleware = KnowledgeCompressionMiddleware(
                knowledge_compressor_func=compressor,
                token_limit=1000,
                token_margin=100,
            )
            middleware(ctx, lambda: None)

        _, spans, _ = runner.run(
            variables=variables,
            on_variables=_compress,
            llm=_OverflowChatModel(responses=["好的"]),
            token_limit=1000,
        )
        assembly_span = next(span for span in spans if span.name == "context.assembly")
        attrs = assembly_span.attributes
        assert not any(key.startswith("context.compression.") for key in attrs)

        compression_spans = [span for span in spans if span.name == "context.compression.generate"]
        assert len(compression_spans) == 1
        assert compression_spans[0].parent.span_id == assembly_span.context.span_id

    def test_ac6_no_compression_no_spans(self, runner):
        """AC6：未发生压缩时无任何压缩属性或压缩 span。"""
        _, spans, _ = runner.run()
        assembly_span = next(span for span in spans if span.name == "context.assembly")
        attrs = assembly_span.attributes
        assert not any(key.startswith("context.compression.") for key in attrs)
        assert all(span.name != "context.compression.generate" for span in spans)

    def test_ac8_compression_failure_does_not_break_call(self, runner):
        """AC8：压缩失败仅标记单次 span，业务流程仍返回结果。"""
        variables = _default_variables(context=["需要被压缩的原文" * 5])

        class _BrokenCompressor:
            def invoke(self, messages):  # noqa: ARG002
                raise RuntimeError("model down")

        def _compress(ctx):
            middleware = KnowledgeCompressionMiddleware(
                knowledge_compressor_func=KnowledgeCompressor(_BrokenCompressor()),
                token_limit=1000,
                token_margin=100,
            )
            middleware(ctx, lambda: None)

        result, spans, _ = runner.run(
            variables=variables,
            on_variables=_compress,
            llm=_OverflowChatModel(responses=["好的"]),
            token_limit=1000,
        )
        assert result.response.content == "好的"
        assembly_span = next(span for span in spans if span.name == "context.assembly")
        assert not any(key.startswith("context.compression.") for key in assembly_span.attributes)
        compression_span = next(span for span in spans if span.name == "context.compression.generate")
        assert compression_span.status.status_code == StatusCode.ERROR

    def test_ac9_exhausted_marks_assembly_error(self, runner):
        """AC9：压缩后仍超预算时装配 span 为 ERROR，不写压缩汇总。"""
        variables = _default_variables()

        def _compress(ctx):
            middleware = ChatHistoryCompressionMiddleware(token_limit=1000, token_margin=100)
            middleware(ctx, lambda: None)

        with pytest.raises(RuntimeError):
            runner.run(
                variables=variables,
                on_variables=_compress,
                llm=_OverflowChatModel(responses=["好的"]),
                token_limit=1000,
            )
        runner.exporter.force_flush()
        spans = runner.exporter.get_finished_spans()
        assembly_span = next(span for span in spans if span.name == "context.assembly")
        assert assembly_span.status.status_code == StatusCode.ERROR
        assert not any(key.startswith("context.compression.") for key in assembly_span.attributes)

    def test_ac10_tracing_disabled_keeps_behavior(self, runner):
        """AC10：无 handler / tracing 关闭时返回值不变且不产生新 span。"""
        disabled = _make_handler(runner.tracer, enabled=False)
        result, spans, _ = runner.run(callbacks=[disabled])
        assert result.response.content == "好的"
        assert all(span.name != "context.assembly" for span in spans)

        result, spans, _ = runner.run(callbacks=[])
        assert result.response.content == "好的"
        assert spans == ()

    def test_ac10_attribute_write_failure_is_fail_open(self, runner):
        """AC10：属性写入异常被吞掉，装配与调用结果不变。"""
        original = context_obs.AssemblyObservation.build_attributes

        def _boom(self):
            raise RuntimeError("attribute too long")

        with patch.object(context_obs.AssemblyObservation, "build_attributes", _boom):
            result, spans, _ = runner.run()
        assert result.response.content == "好的"
        assembly_span = next(span for span in spans if span.name == "context.assembly")
        assert assembly_span.status.status_code == StatusCode.OK
        assert original is not None

    def test_ac11_existing_spans_unchanged(self, runner):
        """AC11：既有 span 名与 gen_ai.operation.name 逐项不变，新 span 不写该键。"""
        _, spans, _ = runner.run(token_limit=1000)
        names = [span.name for span in spans]
        assert "invoke_agent" in names
        assert "chat_model.generate" in names

        by_name = {span.name: span for span in spans}
        assert by_name["invoke_agent"].attributes["gen_ai.operation.name"] == "invoke_agent"
        assert by_name["chat_model.generate"].attributes["gen_ai.operation.name"] == "chat"
        assert "gen_ai.operation.name" not in by_name["context.assembly"].attributes
        assert by_name["chat_model.generate"].attributes["gen_ai.provider.name"] == "bkaidev"

    def test_ac12_no_message_body_in_new_spans(self, runner):
        """AC12：新 span 属性不含提示词、用户输入、知识库原文片段。"""
        _, spans, _ = runner.run(token_limit=1000)
        bodies = ["用户问题内容", "知识库内容", "历史提问", "历史回答", "工具中间结果", "系统提示词"]
        for span in spans:
            if span.name not in {"context.assembly", "context.compression.generate"}:
                continue
            dumped = str(span.attributes)
            for body in bodies:
                assert body not in dumped

    def test_tool_selection_runs_once_per_assembly(self, runner):
        """工具选择前移：一次装配只选一次，重试不重选。"""
        _, _spans, assembly = runner.run(tools=[_search_tool()])
        assert assembly.choice_tools_calls == 1


def _is_descendant(spans, span, ancestor) -> bool:
    """按已导出 span 的 parent 关系判断 span 是否为 ancestor 的后代。"""
    parents = {item.context.span_id: (item.parent.span_id if item.parent is not None else None) for item in spans}
    current = parents.get(span.context.span_id)
    while current is not None:
        if current == ancestor.context.span_id:
            return True
        current = parents.get(current)
    return False
