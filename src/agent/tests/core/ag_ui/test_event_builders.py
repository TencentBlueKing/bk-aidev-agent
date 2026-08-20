# -*- coding: utf-8 -*-
"""event_builders.py 共享纯函数单元测试。

覆盖 is_tool_approval_required / enhance_tool_call / build_tool_result_event /
should_end_thinking / should_switch_thinking_step / build_model_end_payload 六个纯函数的
正常/边界/None 场景。
"""

from unittest.mock import MagicMock

import pytest
from aidev_agent.core.ag_ui.event_builders import (
    _is_deferred_tool,
    build_model_end_payload,
    build_tool_calls_with_approval_filter,
    build_tool_result_event,
    enhance_tool_call,
    is_tool_approval_required,
    should_end_thinking,
    should_suppress_approval_tool_call,
    should_switch_thinking_step,
)
from langchain_core.messages import AIMessage, ToolMessage


def _make_tool(*, description: str = "desc", mcp_name: str = "", approval: dict | None = None) -> MagicMock:
    """构造 Mock Tool 对象，带 description / metadata 属性。"""
    tool = MagicMock()
    tool.description = description
    metadata = {}
    if mcp_name:
        metadata["mcp_name"] = mcp_name
    if approval is not None:
        metadata["approval"] = approval
    tool.metadata = metadata
    return tool


def _make_tool_message(
    *,
    content: str | list | dict | None = "result content",
    tool_call_id: str = "call-1",
    message_id: str = "msg-1",
    duration: float | None = 1.5,
    status: str | None = None,
    error: str | None = None,
    name: str | None = "mock_tool",
) -> MagicMock:
    """构造 Mock ToolMessage 对象，带 content / tool_call_id / id / additional_kwargs / status / name 属性。"""
    tool_msg = MagicMock()
    tool_msg.content = content
    tool_msg.tool_call_id = tool_call_id
    tool_msg.name = None
    tool_msg.id = message_id
    tool_msg.additional_kwargs = {"duration": duration} if duration is not None else {}
    tool_msg.status = status
    tool_msg.error = error
    tool_msg.name = name
    return tool_msg


class TestIsToolApprovalRequired:
    def test_tool_with_approval_configured_returns_true(self):
        tool = _make_tool(approval={"enabled": True})
        tools = {"my_tool": tool}
        assert is_tool_approval_required("my_tool", tools) is True

    def test_tool_without_approval_returns_false(self):
        tool = _make_tool()
        tools = {"my_tool": tool}
        assert is_tool_approval_required("my_tool", tools) is False

    def test_empty_tools_dict_returns_false(self):
        assert is_tool_approval_required("my_tool", {}) is False

    def test_tool_call_name_not_in_tools_returns_false(self):
        tools = {"other_tool": _make_tool(approval={"enabled": True})}
        assert is_tool_approval_required("my_tool", tools) is False


class TestEnhanceToolCall:
    def test_tool_exists_returns_description_and_mcp_name(self):
        tool = _make_tool(description="my description", mcp_name="my-mcp")
        tools = {"my_tool": tool}
        result = enhance_tool_call("my_tool", tools)
        assert result == {"description": "my description", "mcp_name": "my-mcp"}

    def test_tool_none_returns_empty_strings(self):
        result = enhance_tool_call("missing_tool", {})
        assert result == {"description": "", "mcp_name": ""}

    def test_tool_without_mcp_name_returns_empty_mcp_name(self):
        tool = _make_tool(description="desc")
        tools = {"my_tool": tool}
        result = enhance_tool_call("my_tool", tools)
        assert result == {"description": "desc", "mcp_name": ""}


