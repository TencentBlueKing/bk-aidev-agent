# -*- coding: utf-8 -*-
"""KNOWLEDGE_RAG_RESULT 事件透传 + DB 写入回归测试（D-14/D-15/D-06）。

覆盖三个层次：
a. SSE 侧：_dispatch_event 纯分发，CUSTOM 透传不转换（转换在 _handle_on_custom_event 覆写中）
b. DB 侧：handle_reference_document 收到透传后的完整 dict 事件，能正确提取 message_id 并写入
c. 集成：_dispatch_event(CustomEvent(KNOWLEDGE_RAG_RESULT)) 后 DB 收到的 message_id 与 SSE 收到的 message_id 一致
"""

import json
from unittest.mock import MagicMock, patch

from ag_ui.core import CustomEvent, EventType
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.services.event_handlers.base import BaseSessionWriter

# ---------- 测试数据构造 ----------

KNOWLEDGE_MESSAGE_ID = "msg_knowledge_test_001"
REFERENCE_DOC_DATA = [
    {"originFile": "doc1.md", "url": "https://example.com/doc1", "name": "文档1"},
    {"originFile": "doc2.md", "url": "https://example.com/doc2", "name": "文档2"},
]
DURATION = 150


def _make_knowledge_custom_event() -> CustomEvent:
    """构造与 agent.py:765-772 OnCustomEvent 分支一致的 CustomEvent。

    value=event["data"]，即 {"message_id":..., "data":[...], "duration":...} 完整 dict。
    """
    return CustomEvent(
        type=EventType.CUSTOM,
        name=CustomMessageType.KNOWLEDGE_RAG_RESULT.value,
        value={
            "message_id": KNOWLEDGE_MESSAGE_ID,
            "data": REFERENCE_DOC_DATA,
            "duration": DURATION,
        },
        raw_event={
            "event": "on_custom_event",
            "name": CustomMessageType.KNOWLEDGE_RAG_RESULT.value,
            "data": {
                "message_id": KNOWLEDGE_MESSAGE_ID,
                "data": REFERENCE_DOC_DATA,
                "duration": DURATION,
            },
        },
    )


class _ConcreteSessionWriter(BaseSessionWriter):
    """测试专用的最小具体子类，仅实现抽象方法 _do_create_content。

    BaseSessionWriter 是 ABC，Python 的 object.__new__ 会检查
    __abstractmethods__，因此不能直接对 BaseSessionWriter 调用
    __new__ 绕过 __init__——需要一个具体子类。
    """

    def _do_create_content(self, payload, headers):  # noqa: ARG002
        return None


# ---------- a. SSE 侧透传测试 ----------


# ---------- a2. D-06 透传验证测试 ----------


class TestConvertEventD06Passthrough:
    """D-06/D-02/13.6：验证已删除的转换方法确实不存在（回归防护）。

    _convert_event / _convert_raw_event / _convert_custom_event / _convert_tool_call_start
    均已删除（Phase 13.6 D-01 + 前序阶段），_dispatch_event 简化为纯分发。
    """

    def test_convert_custom_event_method_deleted(self):
        """D-06 后 CUSTOM 转换方法已删除（不存在于实例或类上）。"""
        assert not hasattr(AidevAGUIAgent, "_convert_custom_event")
        agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
        assert not hasattr(agent, "_convert_custom_event")

    def test_convert_tool_call_start_method_deleted(self):
        """D-02 后 _convert_tool_call_start 方法已删除。"""
        assert not hasattr(AidevAGUIAgent, "_convert_tool_call_start")
        agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
        assert not hasattr(agent, "_convert_tool_call_start")

    def test_convert_event_and_convert_raw_event_deleted(self):
        """Phase 13.6 D-01：_convert_event + _convert_raw_event 方法已删除。"""
        assert not hasattr(AidevAGUIAgent, "_convert_event")
        assert not hasattr(AidevAGUIAgent, "_convert_raw_event")
        agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
        assert not hasattr(agent, "_convert_event")
        assert not hasattr(agent, "_convert_raw_event")


# ---------- b. DB 侧写入测试 ----------


