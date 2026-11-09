# -*- coding: utf-8 -*-
"""工具循环调用拒绝：判定、拒绝、终止与配置。

用 fake 工具 + ``StateGraph(tools → END)`` 直接驱动工具节点，不接真实模型与 MCP。
"""

import os
import subprocess
import sys
from typing import Any
from unittest.mock import Mock

import pytest
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.nodes.tool import loop_guard as loop_guard_module
from aidev_agent.core.nodes.tool.loop_guard import (
    TERMINATION_MESSAGE,
    TRUNCATED_SUFFIX,
    ToolLoopTerminationError,
    fingerprint,
)
from aidev_agent.core.nodes.tool.node import _mark_content_error, default_tool_call_handler
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import TOOL_CALL_ERROR_TEMPLATE, ToolCallWithContext
from langgraph.types import Command, Send
from typing_extensions import Annotated, TypedDict


class _State(TypedDict):
    messages: Annotated[list, add_messages]


def _tools(counter: list) -> list:
    """构造一对 fake 工具：echo 记录真实执行次数，other 用于穿插。"""

    @tool
    def echo(text: str) -> str:
        """回显文本。"""
        counter.append(text)
        return f"echo:{text}#{len(counter)}"

    @tool
    def other(text: str) -> str:
        """另一个工具。"""
        return f"other:{text}"

    return [echo, other]


def _call(index: int, name: str = "echo", args: dict | None = None) -> dict:
    return {
        "name": name,
        "args": args if args is not None else {"text": "x"},
        "id": f"call-{index}",
        "type": "tool_call",
    }


def _round(index: int, *, name: str = "echo", args: dict | None = None, result: str = "echo:x") -> list:
    return [
        AIMessage(content="", tool_calls=[_call(index, name, args)]),
        ToolMessage(content=result, tool_call_id=f"call-{index}", name=name),
    ]


def _state(rounds: int, *, name: str = "echo", args: dict | None = None, result: str = "echo:x") -> dict:
    """构造 rounds 轮已完成历史 + 当前待执行的第 rounds 次调用。"""
    messages: list = [HumanMessage(content="重复调用测试")]
    for index in range(rounds):
        messages.extend(_round(index, name=name, args=args, result=result))
    messages.append(AIMessage(content="", tool_calls=[_call(rounds, name, args)]))
    return {"messages": messages}


def _graph(tools: list, *, settings: ToolNodeSettings | None = None, checkpointer: Any = None, **node_kwargs):
    node = build_tool_node(
        tools=tools, node_options=settings or ToolNodeSettings(enable_tool_loop_guard=True), **node_kwargs
    )
    graph = StateGraph(_State)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile(checkpointer=checkpointer)


def _last_tool_message(result: dict) -> ToolMessage:
    return [msg for msg in result["messages"] if isinstance(msg, ToolMessage)][-1]


SUMMARY_HEADER = "最后一次真实返回内容摘要：\n"


def _summary_of(content: str) -> str:
    """取出拒绝反馈里「最后一次真实返回内容摘要」段。"""
    _, _, rest = str(content).partition(SUMMARY_HEADER)
    return rest.partition("请改用其他工具")[0].strip()


def _count_contiguous(messages, call):
    return loop_guard_module._scan(messages, call)[0]


class TestFingerprint:
    @pytest.mark.parametrize(
        ("left", "right"),
        [({"b": 1, "a": 2}, {"a": 2, "b": 1}), ({"a": "x  y"}, {"a": "x  y"})],
    )
    def test_key_order_and_whitespace_insensitive(self, left, right):
        assert fingerprint(left) == fingerprint(right)

    @pytest.mark.parametrize(("left", "right"), [({"a": None}, {}), ({"a": 1}, {"a": "1"})])
    def test_distinguishes_null_missing_and_type(self, left, right):
        assert fingerprint(left) != fingerprint(right)

    def test_unserializable_returns_none(self):
        assert fingerprint({"a": {1, 2}}) is None


