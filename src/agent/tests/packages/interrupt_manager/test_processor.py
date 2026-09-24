# -*- coding: utf-8 -*-
"""InterruptProcessor 单元测试（48 v3 语义重写后）。

覆盖（对齐 48-01 语义重写 + 48-02/48-03 迁移基准 CD-05）：

- ``dispatch_interrupts``：全量收集（零处理 ``is`` 断言）+ per-reason ``prepare``
  建单恰一次 + 未知 reason 原样放行 built（D-01 不吞中断）+ 状态标注
  （``built`` / ``prepare_failed``；D-11 后无 ``terminal_skipped``/``gated``）
- ``resolve_resumes``：**无返回值**（D-16）——逐 resume 经 interruptId →
  chat_history interrupt_messages → 消息内 reason → ``handler.on_resume`` 路由
  （D-04，不信任前端 reason）
- ``get_resume_input``：串行推进（D-12 终态判定）——全完成构造 Command + 回放
  三字段（ready=True）/ 未完成内部 dispatch 返回 next_interrupt（ready=False）
- Do-Not-Break 原子能力：``_build_resume_map``（xxh3 key + 身份匹配）、
  ``_filter_claimed_items``（防冒领）、``_unified_resume_values``（逐元素
  DB 权威 hydrate，混合终态不连坐）、``build_command_resume``（单裸列表/多 resume-map）
- 对偶单元门禁：``query_resume_status``（per-pending 定位，DB 权威）
- ``AskUserQuestionHandler.on_resume`` 三态分流（skip / answer）

**删除的旧架构测试**（RESEARCH Pitfall 6：删除锁定已死机制的测试，随 48-01/02/03
语义重写 / 回滚 / D-13 收敛一并移除）：
``process``（D-08 拆分后仅 dispatch_interrupts）、``_next_active_interrupt``
（D-11）、原「审批取消/拒绝终态回填事件收集」方法（D-13 回填事件产出全链路删除，
含 ``ResolveResult.dispatch_events`` 承载）、``get_handler`` / ``registry._HANDLERS`` / ``DEFAULT_HANDLER``
（D-01 注册表机制删除，改 handlers dict 注入）、``terminal_interrupt_ids`` ctx
（U-04 废除，get_resume_input 内部自推导）、``consume_resume``（D-16 收编进
``on_resume``）、``_may_build_next``（架构性死，D-11）。

stub 资产（``_StubResourceManager`` / ``_Task`` / ``_Interrupt`` / ``_approval_value``
/ ``_ask_user_value``）复制自 test_dispatcher.py（保留零处理语义）。
"""

from types import SimpleNamespace

from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_REASON,
    TOOL_APPROVAL_REASON,
    AskUserQuestionHandler,
    ItsmTicketCreator,
)
from aidev_agent.packages.interrupt_manager.approval import ApprovalHandler
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from aidev_agent.packages.interrupt_manager.types import (
    DispatchResult,
    ProcessorContext,
)


class _StubResourceManager:
    """鸭子类型 resource_manager（对齐 D-06，mock 友好）。"""

    def __init__(self, create_result=None, create_side_effect=None):
        self.create_result = create_result
        self.create_side_effect = create_side_effect
        self.create_calls: list[tuple[dict, str | None]] = []

    def create_tool_approval(self, payload: dict, *, username: str | None = None, **kwargs) -> dict:
        self.create_calls.append((payload, username))
        if self.create_side_effect is not None:
            raise self.create_side_effect
        return self.create_result or {}


class _Task:
    """模拟 langgraph state.tasks 中的 task（含 interrupts 列表）。"""

    def __init__(self, name: str, task_id: str, interrupts: list):
        self.name = name
        self.id = task_id
        self.interrupts = interrupts


class _Interrupt(SimpleNamespace):
    """LangGraph Interrupt 鸭子类型（.id / .value），零处理分发单元。"""


def _approval_value(**overrides) -> dict:
    """target 形态 approval value（生产真实形态：策略直抛 ApprovalTarget + reason，
    含 approval 配置块；id 只活在 intr.id——value 不含 id 键）。"""
    value = {
        "reason": TOOL_APPROVAL_REASON,
        "target_type": "tool",
        "toolCallId": "call_1",
        "toolName": "测试工具",
        "toolCode": "test_tool",
        "toolArgs": {"a": 1},
        "approval": {"enabled": True, "approvers": ["approver-x"]},
    }
    value.update(overrides)
    return value


def _ask_user_value(**overrides) -> dict:
    """target 形态（含 interrupt_reason / message / toolCallId / expiresAt，无 reason/metadata，**无 id**）。"""
    value = {
        "questions": [{"question": "确认？", "multiSelect": False}],
        "interrupt_reason": ASK_USER_QUESTION_REASON,
        "message": "需要用户回答：确认？",
        "toolCallId": "call_auq",
        "expiresAt": "2026-08-28T00:00:00+00:00",
    }
    value.update(overrides)
    return value


