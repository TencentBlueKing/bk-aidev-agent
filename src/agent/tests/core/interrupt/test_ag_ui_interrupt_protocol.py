import json
from unittest.mock import MagicMock

import pytest
from ag_ui.core import EventType, RunFinishedEvent, RunStartedEvent, ToolCallStartEvent
from aidev_agent.core.ag_ui.agent import LangGraphAGUIAgent
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.approval import ApprovalOutcomeBuilder
from aidev_agent.core.ag_ui.events import ExtendToolCallStartEvent
from aidev_agent.core.ag_ui.types import (
    AgentInput,
    ExtendAssistantMessage,
    MessageSnapshotEventExtend,
    ResumeItem,
    RunFinishedSuccessOutcome,
    serialize_run_finished_outcome,
)
from langchain_core.tools import StructuredTool


@pytest.mark.asyncio
async def test_aidev_agent_run_exposes_messages_snapshot(monkeypatch):
    async def _fake_parent_run(self, input):  # noqa: ARG001
        yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id="thread-3", run_id="run-3")
        yield MessageSnapshotEventExtend(
            type=EventType.MESSAGES_SNAPSHOT,
            messages=[ExtendAssistantMessage(id="assistant-3", role="assistant", content="snapshot message")],
        )
        yield RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id="thread-3",
            run_id="run-3",
            outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
        )

    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run)

    agent = AidevAGUIAgent(name="outer-agent", graph=MagicMock())
    chunks = [
        chunk async for chunk in agent.run(AgentInput(thread_id="thread-3", run_id="run-3", state={}, messages=[]))
    ]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    assert [payload["type"] for payload in payloads] == [
        EventType.MESSAGES_SNAPSHOT.value,
        EventType.RUN_STARTED.value,
        EventType.RUN_FINISHED.value,
    ]


@pytest.mark.asyncio
async def test_handle_single_event_suppresses_approval_tool_call(monkeypatch):
    """D-01: _handle_single_event 覆写抑制需要审批的 ToolCallStartEvent。"""

    async def _fake_super(self, event, state):  # noqa: ARG001
        yield ToolCallStartEvent(
            type=EventType.TOOL_CALL_START,
            tool_call_id="call-skill-1",
            tool_call_name="skill_tool",
            parent_message_id="msg-1",
        )

    monkeypatch.setattr(LangGraphAGUIAgent, "_handle_single_event", _fake_super)

    async def _tool_impl(a: int, b: int) -> int:
        return a + b

    tool = StructuredTool.from_function(coroutine=_tool_impl, name="skill_tool", description="skill tool")
    tool.metadata = {
        "skill_name": "skill-runner",
        "approval": {
            "tool_type": "skill",
            "skill_code": "skill-runner",
            "tool_name": "Skill Runner",
            "target": {"type": "skill", "skill_name": "skill-runner", "display_name": "Skill Runner"},
        },
    }
    agent = AidevAGUIAgent(name="test-agent", graph=MagicMock(), tools={"skill_tool": tool})

    events = [
        ev async for ev in agent._handle_single_event({"event": "on_chat_model_stream"}, {})
    ]

    # 审批工具的 ToolCallStartEvent 被抑制（不 yield）
    assert len(events) == 0
    assert "call-skill-1" in agent._suppressed_tool_call_ids  # noqa: SLF001