class TestCountContiguous:
    def test_empty_history(self):
        assert _count_contiguous([], _call(0)) == 0

    @pytest.mark.parametrize("rounds", [1, 2, 3])
    def test_counts_previous_rounds(self, rounds):
        assert _count_contiguous(_state(rounds)["messages"], _call(rounds)) == rounds

    def test_interleaved_tool_resets(self):
        messages = [HumanMessage(content="go")]
        messages.extend(_round(0))
        messages.extend(_round(1, name="other", result="other:x"))
        messages.append(AIMessage(content="", tool_calls=[_call(2)]))
        assert _count_contiguous(messages, _call(2)) == 0

    def test_changed_args_resets(self):
        messages = [HumanMessage(content="go")]
        messages.extend(_round(0))
        messages.append(AIMessage(content="", tool_calls=[_call(1, args={"text": "y"})]))
        assert _count_contiguous(messages, _call(1, args={"text": "y"})) == 0

    def test_same_batch_folds_to_one(self):
        messages = [
            HumanMessage(content="go"),
            AIMessage(content="", tool_calls=[_call(0), _call(1)]),
            ToolMessage(content="echo:x", tool_call_id="call-0", name="echo"),
            AIMessage(content="", tool_calls=[_call(2)]),
        ]
        assert _count_contiguous(messages, _call(2)) == 1

    def test_window_starts_after_last_user_message(self):
        messages = [HumanMessage(content="old")]
        messages.extend(_round(0))
        messages.extend(_round(1))
        messages.append(HumanMessage(content="new"))
        messages.append(AIMessage(content="", tool_calls=[_call(5)]))
        assert _count_contiguous(messages, _call(5)) == 0


class TestGuardBehaviour:
    def test_allow_within_threshold(self):
        counter: list = []
        result = _graph(_tools(counter)).invoke(_state(2))
        assert _last_tool_message(result).status == "success"
        assert counter == ["x"]

    def test_reject_at_threshold(self):
        counter: list = []
        message = _last_tool_message(_graph(_tools(counter)).invoke(_state(3)))
        assert message.status == "error"
        assert counter == []
        assert message.tool_call_id == "call-3"

    def test_rejection_feedback_fields(self):
        counter: list = []
        message = _last_tool_message(_graph(_tools(counter)).invoke(_state(3, result="上一轮返回内容")))
        content = message.content
        assert "echo" in content
        assert "4" in content
        assert "拒绝" in content
        assert "上一轮返回内容" in content
        assert "其他工具" in content and "调整" in content

    def test_rejection_feedback_truncates_long_result(self):
        counter: list = []
        settings = ToolNodeSettings(result_limit_thrd=20, enable_tool_loop_guard=True)
        message = _last_tool_message(_graph(_tools(counter), settings=settings).invoke(_state(3, result="y" * 100)))
        assert TRUNCATED_SUFFIX in message.content
        assert "y" * 100 not in message.content

    def test_feedback_round_still_rejects(self):
        counter: list = []
        message = _last_tool_message(_graph(_tools(counter)).invoke(_state(4)))
        assert message.status == "error"
        assert counter == []

    def test_two_rejections_track_last_real_result(self):
        """逐轮驱动 tools 节点：第 4、5 次拒绝的摘要都取自最近一次真实执行结果。"""
        counter: list = []
        graph = _graph(_tools(counter))
        messages: list = [HumanMessage(content="逐轮驱动")]
        results = []
        for index in range(5):
            messages = graph.invoke({"messages": [*messages, AIMessage(content="", tool_calls=[_call(index)])]})[
                "messages"
            ]
            results.append(_last_tool_message({"messages": messages}))

        first, second = results[3], results[4]
        assert (first.status, second.status) == ("error", "error")
        assert "已连续调用次数：4" in first.content
        assert "已连续调用次数：5" in second.content
        assert _summary_of(first.content) == "echo:x#3"
        assert _summary_of(second.content) == "echo:x#3"
        assert "拒绝" not in _summary_of(second.content)
        assert counter == ["x", "x", "x"]

    def test_terminate_after_feedback_rounds(self):
        counter: list = []
        with pytest.raises(ToolLoopTerminationError) as excinfo:
            _graph(_tools(counter)).invoke(_state(5))
        assert TERMINATION_MESSAGE in str(excinfo.value)
        assert "echo" in str(excinfo.value)
        assert counter == []

    def test_termination_keeps_previous_messages(self):
        counter: list = []
        graph = _graph(_tools(counter), checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "loop-termination"}}
        with pytest.raises(ToolLoopTerminationError):
            graph.invoke(_state(5), config=config)
        kept = [msg for msg in graph.get_state(config).values["messages"] if isinstance(msg, ToolMessage)]
        assert len(kept) == 5

    def test_interleaved_tool_is_allowed(self):
        counter: list = []
        messages = [HumanMessage(content="go")]
        messages.extend(_round(0))
        messages.extend(_round(1, name="other", result="other:x"))
        messages.append(AIMessage(content="", tool_calls=[_call(2)]))
        result = _graph(_tools(counter)).invoke({"messages": messages})
        assert _last_tool_message(result).status == "success"
        assert counter == ["x"]

    def test_decision_error_allows_call(self, monkeypatch):
        counter: list = []

        def _boom(*args, **kwargs):
            raise RuntimeError("判定失败")

        monkeypatch.setattr(loop_guard_module, "_scan", _boom)
        result = _graph(_tools(counter)).invoke(_state(3))
        assert _last_tool_message(result).status == "success"
        assert counter == ["x"]


