# -*- coding: utf-8 -*-
"""InterruptProcessor resume 侧单元测试（48 v3 语义重写后迁移）。

覆盖（对齐 48-01/02/03 迁移基准 CD-05，保留 live 行为断言）：

- 单中断裸列表 Command(resume) 构造（``build_command_resume``）
- 多中断 resume-map Command(resume) 构造（Task 1 实测结论，xxh3 key）
- ``_pick_claimed_value`` / ``_build_resume_map`` 未就绪 pending 不写入 resume-map
  （D-10，不误拒绝）
- ``_unified_resume_values`` ask_user 值改 DB 权威源（GATE-03，弃前端透传）
- ApprovalStateHandler ``_get_client`` 未注入 RM 时抛明确错误（D-06）

**删除的旧架构测试**（RESEARCH Pitfall 6：删除锁定已死机制的测试）：
- ``resolve_resumes`` 返回 ``ResolveResult``（六态 action / dispatch_events /
  approve_result / next_interrupt / command / ask_user_question_interrupts）
  ——48-01 D-16 后 ``resolve_resumes`` **无返回值**（on_resume 语义），装配层改走
  ``get_resume_input``（ready/command/回放三字段），本文件不再测已死的六态聚合返回。
- ``registry.get_handler`` / ``registry._HANDLERS`` / ``DEFAULT_HANDLER``（D-01
  注册表机制删除，改 handlers dict 注入）。
- ``consume_resume``（D-16 收编进 ``on_resume``）。
- ``terminal_interrupt_ids`` ctx（U-04 废除，get_resume_input 内部自推导）。
- ``InterruptProcessor(resource_manager=...)`` / ``ticket_creator=`` 构造参数
  （D-03 改 handlers dict 注入）。
"""

from types import SimpleNamespace

from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from aidev_agent.packages.interrupt_manager.types import (
    TOOL_APPROVAL_REASON,
)
from langgraph.types import Command

# ---------------------------------------------------------------------- #
# 单中断裸列表 / 多中断 resume-map Command 构造（build_command_resume Do-Not-Break）
# ---------------------------------------------------------------------- #


def _approval_pending_task(tool_call_id="tc-1"):
    """构造一个带 pending approval interrupt 的 task（SimpleNamespace 鸭子类型）。"""
    return SimpleNamespace(
        name="tools",
        id="task-approval-1",
        interrupts=(
            SimpleNamespace(
                value={"reason": TOOL_APPROVAL_REASON, "toolCallId": tool_call_id, "id": "int-1"},
            ),
        ),
    )


def test_single_interrupt_bare_list_command():
    """单中断 → Command(resume=[value])（裸列表，兼容 chat.py 现例）。"""
    coordinator = InterruptProcessor()
    command = coordinator.build_command_resume(
        tasks=[_approval_pending_task("tc-1")],
        resume_values=[{"interruptId": "int-1", "status": "resolved", "payload": {"approved": True}}],
    )
    assert isinstance(command, Command)
    assert isinstance(command.resume, list)
    assert command.resume[0]["interruptId"] == "int-1"


def test_multi_interrupt_resume_map_command():
    """多中断 → Command(resume={namespace_hash: value})（Task 1 实测结论，xxh3 key Do-Not-Break）。"""
    from xxhash import xxh3_128_hexdigest

    task_a = SimpleNamespace(
        name="tools",
        id="task-a",
        interrupts=(SimpleNamespace(value={"reason": TOOL_APPROVAL_REASON, "toolCallId": "tc-a", "id": "int-a"}),),
    )
    task_b = SimpleNamespace(
        name="tools",
        id="task-b",
        interrupts=(SimpleNamespace(value={"reason": TOOL_APPROVAL_REASON, "toolCallId": "tc-b", "id": "int-b"}),),
    )
    coordinator = InterruptProcessor()
    command = coordinator.build_command_resume(
        tasks=[task_a, task_b],
        resume_values=[
            {"interruptId": "int-a", "toolCallId": "tc-a", "status": "resolved", "payload": {"approved": True}},
            {"interruptId": "int-b", "toolCallId": "tc-b", "status": "resolved", "payload": {"approved": True}},
        ],
    )
    assert isinstance(command, Command)
    assert isinstance(command.resume, dict), f"多中断应构造 resume-map，实际 {type(command.resume)}"
    # key = xxh3_128_hexdigest(f"{task.name}:{task.id}")
    assert xxh3_128_hexdigest("tools:task-a".encode()) in command.resume
    assert xxh3_128_hexdigest("tools:task-b".encode()) in command.resume
    # 每个 key 的值按其 toolCallId 关联到对应 resume item
    assert command.resume[xxh3_128_hexdigest("tools:task-a".encode())]["toolCallId"] == "tc-a"
    assert command.resume[xxh3_128_hexdigest("tools:task-b".encode())]["toolCallId"] == "tc-b"


