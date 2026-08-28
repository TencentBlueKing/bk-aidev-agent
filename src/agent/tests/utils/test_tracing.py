# -*- coding: utf-8 -*-
"""宿主进程接入 Agent trace：每个请求一条独立 trace，并让出站请求把它带给平台。

面向自己起进程驱动 Agent 的宿主（企微长连接是第一个）。走 HTTP 的宿主由 blueapps +
BkAidevAgentInstrumentor 兜住，用不上这里。
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from unittest.mock import patch

import pytest
import requests
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util._once import Once

from aidev_agent.utils import tracing
from aidev_agent.utils.tracing import setup_tracing, start_request_span


@pytest.fixture(scope="module", autouse=True)
def _tracer_provider() -> Iterator[None]:
    """全局 TracerProvider 只能设一次，用内存 exporter 承接本模块产出的 span。

    tracing.py 在 import 时拿到的是 ProxyTracer，会在首次使用时才解析 provider，
    因此这里在 import 之后设置仍然生效。
    """
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
    trace.set_tracer_provider(provider)
    yield
    # instrument 是进程级的，留着会影响同一轮里其它用例发出的请求
    RequestsInstrumentor().uninstrument()


@contextlib.contextmanager
def _capture_outbound_headers() -> Iterator[dict]:
    """拦在 adapter 层：instrument 的注入发生在这之前，看到的就是最终请求头。"""
    captured: dict = {}

    def fake_send(_adapter, request, **_kwargs):
        captured.update(request.headers)
        response = requests.Response()
        response.status_code = 200
        response.request = request
        return response

    with patch.object(requests.adapters.HTTPAdapter, "send", fake_send):
        yield captured


@contextlib.contextmanager
def _forget_the_global_provider() -> Iterator[None]:
    """让全局 provider 回到「没人设过」的状态。

    OTel 用 Once 守住 set_tracer_provider，只设第一次；不复位就测不到选 provider 的分支。
    """
    with patch.object(trace, "_TRACER_PROVIDER", None), patch.object(trace, "_TRACER_PROVIDER_SET_ONCE", Once()):
        yield


def _trace_id_of(headers: dict) -> str:
    """traceparent 格式为 00-<trace_id>-<span_id>-<flags>。"""
    return headers["traceparent"].split("-")[1]


class TestRequestSpan:
    def test_each_request_gets_a_new_trace_id(self):
        """同一进程内连续两次请求必须是两条 trace，否则排障时无法区分。"""
        with start_request_span("wxbot.agent_request") as first:
            pass
        with start_request_span("wxbot.agent_request") as second:
            pass

        assert first and second
        assert len(first) == 32
        assert first != second

    def test_span_is_root_even_when_thread_context_is_polluted(self):
        """常驻 worker 线程可能残留上一次未 detach 的 span，新请求不能继承它的 trace。

        LangChain 回调在生成器被 /stop、超时中途丢弃时不保证走到 on_chain_end，
        attach 的 context 就留在了线程上；继承过去会让后续请求共用同一个 trace id。
        """
        leaked = trace.get_tracer("leak").start_span("leaked")
        leaked_trace_id = format(leaked.get_span_context().trace_id, "032x")
        token = context_api.attach(trace.set_span_in_context(leaked))

        try:
            with start_request_span("wxbot.agent_request") as trace_id:
                assert trace_id != leaked_trace_id
                assert trace.get_current_span().parent is None
        finally:
            context_api.detach(token)
            leaked.end()

    def test_attributes_are_written_to_the_span(self):
        with start_request_span(
            "wxbot.agent_request",
            **{"wxbot.stream_id": "s-1", "wxbot.group_id": "g-1", "wxbot.username": ""},
        ):
            span = trace.get_current_span()
            assert span.attributes["wxbot.stream_id"] == "s-1"
            assert span.attributes["wxbot.group_id"] == "g-1"
            # 空值不写入，避免 APM 上出现一堆空属性
            assert "wxbot.username" not in span.attributes


class TestProviderChoice:
    def test_agent_sdk_provider_is_reused_so_spans_can_reach_apm(self):
        """必须复用 Agent 的 provider：自建的那个没有 exporter，span 建了也上报不出去。"""
        agent_provider = TracerProvider()

        with (
            _forget_the_global_provider(),
            patch.object(tracing, "_agent_tracer_provider", lambda: agent_provider),
        ):
            assert setup_tracing() is True
            assert trace.get_tracer_provider() is agent_provider

    def test_standalone_provider_still_yields_a_usable_trace_id(self):
        """Agent 侧没开 OTel 时也得兜住：本地不上报，但 trace id 仍要能透传给平台。"""
        with _forget_the_global_provider(), patch.object(tracing, "_agent_tracer_provider", lambda: None):
            assert setup_tracing() is True

            with start_request_span("wxbot.agent_request") as trace_id:
                assert len(trace_id) == 32


class TestOutboundPropagation:
    def test_one_request_span_binds_every_outbound_call_into_one_trace(self):
        """一轮对话里发给平台的所有调用必须落在同一条 trace 上。

        断言真实发出的请求头而不是 propagator 本身：平台侧接口有的走宿主自己的
        client、有的走 aidev_bkplugin 的 bkapi client，手工注入总会漏，只有 requests
        这一层的自动注入管得住全部出站调用。
        """
        assert setup_tracing() is True

        with start_request_span("wxbot.agent_request") as trace_id:
            with _capture_outbound_headers() as first:
                requests.get("http://platform.invalid/session")
            with _capture_outbound_headers() as second:
                requests.get("http://platform.invalid/content")

        assert _trace_id_of(first) == trace_id
        assert _trace_id_of(second) == trace_id

    def test_outbound_calls_without_a_request_span_are_unrelated_traces(self):
        """没有 root span 时每次调用自成一条 trace——这正是排障时对不上号的原因。

        instrument 本身会给每个请求开 client span，所以 traceparent 一直都在；
        缺的是把它们收拢到一起的父 span。
        """
        assert setup_tracing() is True

        with _capture_outbound_headers() as first:
            requests.get("http://platform.invalid/session")
        with _capture_outbound_headers() as second:
            requests.get("http://platform.invalid/content")

        assert _trace_id_of(first) != _trace_id_of(second)


class TestConsoleExporter:
    """本地把 span 摘要打到终端，用来区分「没埋点」和「没上报」。"""

    def test_stays_off_unless_asked(self):
        """线上不能被这堆输出淹掉，默认必须是关的。"""
        with patch.object(tracing, "_attach_console_exporter") as attach:
            assert setup_tracing() is True

        attach.assert_not_called()

    def test_the_flag_actually_reaches_the_exporter(self):
        with patch.object(tracing, "_attach_console_exporter", return_value=True) as attach:
            assert setup_tracing(console=True) is True

        attach.assert_called_once()

    def test_attaches_to_the_live_provider_rather_than_a_fresh_one(self):
        """挂错 provider 会打印出另一棵树，看着有 span、要查的那条却还是空的。"""
        provider = TracerProvider()

        with (
            patch.object(trace, "get_tracer_provider", lambda: provider),
            patch.object(provider, "add_span_processor") as add_processor,
        ):
            assert tracing._attach_console_exporter() is True

        assert add_processor.call_count == 1

    def test_a_span_line_carries_its_parent_link(self):
        """靠 span / parent 两列拼树，缺一列就只剩一堆孤立的名字。"""
        tracer = TracerProvider().get_tracer(__name__)
        with (
            tracer.start_as_current_span("agent.execution") as parent,
            tracer.start_as_current_span("tool.execution") as child,
        ):
            pass

        line = tracing._format_span_line(child)

        assert "tool.execution" in line
        assert f"parent={format(parent.get_span_context().span_id, '016x')}" in line
        assert "parent=root" in tracing._format_span_line(parent)