class TestPolicyOverride:
    def test_custom_repeat_limit(self, monkeypatch):
        monkeypatch.setattr("aidev_agent.core.nodes.tool.node.BKAI_TOOL_LOOP_REPEAT_LIMIT", 5)
        counter: list = []
        assert _last_tool_message(_graph(_tools(counter)).invoke(_state(4))).status == "success"
        assert _last_tool_message(_graph(_tools(counter)).invoke(_state(5))).status == "error"

    def test_zero_feedback_rounds_terminates_on_first_repeat(self, monkeypatch):
        monkeypatch.setattr("aidev_agent.core.nodes.tool.node.BKAI_TOOL_LOOP_FEEDBACK_ROUNDS", 0)
        with pytest.raises(ToolLoopTerminationError):
            _graph(_tools([])).invoke(_state(3))


class TestConfig:
    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("BKAI_TOOL_LOOP_REPEAT_LIMIT", "0"),
            ("BKAI_TOOL_LOOP_REPEAT_LIMIT", "abc"),
            ("BKAI_TOOL_LOOP_FEEDBACK_ROUNDS", "-1"),
        ],
    )
    def test_invalid_value_fails_at_import(self, key, value):
        completed = subprocess.run(
            [sys.executable, "-c", "import aidev_agent.config"],
            capture_output=True,
            text=True,
            env={**os.environ, key: value},
            check=False,
        )
        assert completed.returncode != 0
        assert key in completed.stderr


class _ResultEvents(BaseCallbackHandler):
    def __init__(self):
        self.messages = []

    def on_custom_event(self, name, data, **kwargs):
        if name == "on_tool_node_finish":
            self.messages.append(data.model_copy(deep=True))


async def _invoke(graph, state, recorder, use_async):
    config = {"callbacks": [recorder]}
    return await graph.ainvoke(state, config) if use_async else graph.invoke(state, config)


async def _result_event(message):
    agent = Mock(spec=AidevAGUIAgent)
    events = [
        event
        async for event in AidevAGUIAgent._handle_on_custom_event(
            agent, {"name": "on_tool_node_finish", "data": message}
        )
    ]
    assert len(events) == 1
    return events[0]