# ---------------------------------------------------------------------- #
# dispatch_interrupts：全量收集（零处理 is 断言）+ 逐项状态标注
# ---------------------------------------------------------------------- #


def _ctx(**overrides) -> ProcessorContext:
    """构造最小 ProcessorContext（Task 1 鸭子对象）。"""
    base = ProcessorContext(thread_id="t1", run_id="r1", session_code="s1")
    base.__dict__.update(overrides)
    return base


def test_dispatch_interrupts_zero_processing_returns_same_objects():
    """dispatch_interrupts 返回与收集的 intr 是同一对象（is 断言）；value dict 内无 id 键。"""
    processor = InterruptProcessor()
    intrs = [
        _Interrupt(value=_ask_user_value(), id="real-auq-1"),
        _Interrupt(value=_approval_value()),
        _Interrupt(value=_ask_user_value(), id="real-auq-2"),
        _Interrupt(value=_approval_value()),
    ]
    tasks = [
        _Task("node_a", "task_1", [intrs[0]]),
        _Task("node_b", "task_2", [intrs[1]]),
        _Task("node_c", "task_3", [intrs[2], intrs[3]]),
    ]
    result = processor.dispatch_interrupts(tasks, _ctx())
    assert isinstance(result, DispatchResult)
    assert len(result.interrupts) == 4
    for i, outcome in enumerate(result.interrupts):
        assert outcome.intr is intrs[i], "dispatch 返回元素应与收集的 intr 同一对象（is 断言）"
        assert "id" not in outcome.intr.value, "value dict 内不应出现 id 键（id 与 value 彻底分离）"


def test_dispatch_interrupts_built_for_prepare_success_and_no_prepare():
    """dispatch 逐项状态：prepare 成功（approval enrich）与 handler 无建单副作用（ask_user）均标 built。

    返回 :class:`DispatchResult`（非裸 list），intr 零处理保留同对象；approval prepare
    产物经 extract_builtin_property 落在 outcome.builtin_property。ask_user 置于独立
    dispatch 避免 D-04 门禁干扰，验证无建单副作用仍标 built。
    """
    rm = _StubResourceManager(
        create_result={"ticket": {"sn": "TICKET-DISPATCH", "status": "pending"}, "callback_token": "cb_d"}
    )
    processor = InterruptProcessor(
        handlers={
            str(TOOL_APPROVAL_REASON.value): ApprovalHandler(
                resource_manager=rm,
                ticket_creator=ItsmTicketCreator(rm, username="alice", session_code="s1"),
            ),
            str(ASK_USER_QUESTION_REASON.value): AskUserQuestionHandler(),
        }
    )
    intr_approval = _Interrupt(value=_approval_value(), id="int-dispatch-approval")
    intr_ask_user = _Interrupt(value=_ask_user_value(), id="int-dispatch-auq")

    # approval（first_seen）：prepare 成功 → built + enrich 落库字段（ticketSn 经现构造）
    result = processor.dispatch_interrupts([_Task("node_a", "task_1", [intr_approval])], _ctx())
    assert isinstance(result, DispatchResult)
    approval_outcome = result.interrupts[0]
    assert approval_outcome.status == "built"
    assert approval_outcome.intr is intr_approval
    assert isinstance(approval_outcome.builtin_property, dict)
    assert len(rm.create_calls) == 1, "approval 建单恰一次（ItsmTicketCreator 由 handler 自持）"

    # ask_user（first_seen，无建单副作用）：原样放行标 built
    result_auq = processor.dispatch_interrupts([_Task("node_b", "task_2", [intr_ask_user])], _ctx())
    assert len(result_auq.interrupts) == 1
    assert result_auq.interrupts[0].status == "built"
    assert result_auq.interrupts[0].intr is intr_ask_user
    assert len(rm.create_calls) == 1, "ask_user prepare 无建单副作用（不新增 create_calls）"


def test_dispatch_interrupts_unknown_reason_original_forward_built():
    """D-01 不吞中断：未注册 reason 的 interrupt → 无 handler → 原样放行标 built。"""
    processor = InterruptProcessor()  # 空 handlers dict
    intr = _Interrupt(value={"message": "未知中断类型"}, id="int-unknown")
    result = processor.dispatch_interrupts([_Task("node_x", "task_x", [intr])], _ctx())
    assert len(result.interrupts) == 1
    assert result.interrupts[0].status == "built", "未知 reason 原样放行 built（不抛 AttributeError、不吞中断）"
    assert result.interrupts[0].intr is intr


def test_dispatch_interrupts_prepare_failed_status():
    """prepare 异常兜底 → 逐项标 prepare_failed，intr 原样放行（D-01 不吞中断）。"""

    class _RaisingPrepareHandler:
        reason = TOOL_APPROVAL_REASON

        def prepare(self, interrupt, ticket_creator=None, **ctx):
            raise RuntimeError("boom")

        def extract_builtin_property(self, interrupt_id, interrupt, **kwargs):
            return {}

    processor = InterruptProcessor(handlers={str(TOOL_APPROVAL_REASON.value): _RaisingPrepareHandler()})
    intr = _Interrupt(value=_approval_value(), id="int-dispatch-fail")
    result = processor.dispatch_interrupts([_Task("node_a", "task_1", [intr])], _ctx())

    assert len(result.interrupts) == 1
    assert result.interrupts[0].status == "prepare_failed"
    assert result.interrupts[0].intr is intr, "prepare 异常不吞中断（intr 原样放行）"


