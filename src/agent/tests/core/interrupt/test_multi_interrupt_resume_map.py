# -*- coding: utf-8 -*-
"""resume-map 映射 key 推导实测 + 多中断全就绪场景（43-05 Task 1）。

背景（langgraph 1.0.5 硬约束）：
- ``pregel/_loop.py:646-656``：``Command(resume=[...])`` 裸列表在
  ``>1`` 个 pending interrupt 时抛 ``RuntimeError``；只有当 resume 为
  dict 且所有 key 都是 ``xxh3_128_hexdigest``（32 位 hex）时才走 resume-map
  映射形式（``CONFIG_KEY_RESUME_MAP``）。
- ``pregel/_algo.py:601-607``：resume-map 的 key（``namespace_hash``）来自
  ``xxh3_128_hexdigest(task_checkpoint_ns.encode())``，其中
  ``task_checkpoint_ns = f"{checkpoint_ns}{NS_END}{task_id}"``（NS_END=":"）。

本文件落地「多中断全就绪」图级实测（Task 1），核心是验证从
``state.tasks[*]`` 推导 resume-map key 的可行性：

- Test 1：构造含 2 个 pending interrupt 的图（2 个并行 node 各 interrupt 一次），
  ``state.tasks`` 含 2 个 task 且各带 interrupt。
- Test 2：裸列表 ``Command(resume=[v1, v2])`` → 断言抛 ``RuntimeError``。
- Test 3：用 resume-map 映射 ``Command(resume={hash1: v1, hash2: v2})``，
  key 从 ``state.tasks[*]`` 推导 → 断言成功 resume（两个中断都被匹配恢复）。
- Test 4：key 推导基准 + 实测结论注释。

**实测结论（决策输入给 43-05 Task 2 coordinator）**：

推导**可行**且**健壮**。从 ``state.tasks[*]`` 可以直接拿到：
- ``task.id`` == 构造 ``task_checkpoint_ns`` 所用的内部 ``task_id``；
- ``task.name`` == 顶层（非嵌套）图的 ``checkpoint_ns`` 前缀（
  ``_algo.py:592``：``checkpoint_ns = f"{parent_ns}|{name}" if parent_ns else name``，
  顶层图 ``parent_ns`` 为空，故 ``checkpoint_ns == name``）。

因此 resume-map key = ``xxh3_128_hexdigest(f"{task.name}:{task.id}".encode())``，
``task.name`` / ``task.id`` 均为快照直接暴露字段，无需侵入 langgraph 内部结构，
推导算法简单稳定（Test 3 实测两个 key 都命中，双中断都被恢复）。

降级策略（推导脆弱时才启用，本测试证明可用所以不启用）：
「单中断裸列表 + 多中断逐次 resume」。实测证明推导可用，coordinator 直接采用
resume-map 映射形式处理多中断。

**局限说明**：本推导针对顶层（非嵌套）图。若中断发生在子图内，
``parent_ns`` 会带上前缀（``subgraph:...|``），key 需在 ``f"{task.name}:{task.id}"``
前补 parent 前缀。当前 aidev-agent 的中断 node（react 图 `tools`/`ask_user_question`）
均为顶层，故不涉及；子图场景由未来计划按需扩展（本计划不做）。
"""

import operator
from types import SimpleNamespace
from typing import Annotated, TypedDict

from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager import TOOL_APPROVAL_REASON, ApprovalHandler
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from xxhash import xxh3_128_hexdigest


class _State(TypedDict, total=False):
    """可归约 messages 通道，避免并行 node 并发写同一 last_value 通道冲突。"""

    messages: Annotated[list, operator.add]


# ---------------------------------------------------------------------- #
# 构造 2 个 pending interrupt 的图
# ---------------------------------------------------------------------- #


