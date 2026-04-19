# -*- coding: utf-8 -*-
"""
AGUISessionWriter 核心单元测试
"""

from unittest.mock import MagicMock

import pytest
from ag_ui.core import EventType, RunErrorEvent
from ag_ui.core.events import RawEvent
from aidev_agent.core.ag_ui.types import CustomEventNames, LangGraphEventTypes
from aidev_agent.enums import PromptRole
from aidev_agent.services.event_handlers import AGUISessionWriter


@pytest.fixture
def mock_client():
    """创建 Mock 的平台 Client"""
    client = MagicMock()
    client.api.create_chat_session_content = MagicMock()
    return client


@pytest.fixture
def session_writer(mock_client):
    """创建 AGUISessionWriter 实例"""
    return AGUISessionWriter(
        session_code="test-session-123",
        client=mock_client,
        username="test-user",
    )


def make_model_end_event(message_id: str, content: str, tool_calls: list = None, reasoning_content: str = None):
    """构造 on_chat_model_end 事件"""
    output_message = MagicMock()
    output_message.id = message_id
    output_message.content = content
    output_message.tool_calls = tool_calls or []
    output_message.additional_kwargs = {}
    if reasoning_content:
        output_message.additional_kwargs["reasoning_content"] = reasoning_content
        output_message.additional_kwargs["reasoning_time"] = 1.5

    return RawEvent(
        type=EventType.RAW,
        event={
            "event": LangGraphEventTypes.OnChatModelEnd.value,
            "data": {"output": output_message},
        },
    )


def make_tool_finish_event(tool_call_id: str, message_id: str, content: str, status: str = "success"):
    """构造 on_tool_node_finish 事件"""
    tool_message = MagicMock()
    tool_message.id = message_id
    tool_message.tool_call_id = tool_call_id
    tool_message.content = content
    tool_message.status = status
    tool_message.additional_kwargs = {}

    return RawEvent(
        type=EventType.RAW,
        event={
            "event": LangGraphEventTypes.OnCustomEvent.value,
            "name": CustomEventNames.OnToolNodeFinish.value,
            "data": tool_message,
        },
    )


class TestHandleToolFinishStatusMapping:
    """测试 handle_tool_finish 的状态映射逻辑"""

    def test_tool_success_maps_to_success(self, session_writer, mock_client):
        """工具成功时，status='success' 映射为平台的 'success'"""
        event = make_tool_finish_event(
            tool_call_id="call_123",
            message_id="msg_tool_123",
            content="计算结果: 42",
            status="complete",
        )

        session_writer(event)

        # 验证 API 调用
        mock_client.api.create_chat_session_content.assert_called_once()
        call_args = mock_client.api.create_chat_session_content.call_args
        payload = call_args.kwargs["json"]

        assert payload["status"] == "complete"
        assert payload["role"] == PromptRole.TOOL.value
        assert payload["content"] == "计算结果: 42"

    def test_tool_error_maps_to_fail(self, session_writer, mock_client):
        """工具错误时，status='error' 映射为平台的 'fail'"""
        event = make_tool_finish_event(
            tool_call_id="call_456",
            message_id="msg_tool_456",
            content="Tool failed: HTTP 500 Internal Server Error",
            status="error",
        )

        session_writer(event)

        # 验证 API 调用
        mock_client.api.create_chat_session_content.assert_called_once()
        call_args = mock_client.api.create_chat_session_content.call_args
        payload = call_args.kwargs["json"]

        assert payload["status"] == "fail"
        assert payload["role"] == PromptRole.TOOL.value
        assert "HTTP 500" in payload["content"]


