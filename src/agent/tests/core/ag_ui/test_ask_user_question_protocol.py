# -*- coding: utf-8 -*-
"""ask_user_question 协议层纯函数单元测试。

覆盖 抽出的纯函数的边界值：
build_updated_builtin_property / build_skipped_answers /
filter_ask_user_question_interrupts / parse_resume_answers / extract_message_id。
"""

import json
from types import SimpleNamespace

import pytest
from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_REASON,
    ASK_USER_QUESTION_SKIPPED_CONTENT,
    AskUserQuestionMetadata,
    InterruptStatus,
    build_skipped_answers,
    build_updated_builtin_property,
    extract_message_id,
    filter_ask_user_question_interrupts,
    parse_resume_answers,
)

# ------------------------------------------------------------------ #
# build_updated_builtin_property
# ------------------------------------------------------------------ #


def test_build_updated_builtin_property_basic():
    db_item = {"property": {"builtin_property": {"existing": "val"}}}
    result = build_updated_builtin_property(db_item, "int-1", "resolved")
    assert result["existing"] == "val"
    assert result["status"] == "resolved"
    assert result["message_id"] == "int-1"
    assert result["interrupt_id"] == "int-1"
    assert result["reason"] == ASK_USER_QUESTION_REASON


def test_build_updated_builtin_property_no_property():
    db_item = {}
    result = build_updated_builtin_property(db_item, "int-1", "resolved")
    assert result["status"] == "resolved"
    assert result["interrupt_id"] == "int-1"


def test_build_updated_builtin_property_json_string_property():
    db_item = {"property": json.dumps({"builtin_property": {"foo": "bar"}})}
    result = build_updated_builtin_property(db_item, "int-1", "resolved")
    assert result["foo"] == "bar"
    assert result["status"] == "resolved"


def test_build_updated_builtin_property_does_not_mutate_input():
    db_item = {"property": {"builtin_property": {"existing": "val"}}}
    build_updated_builtin_property(db_item, "int-1", "resolved")
    # db_item 的 builtin_property 不应被修改
    assert "status" not in db_item["property"]["builtin_property"]


def test_build_updated_builtin_property_property_invalid_json():
    """property 为无效 JSON 字符串时回退到空 dict 再追加字段。"""
    db_item = {"property": "not json"}
    result = build_updated_builtin_property(db_item, "int-id", "resolved")
    assert result["status"] == "resolved"
    assert result["reason"] == ASK_USER_QUESTION_REASON


def test_build_updated_builtin_property_builtin_not_dict():
    """builtin_property 非 dict 时回退到空 dict。"""
    db_item = {"property": {"builtin_property": "not a dict"}}
    result = build_updated_builtin_property(db_item, "int-id", "resolved")
    assert result["status"] == "resolved"
    assert result["message_id"] == "int-id"


def test_build_updated_builtin_property_cancelled_status():
    """status=cancelled 时正确写入。"""
    result = build_updated_builtin_property({}, "int-id", "cancelled")
    assert result["status"] == "cancelled"


# ------------------------------------------------------------------ #
# filter_ask_user_question_interrupts
# ------------------------------------------------------------------ #


def test_filter_ask_user_question_interrupts_empty():
    assert filter_ask_user_question_interrupts([]) == []


def test_filter_ask_user_question_interrupts_none():
    assert filter_ask_user_question_interrupts(None) == []


def test_filter_ask_user_question_interrupts_match():
    intr_value = {"reason": ASK_USER_QUESTION_REASON, "id": "int-1"}
    task = SimpleNamespace(
        interrupts=[SimpleNamespace(value=intr_value)],
    )
    result = filter_ask_user_question_interrupts([task])
    assert len(result) == 1
    assert result[0]["id"] == "int-1"


def test_filter_ask_user_question_interrupts_json_string_value():
    intr_value = json.dumps({"reason": ASK_USER_QUESTION_REASON, "id": "int-1"})
    task = SimpleNamespace(
        interrupts=[SimpleNamespace(value=intr_value)],
    )
    result = filter_ask_user_question_interrupts([task])
    assert len(result) == 1
    assert result[0]["id"] == "int-1"


def test_filter_ask_user_question_interrupts_wrong_reason():
    task = SimpleNamespace(
        interrupts=[SimpleNamespace(value={"reason": "aidev:tool_approval"})],
    )
    assert filter_ask_user_question_interrupts([task]) == []