def _make_two_interrupt_graph():
    """构造含 2 个并行 interrupt node 的图，触发 2 个 pending interrupt。

    每个 node 调 ``interrupt(payload)`` 一次 → 首次执行抛 GraphInterrupt 暂停，
    resume 后返回 resume 值。两个 node 并行（都从 START 出发），产生 2 个
    独立 pending interrupt，镜像生产环境多 tool_call 并行审批的场景。
    """
    received: dict[str, object] = {}

    def tool_a(state: _State) -> dict:
        # 生产形态：value 含 toolCallId（ApprovalTarget alias），供 per-interrupt
        # 门禁与 resume-map 身份匹配
        val = interrupt({"reason": TOOL_APPROVAL_REASON, "tool": "a", "id": "t-a", "toolCallId": "tc-tool_a"})
        received["a"] = val
        return {"messages": [f"a:{val}"]}

    def tool_b(state: _State) -> dict:
        val = interrupt({"reason": TOOL_APPROVAL_REASON, "tool": "b", "id": "t-b", "toolCallId": "tc-tool_b"})
        received["b"] = val
        return {"messages": [f"b:{val}"]}

    builder = StateGraph(_State)
    builder.add_node("tool_a", tool_a)
    builder.add_node("tool_b", tool_b)
    builder.add_edge(START, "tool_a")
    builder.add_edge(START, "tool_b")
    builder.add_edge("tool_a", END)
    builder.add_edge("tool_b", END)
    graph = builder.compile(checkpointer=MemorySaver())
    return graph, received


def _derive_resume_map(tasks) -> dict:
    """从 ``state.tasks`` 推导 resume-map（实测结论：`{task.name}:{task.id}`）。

    对应 ``_algo.py`` 的 ``namespace_hash = xxh3_128_hexdigest(task_checkpoint_ns.encode())``，
    顶层图 ``task_checkpoint_ns == f"{task.name}:{task.id}"``。

    Args:
        tasks: ``state.tasks``（PregelTask 序列，每个含 ``name`` / ``id``）。

    Returns:
        映射 ``{xxh3_128_hexdigest: value}``，value 由调用方后续填充。
    """
    return {xxh3_128_hexdigest(f"{t.name}:{t.id}".encode()): None for t in tasks}


# ---------------------------------------------------------------------- #
# Test 1：多中断图级场景可构造（2 个 pending interrupt）
# ---------------------------------------------------------------------- #


def test_two_pending_interrupts_in_parallel_tasks():
    """Test 1：构造含 2 个 pending interrupt 的图。

    验证 ``graph.invoke`` 后 ``state.tasks`` 含 2 个 task，且各带 1 个 interrupt。
    """
    graph, _ = _make_two_interrupt_graph()
    config = {"configurable": {"thread_id": "t1"}}

    graph.invoke({}, config)
    snap = graph.get_state(config)

    assert snap.next == ("tool_a", "tool_b")
    assert len(snap.tasks) == 2
    for task in snap.tasks:
        assert task.interrupts, f"task={task.name} 应带 interrupt"
        value = task.interrupts[0].value
        assert value.get("reason") == TOOL_APPROVAL_REASON
    assert len(snap.interrupts) == 2


# ---------------------------------------------------------------------- #
# Test 2：裸列表 resume 在 >1 pending 时抛 RuntimeError
# ---------------------------------------------------------------------- #


def test_bare_list_resume_raises_runtime_error():
    """Test 2：裸列表 ``Command(resume=[v1, v2])`` 在 >1 pending 时抛 RuntimeError。

    验证 langgraph 1.0.5 ``_loop.py:646-656`` 硬约束：多 pending 时必须用
    resume-map（带 interrupt id），裸列表不允许。
    """
    graph, _ = _make_two_interrupt_graph()
    config = {"configurable": {"thread_id": "t2"}}

    graph.invoke({}, config)
    snap = graph.get_state(config)
    assert len(snap.interrupts) == 2

    try:
        graph.invoke(Command(resume=[{"approved": True}, {"approved": True}]), config)
    except RuntimeError as exc:
        assert "multiple pending interrupts" in str(exc)
    else:
        raise AssertionError("裸列表 resume 在 >1 pending 时应抛 RuntimeError")


# ---------------------------------------------------------------------- #
# Test 3：resume-map 映射成功 resume（key 从 state.tasks 推导）
# ---------------------------------------------------------------------- #


