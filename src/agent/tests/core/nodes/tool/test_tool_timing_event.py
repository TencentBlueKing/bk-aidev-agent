# -*- coding: utf-8 -*-
"""工具计时元数据与结果事件派发解耦：计时开关、时长口径与派发时机。

用 fake 工具 + ``StateGraph(tools → END)`` 直接驱动工具节点，不接真实模型与 MCP。
结果事件没有开关：审批拒绝不派发，其他工具结果正常派发；interrupt / 终止以异常抛出，
没有返回值可派发，因此不产生事件。
"""

from types import SimpleNamespace
from typing import Any

import pytest
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node, timer_wrapper
from aidev_agent.core.nodes.tool.loop_guard import ToolLoopTerminationError
from aidev_agent.packages.interrupt_manager.approval import TOOL_APPROVAL_REJECTED_KEY
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from typing_extensions import Annotated, TypedDict

CALL_ID = "call-0"
EVENT_NAME = "on_tool_node_finish"
_CONFIG = {"configurable": {"thread_id": "timing-event"}}


class _State(TypedDict):
    messages: Annotated[list, add_messages]


def _call(name: str = "echo") -> dict:
    return {
        "name": name,
        "args": {"text": "x"} if name in {"echo", "ask", "boom"} else {},
        "id": CALL_ID,
        "type": "tool_call",
    }


def _graph(tools: list, **settings: Any):
    node = build_tool_node(
        tools=tools,
        node_options=ToolNodeSettings(use_tool_redaction=False, use_tool_untrusted_sanitize=False, **settings),
    )
    graph = StateGraph(_State)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile()


async def _await_or_call(graph, state, use_async):
    return await graph.ainvoke(state, _CONFIG) if use_async else graph.invoke(state, _CONFIG)


def _invoke(graph, use_async: bool, name: str = "echo"):
    state = {"messages": [AIMessage(content="", tool_calls=[_call(name)])]}
    return _await_or_call(graph, state, use_async)


def _result(result: dict) -> ToolMessage:
    return [msg for msg in result["messages"] if isinstance(msg, ToolMessage)][-1]


class _Recorder:
    """记录 on_tool_node_finish 派发时刻的快照（深拷贝，避免后续原地修改干扰断言）。"""

    def __init__(self):
        self.sent: list[tuple[str, str, dict]] = []

    def __call__(self, name, data, config):
        self.sent.append((name, data.name, dict(data.additional_kwargs)))


@pytest.fixture
def recorder(monkeypatch):
    recorded = _Recorder()
    monkeypatch.setattr(timer_wrapper, "dispatch_custom_event", recorded)
    return recorded


def _echo_tools(counter: list) -> list:
    @tool
    def echo(text: str) -> str:
        """回显文本。"""
        counter.append(text)
        return f"echo:{text}"

    return [echo]


class TestTimerSwitch:
    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("use_timer", [True, False])
    async def test_timer_switch_only_affects_metadata(self, recorder, use_async, use_timer):
        """计时开关只改元数据：两种情况都恰好派发一次，只有 duration / description 不同。"""
        counter: list = []
        message = _result(await _invoke(_graph(_echo_tools(counter), use_timer=use_timer), use_async))
        assert counter == ["x"]
        assert len(recorder.sent) == 1
        assert recorder.sent[0][:2] == (EVENT_NAME, "echo")
        assert ("description" in message.additional_kwargs) is use_timer
        duration = message.additional_kwargs.get("duration")
        assert duration is None if not use_timer else isinstance(duration, int) and duration >= 0

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_timer_disabled_keeps_event_without_timing_metadata(self, recorder, use_async):
        """关计时仍派发一次：事件与图结果共享同一条消息，不添加计时元数据。"""
        message = _result(await _invoke(_graph(_echo_tools([]), use_timer=False), use_async))
        assert recorder.sent == [(EVENT_NAME, "echo", {})]
        assert message.additional_kwargs == {}

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_timer_enabled_keeps_real_duration(self, recorder, use_async):
        kwargs = _result(await _invoke(_graph(_echo_tools([]), use_timer=True), use_async)).additional_kwargs
        assert [(name, data["description"]) for name, _, data in recorder.sent] == [(EVENT_NAME, "回显文本。")]
        assert isinstance(kwargs["duration"], int) and kwargs["duration"] >= 0


class TestDispatchTiming:
    @pytest.mark.parametrize("use_async", [False, True])
    async def test_event_carries_final_message_after_execute(self, recorder, use_async):
        """派发发生在 execute 返回之后：事件里的消息已是终态（id 补齐、content 已产出）。"""
        message = _result(await _invoke(_graph(_echo_tools([]), use_timer=False), use_async))
        assert len(recorder.sent) == 1
        assert message.id and message.content == "echo:x"

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_command_result_dispatched_once(self, recorder, use_async):
        @tool
        def jump() -> Command:
            """返回 Command。"""
            return Command(update={"messages": [ToolMessage("jump:x", tool_call_id=CALL_ID)]})

        message = _result(await _invoke(_graph([jump], use_timer=False), use_async, name="jump"))
        assert message.content == "jump:x"
        assert recorder.sent == [(EVENT_NAME, "jump", {})]


class TestShortCircuit:
    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("use_timer", [True, False])
    async def test_interrupt_produces_no_event(self, recorder, use_async, use_timer):
        """interrupt 透传：不伪造结果事件，工具侧也不写任何结果元数据。"""

        @tool
        def ask(text: str) -> str:
            """需要人工确认。"""
            return interrupt({"question": text})

        app = _graph([ask], use_timer=use_timer)
        result = await _await_or_call(app, {"messages": [AIMessage(content="", tool_calls=[_call("ask")])]}, use_async)
        assert result.get("__interrupt__")
        assert recorder.sent == []

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("use_timer", [True, False])
    async def test_termination_produces_no_event(self, recorder, use_async, use_timer):
        """循环终止：异常抛出、无返回值故零派发（拒绝路径的恰好一次派发不追加）。"""
        counter: list = []
        graph = _graph(_echo_tools(counter), enable_tool_loop_guard=True, use_timer=use_timer)
        base = _call()
        messages: list = []
        # 3 次放行 + 2 次拒绝，第 6 次触发终止
        for index in range(5):
            messages.append(AIMessage(content="", tool_calls=[{**base, "id": f"call-{index}"}]))
            messages.append(ToolMessage("echo:x", tool_call_id=f"call-{index}", name="echo"))
        messages.append(AIMessage(content="", tool_calls=[{**base, "id": "call-5"}]))
        with pytest.raises(ToolLoopTerminationError):
            await _await_or_call(graph, {"messages": messages}, use_async)
        assert counter == []
        assert recorder.sent == []


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("as_command", [False, True])
@pytest.mark.parametrize("rejected", [False, True])
async def test_approval_rejection_skips_dispatch_only(recorder, use_async, as_command, rejected):
    message = ToolMessage("error", tool_call_id=CALL_ID, name="echo", status="error",
                          additional_kwargs={TOOL_APPROVAL_REJECTED_KEY: rejected})
    output = Command(update={"messages": [message]}) if as_command else message
    request = SimpleNamespace(runtime=SimpleNamespace(config={}))

    def execute(request):
        return output

    async def aexecute(request):
        return output

    if use_async:
        result = await timer_wrapper.dispatch_tool_result_event_async(request, aexecute)
    else:
        result = timer_wrapper.dispatch_tool_result_event(request, execute)
    assert result is output
    assert len(recorder.sent) == (0 if rejected else 1)
