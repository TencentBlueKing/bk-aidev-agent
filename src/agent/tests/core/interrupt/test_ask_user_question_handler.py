# -*- coding: utf-8 -*-
"""``AskUserQuestionHandler`` 单元测试 — 覆盖以下行为用例。

测试覆盖 7 个行为用例：

1. ``ASK_USER_QUESTION_REASON == "aidev:user_question"``
2. ``build_payload`` 基本字段（reason / id 前缀 / metadata.questions + expiresAt，无扩展字段）
3. ``build_payload`` 带 options + multiSelect（options 在 question 项内）
4. ``hydrate_resume`` 不覆写 payload（只设置 status，不动 payload）
5. ``hydrate_resume`` 从 db_data 设置 status（status 来自 db_data）
6. ``AskUserQuestionOutcomeBuilder.build_run_finished_payload`` 终态形态构造（payload.answers + 顶层 status）
"""

from types import SimpleNamespace

import pytest
from aidev_agent.core.ag_ui.utils import contents_to_agui_messages
from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_REASON,
    ASK_USER_QUESTION_SKIPPED_CONTENT,
    AskUserQuestionHandler,
    AskUserQuestionItem,
    AskUserQuestionOutcomeBuilder,
    AskUserQuestionTarget,
    parse_resume_answers,
)
from aidev_agent.pydantic_models import ChatPrompt


# 测试 1：reason 常量
def test_ask_user_question_reason_constant():
    assert ASK_USER_QUESTION_REASON == "aidev:user_question"


# 测试 2：build_payload 基本字段
def test_build_payload_basic_fields():
    handler = AskUserQuestionHandler()
    questions = [
        {
            "header": "颜色",
            "multiSelect": False,
            "question": "What color?",
            "options": [{"label": "Red", "description": "红色"}],
        }
    ]
    payload = handler.build_payload(questions=questions, tool_call_id="call_123")

    assert payload["reason"] == "aidev:user_question"
    # id 格式 int-question-{tool_call_id}-{uuid_hex}
    assert payload["id"].startswith("int-question-call_123-")
    assert payload["toolCallId"] == "call_123"
    assert payload["expiresAt"] is not None
    metadata = payload["metadata"]
    assert metadata["type"] == "ask_user_question"
    assert metadata["status"] == "pending"
    assert metadata["questions"] == questions
    # 删除的字段不存在
    assert "required" not in metadata
    assert "other_enabled" not in metadata
    assert "multi_select" not in metadata  # 已移入 question 项（multiSelect）
    assert "default" not in metadata
    assert "placeholder" not in metadata


# 测试 3：build_payload 带 options + multiSelect（options 在 question 项内）
def test_build_payload_with_options_and_multi_select():
    handler = AskUserQuestionHandler()
    questions = [
        {
            "header": "选择",
            "multiSelect": True,
            "question": "Pick",
            "options": [
                {"label": "A", "description": "选项A"},
                {"label": "B", "description": "选项B"},
            ],
        }
    ]
    payload = handler.build_payload(questions=questions, tool_call_id="c1")

    metadata = payload["metadata"]
    assert metadata["questions"][0]["multiSelect"] is True
    assert metadata["questions"][0]["options"] == [
        {"label": "A", "description": "选项A"},
        {"label": "B", "description": "选项B"},
    ]


# 测试 4：hydrate_resume 不覆写 payload（只设置 status，不动 payload）
def test_hydrate_resume_does_not_modify_payload():
    handler = AskUserQuestionHandler()
    resume_items = [
        {
            "interruptId": "x",
            "status": "resolved",
            "payload": {"answers": [{"question": "Q", "answer": [{"label": "yes", "description": None}]}]},
        }
    ]
    handler.hydrate_resume(resume_items, db_data=None)

    # payload 保持为 answers 结构，不被覆写
    assert resume_items[0]["payload"] == {
        "answers": [{"question": "Q", "answer": [{"label": "yes", "description": None}]}]
    }


