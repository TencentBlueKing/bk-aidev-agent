# -*- coding: utf-8 -*-
"""轮次生命周期测试：图上的 turn_start / turn_end 节点与运行标识绑定。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from typing_extensions import TypedDict

from aidev_agent.core.graphs.react.graph import (
    ReActAgentBuilder,
    _make_turn_end_node,
    _make_turn_start_node,
)
from aidev_agent.core.hook import HookIdentity, HookPoint, HookRunner, HookSet


class TurnState(TypedDict):
    messages: Annotated[List, add_messages]


def _config(**configurable) -> RunnableConfig:
    return RunnableConfig(configurable=dict(configurable))


def _runner(hooks: HookSet) -> HookRunner:
    return HookRunner(hooks)


def _build_graph(hook_runner, model_node):
    builder = ReActAgentBuilder()
    return builder._build_graph(
        state_schema=TurnState,
        callbacks=[],
        debug=False,
        checkpointer=None,
        store=None,
        interrupt_before=None,
        interrupt_after=None,
        name="turn-graph",
        cache=None,
        knowledge_node=None,
        model_node=model_node,
        tool_node=None,
        hook_runner=hook_runner,
    )


def test_turn_start_node_replaces_input() -> None:
    """turn_start 返回新列表时整表替换本轮输入。"""

    def handler(context):
        return [SystemMessage(content="SYS"), *context.payload]

    node = _make_turn_start_node(_runner(HookSet({HookPoint.TURN_START: [handler]})))
    result = node({"messages": [HumanMessage(content="hello")]}, _config())

    assert result["messages"][0].id == REMOVE_ALL_MESSAGES
    assert [message.content for message in result["messages"][1:]] == ["SYS", "hello"]


def test_turn_start_node_returns_empty_update_without_change() -> None:
    node = _make_turn_start_node(_runner(HookSet({HookPoint.TURN_START: [lambda context: None]})))

    assert node({"messages": [HumanMessage(content="hello")]}, _config()) == {}


def test_turn_end_node_runs_handlers() -> None:
    seen: list[str] = []
    node = _make_turn_end_node(_runner(HookSet({HookPoint.TURN_END: [lambda context: seen.append("end")]})))

    assert node({"messages": []}, _config()) == {}
    assert seen == ["end"]


def test_graph_runs_turn_start_before_model_and_turn_end_after() -> None:
    """增量拓扑：turn_start → model → turn_end，处理器按此顺序触发。"""
    seen: list[str] = []

    def model(state, config):
        seen.append("model")
        return {"messages": [AIMessage(content="answer")]}

    hooks = HookSet(
        {
            HookPoint.TURN_START: [lambda context: seen.append("turn_start")],
            HookPoint.TURN_END: [lambda context: seen.append("turn_end")],
        }
    )
    graph, cfg = _build_graph(_runner(hooks), model)
    result = graph.invoke({"messages": [HumanMessage(content="hello")]}, cfg)

    assert seen == ["turn_start", "model", "turn_end"]
    assert result["messages"][-1].content == "answer"


def test_graph_without_hooks_keeps_baseline_topology() -> None:
    """未注入 hooks 时不新增 turn 节点，模型直接连到 END。"""
    graph, cfg = _build_graph(None, lambda state, config: {"messages": [AIMessage(content="answer")]})

    nodes = set(graph.get_graph().nodes)

    assert "turn_start" not in nodes
    assert "turn_end" not in nodes
    assert graph.invoke({"messages": [HumanMessage(content="hello")]}, cfg)["messages"][-1].content == "answer"


def test_identity_is_resolved_from_config() -> None:
    """执行器从 thread_id 与 execute_kwargs 解析 agent_code / session_code / turn_id。"""
    seen: list[HookIdentity] = []
    runner = HookRunner(HookSet({HookPoint.TURN_END: [lambda context: seen.append(context.identity)]}))
    config = _config(
        thread_id="session",
        execute_kwargs=SimpleNamespace(agent_code="agent", session_code="ignored", turn_id="turn-9"),
    )

    runner.turn_end(config)

    assert seen == [HookIdentity(agent_code="agent", session_code="session", turn_id="turn-9")]


def test_identity_falls_back_to_empty_without_run_context() -> None:
    """缺少 execute_kwargs 时标识留空，不阻断处理器。"""
    seen: list[HookIdentity] = []
    runner = HookRunner(HookSet({HookPoint.TURN_END: [lambda context: seen.append(context.identity)]}))

    runner.turn_end(_config())

    assert seen == [HookIdentity()]
