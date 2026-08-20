# -*- coding: utf-8 -*-
"""CR-01 wiring 级测试：agent.py 装配 InterruptProcessor 注入 ItsmTicketCreator（封装 RM）。

``test_dispatcher.py`` 用 stub RM 直测 ``InterruptProcessor``，恰好掩盖了
「agent.py → processor → RM」的真实装配断链（CR-01）。本测试构造真实
``LangGraphAgent`` 实例（通过 ``__new__`` + 显式属性赋值），走
``_resolve_exit``（退出中断处理器）主链路，断言经 ``ItsmTicketCreator`` 注入的 RM
的 ``create_tool_approval`` 被调用、interrupt 被 enrich（metadata.ticket /
ticketSn / callbackToken）。
"""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from aidev_agent.core.ag_ui.agent import LangGraphAgent
from aidev_agent.packages.interrupt_manager import (
    TOOL_APPROVAL_REASON,
    ApprovalHandler,
    ItsmTicketCreator,
)
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from aidev_agent.packages.interrupt_manager.types import DispatchResult, InterruptOutcome
from langgraph.types import Command


class _StubGraph:
    """真实 __init__ 构造用的 graph 桩（LangGraphAgent 仅存储不遍历）。"""


_STUB_GRAPH = _StubGraph()


class _StubResourceManager:
    """鸭子类型 resource_manager（对齐 D-06，mock 友好）。"""

    def __init__(self, result=None):
        self.result = result or {
            "ticket": {"sn": "REQ202608270001"},
            "callback_token": "cb-0123456789",
        }
        self.create_calls: list[tuple[dict, str | None]] = []

    def create_tool_approval(self, payload: dict, *, username: str | None = None, **kwargs) -> dict:
        self.create_calls.append((payload, username))
        return self.result


def _approval_task(tool_call_id: str) -> SimpleNamespace:
    """构造带单条 approval interrupt 的 langgraph task 模拟。

    value 为**target 形态**（生产真实形态：策略直抛 ApprovalTarget alias + reason，
    含 approval 配置块——配置审批人在内；无 metadata——落库 payload 由 prepare 构造）。
    260828-p3w：id 只活在 intr.id（value dict 内不含 id 键，id 与 value 彻底分离）。
    """
    value = {
        "reason": TOOL_APPROVAL_REASON,
        "target_type": "tool",
        "toolCallId": tool_call_id,
        "toolName": "测试工具",
        "toolCode": "test_tool",
        "toolArgs": {"a": 1},
        # 审批配置块（ApprovalTarget.approval）：配置的 ITSM 审批人（建单权威来源）
        "approval": {"enabled": True, "approvers": ["approver-a", "approver-b"]},
    }
    intr = SimpleNamespace(value=value, id=f"int-approval-{tool_call_id}")
    return SimpleNamespace(name="tools", id=f"task-{tool_call_id}", interrupts=(intr,))


def _exit_state(tasks: list) -> SimpleNamespace:
    """构造 ``_resolve_exit`` 消费的 langgraph state 鸭子类型（挂起态）。

    前段 dispatch 消费 ``state.tasks``；后段 node_name 推导消费 ``tasks`` 真值 /
    ``metadata.writes`` / ``next`` / ``values``。
    """
    return SimpleNamespace(
        tasks=tasks,
        metadata={"writes": {}},
        next=("tools",),
        values={"messages": []},
    )


def _make_agent(rm: _StubResourceManager, *, username: str | None = "alice", session_code: str = "sess-1"):
    agent = LangGraphAgent.__new__(LangGraphAgent)
    # D-03/U-01：处理器经 handlers dict 注入，approval 对偶单元自持 RM + ticket_creator
    agent._interrupt_processor = InterruptProcessor(
        handlers={
            TOOL_APPROVAL_REASON: ApprovalHandler(
                resource_manager=rm,
                ticket_creator=ItsmTicketCreator(rm, username=username, session_code=session_code),
            )
        }
    )
    agent.active_run = {"thread_id": "sess-1", "id": "run-1"}
    return agent


