# -*- coding: utf-8 -*-
"""``AskUserQuestionHandler`` 单元测试 — 覆盖 D-01/D-02/D-04~D-07/D-15/D-16。

测试覆盖 7 个行为用例：

1. ``ASK_USER_QUESTION_REASON == "aidev:user_question"``（D-01）
2. ``build_payload`` 基本字段（reason / id 前缀 / metadata.questions + expiresAt，无扩展字段）
3. ``build_payload`` 带 options + multiSelect（D-02，options 在 question 项内）
4. ``hydrate_resume`` 不覆写 payload（D-06 —— 只设置 status，不动 payload）
5. ``hydrate_resume`` 从 db_data 设置 status（D-06 —— status 来自 db_data）
6. ``AskUserQuestionOutcomeBuilder.build_run_finished_payload`` 终态形态构造（payload.answers + 顶层 status）
"""

from aidev_agent.core.ag_ui.ask_user_question import (
    ASK_USER_QUESTION_REASON,
    AskUserQuestionHandler,
    AskUserQuestionOutcomeBuilder,
)


# 测试 1：reason 常量（D-01）
def test_ask_user_question_reason_constant():
    assert ASK_USER_QUESTION_REASON == "aidev:user_question"


# 测试 2：build_payload 基本字段（D-02, D-04, D-05, D-15, D-16）
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
    # D-16: id 格式 int-question-{tool_call_id}-{uuid_hex}
    assert payload["id"].startswith("int-question-call_123-")
    assert payload["toolCallId"] == "call_123"
    assert payload["expiresAt"] is not None  # D-05 新增
    metadata = payload["metadata"]
    assert metadata["type"] == "ask_user_question"
    assert metadata["status"] == "pending"
    assert metadata["questions"] == questions
    # D-04 删除的字段不存在
    assert "required" not in metadata
    assert "other_enabled" not in metadata
    assert "multi_select" not in metadata  # 已移入 question 项（multiSelect）
    assert "default" not in metadata
    assert "placeholder" not in metadata


# 测试 3：build_payload 带 options + multiSelect（D-02，options 在 question 项内）
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


# 测试 4：hydrate_resume 不覆写 payload（D-06 —— 只设置 status，不动 payload）
def test_hydrate_resume_does_not_modify_payload():
    handler = AskUserQuestionHandler()
    resume_items = [
        {
            "interruptId": "x",
            "status": "resolved",
            "payload": {
                "answers": [
                    {"question": "Q", "answer": [{"label": "yes", "description": None}]}
                ]
            },
        }
    ]
    handler.hydrate_resume(resume_items, db_data=None)

    # payload 保持为 answers 结构，不被覆写
    assert resume_items[0]["payload"] == {
        "answers": [
            {"question": "Q", "answer": [{"label": "yes", "description": None}]}
        ]
    }


# 测试 5：hydrate_resume 从 db_data 设置 status（D-06 —— status 来自 db_data）
def test_hydrate_resume_sets_status_from_db_data():
    handler = AskUserQuestionHandler()
    resume_items = [
        {
            "interruptId": "x",
            "payload": {
                "answers": [
                    {"question": "Q", "answer": [{"label": "yes", "description": None}]}
                ]
            },
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
                "answers": [
                    {"question": "Q", "answer": [{"label": "A", "description": "选项A"}]}
                ],
            },
        }
    ]
    outcome, result = AskUserQuestionOutcomeBuilder.build_run_finished_payload(
        interrupts, "resolved"
    )

    assert outcome["type"] == "success"
    assert outcome["interrupts"][0]["metadata"]["status"] == "resolved"
    assert result["id"] == "x"
    assert result["interruptId"] == "x"
    # D-06/D-07: payload.answers 结构（协议 success 格式，非 metadata 透传）
    assert result["payload"]["answers"] == [
        {"question": "Q", "answer": [{"label": "A", "description": "选项A"}]}
    ]
    # 顶层 status（协议新增）
    assert result["status"] == "resolved"
