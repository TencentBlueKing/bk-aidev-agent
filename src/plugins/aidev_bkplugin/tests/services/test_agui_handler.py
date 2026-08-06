# -*- coding: utf-8 -*-
"""
AGUISessionWriter 核心单元测试
"""

import json
from unittest.mock import MagicMock

import pytest
from ag_ui.core import CustomEvent, EventType, RunErrorEvent
from ag_ui.core.events import RawEvent
from aidev_agent.core.ag_ui.events import ExtendToolCallResultEvent
from aidev_agent.core.ag_ui.types import (
    CustomEventNames,
    CustomMessageType,
    LangGraphEventTypes,
    SessionPersistenceEventNames,
)
from aidev_agent.enums import ActivityType, PromptRole, SessionsStatus
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


def make_tool_result_event(
    tool_call_id: str, message_id: str, content: str, *, is_error: bool = False
) -> ExtendToolCallResultEvent:
    """构造 TOOL_CALL_RESULT 事件（DB 回写实际入口）"""
    return ExtendToolCallResultEvent(
        type=EventType.TOOL_CALL_RESULT,
        tool_call_id=tool_call_id,
        message_id=message_id,
        content=content,
        role="tool",
        is_error=is_error,
        additional_metadata={},
    )


class TestHandleToolCallResultStatusMapping:
    """测试 handle_tool_call_result 的状态映射逻辑"""

    def test_tool_success_maps_to_complete(self, session_writer, mock_client):
        """工具成功时回写 status='complete'"""
        event = make_tool_result_event(
            tool_call_id="call_123",
            message_id="msg_tool_123",
            content="计算结果: 42",
            is_error=False,
        )

        session_writer(event)

        mock_client.api.create_chat_session_content.assert_called_once()
        payload = mock_client.api.create_chat_session_content.call_args.kwargs["json"]

        assert payload["status"] == "complete"
        assert payload["role"] == PromptRole.TOOL.value
        assert payload["content"] == "计算结果: 42"

    def test_tool_error_maps_to_error(self, session_writer, mock_client):
        """工具错误时按 v2 协议回写 status='error'"""
        event = make_tool_result_event(
            tool_call_id="call_456",
            message_id="msg_tool_456",
            content="Tool failed: HTTP 500 Internal Server Error",
            is_error=True,
        )

        session_writer(event)

        mock_client.api.create_chat_session_content.assert_called_once()
        payload = mock_client.api.create_chat_session_content.call_args.kwargs["json"]

        assert payload["status"] == "error"
        assert payload["role"] == PromptRole.TOOL.value
        assert "HTTP 500" in payload["content"]


class TestHandleModelEnd:
    """测试 handle_model_end 的回写逻辑"""

    @pytest.mark.parametrize("turn_id", ["", "turn-1"])
    def test_model_end_with_content(self, mock_client, turn_id):
        """模型输出回写；有 turn_id 时写入 property。"""
        writer = AGUISessionWriter(
            session_code="test-session-123",
            client=mock_client,
            username="test-user",
            turn_id=turn_id,
        )
        writer(make_model_end_event(message_id="msg_001", content="这是 AI 的回答"))

        payload = mock_client.api.create_chat_session_content.call_args.kwargs["json"]
        assert payload["role"] == PromptRole.ASSISTANT.value
        assert payload["content"] == "这是 AI 的回答"
        if turn_id:
            assert payload["property"]["turn_id"] == turn_id
        else:
            assert "turn_id" not in payload.get("property", {})

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
        event = make_tool_result_event(
            tool_call_id="call_dup",
            message_id="msg_tool_dup",
            content="结果",
        )

        # 调用两次
        session_writer(event)
        session_writer(event)

        # 只应调用一次
        assert mock_client.api.create_chat_session_content.call_count == 1


class TestCustomEventSessionPath:
    """零 RAW 后：会话回写走 CustomEvent / TOOL_CALL_RESULT 入口"""

    def test_model_end_via_session_persistence_custom(self, session_writer, mock_client):
        event = CustomEvent(
            type=EventType.CUSTOM,
            name=SessionPersistenceEventNames.ChatModelEnd.value,
            value={
                "message_id": "ce_msg_1",
                "content": "自定义通路",
                "tool_calls": [],
                "deferred_tool_calls": [],
            },
        )
        session_writer(event)
        mock_client.api.create_chat_session_content.assert_called_once()
        payload = mock_client.api.create_chat_session_content.call_args.kwargs["json"]
        assert payload["role"] == PromptRole.ASSISTANT.value
        assert payload["content"] == "自定义通路"

    def test_tool_result_via_tool_call_result_event(self, session_writer, mock_client):
        """工具结果走 TOOL_CALL_RESULT（ExtendToolCallResultEvent）回写"""
        event = make_tool_result_event(
            tool_call_id="call_ce",
            message_id="tid1",
            content="tool out",
        )
        session_writer(event)
        mock_client.api.create_chat_session_content.assert_called_once()
        payload = mock_client.api.create_chat_session_content.call_args.kwargs["json"]
        assert payload["role"] == PromptRole.TOOL.value
        assert payload["content"] == "tool out"
        assert payload["status"] == "complete"

    def test_legacy_tool_finish_custom_event_is_ignored(self, session_writer, mock_client):
        tool_message = MagicMock()
        tool_message.id = "tid1"
        tool_message.tool_call_id = "call_ce"
        tool_message.content = "tool out"
        tool_message.status = "complete"
        tool_message.additional_kwargs = {}

        event = CustomEvent(
            type=EventType.CUSTOM,
            name=CustomEventNames.OnToolNodeFinish.value,
            value=tool_message,
        )
        session_writer(event)
        mock_client.api.create_chat_session_content.assert_not_called()


