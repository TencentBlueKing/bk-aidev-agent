# -*- coding: utf-8 -*-
"""AGUISessionWriter 的 ask_user_question 三个事件 handler 与三个私有 DB 方法单测。

使用 e2e 测试的 ``_MockBKAidevClient`` 有状态内存 DB 模式（Q2 模式 A），
宿主为真实 ``AGUISessionWriter``，覆盖跳过/答题/user 落库三条路径及 D-16/D-17/D-19 关键行为。
"""

import json
from unittest.mock import patch

from ag_ui.core import CustomEvent, EventType, RunFinishedEvent
from aidev_agent.core.ag_ui.events import ExtendToolCallResultEvent
from aidev_agent.core.ag_ui.types import RunFinishedOutcomeType, SessionPersistenceEventNames
from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_REASON,
    ASK_USER_QUESTION_SKIPPED_CONTENT,
    TOOL_APPROVAL_REASON,
    AskUserQuestionOutcomeBuilder,
    InterruptStatus,
    build_skipped_answers,
    register_side_effect,
)
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


def _run_finished_event(interrupts: list[dict], thread_id: str = "t1") -> RunFinishedEvent:
    """构造 RUN_FINISHED（interrupt）事件，outcome 含 interrupts（dict 形态）。"""
    return RunFinishedEvent(
        type=EventType.RUN_FINISHED,
        thread_id=thread_id,
        run_id="run-1",
        outcome={"type": RunFinishedOutcomeType.INTERRUPT.value, "interrupts": interrupts},
    )