# 测试 5：hydrate_resume 从 db_data 设置 status（status 来自 db_data）
def test_hydrate_resume_sets_status_from_db_data():
    handler = AskUserQuestionHandler()
    resume_items = [
        {
            "interruptId": "x",
            "payload": {"answers": [{"question": "Q", "answer": [{"label": "yes", "description": None}]}]},
        }
    ]
    handler.hydrate_resume(resume_items, db_data="resolved")

    assert resume_items[0]["status"] == "resolved"


# 测试 6：AskUserQuestionOutcomeBuilder.build_run_finished_payload 终态形态构造
def test_outcome_builder_build_run_finished_payload():
    interrupts = [
        {
            "id": "x",
            "reason": "aidev:user_question",
            "metadata": {
                "status": "pending",
                "questions": [
                    {
                        "header": "选择",
                        "multiSelect": False,
                        "question": "Q",
                        "options": [{"label": "A", "description": "选项A"}],
                    }
                ],
                # 模拟 DB 写回形态：用户回答后的 answers
                "answers": [{"question": "Q", "answer": [{"label": "A", "description": "选项A"}]}],
            },
        }
    ]
    outcome, result = AskUserQuestionOutcomeBuilder.build_run_finished_payload(interrupts, "resolved")

    assert outcome["type"] == "success"
    assert outcome["interrupts"][0]["metadata"]["status"] == "resolved"
    assert result["id"] == "x"
    assert result["interruptId"] == "x"
    # /payload.answers 结构（协议 success 格式，非 metadata 透传）
    assert result["payload"]["answers"] == [{"question": "Q", "answer": [{"label": "A", "description": "选项A"}]}]
    # 顶层 status（协议新增）
    assert result["status"] == "resolved"


# 测试 7：falsy bug 修复 — 空列表 answers 应被显式写入（不与 None 混淆）
@pytest.mark.parametrize(
    "resume_answers, expected_answers",
    [
        ([], []),  # 用户明确提交空 → 写入 []
        (None, []),  # 跳过场景未提交 → 保留 builder 默认 []
        (
            [{"question": "Q", "answer": [{"label": "A", "description": None}]}],
            [{"question": "Q", "answer": [{"label": "A", "description": None}]}],
        ),
    ],
)
def test_build_run_finished_payload_distinguishes_empty_list_from_none(resume_answers, expected_answers):
    interrupts = [
        {
            "id": "x",
            "reason": "aidev:user_question",
            "metadata": {"status": "pending", "questions": []},
        }
    ]
    _, result = AskUserQuestionOutcomeBuilder.build_run_finished_payload(
        interrupts, "resolved", resume_answers=resume_answers
    )
    assert result["payload"]["answers"] == expected_answers


# 测试 8：falsy bug 修复 — upgrade_content_to_success 同样区分 [] 与 None
@pytest.mark.parametrize(
    "resume_answers, expected_answers",
    [
        ([], []),
        (None, []),
        (
            [{"question": "Q", "answer": [{"label": "A", "description": None}]}],
            [{"question": "Q", "answer": [{"label": "A", "description": None}]}],
        ),
    ],
)
def test_upgrade_content_to_success_distinguishes_empty_list_from_none(resume_answers, expected_answers):
    content = {
        "outcome": {
            "type": "interrupt",
            "interrupts": [
                {
                    "id": "x",
                    "reason": "aidev:user_question",
                    "metadata": {"status": "pending", "questions": []},
                }
            ],
        }
    }
    upgraded = AskUserQuestionOutcomeBuilder.upgrade_content_to_success(
        content, "cancelled", resume_answers=resume_answers
    )
    assert upgraded["result"]["payload"]["answers"] == expected_answers
    assert upgraded["outcome"]["interrupts"][0]["metadata"]["status"] == "cancelled"