@pytest.mark.asyncio
async def test_handle_single_event_enhances_non_approval_tool_call(monkeypatch):
    """D-01: 非审批工具的 ToolCallStartEvent 被 enhance 后 yield ExtendToolCallStartEvent。"""

    async def _fake_super(self, event, state):  # noqa: ARG001
        yield ToolCallStartEvent(
            type=EventType.TOOL_CALL_START,
            tool_call_id="call-1",
            tool_call_name="normal_tool",
            parent_message_id="msg-1",
        )

    monkeypatch.setattr(LangGraphAGUIAgent, "_handle_single_event", _fake_super)

    tool = StructuredTool.from_function(coroutine=lambda x: x, name="normal_tool", description="a normal tool")
    tool.metadata = {}
    agent = AidevAGUIAgent(name="test-agent", graph=MagicMock(), tools={"normal_tool": tool})

    events = [
        ev async for ev in agent._handle_single_event({"event": "on_chat_model_stream"}, {})
    ]

    assert len(events) == 1
    assert isinstance(events[0], ExtendToolCallStartEvent)
    assert events[0].tool_call_id == "call-1"
    # enhance_tool_call 注入 description
    assert events[0].description == "a normal tool"
    # 非审批工具不加入 suppressed set
    assert "call-1" not in agent._suppressed_tool_call_ids  # noqa: SLF001


# ---------------------------------------------------------------------------
# 审批续流终态形态：ApprovalOutcomeBuilder.upgrade_content_to_success
#                  / ApprovalOutcomeBuilder.build_run_finished_payload
# ---------------------------------------------------------------------------


def _approval_interrupt_dict() -> dict:
    """构造一条典型的"中断态"interrupt 结构（status=pending），供后续升级测试使用。"""
    return {
        "id": "int-approval-call-x",
        "reason": "aidev:tool_approval",
        "message": "## 工具审批确认\n\n工具需要审批后执行\n\n审批通过后将自动继续执行。",
        "toolCallId": "call-x",
        "metadata": {
            "type": "tool_approval",
            "status": "pending",
            "callbackToken": "tok-x",
            "ticketSn": "DE000001",
            "toolName": "whether-query",
            "toolCode": "whether-query",
            "ticket": {
                "approvers": ["userA", "userB"],
                "sn": "DE000001",
                "status": "RUNNING",
                "submit_time": "2026-06-15T05:34:57+00:00",
                "title": "执行「whether-query」需要审批",
                "url": "https://itsm-stag.example.com/ticket/1",
            },
        },
    }


def _interrupt_content() -> dict:
    return {"outcome": {"type": "interrupt", "interrupts": [_approval_interrupt_dict()]}}


@pytest.mark.parametrize("approve_result", ["approved", "rejected", "cancelled"])
def test_upgrade_content_to_success_upgrades_structure(approve_result):
    original = _interrupt_content()
    upgraded = ApprovalOutcomeBuilder.upgrade_content_to_success(original, approve_result)

    # 不污染入参
    assert original["outcome"]["type"] == "interrupt"
    assert original["outcome"]["interrupts"][0]["metadata"]["status"] == "pending"
    assert original["outcome"]["interrupts"][0]["metadata"]["ticket"]["status"] == "RUNNING"

    # outcome.type 升级
    assert upgraded["outcome"]["type"] == "success"
    interrupt = upgraded["outcome"]["interrupts"][0]
    assert interrupt["metadata"]["status"] == approve_result
    assert interrupt["metadata"]["ticket"]["status"] == approve_result
    # metadata 整体透传（toolCode / approvers 等非裁剪字段保留）
    assert interrupt["metadata"]["toolCode"] == "whether-query"
    assert interrupt["metadata"]["ticket"]["approvers"] == ["userA", "userB"]

    # result：扁平化 interrupts[0]，metadata 移入 payload.metadata
    result = upgraded["result"]
    assert result["id"] == interrupt["id"]
    # interruptId 与 id 同值，供前端按中断 id 关联续流结果
    assert result["interruptId"] == interrupt["id"]
    assert result["interruptId"] == result["id"]
    assert result["reason"] == interrupt["reason"]
    assert result["message"] == interrupt["message"]
    assert result["toolCallId"] == interrupt["toolCallId"]
    assert "metadata" not in result  # 顶层不再有 metadata
    assert result["payload"]["metadata"] == interrupt["metadata"]