class TestAGUISessionWriterWorkerStartupTableized:
    """D-10 查表化：worker 启动经 side_effects 注册表（全量语义，非只看 first_reason）。"""

    def _make_writer(self) -> AGUISessionWriter:
        mock_client = _MockBKAidevClient()
        return AGUISessionWriter(session_code="test-auq-2", client=mock_client, username="test", tools=[])

    def test_worker_factory_called_for_registered_reason(self):
        """注册了 side_effect 的 reason → worker factory 被调用并启动（全量语义）。"""
        writer = self._make_writer()
        calls: list[tuple] = []

        def _factory(session_code, username, graph_thread_id, interrupts):
            calls.append((session_code, username, graph_thread_id, interrupts))

            def _start():
                calls.append(("STARTED", session_code))

            return _start

        # 临时注册 + 清理
        register_side_effect("aidev:test_approval_worker", _factory)
        try:
            event = _run_finished_event(
                [
                    {"id": "int-approval-2", "reason": "aidev:test_approval_worker", "toolCallId": "call_2"},
                    {"id": "int-other", "reason": "aidev:some_other", "toolCallId": "call_3"},
                ]
            )
            writer.handle_run_finished(event)
        finally:
            # 恢复注册表（删除测试 key）
            from aidev_agent.packages.interrupt_manager import side_effects

            side_effects._SIDE_EFFECTS.pop("aidev:test_approval_worker", None)

        # 全量语义：命中注册表的 reason 都启动 worker（非只看 first_reason）
        assert any(c[0] == "STARTED" for c in calls)
        # 未命中注册表的 reason（aidev:some_other）不启动额外 worker
        assert calls.count(("STARTED", "test-auq-2")) == 1

    def test_no_factory_for_unregistered_reason_skips_worker(self):
        """未注册 side_effect 的 reason（ask_user）→ 不启动 worker。"""
        writer = self._make_writer()
        calls: list = []

        def _factory(session_code, username, graph_thread_id, interrupts):
            calls.append(session_code)
            return lambda: None

        register_side_effect("aidev:test_ask_skip", _factory)
        try:
            event = _run_finished_event(
                [{"id": "int-auq-1", "reason": ASK_USER_QUESTION_REASON, "toolCallId": "call_auq"}]
            )
            writer.handle_run_finished(event)
        finally:
            from aidev_agent.packages.interrupt_manager import side_effects

            side_effects._SIDE_EFFECTS.pop("aidev:test_ask_skip", None)
        # ask_user 未注册 → 不调用任何 factory
        assert calls == []

    def test_handle_run_finished_persists_single_active_interrupt_to_db(self):
        """串行语义（用户裁定 2026-08-31）：多中断 RUN_FINISHED → DB 只写第一个活跃 interrupt。

        写入侧 base.py handle_run_finished 取 ``interrupts[:1]``，只对首个活跃 approval
        interrupt 调 ``_upsert_interrupt_session_content`` → 落库 **1** 条 role=interrupt
        记录（DB 一次只写一个 interrupt message）；下一个 interrupt 在成为活跃时（分支 B
        _build_next_interrupt_events 路径）才写入。
        """
        writer = self._make_writer()
        event = _run_finished_event(
            [
                {
                    "id": "int-approval-multi-1",
                    "reason": TOOL_APPROVAL_REASON,
                    "toolCallId": "call_multi_1",
                    "metadata": {"type": "tool_approval", "toolName": "A"},
                },
                {
                    "id": "int-approval-multi-2",
                    "reason": TOOL_APPROVAL_REASON,
                    "toolCallId": "call_multi_2",
                    "metadata": {"type": "tool_approval", "toolName": "B"},
                },
            ]
        )
        writer.handle_run_finished(event)

        interrupt_after = [r for r in writer.client.api._contents if r["role"] == PromptRole.INTERRUPT.value]
        assert len(interrupt_after) == 1, (
            "串行语义：DB 只写第一个活跃 interrupt（一次只写一个 message），多中断流结束时仅首个 pending 落库"
        )
        written_interrupt_ids = {
            ((rec.get("property") or {}).get("builtin_property") or {}).get("interrupt_id")
            or ((rec.get("property") or {}).get("builtin_property") or {}).get("message_id")
            for rec in interrupt_after
        }
        assert written_interrupt_ids == {"int-approval-multi-1"}, (
            "仅第一个活跃 pending interrupt（int-approval-multi-1）落库，int-approval-multi-2 留待成为活跃时写入"
        )

    def test_handle_run_finished_extract_routes_to_ask_user_builtin_property(self):
        """Gap 2 回归：ask_user 中断卡 builtin_property 含 questions（非 4 键兜底）。

        修复前 _INTERRUPT_EXTRACTORS 键用 str()（枚举名）恒 miss → 走兜底 4 键
        （message_id/interrupt_id/graph_thread_id/tool_call_id），questions/options/multiSelect
        丢失，skip 路径连坐空 skipped_answers。修复后 .value 键使 serialized_reason
        （值字符串）命中模块级 extract 纯函数全量提取。
        """
        writer = self._make_writer()
        event = _run_finished_event(
            [
                {
                    "id": "int-auq-1",
                    "reason": ASK_USER_QUESTION_REASON,
                    "toolCallId": "call_auq",
                    "questions": [{"question": "确认继续？", "multiSelect": False}],
                    "options": ["是", "否"],
                    "multiSelect": False,
                }
            ]
        )
        writer.handle_run_finished(event)

        interrupt_after = [r for r in writer.client.api._contents if r["role"] == PromptRole.INTERRUPT.value]
        assert len(interrupt_after) == 1
        builtin = (interrupt_after[0].get("property") or {}).get("builtin_property") or {}
        assert builtin.get("questions"), "ask_user 卡 builtin_property 必须含 questions（路由命中）"
        assert "options" in builtin, "ask_user 卡 builtin_property 必须含 options（路由命中）"
        assert "multiSelect" in builtin, "ask_user 卡 builtin_property 必须含 multiSelect（路由命中）"


