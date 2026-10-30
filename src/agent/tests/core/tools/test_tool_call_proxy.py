# -*- coding: utf-8 -*-
"""单工具代理的结果、异常、审批、并发隔离和 Command 回归。"""

from __future__ import annotations

from typing import Annotated, Any, List, TypedDict

import pytest
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node, timer_wrapper
from aidev_agent.core.tools.task import TaskCreate, merge_task_list
from aidev_agent.core.tools.tool_lazy_loading.catalog import LazyToolCatalog
from aidev_agent.core.tools.tool_lazy_loading.meta_tools import DESCRIBE_TOOL_NAME, ToolCallTool, make_meta_tools
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import BaseTool, ToolException
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import Command
from pydantic import Field, ValidationError


class EchoTool(BaseTool):
    name: str = "echo"
    description: str = "回显"
    calls: list[str] = Field(default_factory=list)

    def _run(self, text: str = "") -> str:
        self.calls.append(text)
        return f"echo:{text}"


class BoomTool(BaseTool):
    name: str = "test_fail_tool"
    description: str = "预期失败"
    error: Any = None

    def _run(self, a: str = "") -> str:
        raise self.error


class ResultTool(BaseTool):
    name: str = "result"
    description: str = "返回完整工具消息"
    status: str = "success"

    def _run(self, runtime: ToolRuntime) -> ToolMessage:
        return ToolMessage(
            content=[{"type": "text", "text": "original"}],
            artifact={"source": "original"},
            additional_kwargs={"custom": 1},
            status=self.status,
            tool_call_id=runtime.tool_call_id,
        )


class GotoTool(BaseTool):
    name: str = "goto_tool"
    description: str = "更新状态并跳转"

    def _run(self, runtime: ToolRuntime) -> Command:
        return Command(
            update={"seen": "updated", "messages": [ToolMessage("done", tool_call_id=runtime.tool_call_id)]},
            goto="after",
        )


class MessageState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]


class TaskState(MessageState):
    task_list: Annotated[List, merge_task_list]


class GotoState(MessageState):
    seen: str
    routed: bool


def make_env(
    tools,
    *,
    state_schema=MessageState,
    wrappers=(),
    async_wrappers=(),
    checkpoint=False,
    result_limit=None,
    use_timer=False,
):
    catalog = LazyToolCatalog(deferred_tools=tools)
    describe_tool, proxy = make_meta_tools(catalog)
    options = ToolNodeSettings(
        use_timer=use_timer,
        use_tool_redaction=False,
        use_tool_untrusted_sanitize=False,
        use_tool_call_proxy=True,
        use_json_repair_on_error=False,
        use_result_limit=result_limit is not None,
        result_limit_thrd=result_limit or 1000,
    )
    node = build_tool_node(
        tools=[*tools, describe_tool, proxy],
        node_options=options,
        wrappers=wrappers,
        async_wrappers=async_wrappers,
    )
    graph = StateGraph(state_schema)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    if state_schema is GotoState:
        graph.add_node("after", lambda state: {"routed": True})
        graph.add_edge("after", END)
    return catalog, proxy, node, graph.compile(checkpointer=MemorySaver() if checkpoint else None)


def tool_input(name, arguments=None, *, proxy_name="tool_call", call_id="outer"):
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": proxy_name,
                        "args": {"name": name, "arguments": arguments or {}},
                        "id": call_id,
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def runtime(call_id="outer"):
    return ToolRuntime(
        state={"messages": []},
        tool_call_id=call_id,
        config={"configurable": {"thread_id": "test"}},
        context=None,
        store=None,
        stream_writer=None,
    )


async def invoke(app, value, is_async, config=None):
    config = config or {"configurable": {"thread_id": "test"}}
    return await app.ainvoke(value, config) if is_async else app.invoke(value, config)


class TestSingleCall:
    @pytest.mark.parametrize(
        "payload", [{"calls": []}, {"name": "echo", "calls": []}, {"name": ["echo"]}, {"name": ""}]
    )
    def test_rejects_list_api(self, payload):
        _, proxy, _, _ = make_env([EchoTool()])
        assert set(proxy.tool_call_schema.model_json_schema()["properties"]) == {"name", "arguments"}
        with pytest.raises(ValidationError):
            proxy.args_schema.model_validate(payload)

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_active_execution_uses_same_wrapper_chain(self, is_async):
        """元工具代理走与原生调用相同的包装链，结果逐项一致（含副作用只发生一次）。"""
        echo = EchoTool()
        _, _, _, app = make_env([echo, EchoTool(name="padding")])
        result = await invoke(app, tool_input("echo", {"text": "test"}), is_async)
        message = result["messages"][-1]
        assert (message.content, message.status, message.name, message.tool_call_id) == (
            "echo:test",
            "success",
            "tool_call",
            "outer",
        )
        assert echo.calls == ["test"]

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_graph_marks_proxy_failure(self, is_async):
        _, _, _, app = make_env([BoomTool(error=ToolException("完成测试 本测试预期失败"))])
        result = await invoke(app, tool_input("test_fail_tool", {"a": "test"}), is_async)
        message = result["messages"][-1]
        assert (message.status, message.content, message.name, message.tool_call_id) == (
            "error",
            "完成测试 本测试预期失败",
            "tool_call",
            "outer",
        )

    @pytest.mark.parametrize("is_async", [False, True])
    @pytest.mark.parametrize("status", ["success", "error"])
    async def test_preserves_returned_message(self, is_async, status):
        _, _, _, app = make_env([ResultTool(status=status)])
        result = await invoke(app, tool_input("result"), is_async)
        message = result["messages"][-1]
        assert message.content == [{"type": "text", "text": "original"}]
        assert message.artifact == {"source": "original"}
        assert message.additional_kwargs == {"custom": 1}
        assert (message.status, message.name, message.tool_call_id) == (status, "tool_call", "outer")

    @pytest.mark.parametrize("is_async", [False, True])
    @pytest.mark.parametrize("name", ["missing", "tool_describe", "tool_call"])
    async def test_rejects_unexecutable_target(self, is_async, name):
        echo = EchoTool()
        _, _, _, app = make_env([echo])
        result = await invoke(app, tool_input(name), is_async)
        assert result["messages"][-1].status == "error"
        assert echo.calls == []


