# -*- coding: utf-8 -*-
"""无绑定状态守卫时的真实装配过滤与 ToolNode 注册边界。"""

from __future__ import annotations

from typing import Annotated, List, TypedDict

import pytest
from aidev_agent.config import settings
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.pydantic_models import AgentExecutorKwargs, ExecuteKwargs, SecuritySettings
from langchain_core.messages import AIMessage, AnyMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

EXECUTED: List[str] = []
WRAPPED: List[str] = []


class RecordingTool(BaseTool):
    name: str
    description: str = "记录执行"

    def _run(self, **kwargs) -> str:
        EXECUTED.append(self.name)
        return f"{self.name}-ok"


class MessageState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]


@pytest.fixture(autouse=True)
def reset_records():
    EXECUTED.clear()
    WRAPPED.clear()
    settings.set("BKAI_TOOL_LAZY_LOADING_ENABLED", True)
    # 阈值 1 让 graph 的一次性闸门放行；本文件只验 ToolNode 注册边界，不验阈值判定
    settings.set("BKAI_TOOL_LAZY_LOADING_THRESHOLD", 1)
    yield
    settings.reset()


def wrap(request, execute):
    WRAPPED.append(request.tool_call["name"])
    return execute(request)


async def awrap(request, execute):
    WRAPPED.append(request.tool_call["name"])
    return await execute(request)


def build_app(*, deny=()):
    builder = ReActAgentBuilder().set_bkai_options(
        AgentExecutorKwargs(security_settings=SecuritySettings(), execute_kwargs=ExecuteKwargs(tool_deny=list(deny)))
    )
    builder._enable_ask_user_question_tool = False
    original = [RecordingTool(name=name) for name in ("kept_a", "kept_b", "deferred_echo")]
    tools, builtin, catalog = builder._prepare_agent_tools(extra_tools=original, langchain_middleware=[])
    options = ToolNodeSettings(
        use_timer=False,
        use_result_limit=False,
        use_json_repair_on_error=False,
        use_tool_redaction=False,
        use_tool_untrusted_sanitize=False,
        use_tool_call_proxy=True,
    )
    node = build_tool_node(tools=tools, node_options=options, wrappers=[wrap], async_wrappers=[awrap])
    # 阈值判定在追加之前：启用时元工具二元组必在尾部，回填的是元工具上的直接执行引用
    call_tool = next(tool for tool in builtin if tool.name == "tool_call")
    graph = StateGraph(MessageState)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile(), node, catalog, call_tool


def message(name, call_id, arguments=None):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": arguments or {}, "id": call_id, "type": "tool_call"}]
    )


async def invoke(app, call, is_async):
    state = {"messages": [call]}
    config = {"configurable": {"thread_id": "registration-boundary"}}
    result = await app.ainvoke(state, config) if is_async else app.invoke(state, config)
    return result["messages"][-1]


class TestRegistrationBoundary:
    @pytest.mark.parametrize("is_async", [False, True])
    @pytest.mark.parametrize("name", ["deferred_echo", "missing"])
    async def test_filtered_and_unknown_native_names_rejected(self, is_async, name):
        app, node, catalog, _ = build_app(deny=["deferred_echo"])
        assert name not in node.tools_by_name
        assert name not in {tool.name for tool in catalog.deferred()}
        result = await invoke(app, message(name, "native-filtered"), is_async)
        assert result.status == "error"
        assert name in result.content and "not a valid tool" in result.content
        assert EXECUTED == []

    @pytest.mark.parametrize("is_async", [False, True])
    @pytest.mark.parametrize("name", ["deferred_echo", "missing"])
    async def test_filtered_and_unknown_proxy_names_rejected(self, is_async, name):
        app, node, catalog, call_tool = build_app(deny=["deferred_echo"])
        assert name not in node.tools_by_name and catalog.executable(name) is None
        call = message(call_tool.name, "proxy-filtered", {"name": name, "arguments": {}})
        result = await invoke(app, call, is_async)
        assert (result.status, result.name, result.tool_call_id) == ("error", call_tool.name, "proxy-filtered")
        assert EXECUTED == []

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_registered_deferred_native_call_succeeds(self, is_async):
        app, node, catalog, _ = build_app()
        assert "deferred_echo" in node.tools_by_name
        assert "deferred_echo" in {tool.name for tool in catalog.deferred()}
        result = await invoke(app, message("deferred_echo", "native-ok"), is_async)
        assert (result.content, result.status, result.name, result.tool_call_id) == (
            "deferred_echo-ok",
            "success",
            "deferred_echo",
            "native-ok",
        )
        assert EXECUTED == WRAPPED == ["deferred_echo"]

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_proxy_and_native_use_same_wrapper_chain(self, is_async):
        app, _, _, call_tool = build_app()
        native = await invoke(app, message("deferred_echo", "native"), is_async)
        proxied = await invoke(
            app, message(call_tool.name, "proxy", {"name": "deferred_echo", "arguments": {}}), is_async
        )
        assert (proxied.content, proxied.status) == (native.content, native.status)
        assert (proxied.name, proxied.tool_call_id) == (call_tool.name, "proxy")
        assert EXECUTED == ["deferred_echo", "deferred_echo"]
        assert WRAPPED == ["deferred_echo", "deferred_echo"]  # 解包后包装链只走一次
