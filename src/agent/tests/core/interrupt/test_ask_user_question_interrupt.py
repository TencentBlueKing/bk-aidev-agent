# -*- coding: utf-8 -*-
"""ask_user_question interrupt 往返 + outcome builder 测试。

本文件证明：

1. ask_user_question interrupt 端到端可用（outcome builder 构造正确、
   hydrate 不动 payload 、完整往返 answer 一致）；
2. approval 行为零回归（ApprovalOutcomeBuilder 续流终态形态构造正确，
   approval 首帧回放仍触发）。

测试镜像 ``tests/core/test_ag_ui_interrupt_protocol.py`` 的模式：monkeypatch
``LangGraphAGUIAgent.run``，用 ``approve_result`` / ``approval_interrupts``
构造 ``AidevAGUIAgent``，断言 SSE 事件类型与 payload 字段。

注：ask_user_question 生产续流首帧回放（依赖 reason 分发）回滚后暂不可用，
留给后续大重构；ApprovalHandler 已随 InterruptHandler 框架撤销移除。
"""

import copy
import json
from unittest.mock import MagicMock

import pytest
from ag_ui.core import EventType, RunFinishedEvent, RunStartedEvent
from aidev_agent.core.ag_ui.agent import LangGraphAGUIAgent
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import (
    AgentInput,
    ResumeItem,
    RunFinishedSuccessOutcome,
    serialize_run_finished_outcome,
)
from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_REASON,
    AskUserQuestionHandler,
    AskUserQuestionOutcomeBuilder,
)

# --------------------------------------------------------------------------- #
# 辅助构造函数
# --------------------------------------------------------------------------- #


def _ask_user_question_interrupt_dict() -> dict:
    """构造一条典型的 ask_user_question "中断态" interrupt（status=pending）。"""
    return {
        "id": "int-question-call1-abc",
        "reason": ASK_USER_QUESTION_REASON,  # "aidev:user_question"
        "message": "需要用户回答：What?",
        "toolCallId": "call1",
        "expiresAt": "2026-06-01T23:59:59+08:00",  #
        "metadata": {
            "type": "ask_user_question",
            "status": "pending",
            "questions": [
                {
                    "header": "选择",
                    "multiSelect": False,
                    "question": "What?",
                    "options": [{"label": "A", "description": "选项A"}],
                }
            ],
            # 模拟 DB 写回形态：用户回答后的 answers
            "answers": [{"question": "What?", "answer": [{"label": "A", "description": "选项A"}]}],
        },
    }


def _approval_interrupt_dict() -> dict:
    """构造一条典型的审批 "中断态" interrupt（status=pending），用于回归测试。"""
    return {
        "id": "int-approval-call1-sn",
        "reason": "aidev:tool_approval",
        "message": "## 工具审批确认\n\n工具需要审批后执行",
        "toolCallId": "call1",
        "callbackToken": "tok-approval",
        "ticketSn": "DE000001",
        "type": "tool_approval",
        "toolName": "whether-query",
        "metadata": {
            "type": "tool_approval",
            "status": "pending",
            "callbackToken": "tok-approval",
            "ticketSn": "DE000001",
            "toolName": "whether-query",
            "ticket": {
                "sn": "DE000001",
                "status": "RUNNING",
                "approvers": ["userA"],
            },
        },
    }


async def _fake_parent_run_normal(self, input):  # noqa: ARG001
    """镜像 test_ag_ui_interrupt_protocol.py 的 fake parent run。"""
    yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id="t1", run_id="r1")
    yield RunFinishedEvent(
        type=EventType.RUN_FINISHED,
        thread_id="t1",
        run_id="r1",
        outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
    )


# --------------------------------------------------------------------------- #
# 测试 1-2：AskUserQuestionOutcomeBuilder.build_run_finished_payload
# --------------------------------------------------------------------------- #


def test_ask_user_question_outcome_builder_resolved():
    """resolved 状态：outcome.type==success，result.id 匹配，payload.answers 存在，顶层 status==resolved。"""
    interrupts = [_ask_user_question_interrupt_dict()]
    outcome, result = AskUserQuestionOutcomeBuilder.build_run_finished_payload(interrupts, "resolved")

    assert outcome["type"] == "success"
    assert outcome["interrupts"][0]["metadata"]["status"] == "resolved"
    assert result["id"] == "int-question-call1-abc"
    assert result["interruptId"] == "int-question-call1-abc"
    # /payload.answers 结构（协议 success 格式，非 metadata 透传）
    assert result["payload"]["answers"] == [{"question": "What?", "answer": [{"label": "A", "description": "选项A"}]}]
    # 顶层 status（协议新增）
    assert result["status"] == "resolved"
    # 入参不被污染
    assert interrupts[0]["metadata"]["status"] == "pending"