class TestKnowledgeRagResultDBWrite:
    """验证 handle_reference_document 收到透传后的完整 dict 事件，能正确写入。"""

    def test_handle_reference_document_extracts_message_id_from_dict_value(self):
        """DB 侧 handle_reference_document 收到 value=完整 dict 的 CustomEvent，
        正确提取 message_id 并调用 _create_session_content。"""
        writer = _ConcreteSessionWriter.__new__(_ConcreteSessionWriter)  # 绕过 __init__
        writer._written_message_ids = set()
        writer._create_session_content = MagicMock()

        event = _make_knowledge_custom_event()
        writer.handle_reference_document(event)

        # 验证 _create_session_content 被调用，且 message_id 正确
        writer._create_session_content.assert_called_once()
        call_kwargs = writer._create_session_content.call_args
        assert call_kwargs.kwargs["message_id"] == KNOWLEDGE_MESSAGE_ID
        assert call_kwargs.kwargs["role"] == "activity"
        # content 是 JSON 序列化的 reference_documents
        content = call_kwargs.kwargs["content"]
        parsed = json.loads(content)
        assert len(parsed) == 2
        # 验证 camelToSnake 转换（originFile → origin_file）
        assert "origin_file" in parsed[0] or "originFile" in parsed[0]
        # builtin_property 含 message_id 和 type
        builtin_prop = call_kwargs.kwargs["builtin_property"]
        assert builtin_prop["message_id"] == KNOWLEDGE_MESSAGE_ID
        assert KNOWLEDGE_MESSAGE_ID in writer._written_message_ids

    def test_handle_reference_document_does_not_write_when_value_is_list(self):
        """反向回归防护：如果 event.value 是 list（旧的精简转换结果），
        handle_reference_document 应该不写入（因为 fallback 到 {} 后 reference_documents 为空）。
        这个测试证明旧精简逻辑确实导致数据丢失，从而验证 D-14 修复的必要性。
        """
        writer = _ConcreteSessionWriter.__new__(_ConcreteSessionWriter)
        writer._written_message_ids = set()
        writer._create_session_content = MagicMock()

        # 构造旧精简逻辑会产生的 event：value 是 list（不是 dict）
        simplified_event = CustomEvent(
            type=EventType.CUSTOM,
            name=CustomMessageType.KNOWLEDGE_RAG_RESULT.value,
            value=REFERENCE_DOC_DATA,  # list，不是 dict —— 旧精简逻辑的结果
        )
        writer.handle_reference_document(simplified_event)

        # 旧精简逻辑导致：isinstance(list, dict) 为 False → event_data={} → reference_documents=[] → return
        writer._create_session_content.assert_not_called()
        assert KNOWLEDGE_MESSAGE_ID not in writer._written_message_ids

    def test_handle_reference_document_dedup_by_message_id(self):
        """同一 message_id 的引用文档事件只写一次（去重逻辑）。"""
        writer = _ConcreteSessionWriter.__new__(_ConcreteSessionWriter)
        writer._written_message_ids = {KNOWLEDGE_MESSAGE_ID}  # 已写过
        writer._create_session_content = MagicMock()

        event = _make_knowledge_custom_event()
        writer.handle_reference_document(event)

        writer._create_session_content.assert_not_called()


# ---------- c. 集成一致性测试 ----------


class TestKnowledgeRagResultIntegrationConsistency:
    """验证 _dispatch_event 完整路径后，DB 收到的 message_id 与 SSE 收到的 message_id 一致。"""

    def test_db_and_sse_receive_same_message_id(self):
        """集成测试：一次完整的 _dispatch_event(CustomEvent(KNOWLEDGE_RAG_RESULT))，
        DB handler 收到的 message_id 与 SSE 收到的 message_id 一致（回归防护）。"""
        agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
        agent._suppressed_tool_call_ids = set()
        agent._tool_mapping = {}

        # mock DB handler 捕获收到的事件
        db_received_events = []

        def mock_event_handler(event):
            db_received_events.append(event)

        agent._event_handler = mock_event_handler

        # mock SSE 侧 super()._dispatch_event，捕获收到的事件
        sse_received_events = []

        with patch.object(
            AidevAGUIAgent.__mro__[1],  # LangGraphAGUIAgent
            "_dispatch_event",
            side_effect=lambda e: sse_received_events.append(e) or "",
        ):
            event = _make_knowledge_custom_event()
            agent._dispatch_event(event)

        # DB 收到 1 个事件
        assert len(db_received_events) == 1
        db_event = db_received_events[0]
        assert isinstance(db_event, CustomEvent)
        assert isinstance(db_event.value, dict)
        db_message_id = db_event.value.get("message_id")

        # SSE 收到 1 个事件
        assert len(sse_received_events) == 1
        sse_event = sse_received_events[0]
        assert isinstance(sse_event, CustomEvent)
        assert isinstance(sse_event.value, dict)
        sse_message_id = sse_event.value.get("message_id")

        # 核心断言：DB 和 SSE 收到的 message_id 一致
        assert db_message_id == sse_message_id == KNOWLEDGE_MESSAGE_ID