def test_dispatch_interrupts_first_seen_builds_multiple_interrupts():
    """D-11 first_seen 实义（Gap 3）：同 task 双活跃中断——首个建单，第二个跳过 prepare 仍放行 built。"""
    rm = _StubResourceManager(
        create_result={"ticket": {"sn": "TICKET-FS", "status": "pending"}, "callback_token": "cb_fs"}
    )
    processor = InterruptProcessor(
        handlers={
            str(TOOL_APPROVAL_REASON.value): ApprovalHandler(
                resource_manager=rm,
                ticket_creator=ItsmTicketCreator(rm, username="alice", session_code="s1"),
            )
        }
    )
    first = _Interrupt(value=_approval_value(), id="int-fs-first")
    second = _Interrupt(value=_approval_value(toolCallId="call_2"), id="int-fs-second")
    result = processor.dispatch_interrupts([_Task("node_a", "task_1", [first, second])], _ctx())
    assert len(result.interrupts) == 2
    assert {o.status for o in result.interrupts} == {"built"}, "双活跃中断均放行 built（第二个跳过 prepare 仍放行）"
    assert len(rm.create_calls) == 1, "仅首个活跃中断建单（D-11 一次一卡 dispatch 侧保障），工单不随 pending 数复利"


def test_dispatch_interrupts_first_seen_prepares_once_for_multi_pending():
    """D-11/Gap 3 回归：多 pending approval 一次 dispatch 轮恰好 1 次 prepare（建单）。

    修复前 first_seen 为 no-op → 每 pending 都 prepare → N 张 ITSM 工单（基线 1 张）；
    叠加 not-ready 轮连终态重复 prepare 复利。恢复后非首个活跃中断跳过 prepare 原样放行。
    """
    prepared = {"count": 0}

    class _CountingApprovalHandler(ApprovalHandler):
        # 覆写 prepare 仅计数并原样返回 interrupt（不触发真实 ITSM 建单——
        # 建单需 ItsmTicketCreator，这里只关心「prepare 被调用次数」即建单副作用次数）。
        def prepare(self, interrupt, ticket_creator=None, **ctx):
            prepared["count"] += 1
            return interrupt

    processor = InterruptProcessor(handlers={str(TOOL_APPROVAL_REASON.value): _CountingApprovalHandler()})
    intr_a = _Interrupt(value=_approval_value(toolCallId="call-1"), id="int-a")
    intr_b = _Interrupt(value=_approval_value(toolCallId="call-2"), id="int-b")
    tasks = [_Task("tools", "task-1", [intr_a]), _Task("tools", "task-2", [intr_b])]

    result = processor.dispatch_interrupts(tasks, _ctx())

    assert prepared["count"] == 1, "一次 dispatch 轮仅首个活跃中断建单（D-11 一次一卡）"
    built = [o for o in result.interrupts if o.status == "built"]
    assert len(built) == 2, "两个 pending 均放行 built（原样放行不吞中断）"
    assert built[0].intr.id == "int-a", "首个活跃中断建单并提取 builtin_property"


def test_get_resume_input_not_ready_terminal_first_prepare_lands_on_pending():
    """Gap 3 残留回归：terminal-first 顺序下 prepare 落到首个活跃 pending（非已答卡）。

    串行多审批路径 [approval-1-已答, approval-2-pending]（tasks 顺序 terminal-first）：
    not-ready 轮内部 dispatch 必须让已答卡不消耗 first_seen 名额，建单落到 approval-2。
    修复前 prepare 落到已答卡（重复 ITSM 单），pending 零 prepare → not-ready SSE 缺
    ticket → 用户无法审批 → 串行多审批死锁。
    """
    prepared = {"ids": []}

    class _CountingApprovalHandler(ApprovalHandler):
        def prepare(self, interrupt, ticket_creator=None, **ctx):
            prepared["ids"].append(getattr(interrupt, "id", None))
            return interrupt

    processor = InterruptProcessor(handlers={str(TOOL_APPROVAL_REASON.value): _CountingApprovalHandler()})
    answered = _Interrupt(value=_approval_value(toolCallId="call-term"), id="int-terminal")
    pending = _Interrupt(value=_approval_value(toolCallId="call-pend"), id="int-pending")
    tasks = [_Task("tools", "task-term", [answered]), _Task("tools", "task-pend", [pending])]
    # chat_history 仅标记 approval-1（int-terminal）为已终态（resolved）→ terminal_ids={int-terminal}；
    # approval-2（int-pending）不在终态集 → next_interrupt=approval-2 → not-ready 内部 dispatch。
    chat_history = [
        SimpleNamespace(
            role=PromptRole.INTERRUPT.value,
            content={
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [
                        {"id": "int-terminal", "reason": TOOL_APPROVAL_REASON, "metadata": {"status": "resolved"}},
                    ],
                }
            },
        )
    ]

    result = processor.get_resume_input(
        tasks=tasks,
        session_code="s1",
        thread_id="t1",
        chat_history=chat_history,
    )

    assert result.ready is False, "approval-2 pending → not-ready（图保持暂停，先下发其卡片）"
    assert result.next_interrupt is pending, "next_interrupt 应为首个未终态 pending（approval-2）"
    # 一次 dispatch 轮仅 1 次 prepare，且落到首个**活跃** pending（int-pending），
    # 不是已答卡（int-terminal）——terminal-first 顺序不消耗 first_seen 名额
    assert prepared["ids"] == ["int-pending"], "prepare 必须落到首个活跃 pending（已答卡不得抢占建单名额）"


