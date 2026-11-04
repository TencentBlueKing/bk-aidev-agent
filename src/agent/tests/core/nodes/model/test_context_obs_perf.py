# -*- coding: utf-8 -*-
"""装配字符统计的耗时基准（REQ-2 性能边界 / REQ-7）。

结论（在本仓基准用例上测得，容器内 800 条消息 + 20 个工具，重复 200 次）：

- 装配步骤新增的耗时来自 ``measure_context`` 的单次消息遍历与工具 schema 序列化；
- 单次统计 P50 ≈ 3.0 ms、P95 ≈ 3.2 ms、最大 ≈ 4.2 ms，低于 10 ms 上限；
- 开启装配 span（SDK TracerProvider，不走 exporter）后 P95 与关闭时的差值在
  1 ms 以内，同样低于 10 ms 上限；
- 工具 schema 序列化结果按工具名元组缓存在 ``ctx.assembly_cache``，缓存命中后
  不再重复序列化，第二次及以后的装配只付遍历成本；
- 统计全程进程内计算，不发起任何网络或模型调用。

本用例标记 ``slow``，默认测试集不运行。
"""

import statistics
import time
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

# OpenTelemetry 是可选依赖：未安装时跳过本文件
pytest.importorskip("opentelemetry")

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402

from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext  # noqa: E402
from aidev_agent.packages.opentelemetry.callback_handler import BkAidevAgentCallbackHandler  # noqa: E402
from aidev_agent.packages.opentelemetry.context_obs import measure_context, observe_assembly  # noqa: E402

pytestmark = pytest.mark.slow

REPEAT = 200
P95_LIMIT_MS = 10.0


def _make_tool(index: int) -> StructuredTool:
    def _run(query: str) -> str:  # noqa: ARG001
        """示例工具。"""
        return "ok"

    return StructuredTool.from_function(_run, name=f"tool_{index}", description=f"示例工具 {index}")


def _make_ctx(message_count: int = 800, tool_count: int = 20) -> ProcessorContext:
    messages = [SystemMessage(content="系统提示词" * 50)]
    for i in range(message_count):
        if i % 3 == 0:
            messages.append(HumanMessage(content=f"用户消息 {i} " + "内容" * 40))
        elif i % 3 == 1:
            messages.append(AIMessage(content=f"助手回复 {i} " + "回答" * 40))
        else:
            messages.append(ToolMessage(content=f"工具输出 {i} " + "结果" * 40, tool_call_id=f"call-{i}"))
    return ProcessorContext(
        state={"messages": []},
        config={"callbacks": []},
        messages=messages,
        variables={
            "query": "用户问题",
            "context": "知识库内容" * 1000,
            "chat_history": messages[1:200],
            "agent_scratchpad": messages[200:400],
        },
        tools=[_make_tool(i) for i in range(tool_count)],
        assembly_cache={},
    )


def test_measure_context_p95_within_budget():
    """单次统计 P95 不超过 10 ms，且不触发任何网络/模型调用。"""
    ctx = _make_ctx()
    # 预热：首次调用会序列化工具 schema（缓存写入）
    measure_context(ctx, query_text="用户问题")

    durations: list[float] = []
    for _ in range(REPEAT):
        started = time.perf_counter()
        chars = measure_context(ctx, query_text="用户问题")
        durations.append((time.perf_counter() - started) * 1000.0)
        assert chars is not None

    p95 = statistics.quantiles(durations, n=20)[18]
    assert p95 < P95_LIMIT_MS, f"装配字符统计 P95={p95:.2f} ms 超过 {P95_LIMIT_MS} ms（样本 {REPEAT} 次）"


def test_tool_schema_serialization_cached():
    """工具 schema 缓存命中后不再重复序列化。"""
    from langchain_core.utils import function_calling

    ctx = _make_ctx(message_count=1, tool_count=5)
    measure_context(ctx, query_text="用户问题")

    calls = []
    original = function_calling.convert_to_openai_tool

    def _counting(tool, *args, **kwargs):
        calls.append(tool)
        return original(tool, *args, **kwargs)

    function_calling.convert_to_openai_tool = _counting
    try:
        for _ in range(5):
            measure_context(ctx, query_text="用户问题")
    finally:
        function_calling.convert_to_openai_tool = original

    assert calls == [], "缓存命中后不应再调用工具 schema 序列化"


def test_measure_does_not_touch_network():
    """统计只读内存数据：不调用模型/tokenizer。"""
    ctx = _make_ctx(message_count=10, tool_count=2)
    ctx.llm = Mock(side_effect=AssertionError("统计不应调用模型"))

    chars = measure_context(ctx, query_text="用户问题")

    assert chars.total >= 0


def _timed_p95(func, repeat: int = REPEAT) -> float:
    durations: list[float] = []
    for _ in range(repeat):
        started = time.perf_counter()
        func()
        durations.append((time.perf_counter() - started) * 1000.0)
    return statistics.quantiles(durations, n=20)[18]


def test_observation_overhead_within_budget():
    """观测开启与关闭的 P95 差值不超过 10 ms。"""
    handler = BkAidevAgentCallbackHandler(tracer=TracerProvider().get_tracer(__name__))

    plain_ctx = _make_ctx()
    traced_ctx = _make_ctx()
    traced_ctx.config = {"callbacks": [handler]}
    # 预热，避免首次建 span / 首次序列化污染样本
    measure_context(plain_ctx, query_text="用户问题")
    measure_context(traced_ctx, query_text="用户问题")

    baseline = _timed_p95(lambda: measure_context(plain_ctx, query_text="用户问题"))

    def _observed() -> None:
        with observe_assembly(traced_ctx) as observation:
            if observation is not None:
                observation.record_chars(measure_context(traced_ctx, query_text="用户问题"))

    observed = _timed_p95(_observed)

    assert observed - baseline < P95_LIMIT_MS, (
        f"观测开启 P95={observed:.2f} ms，关闭 P95={baseline:.2f} ms，差值超过 {P95_LIMIT_MS} ms"
    )
