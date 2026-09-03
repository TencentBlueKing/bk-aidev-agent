# -*- coding: utf-8 -*-
"""审批（ITSM tool approval）测试合集——按类别合并三个测试文件（2026-09-02）。

一、ItsmApproval* 协议对齐 Pydantic 模型组测试（quick 260828-36w，原 test_approval_models.py）

覆盖（对齐 PLAN acceptance criteria + 威胁模型 T-260828-01/02/03）：

- Test 1: 首跑形态 —— ``ApprovalHandler._build_first_run_interrupt(target)`` 产出
  （metadata 含 type="tool_approval" / status="pending" / callbackToken="" / ticketSn="" /
  ticket={}）经 ``ItsmApprovalInterrupt.model_validate(payload)`` 校验通过。
- Test 2: enrich 后形态 —— 注入 stub RM（经 ``ItsmTicketCreator``）调
  ``ApprovalHandler.prepare`` 后的 interrupt（metadata.ticket 填充 sn/url 等、
  ticketSn/callbackToken 非空）经 ``ItsmApprovalInterrupt.model_validate()`` 校验通过。
- Test 3: 默认值/字段完整性 —— ``ItsmApprovalTicket()`` 全默认可构造；
  ``ItsmApprovalMetadata().status == "pending"``；``.type == "tool_approval"``；
  非法 status 抛 ValidationError。
- Test 4: 终态 result —— ``ApprovalOutcomeBuilder.build_run_finished_payload`` 与
  ``upgrade_content_to_success`` 产出的扁平化 ``result``（id/interruptId 同值 +
  payload.metadata 整体透传）经 ``ItsmApprovalResult.model_validate()`` 校验通过，
  且终态 status 已被刷写。

测试从包顶层导入（``from aidev_agent.packages.interrupt_manager import ...``）
以同时验证双层导出（approval.py ``__all__`` + 包 ``__init__.py``）可用。

二、get_itsm_approval_target 幂等 / alias dump 与状态短路（260828-65m，原 test_approval_itsm_target.py）

- 幂等：同一 request（tool 有 approval_enabled=True metadata）调两次 get_itsm_approval_target，
  断言输出字段逐项相等（纯函数无副作用）。
- 无需审批：tool 无 approval 配置 → 返回 None。
- alias dump：``model_dump(by_alias=True)`` 输出含 toolCallId / toolName / toolCode /
  toolArgs 且不含 tool；``model_dump()`` 输出含 target_id / target_name 等原名。
- status 短路：state 含 ``{TOOL_APPROVAL_STATE_KEY: {"call_1": {"status": "approved"}}}``
  → get_tool_call_approval_status_from_state(state, "call_1") is True；"rejected" → False；
  无记录/非 dict → None。
- prepare 适配 target 形态（Task 4）：target 形态 → 单格式 payload 建单 enrich；
  非法形态 fail fast 抛 InvalidApprovalInterruptError，不建单不虚构。

三、ItsmTicketCreator 建单平台侧封装（quick 260828-gcn，原 test_approval_itsm_ticket_creator.py）

- payload 字段集完整（tool_call_id/tool_type/tool_name/tool_code/mcp_name/tool_args/
  approvers/session_code/thread_id/run_id/ticket_title）。
- approvers 取 tool_info 配置透传，绝不取 username（自审自批违规，UAT 裁定）。
- run_id 回落：ctx 无 run_id → run_id=tool_call_id。
- rm.create_tool_approval 被调 + 返回结果原样返回。
- ticket_title=f"执行「{tool_name}」需要审批"。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pydantic
from aidev_agent.core.nodes.tool.approval_wrapper import (
    TOOL_APPROVAL_STATE_KEY,
    get_itsm_approval_target,
    get_tool_call_approval_status_from_state,
)
from aidev_agent.packages.interrupt_manager import (
    ApprovalHandler,
    ApprovalOutcomeBuilder,
    ItsmApprovalInterrupt,
    ItsmApprovalMetadata,
    ItsmApprovalResult,
    ItsmApprovalTicket,
    ItsmTicketCreator,
)
from aidev_agent.packages.interrupt_manager.approval import ApprovalTarget
from langchain_core.messages import AIMessage
from pydantic import BaseModel

# ============================================================================ #
# 一、ItsmApproval* 协议对齐 Pydantic 模型组
# ============================================================================ #


class _StubResourceManager:
    """鸭子类型 resource_manager（对齐 D-06，mock 友好）。

    镜像 ``tests/core/ag_ui/test_interrupt_wiring.py`` 的 ``_StubResourceManager``：
    ``create_tool_approval`` 返回建单结果（含 ``ticket`` / ``callback_token``）。
    """

    def __init__(self, result=None):
        self.result = result or {
            # 字段集对齐真实平台建单返回（harness/ref-interrupt/stream3 抓包：
            # ticket 含 id/sn/submit_time/url/status/title/approvers）
            "ticket": {
                "id": "102026071517020507532412",
                "sn": "REQ202608270001",
                "submit_time": "2026-08-27T10:30:00+00:00",
                "url": "http://itsm/req/1",
                "status": "pending",
                "title": "审批",
                "approvers": ["u"],
            },
            "callback_token": "cb-0123456789",
        }
        self.create_calls: list[tuple[dict, str | None]] = []

    def create_tool_approval(self, payload: dict, *, username: str | None = None, **kwargs) -> dict:
        self.create_calls.append((payload, username))
        return self.result


def _first_run_payload():
    """构造首跑形态 interrupt payload（直接走生产 ``ApprovalHandler._build_first_run_interrupt``）。"""
    target = ApprovalTarget(
        target_type="tool",
        target_id="call-1",
        target_name="测试工具",
        target_code="test_tool",
        args={"a": 1},
        approval={"enabled": True},
    )
    return ApprovalHandler()._build_first_run_interrupt(target)


def _target_value(approvers: list[str] | None = None) -> dict:
    """构造 target 形态 value（生产真实入参：策略直抛 ApprovalTarget + reason）。

    prepare 的入参必须是 target 形态（含 approval 配置块）——非 target 形态
    会抛 InvalidApprovalInterruptError（fail fast，不虚构）。
    """
    return {
        **ApprovalTarget(
            target_type="tool",
            target_id="call-1",
            target_name="测试工具",
            target_code="test_tool",
            args={"a": 1},
            approval={"enabled": True, "approvers": approvers or ["approver-x"]},
        ).model_dump(by_alias=True),
        "reason": "aidev:tool_approval",
    }


# ---------------------------------------------------------------------- #
# Test 1: 首跑形态校验
# ---------------------------------------------------------------------- #


def test_itsm_approval_interrupt_validate_first_run_payload():
    """首跑形态：``ApprovalHandler._build_first_run_interrupt`` 产出经 ``model_validate`` 校验通过。"""
    payload = _first_run_payload()
    validated = ItsmApprovalInterrupt.model_validate(payload)

    # 顶层协议字段
    assert validated.id == payload["id"]
    assert validated.reason == payload["reason"]
    assert validated.toolCallId == "call-1"
    assert validated.message
    assert validated.type == "tool_approval"
    assert validated.toolName == "测试工具"
    assert validated.toolCode == "test_tool"
    assert validated.toolArgs == {"a": 1}

    # metadata 首跑形态：pending + 空 ticket（sn==""）
    assert validated.metadata.type == "tool_approval"
    assert validated.metadata.status == "pending"
    assert validated.metadata.callbackToken == ""
    assert validated.metadata.ticketSn == ""
    assert validated.metadata.ticket.sn == ""
    assert validated.metadata.create_ticket_error is False


# ---------------------------------------------------------------------- #
# Test 2: enrich 后形态校验
# ---------------------------------------------------------------------- #


def test_itsm_approval_interrupt_validate_enriched_payload():
    """enrich 后形态：``ApprovalHandler.prepare`` 建单后经 ``model_validate`` 校验通过。"""
    rm = _StubResourceManager()
    interrupt = _target_value()
    # 260828-p3w：prepare 接收 intr 对象，就地 enrich intr.value，返回同一 intr 对象
    intr = SimpleNamespace(value=interrupt, id="int-call-1")
    enriched = ApprovalHandler().prepare(intr, ItsmTicketCreator(rm, username="u"))
    assert enriched is intr, "prepare 应返回同一 intr 对象"
    enriched = intr.value

    validated = ItsmApprovalInterrupt.model_validate(enriched)

    # enrich 后：ticketSn / callbackToken 非空，ticket.id / sn 非空（真实抓包字段集）
    assert validated.metadata.status == "pending"
    assert validated.metadata.ticketSn == "REQ202608270001"
    assert validated.metadata.ticket.id == "102026071517020507532412"
    assert validated.metadata.ticket.sn == "REQ202608270001"
    assert validated.metadata.ticket.submit_time == "2026-08-27T10:30:00+00:00"
    assert validated.metadata.ticket.url
    assert validated.metadata.ticket.approvers == ["u"]
    assert validated.metadata.callbackToken == "cb-0123456789"
    assert validated.metadata.ticket.title == "审批"
    assert validated.metadata.create_ticket_error is False
    # RM 建单被调用：payload 审批人来自 approval 配置（非 username）
    assert len(rm.create_calls) == 1
    payload, _ = rm.create_calls[0]
    assert payload["approvers"] == ["approver-x"], "建单审批人取 approval 配置，不取 username"


# ---------------------------------------------------------------------- #
# Test 3: 默认值 / 字段完整性
# ---------------------------------------------------------------------- #


def test_itsm_approval_models_defaults_and_literals():
    """默认值 / Literal 锁定：默认构造 + 非法 status 抛 ValidationError。"""
    # ItsmApprovalTicket 全字段有默认，可空构造
    ticket = ItsmApprovalTicket()
    assert ticket.id == ""
    assert ticket.sn == ""
    assert ticket.submit_time == ""
    assert ticket.url == ""
    assert ticket.status == ""
    assert ticket.title == ""
    assert ticket.approvers == []

    # ItsmApprovalMetadata 默认 status/type 锁定
    assert ItsmApprovalMetadata().status == "pending"
    assert ItsmApprovalMetadata().type == "tool_approval"

    # 非法 status 抛 ValidationError（T-260828-02 协议漂移防护）
    try:
        ItsmApprovalMetadata(status="nonsense")
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("非法 status 应抛 pydantic.ValidationError")

    # ItsmApprovalResult 全字段有默认，可空构造
    result = ItsmApprovalResult()
    assert result.id == ""
    assert result.interruptId == ""
    assert result.reason == "aidev:tool_approval"
    assert result.payload.metadata.status == "pending"


def test_itsm_approval_models_default_factory_isolation():
    """可变默认值经 ``Field(default_factory=...)`` 初始化：实例间不共享、默认等值。"""
    t1, t2 = ItsmApprovalTicket(), ItsmApprovalTicket()
    t1.approvers.append("u")
    assert t2.approvers == [], "approvers 默认值不应在实例间共享（default_factory 语义）"

    m1, m2 = ItsmApprovalMetadata(), ItsmApprovalMetadata()
    m1.toolArgs["k"] = 1
    assert m2.toolArgs == {}, "toolArgs 默认值不应在实例间共享（default_factory 语义）"
    assert m1.ticket is not m2.ticket, "嵌套 ticket 默认实例不应共享"
    m1.ticket.approvers.append("u")
    assert m2.ticket.approvers == []

    i1, i2 = ItsmApprovalInterrupt(id="i-1"), ItsmApprovalInterrupt(id="i-2")
    assert i1.metadata is not i2.metadata, "嵌套 metadata 默认实例不应共享"


# ---------------------------------------------------------------------- #
# Test 4: 终态 result 校验（ApprovalOutcomeBuilder 产出形态）
# ---------------------------------------------------------------------- #


def _enriched_payload():
    """构造 enrich 后形态 interrupt（prepare 建单 + enrich），供终态构造消费。

    260828-p3w：prepare 接收 intr 对象，就地 enrich intr.value；返回 dict value 供终态构造。
    入参为 target 形态（生产真实形态）。
    """
    rm = _StubResourceManager()
    intr = SimpleNamespace(value=_target_value(), id="int-call-1")
    ApprovalHandler().prepare(intr, ItsmTicketCreator(rm, username="u"))
    return intr.value


def test_itsm_approval_result_validate_build_run_finished_payload():
    """``build_run_finished_payload`` 产出的扁平化 result 经 ``model_validate`` 校验通过。"""
    enriched = _enriched_payload()
    outcome, result = ApprovalOutcomeBuilder.build_run_finished_payload([enriched], "approved")

    assert outcome["type"] == "success"
    validated = ItsmApprovalResult.model_validate(result)

    # id / interruptId 同值（供前端按中断 id 关联续流结果）
    assert validated.id == enriched["id"]
    assert validated.interruptId == enriched["id"]
    assert validated.toolCallId == "call-1"
    # payload.metadata 整体透传：终态 status 已刷写，ticket 字段保留
    assert validated.payload.metadata.status == "approved"
    assert validated.payload.metadata.ticketSn == "REQ202608270001"
    assert validated.payload.metadata.ticket.id == "102026071517020507532412"
    assert validated.payload.metadata.ticket.status == "approved"


def test_itsm_approval_result_validate_upgrade_content_to_success():
    """``upgrade_content_to_success`` 写入 content 的 result 同样可校验通过。"""
    enriched = _enriched_payload()
    content = {"outcome": {"type": "interrupt", "interrupts": [enriched]}}

    upgraded = ApprovalOutcomeBuilder.upgrade_content_to_success(content, "rejected")

    assert upgraded is not None
    validated = ItsmApprovalResult.model_validate(upgraded["result"])
    assert validated.id == enriched["id"]
    assert validated.payload.metadata.status == "rejected"
    assert validated.payload.metadata.ticket.status == "rejected"


# ============================================================================ #
# 二、get_itsm_approval_target 幂等 / alias dump 与状态短路
# ============================================================================ #


def _make_request(tool: MagicMock, tool_call: dict) -> MagicMock:
    request = MagicMock()
    request.tool = tool
    request.tool_call = tool_call
    return request


def _approved_tool() -> MagicMock:
    """构造带 approval_enabled=True 元数据的工具。"""
    tool = MagicMock()
    tool.name = "calculator"
    tool.metadata = {"approval": {"approval_enabled": True}}
    return tool


def _tool_call() -> dict:
    return {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"}


# ---------------------------------------------------------------------- #
# 幂等性
# ---------------------------------------------------------------------- #


def test_get_itsm_approval_target_is_idempotent():
    """同一 request 调两次输出逐项相等（纯函数无副作用）。"""
    request = _make_request(_approved_tool(), _tool_call())
    first = get_itsm_approval_target(request)
    second = get_itsm_approval_target(request)

    assert first is not None
    assert second is not None
    assert first.target_type == second.target_type == "tool"
    assert first.target_id == second.target_id == "call_1"
    assert first.target_name == second.target_name == "calculator"
    assert first.target_code == second.target_code == "calculator"
    assert first.args == second.args == {"a": 1, "b": 2}
    assert first.approval == second.approval == {"approval_enabled": True}


# ---------------------------------------------------------------------- #
# 无需审批
# ---------------------------------------------------------------------- #


def test_get_itsm_approval_target_returns_none_without_approval():
    """tool 无 approval 配置 → 返回 None。"""
    tool = MagicMock()
    tool.name = "calculator"
    tool.metadata = {}  # 无 approval
    request = _make_request(tool, _tool_call())
    assert get_itsm_approval_target(request) is None


# ---------------------------------------------------------------------- #
# alias dump
# ---------------------------------------------------------------------- #


def test_get_itsm_approval_target_alias_dump():
    """alias 协议名 dump 与原名 dump 双通道可用，且不含 tool 字段。"""
    request = _make_request(_approved_tool(), _tool_call())
    target = get_itsm_approval_target(request)
    assert isinstance(target, ApprovalTarget)
    assert isinstance(target, BaseModel)

    by_alias = target.model_dump(by_alias=True)
    assert by_alias["toolCallId"] == "call_1"
    assert by_alias["toolName"] == "calculator"
    assert by_alias["toolCode"] == "calculator"
    assert by_alias["toolArgs"] == {"a": 1, "b": 2}
    assert "tool" not in by_alias

    by_name = target.model_dump()
    assert by_name["target_id"] == "call_1"
    assert by_name["target_name"] == "calculator"
    assert by_name["target_code"] == "calculator"
    assert by_name["args"] == {"a": 1, "b": 2}
    assert "tool" not in by_name


# ---------------------------------------------------------------------- #
# get_tool_call_approval_status_from_state 状态短路
# ---------------------------------------------------------------------- #


def test_status_from_state_approved_true():
    """state 含 approved 终态 → True。"""
    state = {
        "messages": [
            AIMessage(
                content="",
                additional_kwargs={TOOL_APPROVAL_STATE_KEY: {"call_1": {"status": "approved"}}},
            )
        ]
    }
    assert get_tool_call_approval_status_from_state(state, "call_1") is True


def test_status_from_state_rejected_false():
    """state 含 rejected 终态 → False。"""
    state = {
        "messages": [
            AIMessage(
                content="",
                additional_kwargs={TOOL_APPROVAL_STATE_KEY: {"call_1": {"status": "rejected"}}},
            )
        ]
    }
    assert get_tool_call_approval_status_from_state(state, "call_1") is False


def test_status_from_state_missing_or_non_dict_none():
    """无记录 / 非 dict 记录 → None。"""
    # 无记录
    state = {"messages": [AIMessage(content="")]}
    assert get_tool_call_approval_status_from_state(state, "call_1") is None

    # 非 dict 记录
    state2 = {
        "messages": [AIMessage(content="", additional_kwargs={TOOL_APPROVAL_STATE_KEY: {"call_1": "not-a-dict"}})]
    }
    assert get_tool_call_approval_status_from_state(state2, "call_1") is None


# ---------------------------------------------------------------------- #
# Task 4：ApprovalHandler.prepare 适配 target 形态
# ---------------------------------------------------------------------- #


class _StubTargetResourceManager:
    """鸭子类型 resource_manager（对齐 D-06，mock 友好）。"""

    def __init__(self):
        self.result = {
            "ticket": {"id": "102026071517020507532412", "sn": "REQ202608270001"},
            "callback_token": "cb-0123456789",
        }
        self.create_calls: list[tuple[dict, str | None]] = []

    def create_tool_approval(self, payload: dict, *, username: str | None = None, **kwargs) -> dict:
        self.create_calls.append((payload, username))
        return self.result


def _target_form_interrupt() -> dict:
    """构造策略直抛的 target 形态 interrupt（alias 协议名 + reason）。"""
    target = ApprovalTarget(
        target_type="tool",
        target_id="call_1",
        target_name="测试工具",
        target_code="test_tool",
        args={"a": 1},
        approval={"enabled": True},
    )
    return {**target.model_dump(by_alias=True), "reason": "aidev:tool_approval"}


def test_prepare_target_form_builds_single_format_payload():
    """target 形态 → 构造完整单格式 payload 并走既有建单 enrich。

    260828-p3w：prepare 接收 intr 对象，id 取 intr.id（不读 value 内 id）。
    """
    rm = _StubTargetResourceManager()
    interrupt = _target_form_interrupt()
    # 生产路径：intr.id 为真实 LangGraph interrupt id → 首跑 payload id 沿用（不回落 int-approval-）
    intr = SimpleNamespace(value=interrupt, id="ef37fae67cf416388c5253cf66595554")
    enriched = ApprovalHandler().prepare(intr, ItsmTicketCreator(rm, username="u"))
    assert enriched is intr, "prepare 应返回同一 intr 对象"
    enriched = intr.value

    # 顶层完整单格式字段
    assert enriched["toolCallId"] == "call_1"
    assert enriched["toolName"] == "测试工具"
    assert enriched["toolCode"] == "test_tool"
    assert enriched["toolArgs"] == {"a": 1}
    assert enriched["reason"] == "aidev:tool_approval"
    # intr.id 保留（真实 LangGraph interrupt id，非回落生成的 int-approval-）
    assert enriched["id"] == "ef37fae67cf416388c5253cf66595554"
    # metadata enrich：ticketSn 非空 + status pending
    assert enriched["metadata"]["status"] == "pending"
    assert enriched["metadata"]["ticketSn"] == "REQ202608270001"
    assert enriched["metadata"]["ticket"]["sn"] == "REQ202608270001"
    assert enriched["metadata"]["callbackToken"] == "cb-0123456789"
    # RM 建单被调用一次（经 ItsmTicketCreator 收敛，username 透传）
    assert len(rm.create_calls) == 1
    assert rm.create_calls[0][1] == "u"


def test_prepare_invalid_target_form_raises_no_create():
    """非法 target 形态（approval 非 dict）→ model_validate 失败 → 抛异常，不建单不虚构。

    fail fast 契约（用户裁定）：value 有问题必须抛 InvalidApprovalInterruptError，
    静默拦截或虚构造单是生产事故。
    """
    import pytest
    from aidev_agent.packages.interrupt_manager.approval import InvalidApprovalInterruptError

    rm = _StubTargetResourceManager()
    interrupt = _target_form_interrupt()
    interrupt["approval"] = "not-a-dict"  # 破坏结构

    intr = SimpleNamespace(value=interrupt, id="int-approval-call_1")
    with pytest.raises(InvalidApprovalInterruptError, match="ApprovalTarget 校验失败"):
        ApprovalHandler().prepare(intr, ItsmTicketCreator(rm, username="u"))
    assert len(rm.create_calls) == 0


def test_build_first_run_interrupt_uses_injected_id():
    """Test K：_build_first_run_interrupt 传入注入 id → id == 注入值（生产路径尊重 intr.id）。"""
    target = ApprovalTarget(
        target_type="tool",
        target_id="call_1",
        target_name="测试工具",
        target_code="test_tool",
        args={"a": 1},
        approval={"enabled": True},
    )
    payload = ApprovalHandler()._build_first_run_interrupt(target, interrupt_id="ef37fae67cf416388c5253cf66595554")
    assert payload["id"] == "ef37fae67cf416388c5253cf66595554"


def test_build_first_run_interrupt_defaults_to_int_approval_prefix():
    """Test K：_build_first_run_interrupt 未传注入 id → 回落 int-approval-{target_id}-{uuid8} 前缀。"""
    target = ApprovalTarget(
        target_type="tool",
        target_id="call_1",
        target_name="测试工具",
        target_code="test_tool",
        args={"a": 1},
        approval={"enabled": True},
    )
    payload = ApprovalHandler()._build_first_run_interrupt(target)
    assert payload["id"].startswith("int-approval-call_1-")


def test_prepare_legacy_payload_form_raises_fail_fast():
    """旧 payload 形态（含 metadata，非 target 形态）→ 抛异常（fail fast，不虚构）。

    生产中 approval 中断 value 恒为策略直抛的 target 形态；落库形态流入 prepare
    属程序错误——静默走「原路径」会虚构无审批配置的单据（历史 bug 根因之一）。
    """
    import pytest
    from aidev_agent.packages.interrupt_manager.approval import InvalidApprovalInterruptError

    rm = _StubTargetResourceManager()
    legacy = ApprovalHandler()._build_first_run_interrupt(
        ApprovalTarget(
            target_type="tool",
            target_id="call_1",
            target_name="测试工具",
            target_code="test_tool",
            args={"a": 1},
            approval={"enabled": True},
        )
    )
    assert "metadata" in legacy  # 落库形态含 metadata

    intr = SimpleNamespace(value=legacy, id=legacy["id"])
    with pytest.raises(InvalidApprovalInterruptError, match="非法 target 形态"):
        ApprovalHandler().prepare(intr, ItsmTicketCreator(rm, username="u"))
    assert len(rm.create_calls) == 0


# ============================================================================ #
# 三、ItsmTicketCreator 建单平台侧封装
# ============================================================================ #


class _StubTicketCreatorResourceManager:
    """鸭子类型 resource_manager（对齐 D-06，mock 友好）。"""

    def __init__(self, result=None):
        self.result = result or {"ticket": {"sn": "REQ1"}, "callback_token": "cb_1"}
        self.create_calls: list[tuple[dict, str | None]] = []

    def create_tool_approval(self, payload: dict, *, username: str | None = None, **kwargs) -> dict:
        self.create_calls.append((payload, username))
        return self.result


def _target(**approval_overrides):
    """构造带审批配置的 ApprovalTarget（建单入参——含配置审批人）。"""
    approval = {"enabled": True, "mcp_code": "mcp-demo"}
    approval.update(approval_overrides)
    return ApprovalTarget(
        target_type="tool_approval",
        target_id="call_1",
        target_name="测试工具",
        target_code="test_tool",
        args={"a": 1},
        approval=approval,
    )


def test_payload_field_set_complete():
    """payload 字段集完整：全部平台建单字段随 ApprovalTarget + ctx 组装。"""
    rm = _StubTicketCreatorResourceManager()
    creator = ItsmTicketCreator(rm, username="alice", session_code="s1")

    result = creator(_target(), thread_id="t1", run_id="r1")

    assert result is rm.result, "creator 应原样返回 rm.create_tool_approval 结果"
    assert len(rm.create_calls) == 1
    payload, username = rm.create_calls[0]
    assert username == "alice"
    assert payload["tool_call_id"] == "call_1"
    assert payload["tool_type"] == "tool_approval"
    assert payload["tool_name"] == "测试工具"
    assert payload["tool_code"] == "test_tool"
    assert payload["mcp_name"] == "mcp-demo"
    assert payload["tool_args"] == {"a": 1}
    assert payload["approvers"] == [], (
        "tool_info 未携带配置审批人时 approvers 为空（审批人由 ITSM 配置流决定，"
        "绝不取 username——自审自批违规，UAT 严重错误裁定）"
    )
    assert payload["session_code"] == "s1"
    assert payload["thread_id"] == "t1"
    assert payload["run_id"] == "r1"
    assert payload["ticket_title"] == "执行「测试工具」需要审批"


def test_approvers_from_tool_info_not_username():
    """approvers 取 tool_info（审批配置透传）；与 username 无关；None/缺失 → 空。"""
    rm = _StubTicketCreatorResourceManager()
    ItsmTicketCreator(rm, username="bob")(_target(approvers=["approver-1", "approver-2"]))
    ItsmTicketCreator(rm, username="bob")(_target())
    ItsmTicketCreator(rm)(_target(approvers=["x"]))
    assert rm.create_calls[0][0]["approvers"] == ["approver-1", "approver-2"], "配置审批人透传"
    assert rm.create_calls[1][0]["approvers"] == [], "无配置 → 空（不回落 username）"
    assert rm.create_calls[2][0]["approvers"] == ["x"]


def test_run_id_falls_back_to_tool_call_id():
    """ctx 无 run_id → run_id=tool_call_id（保持现行为）。"""
    rm = _StubTicketCreatorResourceManager()
    creator = ItsmTicketCreator(rm)
    creator(_target(), thread_id="t1")
    payload, _ = rm.create_calls[0]
    assert payload["run_id"] == "call_1", "无 run_id 时应回落 tool_call_id"


def test_session_code_defaults_empty():
    """session_code 未注入时默认空串。"""
    rm = _StubTicketCreatorResourceManager()
    ItsmTicketCreator(rm)(_target(), thread_id="t1", run_id="r1")
    payload, _ = rm.create_calls[0]
    assert payload["session_code"] == ""


def test_ticket_title_fallback_when_tool_name_empty():
    """tool_name 空 → ticket_title 兜底「执行工具需要审批」。"""
    rm = _StubTicketCreatorResourceManager()
    ItsmTicketCreator(rm)(ApprovalTarget(target_id="call_1", target_name="", target_code=""))
    payload, _ = rm.create_calls[0]
    assert payload["ticket_title"] == "执行工具需要审批"