class TestBuildToolResultEvent:
    @pytest.mark.parametrize("name", ["ask_user_question", "query_logs", None])
    @pytest.mark.parametrize("immediate", [False, True])
    def test_tool_name_survives_wire_serialization(self, name, immediate):
        message = ToolMessage(content="done", tool_call_id="call-1", name=name)
        event = build_tool_result_event(message, is_immediate=immediate)
        assert event.model_dump(by_alias=True)["toolCallName"] == name

    @pytest.mark.parametrize("name", ["ask_user_question", None])
    def test_replayed_tool_result_keeps_name(self, name):
        from aidev_agent.core.ag_ui.utils import langchain_messages_to_streaming_events

        message = ToolMessage(content="done", tool_call_id="call-1", name=name)
        (event,) = list(langchain_messages_to_streaming_events([message]))
        assert event.model_dump(by_alias=True)["toolCallName"] == name

    def test_normal_completion_duration_and_error_from_kwargs(self):
        tool_msg = _make_tool_message(duration=3.2, status=None, error=None)
        event = build_tool_result_event(tool_msg, is_immediate=False)
        assert event.duration == 3.2
        assert event.is_error is False
        assert event.tool_call_id == "call-1"
        assert event.message_id == "msg-1"
        assert event.content == "result content"
        assert event.role == "tool"
        # D-06：tool_call_name 取自 ToolMessage.name
        assert event.tool_call_name == "mock_tool"

    def test_error_status_sets_is_error_true(self):
        tool_msg = _make_tool_message(status="error")
        event = build_tool_result_event(tool_msg, is_immediate=False)
        assert event.is_error is True

    def test_error_attr_sets_is_error_true(self):
        tool_msg = _make_tool_message(status=None, error="boom")
        event = build_tool_result_event(tool_msg, is_immediate=False)
        assert event.is_error is True

    def test_is_immediate_true_duration_none_and_error_false(self):
        tool_msg = _make_tool_message(duration=99, status="error")
        event = build_tool_result_event(tool_msg, is_immediate=True)
        assert event.duration is None
        assert event.is_error is False

    def test_content_non_str_converted_to_str(self):
        tool_msg = _make_tool_message(content=[1, 2, 3])
        event = build_tool_result_event(tool_msg, is_immediate=False)
        assert isinstance(event.content, str)
        assert event.content == "[1, 2, 3]"

    def test_content_empty_value_converted_to_empty_str(self):
        tool_msg = _make_tool_message(content=None)
        event = build_tool_result_event(tool_msg, is_immediate=False)
        assert event.content == ""

    def test_message_id_fallback_to_uuid_when_no_id(self):
        tool_msg = _make_tool_message(message_id="")
        tool_msg.id = None
        event = build_tool_result_event(tool_msg, is_immediate=False)
        assert event.message_id  # 非空，是生成的 uuid


class TestShouldEndThinking:
    def test_thinking_process_present_reasoning_none_returns_true(self):
        assert should_end_thinking({"index": 0}, None) is True

    def test_reasoning_present_returns_false(self):
        assert should_end_thinking({"index": 0}, {"index": 0}) is False

    def test_thinking_process_none_returns_false(self):
        assert should_end_thinking(None, None) is False


class TestShouldSwitchThinkingStep:
    def test_different_index_returns_true(self):
        assert should_switch_thinking_step({"index": 0}, {"index": 1}) is True

    def test_same_index_returns_false(self):
        assert should_switch_thinking_step({"index": 0}, {"index": 0}) is False

    def test_thinking_process_empty_returns_false(self):
        assert should_switch_thinking_step(None, {"index": 1}) is False

    def test_reasoning_data_empty_returns_false(self):
        assert should_switch_thinking_step({"index": 0}, None) is False