class TestHandleRunError:
    """测试 handle_run_error 的回写逻辑"""

    def test_run_error_defers_session_status(self, session_writer, mock_client):
        """RUN_ERROR 只记录错误内容，不能抢先写会话终态。"""
        event = RunErrorEvent(type=EventType.RUN_ERROR, message="执行过程中发生错误")

        session_writer(event)

        mock_client.api.create_chat_session_content.assert_called_once()
        call_args = mock_client.api.create_chat_session_content.call_args
        payload = call_args.kwargs["json"]

        assert payload["status"] == "fail"
        assert payload["role"] == PromptRole.ASSISTANT.value
        assert payload["content"] == "执行过程中发生错误"
        assert payload["property"]["builtin_property"]["error"] is True
        mock_client.api.update_chat_session.assert_not_called()

    def test_run_error_finished_keeps_session_failed(self, session_writer, mock_client):
        """运行错误后结束流，不应把会话覆盖为 finished"""
        event = RunErrorEvent(type=EventType.RUN_ERROR, message="执行过程中发生错误")

        session_writer(event)
        session_writer.set_streaming_finished()

        mock_client.api.update_chat_session.assert_called_once_with(
            path_params={"session_code": "test-session-123"},
            json={"status": SessionsStatus.FAILED.value},
            headers={"X-BKAIDEV-USER": "test-user"},
        )

    def test_finished_status_retries_then_succeeds(self, session_writer, mock_client, monkeypatch):
        sleep = MagicMock()
        monkeypatch.setattr("aidev_agent.services.event_handlers.agui_writer.time.sleep", sleep)
        mock_client.api.update_chat_session.side_effect = [RuntimeError("one"), RuntimeError("two"), {}]

        session_writer.set_streaming_finished()

        assert mock_client.api.update_chat_session.call_count == 3
        assert [call.args[0] for call in sleep.call_args_list] == [0.2, 0.4]

    def test_finished_status_raises_after_retries_exhausted(self, session_writer, mock_client, monkeypatch):
        monkeypatch.setattr("aidev_agent.services.event_handlers.agui_writer.time.sleep", MagicMock())
        mock_client.api.update_chat_session.side_effect = RuntimeError("platform unavailable")

        with pytest.raises(RuntimeError, match="platform unavailable"):
            session_writer.set_streaming_finished()

        assert mock_client.api.update_chat_session.call_count == 3


def make_flow_agent_result_event(task_id: str, task_state: str = "RUNNING"):
    """构造 flow_agent_result 自定义事件（value 为 dict）"""
    return CustomEvent(
        type=EventType.CUSTOM,
        name=CustomMessageType.FLOW_AGENT_RESULT.value,
        value={"task_id": task_id, "task_state": task_state, "nodes": {}},
    )


def make_existing_flow_content(content_id: int, task_id: str, turn_id: str = ""):
    """构造一条已入库的 flow_agent activity 记录"""
    content_property = {
        "builtin_property": {
            "message_id": f"flow_result_existing_{content_id}",
            "type": ActivityType.FLOW_AGENT.value,
        }
    }
    if turn_id:
        content_property["turn_id"] = turn_id
    return {
        "id": content_id,
        "role": PromptRole.ACTIVITY.value,
        "content": json.dumps({"task_id": task_id, "task_state": "FAILED"}),
        "property": content_property,
    }


class TestFlowAgentResultResume:
    """retry/skip resume：命中已有 flow_agent activity 则 update，否则按场景 create 或抛错"""

    def test_resume_updates_matched_record(self, mock_client):
        """仅 task_id 命中：update 原记录，并从库里恢复 turn_id"""
        mock_client.api.get_chat_session_contents.return_value = {
            "data": [make_existing_flow_content(content_id=42, task_id="123", turn_id="turn-x")]
        }
        writer = AGUISessionWriter(session_code="sc", client=mock_client, username="u", task_id="123")

        writer(make_flow_agent_result_event(task_id="123"))

        mock_client.api.create_chat_session_content.assert_not_called()
        update_args = mock_client.api.update_chat_session_content.call_args
        assert update_args.kwargs["path_params"] == {"id": 42}
        assert update_args.kwargs["json"]["property"]["turn_id"] == "turn-x"

    @pytest.mark.parametrize(
        "existing_contents",
        [[], [make_existing_flow_content(content_id=42, task_id="999")]],
    )
    def test_resume_raises_when_unresolved(self, mock_client, existing_contents):
        """task_id 未命中：抛错，禁止新建"""
        mock_client.api.get_chat_session_contents.return_value = {"data": existing_contents}
        writer = AGUISessionWriter(session_code="sc", client=mock_client, username="u", task_id="123")

        with pytest.raises(RuntimeError, match="task_id=123"):
            writer(make_flow_agent_result_event(task_id="123"))

        mock_client.api.create_chat_session_content.assert_not_called()


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