def test_filter_ask_user_question_interrupts_no_interrupts_attr():
    task = SimpleNamespace()
    assert filter_ask_user_question_interrupts([task]) == []


def test_filter_ask_user_question_interrupts_task_interrupts_none():
    """task.interrupts 为 None 时跳过。"""
    task = SimpleNamespace(interrupts=None)
    assert filter_ask_user_question_interrupts([task]) == []


def test_filter_ask_user_question_interrupts_invalid_json_string():
    """intr.value 为无效 JSON 字符串时跳过。"""
    task = SimpleNamespace(interrupts=[SimpleNamespace(value="not json")])
    assert filter_ask_user_question_interrupts([task]) == []


def test_filter_ask_user_question_interrupts_multiple_tasks():
    """多个 task 混合 reason，只保留 ASK_USER_QUESTION_REASON。"""
    v1 = {"reason": ASK_USER_QUESTION_REASON, "id": "q1"}
    v2 = {"reason": "other", "id": "x1"}
    v3 = {"reason": ASK_USER_QUESTION_REASON, "id": "q2"}
    tasks = [
        SimpleNamespace(interrupts=[SimpleNamespace(value=v1)]),
        SimpleNamespace(interrupts=[SimpleNamespace(value=v2)]),
        SimpleNamespace(interrupts=[SimpleNamespace(value=v3)]),
    ]
    result = filter_ask_user_question_interrupts(tasks)
    assert len(result) == 2
    assert result[0]["id"] == "q1"
    assert result[1]["id"] == "q2"


def test_filter_ask_user_question_interrupts_multiple_per_task():
    """单个 task 含多个匹配 interrupt 时全部保留。"""
    v1 = {"reason": ASK_USER_QUESTION_REASON, "id": "q1"}
    v2 = {"reason": ASK_USER_QUESTION_REASON, "id": "q2"}
    task = SimpleNamespace(interrupts=[SimpleNamespace(value=v1), SimpleNamespace(value=v2)])
    result = filter_ask_user_question_interrupts([task])
    assert len(result) == 2


# ------------------------------------------------------------------ #
# parse_resume_answers
# ------------------------------------------------------------------ #


def test_parse_resume_answers_none():
    assert parse_resume_answers(None) is None


def test_parse_resume_answers_list_with_payload_answers():
    resume_value = [{"interruptId": "x", "status": "resolved", "payload": {"answers": ["a"]}}]
    assert parse_resume_answers(resume_value) == ["a"]


def test_parse_resume_answers_list_with_payload_no_answers():
    resume_value = [{"payload": "direct-value"}]
    assert parse_resume_answers(resume_value) == "direct-value"


def test_parse_resume_answers_list_first_not_dict():
    resume_value = ["raw-answer"]
    assert parse_resume_answers(resume_value) == "raw-answer"


def test_parse_resume_answers_dict_with_answers():
    assert parse_resume_answers({"answers": ["a", "b"]}) == ["a", "b"]


def test_parse_resume_answers_dict_with_payload():
    assert parse_resume_answers({"payload": {"answers": ["c"]}}) == ["c"]


def test_parse_resume_answers_dict_no_answers():
    assert parse_resume_answers({"foo": "bar"}) == {"foo": "bar"}


def test_parse_resume_answers_scalar():
    assert parse_resume_answers(42) == 42
    assert parse_resume_answers("hello") == "hello"


def test_parse_resume_answers_empty_list():
    """空列表返回空列表（非 None）。"""
    assert parse_resume_answers([]) == []


# ------------------------------------------------------------------ #
# InterruptStatus
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "member, expected",
    [
        (InterruptStatus.PENDING, "pending"),
        (InterruptStatus.RESOLVED, "resolved"),
        (InterruptStatus.CANCELLED, "cancelled"),
    ],
)
def test_interrupt_status_str_value(member, expected):
    """(str, Enum) 成员的 str 值等于字面量。"""
    assert member.value == expected
    assert member == expected  # str 继承


def test_interrupt_status_pydantic_serialization():
    """Pydantic v2 序列化输出字符串值（非枚举名）— Pitfall 3 验证。"""
    m = AskUserQuestionMetadata(questions=[])
    assert m.status == InterruptStatus.PENDING
    # model_dump_json 输出 "pending" 而非 "InterruptStatus.PENDING"
    dumped = m.model_dump_json()
    assert '"status":"pending"' in dumped