def test_wiring_dispatch_injects_rm_and_enriches_metadata():
    """主链路 prepare 能拿到注入的 RM：建单被调用 + interrupt 被 enrich。"""
    rm = _StubResourceManager()
    agent = _make_agent(rm)

    task = _approval_task("call_1")
    result = agent._resolve_exit(_exit_state([task]), last_node_name="tools")

    assert len(rm.create_calls) == 1, "装配点注入 RM 后，流结束建单应被调用一次"
    payload, username = rm.create_calls[0]
    assert username == "alice"
    assert payload["tool_call_id"] == "call_1"
    assert payload["session_code"] == "sess-1"
    assert payload["approvers"] == ["approver-a", "approver-b"], (
        "审批人必须取审批配置（value.approval.approvers）的 ITSM 审批人，"
        "绝不能是提单人自己（自审自批违规，UAT 严重错误裁定）"
    )

    # enrich 结果应含 ticket / ticketSn / callbackToken（enrich 就地作用 intr.value）
    assert len(result.interrupt_values) == 1
    metadata = task.interrupts[0].value["metadata"]
    assert metadata.get("ticket", {}).get("sn") == "REQ202608270001"
    assert metadata.get("ticketSn") == "REQ202608270001"
    assert metadata.get("callbackToken") == "cb-0123456789"


def test_wiring_dispatch_no_rm_skips_build():
    """装配点未注入 RM 时，建单副作用跳过但 interrupt 照发（D-01 不吞中断）。"""
    agent = _make_agent(_StubResourceManager())
    agent._interrupt_processor = InterruptProcessor()  # 模拟未装配 ticket_creator 的裸 processor

    task = _approval_task("call_2")
    result = agent._resolve_exit(_exit_state([task]), last_node_name="tools")

    assert len(result.interrupt_values) == 1, "未注入 RM 也应放行 interrupt（不吞中断）"
    metadata = task.interrupts[0].value.get("metadata", {})
    assert not (metadata.get("ticket") or {}).get("sn"), "未注入 RM 不应有建单工单号（首跑 payload 的空 ticket 除外）"


def test_wiring_dispatch_invalid_value_raises_no_fabrication():
    """协议错误 fail fast：非 target 形态 value（如已 enrich 的落库形态）→ 抛异常。

    生产中 approval 中断 value 恒为策略直抛的 target 形态（checkpoint 保存原始
    抛出值）；收到其他形态属程序错误——绝不静默拦截或虚构 ApprovalTarget 建单
    （空审批人工单是生产事故，用户裁定 fail fast）。
    """
    import pytest
    from aidev_agent.packages.interrupt_manager.approval import InvalidApprovalInterruptError

    rm = _StubResourceManager()
    agent = _make_agent(rm)

    task = _approval_task("call_invalid")
    # 构造非法形态：带 metadata（落库形态，非 target 形态）
    task.interrupts[0].value["metadata"] = {"ticketSn": "REQ1", "status": "pending"}
    with pytest.raises(InvalidApprovalInterruptError, match="非法 target 形态"):
        agent._resolve_exit(_exit_state([task]), last_node_name="tools")
    assert rm.create_calls == [], "协议错误必须在建单前抛出（不虚构单据）"


def test_wiring_dispatch_str_value_untouched_zero_processing():
    """零处理：str 形态的 interrupt value 不被 json.loads，prepare 对非 dict value 原样放行（不吞中断）。

    260828-p3w：dispatcher 零处理收集（str value 不再 json.loads）；approval prepare
    对非 dict value 防御性原样返回，不建单、不抛异常。经 ``_resolve_exit`` 主链路
    断言原始 intr 对象 in-place 未被触碰（prepare 就地 enrich 语义下的等价观测）。
    """
    rm = _StubResourceManager()
    agent = _make_agent(rm)

    value = {
        "reason": TOOL_APPROVAL_REASON,
        "toolCallId": "call_5",
        "toolName": "测试工具",
        "toolCode": "test_tool",
        "metadata": {"type": "tool_approval", "toolName": "测试工具", "toolArgs": {}},
    }
    intr = SimpleNamespace(value=json.dumps(value), id="int-approval-call_5")
    task = SimpleNamespace(name="tools", id="task-call_5", interrupts=(intr,))
    result = agent._resolve_exit(_exit_state([task]), last_node_name="tools")

    assert len(result.interrupt_values) == 1, "str value interrupt 不应被丢弃（零处理不吞中断）"
    assert intr.value == json.dumps(value), "str value 原样保留（prepare 不 json.loads、不 enrich）"
    assert len(rm.create_calls) == 0, "str（非 dict）value 的 prepare 不建单"


def test_wiring_init_injects_processor_instance():
    """真实 __init__ 构造注入生效：_interrupt_processor is 传入实例。"""
    processor = InterruptProcessor()
    agent = LangGraphAgent(name="test", graph=_STUB_GRAPH, interrupt_processor=processor)
    assert agent._interrupt_processor is processor, "构造注入的 processor 应被原样保留"


def test_wiring_init_fallback_to_bare_processor():
    """不传 interrupt_processor 时兜底裸 processor（空 handlers → dispatch 未命中 reason 原样放行）。"""
    agent = LangGraphAgent(name="test", graph=_STUB_GRAPH)
    assert isinstance(agent._interrupt_processor, InterruptProcessor)
    assert agent._interrupt_processor._handlers == {}, "兜底裸 processor 应为空 handlers dict（D-03 不吞中断）"