# 测试 9：ASK_USER_QUESTION_SKIPPED_CONTENT 常量存在且非空
def test_skipped_content_constant_exists():
    assert isinstance(ASK_USER_QUESTION_SKIPPED_CONTENT, str)
    assert "已跳过" in ASK_USER_QUESTION_SKIPPED_CONTENT


# 测试 10：parse_resume_answers 纯协议解析
@pytest.mark.parametrize(
    "resume_items, expected",
    [
        # list 形态（标准 ResumeItem）
        (
            [{"interruptId": "x", "payload": {"answers": [{"question": "Q", "answer": []}]}}],
            [{"question": "Q", "answer": []}],
        ),
        # dict 形态（单条）
        ({"interruptId": "x", "payload": {"answers": []}}, []),
        # 空 answers
        ([{"interruptId": "x", "payload": {"answers": []}}], []),
        # None 入参
        (None, None),
        # 无 payload → 返回 first dict 本身
        ([{"interruptId": "x"}], {"interruptId": "x"}),
    ],
)
def test_parse_resume_answers(resume_items, expected):
    assert parse_resume_answers(resume_items) == expected


# ---------------------------------------------------------------------- #
# Task 2：AskUserQuestionTarget 模型 + get_ask_user_question_target + prepare
# ---------------------------------------------------------------------- #


def test_target_default_reason_and_coerce():
    """AskUserQuestionTarget 默认 interrupt_reason == ASK_USER_QUESTION_REASON；dict→Item coerce。"""
    target = AskUserQuestionTarget(questions=[{"question": "确认？", "multiSelect": False}])
    assert target.interrupt_reason == ASK_USER_QUESTION_REASON
    assert isinstance(target.questions[0], AskUserQuestionItem)
    assert target.questions[0].question == "确认？"
    assert target.questions[0].multiSelect is False


def test_target_new_field_defaults():
    """Test A：AskUserQuestionTarget 新字段默认值 — message/toolCallId/expiresAt 空串。"""
    target = AskUserQuestionTarget(questions=[{"question": "Q"}])
    assert target.message == ""
    assert target.toolCallId == ""
    assert target.expiresAt == ""
    assert target.interrupt_reason == ASK_USER_QUESTION_REASON
    # extra="ignore" 仍忽略注入的 reason extra 键（reason 不是 target 字段，保持忽略）
    assert "reason" not in target.model_dump()


def test_target_ignores_extra_keys():
    """AskUserQuestionTarget 的 toolCallId 现为合法字段，注入后作为真字段被接受。"""
    target = AskUserQuestionTarget.model_validate(
        {"questions": [{"question": "Q"}], "reason": ASK_USER_QUESTION_REASON, "toolCallId": "q1"}
    )
    assert target.interrupt_reason == ASK_USER_QUESTION_REASON
    # toolCallId 已从 extra 键升级为真字段，注入后保留
    assert target.toolCallId == "q1"


# ---------------------------------------------------------------------- #
# 注：get_ask_user_question_target 已随 47-04 D-12 删除（ask_user 工具本体直调
# interrupt()，自建 target 已内联到 aidev_agent/core/tools/ask_user_question.py）。
# 其行为（tool_call → AskUserQuestionTarget 构造 / 非法 questions 抛 ValidationError /
# message/toolCallId/expiresAt 确定性填充）由 tests/core/nodes/tool/approval_wrapper.py
# 的 TestInterruptWrapperUserQuestion 与 tests/core/interrupt/
# test_ask_user_question_interrupt_trigger.py 覆盖。
# ---------------------------------------------------------------------- #


