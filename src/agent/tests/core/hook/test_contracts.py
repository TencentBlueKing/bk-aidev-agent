# -*- coding: utf-8 -*-
"""hook 协议与执行器契约测试：点位、处理器链、fail-open 与控制流异常。"""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolRuntime
from langgraph.types import Command

from aidev_agent.core.hook import (
    HookAbort,
    HookPoint,
    HookRetry,
    HookRunner,
    HookSet,
)

from .conftest import make_config


def _ctx(messages=None, response=None) -> SimpleNamespace:
    """模型点位的最小 ProcessorContext 替身：runner 只读写 config / messages / response。"""
    return SimpleNamespace(
        config=make_config(),
        messages=list(messages or [HumanMessage(content="hello")]),
        response=response if response is not None else AIMessage(content="answer"),
    )


def _request(args: dict | None = None) -> ToolCallRequest:
    tool = Mock()
    tool.name = "search"
    return ToolCallRequest(
        tool_call={"id": "call-1", "name": "search", "args": args or {"query": "q"}},
        tool=tool,
        state={},
        runtime=ToolRuntime(
            state={},
            context=None,
            config=make_config(),
            stream_writer=Mock(),
            tool_call_id="call-1",
            store=None,
        ),
    )


def test_hook_points_are_fixed() -> None:
    """点位集合固定为 6 个，名称与拼写不得变更。"""
    assert [point.value for point in HookPoint] == [
        "turn_start",
        "model_pre",
        "model_post",
        "tool_pre",
        "tool_post",
        "turn_end",
    ]


def test_hook_set_rejects_unknown_point() -> None:
    with pytest.raises(ValueError):
        HookSet({"unknown_point": [lambda context: None]})


def test_hook_set_rejects_non_callable() -> None:
    with pytest.raises(TypeError):
        HookSet({HookPoint.TOOL_PRE: ["not-callable"]})  # type: ignore[list-item]


def test_hook_set_accepts_string_point_names() -> None:
    """字符串点位名经 _normalize_point 归一化为 HookPoint。"""

    def handler(context):
        return None

    hooks = HookSet({"model_pre": [handler]})

    assert hooks.handlers(HookPoint.MODEL_PRE) == (handler,)


def test_handlers_run_in_injection_order_and_chain_payload() -> None:
    """同点位按注入顺序执行，后一个处理器看到前一个的结果。"""
    seen: list[int] = []

    def first(context):
        seen.append(len(context.payload.messages))
        return [*context.payload.messages, SystemMessage(content="first")]

    def second(context):
        seen.append(len(context.payload.messages))
        return [*context.payload.messages, SystemMessage(content="second")]

    runner = HookRunner(HookSet({HookPoint.MODEL_PRE: [first, second]}))
    ctx = _ctx()
    runner.model_pre(ctx)

    assert [message.content for message in ctx.messages] == ["hello", "first", "second"]
    assert seen == [1, 2]


def test_model_post_uses_and_replaces_ctx_response() -> None:
    """model_post 收到 ctx，可直接改响应或返回新 AIMessage。"""
    seen: list[str] = []

    def replace(context):
        seen.append(context.payload.response.content)
        return context.payload.response.model_copy(update={"content": "FIXED"})

    runner = HookRunner(HookSet({HookPoint.MODEL_POST: [replace]}))
    ctx = _ctx(response=AIMessage(content="raw"))
    runner.model_post(ctx)

    assert seen == ["raw"]
    assert ctx.response.content == "FIXED"


@pytest.mark.parametrize(
    "result",
    [
        ToolMessage(content="blocked", tool_call_id="call-1"),
        Command(update={"messages": [ToolMessage(content="blocked", tool_call_id="call-1")]}),
    ],
)
def test_tool_pre_short_circuits(result) -> None:
    """处理器返回 ToolMessage / Command 时直接短路，工具不再执行。"""
    runner = HookRunner(HookSet({HookPoint.TOOL_PRE: [lambda context: result]}))

    assert runner.tool_pre(_request()) is result


def test_tool_pre_rewrites_request() -> None:
    original = _request()
    rewritten = _request(args={"query": "rewritten"})
    runner = HookRunner(HookSet({HookPoint.TOOL_PRE: [lambda context: rewritten]}))

    assert runner.tool_pre(original) is rewritten


def test_tool_post_chains_multiple_handlers() -> None:
    """同点位多个处理器依次改写 ToolMessage，后一个看到前一个的结果。"""

    def first(context):
        return context.payload.model_copy(update={"content": f"{context.payload.content}:first"})

    def second(context):
        return context.payload.model_copy(update={"content": f"{context.payload.content}:second"})

    runner = HookRunner(HookSet({HookPoint.TOOL_POST: [first, second]}))
    result = runner.tool_post(make_config(), ToolMessage(content="raw", tool_call_id="call-1"))

    assert result is not None and result.content == "raw:first:second"