def test_upgrade_content_to_success_idempotent():
    """对已是 success 形态的 content 再次刷写，结构稳定、status 仍为目标值。"""
    once = ApprovalOutcomeBuilder.upgrade_content_to_success(_interrupt_content(), "approved")
    twice = ApprovalOutcomeBuilder.upgrade_content_to_success(once, "approved")
    assert twice["outcome"]["type"] == "success"
    assert twice["outcome"]["interrupts"][0]["metadata"]["status"] == "approved"
    assert twice["result"]["payload"]["metadata"]["status"] == "approved"


def test_upgrade_content_to_success_returns_none_for_invalid():
    assert ApprovalOutcomeBuilder.upgrade_content_to_success(None, "approved") is None
    assert ApprovalOutcomeBuilder.upgrade_content_to_success("not-a-json", "approved") is None
    assert ApprovalOutcomeBuilder.upgrade_content_to_success({}, "approved") is None
    assert ApprovalOutcomeBuilder.upgrade_content_to_success({"outcome": {"type": "other"}}, "approved") is None
    assert (
        ApprovalOutcomeBuilder.upgrade_content_to_success(
            {"outcome": {"type": "interrupt", "interrupts": []}}, "approved"
        )
        is None
    )


def test_build_run_finished_payload_matches_success_content():
    interrupts = [_approval_interrupt_dict()]
    outcome, result = ApprovalOutcomeBuilder.build_run_finished_payload(interrupts, "approved")
    assert outcome["type"] == "success"
    assert outcome["interrupts"][0]["metadata"]["status"] == "approved"
    assert outcome["interrupts"][0]["metadata"]["ticket"]["status"] == "approved"
    assert result["payload"]["metadata"] == outcome["interrupts"][0]["metadata"]
    # 入参不被污染
    assert interrupts[0]["metadata"]["status"] == "pending"


# ---------------------------------------------------------------------------
# 续流场景：AidevAGUIAgent.run 首条 SSE 事件应为带 result 的 RUN_FINISHED
# ---------------------------------------------------------------------------


async def _fake_parent_run_normal(self, input):  # noqa: ARG001
    yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id="t", run_id="r")
    yield RunFinishedEvent(
        type=EventType.RUN_FINISHED,
        thread_id="t",
        run_id="r",
        outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
    )


@pytest.mark.asyncio
async def test_resume_emits_terminal_run_finished_before_run_started(monkeypatch):
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    interrupts = [_approval_interrupt_dict()]
    agent = AidevAGUIAgent(
        name="resume-agent",
        graph=MagicMock(),
        approve_result="approved",
        approval_interrupts=interrupts,
    )
    chunks = [
        chunk
        async for chunk in agent.run(
            AgentInput(
                thread_id="t",
                run_id="r",
                state={},
                messages=[],
                resume=[ResumeItem(interruptId="int-approval-call-x", status="resolved")],
            )
        )
    ]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    # 首条 MESSAGES_SNAPSHOT 之后紧跟 RUN_FINISHED（终态回放），随后才是 SDK 的 RUN_STARTED / RUN_FINISHED
    assert [p["type"] for p in payloads] == [
        EventType.MESSAGES_SNAPSHOT.value,
        EventType.RUN_FINISHED.value,
        EventType.RUN_STARTED.value,
        EventType.RUN_FINISHED.value,
    ]

    first = payloads[1]
    assert first["outcome"]["type"] == "success"
    assert first["outcome"]["interrupts"][0]["metadata"]["status"] == "approved"
    assert first["outcome"]["interrupts"][0]["metadata"]["ticket"]["status"] == "approved"
    # run_id（SSE 序列化后字段名 runId）取自前端续流请求的 interruptId
    assert first["runId"] == "int-approval-call-x"
    # result 顶层字段（与 outcome 平级）
    assert "result" in first
    assert first["result"]["id"] == "int-approval-call-x"
    # interruptId 与 id 同值，供前端按中断 id 关联续流结果
    assert first["result"]["interruptId"] == "int-approval-call-x"
    assert first["result"]["toolCallId"] == "call-x"
    assert "metadata" not in first["result"]
    assert first["result"]["payload"]["metadata"]["status"] == "approved"
    assert first["result"]["payload"]["metadata"]["toolCode"] == "whether-query"