class TestCommand:
    @pytest.mark.parametrize("is_async", [False, True])
    async def test_task_state_matches_direct_call(self, is_async):
        _, _, _, app = make_env([TaskCreate], state_schema=TaskState)
        arguments = {"subject": "写测试", "description": "覆盖状态透传"}
        direct = {
            "messages": [AIMessage(content="", tool_calls=[{"name": "TaskCreate", "args": arguments, "id": "outer"}])]
        }
        expected = await invoke(app, direct, is_async)
        actual = await invoke(app, tool_input("TaskCreate", arguments), is_async)
        assert len(expected["task_list"]) == len(actual["task_list"]) == 1
        assert actual["task_list"][0].task_id == expected["task_list"][0].task_id
        assert actual["task_list"][0].subject == "写测试"
        assert actual["messages"][-1].tool_call_id == "outer"
        assert actual["messages"][-1].name == "tool_call"

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_command_goto_and_nonmessage_update(self, is_async):
        _, _, _, app = make_env([GotoTool()], state_schema=GotoState)
        result = await invoke(app, tool_input("goto_tool"), is_async)
        assert result["seen"] == "updated"
        assert result["routed"] is True
        assert result["messages"][-1].tool_call_id == "outer"


class TestWrapperChain:
    @pytest.mark.parametrize("is_async", [False, True])
    async def test_custom_wrapper_is_used(self, is_async):
        hits = []

        def wrapper(request, execute):
            hits.append(request.tool_call["name"])
            return execute(request)

        async def awrapper(request, execute):
            hits.append(request.tool_call["name"])
            return await execute(request)

        _, _, _, app = make_env([EchoTool()], wrappers=[wrapper], async_wrappers=[awrapper])
        await invoke(app, tool_input("echo"), is_async)
        assert hits == ["echo"]  # 解包后包装链只走一次，且看到的是目标工具

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_result_limit_is_used(self, is_async):
        _, _, _, app = make_env([EchoTool()], result_limit=5)
        result = await invoke(app, tool_input("echo", {"text": "0123456789"}), is_async)
        assert "超长" in result["messages"][-1].content

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_approval_interrupt_and_resume_once(self, is_async):
        echo = EchoTool(metadata={"approval": {"enabled": True}})
        _, _, _, app = make_env([echo], checkpoint=True)
        result = await invoke(app, tool_input("echo"), is_async)
        assert result.get("__interrupt__") and echo.calls == []
        assert result["__interrupt__"][0].value["toolCallId"] == "outer"
        assert result["__interrupt__"][0].value["toolName"] == "echo"
        resumed = await invoke(app, Command(resume={"approved": True, "toolCallId": "outer"}), is_async)
        assert resumed["messages"][-1].status == "success"
        assert echo.calls == [""]


class TestBuildCallErrorHint:
    """无效目标名的错误提示只用真实元工具名；无 catalog 时不伪造任何名字。"""

    @pytest.mark.parametrize("is_async", [False, True])
    async def test_hint_uses_fixed_describe_name(self, is_async):
        """业务工具同时占据原名与让名前缀名：提示仍是固定名，不随工厂改名漂移。"""
        business = [EchoTool(name="tool_describe"), EchoTool(name="aidev_lazy__tool_describe")]
        catalog = LazyToolCatalog(deferred_tools=business)
        describe_tool, call_tool = make_meta_tools(catalog)
        with pytest.raises(ToolException) as raised:
            if is_async:
                await call_tool._arun("missing", {})
            else:
                call_tool._run("missing", {})
        assert describe_tool.name == DESCRIBE_TOOL_NAME
        assert "请先调用 tool_describe 确认可用工具" in str(raised.value)

    def test_absent_catalog_raises_generic_error_without_meta_name(self):
        with pytest.raises(ToolException) as raised:
            ToolCallTool(catalog=None)._run("echo", {})
        assert str(raised.value) == "延迟工具目录不可用"
        assert "tool_describe" not in str(raised.value)


class TestTimerEvent:
    @pytest.mark.parametrize("is_async", [False, True])
    async def test_result_event_named_as_proxy_with_target_description(self, is_async, monkeypatch):
        """计时器派发时刻的结果名已是 tool_call（派发即被消费，不能靠外层事后原地改名），描述取自目标工具。"""
        sent = []

        def record(name, data, config):
            sent.append((data.name, data.additional_kwargs["description"]))

        monkeypatch.setattr(timer_wrapper, "dispatch_custom_event", record)
        _, _, _, app = make_env([EchoTool()], use_timer=True)
        result = await invoke(app, tool_input("echo", {"text": "x"}), is_async)
        assert sent == [("tool_call", "回显")]
        assert result["messages"][-1].name == "tool_call"