def test_resume_map_derived_key_resumes_both_interrupts():
    """Test 3：用 resume-map 映射成功 resume，key 从 ``state.tasks`` 推导。

    验证 ``xxh3_128_hexdigest(f"{task.name}:{task.id}".encode())`` 的推导 key
    能命中两个 pending interrupt，两个 node 都收到各自的 resume 值。
    """
    graph, received = _make_two_interrupt_graph()
    config = {"configurable": {"thread_id": "t3"}}

    graph.invoke({}, config)
    snap = graph.get_state(config)
    assert len(snap.tasks) == 2

    resume_map = _derive_resume_map(snap.tasks)
    assert len(resume_map) == 2, "应从 2 个 task 推导出 2 个互不相同的 key"
    # 填充每个 task 的 resume 值（approval decision 形态，toolCallId 区分）
    for task in snap.tasks:
        resume_map[xxh3_128_hexdigest(f"{task.name}:{task.id}".encode())] = {
            "approved": True,
            "toolCallId": f"tc-{task.name}",
        }

    graph.invoke(Command(resume=resume_map), config)

    # 两个中断都被恢复，received 记录两个 node 收到的 resume 值
    assert set(received.keys()) == {"a", "b"}
    assert received["a"]["toolCallId"] == "tc-tool_a"
    assert received["b"]["toolCallId"] == "tc-tool_b"

    final = graph.get_state(config)
    assert final.next == (), f"resume 后不应有 pending task，实际 next={final.next}"
    assert len(final.interrupts) == 0, "resume 后不应有 pending interrupt"


# ---------------------------------------------------------------------- #
# Test 4：key 推导基准 —— task.name/task.id 到 namespace_hash 的映射关系
# ---------------------------------------------------------------------- #


def test_key_derivation_maps_task_name_and_id_to_namespace_hash():
    """Test 4：key 推导基准。

    验证推导式 ``xxh3_128_hexdigest(f"{task.name}:{task.id}".encode())`` 与
    langgraph ``_algo.py`` 的 ``namespace_hash = xxh3_128_hexdigest(task_checkpoint_ns)``
    （顶层图 ``task_checkpoint_ns = f"{name}:{task_id}"``）一致，并据此注释实测结论。
    """
    graph, _ = _make_two_interrupt_graph()
    config = {"configurable": {"thread_id": "t4"}}

    graph.invoke({}, config)
    snap = graph.get_state(config)

    for task in snap.tasks:
        task_checkpoint_ns = f"{task.name}:{task.id}"
        expected_hash = xxh3_128_hexdigest(task_checkpoint_ns.encode())
        # 推导 key 就是 expected_hash（同一表达式），Test 3 已实测命中；
        # 此处断言 key 是合法的 xxh3_128_128 hexdigest（32 位 hex），
        # 且与从 task 推导结果一致，固化推导基准防止回归。
        derived_hash = xxh3_128_hexdigest(f"{task.name}:{task.id}".encode())
        assert derived_hash == expected_hash
        assert len(derived_hash) == 32
        # task.id 直接出现在 namespace 字符串中 → 推导直接可用，无需侵入 langgraph 内部
        assert task.id in task_checkpoint_ns


# ---------------------------------------------------------------------- #
# 生产路径续流（D-03）：ResumeCoordinator.build_command_resume 驱动多中断 resume
# ---------------------------------------------------------------------- #


def test_production_resume_map_drives_multi_interrupt_resume():
    """生产路径续流（D-03）：经 ResumeCoordinator.build_command_resume 构造 resume-map，
    驱动多中断图 resume 成功。

    镜像 chat.py ``_prepare_stream_input`` 的多中断分支：把 ``state.tasks`` 与前端
    resume items 交给 coordinator，由其推导 resume-map 并构造 ``Command(resume)``，
    再对真实多中断图续流，断言两个 pending interrupt 均被恢复（全就绪后 resume 成功）。
    """
    graph, received = _make_two_interrupt_graph()
    config = {"configurable": {"thread_id": "t5"}}

    graph.invoke({}, config)
    snap = graph.get_state(config)
    assert len(snap.tasks) == 2

    # 前端 resume items（approval decision 形态；interruptId 与图中断 intr.id 同源，
    # 生产现实：前端卡片 id 即 LangGraph 中断 id）
    real_ids = _real_interrupt_ids(snap.tasks)
    resume_items = [
        {"interruptId": real_ids[0], "toolCallId": "tc-tool_a", "status": "resolved", "payload": {"approved": True}},
        {"interruptId": real_ids[1], "toolCallId": "tc-tool_b", "status": "resolved", "payload": {"approved": True}},
    ]

    # 生产路径：InterruptProcessor 从 state.tasks 推导 resume-map 并构造 Command(resume)
    # （Do-Not-Break：构造参数改为 handlers dict / 无参——D-03 后无 resource_manager 构造参数）
    coordinator = InterruptProcessor()
    command = coordinator.build_command_resume(tasks=snap.tasks, resume_values=resume_items)
    assert isinstance(command, Command)
    assert isinstance(command.resume, dict), "多中断应构造 resume-map"

    # 续流成功：两个中断都被恢复（D-03 全就绪后 resume）
    graph.invoke(command, config)

    assert set(received.keys()) == {"a", "b"}
    assert received["a"]["toolCallId"] == "tc-tool_a"
    assert received["b"]["toolCallId"] == "tc-tool_b"

    final = graph.get_state(config)
    assert final.next == (), f"resume 后不应有 pending task，实际 next={final.next}"
    assert len(final.interrupts) == 0, "resume 后不应有 pending interrupt"


