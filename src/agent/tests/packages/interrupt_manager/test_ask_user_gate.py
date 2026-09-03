# -*- coding: utf-8 -*-
"""GATE-02：``AskUserQuestionHandler.query_resume_status`` 只读门禁方法单测。

门禁方法按当前 pending interrupt id（经 ``interrupt_id_of`` 提取）定位其**专属**
已答记录，返回对偶单元层门禁契约 ``{"action": "resolved"/"not_ready",
"resume_value": ...}``。resume_value 从已答记录的 ``result.payload.answers``
重建（DB 权威，Pitfall 4），绝不被其他中断终态污染误放行（per-pending 定位，
Pitfall 2 防线）。

**桩注入方式**：门禁方法在方法内构造 ``ApprovalStateHandler(resource_manager=...)``
并调用 ``_list_interrupt_records`` / ``_extract_interrupts_from_content``。测试用
``monkeypatch`` 替换 ``ApprovalStateHandler._list_interrupt_records`` 类方法使其
返回桩记录（忽略真实 RM / DB），``_extract_interrupts_from_content`` 保持真实的
content 解析（验证桩记录的 content 结构可被真实解析器抽取 interrupts）。
"""

from aidev_agent.packages.interrupt_manager.approval import ApprovalStateHandler
from aidev_agent.packages.interrupt_manager.ask_user_question import AskUserQuestionHandler

# ---------------------------------------------------------------------- #
# 桩记录构造
# ---------------------------------------------------------------------- #


def _resolved_record(interrupt_id="int-q", answers=None, tool_call_id=None):
    """ask_user 已答终态记录（outcome.type=success，result.payload.answers 落库权威）。"""
    element = {"id": interrupt_id, "reason": "aidev:user_question"}
    if tool_call_id:
        element["toolCallId"] = tool_call_id
    return {
        "role": "interrupt",
        "content": {
            "outcome": {
                "type": "success",
                "interrupts": [element],
            },
            "result": {
                "id": interrupt_id,
                "interruptId": interrupt_id,
                "status": "resolved",
                "payload": {"answers": answers if answers is not None else ["是"]},
            },
        },
    }


def _pending_record(interrupt_id="int-q"):
    """ask_user 未答 pending 记录（outcome.type=interrupt，无 result）。"""
    return {
        "role": "interrupt",
        "content": {
            "outcome": {"type": "interrupt", "interrupts": [{"id": interrupt_id, "reason": "aidev:user_question"}]}
        },
    }


def _install_records(monkeypatch, records):
    """monkeypatch ``ApprovalStateHandler._list_interrupt_records`` 返回桩记录。"""

    def _fake_list_records(self, session_code):
        return records

    monkeypatch.setattr(ApprovalStateHandler, "_list_interrupt_records", _fake_list_records)


# ---------------------------------------------------------------------- #
# 场景 1：已答 → resolved + Pitfall 4 answers 断言
# ---------------------------------------------------------------------- #


def test_query_resume_status_resolved_reads_payload_answers(monkeypatch):
    """已答记录 → action=resolved，resume_value 从 result.payload.answers 重建（DB 权威）。"""
    _install_records(monkeypatch, [_resolved_record("int-q", answers=["是"])])

    handler = AskUserQuestionHandler()
    result = handler.query_resume_status("s1", {"id": "int-q"})

    assert result["action"] == "resolved"
    assert result["resume_value"] == {
        "interruptId": "int-q",
        "status": "resolved",
        "payload": {"answers": ["是"]},
    }
    # Pitfall 4 防线：answers 必须取自 result.payload.answers（DB 权威落点），
    # 而非 outcome.interrupts[0].metadata（首跑落库时 metadata 无 answers，恒空）。
    assert result["resume_value"]["payload"]["answers"] == ["是"]


# ---------------------------------------------------------------------- #
# 场景 2：记录仍为 interrupt 形态（未答）→ not_ready
# ---------------------------------------------------------------------- #