def test_ask_user_question_outcome_builder_cancelled():
    """cancelled 状态：metadata.status==cancelled，payload.answers 仍存在。"""
    interrupts = [_ask_user_question_interrupt_dict()]
    outcome, result = AskUserQuestionOutcomeBuilder.build_run_finished_payload(interrupts, "cancelled")

    assert outcome["type"] == "success"
    assert outcome["interrupts"][0]["metadata"]["status"] == "cancelled"
    assert result["payload"]["answers"] == [{"question": "What?", "answer": [{"label": "A", "description": "选项A"}]}]
    assert result["status"] == "cancelled"


# --------------------------------------------------------------------------- #
# 测试 4-5：AidevAGUIAgent 首帧回放（_should_emit_resume_interrupt_finished）
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_approval_resume_still_emits_first_frame_finished(monkeypatch):
    """回归：approval interrupt 续流仍发出首帧 RUN_FINISHED。"""
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    agent = AidevAGUIAgent(
        name="approval-resume-agent",
        graph=MagicMock(),
        approve_result="approved",
        approval_interrupts=[_approval_interrupt_dict()],
    )
    chunks = [
        chunk
        async for chunk in agent.run(
            AgentInput(
                thread_id="t1",
                run_id="r1",
                state={},
                messages=[],
                resume=[ResumeItem(interruptId="int-approval-call1-sn", status="resolved")],
            )
        )
    ]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    assert payloads[0]["type"] == EventType.MESSAGES_SNAPSHOT.value
    assert payloads[1]["type"] == EventType.RUN_FINISHED.value
    assert payloads[1]["outcome"]["type"] == "success"
    assert payloads[1]["outcome"]["interrupts"][0]["metadata"]["status"] == "approved"
    # approval 的 ticket.status 也被刷写
    assert payloads[1]["outcome"]["interrupts"][0]["metadata"]["ticket"]["status"] == "approved"


@pytest.mark.asyncio
async def test_unknown_reason_resume_does_not_emit_first_frame_finished(monkeypatch):
    """未知 reason 的 interrupt 续流不发出首帧 RUN_FINISHED（_should_emit_resume_interrupt_finished 返回 False）。"""
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    unknown = dict(_ask_user_question_interrupt_dict(), reason="aidev:unknown")
    agent = AidevAGUIAgent(
        name="unknown-resume-agent",
        graph=MagicMock(),
        approve_result="resolved",
        approval_interrupts=[unknown],
    )
    chunks = [chunk async for chunk in agent.run(AgentInput(thread_id="t1", run_id="r1", state={}, messages=[]))]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    # 无首帧回放：MESSAGES_SNAPSHOT → RUN_STARTED → RUN_FINISHED
    assert [p["type"] for p in payloads] == [
        EventType.MESSAGES_SNAPSHOT.value,
        EventType.RUN_STARTED.value,
        EventType.RUN_FINISHED.value,
    ]


# --------------------------------------------------------------------------- #
# 测试 6：AskUserQuestionHandler.hydrate_resume 不动 payload
# --------------------------------------------------------------------------- #


def test_ask_user_question_hydrate_preserves_payload():
    """hydrate_resume 设置 status 但不触碰 payload，payload.answers 被保留。"""
    handler = AskUserQuestionHandler()
    items = [
        {
            "interruptId": "x",
            "status": "resolved",
            "payload": {"answers": [{"question": "Pick one", "answer": [{"label": "A", "description": "选项A"}]}]},
        }
    ]
    handler.hydrate_resume(items, "resolved")

    # payload 未被触碰
    assert items[0]["payload"]["answers"] == [
        {"question": "Pick one", "answer": [{"label": "A", "description": "选项A"}]}
    ]
    assert items[0]["status"] == "resolved"


# --------------------------------------------------------------------------- #
# 测试 7：AskUserQuestionHandler.extract_builtin_property
# --------------------------------------------------------------------------- #