# ---------------------------------------------------------------------- #
# resolve_resumes：无返回值（D-16）——按 interruptId 路由到 handler.on_resume
# ---------------------------------------------------------------------- #


def test_resolve_resumes_returns_none_and_routes_by_reason():
    """D-16/D-04：resolve_resumes 无返回值，按 interruptId → chat_history 消息内 reason 路由。

    用 handlers dict 注入的桩 handler 捕获 on_resume 调用，断言按 chat_history
    末尾 INTERRUPT 记录内的 reason 路由到对应 handler（不信任前端 reason）。
    """
    captured: dict[str, list] = {"on_resume": []}

    class _ApprovalHandler:
        reason = TOOL_APPROVAL_REASON

        def on_resume(self, resume, *, interrupt_messages, **ctx):
            captured["on_resume"].append(("approval", resume, interrupt_messages))

    class _AskUserHandler:
        reason = ASK_USER_QUESTION_REASON

        def on_resume(self, resume, *, interrupt_messages, **ctx):
            captured["on_resume"].append(("ask_user", resume, interrupt_messages))

    processor = InterruptProcessor(
        handlers={
            str(TOOL_APPROVAL_REASON.value): _ApprovalHandler(),
            str(ASK_USER_QUESTION_REASON.value): _AskUserHandler(),
        }
    )
    chat_history = [
        SimpleNamespace(
            id="rec-1",
            role=PromptRole.INTERRUPT.value,
            content={
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [
                        {"id": "int-approval", "reason": TOOL_APPROVAL_REASON, "toolCallId": "call_1"},
                    ],
                }
            },
        )
    ]
    resume = [{"interruptId": "int-approval", "status": "resolved", "payload": {"approved": True}}]

    returned = processor.resolve_resumes(
        resume, ProcessorContext(session_code="s1", thread_id="t1", chat_history=chat_history)
    )

    assert returned is None, "resolve_resumes 无返回值（D-16，事件派发内聚到 handler）"
    assert len(captured["on_resume"]) == 1
    kind, r, msgs = captured["on_resume"][0]
    assert kind == "approval", "按 chat_history 消息内 reason 路由到 approval handler（不信任前端 reason）"
    assert msgs[0]["toolCallId"] == "call_1"
    assert r is resume[0]


def test_resolve_resumes_unmatched_interrupt_id_skips():
    """D-04：resume item interruptId 未命中 chat_history 末尾 interrupt_messages → 跳过（不抛）。"""
    captured: dict[str, int] = {"calls": 0}

    class _ApprovalHandler:
        reason = TOOL_APPROVAL_REASON

        def on_resume(self, resume, *, interrupt_messages, **ctx):
            captured["calls"] += 1

    processor = InterruptProcessor(handlers={str(TOOL_APPROVAL_REASON.value): _ApprovalHandler()})
    # chat_history 无 INTERRUPT 记录（空）→ 无法路由
    processor.resolve_resumes(
        [{"interruptId": "int-missing", "status": "resolved", "payload": {"approved": True}}],
        ProcessorContext(session_code="s1", thread_id="t1", chat_history=[]),
    )
    assert captured["calls"] == 0, "未命中路由的 resume item 被跳过（不抛异常，D-04）"


# ---------------------------------------------------------------------- #
# get_resume_input：串行推进（D-12 终态判定）→ Command / next_interrupt
# ---------------------------------------------------------------------- #