def test_tool_pre_chains_request_rewrites() -> None:
    """tool_pre 多个处理器依次改写请求，最后一次改写生效。"""

    def rewrite(query):
        return lambda context: context.payload.override(
            tool_call={**context.payload.tool_call, "args": {"query": query}}
        )

    runner = HookRunner(HookSet({HookPoint.TOOL_PRE: [rewrite("first"), rewrite("second")]}))
    result = runner.tool_pre(_request(args={"query": "origin"}))

    assert result.tool_call["args"] == {"query": "second"}


def test_tool_pre_ignores_unrelated_return_type(caplog: pytest.LogCaptureFixture) -> None:
    original = _request()
    runner = HookRunner(HookSet({HookPoint.TOOL_PRE: [lambda context: "deny"]}))

    with caplog.at_level(logging.WARNING):
        assert runner.tool_pre(original) is original
    assert "invalid_result" in caplog.text


def test_exception_degrades_and_keeps_following_handlers(caplog: pytest.LogCaptureFixture) -> None:
    """处理器抛异常时跳过该处理器，同点位其余处理器与业务链路继续。"""
    calls: list[str] = []

    def boom(context):
        calls.append("boom")
        raise RuntimeError("handler failed")

    def keep(context):
        calls.append("keep")
        return ToolMessage(content="rewritten", tool_call_id="call-1")

    message = ToolMessage(content="raw", tool_call_id="call-1")
    runner = HookRunner(HookSet({HookPoint.TOOL_POST: [boom, keep]}))
    with caplog.at_level(logging.WARNING):
        result = runner.tool_post(make_config(), message)

    assert calls == ["boom", "keep"]
    assert result is not None and result.content == "rewritten"
    assert "degraded" in caplog.text


def test_timeout_degrades(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """单处理器超过 TIMEOUT_SECONDS 时按不干预处理并记 warning。"""
    monkeypatch.setattr(HookRunner, "TIMEOUT_SECONDS", 0.05)

    def slow(context):
        time.sleep(0.5)
        return ToolMessage(content="too slow", tool_call_id="call-1")

    runner = HookRunner(HookSet({HookPoint.TOOL_POST: [slow]}))
    with caplog.at_level(logging.INFO):
        result = runner.tool_post(make_config(), ToolMessage(content="raw", tool_call_id="call-1"))

    assert result is None
    assert "timeout" in caplog.text


def test_hook_abort_is_not_swallowed() -> None:
    def abort(context):
        raise HookAbort(HookPoint.MODEL_PRE, "stop here")

    runner = HookRunner(HookSet({HookPoint.MODEL_PRE: [abort]}))
    with pytest.raises(HookAbort, match="stop here"):
        runner.model_pre(_ctx())


def test_hook_retry_is_not_swallowed() -> None:
    def retry(context):
        raise HookRetry("ask again")

    runner = HookRunner(HookSet({HookPoint.MODEL_POST: [retry]}))
    with pytest.raises(HookRetry, match="ask again"):
        runner.model_post(_ctx())


def test_async_handler_is_supported() -> None:
    async def handler(context):
        return AIMessage(content="async")

    runner = HookRunner(HookSet({HookPoint.MODEL_POST: [handler]}))
    ctx = _ctx(response=AIMessage(content="raw"))
    runner.model_post(ctx)

    assert ctx.response.content == "async"


def test_each_execution_logs_structured_record(caplog: pytest.LogCaptureFixture) -> None:
    """每次处理器执行产生一条含 point / handler / status / duration_ms 的日志。"""
    runner = HookRunner(HookSet({HookPoint.TOOL_POST: [lambda context: None]}))
    with caplog.at_level(logging.INFO):
        runner.tool_post(make_config(), ToolMessage(content="raw", tool_call_id="call-1"))

    message = next(each.getMessage() for each in caplog.records if "[Hook] point=" in each.getMessage())
    for field in ("point=tool_post", "handler=", "status=ok", "duration_ms=", "turn=turn-1"):
        assert field in message


def test_turn_end_runs_all_handlers() -> None:
    seen: list[str] = []
    hooks = HookSet({HookPoint.TURN_END: [lambda context: seen.append("first"), lambda context: seen.append("second")]})

    HookRunner(hooks).turn_end(make_config())

    assert seen == ["first", "second"]


def test_empty_hook_set_changes_nothing() -> None:
    runner = HookRunner(HookSet())
    message = ToolMessage(content="raw", tool_call_id="call-1")

    assert runner.model_pre(_ctx()) is None
    assert runner.model_post(_ctx()) is None
    assert runner.tool_post(make_config(), message) is None
    assert runner.turn_end(make_config()) is None


def test_sync_handler_sees_caller_contextvars() -> None:
    """同步处理器在独立线程执行时仍能看到调用方的 contextvars。"""
    import contextvars

    marker: contextvars.ContextVar[str] = contextvars.ContextVar("marker", default="")
    marker.set("trace-ctx")
    seen: list[str] = []

    runner = HookRunner(HookSet({HookPoint.MODEL_PRE: [lambda context: seen.append(marker.get())]}))
    runner.model_pre(_ctx())

    assert seen == ["trace-ctx"]