def test_prepare_target_shape_builds_single_payload():
    """Test I：target 形态（含 interrupt_reason + 注入 id + message/toolCallId/expiresAt）→ dict 手术。

    260828-p3w：prepare 接收 intr 对象，dict 手术就地作用于 intr.value，返回同一 intr 对象。
    """
    handler = AskUserQuestionHandler()
    value = {
        "questions": [{"question": "确认？", "multiSelect": False}],
        "interrupt_reason": ASK_USER_QUESTION_REASON,
        "message": "需要用户回答：确认？",
        "toolCallId": "q1",
        "expiresAt": "2026-08-28T00:00:00+00:00",
    }
    intr = SimpleNamespace(value=value, id="ef37fae67cf416388c5253cf66595554")
    payload = handler.prepare(intr)
    assert payload is intr, "prepare 应返回同一 intr 对象"
    payload = intr.value
    # pop interrupt_reason → reason 设置
    assert payload["reason"] == ASK_USER_QUESTION_REASON
    assert "interrupt_reason" not in payload
    # value dict 无 id（零处理，id 只活在 intr.id）
    assert "id" not in payload
    # metadata{type,status,questions,toolArgs（D-15：镜像 approval enrich，承载 questions 参数）}
    assert payload["metadata"] == {
        "type": "ask_user_question",
        "status": "pending",
        "questions": [{"question": "确认？", "multiSelect": False}],
        "toolArgs": {"questions": [{"question": "确认？", "multiSelect": False}]},
    }
    # message/toolCallId/expiresAt 保留（target 已填充）
    assert payload["message"] == "需要用户回答：确认？"
    assert payload["toolCallId"] == "q1"
    assert payload["expiresAt"] == "2026-08-28T00:00:00+00:00"


def test_prepare_full_shape_passthrough():
    """Test J：完整形态（无 interrupt_reason 键）→ 原样返回（旧 checkpoint 兼容）。"""
    handler = AskUserQuestionHandler()
    full = {
        "id": "int-question-x",
        "reason": ASK_USER_QUESTION_REASON,
        "toolCallId": "q1",
        "metadata": {"questions": [{"question": "Q"}]},
    }
    intr = SimpleNamespace(value=full, id="int-question-x")
    assert handler.prepare(intr) is intr


def test_prepare_invalid_questions_metadata_keeps_running():
    """含 interrupt_reason 键但 questions 非 list → dict 手术仍执行，questions=[] 兜底，不抛异常。"""
    handler = AskUserQuestionHandler()
    bad = {
        "questions": "not-a-list",
        "interrupt_reason": ASK_USER_QUESTION_REASON,
        "message": "需要用户回答",
        "toolCallId": "q1",
    }
    intr = SimpleNamespace(value=bad, id="x")
    result = handler.prepare(intr)
    assert result is intr
    assert result.value["reason"] == ASK_USER_QUESTION_REASON
    assert result.value["metadata"]["questions"] == []
    assert "id" not in result.value


# ---------------------------------------------------------------------------
# 回归（2026-09-02 快照卡消失）：_upgrade_interrupt 必须同步记录消息级 status
# ---------------------------------------------------------------------------
#
# 根因链：账本 interrupt 记录建卡时 status="pending"，content 升级为 resolved
# 终态后 status 未同步 → 首帧 MESSAGES_SNAPSHOT（数据源=本账本）携带
# status=pending + content=resolved 的卡 → 前端 getCurrentLoadingMessage()
# 命中该卡，流末尾裸 RUN_FINISHED(success) 整体覆写 content 丢 result →
# 回显卡卸载。修复：content 升级成功时同步 interrupt.status="complete"。