class TestHandleModelEnd:
    """测试 handle_model_end 的回写逻辑"""

    def test_model_end_with_content(self, session_writer, mock_client):
        """模型输出有内容时正常回写"""
        event = make_model_end_event(
            message_id="msg_001",
            content="这是 AI 的回答",
        )

        session_writer(event)

        mock_client.api.create_chat_session_content.assert_called_once()
        call_args = mock_client.api.create_chat_session_content.call_args
        payload = call_args.kwargs["json"]

        assert payload["role"] == PromptRole.ASSISTANT.value
        assert payload["content"] == "这是 AI 的回答"
        assert payload["status"] == "complete"

    def test_model_end_empty_content_uses_placeholder(self, session_writer, mock_client):
        """模型输出内容为空但有 tool_calls 时使用占位符（后端 API 不接受空字符串或纯空白字符）"""
        event = make_model_end_event(
            message_id="msg_002",
            content="",
            tool_calls=[{"id": "call_1", "name": "calculator", "args": {"a": 1}}],
        )

        session_writer(event)

        call_args = mock_client.api.create_chat_session_content.call_args
        payload = call_args.kwargs["json"]

        assert "..." in payload["content"]

    def test_model_end_with_reasoning(self, session_writer, mock_client):
        """包含 reasoning_content 时额外回写推理内容"""
        event = make_model_end_event(
            message_id="msg_003",
            content="最终答案",
            reasoning_content="让我思考一下...",
        )

        session_writer(event)

        # 应该调用两次：一次 reasoning，一次 assistant
        assert mock_client.api.create_chat_session_content.call_count == 2

        calls = mock_client.api.create_chat_session_content.call_args_list

        # 第一次是 reasoning
        reasoning_payload = calls[0].kwargs["json"]
        assert reasoning_payload["role"] == PromptRole.REASONING.value
        assert reasoning_payload["content"] == '["让我思考一下..."]'

        # 第二次是 assistant
        assistant_payload = calls[1].kwargs["json"]
        assert assistant_payload["role"] == PromptRole.ASSISTANT.value
        assert assistant_payload["content"] == "最终答案"


class TestDeduplication:
    """测试去重逻辑"""

    def test_duplicate_message_id_not_written(self, session_writer, mock_client):
        """重复的 message_id 不会重复调用 API"""
        event = make_model_end_event(message_id="msg_dup", content="内容")

        # 调用两次
        session_writer(event)
        session_writer(event)

        # 只应调用一次
        assert mock_client.api.create_chat_session_content.call_count == 1

    def test_duplicate_tool_call_id_not_written(self, session_writer, mock_client):
        """重复的 tool_call_id 不会重复调用 API"""
        event = make_tool_finish_event(
            tool_call_id="call_dup",
            message_id="msg_tool_dup",
            content="结果",
            status="success",
        )

        # 调用两次
        session_writer(event)
        session_writer(event)

        # 只应调用一次
        assert mock_client.api.create_chat_session_content.call_count == 1


class TestHandleRunError:
    """测试 handle_run_error 的回写逻辑"""

    def test_run_error_writes_fail_status(self, session_writer, mock_client):
        """运行错误时回写 fail 状态"""
        event = RunErrorEvent(type=EventType.RUN_ERROR, message="执行过程中发生错误")

        session_writer(event)

        mock_client.api.create_chat_session_content.assert_called_once()
        call_args = mock_client.api.create_chat_session_content.call_args
        payload = call_args.kwargs["json"]

        assert payload["status"] == "fail"
        assert payload["role"] == PromptRole.ASSISTANT.value
        assert payload["content"] == "执行过程中发生错误"
        assert payload["property"]["builtin_property"]["error"] is True


class TestAPIErrorHandling:
    """测试 API 调用异常处理"""

    def test_api_error_logged_not_raised(self, session_writer, mock_client):
        """API 调用失败时记录日志但不抛出异常"""
        mock_client.api.create_chat_session_content.side_effect = Exception("Network error")

        event = make_model_end_event(message_id="msg_err", content="内容")

        # 不应抛出异常
        session_writer(event)

        # 验证确实调用了 API（即使失败）
        mock_client.api.create_chat_session_content.assert_called_once()
