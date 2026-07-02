import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from ag_ui.core import EventType, RunFinishedEvent, RunStartedEvent
from aidev_agent.core.ag_ui.agent import LangGraphAGUIAgent
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.approval import ApprovalOutcomeBuilder
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


def test_event_dispatcher_suppresses_skill_approval_without_need_approval():
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
    agent = AidevAGUIAgent(name="outer-agent", graph=MagicMock(), tools={"skill_tool": tool})

    suppressed = agent._event_dispatcher._handle_tool_call_start(  # noqa: SLF001
        SimpleNamespace(
            type=EventType.TOOL_CALL_START,
            tool_call_id="call-skill-1",
            tool_call_name="skill_tool",
            model_dump=lambda: {
                "type": EventType.TOOL_CALL_START,
                "tool_call_id": "call-skill-1",
                "tool_call_name": "skill_tool",
            },
        )
    )

    assert suppressed == ""
    assert "call-skill-1" in agent._event_dispatcher._suppressed_tool_call_ids  # noqa: SLF001


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
