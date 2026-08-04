# -*- coding: utf-8 -*-
"""AGUISessionWriter 的 ask_user_question 三个事件 handler 与三个私有 DB 方法单测。

使用 e2e 测试的 ``_MockBKAidevClient`` 有状态内存 DB 模式（Q2 模式 A），
宿主为真实 ``AGUISessionWriter``，覆盖跳过/答题/user 落库三条路径及 D-16/D-17/D-19 关键行为。
"""

import json
from unittest.mock import patch

from ag_ui.core import CustomEvent, EventType
from aidev_agent.core.ag_ui.ask_user_question import (
    ASK_USER_QUESTION_REASON,
    ASK_USER_QUESTION_SKIPPED_CONTENT,
    AskUserQuestionOutcomeBuilder,
    InterruptStatus,
    build_skipped_answers,
)
from aidev_agent.core.ag_ui.events import ExtendToolCallResultEvent
from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.enums import PromptRole
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter


class _MockBKAidevClient:
    """模拟 BKAidev API client，追踪 DB 读写。"""

    def __init__(self):
        self.api = _MockApi(self)


class _MockApi:
    def __init__(self, client):
        self.client = client
        self._contents: list[dict] = []
        self._next_id = 1

    def create_chat_session_content(self, json, headers):
        content_id = self._next_id
        self._next_id += 1
        record = {
            "id": content_id,
            "role": json.get("role"),
            "content": json.get("content"),
            "status": json.get("status"),
            "property": json.get("property", {}),
        }
        self._contents.append(record)
        return {"data": {"id": content_id}}

    def update_chat_session_content(self, path_params, json, headers):
        content_id = path_params["id"]
        for rec in self._contents:
            if rec["id"] == content_id:
                if "content" in json:
                    rec["content"] = json["content"]
                if "status" in json:
                    rec["status"] = json["status"]
                if "property" in json:
                    rec["property"] = json["property"]
                break
        return {"data": {"id": content_id}}

    def get_chat_session_contents(self, params, headers):
        # 模拟生产环境：API 返回的 property 不含 builtin_property
        stripped = []
        for rec in self._contents:
            rec_copy = dict(rec)
            prop = rec_copy.get("property") or {}
            if isinstance(prop, dict):
                stripped_prop = {k: v for k, v in prop.items() if k != "builtin_property"}
                rec_copy["property"] = stripped_prop
            stripped.append(rec_copy)
        return {"data": stripped}

    def update_chat_session(self, path_params, json, headers):
        return {"data": {}}

    def retrieve_chat_session(self, path_params, headers):
        return {"data": {"session_property": {}}}


def _pending_interrupt_record(content_id: int = 1, tool_call_id: str = "call_auq_001") -> dict:
    """构造一条 pending 的 ask_user_question interrupt 记录。"""
    return {
        "id": content_id,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": json.dumps(
            {
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [
                        {
                            "id": "int-question-001",
                            "reason": ASK_USER_QUESTION_REASON,
                            "toolCallId": tool_call_id,
                            "metadata": {
                                "questions": [
                                    {"question": "确认继续？", "multiSelect": False},
                                ]
                            },
                        }
                    ],
                }
            }
        ),
        "property": {"turn_id": "t1"},
    }