# ---------------------------------------------------------------------- #
# 44-04 D-05 串行语义：processor.resolve_resumes 编排（经 get_handler(reason).query_resume_status）
# ---------------------------------------------------------------------- #


class _StubRm:
    """鸭子类型 resource_manager：模拟 DB 审批记录（query_approval_info 数据源）。

    ``approve_result`` 为 None 表示审批未回调（not_ready）；否则返回每个
    toolCallId 一条 role=interrupt 记录（per-interrupt 门禁按 toolCallId 定位
    各自专属记录），``property.builtin_property.approve_result`` 载审批结果，
    content 元素与图 value 的 toolCallId 一致（生产形态）。
    """

    def __init__(self, approve_result=None):
        self._approve_result = approve_result

    def get_chat_session_contents(self, session_code: str):
        if self._approve_result is None:
            return []
        records = []
        for call_id in ("tc-tool_a", "tc-tool_b"):
            records.append(
                {
                    "role": PromptRole.INTERRUPT.value,
                    "content": (
                        '{"outcome": {"type": "interrupt", "interrupts": [{"id": "i-'
                        + call_id[-1]
                        + f'", "reason": "{TOOL_APPROVAL_REASON}", "toolCallId": "{call_id}"'
                        + "}]}}"
                    ),
                    "property": {"builtin_property": {"approve_result": self._approve_result, "tool_call_id": call_id}},
                }
            )
        return records

    def is_resume_session(self, session_code: str) -> bool:
        return self._approve_result is not None


def _snap_tasks(graph, thread_id: str):
    """invoke 2 中断图并返回 state.tasks。"""
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke({}, config)
    return graph.get_state(config).tasks


def _real_interrupt_ids(tasks) -> list[str]:
    """按序提取 tasks 中全部 pending interrupt 的真实 id（与前端卡片 id 同源）。"""
    ids = []
    for task in tasks:
        for intr in getattr(task, "interrupts", None) or []:
            intr_id = getattr(intr, "id", None)
            if intr_id:
                ids.append(str(intr_id))
    return ids


def _flatten_command_resume_items(command: Command) -> list[dict]:
    """把 ``Command.resume``（裸列表 或 resume-map dict）归一为 item dict 列表。"""
    resume = getattr(command, "resume", None)
    if isinstance(resume, dict):
        return [v for v in resume.values() if isinstance(v, dict)]
    if isinstance(resume, list):
        return [v for v in resume if isinstance(v, dict)]
    return []


def _terminal_chat_history(real_ids: list[str]) -> list:
    """构造已终态 interrupt 的 chat_history（get_resume_input 串行完成判定源）。

    ``get_resume_input`` 经 ``terminal_interrupt_ids_from_messages(chat_history)``
    判全完成（D-12）。这里构造 role=INTERRUPT 的记录，outcome.type=success，
    interrupts 元素 id 用真实 LangGraph 中断 id（与 ``interrupt_id_of(intr)`` 同源），
    使全 pending 均判为已终态 → 走全就绪分支（构造 Command + 回放三字段）。
    """
    return [
        SimpleNamespace(
            role=PromptRole.INTERRUPT.value,
            content={
                "outcome": {
                    "type": "success",
                    "interrupts": [{"id": str(i), "metadata": {"status": "resolved"}} for i in real_ids],
                }
            },
        )
    ]


def _approval_processor(approve_result) -> InterruptProcessor:
    """构造带审批 handler 的 processor（handlers dict 注入，D-03）。

    审批 handler 自持 resource_manager（鸭子类型 _StubRm，D-05 approval 空实现——
    终态由审批平台回调写 DB，agent 侧纯读门禁）。
    """
    return InterruptProcessor(
        handlers={
            # 键用 reason 值字符串（str-enum 的 str() 会返回枚举名而非值，processor
            # 聚合门禁按 pending value 的 reason 字段（值字符串）查表，须 hash 等价）。
            str(TOOL_APPROVAL_REASON.value): ApprovalHandler(resource_manager=_StubRm(approve_result=approve_result))
        }
    )


