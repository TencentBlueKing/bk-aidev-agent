# -*- coding: utf-8 -*-
"""工具循环拒绝与内容路径失败的 Trace 表达。

用 ``InMemorySpanExporter`` 断言 ``tool.execution`` span 的名称、状态与属性，
确认拒绝调用与真实调用同格式上报 ``tool.name`` / ``tool.input``。
"""

import asyncio

import pytest
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.nodes.tool.node import default_tool_call_handler
from aidev_agent.packages.opentelemetry.callback_handler import BkAidevAgentCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from typing_extensions import Annotated, TypedDict


class _State(TypedDict):
    messages: Annotated[list, add_messages]


@tool
def echo(text: str) -> str:
    """回显文本。"""
    return f"echo:{text}"


@tool
def passthrough(text: str) -> str:
    """原样返回文本。"""
    return text


@pytest.fixture
def handler_and_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    handler = BkAidevAgentCallbackHandler(tracer=provider.get_tracer(__name__))
    return handler, exporter


def _call(index: int, name: str = "echo", text: str = "x") -> dict:
    return {"name": name, "args": {"text": text}, "id": f"call-{index}", "type": "tool_call"}


def _state(rounds: int, *, name: str = "echo", text: str = "x") -> dict:
    messages: list = [HumanMessage(content="重复调用测试")]
    for index in range(rounds):
        messages.append(AIMessage(content="", tool_calls=[_call(index, name, text)]))
        messages.append(ToolMessage(content=f"echo:{text}", tool_call_id=f"call-{index}", name=name))
    messages.append(AIMessage(content="", tool_calls=[_call(rounds, name, text)]))
    return {"messages": messages}


def _single_call_state(text: str = "x", name: str = "passthrough") -> dict:
    return {
        "messages": [
            HumanMessage(content="普通调用"),
            AIMessage(content="", tool_calls=[_call(0, name, text)]),
        ]
    }


def _run(state: dict, handler, *, use_async: bool = False, tools=None) -> dict:
    node = build_tool_node(
        tools=tools or [echo, passthrough], node_options=ToolNodeSettings(enable_tool_loop_guard=True)
    )
    graph = StateGraph(_State)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile()
    config = {"callbacks": [handler]}
    if use_async:
        return asyncio.run(compiled.ainvoke(state, config=config))
    return compiled.invoke(state, config=config)


def _tool_spans(exporter: InMemorySpanExporter) -> list:
    return [span for span in exporter.get_finished_spans() if span.name == "tool.execution"]


def _last_tool_message(result: dict) -> ToolMessage:
    return [msg for msg in result["messages"] if isinstance(msg, ToolMessage)][-1]


_VOLATILE_ATTRIBUTES = {"agent.conversation_root_span_id"}


def _stable_attributes(span) -> dict:
    """剔除随 handler 实例变化的属性，只比对与工具调用语义相关的部分。"""
    return {key: value for key, value in dict(span.attributes).items() if key not in _VOLATILE_ATTRIBUTES}


class TestRejectionSpan:
    def test_rejection_span_error_and_no_result(self, handler_and_exporter):
        handler, exporter = handler_and_exporter
        message = _last_tool_message(_run(_state(3), handler))
        spans = _tool_spans(exporter)
        assert message.status == "error"
        assert len(spans) == 1
        assert spans[0].status.status_code.name == "ERROR"
        assert spans[0].attributes["error.type"] == "ToolLoopRejection"
        assert "gen_ai.tool.call.result" not in spans[0].attributes

    def test_rejection_span_matches_real_span_payload(self, handler_and_exporter):
        handler, exporter = handler_and_exporter
        _run(_state(0), handler)
        _run(_state(3), handler)
        real_span, rejected_span = _tool_spans(exporter)[0], _tool_spans(exporter)[-1]
        assert real_span.attributes["tool.name"] == rejected_span.attributes["tool.name"]
        assert real_span.attributes["tool.input"] == rejected_span.attributes["tool.input"]
        assert (
            real_span.attributes["gen_ai.tool.call.arguments"]
            == (rejected_span.attributes["gen_ai.tool.call.arguments"])
        )

    def test_success_span_stays_ok(self, handler_and_exporter):
        handler, exporter = handler_and_exporter
        _run(_state(0), handler, use_async=True)
        spans = _tool_spans(exporter)
        assert [span.status.status_code.name for span in spans] == ["OK"]
        assert "error.type" not in spans[0].attributes

    def test_async_rejection_span(self, handler_and_exporter):
        handler, exporter = handler_and_exporter
        _last_tool_message(_run(_state(3), handler, use_async=True))
        spans = _tool_spans(exporter)
        assert len(spans) == 1
        assert spans[0].status.status_code.name == "ERROR"
        assert spans[0].attributes["error.type"] == "ToolLoopRejection"


