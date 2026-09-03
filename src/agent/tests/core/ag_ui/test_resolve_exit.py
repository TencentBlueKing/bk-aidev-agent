# -*- coding: utf-8 -*-
"""``_resolve_exit`` 退出中断处理器单元测试（44 D-12 / 退出中断内聚重构）。

``_resolve_exit(state, last_node_name) -> ExitResult`` 是 LangGraph Agent 退出时的
中断处理器：前段经注入的 ``InterruptProcessor`` 全量收集 ``state.tasks`` pending
并 per-reason prepare（建单 + 就地 enrich），enrich 先于归一化；后段推导
node_name / is_end_node / interrupt_values / outcome。剩余副作用（_dispatch_event
多态 DB 写 / _emit_run_end_extras 子类 hook）仍挡调用方——本方法不产出事件、
不 yield。D-12 修正：空 ``state.values`` 时 ``state_values`` 用 ``{}``，
不传 StateSnapshot 对象。

测试沿用 test_interrupt_wiring.py ``__new__`` + 显式属性赋值构造模式（绕过构造依赖）。
"""

import inspect

from aidev_agent.core.ag_ui.agent import LangGraphAgent
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import Interrupt, RunFinishedInterruptOutcome, RunFinishedSuccessOutcome
from aidev_agent.packages.interrupt_manager import TOOL_APPROVAL_REASON
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor


def _task(*intrs):
    """构造挂起 task 鸭子类型（``.interrupts`` 元组，processor 收集单位）。"""
    from types import SimpleNamespace

    return SimpleNamespace(name="tools", id="task-1", interrupts=intrs)


def _fake_state(
    *,
    tasks=(),
    writes=None,
    next_nodes=(),
    values=None,
):
    """构造 ``_resolve_exit`` 消费的 langgraph state 鸭子类型。

    ``_resolve_exit`` 内部经 ``state.tasks``（dispatch 收集 + node_name 推导）/
    ``getattr(state, "metadata", None).get("writes", {})`` /
    ``getattr(state, "next", None)`` / ``getattr(state, "values", None)`` 取值，
    故本桩仅需提供这四个属性。``tasks`` 须为带 ``.interrupts`` 的 task 对象列表。
    """

    class _FakeState:
        pass

    st = _FakeState()
    st.tasks = tasks
    st.metadata = {"writes": writes or {}}
    st.next = next_nodes
    st.values = values
    return st


def _make_agent():
    """构造持有注入 processor 的最小 agent（__new__ + 显式属性赋值）。"""
    agent = LangGraphAgent.__new__(LangGraphAgent)
    agent._interrupt_processor = InterruptProcessor()
    agent.active_run = {"thread_id": "sess-1", "id": "run-1"}
    return agent


def _pending_intr(reason="tool_call", tool_call_id="call_1", message="需要审批"):
    """构造 pending interrupt 鸭子类型（.id / .value）。"""
    from types import SimpleNamespace

    value = {
        "reason": reason,
        "toolCallId": tool_call_id,
        "message": message,
    }
    return SimpleNamespace(value=value, id=f"int-{tool_call_id}")


def test_resolve_exit_returns_dataclass_fields():
    """``_resolve_exit`` 返回 ExitResult，字段含 node_name / is_end_node /
    interrupt_values / state_values / outcome。"""
    agent = _make_agent()
    state = _fake_state(tasks=[], values={"messages": []})
    result = agent._resolve_exit(state, last_node_name="__end__")

    assert hasattr(result, "node_name")
    assert hasattr(result, "is_end_node")
    assert hasattr(result, "interrupt_values")
    assert hasattr(result, "state_values")
    assert hasattr(result, "outcome")
    # 无 tasks + 无 next → 终态节点
    assert result.node_name == "__end__"
    assert result.is_end_node is True
    assert isinstance(result.state_values, dict)
    assert isinstance(result.outcome, RunFinishedSuccessOutcome)


def test_resolve_exit_interrupt_outcome_and_values():
    """有 pending interrupt 时 outcome 为 RunFinishedInterruptOutcome，interrupt_values 归一为 Interrupt。"""
    agent = _make_agent()
    intr = _pending_intr()
    state = _fake_state(tasks=[_task(intr)], next_nodes=("tools",), values={"messages": []})
    result = agent._resolve_exit(state, last_node_name="tools")

    assert isinstance(result.outcome, RunFinishedInterruptOutcome)
    assert isinstance(result.interrupt_values, list)
    assert isinstance(result.interrupt_values[0], Interrupt)
    assert result.interrupt_values[0].reason == "tool_call"


def test_resolve_exit_no_event_production():
    """静态断言：``_resolve_exit`` 源码无 ``yield`` 且无 ``_dispatch_event`` 引用。

    剩余契约（D-07 收敛后存留部分）：dispatch 内聚于本方法，但事件派发（多态
    DB 写 / RUN_FINISHED）仍由调用方按顺序协议执行——本方法不产出事件、不 yield。
    """
    src = inspect.getsource(LangGraphAgent._resolve_exit)
    assert "yield" not in src, "退出块内部不应出现 yield（事件派发由调用方承担）"
    assert "self._dispatch_event" not in src, "退出块内部不应直接派发事件（事件派发由调用方承担）"


