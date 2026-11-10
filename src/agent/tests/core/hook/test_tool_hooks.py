# -*- coding: utf-8 -*-
"""工具点位测试：tool_pre 短路 / 改写，tool_post 改写原生 ToolMessage 与 Command 结果，同步 / 异步双跑。"""

from __future__ import annotations

from typing import Annotated, List

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from typing_extensions import TypedDict

from aidev_agent.core.hook import HookPoint, HookRunner, HookSet
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.nodes.tool.result_limit_wrapper import TOOL_RESULT_TOO_LONG_MESSAGE
from aidev_agent.utils.tool_result import build_tool_rejection_message

from .conftest import make_config

MESSAGES = [HumanMessage(content="hello")]


class ToolState(TypedDict):
    """最简工具节点图状态。"""

    messages: Annotated[List, add_messages]


def _tool_call(tool_call_id: str = "call-1", name: str = "echo", args: dict | None = None) -> dict:
    return {"name": name, "args": args if args is not None else {"query": "origin"}, "id": tool_call_id}


def _state(tool_calls: list[dict]) -> dict:
    return {"messages": [*MESSAGES, AIMessage(content="", tool_calls=tool_calls)]}


def _graph(node):
    graph = StateGraph(ToolState)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile()


def _run_node(node, state: dict, config) -> dict:
    return _graph(node).invoke(state, config)


async def _await_or_call(node, state: dict, config, use_async: bool) -> dict:
    """同步 / 异步双跑，覆盖 sync wrapper 与 awrap_tool_call 链。"""
    graph = _graph(node)
    return await graph.ainvoke(state, config) if use_async else graph.invoke(state, config)


def _build_node(tools, hooks: HookSet, **options):
    node_options = ToolNodeSettings(
        use_tool_redaction=False,
        use_tool_untrusted_sanitize=False,
        use_json_repair_on_error=False,
        enable_tool_loop_guard=False,
        **options,
    )
    return build_tool_node(tools=tools, node_options=node_options, hook_runner=HookRunner(hooks))


def _echo_tool(calls: list[str]):
    @tool
    def echo(query: str) -> str:
        """Echo the query."""
        calls.append(query)
        return f"echo:{query}"

    return echo


def test_tool_pre_short_circuit_blocks_execution() -> None:
    """tool_pre 返回 ToolMessage 时工具不执行，拒绝结果落库（不带审批跳过标记）。"""
    calls: list[str] = []

    def deny(context):
        return build_tool_rejection_message(context.payload, "not allowed")

    hooks = HookSet({HookPoint.TOOL_PRE: [deny]})
    node = _build_node([_echo_tool(calls)], hooks)

    result = _run_node(node, _state([_tool_call()]), make_config())

    message = result["messages"][-1]
    assert calls == []
    assert message.status == "error"
    assert message.content == "not allowed"
    assert message.additional_kwargs == {}


def test_tool_pre_rewrites_arguments() -> None:
    """tool_pre 返回改写后的 ToolCallRequest，工具收到新参数。"""
    calls: list[str] = []

    def rewrite(context):
        request = context.payload
        return request.override(tool_call={**request.tool_call, "args": {"query": "changed"}})

    hooks = HookSet({HookPoint.TOOL_PRE: [rewrite]})
    node = _build_node([_echo_tool(calls)], hooks)

    _run_node(node, _state([_tool_call()]), make_config())

    assert calls == ["changed"]


def test_tool_pre_triggers_once_per_call() -> None:
    """每次工具调用恰好触发一次 tool_pre（并行调度顺序不作断言）。"""
    seen: list[str] = []
    hooks = HookSet({HookPoint.TOOL_PRE: [lambda context: seen.append(context.payload.tool_call["id"])]})
    node = _build_node([_echo_tool([])], hooks)

    _run_node(node, _state([_tool_call("call-1"), _tool_call("call-2")]), make_config())

    assert sorted(seen) == ["call-1", "call-2"]


def test_tool_pre_reports_real_tool_name() -> None:
    """tool_pre 收到真实工具名与 tool_call_id。"""
    seen: list[tuple[str, str]] = []
    hooks = HookSet(
        {
            HookPoint.TOOL_PRE: [
                lambda context: seen.append((context.payload.tool.name, context.payload.tool_call["id"]))
            ]
        }
    )
    node = _build_node([_echo_tool([])], hooks)

    _run_node(node, _state([_tool_call()]), make_config())

    assert seen == [("echo", "call-1")]