@pytest.mark.asyncio
async def test_resume_run_id_falls_back_to_interrupt_id(monkeypatch):
    """前端续流请求未带 resume 列表时，run_id 兜底取 approval_interrupts[0].id。"""
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    agent = AidevAGUIAgent(
        name="resume-agent",
        graph=MagicMock(),
        approve_result="rejected",
        approval_interrupts=[_approval_interrupt_dict()],
    )
    chunks = [chunk async for chunk in agent.run(AgentInput(thread_id="t", run_id="r", state={}, messages=[]))]
    first = json.loads(chunks[1][6:])
    assert first["type"] == EventType.RUN_FINISHED.value
    assert first["runId"] == "int-approval-call-x"
    assert first["outcome"]["interrupts"][0]["metadata"]["status"] == "rejected"


@pytest.mark.asyncio
async def test_normal_chat_does_not_emit_resume_run_finished(monkeypatch):
    """非审批续流场景：不应额外发出回放 RUN_FINISHED。"""
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    agent = AidevAGUIAgent(name="normal-agent", graph=MagicMock())
    chunks = [chunk async for chunk in agent.run(AgentInput(thread_id="t", run_id="r", state={}, messages=[]))]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]
    assert [p["type"] for p in payloads] == [
        EventType.MESSAGES_SNAPSHOT.value,
        EventType.RUN_STARTED.value,
        EventType.RUN_FINISHED.value,
    ]


@pytest.mark.asyncio
async def test_resume_skipped_for_non_approval_interrupt(monkeypatch):
    """非 aidev:tool_approval 类型的 interrupt 续流亦不触发回放（保险机制）。"""
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    other = dict(_approval_interrupt_dict(), reason="aidev:other_interrupt")
    agent = AidevAGUIAgent(
        name="resume-agent",
        graph=MagicMock(),
        approve_result="approved",
        approval_interrupts=[other],
    )
    chunks = [chunk async for chunk in agent.run(AgentInput(thread_id="t", run_id="r", state={}, messages=[]))]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]
    assert [p["type"] for p in payloads] == [
        EventType.MESSAGES_SNAPSHOT.value,
        EventType.RUN_STARTED.value,
        EventType.RUN_FINISHED.value,
    ]


# ---------------------------------------------------------------------------
# SSE 层 metadata 裁剪：approval 裁剪为 ticket-only，ask_user_question 保留完整
# ---------------------------------------------------------------------------