class TestBuildModelEndPayload:
    """build_model_end_payload 行为等价性测试（迁移自 base.py _build_tool_calls_with_approval_filter + _resolve_content）。"""

    def test_plain_text_reply(self):
        """普通文本回复：content="你好", tool_calls=[], reasoning_content=None"""
        output_message = AIMessage(content="你好", id="msg-1", tool_calls=[], additional_kwargs={})
        payload = build_model_end_payload(output_message, {})
        assert payload["content"] == "你好"
        assert payload["tool_calls"] == []
        assert payload["deferred_tool_calls"] == []

    def test_immediate_tool_call_non_approval(self):
        """有即时工具调用（非审批工具）：content="正在调用工具...", tool_calls 含 1 项, deferred_tool_calls == []"""
        tool = _make_tool()
        tools_mapping = {"get_weather": tool}
        output_message = AIMessage(
            content="",
            id="msg-2",
            tool_calls=[{"name": "get_weather", "args": {}, "id": "call-1"}],
            additional_kwargs={},
        )
        payload = build_model_end_payload(output_message, tools_mapping)
        assert payload["content"] == "正在调用工具..."
        assert len(payload["tool_calls"]) == 1
        assert payload["deferred_tool_calls"] == []

    def test_approval_tool_call_deferred(self):
        """有审批工具调用：content="", tool_calls == [], deferred_tool_calls 含 1 项"""
        tool = _make_tool(approval={"enabled": True})
        tools_mapping = {"approval_tool": tool}
        output_message = AIMessage(
            content="",
            id="msg-3",
            tool_calls=[{"name": "approval_tool", "args": {}, "id": "call-2"}],
            additional_kwargs={},
        )
        payload = build_model_end_payload(output_message, tools_mapping)
        assert payload["content"] == ""
        assert payload["tool_calls"] == []
        assert len(payload["deferred_tool_calls"]) == 1

    def test_reasoning_model_empty_content(self):
        """reasoning 模型空 content：content="", tool_calls=[], reasoning_content="思考结论" """
        output_message = AIMessage(
            content="",
            id="msg-4",
            tool_calls=[],
            additional_kwargs={"reasoning_content": "思考结论"},
        )
        payload = build_model_end_payload(output_message, {})
        assert payload["content"] == "思考结论"
        assert payload["reasoning_content"] == "思考结论"

    def test_reasoning_duration_extraction(self):
        """reasoning_duration 提取：additional_kwargs={"reasoning_time": 5} → payload.reasoning_duration == 5"""
        output_message = AIMessage(
            content="回复",
            id="msg-5",
            tool_calls=[],
            additional_kwargs={"reasoning_time": 5},
        )
        payload = build_model_end_payload(output_message, {})
        assert payload["reasoning_duration"] == 5

    def test_message_id_extraction(self):
        """message_id 提取：output_message.id == "msg-1" → payload.message_id == "msg-1" """
        output_message = AIMessage(content="回复", id="msg-1", tool_calls=[], additional_kwargs={})
        payload = build_model_end_payload(output_message, {})
        assert payload["message_id"] == "msg-1"


class TestShouldSuppressApprovalToolCall:
    """DB 等价谓词 should_suppress_approval_tool_call 组合矩阵（D-05 方向 a 同源复算）。"""

    def test_non_approval_tool_call_never_suppressed(self):
        """非审批工具：即使无 ToolMessage 也保留（immediate 不过滤）。"""
        tool_call = {"id": "c1", "name": "my_tool", "args": {}, "type": "tool_call"}
        tools = {"my_tool": _make_tool(approval=None)}
        assert should_suppress_approval_tool_call(tool_call, [], tools) is False

    def test_approval_pending_no_tool_message_suppressed(self):
        """审批配置命中且无对应 ToolMessage → 应过滤（True）。"""
        tool_call = {"id": "c1", "name": "ask_user_question", "args": {}, "type": "tool_call"}
        tools = {"ask_user_question": _make_tool(approval={"enabled": True})}
        assert should_suppress_approval_tool_call(tool_call, [], tools) is True

    def test_approval_executed_with_tool_message_kept(self):
        """审批配置命中但有对应 ToolMessage（已执行）→ 保留（False）。"""
        tool_call = {"id": "c1", "name": "ask_user_question", "args": {}, "type": "tool_call"}
        tools = {"ask_user_question": _make_tool(approval={"enabled": True})}
        state_messages = [ToolMessage(content="answered", tool_call_id="c1", name="ask_user_question")]
        assert should_suppress_approval_tool_call(tool_call, state_messages, tools) is False

    def test_approval_pending_with_other_tool_message_keeps_suppressed(self):
        """审批配置命中但仅有其他 tool_call 的 ToolMessage → 仍 pending（True）。"""
        tool_call = {"id": "c1", "name": "ask_user_question", "args": {}, "type": "tool_call"}
        tools = {"ask_user_question": _make_tool(approval={"enabled": True})}
        state_messages = [ToolMessage(content="result", tool_call_id="other-call", name="my_tool")]
        assert should_suppress_approval_tool_call(tool_call, state_messages, tools) is True

    def test_empty_tools_mapping_no_suppression(self):
        """tools_mapping 为空 → 无审批工具命中 → 保留（False）。"""
        tool_call = {"id": "c1", "name": "ask_user_question", "args": {}, "type": "tool_call"}
        assert should_suppress_approval_tool_call(tool_call, [], {}) is False

    def test_missing_tool_call_id_handled(self):
        """tool_call 缺 id：无 ToolMessage 命中 → pending 过滤（True）。"""
        tool_call = {"name": "ask_user_question", "args": {}}
        tools = {"ask_user_question": _make_tool(approval={"enabled": True})}
        assert should_suppress_approval_tool_call(tool_call, [], tools) is True