def _terminal_chat_history(real_ids: list[str]) -> list:
    """构造已终态 interrupt 的 chat_history（get_resume_input 串行完成判定源）。

    ``get_resume_input`` 经 ``terminal_interrupt_ids_from_messages(chat_history)``
    判全完成（D-12）。outcome.type=success，interrupts 元素 id 用真实 LangGraph
    中断 id，使全 pending 均判为已终态 → 走全就绪分支（构造 Command + 回放三字段）。
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


def _pending_chat_history(real_ids: list[str]) -> list:
    """构造 pending 的 chat_history（全 pending 均判为未终态 → 走未完成分支）。"""
    return [
        SimpleNamespace(
            role=PromptRole.INTERRUPT.value,
            content={
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [{"id": str(i), "metadata": {"status": "pending"}} for i in real_ids],
                }
            },
        )
    ]


def test_get_resume_input_not_ready_returns_next_interrupt():
    """D-10/D-12：未完成 → get_resume_input 返回 ready=False + next_interrupt（不产出 Command）。

    串行语义：未完成 pending 保持挂起，图不 resume，返回首个未完成中断供装配层
    下发下一张卡。pending chat_history（未终态）→ 走未完成分支。
    """
    processor = InterruptProcessor()
    pending = _Interrupt(value=_approval_value(), id="int-pending")
    tasks = [_Task("node_a", "task_1", [pending])]

    result = processor.get_resume_input(
        tasks=tasks,
        session_code="s1",
        thread_id="t1",
        chat_history=_pending_chat_history(["int-pending"]),
    )

    assert result.ready is False, "未完成 → ready=False（图保持暂停）"
    assert result.next_interrupt is pending, "未完成 → 返回首个未完成 pending 作为 next_interrupt"
    assert result.command is None, "未完成不产出 Command(resume)"


def test_get_resume_input_all_ready_returns_resume_command():
    """U-03/D-06：全就绪 → get_resume_input 返回 ready=True + command: Command。

    全 pending 终态（terminal chat_history）→ DB 权威 hydrate → 构造
    ``Command(resume=...)`` + 回放三字段（approve_result / approval_interrupts /
    ask_user_question_interrupts）。
    """
    from langgraph.types import Command

    processor = InterruptProcessor(
        handlers={
            str(TOOL_APPROVAL_REASON.value): ApprovalHandler(
                resource_manager=_ApprovedRm(),
                ticket_creator=ItsmTicketCreator(_ApprovedRm(), username="alice", session_code="s1"),
            )
        }
    )
    answered = _Interrupt(value=_approval_value(), id="int-1")
    tasks = [_Task("tools", "task_1", [answered])]

    result = processor.get_resume_input(
        tasks=tasks,
        session_code="s1",
        thread_id="t1",
        chat_history=_terminal_chat_history(["int-1"]),
    )

    assert result.ready is True, "全就绪 → ready=True"
    assert isinstance(result.command, Command), "ready 时应携带 Command"
    assert result.next_interrupt is None, "全就绪不应构造下一个 interrupt"


def test_get_resume_input_ask_user_all_ready_returns_answers_command():
    """Gap 1 回归：ask_user 自持 RM，全就绪续流 Command.resume 携带 DB 权威 answers（非空）。

    复现纯 ask_user 场景：ask_user pending + 终态 chat_history（answers 落库）。
    修复前 RM 缺失 → _get_client 抛 → 恒 not_ready → Command(resume=[])，答案丢失。
    注意：pending 走 value dict（target 形态无 id，仅 toolCallId），门禁经
    toolCallId 匹配 DB 记录（query_resume_status per-pending 定位）。
    """
    from langgraph.types import Command

    rm = _AskUserAnsweredRm()  # get_chat_session_contents 返回 ask_user 已答终态记录
    processor = InterruptProcessor(
        handlers={
            str(ASK_USER_QUESTION_REASON.value): AskUserQuestionHandler(
                dispatch_skip=lambda r: None,
                dispatch_answer=lambda r: None,
                resource_manager=rm,  # Gap 1：注入 RM → query_resume_status 回落自持实例
            )
        }
    )
    answered = _Interrupt(value=_ask_user_value(toolCallId="call_auq"), id="int-ask-1")
    tasks = [_Task("tools", "task-ask-1", [answered])]

    result = processor.get_resume_input(
        tasks=tasks,
        session_code="s1",
        thread_id="t1",
        chat_history=_terminal_chat_history(["int-ask-1"]),
    )

    assert result.ready is True
    assert isinstance(result.command, Command)
    # Command.resume 必须非空——DB 权威 answers 已进入 resume 值
    resume = result.command.resume
    assert resume, "Gap 1：ask_user 全就绪 Command.resume 不得为空（用户答案不得静默丢失）"


class _ApprovedRm:
    """鸭子 resource_manager：DB 审批记录全部 approved（get_resume_input 全就绪 hydrate 源）。"""

    def get_chat_session_contents(self, session_code: str) -> list[dict]:
        return [
            {
                "role": PromptRole.INTERRUPT.value,
                "content": {
                    "outcome": {
                        "type": "success",
                        "interrupts": [{"id": "int-1", "reason": TOOL_APPROVAL_REASON, "toolCallId": "call_1"}],
                    }
                },
            }
        ]


class _AskUserAnsweredRm:
    """鸭子 RM：ask_user 已答终态记录（result.payload.answers 落库权威，Gap 1 门禁源）。

    记录元素必须带 ``toolCallId: "call_auq"``（与 pending value 的 toolCallId 匹配；
    ask_user target 值无 id，门禁经 toolCallId per-pending 定位）。
    """

    def get_chat_session_contents(self, session_code: str) -> list[dict]:
        return [
            {
                "role": PromptRole.INTERRUPT.value,
                "content": {
                    "outcome": {
                        "type": "success",
                        "interrupts": [
                            {"id": "int-ask-1", "reason": ASK_USER_QUESTION_REASON, "toolCallId": "call_auq"}
                        ],
                    },
                    "result": {
                        "id": "int-ask-1",
                        "interruptId": "int-ask-1",
                        "status": "resolved",
                        "payload": {"answers": [{"value": "是", "question": "继续吗?"}]},
                    },
                },
            }
        ]


# ---------------------------------------------------------------------- #
# Do-Not-Break：_build_resume_map / _filter_claimed_items / _unified_resume_values
# ---------------------------------------------------------------------- #


def test_build_resume_map_matches_by_interrupt_id_across_task_order():
    """UAT 死循环根因回归：resume item 按 interruptId 精确匹配到正确的 task。

    resume-map key = xxh3_128_hexdigest(f"{task.name}:{task.id}")（Do-Not-Break）。
    历史缺陷：item 侧索引键（interruptId=LangGraph 中断 id）与 task 侧匹配键
    （value.toolCallId）命名空间错位恒不匹配，退化顺序兜底派错 task。
    """
    from xxhash import xxh3_128_hexdigest

    processor = InterruptProcessor()
    answered = _Interrupt(
        value={"interrupt_reason": "aidev:user_question", "toolCallId": "call-q1", "questions": []},
        id="ce91e598cc3909d7194475c09cc40b7f",
    )
    waiting = _Interrupt(
        value={"interrupt_reason": "aidev:user_question", "toolCallId": "call-q2", "questions": []},
        id="aa11bb22cc33dd44ee55ff6677889900",
    )
    # state.tasks 顺序与回答顺序相反（问题二在前）——旧顺序兜底必派错
    task_waiting_first = _Task("tools", "task-q2", [waiting])
    task_answered = _Task("tools", "task-q1", [answered])
    tasks = [task_waiting_first, task_answered]
    resume_items = [
        {"interruptId": "ce91e598cc3909d7194475c09cc40b7f", "status": "resolved", "payload": {"answers": []}}
    ]

    resume_map = processor._build_resume_map(processor._pending_tasks(tasks), resume_items)

    key_answered = xxh3_128_hexdigest("tools:task-q1".encode())
    key_waiting = xxh3_128_hexdigest("tools:task-q2".encode())
    assert resume_map.get(key_answered) is resume_items[0], (
        "resume item 必须按 interruptId 命中问题一的 task（intr.id ↔ item.interruptId 同源）"
    )
    assert key_waiting not in resume_map, "问题二未被回答，保持挂起（D-10 不写入 resume-map）"


def test_build_resume_map_tool_call_id_still_matches():
    """toolCallId 匹配保留：无 interruptId 的 item 仍可按 value.toolCallId 命中。"""
    from xxhash import xxh3_128_hexdigest

    processor = InterruptProcessor()
    intr = _Interrupt(value=_approval_value(toolCallId="call-x"), id="int-approval-x")
    task = _Task("tools", "task-x", [intr])
    resume_items = [{"toolCallId": "call-x", "status": "resolved", "payload": {"approved": True}}]

    resume_map = processor._build_resume_map([task], resume_items)

    key = xxh3_128_hexdigest("tools:task-x".encode())
    assert resume_map.get(key) is resume_items[0], "toolCallId 命名空间内匹配应继续工作"


def test_filter_claimed_items_drops_forged_id():
    """T-44-01（Do-Not-Break）：携带身份 id 但不命中任何 pending → 丢弃（防伪造 id 冒领）。

    ``_filter_claimed_items`` 对裸列表 resume items 做身份校验——带 interruptId /
    toolCallId 但不命中任何 pending 的 item 被丢弃；无 id 旧形态原样放行（位置语义）。
    """
    processor = InterruptProcessor()
    intr = _Interrupt(value=_approval_value(toolCallId="call-real"), id="int-real")
    task = _Task("tools", "task-x", [intr])

    # 伪造 id 冒领：不命中任何 pending → 丢弃
    forged = [{"interruptId": "int-forged", "status": "resolved", "payload": {"approved": True}}]
    kept = processor._filter_claimed_items([task], forged)
    assert kept == [], "伪造 id 的 resume item 必须被丢弃（防冒领）"

    # 命中真实 pending → 保留
    real = [{"interruptId": "int-real", "status": "resolved", "payload": {"approved": True}}]
    kept_real = processor._filter_claimed_items([task], real)
    assert len(kept_real) == 1, "命中真实 pending 的 item 保留"

    # 无 id 旧形态 → 位置语义放行
    legacy = [{"status": "resolved", "payload": {"approved": True}}]
    kept_legacy = processor._filter_claimed_items([task], legacy)
    assert len(kept_legacy) == 1, "无 id 旧形态按位置语义放行"


def test_unified_resume_values_hydrates_each_element_own_verdict():
    """UAT 回归（混合终态连坐 bug）：一批准一拒绝——approved 元素不得被覆写成拒绝。

    ``_unified_resume_values`` 按各单元自身 DB 终态逐元素 hydrate（approved 元素
    payload.approved=True 保持，rejected 元素 False）——统一覆写 REJECTED 会经
    hydrate_resume_payload 无条件覆写连坐已批准元素。
    """
    from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor as P

    processor = P()
    unit_results = [
        {"action": "approved", "resume_value": [{"id": "i1", "reason": TOOL_APPROVAL_REASON, "toolCallId": "call_1"}]},
        {"action": "rejected", "resume_value": [{"id": "i2", "reason": TOOL_APPROVAL_REASON, "toolCallId": "call_sz"}]},
    ]
    values = processor._unified_resume_values(unit_results, None)

    by_id = {v["id"]: v for v in values}
    assert by_id["i1"]["payload"]["approved"] is True, (
        "已批元素 payload.approved 必须保持 True（不被 rejected 连坐覆写）"
    )
    assert by_id["i2"]["payload"]["approved"] is False, "已拒元素 payload.approved=False"


def test_build_command_resume_single_bare_list():
    """单中断 → build_command_resume 返回裸列表 Command（兼容 chat.py 现例）。"""
    from langgraph.types import Command

    processor = InterruptProcessor()
    intr = _Interrupt(value=_approval_value(), id="int-1")
    tasks = [_Task("tools", "task_1", [intr])]
    command = processor.build_command_resume(tasks, [{"approved": True, "toolCallId": "call_1"}])
    assert isinstance(command, Command)
    assert isinstance(command.resume, list), "单中断应为裸列表"


def test_build_command_resume_multi_resume_map_key_xxh3():
    """多中断 → build_command_resume 构造 resume-map（key = xxh3(task.name:task.id)）。"""
    from langgraph.types import Command
    from xxhash import xxh3_128_hexdigest

    processor = InterruptProcessor()
    a = _Interrupt(value=_approval_value(toolCallId="call_1"), id="int-a")
    b = _Interrupt(value=_approval_value(toolCallId="call_2"), id="int-b")
    tasks = [_Task("tools", "task_a", [a]), _Task("tools", "task_b", [b])]
    command = processor.build_command_resume(
        tasks, [{"approved": True, "toolCallId": "call_1"}, {"approved": True, "toolCallId": "call_2"}]
    )
    assert isinstance(command, Command)
    assert isinstance(command.resume, dict), "多中断应为 resume-map"
    key_a = xxh3_128_hexdigest("tools:task_a".encode())
    key_b = xxh3_128_hexdigest("tools:task_b".encode())
    assert key_a in command.resume, "task_a（call_1）应被身份匹配认领"
    assert key_b in command.resume, "task_b（call_2）应被身份匹配认领"
    assert command.resume[key_a]["toolCallId"] == "call_1"
    assert command.resume[key_b]["toolCallId"] == "call_2"


# ---------------------------------------------------------------------- #
# 对偶单元门禁：query_resume_status（per-pending 定位，DB 权威）
# ---------------------------------------------------------------------- #


class _StubApprovalStateHandler:
    """ApprovalHandler.query_resume_status 门禁桩：按记录列表模拟 DB interrupt 记录。"""

    def __init__(self, records: list[dict]):
        self.records = records

    def query_approval_info_for_interrupt(self, session_code: str, pending_interrupt):
        tcid = pending_interrupt.get("toolCallId")
        for record in reversed(self.records):
            if record.get("tool_call_id") == tcid:
                result = record.get("approve_result")
                if result not in {"approved", "rejected", "cancelled"}:
                    return None
                return {"approve_result": result, "interrupts": record.get("interrupts") or [], "id": record.get("id")}
        return None


def _approval_pending_value(tool_call_id: str) -> dict:
    return {
        "reason": TOOL_APPROVAL_REASON,
        "toolCallId": tool_call_id,
        "message": "需要人工审批",
        "metadata": {"type": "tool_approval", "status": "pending"},
    }


def test_on_resume_gate_checks_current_pending_record_not_latest():
    """UAT 回归（每次 resume 都拉起图）：门禁按当前 pending 的 toolCallId 定位专属记录。

    场景：前序审批已 approved（恰为最新一条记录）+ 当前审批 pending 未回调。
    旧「最新一条记录」语义误放行 approved → 图每次被拉起；新语义按 pending
    专属记录判定 → not_ready → 图保持暂停。
    """
    records = [
        {"tool_call_id": "call_old", "approve_result": "approved", "interrupts": [], "id": 1},  # 前序已批
        {"tool_call_id": "call_cur", "approve_result": None, "interrupts": [], "id": 2},  # 当前 pending
    ]
    handler = ApprovalHandler()
    handler._state_handler = _StubApprovalStateHandler(records)
    pending = _approval_pending_value("call_cur")

    result = handler.query_resume_status("s1", pending)

    assert result.get("action") == "not_ready", (
        "当前审批未回调 → 门禁必须 not_ready（旧最新记录语义误读前序 approved 放行，图被反复拉起）"
    )


def test_on_resume_gate_passes_when_current_pending_record_terminal():
    """当前 pending 专属记录已回调 approved → 门禁放行（resume_value 为该记录 interrupts）。"""
    records = [
        {"tool_call_id": "call_old", "approve_result": "rejected", "interrupts": [], "id": 1},
        {"tool_call_id": "call_cur", "approve_result": "approved", "interrupts": [{"id": "int-cur"}], "id": 2},
    ]
    handler = ApprovalHandler()
    handler._state_handler = _StubApprovalStateHandler(records)
    pending = _approval_pending_value("call_cur")

    result = handler.query_resume_status("s1", pending)

    assert result.get("action") == "approved"
    assert result.get("resume_value") == [{"id": "int-cur"}]


# ---------------------------------------------------------------------- #
# AskUserQuestionHandler.on_resume 三态分流（skip / answer）
# ---------------------------------------------------------------------- #


def _chat_interrupt(resume_id="int-q", questions=None, tool_call_id="tc-q"):
    """构造一条 role=interrupt 的 chat_history 记录（ChatPrompt 鸭子类型）。"""
    return SimpleNamespace(
        id=resume_id,
        role=PromptRole.INTERRUPT.value,
        content={
            "outcome": {
                "type": "interrupt",
                "interrupts": [
                    {
                        "id": resume_id,
                        "reason": ASK_USER_QUESTION_REASON,
                        "toolCallId": tool_call_id,
                        "metadata": {
                            "type": "ask_user_question",
                            "status": "pending",
                            "questions": questions or [{"question": "确认？", "multiSelect": False}],
                        },
                    }
                ],
            }
        },
        builtin_property={"tool_call_id": tool_call_id, "questions": questions or [{"question": "确认？"}]},
    )


def _ask_user_resume(resume_id="int-q", answers=None):
    """构造前端 ask_user resume（list[dict] 形态，含 payload.answers）。"""
    return [{"interruptId": resume_id, "status": "resolved", "payload": {"answers": answers or []}}]


def test_ask_user_on_resume_skip_path():
    """D-13：input 或空 answers → on_resume skip 路径（改写 interrupt 为 CANCELLED）。"""
    dispatched = []
    handler = AskUserQuestionHandler(dispatch_skip=lambda result: dispatched.append(result))
    interrupt = _chat_interrupt()
    handler.on_resume(
        _ask_user_resume(answers=[]),
        interrupt_messages=[{"id": "int-q", "reason": ASK_USER_QUESTION_REASON}],
        chat_history=[interrupt],
        turn_id="turn-1",
        input_text="用户直接输入新消息",
    )
    assert len(dispatched) == 1, "skip 经注入 dispatch_skip 派发事件（D-16 内聚到 on_resume）"
    assert dispatched[0]["action"] == "skip", "input 存在 → skip 路径"
    assert dispatched[0]["status"] == "cancelled", "skip 将 interrupt 改写为 CANCELLED"
    upgraded = interrupt.content["outcome"]
    assert upgraded["type"] == "success"
    assert upgraded["interrupts"][0]["metadata"]["status"] == "cancelled"


def test_ask_user_on_resume_answer_path():
    """D-13：非空 answers → on_resume answer 路径（改写 interrupt 为 RESOLVED）。"""
    dispatched = []
    handler = AskUserQuestionHandler(dispatch_answer=lambda result: dispatched.append(result))
    interrupt = _chat_interrupt()
    answers = [{"question": "确认？", "answer": [{"label": "是"}]}]
    handler.on_resume(
        _ask_user_resume(answers=answers),
        interrupt_messages=[{"id": "int-q", "reason": ASK_USER_QUESTION_REASON}],
        chat_history=[interrupt],
        turn_id="turn-1",
        input_text="",
    )
    assert len(dispatched) == 1, "answer 经注入 dispatch_answer 派发事件（D-16）"
    assert dispatched[0]["action"] == "answer", "非空 answers → answer 路径"
    assert dispatched[0]["status"] == "resolved", "answer 将 interrupt 改写为 RESOLVED"
    assert dispatched[0]["answers"] == answers, "answer 路径携带用户答案"


def test_ask_user_on_resume_non_ask_user_is_noop():
    """非 ask_user resume → on_resume 直接返回（不吞并，交其他 handler）。"""
    handler = AskUserQuestionHandler(dispatch_skip=lambda r: None, dispatch_answer=lambda r: None)
    interrupt = _chat_interrupt()
    handler.on_resume(
        [{"interruptId": "x", "status": "resolved", "payload": {"approved": True}}],
        interrupt_messages=[{"id": "x", "reason": TOOL_APPROVAL_REASON}],
        chat_history=[interrupt],
        turn_id="turn-1",
        input_text="",
    )
    # 无 dispatch 派发（非 ask_user resume 不触发 skip/answer），interrupt 未被改写
    assert interrupt.content["outcome"]["type"] == "interrupt", "非 ask_user resume 不改写 interrupt"