# ---------------------------------------------------------------------- #
# 重复提单修复回归：prepare_stream 在 resume 场景跳过 processor
# ---------------------------------------------------------------------- #


class _SpyProcessor:
    """记录 dispatch_interrupts 调用的 processor spy（D-08：prepare_stream 纯拉图，应零调用）。"""

    def __init__(self, values=None):
        self.values = values if values is not None else []
        self.calls: list[tuple[object, object]] = []

    def process(self, tasks, **ctx):
        self.calls.append((tasks, ctx))
        return self.values

    def dispatch_interrupts(self, tasks, ctx):
        # 45-03：_resolve_exit 前段 dispatch 调 dispatch_interrupts（返回 DispatchResult）
        self.calls.append((tasks, ctx))
        return DispatchResult(interrupts=[InterruptOutcome(intr=v) for v in self.values])


def _make_prepare_stream_agent(spy: _SpyProcessor) -> LangGraphAgent:
    """构造最小可运行 prepare_stream 的 agent（__new__ + 显式属性 + 桩方法）。"""
    agent = LangGraphAgent.__new__(LangGraphAgent)
    agent._interrupt_processor = spy
    agent.active_run = {
        "id": "run-1",
        "thread_id": "t-1",
        "mode": "start",
        "node_name": None,
        "current_graph_state": {},
        "schema_keys": None,
    }
    agent.constant_schema_keys = ["messages"]
    agent.graph = MagicMock()
    agent.get_schema_keys = lambda config: {"input": [], "output": []}
    agent.get_stream_kwargs = lambda **kwargs: {"fake_stream_kwargs": True}
    agent._build_terminal_snapshot_events = lambda state: [MagicMock(), MagicMock()]
    return agent


def _prepare_stream_input(
    forwarded_props: dict, messages: list | None = None, stream_input: Any = None
) -> SimpleNamespace:
    return SimpleNamespace(
        forwarded_props=forwarded_props,
        thread_id="t-1",
        state={},
        stream_input=stream_input,
        messages=messages,
    )


async def test_prepare_stream_resume_branch_no_build():
    """D-01（47-02）全就绪 resume：pre_run 产出 Command → prepare_stream 直接拉图，不建单。

    分支 B 已删除，ag_ui 层零 resume 编排。全就绪/拒绝 resume 的 ``input.stream_input``
    即 pre_run（chat.py _prepare_pre_run_history）产出的 ``Command``——prepare_stream
    判定到 Command 直接统一启动，**绝不**触发流结束 dispatch（``_resolve_exit`` 前段，
    D-08：resume 侧绝不建单）。
    """
    task = _approval_task("call_resume")
    spy = _SpyProcessor(values=[task.interrupts[0]])
    agent = _make_prepare_stream_agent(spy)
    input = _prepare_stream_input(
        {"command": {"resume": [{"toolCallId": "call_resume", "status": "approved"}]}},
        stream_input=Command(resume=[{"toolCallId": "call_resume", "status": "approved"}]),
    )
    agent_state = SimpleNamespace(tasks=[task], values={"messages": []})

    result = await agent.prepare_stream(input, agent_state, config={})

    assert spy.calls == [], "全就绪 resume 不应触发 process/dispatch（建单计数 0，D-08）"
    assert result["stream"] is not None, "全就绪 resume 应走正常 astream 启动（input.stream_input 即 Command）"
    assert result.get("events_to_dispatch") is None, "全就绪 resume 不应回放中断卡片"


async def test_prepare_stream_payload_direct_launch_no_dispatch():
    """D-08：正常 payload / 非 resume 直接拉图，零中断下发编排。

    prepare_stream 回归纯拉图——Command 或正常 payload 统一直接 ``astream_events``
    拉图（内联收敛于 prepare_stream 尾部），**绝不**触发流结束 dispatch
    （``_resolve_exit`` 前段）。not_ready 的中断下发已由 chat 层
    D-09（``_build_not_ready_sse``）承担，prepare_stream 不再处理。
    """
    task = _approval_task("call_reentry")
    spy = _SpyProcessor(values=[task.interrupts[0]])
    agent = _make_prepare_stream_agent(spy)
    input = _prepare_stream_input({}, stream_input={"messages": []})
    agent_state = SimpleNamespace(tasks=[task], values={"messages": []})

    result = await agent.prepare_stream(input, agent_state, config={})

    assert spy.calls == [], "prepare_stream 纯拉图，不应触发 process/dispatch（零中断下发，D-08）"
    assert result["stream"] is not None, "正常 payload 应直接拉图（astream 启动）"
    assert result.get("events_to_dispatch") is None, "prepare_stream 不再回放中断卡片"