# ------------------------------------------------------------------ #
# extract_message_id ( ②)
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "upgraded, expected",
    [
        ({"result": {"interruptId": "id-1"}, "outcome": {"interrupts": [{"id": "id-2"}]}}, "id-1"),
        ({"result": {}, "outcome": {"interrupts": [{"id": "id-2"}]}}, "id-2"),
        ({"result": {}, "outcome": {"interrupts": []}}, ""),
        ({}, ""),
    ],
)
def test_extract_message_id(upgraded, expected):
    """result.interruptId 优先 → outcome.interrupts[0].id 次之 → 空串兜底。"""
    assert extract_message_id(upgraded) == expected


# ------------------------------------------------------------------ #
# build_skipped_answers ( ③)
# ------------------------------------------------------------------ #


def test_build_skipped_answers_basic():
    """正常构造：每个 question 生成 label="skipped" 的 answer。"""
    questions = [{"question": "Q1", "multiSelect": False}]
    result = build_skipped_answers(questions)
    assert len(result) == 1
    assert result[0]["question"] == "Q1"
    assert result[0]["multiSelect"] is False
    assert result[0]["answer"][0]["label"] == "skipped"
    assert result[0]["answer"][0]["description"] == ASK_USER_QUESTION_SKIPPED_CONTENT


def test_build_skipped_answers_empty():
    assert build_skipped_answers([]) == []


def test_build_skipped_answers_filters_non_dict():
    """过滤非 dict 元素。"""
    result = build_skipped_answers([{"question": "Q"}, "not-a-dict", None])
    assert len(result) == 1
    assert result[0]["question"] == "Q"


def test_build_skipped_answers_question_missing():
    """question 缺失默认空串。"""
    result = build_skipped_answers([{"multiSelect": True}])
    assert result[0]["question"] == ""


# ------------------------------------------------------------------ #
# D-07：InterruptHandler Protocol 方法集定型
# ------------------------------------------------------------------ #


def test_stream_interrupt_handler_protocol_method_set():
    """D-07/48-01：Protocol 方法集定型为 prepare / query_resume_status / on_resume / extract_builtin_property。

    Phase 48（48-01）重定义 ``on_resume`` 为**必需写路径**（新签名
    ``on_resume(resume, *, interrupt_messages, **ctx) -> None``，D-05/D-16），
    ``on_resume`` 重入 Protocol 强制集；``consume_resume`` 已删（职责收编进
    on_resume，D-16），不进 Protocol。
    """
    from aidev_agent.packages.interrupt_manager.types import InterruptHandler

    required = {"prepare", "query_resume_status", "on_resume", "extract_builtin_property"}
    members = {name for name in dir(InterruptHandler) if not name.startswith("_")}
    assert required.issubset(members), f"Protocol 缺少必需方法: {required - members}"
    assert "consume_resume" not in members, "consume_resume 已删（D-16），不进 Protocol"


def test_ask_user_handler_implements_dual_capability():
    """D-06/48-01：AskUserQuestionHandler 双能力——query_resume_status（门禁）+ on_resume（写）。"""
    from aidev_agent.packages.interrupt_manager.ask_user_question import AskUserQuestionHandler

    handler = AskUserQuestionHandler()
    assert callable(getattr(handler, "query_resume_status", None)), "ask_user 必须实现 query_resume_status 只读门禁"
    assert callable(getattr(handler, "on_resume", None)), "ask_user 必须实现 on_resume 写路径（D-05）"
    assert not callable(getattr(handler, "consume_resume", None)), "consume_resume 已删，职责收编进 on_resume（D-16）"


def test_approval_handler_implements_query_resume_status_gate():
    """D-07/48-01：ApprovalHandler 实现 query_resume_status 只读门禁 + on_resume 空实现（无 consume_resume）。"""
    from aidev_agent.packages.interrupt_manager.approval import ApprovalHandler

    handler = ApprovalHandler()
    assert callable(getattr(handler, "query_resume_status", None)), "approval 必须实现 query_resume_status 只读门禁"
    assert callable(getattr(handler, "on_resume", None)), (
        "approval 必须实现 on_resume 空实现（D-05，审批终态平台侧写，agent 侧纯读）"
    )
    assert not callable(getattr(handler, "consume_resume", None)), "approval 无 consume_resume（D-16 已删）"