def test_ask_user_question_extract_builtin_property():
    """extract_builtin_property 返回 questions、options、answers、multiSelect 字段（ 字段名对齐）。"""
    handler = AskUserQuestionHandler()
    interrupt = {
        "id": "int-question-c1-abc",
        "reason": ASK_USER_QUESTION_REASON,
        "toolCallId": "c1",
        "metadata": {
            "type": "ask_user_question",
            "status": "resolved",
            "questions": [
                {
                    "header": "选择",
                    "multiSelect": False,
                    "question": "Pick one",
                    "options": [{"label": "A", "description": "选项A"}],
                }
            ],
            "answers": [{"question": "Pick one", "answer": [{"label": "A", "description": "选项A"}]}],
        },
    }
    bp = handler.extract_builtin_property("int-question-c1-abc", interrupt, graph_thread_id="t1")

    assert bp["questions"] == [
        {
            "header": "选择",
            "multiSelect": False,
            "question": "Pick one",
            "options": [{"label": "A", "description": "选项A"}],
        }
    ]
    assert bp["answers"] == [{"question": "Pick one", "answer": [{"label": "A", "description": "选项A"}]}]
    # multiSelect 存在于 questions[0] 项内（协议结构），顶层 metadata 无此字段
    assert bp["multiSelect"] is None
    assert bp["questions"][0]["multiSelect"] is False  # 非 multi_select（字段名对齐）
    assert bp["type"] == "ask_user_question"
    assert bp["reason"] == ASK_USER_QUESTION_REASON
    assert bp["interrupt_id"] == "int-question-c1-abc"
    assert bp["tool_call_id"] == "c1"
    assert bp["graph_thread_id"] == "t1"
    # ask_user_question 不提取审批专属字段
    assert "callback_token" not in bp
    assert "ticket_sn" not in bp


# --------------------------------------------------------------------------- #
# 测试 9：完整往返 — build_payload → hydrate_resume → build_run_finished_payload
# --------------------------------------------------------------------------- #


def test_ask_user_question_full_roundtrip_preserves_answer():
    """完整往返：answers 在整个管道中被保留（ +  + ）。

    流程：
    1. handler.build_payload 构造 pending 态 interrupt（questions 数组）
    2. 前端提交 ResumeItem（payload.answers = [...]）
    3. handler.hydrate_resume 仅补 status，不动 payload
    4. handler.outcome_builder.build_run_finished_payload 构造终态形态
    → answers 在 result.payload.answers 中被保留（协议 success 格式）
    """
    handler = AskUserQuestionHandler()

    # 1. 构造 pending 态 interrupt
    questions = [
        {
            "header": "选择",
            "multiSelect": False,
            "question": "Pick one",
            "options": [{"label": "A", "description": "选项A"}],
        }
    ]
    payload = handler.build_payload(questions=questions, tool_call_id="c1")
    assert payload["metadata"]["status"] == "pending"
    assert "answers" not in payload["metadata"]  # pending 态无 answers

    # 2. 前端提交 ResumeItem（payload 含 answers）
    submitted_answers = [{"question": "Pick one", "answer": [{"label": "A", "description": "选项A"}]}]
    resume_items = [{"interruptId": payload["id"], "status": "resolved", "payload": {"answers": submitted_answers}}]
    # 模拟前端把 answers 写入 interrupt metadata（DB 落库后的形态）
    db_interrupt = copy.deepcopy(payload)
    db_interrupt["metadata"]["answers"] = submitted_answers

    # 3. hydrate_resume 仅补 status，不动 payload
    original_payload = copy.deepcopy(resume_items[0]["payload"])
    handler.hydrate_resume(resume_items, "resolved")
    assert resume_items[0]["payload"] == original_payload  # payload 未变
    assert resume_items[0]["status"] == "resolved"

    # 4. outcome_builder 构造终态形态
    outcome, result = handler.outcome_builder.build_run_finished_payload([db_interrupt], "resolved")
    assert outcome["type"] == "success"
    assert outcome["interrupts"][0]["metadata"]["status"] == "resolved"
    # answers 在 result.payload.answers 中被保留（协议 success 格式，非 metadata 透传）
    assert result["payload"]["answers"] == submitted_answers
    assert result["status"] == "resolved"  # 顶层 status（协议新增）
    assert result["id"] == payload["id"]
    assert result["reason"] == ASK_USER_QUESTION_REASON