class TestLoopGuardEvents:
    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("use_timer", [False, True])
    async def test_rejection_event_is_written_once(self, use_async, use_timer):
        counter, recorder = [], _ResultEvents()
        graph = _graph(_tools(counter), settings=ToolNodeSettings(use_timer=use_timer, enable_tool_loop_guard=True))
        result = await _invoke(graph, _state(3), recorder, use_async)
        assert counter == [] and len(recorder.messages) == 1
        sent = recorder.messages[0]
        assert sent.status == "error" and sent.id == _last_tool_message(result).id
        event = await _result_event(sent)
        assert event.is_error and not event.skip_db and event.duration == 0
        writer = Mock(spec=BaseSessionWriter)
        writer._written_message_ids = set()
        BaseSessionWriter.handle_tool_call_result(writer, event)
        BaseSessionWriter.handle_tool_call_result(writer, event)
        writer._create_session_content.assert_called_once()
        payload = writer._create_session_content.call_args.kwargs
        assert payload["status"] == "error" and payload["content"] == sent.content
        assert payload["builtin_property"]["tool_call_id"] == sent.tool_call_id
        writer._flush_deferred_tool_call.assert_not_called()

    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize(
        "error_handler", [False, True, "failed", ValueError, (ValueError,), default_tool_call_handler]
    )
    async def test_termination_escapes_without_result_event(self, use_async, error_handler):
        recorder, counter = _ResultEvents(), []
        graph = _graph(_tools(counter), handle_tool_errors=error_handler)
        with pytest.raises(ToolLoopTerminationError):
            await _invoke(graph, _state(5), recorder, use_async)
        assert recorder.messages == [] and counter == []

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_send_context_rejection(self, use_async):
        counter, recorder = [], _ResultEvents()
        graph = StateGraph(_State)
        graph.add_node(
            "tools", build_tool_node(_tools(counter), node_options=ToolNodeSettings(enable_tool_loop_guard=True))
        )
        graph.add_conditional_edges(
            START,
            lambda state: [
                Send(
                    "tools",
                    ToolCallWithContext(
                        __type="tool_call_with_context", tool_call=state["messages"][-1].tool_calls[0], state=state
                    ),
                )
            ],
        )
        graph.add_edge("tools", END)
        result = await _invoke(graph.compile(), _state(3), recorder, use_async)
        assert counter == [] and len(recorder.messages) == 1
        assert _last_tool_message(result).tool_call_id == "call-3"


class TestContentErrorEvents:
    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("content, is_error", [("[ERROR] boom", True), ("text [ERROR]", False)])
    async def test_untrusted_status_is_set_before_event(self, use_async, content, is_error):
        @tool
        def external() -> str:
            """Fake MCP result."""
            return content

        external.metadata = {"mcp_name": "fake"}
        recorder = _ResultEvents()
        state = {"messages": [AIMessage(content="", tool_calls=[_call(0, "external", {})])]}
        result = await _invoke(_graph([external]), state, recorder, use_async)
        assert _last_tool_message(result).content.startswith("<untrusted>")
        assert (_last_tool_message(result).status == "error") is is_error
        assert len(recorder.messages) == 1
        event = await _result_event(recorder.messages[0])
        assert event.is_error is is_error

    def test_command_content_status(self):
        message = ToolMessage("[ERROR] boom", tool_call_id="call")
        command = Command(update={"messages": [message], "other": 1})
        result = _mark_content_error(command)
        assert result is command and result.update["other"] == 1 and message.status == "error"


class TestScanCost:
    def test_only_fingerprints_current_and_previous_segment(self, monkeypatch):
        messages = [HumanMessage(content="go")]
        for index in range(100):
            messages.extend(_round(index, name="other"))
        messages.extend(_round(100))
        messages.append(AIMessage(content="", tool_calls=[_call(101)]))
        original = loop_guard_module.fingerprint
        seen = []

        def record(args):
            seen.append(args)
            return original(args)

        monkeypatch.setattr(loop_guard_module, "fingerprint", record)
        assert _count_contiguous(messages, _call(101)) == 1
        assert len(seen) == 4