class TestAGUISessionWriterAskUserQuestionHandlers:
    """AGUISessionWriter 的 ask_user_question 三个 handler 与私有 DB 方法。"""

    def _make_writer(self, contents=None) -> AGUISessionWriter:
        mock_client = _MockBKAidevClient()
        if contents:
            mock_client.api._contents = contents
        return AGUISessionWriter(session_code="test-auq-1", client=mock_client, username="test", tools=[])

    def _event(self, name, value):
        return CustomEvent(type=EventType.CUSTOM, name=name, value=value)

    def _skipped_event_value(self, record: dict) -> dict:
        """构造与 chat.py `_handle_skip_path` 一致的富化跳过 finalize 事件 value。

        chat.py 已调 ``upgrade_content_to_success`` 把 content 升级为终态 dict 后透传，
        本 helper 同样预升级（模拟 chat.py 行为）。跳过路径的 tool 记录由 chat.py 单独派发
        TOOL_CALL_RESULT 事件（handle_tool_call_result）写入，不在本 value 内。
        """
        parsed = json.loads(record["content"])
        interrupts = (parsed.get("outcome") or {}).get("interrupts") or []
        first = interrupts[0] if interrupts and isinstance(interrupts[0], dict) else {}
        metadata = first.get("metadata") or {}
        skipped_answers = build_skipped_answers(metadata.get("questions") or [])
        upgraded = AskUserQuestionOutcomeBuilder.upgrade_content_to_success(
            record["content"], InterruptStatus.CANCELLED.value, resume_answers=skipped_answers
        )
        bp = record.get("builtin_property") or {}
        return {
            "turn_id": (record.get("property") or {}).get("turn_id") or "",
            "status": InterruptStatus.CANCELLED.value,
            "content_id": record["id"],
            "content": upgraded,
            "answers": skipped_answers,
            "builtin_property": bp,
        }

    def _resolved_event_value(self, record: dict, answers: list) -> dict:
        """构造与 chat.py `_handle_answer_path` 一致的富化答题事件 value。

        chat.py 已调 ``upgrade_content_to_success`` 把 content 升级为终态 dict 后透传，
        本 helper 同样预升级（模拟 chat.py 行为）。
        """
        upgraded = AskUserQuestionOutcomeBuilder.upgrade_content_to_success(
            record["content"], InterruptStatus.RESOLVED.value, resume_answers=answers
        )
        bp = record.get("builtin_property") or {}
        return {
            "turn_id": (record.get("property") or {}).get("turn_id") or "",
            "answers": answers,
            "status": InterruptStatus.RESOLVED.value,
            "content_id": record["id"],
            "content": upgraded,
            "builtin_property": bp,
        }

    def test_dispatch_routes_to_skipped_handler(self):
        writer = self._make_writer()
        with patch.object(writer, "handle_ask_user_question_finalize") as h:
            writer._dispatch_custom_event_direct(
                self._event(SessionPersistenceEventNames.AskUserQuestionFinalized.value, {})
            )
            h.assert_called_once()

    def test_dispatch_routes_to_resolved_handler(self):
        writer = self._make_writer()
        with patch.object(writer, "handle_ask_user_question_finalize") as h:
            writer._dispatch_custom_event_direct(
                self._event(SessionPersistenceEventNames.AskUserQuestionFinalized.value, {})
            )
            h.assert_called_once()

    def test_dispatch_routes_to_user_input_handler(self):
        writer = self._make_writer()
        with patch.object(writer, "handle_user_input_saved") as h:
            writer._dispatch_custom_event_direct(self._event(SessionPersistenceEventNames.UserInputSaved.value, {}))
            h.assert_called_once()

    def test_handle_user_input_saved_creates_user_record(self):
        writer = self._make_writer()
        with patch.object(writer, "_do_create_content") as create:
            writer.handle_user_input_saved(self._event("user_input_saved", {"content": "你好", "turn_id": "t1"}))
            payload = create.call_args.kwargs["payload"]
            assert payload["role"] == PromptRole.USER.value
            assert payload["status"] == "success"
            assert payload["property"] == {"turn_id": "t1"}
            assert "builtin_property" not in payload["property"]

    def test_handle_user_input_saved_propagates_exception(self):
        writer = self._make_writer()
        with patch.object(writer, "_do_create_content", side_effect=RuntimeError("boom")):
            writer.handle_user_input_saved(self._event("user_input_saved", {"content": "hi", "turn_id": "t1"}))

    def test_handle_finalize_cancelled_finalizes_to_cancelled(self):
        writer = self._make_writer(contents=[_pending_interrupt_record()])
        value = self._skipped_event_value(_pending_interrupt_record())
        writer.handle_ask_user_question_finalize(
            self._event(SessionPersistenceEventNames.AskUserQuestionFinalized.value, value)
        )
        # finalize handler 仅终态 interrupt，不写 tool 记录（tool 由 chat.py 派发 TOOL_CALL_RESULT 单独写入）
        tool_records = [r for r in writer.client.api._contents if r["role"] == PromptRole.TOOL.value]
        assert not tool_records
        interrupt_after = [r for r in writer.client.api._contents if r["role"] == PromptRole.INTERRUPT.value]
        builtin = (interrupt_after[0].get("property") or {}).get("builtin_property") or {}
        assert builtin["status"] == "cancelled"

    def test_handle_tool_call_result_writes_skipped_tool(self):
        writer = self._make_writer(contents=[_pending_interrupt_record()])
        writer.handle_tool_call_result(
            ExtendToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                tool_call_id="call_auq_001",
                message_id="call_auq_001",
                content=ASK_USER_QUESTION_SKIPPED_CONTENT,
                role="tool",
                duration=None,
                is_error=False,
                additional_metadata={},
                skip_db=False,
            )
        )
        tool_records = [r for r in writer.client.api._contents if r["role"] == PromptRole.TOOL.value]
        assert tool_records
        assert tool_records[0]["content"] == ASK_USER_QUESTION_SKIPPED_CONTENT
        tool_builtin = (tool_records[0].get("property") or {}).get("builtin_property") or {}
        assert tool_builtin["tool_call_id"] == "call_auq_001"

    def test_handle_skipped_finalize_failure_does_not_rollback(self):
        writer = self._make_writer(contents=[_pending_interrupt_record()])
        value = self._skipped_event_value(_pending_interrupt_record())
        with patch.object(writer, "_do_update_content", side_effect=RuntimeError("boom")):
            writer.handle_ask_user_question_finalize(
                self._event(SessionPersistenceEventNames.AskUserQuestionFinalized.value, value)
            )
        # finalize 失败只 log 不回滚（无 tool 记录，interrupt 仍 pending）
        tool_records = [r for r in writer.client.api._contents if r["role"] == PromptRole.TOOL.value]
        assert not tool_records

    def test_handle_resolved_finalizes_to_resolved(self):
        writer = self._make_writer(contents=[_pending_interrupt_record()])
        value = self._resolved_event_value(_pending_interrupt_record(), answers=[{"a": 1}])
        writer.handle_ask_user_question_finalize(
            self._event(SessionPersistenceEventNames.AskUserQuestionFinalized.value, value)
        )
        interrupt_after = [r for r in writer.client.api._contents if r["role"] == PromptRole.INTERRUPT.value]
        builtin = (interrupt_after[0].get("property") or {}).get("builtin_property") or {}
        assert builtin["status"] == "resolved"

    def test_handle_resolved_missing_content_id_does_not_finalize(self):
        writer = self._make_writer(contents=[_pending_interrupt_record()])
        writer.handle_ask_user_question_finalize(
            self._event(
                SessionPersistenceEventNames.AskUserQuestionFinalized.value,
                {
                    "turn_id": "t1",
                    "answers": [{"a": 1}],
                    "status": InterruptStatus.RESOLVED.value,
                },
            )
        )
        interrupt_after = [r for r in writer.client.api._contents if r["role"] == PromptRole.INTERRUPT.value]
        builtin = (interrupt_after[0].get("property") or {}).get("builtin_property") or {}
        assert builtin.get("status") != "resolved"

    def test_handle_finalize_missing_upgraded_content_does_not_finalize(self):
        """事件有 content_id 但缺终态 content（chat.py upgrade 失败未派发，防御性 case）→ 不写 DB。"""
        writer = self._make_writer(contents=[_pending_interrupt_record()])
        writer.handle_ask_user_question_finalize(
            self._event(
                SessionPersistenceEventNames.AskUserQuestionFinalized.value,
                {
                    "turn_id": "t1",
                    "content_id": 1,
                    "answers": [],
                    "status": InterruptStatus.CANCELLED.value,
                },
            )
        )
        interrupt_after = [r for r in writer.client.api._contents if r["role"] == PromptRole.INTERRUPT.value]
        builtin = (interrupt_after[0].get("property") or {}).get("builtin_property") or {}
        assert builtin.get("status") != "cancelled"
