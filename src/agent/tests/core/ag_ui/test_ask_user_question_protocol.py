# -*- coding: utf-8 -*-
"""ask_user_question 协议层纯函数单元测试。

覆盖 Phase 14.1 D-01/D-03/D-04 抽出的 4 个纯函数的边界值：
find_pending_interrupt / build_updated_builtin_property /
filter_ask_user_question_interrupts / parse_resume_answers。
"""

import json
from types import SimpleNamespace

from aidev_agent.core.ag_ui.ask_user_question import (
    ASK_USER_QUESTION_REASON,
    build_updated_builtin_property,
    filter_ask_user_question_interrupts,
    find_pending_interrupt,
    parse_resume_answers,
)
from aidev_agent.enums import PromptRole

# ------------------------------------------------------------------ #
# find_pending_interrupt
# ------------------------------------------------------------------ #


def test_find_pending_interrupt_empty():
    assert find_pending_interrupt([], "int-1") is None


def test_find_pending_interrupt_match():
    raw_content = {
        "outcome": {
            "interrupts": [{"id": "int-1", "reason": ASK_USER_QUESTION_REASON}],
        },
    }
    item = {
        "id": 42,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": json.dumps(raw_content),
    }
    result = find_pending_interrupt([item], "int-1")
    assert result is not None
    content_id, raw_db_content, db_item = result
    assert content_id == 42
    assert raw_db_content["outcome"]["interrupts"][0]["id"] == "int-1"
    assert db_item is item


def test_find_pending_interrupt_wrong_role():
    item = {
        "id": 42,
        "role": "activity",
        "status": "pending",
        "content": "{}",
    }
    assert find_pending_interrupt([item], "int-1") is None


def test_find_pending_interrupt_wrong_status():
    item = {
        "id": 42,
        "role": PromptRole.INTERRUPT.value,
        "status": "complete",
        "content": "{}",
    }
    assert find_pending_interrupt([item], "int-1") is None


def test_find_pending_interrupt_wrong_id():
    raw_content = {
        "outcome": {
            "interrupts": [{"id": "int-other", "reason": ASK_USER_QUESTION_REASON}],
        },
    }
    item = {
        "id": 42,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": json.dumps(raw_content),
    }
    assert find_pending_interrupt([item], "int-1") is None


def test_find_pending_interrupt_reversed_order():
    """逆序遍历，最新记录优先。"""
    raw_old = {
        "outcome": {"interrupts": [{"id": "int-1", "reason": ASK_USER_QUESTION_REASON}]},
    }
    raw_new = {
        "outcome": {"interrupts": [{"id": "int-1", "reason": ASK_USER_QUESTION_REASON}]},
    }
    old_item = {
        "id": 1,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": json.dumps(raw_old),
    }
    new_item = {
        "id": 2,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": json.dumps(raw_new),
    }
    result = find_pending_interrupt([old_item, new_item], "int-1")
    assert result is not None
    content_id, _, _ = result
    assert content_id == 2  # 逆序，new_item 先匹配


def test_find_pending_interrupt_reason_not_ask_user_question():
    """匹配 id 但 reason 非 ASK_USER_QUESTION_REASON 时不返回。"""
    raw_content = {
        "outcome": {"interrupts": [{"id": "int-1", "reason": "aidev:tool_approval"}]},
    }
    item = {
        "id": 42,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": json.dumps(raw_content),
    }
    assert find_pending_interrupt([item], "int-1") is None


def test_find_pending_interrupt_content_not_json():
    """content 非 JSON 字符串时跳过该记录。"""
    item = {
        "id": 1,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": "not json",
    }
    assert find_pending_interrupt([item], "int-1") is None


def test_find_pending_interrupt_missing_interrupts_field():
    """outcome 缺少 interrupts 字段时跳过该记录。"""
    raw_content = {"outcome": {}}
    item = {
        "id": 1,
        "role": PromptRole.INTERRUPT.value,
        "status": "pending",
        "content": json.dumps(raw_content),
    }
    assert find_pending_interrupt([item], "int-1") is None


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