class TestIsDeferredTool:
    """D-15 deferred 判定谓词：approval 或 ask_user_question 均延迟写入（同源复算对称）。"""

    def test_approval_configured_tool_is_deferred(self):
        tool = _make_tool(approval={"enabled": True}, description="t")
        assert _is_deferred_tool(tool) is True

    def test_ask_user_question_tool_is_deferred_without_approval(self):
        """ask_user_question 工具即使未配置 approval 也走 deferred（D-15 核心）。"""
        tool = _make_tool(approval=None)
        tool.name = "ask_user_question"
        assert _is_deferred_tool(tool) is True

    def test_plain_tool_not_deferred(self):
        tool = _make_tool(approval=None)
        tool.name = "get_weather"
        assert _is_deferred_tool(tool) is False

    def test_none_tool_not_deferred(self):
        assert _is_deferred_tool(None) is False


class TestAskUserQuestionDeferred:
    """D-15 ask_user deferred 对齐：build_tool_calls_with_approval_filter 将 ask_user 延迟写入。"""

    def test_ask_user_tool_call_goes_to_deferred(self):
        """ask_user_question 工具调用 → deferred_tool_calls（延迟写而非 immediate）。"""
        tool = _make_tool(approval=None)
        tool.name = "ask_user_question"
        tools_mapping = {"ask_user_question": tool}
        output_message = AIMessage(
            content="",
            id="msg-auq",
            tool_calls=[
                {"name": "ask_user_question", "args": {"questions": [{"question": "确认？"}]}, "id": "call-auq"}
            ],
            additional_kwargs={},
        )
        immediate, deferred = build_tool_calls_with_approval_filter(output_message, tools_mapping)
        assert immediate == []
        assert len(deferred) == 1
        assert deferred[0]["id"] == "call-auq"

    def test_plain_tool_stays_immediate_in_same_call(self):
        """同一次 build：普通工具走 immediate，ask_user 走 deferred（两谓词对称不互扰）。"""
        ask_tool = _make_tool(approval=None)
        ask_tool.name = "ask_user_question"
        plain_tool = _make_tool(approval=None)
        plain_tool.name = "get_weather"
        tools_mapping = {"ask_user_question": ask_tool, "get_weather": plain_tool}
        output_message = AIMessage(
            content="",
            id="msg-mix",
            tool_calls=[
                {"name": "get_weather", "args": {}, "id": "call-w"},
                {"name": "ask_user_question", "args": {"questions": []}, "id": "call-a"},
            ],
            additional_kwargs={},
        )
        immediate, deferred = build_tool_calls_with_approval_filter(output_message, tools_mapping)
        assert [t["id"] for t in immediate] == ["call-w"]
        assert [t["id"] for t in deferred] == ["call-a"]

    def test_suppress_symmetric_with_ask_user_without_approval(self):
        """同源复算对称：ask_user 工具未配置 approval 时也应被 should_suppress 过滤（快照/重放对称）。"""
        tool = _make_tool(approval=None)
        tool.name = "ask_user_question"
        tools = {"ask_user_question": tool}
        tool_call = {"id": "call-auq", "name": "ask_user_question", "args": {}}
        # 无 ToolMessage → 过滤（True），与 approval pending 同语义
        assert should_suppress_approval_tool_call(tool_call, [], tools) is True
        # 有 ToolMessage（已执行/已答）→ 保留（False）
        state_messages = [ToolMessage(content="answered", tool_call_id="call-auq", name="ask_user_question")]
        assert should_suppress_approval_tool_call(tool_call, state_messages, tools) is False