class TestAGUISessionWriterDeferredResumeBackfill:
    """D-12 续流回填：_fetch_tool_call_reconstruction 从 DB 重建 assistant.tool_calls。"""

    def test_reconstruct_appends_approval_tool_call_to_latest_assistant(self):
        writer = _TestWriterHelper.make_writer()
        # 预置：一条 assistant 记录 + 一条 interrupt 记录（含 toolArgs）
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "需要审批执行",
            "status": "complete",
            "property": {"builtin_property": {"message_id": "assist-1", "tool_calls": []}},
        }
        interrupt_rec = {
            "id": 11,
            "role": PromptRole.INTERRUPT.value,
            "status": "pending",
            "content": json.dumps(
                {
                    "outcome": {
                        "type": "interrupt",
                        "interrupts": [
                            {
                                "id": "int-approval-1",
                                "reason": TOOL_APPROVAL_REASON,
                                "toolCallId": "call_approval_001",
                                "metadata": {"toolArgs": {"q": 1}},
                            }
                        ],
                    }
                }
            ),
            "property": {"builtin_property": {"tool_call_id": "call_approval_001"}},
        }
        writer.client.api._contents = [assistant_rec, interrupt_rec]

        result = writer._fetch_tool_call_reconstruction("call_approval_001", "approval_tool")
        assert result is not None
        content_id, merged_property = result
        assert content_id == 10
        # D-07：merged_property 为完整 builtin_property dict（展开保留既有键 + tool_calls），
        # 不再只返回 tool_calls list。注：get_chat_session_contents 模拟生产剥离 builtin_property，
        # 故此处 assistant_builtin 为空，message_id 无法经此读源恢复（生产同样如此）。
        assert isinstance(merged_property, dict)
        merged = merged_property["tool_calls"]
        # 重建 tool_call（OpenAI 嵌套形态），含 id/type/name/arguments
        assert any(tc["id"] == "call_approval_001" for tc in merged)
        tc = next(tc for tc in merged if tc["id"] == "call_approval_001")
        # D-07：补 type 键对齐 immediate 形态
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "approval_tool"
        assert json.loads(tc["function"]["arguments"]) == {"q": 1}

    def test_reconstruct_no_matching_interrupt_uses_empty_args(self):
        """无匹配 interrupt 记录 → toolArgs 为空 dict，仍重建 tool_call（name/arguments 兜底）。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "已回填",
            "status": "complete",
            "property": {"builtin_property": {"message_id": "assist-1", "tool_calls": []}},
        }
        writer.client.api._contents = [assistant_rec]
        result = writer._fetch_tool_call_reconstruction("call_unknown", "some_tool")
        assert result is not None
        _, merged_property = result
        tc = next(tc for tc in merged_property["tool_calls"] if tc["id"] == "call_unknown")
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "some_tool"
        assert tc["function"]["arguments"] == "{}"

    def test_reconstruct_no_assistant_returns_none(self):
        """无 assistant 记录 → 返回 None（基类 no-op）。"""
        writer = _TestWriterHelper.make_writer()
        writer.client.api._contents = [
            {
                "id": 11,
                "role": PromptRole.INTERRUPT.value,
                "status": "pending",
                "content": json.dumps(
                    {
                        "outcome": {
                            "type": "interrupt",
                            "interrupts": [{"id": "i1", "reason": TOOL_APPROVAL_REASON, "toolCallId": "call_x"}],
                        }
                    }
                ),
                "property": {},
            }
        ]
        assert writer._fetch_tool_call_reconstruction("call_x", "t") is None

    def test_reconstruct_name_recovery_never_falls_back_to_tool_call_id(self):
        """D-06（根因 A）：任何 name 源取不到时 name=""，绝不回退到 tool_call_id。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "已回填",
            "status": "complete",
            "property": {"builtin_property": {"message_id": "assist-1", "tool_calls": []}},
        }
        # 无 interrupt 记录、无 tool_name、_tools_mapping 也无命中
        writer.client.api._contents = [assistant_rec]
        result = writer._fetch_tool_call_reconstruction("call_no_name", None)
        assert result is not None
        _, merged_property = result
        tc = next(tc for tc in merged_property["tool_calls"] if tc["id"] == "call_no_name")
        assert tc["function"]["name"] == ""
        assert tc["function"]["name"] != "call_no_name"

    def test_reconstruct_name_recovery_from_interrupt_metadata_tool_name(self):
        """D-06（根因 A）：tool_name 缺失时兜底 interrupt 卡片 metadata.toolName。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "需审批",
            "status": "complete",
            "property": {"builtin_property": {"message_id": "assist-1", "tool_calls": []}},
        }
        interrupt_rec = {
            "id": 11,
            "role": PromptRole.INTERRUPT.value,
            "status": "pending",
            "content": json.dumps(
                {
                    "outcome": {
                        "type": "interrupt",
                        "interrupts": [
                            {
                                "id": "int-approval-n",
                                "reason": TOOL_APPROVAL_REASON,
                                "toolCallId": "call_approval_n",
                                "metadata": {"toolArgs": {"q": 1}, "toolName": "metadata_resolved_tool"},
                            }
                        ],
                    }
                }
            ),
            "property": {"builtin_property": {"tool_call_id": "call_approval_n"}},
        }
        writer.client.api._contents = [assistant_rec, interrupt_rec]
        result = writer._fetch_tool_call_reconstruction("call_approval_n", None)
        assert result is not None
        _, merged_property = result
        tc = next(tc for tc in merged_property["tool_calls"] if tc["id"] == "call_approval_n")
        assert tc["function"]["name"] == "metadata_resolved_tool"
        assert tc["function"]["name"] != "call_approval_n"

    def test_reconstruct_name_primary_source_is_event_tool_name(self):
        """D-06（根因 A）：主源事件 tool_name（真实工具名）优先于 interrupt 卡片 toolName。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "需审批",
            "status": "complete",
            "property": {"builtin_property": {"message_id": "assist-1", "tool_calls": []}},
        }
        interrupt_rec = {
            "id": 11,
            "role": PromptRole.INTERRUPT.value,
            "status": "pending",
            "content": json.dumps(
                {
                    "outcome": {
                        "type": "interrupt",
                        "interrupts": [
                            {
                                "id": "int-approval-p",
                                "reason": TOOL_APPROVAL_REASON,
                                "toolCallId": "call_approval_p",
                                "metadata": {"toolArgs": {"q": 1}, "toolName": "metadata_fallback"},
                            }
                        ],
                    }
                }
            ),
            "property": {"builtin_property": {"tool_call_id": "call_approval_p"}},
        }
        writer.client.api._contents = [assistant_rec, interrupt_rec]
        result = writer._fetch_tool_call_reconstruction("call_approval_p", "primary_tool")
        assert result is not None
        _, merged_property = result
        tc = next(tc for tc in merged_property["tool_calls"] if tc["id"] == "call_approval_p")
        assert tc["function"]["name"] == "primary_tool"

    def test_reconstruct_preserves_existing_builtin_keys_when_read_has_them(self):
        """D-07（根因 E）：merged_property 用 ``{**assistant_builtin, "tool_calls": ...}``
        展开保留既有键（message_id 等）。生产 get_chat_session_contents 剥离 builtin_property，
        但若读源返回既有键，必须保留，不再只回写 tool_calls 覆盖式丢失 message_id。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "需审批",
            "status": "complete",
            "property": {
                # 直接 patch get_chat_session_contents 返回含 builtin_property 的记录
                "builtin_property": {"message_id": "assist-keep", "tool_calls": []}
            },
        }
        interrupt_rec = {
            "id": 11,
            "role": PromptRole.INTERRUPT.value,
            "status": "pending",
            "content": json.dumps(
                {
                    "outcome": {
                        "type": "interrupt",
                        "interrupts": [
                            {
                                "id": "int-approval-k",
                                "reason": TOOL_APPROVAL_REASON,
                                "toolCallId": "call_approval_k",
                                "metadata": {"toolArgs": {"q": 1}},
                            }
                        ],
                    }
                }
            ),
            "property": {"builtin_property": {"tool_call_id": "call_approval_k"}},
        }
        with patch.object(
            writer.client.api, "get_chat_session_contents", return_value={"data": [assistant_rec, interrupt_rec]}
        ):
            result = writer._fetch_tool_call_reconstruction("call_approval_k", "keep_tool")
        assert result is not None
        _, merged_property = result
        # D-07：保留既有键 message_id
        assert merged_property["message_id"] == "assist-keep"
        tc = next(tc for tc in merged_property["tool_calls"] if tc["id"] == "call_approval_k")
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "keep_tool"

    def test_reconstruct_reads_top_level_tool_calls_when_builtin_property_stripped(self):
        """生产形态回归：get_chat_session_contents 返回的 property 不含 builtin_property，
        tool_calls 为记录顶层账本字段。existing_tool_calls 必须回退读顶层，否则恒为空——
        幂等检查失效且既有 tool_calls（如 LLM 已发起的 weather-query）在 merged_property 中丢失。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 51717312,
            "role": PromptRole.ASSISTANT.value,
            "content": "我是智能体助手。",
            "status": "complete",
            # 生产记录形状：property 无 builtin_property，tool_calls 在顶层
            "property": {"turn_id": "", "extra": None, "flow_info": None, "artifacts": None},
            "tool_calls": [
                {
                    "id": "chatcmpl-tool-ab3ec6d061678296",
                    "type": "function",
                    "function": {"name": "weather-query", "arguments": '{"query__place": "天津"}'},
                }
            ],
        }
        interrupt_rec = {
            "id": 51717313,
            "role": PromptRole.INTERRUPT.value,
            "status": "pending",
            "content": json.dumps(
                {
                    "outcome": {
                        "type": "interrupt",
                        "interrupts": [
                            {
                                "id": "int-approval-top",
                                "reason": TOOL_APPROVAL_REASON,
                                "toolCallId": "call_top_level",
                                "metadata": {"toolArgs": {"q": 1}},
                            }
                        ],
                    }
                }
            ),
            "property": {},
        }
        writer.client.api._contents = [assistant_rec, interrupt_rec]

        result = writer._fetch_tool_call_reconstruction("call_top_level", "approval_tool")
        assert result is not None
        content_id, merged_property = result
        assert content_id == 51717312
        merged = merged_property["tool_calls"]
        # 既有顶层 tool_calls 保留（不丢 LLM 已发起的调用）
        assert any(tc["id"] == "chatcmpl-tool-ab3ec6d061678296" for tc in merged)
        # 审批 tool_call 追加
        tc = next(tc for tc in merged if tc["id"] == "call_top_level")
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "approval_tool"

    def test_reconstruct_idempotent_against_top_level_tool_calls(self):
        """幂等检查覆盖顶层 tool_calls：已含匹配 tool_call_id（顶层形态）时不再重复追加。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "已回填",
            "status": "complete",
            "property": {},
            "tool_calls": [
                {"id": "call_dup", "type": "function", "function": {"name": "some_tool", "arguments": "{}"}}
            ],
        }
        writer.client.api._contents = [assistant_rec]
        assert writer._fetch_tool_call_reconstruction("call_dup", "some_tool") is None

    def test_fallback_override_writes_back_reconstruction(self):
        """子类覆写 _flush_deferred_tool_call_fallback：从 DB 重建并回写 assistant 记录。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 10,
            "role": PromptRole.ASSISTANT.value,
            "content": "需审批",
            "status": "complete",
            "property": {},
            "tool_calls": [],
        }
        interrupt_rec = {
            "id": 11,
            "role": PromptRole.INTERRUPT.value,
            "status": "pending",
            "content": json.dumps(
                {
                    "outcome": {
                        "type": "interrupt",
                        "interrupts": [
                            {
                                "id": "int-fb-1",
                                "reason": TOOL_APPROVAL_REASON,
                                "toolCallId": "call_fb_001",
                                "metadata": {"toolArgs": {"q": 1}},
                            }
                        ],
                    }
                }
            ),
            "property": {},
        }
        writer.client.api._contents = [assistant_rec, interrupt_rec]

        writer._flush_deferred_tool_call_fallback("call_fb_001", "approval_tool")
        updated = writer.client.api._contents[0]
        merged = updated["property"]["builtin_property"]["tool_calls"]
        assert any(tc["id"] == "call_fb_001" for tc in merged)
        tc = next(tc for tc in merged if tc["id"] == "call_fb_001")
        assert tc["function"]["name"] == "approval_tool"
        assert json.loads(tc["function"]["arguments"]) == {"q": 1}

    def test_fallback_no_hit_is_noop(self):
        """无 DB 命中时 fallback 静默跳过（不抛错、不写库）。"""
        writer = _TestWriterHelper.make_writer()
        writer.client.api._contents = []
        writer._flush_deferred_tool_call_fallback("call_none", "t")  # 不抛错即通过
        assert writer.client.api._contents == []