def test_tool_post_sees_raw_result_and_flows_through_content_error() -> None:
    """tool_post 看到未截断原文；返回的新消息继续流经 _content_error 重新识别错误。"""
    seen: list[str] = []

    def handler(context):
        seen.append(context.payload.content)
        return context.payload.model_copy(update={"content": "[ERROR]replaced"})

    hooks = HookSet({HookPoint.TOOL_POST: [handler]})
    node = _build_node([_echo_tool([])], hooks)

    result = _run_node(node, _state([_tool_call()]), make_config())

    message = result["messages"][-1]
    assert seen == ["echo:origin"]
    assert message.content == "[ERROR]replaced"
    assert message.status == "error"


def test_tool_post_rewrites_in_place() -> None:
    """tool_post 直接改写原生 ToolMessage 即生效。"""

    def handler(context):
        context.payload.content = f"{context.payload.content}\n\nNOTE"

    hooks = HookSet({HookPoint.TOOL_POST: [handler]})
    node = _build_node([_echo_tool([])], hooks)

    result = _run_node(node, _state([_tool_call()]), make_config())

    assert result["messages"][-1].content == "echo:origin\n\nNOTE"


def test_tool_post_sees_error_on_tool_exception() -> None:
    """工具抛错时 tool_post 同样触发，消息状态为 error。"""

    @tool
    def broken(query: str) -> str:
        """Always fails."""
        raise RuntimeError("boom")

    seen: list[str] = []
    hooks = HookSet({HookPoint.TOOL_POST: [lambda context: seen.append(context.payload.status)]})
    node = _build_node([broken], hooks)

    _run_node(node, _state([_tool_call(name="broken")]), make_config())

    assert seen == ["error"]


def test_tool_post_sees_untruncated_result() -> None:
    """tool_post 位于结果截断之内，看到完整原文。"""
    payload = "x" * 200
    seen: list[int] = []

    @tool
    def long_tool(query: str) -> str:
        """Return long content."""
        return payload

    hooks = HookSet({HookPoint.TOOL_POST: [lambda context: seen.append(len(context.payload.content))]})
    node = _build_node([long_tool], hooks, use_result_limit=True, result_limit_thrd=50)

    result = _run_node(node, _state([_tool_call(name="long_tool")]), make_config())

    assert seen == [200]
    assert result["messages"][-1].content == TOOL_RESULT_TOO_LONG_MESSAGE


def test_tool_post_rewrites_command_messages() -> None:
    """工具返回 Command 时，tool_post 改写其中每条 ToolMessage。"""
    seen: list[str] = []

    @tool
    def jump(query: str) -> Command:
        """Return a Command result."""
        return Command(update={"messages": [ToolMessage(content=f"jump:{query}", tool_call_id="call-1")]})

    def handler(context):
        seen.append(context.payload.content)
        return context.payload.model_copy(update={"content": f"{context.payload.content}:HOOKED"})

    hooks = HookSet({HookPoint.TOOL_POST: [handler]})
    result = _run_node(_build_node([jump], hooks), _state([_tool_call(name="jump")]), make_config())

    assert seen == ["jump:origin"]
    assert result["messages"][-1].content == "jump:origin:HOOKED"


def test_tool_pre_command_short_circuit_blocks_execution() -> None:
    """tool_pre 返回 Command 时工具不执行，结果来自该 Command。"""
    calls: list[str] = []
    short = Command(update={"messages": [ToolMessage(content="short-circuited", tool_call_id="call-1")]})
    hooks = HookSet({HookPoint.TOOL_PRE: [lambda context: short]})

    result = _run_node(_build_node([_echo_tool(calls)], hooks), _state([_tool_call()]), make_config())

    assert calls == []
    assert result["messages"][-1].content == "short-circuited"


@pytest.mark.parametrize("use_async", [False, True])
async def test_tool_hooks_work_in_async_invocation(use_async: bool) -> None:
    """同步与异步调用路径都触发 tool_pre / tool_post。"""
    seen: list[str] = []
    hooks = HookSet(
        {
            HookPoint.TOOL_PRE: [lambda context: seen.append("pre")],
            HookPoint.TOOL_POST: [lambda context: seen.append("post")],
        }
    )
    node = _build_node([_echo_tool([])], hooks)

    result = await _await_or_call(node, _state([_tool_call()]), make_config(), use_async)

    assert seen == ["pre", "post"]
    assert result["messages"][-1].content == "echo:origin"
