# -*- coding: utf-8 -*-
"""interrupt_manager 的统一中断编排：``InterruptProcessor``（44 D-02，48 v3 语义重写）。

本模块合并流结束侧（原 ``InterruptDispatcher.process``）与 resume 侧（原
``ResumeCoordinator`` 四方法）为统一编排类。per-reason 对偶单元经构造注入的
``handlers={reason: handler}`` dict 显式持有（D-03），**不再经 registry 查表**
（D-01：注册表机制删除）。

设计要点（48 v3 语义，修正 Phase 47 过度架构化）：

- **显式 handler dict 注入（D-03/U-01）**：构造参数 ``handlers: dict[str, Any]``，
  移除 ``resource_manager`` / ``ticket_creator`` 构造参数（建单依赖由 handler
  自持或经 ctx 提供）。新增中断类型零改签名（dict 键即 reason）。
- **双接口语义（D-02/D-03）**：
  - :meth:`resolve_resumes` —— **无返回值**（on_resume 语义，D-16）：逐 resume
    经 ``interruptId → chat_history interrupt_messages → 消息内 reason → handler``
    路由（D-04，不信任前端 reason），调 ``handler.on_resume``。事件派发内聚到
    on_resume（ask_user 经注入 bound method，approval 空实现）。
  - :meth:`get_resume_input` —— **串行推进**（U-03/D-06/D-07）：拉平 pending →
    按 chat_history interrupt_messages 终态判定（D-12）→ 全完成构造 Command +
    回放三字段（ready=True）；未完成取首个未完成 interrupt，内部执行 dispatch
    （建单 + enrich，D-07）返回 ready=False + next_interrupt。
- **dispatch_interrupts 瘦身（U-04/D-11）**：移除 ``terminal_ids`` / ``terminal_skipped``
  终态集合防线与「上一单终态判定」串行建单门禁（架构性死），保留 ``first_seen``
  一次一卡语义。``InterruptOutcome.status`` 字面量：``built`` / ``prepare_failed``。

**保留复用的原子能力（Do-Not-Break，逻辑逐行不动）**：
``build_command_resume`` / ``_build_resume_map`` / ``_pick_claimed_value`` /
``_filter_claimed_items`` / ``_unified_resume_values`` / ``_collect_interrupts`` /
``_get_interrupts_from_tasks`` / ``_reason_of``。

**Harness 红线**：本模块（packages 内）不 import core/services/api。
``handlers`` 注入的 handler 携带自身依赖（鸭子类型收敛）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from xxhash import xxh3_128_hexdigest

from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager.approval import (
    ApprovalStateHandler,
    ApproveResult,
    InvalidApprovalInterruptError,
)
from aidev_agent.packages.interrupt_manager.ask_user_question import (
    filter_ask_user_question_interrupts,
)
from aidev_agent.packages.interrupt_manager.types import (
    DispatchResult,
    InterruptOutcome,
    ProcessorContext,
    ResumeInputResult,
)
from aidev_agent.packages.interrupt_manager.utils import (
    interrupt_id_of,
    terminal_interrupt_ids_from_messages,
)

logger = logging.getLogger(__name__)


class InterruptProcessor:
    """统一中断编排类（取代 ``InterruptDispatcher`` + ``ResumeCoordinator``，D-02）。

    48 v3 语义重写后：显式持有 ``handlers={reason: handler}`` dict（D-03），
    流结束侧 ``dispatch_interrupts`` 与 resume 侧 ``resolve_resumes`` /
    ``get_resume_input`` 双入口。per-reason 对偶单元经构造注入的 handlers dict
    直取，不依赖 registry 查表。

    Attributes:
        _handlers: reason 字符串 → InterruptHandler 实例的 dict（构造时
            ``dict(handlers)`` 防御性拷贝，杜绝外部可变 dict 引用污染）。
    """

    def __init__(self, handlers: dict[str, Any] | None = None) -> None:
        self._handlers = dict(handlers) if handlers else {}

    # ------------------------------------------------------------------ #
    # 流结束侧：dispatch_interrupts（D-09 零处理 + D-02 逐项状态标注 + U-04/D-11 瘦身）
    # ------------------------------------------------------------------ #

    def dispatch_interrupts(
        self, tasks: Any, ctx: ProcessorContext, *, terminal_ids: set[str] | None = None
    ) -> DispatchResult:
        """从 ``state.tasks`` 全量收集 pending interrupt 并执行 per-reason prepare。

        分发单位是**原始 interrupt 对象**（用户裁定，零处理）：收集阶段不做任何
        解析 / 包装 / 注入，per-reason prepare 就地 enrich ``intr.value``，返回
        :class:`DispatchResult`（逐项 ``InterruptOutcome``，含 intr 与状态标注）。

        U-04/D-11 瘦身：移除 ``terminal_ids`` 终态集合防线与「上一单终态判定」
        串行建单门禁（架构性死），保留 ``first_seen`` 一次一卡语义（单轮一次只建
        一张卡）。``handler = self._handlers.get(reason)`` 未命中 → 无 prepare →
        原样放行 built（对齐 D-01 不吞中断）。

        Gap 3 残留修复（processor 内部自推导）：``terminal_ids`` 是**内部** keyword
        参数（非 U-04 禁止的 caller-facing terminal_interrupt_ids）——由
        :meth:`get_resume_input` 从 chat_history 内部推导并线程进未完成分支的内部
        dispatch。terminal pending（interrupt id ∈ terminal_ids，已终态）**不消耗
        first_seen 建单名额**：跳过 prepare 原样放行 built（既避免重复建单，又避免
        terminal-first 顺序下已答卡抢占首个活跃 pending 的建单名额 → 后者无工单 →
        not-ready SSE 缺 ticket → 串行多审批死锁）。缺省 None → 空集合 → 全按非
        终态处理（agent.py prepare_stream 纯拉图路径尾部 pending 恒为本次新抛）。

        状态字面量（:class:`InterruptOutcome.status`）：``built``（prepare 成功 /
        handler 无 prepare 原样放行）、``prepare_failed``（prepare 异常兜底，intr
        原样放行不吞中断）。

        Args:
            tasks: graph ``state.tasks``（含各 pending interrupt 的 task 对象）。
            ctx: 显式运行时状态（:class:`ProcessorContext`，装配层现场拼装）。
            terminal_ids: 内部 keyword 参数（默认 None → 空集合）。已终态 interrupt
                id 集合；命中的 pending 跳过 prepare 原样放行，不消耗 first_seen 名额。

        Returns:
            :class:`DispatchResult`——逐项 ``InterruptOutcome``。未知 reason 或
            prepare 异常的 interrupt 不丢弃（D-01 精神）。
        """
        interrupts = self._collect_interrupts(tasks)
        # first_seen 表示「尚未处理到首个需建单的活跃中断」——首个需建单的中断
        # 流结束即活跃、无条件建单；U-04 后不再做上一单终态判定（D-11 删除该
        # 门禁），first_seen 语义简化为「首个活跃中断无条件建单」。
        result = DispatchResult()
        first_seen = True
        terminal_ids = terminal_ids or set()
        for intr in interrupts:
            value = getattr(intr, "value", intr)
            reason = (value.get("reason") or value.get("interrupt_reason")) if isinstance(value, dict) else None
            handler = self._handlers.get(reason)
            prepare = getattr(handler, "prepare", None) if handler is not None else None
            if prepare is None:
                # handler 不实现 prepare（或未注册该 reason）→ 原样放行
                result.interrupts.append(InterruptOutcome(intr=intr, reason=reason, status="built"))
                continue
            if terminal_ids:
                intr_id = interrupt_id_of(intr)
                if intr_id and str(intr_id) in terminal_ids:
                    # Gap 3 残留：terminal pending（已终态）不消耗 first_seen 名额——
                    # 跳过 prepare 原样放行 built（避免重复建单，且不让已答卡抢占
                    # 首个活跃 pending 的建单名额）。
                    result.interrupts.append(InterruptOutcome(intr=intr, reason=reason, status="built"))
                    continue
            if not first_seen:
                # D-11 first_seen 实义：单轮一次只建一张卡（一次一卡平台约束的 dispatch
                # 侧保障）。第二个及后续活跃中断跳过 prepare 建单副作用，仍原样放行 built
                # （装配层 [:1] trim 保住一卡 UX，此分支另拦 prepare 的 ITSM 建单副作用
                # ——工单不随 pending 数复利）。
                result.interrupts.append(InterruptOutcome(intr=intr, reason=reason, status="built"))
                continue
            first_seen = False
            try:
                prepare(intr, thread_id=ctx.thread_id, run_id=ctx.run_id)
                result.interrupts.append(
                    InterruptOutcome(
                        intr=intr,
                        reason=reason,
                        status="built",
                        builtin_property=self._extract_builtin_property(handler, intr, ctx),
                    )
                )
            except InvalidApprovalInterruptError:
                # 协议/程序错误（value 非 target 形态等）：fail fast 上抛——
                # 静默拦截或虚构建单是生产事故（用户裁定），绝不吞
                raise
            except Exception:
                # prepare 异常兜底：不吞中断（D-01 精神），intr 原样放行 + 记 error
                logger.exception(
                    "[InterruptProcessor] prepare 异常，interrupt 原样放行: reason=%s, id=%s",
                    reason,
                    getattr(intr, "id", None),
                )
                result.interrupts.append(InterruptOutcome(intr=intr, reason=reason, status="prepare_failed"))
        return result

    @staticmethod
    def _extract_builtin_property(handler: Any, intr: Any, ctx: ProcessorContext) -> dict[str, Any] | None:
        """从 prepare 后的 intr 提取落库 ``builtin_property`` 字段集（D-02）。

        优先走对偶单元 ``extract_builtin_property``（approval / ask_user 均实现，
        registry Protocol），提取失败则兜底取 ``intr.value.metadata``（approval enrich
        已落库字段）。纯辅助，不改变中断对象。
        """
        extract = getattr(handler, "extract_builtin_property", None)
        if extract is not None:
            try:
                builtin = extract(getattr(intr, "id", None), intr, graph_thread_id=ctx.thread_id)
                if isinstance(builtin, dict):
                    return builtin
            except Exception:
                logger.debug("[InterruptProcessor] extract_builtin_property 提取失败，兜底 metadata", exc_info=True)
        value = getattr(intr, "value", intr)
        metadata = value.get("metadata") if isinstance(value, dict) else None
        return metadata if isinstance(metadata, dict) else None

    @staticmethod
    def _collect_interrupts(tasks: Any) -> list[Any]:
        """从 ``state.tasks`` 全量收集 pending interrupt（**零处理**，用户裁定）。

        收集阶段对 ``task.interrupts[*]`` 不做任何处理：不 JSON parse、不 dict 包装、
        不注入 id、不建 ``{id, value}`` 包装结构——传入什么对象返回什么对象。
        id 与 value 彻底分离：id 只活在 intr 对象上（``intr.id``），value dict 内
        绝不出现 id 键。

        Returns:
            原始 intr 对象列表。tasks 为空时返回空列表。
        """
        interrupts: list[Any] = []
        if not tasks:
            return interrupts
        for task in tasks:
            interrupts.extend(getattr(task, "interrupts", None) or [])
        return interrupts

    # ------------------------------------------------------------------ #
    # resume 侧：resolve_resumes（无返回值，on_resume 语义）+ get_resume_input（串行）
    # ------------------------------------------------------------------ #

    def resolve_resumes(self, resumes: Any, ctx: ProcessorContext) -> None:
        """resume 前置编排统一入口（U-02/U-05/D-04/D-16，**无返回值**）。

        对每个 resume item 逐项路由到 handler 并调 ``handler.on_resume``：
        resume item 的 ``interruptId`` → chat_history 提取的 ``{interrupt_id:
        interrupt_messages}`` → 消息内 reason → ``self._handlers[reason]`` →
        ``handler.on_resume``（D-04，不信任前端 reason 字段）。事件派发内聚到
        on_resume（D-16）。

        Args:
            resumes: 前端续流 resume 值（不可信输入，T-48-01；dict 或 list[dict]）。
            ctx: 显式运行时状态（:class:`ProcessorContext`，含 chat_history /
                session_code / thread_id / turn_id / input_text）。
        """
        if isinstance(resumes, dict):
            resumes = [resumes]
        resume_list = list(resumes) if resumes else []
        chat_history = ctx.chat_history or []
        interrupt_messages = self._extract_trailing_interrupt_messages(chat_history)  # U-02b
        session_code = ctx.session_code or ctx.thread_id
        for resume_item in resume_list:
            item = resume_item if isinstance(resume_item, dict) else {}
            interrupt_id = item.get("interruptId") or item.get("interrupt_id") or item.get("id")
            msgs = interrupt_messages.get(str(interrupt_id)) if interrupt_id else None
            if msgs is None:
                # 未命中 chat_history interrupt_messages → 无法路由（D-04 不信任前端 reason），跳过
                logger.warning(
                    "[InterruptProcessor] resume item 未命中 chat_history interrupt 记录，跳过: id=%r",
                    interrupt_id,
                )
                continue
            reason = msgs[0].get("reason") or msgs[0].get("interrupt_reason") if isinstance(msgs[0], dict) else None
            handler = self._handlers.get(reason)
            if handler is None:
                logger.warning("[InterruptProcessor] 无 reason=%s 的 handler，跳过 on_resume", reason)
                continue
            on_resume = getattr(handler, "on_resume", None)
            if on_resume is not None:
                on_resume(
                    resume_item,
                    interrupt_messages=msgs,
                    chat_history=chat_history,
                    session_code=session_code,
                    thread_id=ctx.thread_id,
                    turn_id=ctx.turn_id or "",
                    input_text=ctx.input_text or "",
                )

    def get_resume_input(
        self,
        *,
        tasks: Any,
        session_code: str,
        thread_id: str,
        chat_history: list[Any] | None = None,
    ) -> ResumeInputResult:
        """串行推进到 Command（U-03/D-06/D-07）：拉平 pending → 判完成 → 构造/推进。

        - **全完成**（全 pending 的 ``interrupt_id_of`` 均 ∈
          ``terminal_interrupt_ids_from_messages(chat_history)``，D-12）→ 用
          ``_unified_resume_values``（DB 权威 hydrate）构造 resume_values →
          ``build_command_resume`` 构造 Command + 回放三字段（approve_result /
          approval_interrupts / ask_user_question_interrupts，D-06）→ ``ready=True``。
        - **未完成** → 取首个 ``interrupt_id_of`` 未 ∈ 终态集合的 pending 作为
          ``next_interrupt``，对首个未完成 pending 调 ``dispatch_interrupts`` 内部
          建单 + enrich（D-07，agent.py 只负责事件下发）→ ``ready=False``。

        Args:
            tasks: graph ``state.tasks``（含各 pending interrupt 的 task）。
            session_code: 会话 code（DB 权威记录查询用）。
            thread_id: 图线程 id。
            chat_history: chat 历史（ChatPrompt 鸭子对象列表，判完成用）。

        Returns:
            :class:`ResumeInputResult`（command + 回放三字段 + ready + next_interrupt）。
        """
        chat_history = chat_history or []
        terminal_ids = terminal_interrupt_ids_from_messages(chat_history)  # D-12 终态判定底层
        next_interrupt: Any | None = None
        all_complete = True
        for task in tasks or []:
            for intr in getattr(task, "interrupts", None) or []:
                intr_id = interrupt_id_of(intr)
                if intr_id is None:
                    # 无法定位 id 的 pending：保守视为未完成（无法判定已终态）
                    if next_interrupt is None:
                        next_interrupt = intr
                        all_complete = False
                    continue
                if str(intr_id) not in terminal_ids:
                    if next_interrupt is None:
                        next_interrupt = intr
                        all_complete = False
                    break
            if next_interrupt is not None:
                break

        if next_interrupt is None and all_complete:
            # 全完成：DB 权威 hydrate → Command + 回放三字段（D-06）
            unit_results = self._aggregate_resume_status(tasks, session_code, thread_id)
            resume_values = self._unified_resume_values(unit_results, None)
            command = self.build_command_resume(tasks, resume_values)
            # 回放 approve_result：取首个已终态 approval 单元的 DB 权威 action
            approve_result = next(
                (r.get("action") for r in unit_results if r.get("action") in ApproveResult.ALL),
                None,
            )
            approval_interrupts = [
                e
                for r in unit_results
                for e in (r.get("resume_value") if isinstance(r.get("resume_value"), list) else [])
                if isinstance(e, dict)
            ]
            ask_user_question_interrupts = filter_ask_user_question_interrupts(tasks)  # D-06 graph-tasks 源过滤
            return ResumeInputResult(
                ready=True,
                command=command,
                approve_result=approve_result,
                approval_interrupts=approval_interrupts,
                ask_user_question_interrupts=ask_user_question_interrupts,
            )

        # 未完成：内部 dispatch（建单 + enrich，D-07）后返回 ready=False + next_interrupt
        if next_interrupt is not None:
            ctx = ProcessorContext(
                session_code=session_code,
                thread_id=thread_id,
                chat_history=chat_history,
            )
            # Gap 3 残留：线程已由本方法从 chat_history 内部推导的 terminal_ids，使
            # dispatch_interrupts 的 first_seen 名额只被非终态活跃 pending 消耗
            # （terminal-first 顺序下已答卡不得抢占首个活跃 pending 的建单名额）。
            self.dispatch_interrupts(tasks, ctx, terminal_ids=terminal_ids)
        return ResumeInputResult(ready=False, next_interrupt=next_interrupt)

    @staticmethod
    def _extract_trailing_interrupt_messages(chat_history: list[Any]) -> dict[str, list]:
        """U-02b：从 chat_history 末尾起反向收集**连续** role=INTERRUPT 的 ChatPrompt
        鸭子对象，转为 ``{interrupt_id: [msg_content_dicts]}``。

        chat_history 元素为 services 层 ChatPrompt 鸭子对象（具 ``role`` /
        ``content`` / ``builtin_property`` / ``id``，getattr 访问）。从末尾反向收集
        连续 ``role == INTERRUPT`` 的元素，对每个元素的 ``content``
        （``{"outcome": {"type": ..., "interrupts": [...]}}``）遍历 interrupts
        元素（dict，含 ``id`` / ``reason``），按 ``id`` 分组收集。
        迭代 / 取中断元素手法参考 ``terminal_interrupt_ids_from_messages``
        （utils.py:121-154）对 ``msg.content.outcome.interrupts`` 的遍历。

        Returns:
            ``{interrupt_id: [interrupt 元素 dict, ...]}``。
        """
        result: dict[str, list] = {}
        trailing: list[Any] = []
        for msg in reversed(chat_history):
            role = getattr(msg, "role", None)
            if role != PromptRole.INTERRUPT.value:
                break
            trailing.append(msg)
        trailing.reverse()
        for msg in trailing:
            content = getattr(msg, "content", None)
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (TypeError, ValueError):
                    continue
            if not isinstance(content, dict):
                continue
            outcome = content.get("outcome")
            if not isinstance(outcome, dict):
                continue
            interrupts = outcome.get("interrupts")
            if not isinstance(interrupts, list):
                continue
            for intr in interrupts:
                if not isinstance(intr, dict):
                    continue
                intr_id = intr.get("id")
                if intr_id:
                    result.setdefault(str(intr_id), []).append(intr)
        return result

    def _unified_resume_values(self, unit_results: list[dict[str, Any]], resume: Any) -> list[Any]:
        """为**全部** pending interrupt 统一构造 resume 值（一个 Command 承载所有中断）。

        - approval pending：取各自 DB 权威元素（``unit_results.resume_value``），
          按元素**自身** ``metadata.status`` 逐元素 hydrate（approved→payload.approved
          =True；cancelled/rejected→False）——混合终态各自正确，且前端伪造的
          approval 项被 DB 元素整体取代（CR-01 强化）；
        - ask_user pending（GATE-03）：取 gate 产出的 DB 权威元素
          （``{interruptId, status, payload:{answers}}``，重建自已答记录的
          ``result.payload.answers``）。前端 items 透传的 answers 项**整体弃用**
          （T-46-01：防伪造答案透传，弃前端 answers）。
        """
        values: list[Any] = []
        for unit_result in unit_results:
            rv = unit_result.get("resume_value")
            if not rv:
                continue
            action = unit_result.get("action")
            elements = rv if isinstance(rv, list) else [rv]
            for element in elements:
                if not isinstance(element, dict):
                    continue
                # 按该 pending 的 DB 权威终态（unit action = 记录 approve_result）
                # 逐元素 hydrate——混合终态各自正确；前端伪造的 approval 项被
                # DB 元素整体取代（CR-01 强化）。ask_user 的 action == "resolved"
                # 不在 ApproveResult.ALL → 天然不走 hydrate_resume_payload
                # （answers 不被注入 approved）。
                if action in ApproveResult.ALL:
                    ApprovalStateHandler.hydrate_resume_payload([element], action)
                values.append(element)
        items = resume if isinstance(resume, list) else ([resume] if resume else [])
        has_db_elements = bool(values)
        # GATE-03：存在 DB 权威元素时，**所有**前端 item 整体弃用——approval 前端项
        # （CR-01）与 ask_user 前端 answers 项（T-46-01）同处置，伪造 id / 伪造
        # answers 均无从透传。仅当无 DB 元素（理论不发生）才保留前端项兜底。
        if not has_db_elements:
            values.extend(items)
        return values

    def build_command_resume(self, tasks: Any, resume_values: list[Any] | Mapping[str, Any]) -> Any:
        """构造 ``Command(resume=...)``（单中断裸列表 / 多中断 resume-map）。

        依据 Task 1 实测（``tests/core/interrupt/test_multi_interrupt_resume_map.py``）：
        单中断裸列表，多中断 resume-map（key = ``xxh3_128_hexdigest(f"{task.name}:{task.id}")``）。
        """
        from langgraph.types import Command

        if isinstance(resume_values, Mapping):
            # 已是 resume-map 形态：直接使用（调用方已按 task 推导 key）
            return Command(resume=dict(resume_values))

        items = list(resume_values) if isinstance(resume_values, list) else [resume_values]
        pending_tasks = self._pending_tasks(tasks)
        if len(pending_tasks) > 1:
            resume_map = self._build_resume_map(pending_tasks, items)
            logger.info(
                "[InterruptProcessor] 多中断 resume: %d tasks, 构造 resume-map",
                len(pending_tasks),
            )
            return Command(resume=resume_map)

        # 单中断裸列表（兼容 chat.py 现例）。带身份 id 的 item 需命中该 task 的
        # pending interrupt（防伪造 id 冒领——裸列表按位置消费不校验身份，
        # T-44-01）；无 id 旧形态原样放行
        claimed = self._filter_claimed_items(pending_tasks, items)
        return Command(resume=claimed)

    def _filter_claimed_items(self, pending_tasks: list[Any], items: list[Any]) -> list[Any]:
        """过滤裸列表 resume items：带身份 id 的须命中某 pending interrupt。

        item 无任何 id 键（旧形态）→ 原样保留（位置语义）；携带 interruptId /
        toolCallId 但不命中任何 pending → 丢弃（防伪造 id 冒领 resume 值）。
        """
        pending_ids: set[str] = set()
        pending_call_ids: set[str] = set()
        for task in pending_tasks:
            for intr in getattr(task, "interrupts", None) or []:
                intr_id = interrupt_id_of(intr)
                if intr_id:
                    pending_ids.add(str(intr_id))
                value = getattr(intr, "value", intr)
                if isinstance(value, dict) and value.get("toolCallId"):
                    pending_call_ids.add(str(value["toolCallId"]))
        kept: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                item_id = item.get("interruptId") or item.get("interrupt_id") or item.get("id")
                item_call_id = item.get("toolCallId")
            else:
                item_id = (
                    getattr(item, "interruptId", None)
                    or getattr(item, "interrupt_id", None)
                    or getattr(item, "id", None)
                )
                item_call_id = getattr(item, "toolCallId", None)
            if item_id is None and item_call_id is None:
                kept.append(item)  # 无 id 旧形态：位置语义放行
                continue
            if (item_id and str(item_id) in pending_ids) or (item_call_id and str(item_call_id) in pending_call_ids):
                kept.append(item)
            else:
                logger.warning(
                    "[InterruptProcessor] resume item 身份未命中任何 pending，丢弃（防冒领）: "
                    "interruptId=%r, toolCallId=%r",
                    item_id,
                    item_call_id,
                )
        return kept

    def _pending_tasks(self, tasks: Any) -> list[Any]:
        """返回带 pending interrupt 的 task 列表。"""
        if not tasks:
            return []
        return [t for t in tasks if getattr(t, "interrupts", None)]

    def _build_resume_map(self, pending_tasks: list[Any], resume_items: list[Any]) -> dict[str, Any]:
        """按 task 与 resume item 关联构造 resume-map（D-05，Task 1 实测结论）。

        两遍匹配（UAT 死循环修复）：Pass 1 身份精确匹配优先认领——``intr.id`` ↔
        item.interruptId（同一命名空间：LangGraph 中断 id 与前端卡片 id 同源）；
        Pass 2 顺序兜底仅对未精确命中的 task、且只能使用剩余未被认领的 item。
        单遍顺序兜底会被 state.tasks 顺序抢先劫走带身份的 item（派错 task →
        被答 interrupt 永不消费 → 每轮重推同一张卡死循环）。
        """
        # 双命名空间索引：interruptId（LangGraph 中断 id，兼容 DB 元素的 ``id`` 键）
        # 与 toolCallId（tool 链接），两键恒不互通（历史 bug：单键索引跨命名空间
        # 匹配恒失败）
        by_interrupt_id: dict[str, Any] = {}
        by_tool_call_id: dict[str, Any] = {}
        for item in resume_items:
            if isinstance(item, dict):
                item_interrupt_id = item.get("interruptId") or item.get("id")
                item_call_id = item.get("toolCallId")
            else:
                item_interrupt_id = getattr(item, "interruptId", None) or getattr(item, "id", None)
                item_call_id = getattr(item, "toolCallId", None)
            if item_interrupt_id:
                by_interrupt_id.setdefault(str(item_interrupt_id), item)
            if item_call_id:
                by_tool_call_id.setdefault(str(item_call_id), item)

        resume_map: dict[str, Any] = {}
        used: set[int] = set()
        claimed: set[int] = set()

        def _task_key(task: Any) -> str:
            return xxh3_128_hexdigest(f"{task.name}:{task.id}".encode())

        # Pass 1：身份精确匹配优先认领（interrupt id 同源 → toolCallId）
        for idx, task in enumerate(pending_tasks):
            value = self._pick_claimed_value(task, by_interrupt_id, by_tool_call_id, resume_items, used)
            if value is not None:
                claimed.add(idx)
                resume_map[_task_key(task)] = value

        # Pass 2：顺序兜底（**仅无 id 旧形态** item 的兼容路径）——只要任何 item
        # 携带 interruptId / toolCallId 身份，即关闭兜底：未命中身份的 item 直接
        # 丢弃（防伪造 id 冒领无关 pending 的 resume 值，T-44-01 旁路）
        if by_interrupt_id or by_tool_call_id:
            return resume_map
        for idx, task in enumerate(pending_tasks):
            if idx in claimed:
                continue
            for item_idx, item in enumerate(resume_items):
                if item_idx not in used:
                    used.add(item_idx)
                    resume_map[_task_key(task)] = item
                    break
            # 无剩余 item：D-10——未就绪 pending 保持挂起，不写入 resume-map
        return resume_map

    def _pick_claimed_value(
        self,
        task: Any,
        by_interrupt_id: dict[str, Any],
        by_tool_call_id: dict[str, Any],
        resume_items: list[Any],
        used: set[int],
    ) -> Any:
        """Pass 1：按身份精确认领 resume item（不顺序兜底）。

        匹配优先级：``intr.id`` ↔ item.interruptId（同源命名空间）→
        ``value.toolCallId`` ↔ item.toolCallId。未命中返回 None（是否兜底由
        调用方两遍编排决定）。
        """

        def _claim(candidate: Any) -> Any | None:
            idx = next((i for i, r in enumerate(resume_items) if r is candidate), -1)
            if idx >= 0:
                used.add(idx)
                return candidate
            return None

        for intr in getattr(task, "interrupts", None) or []:
            intr_id = interrupt_id_of(intr)
            if intr_id and str(intr_id) in by_interrupt_id:
                claimed_value = _claim(by_interrupt_id[str(intr_id)])
                if claimed_value is not None:
                    return claimed_value
            value = getattr(intr, "value", intr)
            if isinstance(value, dict):
                call_id = value.get("toolCallId")
                if call_id and str(call_id) in by_tool_call_id:
                    claimed_value = _claim(by_tool_call_id[str(call_id)])
                    if claimed_value is not None:
                        return claimed_value
        return None

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #

    def _get_interrupts_from_tasks(self, tasks: Any) -> list[dict]:
        """从 LangGraph 的 state tasks 获取 interrupt（value dict）。

        收集待 gate 的**全部** pending interrupt value（含 ask_user，GATE-01）。
        串行门禁对**所有**中断做就绪判定：approval / ask_user 统一走只读门禁
        ``query_resume_status``（D-06/08）——都只读 DB 权威记录判终态，不写 DB。
        读写分离（D-13 精神）：门禁只读，写仍由 handler.on_resume 承担。
        """
        values: list[dict] = []
        if not tasks:
            return values
        for task in tasks:
            for intr in getattr(task, "interrupts", None) or []:
                value = getattr(intr, "value", intr)
                if not isinstance(value, dict):
                    continue
                # 兼容 target 形态（interrupt_reason，reason=None）与 prepare 后完整形态。
                # GATE-01：ask_user pending 不再跳过，纳入全量收集（读门禁判已答）。
                values.append(value)
        return values

    @staticmethod
    def _reason_of(pending: dict) -> str | None:
        """从 pending interrupt value 提取 reason（查表键）。"""
        if not isinstance(pending, dict):
            return None
        return pending.get("reason") or pending.get("interrupt_reason")

    def _aggregate_resume_status(
        self,
        tasks: Any,
        session_code: str,
        thread_id: str,
    ) -> list[dict[str, Any]]:
        """**零 reason 聚合循环**（D-06/08）：全 pending 统一经 ``query_resume_status`` 只读门禁。

        逐个 pending interrupt 经 ``self._handlers.get(self._reason_of(pending))``
        查命中对偶单元，统一调 ``handler.query_resume_status(session_code, pending)``
        —— **无任何 reason 特判**（approval / ask_user 全走此门禁）。门禁只读 DB
        权威记录判就绪，不写 DB（读写分离 D-13）。未注册 reason 的 handler 返回
        None → 跳过该 pending（无法判定 → 保守不计入就绪）。聚合后的逐元素
        hydrate / Command 构造由调用方（:meth:`get_resume_input`）承接
        （``_unified_resume_values`` / ``build_command_resume`` 契约不变）。

        Args:
            tasks: graph ``state.tasks``（含各 pending interrupt 的 task）。
            session_code: 会话 code（DB 权威记录查询用）。
            thread_id: 图线程 id。

        Returns:
            各对偶单元门禁返回的 ``{"action": ..., "resume_value": ...}`` dict 列表。
        """
        unit_results: list[dict[str, Any]] = []
        for pending in self._get_interrupts_from_tasks(tasks):
            handler = self._handlers.get(self._reason_of(pending))
            if handler is None:
                logger.warning(
                    "[InterruptProcessor] 无 reason=%s 的 handler，跳过聚合门禁（保守不计入就绪）",
                    self._reason_of(pending),
                )
                continue
            unit_results.append(
                handler.query_resume_status(
                    session_code,
                    pending,
                )
            )
        return unit_results


__all__ = [
    "InterruptProcessor",
]