def test_resolve_exit_empty_values_not_state_object():
    """D-12 修正：state.values 为空 dict 时 state_values 是 dict（{}），不是 StateSnapshot 对象。"""
    agent = _make_agent()
    state = _fake_state(tasks=[], values={})
    result = agent._resolve_exit(state, last_node_name="__end__")

    assert isinstance(result.state_values, dict), "空 values 时 state_values 应为 dict，而非 StateSnapshot 对象（D-12）"
    assert result.state_values == {}, "空 values 时 state_values 应为空 dict"


def test_resolve_exit_node_name_from_tasks():
    """有 tasks（挂起）时 node_name 取 last_node_name（活跃节点），is_end_node=False。"""
    agent = _make_agent()
    intr = _pending_intr()
    state = _fake_state(tasks=[_task(intr)], next_nodes=("tools",), values={"messages": []})
    result = agent._resolve_exit(state, last_node_name="tools")

    assert result.node_name == "tools"
    assert result.is_end_node is False


def test_resolve_exit_outcome_single_active_interrupt_for_db():
    """串行语义（用户裁定 2026-08-31）：_resolve_exit 的 outcome.interrupts 单元素。

    outcome.interrupts 是 base.py handle_run_finished 的 DB 落库源（经
    _dispatch_event 的 _event_handler）。DB 一次只写一个 interrupt message——只写
    当前活跃（首个）pending；下一个 interrupt 在成为活跃时（分支 B
    _build_next_interrupt_events 路径）才写入。SSE 侧 _trim_run_finished_interrupts_for_sse
    仍为 no-op 防御。2 个 pending → outcome.interrupts 长度 == 1（首个活跃）。
    """
    agent = _make_agent()
    intr1 = _pending_intr(tool_call_id="call_1", message="审批 A")
    intr2 = _pending_intr(tool_call_id="call_2", message="审批 B")
    state = _fake_state(tasks=[_task(intr1, intr2)], next_nodes=("tools",), values={"messages": []})

    result = agent._resolve_exit(state, last_node_name="tools")

    assert isinstance(result.outcome, RunFinishedInterruptOutcome)
    # 单元素（串行语义：DB 仅写当前活跃 interrupt），非全量
    assert len(result.outcome.interrupts) == 1, (
        "串行语义：outcome.interrupts 仅保留首个活跃 pending（DB 一次只写一个 interrupt message）"
    )
    assert result.outcome.interrupts[0].toolCallId == "call_1"


def test_trim_run_finished_interrupts_for_sse_single_element():
    """串行语义（用户裁定 2026-08-31）：SSE 边界防御性裁剪 outcome.interrupts 为单元素。

    ``_trim_run_finished_interrupts_for_sse`` 在 SSE 序列化边界裁剪为单元素（首个活跃
    pending）。源头已单元素化后此处为 no-op 防御，但对多元素输入仍兜底裁剪。approval
    中断 metadata 顺带精简为仅 ticket（非 approval 保留完整 metadata）。
    """
    # 2 个 pending 的 outcome（防御验证：多元素输入被裁剪）
    outcome = {
        "type": "interrupt",
        "interrupts": [
            {
                "id": "i-1",
                "reason": TOOL_APPROVAL_REASON,
                "toolCallId": "call_1",
                "metadata": {"type": "tool_approval", "ticket": {"sn": "T1"}, "toolName": "A"},
            },
            {
                "id": "i-2",
                "reason": TOOL_APPROVAL_REASON,
                "toolCallId": "call_2",
                "metadata": {"type": "tool_approval", "ticket": {"sn": "T2"}, "toolName": "B"},
            },
        ],
    }
    AidevAGUIAgent._trim_run_finished_interrupts_for_sse(outcome)

    assert outcome["type"] == "interrupt"
    assert len(outcome["interrupts"]) == 1, "SSE 边界裁剪为单元素（防御，源头已单元素）"
    assert outcome["interrupts"][0]["toolCallId"] == "call_1", "只保留第一个活跃 pending"
    assert outcome["interrupts"][0]["metadata"] == {"ticket": {"sn": "T1"}}, "approval 中断 metadata 精简为仅 ticket"


def test_trim_run_finished_interrupts_for_sse_ignores_non_interrupt_outcome():
    """HI-02：非 interrupt outcome（如 success / cancelled）不被 SSE 裁剪触碰。"""
    outcome = {"type": "success", "interrupts": [{"id": "i-1"}, {"id": "i-2"}]}
    AidevAGUIAgent._trim_run_finished_interrupts_for_sse(outcome)
    assert len(outcome["interrupts"]) == 2, "非 interrupt outcome 不裁剪"