def _ask_user_question_interrupt_dict() -> dict:
    """构造 ask_user_question 中断态结构（含 questions 数组）。"""
    return {
        "id": "int-question-call1-abc",
        "reason": "aidev:user_question",
        "message": "需要用户回答：请选择部署环境",
        "toolCallId": "call1",
        "metadata": {
            "type": "ask_user_question",
            "status": "pending",
            "questions": [
                {
                    "header": "部署确认",
                    "multiSelect": False,
                    "question": "请选择部署环境",
                    "options": [
                        {"label": "测试环境", "description": "test"},
                        {"label": "生产环境", "description": "prod"},
                    ],
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_run_finished_preserves_ask_user_question_metadata(monkeypatch):
    """ask_user_question 中断的 RUN_FINISHED 事件应保留完整 metadata（含 questions 数组），
    不被 approval 的 ticket-only 裁剪逻辑误伤。"""

    async def _fake_parent_run_interrupt(self, input):  # noqa: ARG001
        yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id="t", run_id="r")
        from aidev_agent.core.ag_ui.types import RunFinishedInterruptOutcome

        outcome = serialize_run_finished_outcome(
            RunFinishedInterruptOutcome(interrupts=[_ask_user_question_interrupt_dict()])
        )
        yield RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id="t",
            run_id="r",
            outcome=outcome,
        )

    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_interrupt)

    agent = AidevAGUIAgent(name="auq-agent", graph=MagicMock())
    chunks = [chunk async for chunk in agent.run(AgentInput(thread_id="t", run_id="r", state={}, messages=[]))]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    # 找到 RUN_FINISHED 事件
    run_finished = next(p for p in payloads if p["type"] == EventType.RUN_FINISHED.value)
    assert run_finished["outcome"]["type"] == "interrupt"
    interrupt = run_finished["outcome"]["interrupts"][0]

    # 关键断言：metadata 保留完整 questions 数组，未被裁剪为 None
    assert interrupt["metadata"] is not None, "ask_user_question metadata 被裁剪为 None"
    assert "questions" in interrupt["metadata"], "metadata 缺少 questions 数组"
    assert len(interrupt["metadata"]["questions"]) == 1
    assert interrupt["metadata"]["questions"][0]["question"] == "请选择部署环境"
    assert len(interrupt["metadata"]["questions"][0]["options"]) == 2


@pytest.mark.asyncio
async def test_run_finished_still_truncates_approval_metadata(monkeypatch):
    """approval 中断的 RUN_FINISHED 事件仍裁剪 metadata 为 ticket-only（回归保护）。"""

    async def _fake_parent_run_approval(self, input):  # noqa: ARG001
        yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id="t", run_id="r")
        from aidev_agent.core.ag_ui.types import RunFinishedInterruptOutcome

        outcome = serialize_run_finished_outcome(RunFinishedInterruptOutcome(interrupts=[_approval_interrupt_dict()]))
        yield RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id="t",
            run_id="r",
            outcome=outcome,
        )

    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_approval)

    agent = AidevAGUIAgent(name="approval-agent", graph=MagicMock())
    chunks = [chunk async for chunk in agent.run(AgentInput(thread_id="t", run_id="r", state={}, messages=[]))]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    run_finished = next(p for p in payloads if p["type"] == EventType.RUN_FINISHED.value)
    interrupt = run_finished["outcome"]["interrupts"][0]

    # approval metadata 应被裁剪为只含 ticket
    assert interrupt["metadata"] is not None
    assert "ticket" in interrupt["metadata"]
    assert "callbackToken" not in interrupt["metadata"]
    assert "toolName" not in interrupt["metadata"]