def _pending_interrupt_record() -> "ChatPrompt":
    """构造建卡形态的账本 interrupt 记录（生产适配层拍平形态）。

    - ``status="pending"``（行 status）+ bp 内嵌回嵌副本 ``status: "pending"``
      （migration 回嵌，快照转换器 ``_read_field`` 是 bp 优先读取）；
    - **questions 在顶层 extras 而非 bp**——适配层把 ``property.builtin_property``
      拍平到行顶层（2026-09-02 pdb 实证），``_handle_skip_path`` 须有 extras 回退，
      否则 skipped_answers=[] → 回答内容卡为空。
    """
    questions = [
        {
            "header": "偏好调查",
            "multiSelect": False,
            "question": "您更喜欢哪种类型的助手服务？",
            "options": [{"label": "信息查询", "description": "帮助您查询信息"}],
        }
    ]
    payload = AskUserQuestionHandler().build_payload(questions=questions, tool_call_id="call_fix")
    return ChatPrompt(
        role="interrupt",
        content={"outcome": {"type": "interrupt", "interrupts": [payload]}},
        status="pending",
        builtin_property={
            "message_id": payload["id"],
            "type": "ask_user_question",
            "interrupt_id": payload["id"],
            "reason": payload["reason"],
            "tool_call_id": "call_fix",
            "status": "pending",
        },
        questions=questions,
    )


def test_answer_path_syncs_record_status_to_complete():
    """答题路径：content 升级终态后，记录消息级 status 必须顶层 + bp 双写同步为 complete。"""
    handler = AskUserQuestionHandler()
    record = _pending_interrupt_record()

    result = handler._handle_answer_path(
        record,
        [
            {
                "question": "您更喜欢哪种类型的助手服务？",
                "multiSelect": False,
                "answer": [{"label": "信息查询", "description": "帮助您查询信息"}],
            }
        ],
        "turn-1",
    )

    assert result["upgraded_content"] is not None
    assert record.status == "complete"
    assert record.builtin_property["status"] == "complete"
    assert record.content["outcome"]["type"] == "success"
    assert record.content["result"]["status"] == "resolved"


def test_skip_path_syncs_record_status_to_complete():
    """跳过路径：content 升级为 CANCELLED 终态后，记录 status 同样为 complete。"""
    handler = AskUserQuestionHandler()
    record = _pending_interrupt_record()

    handler._handle_skip_path(record, "turn-1")

    assert record.status == "complete"
    assert record.builtin_property["status"] == "complete"
    assert record.content["outcome"]["type"] == "success"
    assert record.content["result"]["status"] == "cancelled"


def test_skip_path_builds_skipped_answers_from_top_level_questions():
    """跳过路径回归：questions 在顶层 extras（适配层拍平形态）时 skipped_answers 不得为空。

    只读 bp.questions 会得到 [] → result.payload.answers=[] → 前端"回答内容"卡
    只剩标题无内容。修复后经 extras 回退取到 questions，逐题生成
    label="skipped" + description=ASK_USER_QUESTION_SKIPPED_CONTENT 的答案。
    """
    handler = AskUserQuestionHandler()
    record = _pending_interrupt_record()

    result = handler._handle_skip_path(record, "turn-1")

    answers = result["skipped_answers"]
    assert answers, "skipped_answers 不得为空（questions 经顶层 extras 回退取到）"
    assert answers[0]["question"] == "您更喜欢哪种类型的助手服务？"
    assert answers[0]["answer"] == [{"label": "skipped", "description": ASK_USER_QUESTION_SKIPPED_CONTENT}]
    # 终态 content 的 payload.answers 同步携带 skipped 答案（前端回答内容卡数据源）
    payload_answers = record.content["result"]["payload"]["answers"]
    assert payload_answers == answers


def test_snapshot_conversion_emits_complete_status_after_answer():
    """生产不变量：答题后账本经快照转换，卡片消息 status 不得为 pending。

    若为 pending，前端把 resolved 卡当 loading 消息，流末尾裸
    RUN_FINISHED(success) 覆写 content 丢 result → 回显卡消失。
    """
    handler = AskUserQuestionHandler()
    record = _pending_interrupt_record()
    handler._handle_answer_path(
        record,
        [
            {
                "question": "您更喜欢哪种类型的助手服务？",
                "multiSelect": False,
                "answer": [{"label": "信息查询", "description": "帮助您查询信息"}],
            }
        ],
        "turn-1",
    )

    messages = contents_to_agui_messages([record.model_dump()])

    assert len(messages) == 1
    assert messages[0].status == "complete"
