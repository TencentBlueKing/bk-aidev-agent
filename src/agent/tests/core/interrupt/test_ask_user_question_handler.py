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

import pytest
from aidev_agent.core.ag_ui.ask_user_question import (
    ASK_USER_QUESTION_REASON,
    ASK_USER_QUESTION_SKIPPED_CONTENT,
    AskUserQuestionHandler,
    AskUserQuestionOutcomeBuilder,
    parse_resume_answers,
)


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


# 测试 11：_normalize_questions 兼容 LLM 输出的各种脏结构
# 覆盖 str / list[str] / dict / 混合列表 / None / 非法项，防御 build_payload 崩溃。
@pytest.mark.parametrize(
    "raw, expected_count, first_question",
    [
        (None, 0, None),  # None → 空列表
        ([], 0, None),  # 空 list
        ("单字符串", 1, "单字符串"),  # 整个 str（LLM 退化输出）
        (["问题1", "问题2"], 2, "问题1"),  # list of str
        ([{"question": "Q1"}], 1, "Q1"),  # 合法 dict list（原样保留）
        ([{"question": "Q1"}, "Q2"], 2, "Q1"),  # 混合 dict + str
        ({"question": "solo"}, 1, "solo"),  # 单 dict（未包 list）
        ([None, 123, "有效", {"question": "也有效"}], 2, "有效"),  # 混合非法项，静默丢弃
        (["   ", "有效"], 1, "有效"),  # 空白 str 丢弃
    ],
)
def test_normalize_questions_various_shapes(raw, expected_count, first_question):
    out = AskUserQuestionHandler._normalize_questions(raw)
    assert len(out) == expected_count
    if expected_count > 0:
        assert out[0]["question"] == first_question


# 测试 11.1：str 项被包装成完整协议字段（header/multiSelect/options 补齐默认值）
# dict 项则原样保留（不强改 LLM 已给出的合法 dict）—— 这是刻意设计。
def test_normalize_questions_wraps_str_into_full_dict():
    out = AskUserQuestionHandler._normalize_questions(["问题A"])
    assert len(out) == 1
    # str 转 dict 时必带协议要求的默认字段
    assert out[0] == {"question": "问题A", "header": "", "multiSelect": False, "options": []}


def test_normalize_questions_preserves_dict_as_is():
    # LLM 已给出合法 dict（哪怕只带 question），不强填其他字段避免覆盖 LLM 意图
    raw = [{"question": "Q1"}]
    out = AskUserQuestionHandler._normalize_questions(raw)
    assert out == [{"question": "Q1"}]  # 原样保留


# 测试 12：_first_question_text 缺字段回落链
@pytest.mark.parametrize(
    "questions, expected",
    [
        ([], ""),
        ([{"question": "Q"}], "Q"),
        ([{"header": "H"}], "H"),  # 缺 question → 回落 header
        ([{"question": "", "header": "H"}], "H"),  # question 空串 → 回落 header
        ([{}], ""),  # 都缺 → 空串
        (["直接字符串"], "直接字符串"),  # str 项直接返回
    ],
)
def test_first_question_text_fallback(questions, expected):
    assert AskUserQuestionHandler._first_question_text(questions) == expected


# 测试 13：build_payload 接受脏 questions 不再 500
# 回归测试 —— 修前 questions=["纯字符串问题"] 会触发
# TypeError: string indices must be integers。
def test_build_payload_accepts_dirty_questions_without_crash():
    handler = AskUserQuestionHandler()
    payload = handler.build_payload(questions=["今天天气怎么样？"], tool_call_id="call_x")

    assert payload["reason"] == "aidev:user_question"
    assert payload["toolCallId"] == "call_x"
    # 归一化后的 questions 必为标准 dict 形态
    normalized = payload["metadata"]["questions"]
    assert len(normalized) == 1
    assert normalized[0]["question"] == "今天天气怎么样？"
    assert normalized[0]["header"] == ""
    assert normalized[0]["multiSelect"] is False
    assert normalized[0]["options"] == []
    # message 用归一化后的首个 question
    assert payload["message"] == "需要用户回答：今天天气怎么样？"


# 测试 14：build_payload 空 questions 走"需要用户回答"兜底 message
def test_build_payload_empty_questions_fallback_message():
    handler = AskUserQuestionHandler()
    payload = handler.build_payload(questions=[], tool_call_id="call_y")

    assert payload["message"] == "需要用户回答"
    assert payload["metadata"]["questions"] == []
    # 空 questions 时其他顶层字段仍应正常生成
    assert payload["reason"] == "aidev:user_question"
    assert payload["id"].startswith("int-question-call_y-")
    assert payload["expiresAt"] is not None


# 测试 15：build_payload 处理 dict 项缺 question 字段时 message 回落 header
def test_build_payload_message_falls_back_to_header_when_question_missing():
    handler = AskUserQuestionHandler()
    questions = [{"header": "选择环境", "multiSelect": False, "options": []}]
    payload = handler.build_payload(questions=questions, tool_call_id="call_z")

    assert payload["message"] == "需要用户回答：选择环境"