class TestContentPathStatus:
    @pytest.mark.parametrize("content", ["[ERROR] boom", "   [ERROR] boom"])
    def test_error_prefix_marks_failed(self, handler_and_exporter, content):
        handler, exporter = handler_and_exporter
        message = _last_tool_message(_run(_single_call_state(content), handler))
        span = _tool_spans(exporter)[0]
        assert message.status == "error"
        assert span.status.status_code.name == "ERROR"
        assert span.attributes["error.type"] == "ToolResultError"
        assert span.attributes["gen_ai.tool.call.result"] == content

    @pytest.mark.parametrize("content", ["start [ERROR] middle", "tail [ERROR]"])
    def test_error_marker_elsewhere_stays_success(self, handler_and_exporter, content):
        handler, exporter = handler_and_exporter
        message = _last_tool_message(_run(_single_call_state(content), handler))
        span = _tool_spans(exporter)[0]
        assert message.status == "success"
        assert span.status.status_code.name == "OK"
        assert "error.type" not in span.attributes

    def test_async_error_prefix_marks_failed(self, handler_and_exporter):
        handler, exporter = handler_and_exporter
        message = _last_tool_message(_run(_single_call_state("[ERROR] boom"), handler, use_async=True))
        assert message.status == "error"
        assert _tool_spans(exporter)[0].attributes["error.type"] == "ToolResultError"


class TestPlainCallUnchanged:
    def test_plain_call_matches_bypassed_guard(self, handler_and_exporter):
        handler, exporter = handler_and_exporter
        guarded = _last_tool_message(_run(_single_call_state(), handler))
        guarded_span = _tool_spans(exporter)[0]

        bypassed_exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(bypassed_exporter))
        bypassed_handler = BkAidevAgentCallbackHandler(tracer=provider.get_tracer(__name__))
        bypassed_node = ToolNode(
            tools=[echo, passthrough],
            handle_tool_errors=default_tool_call_handler,
        )
        graph = StateGraph(_State)
        graph.add_node("tools", bypassed_node)
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        bypassed = _last_tool_message(
            graph.compile().invoke(_single_call_state(), config={"callbacks": [bypassed_handler]})
        )
        bypassed_span = _tool_spans(bypassed_exporter)[0]

        assert guarded.content == bypassed.content
        assert guarded.status == bypassed.status
        assert guarded.name == bypassed.name
        assert guarded.tool_call_id == bypassed.tool_call_id
        assert guarded_span.name == bypassed_span.name
        assert guarded_span.status.status_code == bypassed_span.status.status_code
        # conversation_root_span_id 由各 handler 的根 span 随机生成，与本次变更无关
        assert _stable_attributes(guarded_span) == _stable_attributes(bypassed_span)


class TestUntrustedContentStatus:
    @pytest.mark.parametrize("use_async", [False, True])
    def test_mcp_error_content_matches_span_status(self, handler_and_exporter, use_async):
        handler, exporter = handler_and_exporter
        external = passthrough.model_copy(update={"metadata": {"mcp_name": "fake"}})
        result = _run(_single_call_state("[ERROR] boom"), handler, use_async=use_async, tools=[echo, external])
        message = _last_tool_message(result)
        assert message.status == "error" and message.content.startswith("<untrusted>")
        span = _tool_spans(exporter)[0]
        assert span.status.status_code.name == "ERROR"
        assert span.attributes["error.type"] == "ToolResultError"