def test_resume_map_prebuilt_passthrough():
    """调用方已构造 resume-map → 原样透传（不重复推导）。"""
    coordinator = InterruptProcessor()
    prebuilt = {"abc123": {"approved": True}}
    command = coordinator.build_command_resume(tasks=[], resume_values=prebuilt)
    assert command.resume == prebuilt


def test_approval_state_handler_requires_rm_for_db_access():
    """ApprovalStateHandler 未注入 RM 时 DB 访问方法兜底返回 False，_get_client 抛明确错误（D-06）。"""
    from aidev_agent.packages.interrupt_manager.approval import ApprovalStateHandler

    handler = ApprovalStateHandler(resource_manager=None)
    # _get_client 明确抛出未注入错误（供上层定位，D-06 收敛）
    try:
        handler._get_client()
    except RuntimeError as exc:
        assert "resource_manager" in str(exc)
    else:
        raise AssertionError("未注入 RM 的 _get_client 应抛 RuntimeError")
    # check_resume 对任何异常兜底返回 False（安全默认：非 resume 会话）
    assert handler.check_resume("s1") is False


# ---------------------------------------------------------------------- #
# D-10：未就绪 pending 不写入 resume-map（不误拒绝）
# ---------------------------------------------------------------------- #


def test_pick_resume_value_returns_none_when_all_exhausted():
    """D-10：``_pick_claimed_value`` 全部未匹配时返回 None（非 ``{}``）。"""
    coordinator = InterruptProcessor()
    pending_task = _approval_pending_task("tc-unmatched")
    # resume_items 为空：无匹配项（双索引均空，不顺序兜底）
    result = coordinator._pick_claimed_value(pending_task, {}, {}, [], set())
    assert result is None, "D-10：未匹配 resume item 时精确认领应返回 None（非 {}）"


def test_build_resume_map_excludes_unready_pending_key():
    """D-10：``_build_resume_map`` 对未匹配 resume item 的 pending task 不写入其 key。

    未就绪 pending 保持挂起（串行语义下由下一轮 resume 处理），避免
    ``_is_approved({})``=False 误判拒绝（T-44-03）。
    """
    from xxhash import xxh3_128_hexdigest

    coordinator = InterruptProcessor()
    # task_a 匹配到 resume item（tc-a）；task_b 无匹配（tc-b 不在 resume_items）
    task_a = SimpleNamespace(
        name="tools",
        id="task-a",
        interrupts=(SimpleNamespace(value={"reason": TOOL_APPROVAL_REASON, "toolCallId": "tc-a", "id": "int-a"}),),
    )
    task_b = SimpleNamespace(
        name="tools",
        id="task-b",
        interrupts=(SimpleNamespace(value={"reason": TOOL_APPROVAL_REASON, "toolCallId": "tc-b", "id": "int-b"}),),
    )
    resume_items = [{"interruptId": "int-a", "toolCallId": "tc-a", "status": "resolved", "payload": {"approved": True}}]

    resume_map = coordinator._build_resume_map([task_a, task_b], resume_items)

    key_a = xxh3_128_hexdigest("tools:task-a".encode())
    key_b = xxh3_128_hexdigest("tools:task-b".encode())
    assert key_a in resume_map, "已就绪 task（匹配到 resume item）应写入 resume-map"
    assert resume_map[key_a]["toolCallId"] == "tc-a"
    assert key_b not in resume_map, "D-10：未就绪 pending 不应写入 resume-map（key_b 缺席，保持挂起）"


# ---------------------------------------------------------------------- #
# GATE-03：_unified_resume_values ask_user 值改 DB 权威源（弃前端透传）
# ---------------------------------------------------------------------- #


def test_unified_resume_values_ask_user_uses_db_authoritative():
    """GATE-03：ask_user resume 值改 DB 权威源（弃前端透传，T-46-01）。

    全就绪时 ask_user gate 产 DB 权威元素（{interruptId, status, payload:{answers}}），
    前端 items 透传的 answers 项整体弃用——前端伪造答案无从透传。action="resolved"
    不在 ApproveResult.ALL → 天然不走 hydrate_resume_payload（answers 不被注入 approved）。
    """
    processor = InterruptProcessor()
    unit_results = [
        {
            "action": "resolved",  # ask_user gate action（不在 ApproveResult.ALL → 不走 hydrate）
            "resume_value": {
                "interruptId": "int-q",
                "status": "resolved",
                "payload": {"answers": ["是"]},  # DB 权威 answers
            },
        }
    ]
    # 前端 resume 透传伪造答案（与 DB 不一致，T-46-01 防伪造）
    resume = [{"interruptId": "int-q", "status": "resolved", "payload": {"answers": ["伪造答案"]}}]

    values = processor._unified_resume_values(unit_results, resume)

    # 应只有 gate 的 DB 权威元素（前端 answers 项被整体弃用）
    assert len(values) == 1, f"GATE-03：前端 answers 项应整体弃用，只保留 gate DB 权威元素；实际 {values}"
    assert values[0]["payload"]["answers"] == ["是"], (
        "GATE-03：ask_user 值必须来自 gate DB 权威 answers，弃前端透传（伪造答案不得出现）"
    )