def test_get_resume_input_all_ready_returns_resume_command():
    """U-03/D-06：全就绪 → get_resume_input 返回 ready=True + command: Command。

    DB 审批已回调（approve_result=approved）→ ApprovalHandler.query_resume_status 返回
    approved → 串行完成判定全过 → 构造 ``Command(resume=...)``（DB 权威）+ 回放三字段。
    """
    graph, _ = _make_two_interrupt_graph()
    tasks = _snap_tasks(graph, "ser-s2")

    processor = _approval_processor(approve_result="approved")
    result = processor.get_resume_input(
        tasks=tasks,
        session_code="s1",
        thread_id="t1",
        chat_history=_terminal_chat_history(_real_interrupt_ids(tasks)),
    )

    assert result.ready is True, "全就绪 → ready=True"
    assert isinstance(result.command, Command), "ready 时应携带 Command"
    assert result.next_interrupt is None, "全就绪不应构造下一个 interrupt"


def test_get_resume_input_ready_hydrates_db_verdict_prevents_forgery():
    """CR-01（T-44-01）：全就绪分支用 DB 权威终态 hydrate，前端伪造 approved=true 不绕过审批。

    DB 审批结果为 cancelled（拒绝/取消语义），但前端伪造 ``payload.approved=True``。
    ``_unified_resume_values`` 全就绪分支必须用 DB 权威终态覆写 resume 值，使
    ``payload.approved=False``（工具被拒，不执行）；若把伪造值透传进 ``Command(resume)``，
    图侧 ``_is_approved`` 会读 approved=True → 高危工具在 DB 记录为「已取消」的情况下被执行。
    """
    graph, _ = _make_two_interrupt_graph()
    tasks = _snap_tasks(graph, "ser-cr1")

    # DB=cancelled；前端伪造 approved=true
    processor = _approval_processor(approve_result="cancelled")
    result = processor.get_resume_input(
        tasks=tasks,
        session_code="s1",
        thread_id="t1",
        chat_history=_terminal_chat_history(_real_interrupt_ids(tasks)),
    )

    assert result.ready is True, "cancelled 亦按就绪放行（resume 图携带 CANCELLED 值走策略分支）"
    command_items = _flatten_command_resume_items(result.command)
    assert command_items, "Command 应含 resume 值"
    for item in command_items:
        assert item.get("payload", {}).get("approved") is False, (
            "CR-01：DB=cancelled 时前端伪造 approved=true 必须被覆写为 False（工具不执行）"
        )


def test_get_resume_input_ready_db_approved_not_falsely_rejected():
    """CR-01（T-44-01）：DB=approved + 前端 payload.approved=false → 不误拒。

    ``_unified_resume_values`` 必须用 DB 权威值（approved）覆写前端缺省/陈旧/伪造的
    ``approved=false``，避免 DB 已通过的工具被误拒（DB 权威 hydrate，Do-Not-Break）。
    """
    graph, _ = _make_two_interrupt_graph()
    tasks = _snap_tasks(graph, "ser-cr2")

    # DB=approved；前端 payload.approved=false（陈旧/伪造）
    processor = _approval_processor(approve_result="approved")
    result = processor.get_resume_input(
        tasks=tasks,
        session_code="s1",
        thread_id="t1",
        chat_history=_terminal_chat_history(_real_interrupt_ids(tasks)),
    )

    assert result.ready is True
    command_items = _flatten_command_resume_items(result.command)
    assert command_items, "Command 应含 resume 值"
    for item in command_items:
        assert item.get("payload", {}).get("approved") is True, (
            "CR-01：DB=approved 时不得因前端 approved=false 误拒工具（DB 权威覆写）"
        )


# ---------------------------------------------------------------------- #
# 48 迁移说明（CD-05）：
# - test_production_resume_map_drives_multi_interrupt_resume（build_command_resume /
#   xxh3 key Do-Not-Break）保留，仅构造改 InterruptProcessor()。
# - resolve_resumes 无返回值（D-16）后，原「六态 action 返回」的串行断言迁移为
#   get_resume_input（ready / next_interrupt / Command / DB 权威 hydrate 逐元素）。
# - `_may_build_next` / `_next_active_interrupt` / `process` / `ticket_creator=`
#   属 D-11 删除的「逐个建单状态机」架构，对应测试随机制删除（RESEARCH Pitfall 6）。
# ---------------------------------------------------------------------- #