# ---------------------------------------------------------------------------
# ask_user_question 续流首帧回放：关闭前端弹窗
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_ask_user_question_emits_first_frame_run_finished(monkeypatch):
    """ask_user_question 续流时应发首帧 RUN_FINISHED（outcome=success），关闭前端弹窗。"""
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    auq_interrupts = [_ask_user_question_interrupt_dict()]
    agent = AidevAGUIAgent(
        name="auq-resume-agent",
        graph=MagicMock(),
        ask_user_question_interrupts=auq_interrupts,
    )
    chunks = [
        chunk
        async for chunk in agent.run(
            AgentInput(
                thread_id="t",
                run_id="r",
                state={},
                messages=[
                    {"role": "user", "content": "问我问题", "id": "u1"},
                    {
                        "role": "interrupt",
                        "content": {"outcome": {"type": "interrupt"}},
                        "id": auq_interrupts[0]["id"],
                        "status": "pending",
                    },
                ],
                forwarded_props={
                    "command": {
                        "resume": [
                            {
                                "interruptId": auq_interrupts[0]["id"],
                                "status": "resolved",
                                "payload": {
                                    "answers": [{"question": "q", "answer": [{"label": "a", "description": "d"}]}]
                                },
                            }
                        ]
                    }
                },
            )
        )
    ]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    # 首条 MESSAGES_SNAPSHOT 之后紧跟 ACTIVITY_SNAPSHOT（首帧回放，关闭弹窗）
    types = [p["type"] for p in payloads]
    assert types[0] == EventType.MESSAGES_SNAPSHOT.value
    assert types[1] == EventType.ACTIVITY_SNAPSHOT.value, f"首帧回放 ACTIVITY_SNAPSHOT 未发出，types={types}"

    activity_snapshot = payloads[1]
    assert activity_snapshot["activityType"] == "interrupt"
    assert activity_snapshot["messageId"] == auq_interrupts[0]["id"]
    assert activity_snapshot["replace"] is True

    content = activity_snapshot["content"]
    assert content["outcome"]["type"] == "success"
    # 修复后 outcome 含 interrupts 字段（来自 AskUserQuestionOutcomeBuilder.build_run_finished_payload）
    assert "interrupts" in content["outcome"], "outcome 应含 interrupts 字段"
    assert len(content["outcome"]["interrupts"]) > 0, "interrupts 应非空"
    # interrupts[0] 应为已答问题的历史快照，status 刷写为 resolved
    auq_interrupt = content["outcome"]["interrupts"][0]
    assert auq_interrupt["reason"] == "aidev:user_question"
    assert auq_interrupt["metadata"]["status"] == "resolved"
    assert content["runId"] == auq_interrupts[0]["id"], "runId 应为 interruptId，让前端据此关闭弹窗"

    # result 是数组，每项含 interruptId/payload/reason/status（前端协议）
    result_list = content.get("result")
    assert isinstance(result_list, list), f"result 应为数组，实际: {type(result_list)}"
    assert len(result_list) == 1
    result_item = result_list[0]
    assert result_item["interruptId"] == auq_interrupts[0]["id"]
    assert result_item["reason"] == "aidev:user_question"
    assert result_item["status"] == "resolved"
    # WR-02 修复：断言 answers 内容等于 resume payload 的值，而非仅 key 存在。
    # resume payload（第 433 行）answers = [{"question": "q", "answer": [{"label": "a", "description": "d"}]}]
    # 修复前 builder 从 metadata.answers 取值（fixture metadata 无 answers）→ []，此断言会失败
    assert result_item["payload"]["answers"] == [{"question": "q", "answer": [{"label": "a", "description": "d"}]}], (
        "result.payload.answers 应来自 resume payload（用户刚提交的答案），而非空的 metadata.answers"
    )

    # ACTIVITY_SNAPSHOT 之后应推送额外的 MESSAGES_SNAPSHOT，将 interrupt 消息更新为终态
    assert types[2] == EventType.MESSAGES_SNAPSHOT.value, f"ACTIVITY_SNAPSHOT 后应推送 MESSAGES_SNAPSHOT，types={types}"
    updated_snapshot = payloads[2]
    updated_messages = updated_snapshot.get("messages", [])
    interrupt_msgs = [m for m in updated_messages if m.get("role") == "interrupt"]
    assert interrupt_msgs, "更新后的 MESSAGES_SNAPSHOT 应包含 interrupt 消息"
    updated_interrupt = interrupt_msgs[0]
    assert updated_interrupt["status"] == "complete", "interrupt 消息 status 应为 complete"
    assert updated_interrupt["content"]["outcome"]["type"] == "success", (
        "interrupt 消息 content.outcome.type 应为 success"
    )
    # MESSAGES_SNAPSHOT 的 terminal_content 也应含 interrupts（与 ACTIVITY_SNAPSHOT 一致，使用同一个 builder）
    assert "interrupts" in updated_interrupt["content"]["outcome"], (
        "MESSAGES_SNAPSHOT 的 outcome 也应含 interrupts 字段"
    )
    assert len(updated_interrupt["content"]["outcome"]["interrupts"]) > 0


@pytest.mark.asyncio
async def test_normal_chat_does_not_emit_auq_resume_finished(monkeypatch):
    """非续流场景不应发 ask_user_question 首帧回放。"""
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    agent = AidevAGUIAgent(name="normal-agent", graph=MagicMock())
    chunks = [chunk async for chunk in agent.run(AgentInput(thread_id="t", run_id="r", state={}, messages=[]))]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    types = [p["type"] for p in payloads]
    assert types == [
        EventType.MESSAGES_SNAPSHOT.value,
        EventType.RUN_STARTED.value,
        EventType.RUN_FINISHED.value,
    ], f"普通对话不应有首帧回放，types={types}"