def _value_error_handler(error: ValueError | TypeError) -> str:
    return f"handled:{error}"


class TestErrorHandlerCompatibility:
    @pytest.mark.parametrize(
        "flag, expected",
        [
            (True, TOOL_CALL_ERROR_TEMPLATE.format(error="ValueError('boom')")),
            ("custom", "custom"),
            (ValueError, TOOL_CALL_ERROR_TEMPLATE.format(error="ValueError('boom')")),
            ((ValueError,), TOOL_CALL_ERROR_TEMPLATE.format(error="ValueError('boom')")),
            (_value_error_handler, "handled:boom"),
        ],
    )
    def test_existing_tool_error_policy(self, flag, expected):
        @tool
        def fail() -> str:
            """Raise an ordinary tool error."""
            raise ValueError("boom")

        graph = _graph([fail], handle_tool_errors=flag)
        message = _last_tool_message(
            graph.invoke({"messages": [AIMessage(content="", tool_calls=[_call(0, "fail", {})])]})
        )
        assert message.status == "error" and message.content == expected

    def test_narrow_handler_preserves_wrapper_fallback(self):
        @tool
        def fail() -> str:
            """Raise an unhandled tool error."""
            raise RuntimeError("boom")

        graph = _graph([fail], handle_tool_errors=_value_error_handler)
        # ToolNode 原有 wrapper 兜底仍调用 handler；该层行为不因扩展异常注解而改变。
        message = _last_tool_message(
            graph.invoke({"messages": [AIMessage(content="", tool_calls=[_call(0, "fail", {})])]})
        )
        assert message.content == "handled:boom"


class TestLoopGuardEnabled:
    @pytest.mark.parametrize("use_async", [False, True])
    @pytest.mark.parametrize("enabled", [False, True])
    async def test_switch_controls_rejection(self, use_async, enabled):
        counter, recorder = [], _ResultEvents()
        result = await _invoke(
            _graph(_tools(counter), settings=ToolNodeSettings(enable_tool_loop_guard=enabled)),
            _state(3),
            recorder,
            use_async,
        )
        assert counter == ([] if enabled else ["x"])
        assert (_last_tool_message(result).status == "error") is enabled
        assert len(recorder.messages) == 1
        assert (recorder.messages[0].status == "error") is enabled

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_disabled_skips_scan_and_termination(self, monkeypatch, use_async):
        scan = Mock(side_effect=AssertionError("disabled guard must not scan"))
        monkeypatch.setattr(loop_guard_module, "_scan", scan)
        counter, recorder = [], _ResultEvents()
        result = await _invoke(
            _graph(_tools(counter), settings=ToolNodeSettings(enable_tool_loop_guard=False)),
            _state(5),
            recorder,
            use_async,
        )
        scan.assert_not_called()
        assert counter == ["x"] and _last_tool_message(result).status == "success"
        assert len(recorder.messages) == 1

    @pytest.mark.parametrize("value, expected", [("true", "True"), ("false", "False")])
    def test_env_boolean(self, value, expected):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from aidev_agent.core.nodes.tool import ToolNodeSettings; print(ToolNodeSettings().enable_tool_loop_guard)",
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "BKAI_TOOL_LOOP_GUARD_ENABLED": value},
        )
        assert result.returncode == 0 and result.stdout.strip() == expected


class TestLoopGuardDefault:
    def test_unset_env_disables_guard(self):
        env = dict(os.environ)
        env.pop("BKAI_TOOL_LOOP_GUARD_ENABLED", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from aidev_agent.core.nodes.tool import ToolNodeSettings; print(ToolNodeSettings().enable_tool_loop_guard)",
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert result.returncode == 0 and result.stdout.strip() == "False"