# --------------------------------------------------------------------------- #
# 测试 10：回归测试 — 续流首帧路径实际调用 AskUserQuestionOutcomeBuilder.build_run_finished_payload
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_resume_first_frame_calls_outcome_builder(monkeypatch):
    """回归测试：ask_user_question 续流首帧应实际调用 AskUserQuestionOutcomeBuilder.build_run_finished_payload，
    防止回退为硬编码 outcome={"type":"success"} 的死代码路径。"""
    # spy：包装原始 build_run_finished_payload 记录调用
    call_count = {"n": 0}
    original = AskUserQuestionOutcomeBuilder.build_run_finished_payload

    @classmethod
    def _spy(cls, interrupts, status, resume_answers=None):  # noqa: ARG001
        call_count["n"] += 1
        return original.__func__(cls, interrupts, status, resume_answers=resume_answers)

    monkeypatch.setattr(AskUserQuestionOutcomeBuilder, "build_run_finished_payload", _spy)

    async def _fake_parent_run(self, input):  # noqa: ARG001
        yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id="t", run_id="r")
        yield RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id="t",
            run_id="r",
            outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
        )

    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run)

    auq_interrupts = [
        {
            "id": "int-question-call1-abc",
            "reason": ASK_USER_QUESTION_REASON,
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
                        "options": [{"label": "测试环境", "description": "test"}],
                    }
                ],
            },
        }
    ]
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

    # 2026-09-02 处置：ask_user 续流首帧回放已移除（处理前置改写 + MESSAGES_SNAPSHOT
    # 完整携带 resolved 卡片，replay 冗余且 raw 数据缺 reason 使前端卡片消失——
    # 生产回归实证；294ff5d55 好基线同样不推）。builder 不应被调用。
    assert call_count["n"] == 0, (
        f"replay 已移除，AskUserQuestionOutcomeBuilder.build_run_finished_payload 不应被调用，实际 {call_count['n']} 次"
    )
    # 确保确实产生了 SSE 事件（非空流）
    assert chunks, "续流应产生 SSE 事件"
    # 不应出现 resume_replay 事件
    replay_chunks = [c for c in chunks if '"resume_replay":true' in c]
    assert not replay_chunks, f"不应推送 resume_replay 事件，实际: {replay_chunks}"


@pytest.mark.asyncio
async def test_resume_first_frame_result_answers_from_resume_payload(monkeypatch):
    """WR-01 回归测试：续流首帧 result[0].payload.answers 必须等于 resume payload 的 answers
    （用户刚提交的答案原样透传），而非空的 interrupt.metadata.answers。

    生产中 self._ask_user_question_interrupts 来自 graph checkpoint（pending 态），
    metadata 无 answers 字段；用户答案通过 forwarded_props.command.resume[0].payload.answers
    单独传入。修复前 builder 从 metadata.answers 取值 → []（空），答案丢失。
    """
    monkeypatch.setattr(LangGraphAGUIAgent, "run", _fake_parent_run_normal)

    # 生产形态：metadata 无 answers（来自 graph checkpoint pending 态）
    auq_interrupts = [
        {
            "id": "int-question-call1-abc",
            "reason": ASK_USER_QUESTION_REASON,
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
                        "options": [{"label": "测试环境", "description": "test"}],
                    }
                ],
                # 注意：无 answers 字段（模拟生产 graph checkpoint pending 态）
            },
        }
    ]
    # resume payload 的 answers（用户刚提交的答案）
    expected_answers = [{"question": "请选择部署环境", "answer": [{"label": "测试环境", "description": "test"}]}]

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
                                "payload": {"answers": expected_answers},
                            }
                        ]
                    }
                },
            )
        )
    ]
    payloads = [json.loads(chunk[6:]) for chunk in chunks]

    # 2026-09-02 处置：ask_user 续流不再发 replay 首帧事件——用户答案的权威载体为
    # MESSAGES_SNAPSHOT 中被处理前置改写为终态的 interrupt 记录（result.payload.answers，
    # 生产路径回归见 test_ask_user_card_production_path.py）。此处断言无 replay 事件。
    replay_finished = [p for p in payloads if p["type"] == EventType.RUN_FINISHED.value and p.get("resume_replay")]
    assert not replay_finished, f"ask_user 续流不应推送 replay RUN_FINISHED，实际: {replay_finished}"

    # 首帧 MESSAGES_SNAPSHOT 仍在（已答卡回显载体）
    messages_snapshots = [p for p in payloads if p["type"] == EventType.MESSAGES_SNAPSHOT.value]
    assert len(messages_snapshots) >= 1, f"应至少有 1 个 MESSAGES_SNAPSHOT（首帧），实际: {len(messages_snapshots)}"