class TestAskUserQuestionBackfillReconstruction:
    """D-15 ask_user 续流回填：_fetch_tool_call_reconstruction 从 DB 重建 ask_user tool_call（含 questions）。"""

    def _ask_user_interrupt_record(
        self,
        content_id: int = 21,
        tool_call_id: str = "call_auq_001",
        interrupt_id: str = "int-question-001",
    ) -> dict:
        """构造一条含 metadata.toolArgs={questions} 的 ask_user interrupt 记录（D-15 prepare enrich 落库形态）。"""
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
                                "id": interrupt_id,
                                "reason": ASK_USER_QUESTION_REASON,
                                "toolCallId": tool_call_id,
                                "metadata": {
                                    "type": "ask_user_question",
                                    "status": "pending",
                                    "questions": [{"question": "确认继续？", "multiSelect": False}],
                                    # D-15：prepare enrich 落库的 toolArgs（questions 参数）
                                    "toolArgs": {"questions": [{"question": "确认继续？", "multiSelect": False}]},
                                },
                            }
                        ],
                    }
                }
            ),
            "property": {"builtin_property": {"tool_call_id": tool_call_id}},
        }

    def test_reconstruct_ask_user_backfills_questions_tool_call(self):
        """ask_user 中断 → 回填 tool_call，arguments 还原为 questions JSON（D-15）。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 20,
            "role": PromptRole.ASSISTANT.value,
            "content": "已提问",
            "status": "complete",
            "property": {"builtin_property": {"message_id": "assist-auq", "tool_calls": []}},
        }
        writer.client.api._contents = [assistant_rec, self._ask_user_interrupt_record()]
        result = writer._fetch_tool_call_reconstruction("call_auq_001", "ask_user_question")
        assert result is not None
        _, merged_property = result
        tc = next(tc for tc in merged_property["tool_calls"] if tc["id"] == "call_auq_001")
        assert tc["type"] == "function"
        # 事件 tool_name 为主源（D-06 name 恢复链）
        assert tc["function"]["name"] == "ask_user_question"
        # 回填 questions 参数（metadata.toolArgs）
        assert json.loads(tc["function"]["arguments"]) == {
            "questions": [{"question": "确认继续？", "multiSelect": False}]
        }

    def test_reconstruct_ask_user_name_from_metadata_tool_name_when_event_missing(self):
        """tool_name 事件缺失 → ask_user 兜底 metadata.toolName（可能缺失则 name 空，绝不回退 tool_call_id）。"""
        writer = _TestWriterHelper.make_writer()
        assistant_rec = {
            "id": 20,
            "role": PromptRole.ASSISTANT.value,
            "content": "已提问",
            "status": "complete",
            "property": {"builtin_property": {"message_id": "assist-auq", "tool_calls": []}},
        }
        writer.client.api._contents = [assistant_rec, self._ask_user_interrupt_record()]
        result = writer._fetch_tool_call_reconstruction("call_auq_001", None)
        assert result is not None
        _, merged_property = result
        tc = next(tc for tc in merged_property["tool_calls"] if tc["id"] == "call_auq_001")
        # ask_user interrupt metadata 无 toolName → name=""（绝不回退 tool_call_id）
        assert tc["function"]["name"] == ""
        assert tc["function"]["name"] != "call_auq_001"


class _TestWriterHelper:
    @staticmethod
    def make_writer() -> AGUISessionWriter:
        mock_client = _MockBKAidevClient()
        return AGUISessionWriter(session_code="test-auq-3", client=mock_client, username="test", tools=[])
