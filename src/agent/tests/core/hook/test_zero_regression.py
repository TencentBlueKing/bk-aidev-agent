# -*- coding: utf-8 -*-
"""零回归测试：未注入 hooks 时行为与基线逐项一致。

# AC11 test_no_hooks_matches_baseline_sequence / test_pass_only_hooks_do_not_change_behavior
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, List

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from aidev_agent.core.hook import HookPoint, HookSet
from aidev_agent.core.hook.runner import HookRunner
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node

from .conftest import make_config

TOOL_RESULT_EVENT = "on_tool_node_finish"


class RegressionState(TypedDict):
    messages: Annotated[List, add_messages]


class EventRecorder(BaseCallbackHandler):
    """记录自定义事件名称序列。"""

    def __init__(self) -> None:
        self.names: list[str] = []

    def on_custom_event(self, name: str, data: Any, **kwargs: Any) -> None:
        self.names.append(name)


def _route(state: dict) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _build_graph(model_node, tool_node):
    graph = StateGraph(RegressionState)
    graph.add_node("model", model_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", _route, {"tools": "tools", END: END})
    graph.add_edge("tools", "model")
    return graph.compile()


def _build_scenario(fake_llm, build_model_node_with_hooks, hooks=None):
    calls: list[str] = []

    @tool
    def echo(query: str) -> str:
        """Echo."""
        calls.append(query)
        return f"echo:{query}"

    responses = [
        AIMessage(content="", tool_calls=[{"name": "echo", "args": {"query": "x"}, "id": "call-1"}]),
        AIMessage(content="final"),
    ]
    llm = fake_llm(responses)
    model_node = build_model_node_with_hooks(llm, hooks=hooks, tools=[echo])
    tool_node = build_tool_node(
        tools=[echo],
        node_options=ToolNodeSettings(
            use_tool_redaction=False,
            use_tool_untrusted_sanitize=False,
            use_json_repair_on_error=False,
            enable_tool_loop_guard=False,
        ),
        hook_runner=HookRunner(hooks) if hooks is not None else None,
    )
    return llm, calls, _build_graph(model_node, tool_node)


def _run(fake_llm, build_model_node_with_hooks, hooks=None):
    llm, calls, graph = _build_scenario(fake_llm, build_model_node_with_hooks, hooks)
    recorder = EventRecorder()
    config = {**make_config(), "callbacks": [recorder]}
    result = graph.invoke({"messages": [HumanMessage(content="hello")]}, config)
    return {
        "model_calls": len(llm.calls),
        "tool_calls": list(calls),
        "output": result["messages"][-1].content,
        "events": [name for name in recorder.names if name == TOOL_RESULT_EVENT],
        "state_keys": set(result),
    }


def test_no_hooks_matches_baseline_sequence(fake_llm, build_model_node_with_hooks, caplog) -> None:
    """AC11 未注入 hooks 时模型请求序列、工具执行序列、最终输出、事件序列与基线一致。"""
    with caplog.at_level(logging.INFO):
        observed = _run(fake_llm, build_model_node_with_hooks, hooks=None)

    assert observed["model_calls"] == 2
    assert observed["tool_calls"] == ["x"]
    assert observed["output"] == "final"
    assert observed["events"] == [TOOL_RESULT_EVENT]
    assert observed["state_keys"] == {"messages"}
    assert "[Hook]" not in caplog.text


def test_pass_only_hooks_do_not_change_behavior(fake_llm, build_model_node_with_hooks) -> None:
    """注入全 pass 处理器后，业务序列与未注入时逐项一致。"""
    baseline = _run(fake_llm, build_model_node_with_hooks, hooks=None)

    def handler(context):
        return None

    hooks = HookSet(
        {
            HookPoint.TURN_START: [handler],
            HookPoint.MODEL_PRE: [handler],
            HookPoint.MODEL_POST: [handler],
            HookPoint.TOOL_PRE: [handler],
            HookPoint.TOOL_POST: [handler],
            HookPoint.TURN_END: [handler],
        }
    )
    with_hooks = _run(fake_llm, build_model_node_with_hooks, hooks=hooks)

    assert with_hooks["model_calls"] == baseline["model_calls"]
    assert with_hooks["tool_calls"] == baseline["tool_calls"]
    assert with_hooks["output"] == baseline["output"]
    assert with_hooks["events"] == baseline["events"]
    assert with_hooks["state_keys"] == baseline["state_keys"]
