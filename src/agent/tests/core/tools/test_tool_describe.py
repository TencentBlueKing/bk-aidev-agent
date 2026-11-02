# -*- coding: utf-8 -*-
"""``tool_describe`` 语义（REQ-4 / REQ-11；AC-4）。

describe 只读取已装配的工具定义：不执行目标工具、不触发远程连接，
未知名逐条报错但整批仍成功。
"""

from __future__ import annotations

import json
from typing import Annotated, List, TypedDict

import pytest
from aidev_agent.config import settings
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.tools.tool_lazy_loading.catalog import LazyToolCatalog
from aidev_agent.core.tools.tool_lazy_loading.meta_tools import DESCRIBE_DESCRIPTION, make_meta_tools
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

SIDE_EFFECTS: List[str] = []
MCP_CONNECTIONS: List[str] = []


class GreetInput(BaseModel):
    """问候工具入参。"""

    who: str = Field(description="问候对象")


class GreetTool(BaseTool):
    name: str = "greet"
    description: str = "向指定对象打招呼"
    args_schema: type[BaseModel] = GreetInput

    def _run(self, who: str) -> str:  # type: ignore[override]
        SIDE_EFFECTS.append(who)
        return f"hello {who}"


class MockMcpTool(BaseTool):
    name: str = "mcp_search"
    description: str = "MCP 检索工具"

    def _run(self, **kwargs) -> str:  # type: ignore[override]
        MCP_CONNECTIONS.append("connected")
        return "mcp result"


class MessageState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]


def make_catalog(tools) -> LazyToolCatalog:
    return LazyToolCatalog(deferred_tools=tools)


def build_node_for(tools, catalog: LazyToolCatalog, *, wrappers=None, call_tool=None):
    node = build_tool_node(
        tools=tools,
        node_options=ToolNodeSettings(
            use_timer=False,
            use_result_limit=False,
            use_json_repair_on_error=False,
            use_tool_redaction=False,
            use_tool_untrusted_sanitize=False,
            use_tool_call_proxy=True,
        ),
        wrappers=wrappers,
    )
    graph = StateGraph(MessageState)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile()


@pytest.fixture(autouse=True)
def _reset_records():
    SIDE_EFFECTS.clear()
    MCP_CONNECTIONS.clear()
    settings.set("BKAI_TOOL_LAZY_LOADING_ENABLED", True)
    settings.set("BKAI_TOOL_LAZY_LOADING_THRESHOLD", 30)
    yield
    settings.reset()


def call_describe(app, names, call_id: str = "call_describe_1") -> ToolMessage:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "tool_describe", "args": {"names": names}, "id": call_id, "type": "tool_call"}],
    )
    result = app.invoke({"messages": [message]}, {"configurable": {"thread_id": "describe-thread"}})
    return result["messages"][-1]


class TestDescribeSemantics:
    def test_returns_description_and_full_schema_without_executing(self):
        """AC-4：返回 description 与完整参数 schema，且不执行目标工具、不连接 MCP。"""
        tools = [GreetTool(), MockMcpTool()]
        catalog = make_catalog(tools)
        describe_tool, _ = make_meta_tools(catalog)
        app = build_node_for([*tools, describe_tool], catalog)

        result = call_describe(app, ["greet", "mcp_search"])

        payload = json.loads(result.content)
        greet = payload["results"][0]
        assert greet["name"] == "greet"
        assert greet["description"] == "向指定对象打招呼"
        assert greet["parameters"]["properties"]["who"]["type"] == "string"
        assert SIDE_EFFECTS == []
        assert MCP_CONNECTIONS == []

    def test_unknown_name_returns_error_without_failing_batch(self):
        """未知名逐条返回带名称的 error，整批仍成功。"""
        catalog = make_catalog([GreetTool()])
        describe_tool, _ = make_meta_tools(catalog)
        app = build_node_for([GreetTool(), describe_tool], catalog)

        result = call_describe(app, ["greet", "not_exists"])

        payload = json.loads(result.content)
        assert payload["results"][0]["name"] == "greet"
        assert payload["results"][1]["name"] == "not_exists"
        assert "error" in payload["results"][1]
        assert "not_exists" in payload["results"][1]["error"]

    def test_message_carries_tool_call_id(self):
        """返回的 ToolMessage 的 tool_call_id 与本次调用一致。"""
        catalog = make_catalog([GreetTool()])
        describe_tool, _ = make_meta_tools(catalog)
        app = build_node_for([GreetTool(), describe_tool], catalog)

        result = call_describe(app, ["greet"], call_id="call_abc")

        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "call_abc"

    def test_description_describes_three_step_flow(self):
        """REQ-11：description 写明「目录 → tool_describe → tool_call」与「不要直接调用工具名」。"""
        assert "tool_describe" in DESCRIBE_DESCRIPTION
        assert "tool_call" in DESCRIBE_DESCRIPTION
        assert "目录" in DESCRIBE_DESCRIPTION
        assert "不要直接调用" in DESCRIBE_DESCRIPTION

    def test_tool_is_not_exposed_as_callable_argument(self):
        """入参只暴露 names，注入参数不出现在模型可见 schema 中。"""
        catalog = make_catalog([GreetTool()])
        describe_tool, _ = make_meta_tools(catalog)
        schema = describe_tool.tool_call_schema.model_json_schema()
        assert set(schema["properties"]) == {"names"}

    def test_dictionary_schema_through_real_describe_node(self):
        class DictionaryTool(BaseTool):
            name: str = "dictionary"
            description: str = "字典 schema"
            args_schema: dict = {
                "type": "object",
                "properties": {"query": {"$ref": "#/$defs/Query"}},
                "required": ["query"],
                "$defs": {"Query": {"type": "string"}},
            }

            def _run(self, query: str) -> str:
                SIDE_EFFECTS.append(query)
                return query

        target = DictionaryTool()
        catalog = make_catalog([target])
        describe, _ = make_meta_tools(catalog)
        app = build_node_for([target, describe], catalog)
        result = call_describe(app, [target.name])
        parameters = json.loads(result.content)["results"][0]["parameters"]
        assert parameters == target.tool_call_schema
        assert parameters["required"] == ["query"]
        assert parameters["$defs"] == {"Query": {"type": "string"}}
        assert SIDE_EFFECTS == []