async def test_prepare_stream_never_dispatches_regardless_of_pending():
    """D-08：即使 state.tasks 存在活跃 pending，prepare_stream 也绝不 dispatch（纯拉图）。

    分支 A 已删除：prepare_stream 不再收集活跃 pending / 不再短路回放。未就绪场景的
    中断下发由 chat 层 D-09 在进入 Agent 前早退处理，prepare_stream 只负责拉图。
    """
    task = _approval_task("call_pending")
    task2 = _approval_task("call_pending_2")
    spy = _SpyProcessor(values=[task.interrupts[0], task2.interrupts[0]])
    agent = _make_prepare_stream_agent(spy)
    input = _prepare_stream_input({}, stream_input={"messages": []})
    agent_state = SimpleNamespace(tasks=[task, task2], values={"messages": []})

    result = await agent.prepare_stream(input, agent_state, config={})

    assert spy.calls == [], "存在活跃 pending 时 prepare_stream 也绝不 dispatch（纯拉图，D-08）"
    assert result["stream"] is not None, "prepare_stream 恒直接拉图"


def test_normalize_interrupt_value_target_form_reason():
    """UAT 回归：target 形态（reason=None + interrupt_reason）归一化不得丢失真实 reason。

    真实图 ask_user 直抛 5 键 target 形态（questions/interrupt_reason/message/
    toolCallId/expiresAt）；归一化若直接回退 "tool_call" 会让落库查表
    （base.py get_handler(serialized_reason)）落到 DEFAULT_HANDLER，builtin_property
    缺 tool_call_id，resume 侧一致性校验误判脏数据。归一化链须与
    processor._reason_of 对齐：reason → interrupt_reason → "tool_call"。
    """
    target_form = SimpleNamespace(
        id="int-question-call_auq_001-abcd1234",
        value={
            "questions": [{"question": "Q", "multiSelect": False}],
            "interrupt_reason": "aidev:user_question",
            "reason": None,
            "message": "需要用户回答：Q",
            "toolCallId": "call_auq_001",
        },
    )
    intr = LangGraphAgent._normalize_interrupt_value(target_form)
    assert intr.reason == "aidev:user_question", "target 形态应取 interrupt_reason 作为 reason（不得回退 tool_call）"
    assert intr.toolCallId == "call_auq_001"

    # 旧形态（reason 直接存在）与纯 approval 回退不受影响
    legacy = LangGraphAgent._normalize_interrupt_value(SimpleNamespace(id="int-a", value={"reason": "tool_approval"}))
    assert legacy.reason == "tool_approval"
    fallback = LangGraphAgent._normalize_interrupt_value(SimpleNamespace(id="int-b", value={"message": "m"}))
    assert fallback.reason == "tool_call", "无任何 reason 键时保持 tool_call 回退"


def test_normalize_interrupt_value_target_form_synthesizes_metadata():
    """UAT 回归：target 形态（无 metadata、questions 顶层）归一化合成标准 metadata。

    策略直抛 target 5 键无 metadata，归一化若不合成则落库元素缺
    metadata.status，resume 一致性校验报「期望 status=pending，实际 None」。
    """
    target_form = SimpleNamespace(
        id="int-question-call_auq_001-abcd1234",
        value={
            "questions": [{"question": "Q", "multiSelect": False}],
            "interrupt_reason": "aidev:user_question",
            "reason": None,
            "message": "需要用户回答：Q",
            "toolCallId": "call_auq_001",
            "expiresAt": "2026-09-01T00:00:00+00:00",
        },
    )
    intr = LangGraphAgent._normalize_interrupt_value(target_form)
    assert intr.metadata is not None, "target 形态应合成标准 metadata"
    assert intr.metadata["type"] == "ask_user_question"
    assert intr.metadata["status"] == "pending", "合成 status=pending（resume 校验依赖）"
    assert intr.metadata["questions"] == [{"question": "Q", "multiSelect": False}], "questions 迁入 metadata"
    # 已带 metadata 的完整形态不受影响
    full_form = SimpleNamespace(
        id="int-full",
        value={
            "reason": "aidev:user_question",
            "toolCallId": "call_auq_002",
            "metadata": {"type": "ask_user_question", "status": "resolved", "questions": []},
        },
    )
    full = LangGraphAgent._normalize_interrupt_value(full_form)
    assert full.metadata["status"] == "resolved", "已有 metadata 原样保留（不覆盖终态）"