def test_query_resume_status_pending_record_not_ready(monkeypatch):
    """记录仍为 interrupt 形态（未答）→ action=not_ready，resume_value is None。"""
    _install_records(monkeypatch, [_pending_record("int-q")])

    handler = AskUserQuestionHandler()
    result = handler.query_resume_status("s1", {"id": "int-q"})

    assert result["action"] == "not_ready"
    assert result["resume_value"] is None


# ---------------------------------------------------------------------- #
# 场景 3：无任何匹配记录 → not_ready
# ---------------------------------------------------------------------- #


def test_query_resume_status_no_records_not_ready(monkeypatch):
    """无任何匹配记录（空 records 列表）→ action=not_ready，resume_value is None。"""
    _install_records(monkeypatch, [])

    handler = AskUserQuestionHandler()
    result = handler.query_resume_status("s1", {"id": "int-q"})

    assert result["action"] == "not_ready"
    assert result["resume_value"] is None


# ---------------------------------------------------------------------- #
# 场景 4：per-pending 定位（Pitfall 2 防线）
# ---------------------------------------------------------------------- #


def test_query_resume_status_per_pending_locates_own_record(monkeypatch):
    """per-pending 定位：最新一条是**其他**中断终态，当前 pending 未被答 → 不被污染误放行。

    场景：最新一条记录是 ``int-other`` 的终态（恰为 ``int-q`` 之后写库），当前
    pending 是 ``int-q`` 的 pending 记录。旧「会话级最新一条」语义会误读
    ``int-other`` 的终态放行；per-pending 语义按 ``outcome.interrupts[*].id ==
    pending_id`` 定位 → 找到 ``int-q`` 的 pending 记录 → not_ready。
    """
    _install_records(
        monkeypatch,
        [
            _resolved_record("int-other", answers=["是"]),  # 其他中断终态（最新，reversed 先遍历）
            _pending_record("int-q"),  # 当前 pending（旧）
        ],
    )

    handler = AskUserQuestionHandler()
    result = handler.query_resume_status("s1", {"id": "int-q"})

    assert result["action"] == "not_ready"
    assert result["resume_value"] is None


def test_query_resume_status_per_pending_resolves_own_terminal(monkeypatch):
    """per-pending 定位正向：当前 pending 的专属记录已是终态 → resolved（放行本中断）。"""
    _install_records(
        monkeypatch,
        [
            _resolved_record("int-other", answers=["是"]),  # 其他中断终态（最新）
            _resolved_record("int-q", answers=["确认"]),  # 当前 pending 已答（旧）
        ],
    )

    handler = AskUserQuestionHandler()
    result = handler.query_resume_status("s1", {"id": "int-q"})

    assert result["action"] == "resolved"
    assert result["resume_value"] == {
        "interruptId": "int-q",
        "status": "resolved",
        "payload": {"answers": ["确认"]},
    }


def test_query_resume_status_matches_by_tool_call_id_when_value_has_no_id(monkeypatch):
    """per-pending 定位：pending value 无 id（id 与 value 分离）时按 toolCallId 兜底匹配。

    编排层 ``_get_interrupts_from_tasks`` 返回 value dict（id 只活在 ``intr.id``），
    ask_user target 形态 value 无 id 但必有 toolCallId——镜像 approval
    ``query_approval_info_for_interrupt`` 按 toolCallId 定位专属已答记录。
    resume_value.interruptId 取匹配 DB 元素的真实 id（非 pending 空 id）。
    """
    _install_records(
        monkeypatch,
        [_resolved_record("int-q", answers=["是"], tool_call_id="tc-q")],
    )

    handler = AskUserQuestionHandler()
    # 真实图 value dict：无 id，仅 toolCallId（target 形态）
    result = handler.query_resume_status("s1", {"toolCallId": "tc-q", "reason": "aidev:user_question"})

    assert result["action"] == "resolved", "无 id 的 pending 应按 toolCallId 兜底定位到专属已答记录"
    assert result["resume_value"] == {
        "interruptId": "int-q",  # 取匹配 DB 元素 id（非 pending 空 id）
        "status": "resolved",
        "payload": {"answers": ["是"]},
    }
