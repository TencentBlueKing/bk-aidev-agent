# -*- coding: utf-8 -*-
"""ask_user_question interrupt 处理器 — 通用「向用户提问」交互工具的独立处理器。

本模块为 ask_user_question 中断处理层的**单源承载**（原 ag_ui 侧实现整块迁入 43-03，
shim 已随 43-07 移除），提供：

- ``AskUserQuestionHandler`` —— 独立类（不继承任何 ABC），实现 4 个方法
  + ``outcome_builder`` 属性，供工具与测试直接实例化调用。
- ``AskUserQuestionOutcomeBuilder`` —— 续流终态形态 ``(outcome, result)``
  构造器（与 ``ApprovalOutcomeBuilder`` 对称，差异：无 ticket 子结构）。
- ``AskUserQuestionMetadata`` / ``AskUserQuestionOption`` /
  ``AskUserQuestionItem`` —— 协议对齐的 Pydantic 定义
- 协议层纯函数（``extract_message_id`` / ``build_skipped_answers`` /
  ``build_updated_builtin_property`` / ``filter_ask_user_question_interrupts`` /
  ``parse_resume_answers``）。

Harness 依赖方向：本模块仅依赖标准库 / pydantic / ``aidev_agent.enums``（PromptRole
全局合法） / 包内 ``utils.py``（get_interrupt_value），不 import core/services/api。
"""

from __future__ import annotations

import copy
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict

from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager.types import ASK_USER_QUESTION_REASON
from aidev_agent.packages.interrupt_manager.utils import get_interrupt_value, interrupt_id_of

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------- #
# 常量
# ---------------------------------------------------------------------- #

# ``ASK_USER_QUESTION_REASON`` 由 ``interrupt_manager.types`` 提供（= InterruptReason.USER_QUESTION）。
# 该字段是 AGUI 协议中断标识，用于区分 ask_user_question 与 ``tool_approval``，
# 驱动路由分发与 DB 查询过滤。必须显式设置，否则 ``_normalize_interrupt_value``
# 会 fallback 到 ``"tool_call"``（研究报告 6.4 节风险点）。


class InterruptStatus(str, Enum):
    """ask_user_question 中断三态。

    与 ``approval.py`` 的 ``ApproveResult`` 三态设计对称（差异：ApproveResult
    用普通类属性，InterruptStatus 用 Enum 以获得类型安全和成员枚举能力）。
    继承 ``str`` 保证 ``InterruptStatus.PENDING == "pending"`` 为 ``True``，
    Pydantic v2 序列化输出字符串值 ``"pending"``（非 ``"InterruptStatus.PENDING"``）。
    """

    PENDING = "pending"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


ASK_USER_QUESTION_SKIPPED_CONTENT = "用户未回答本次提问，已跳过；用户改为直接输入了新的消息。"
"""用户跳过提问时的工具返回文案。

用户忽略提问弹窗、直接输入新消息时（``resume`` 与 ``input`` 同时有值），
本文案作为 ``ask_user_question`` 的工具返回值，让 LLM 明确知道问题未被回答
且不应重复提问。与审批的 ``"工具审批未通过，已取消执行。`` 定位一致，
差异：跳过不是错误（``status="success"``），审批拒绝是错误（``status="error"``）。
"""


# ---------------------------------------------------------------------- #
# 完整问题模型 Pydantic 定义
# ---------------------------------------------------------------------- #


class AskUserQuestionOption(BaseModel):
    """ask_user_question 的结构化选项（协议字段：label + description，无 value）。"""

    label: str
    description: str | None = None


class AskUserQuestionItem(BaseModel):
    """单问题项 —— 协议 metadata.questions 数组元素。"""

    header: str | None = None
    multiSelect: bool = False
    question: str
    options: list[AskUserQuestionOption] | None = None


class AskUserQuestionMetadata(BaseModel):
    """ask_user_question interrupt 的 metadata 字段。

    metadata 仅含 questions 数组（+ 运行时 type/status 字段），所有
    ask_user_question 专属字段承载于 ``metadata.questions`` 内，
    顶层复用 AG-UI ``Interrupt`` 模型，不修改 ``ag_ui/types.py``。
    """

    type: Literal["ask_user_question"] = "ask_user_question"
    status: InterruptStatus = InterruptStatus.PENDING
    questions: list[AskUserQuestionItem]


class AskUserQuestionTarget(BaseModel):
    """ask_user_question 中断目标抽象（Pydantic 承载，抛出层直抛，无随机 id）。

    仅承载「向用户提问」的目标数据（questions + 固定 reason + message/toolCallId/
    expiresAt），不含 id / metadata —— 这些单格式 payload 字段由分发层
    ``InterruptDispatcher`` 注入真实 LangGraph ``Interrupt.id``、由流结束层
    ``AskUserQuestionHandler.prepare`` 就地拼装（id 生成一次，SSE/DB 同源）。
    ``interrupt_reason`` 固定为 ``ASK_USER_QUESTION_REASON``（InterruptReason.USER_QUESTION
    = "aidev:user_question"）。``message`` / ``toolCallId`` / ``expiresAt`` 由抛出层
    ``get_ask_user_question_target`` 在构造时确定性填充（不在 target 内生成随机
    值）；id 不在 target（由 LangGraph 分配、dispatcher 注入）。``extra="ignore"``
    保证兼容旧 checkpoint（注入的 ``reason`` 等 extra 键被忽略，不报错）。
    """

    model_config = ConfigDict(extra="ignore")
    questions: list[AskUserQuestionItem]
    interrupt_reason: str = ASK_USER_QUESTION_REASON
    message: str = ""
    toolCallId: str = ""
    expiresAt: str = ""


# ---------------------------------------------------------------------- #
# 续流终态形态构造器
# ---------------------------------------------------------------------- #


class AskUserQuestionOutcomeBuilder:
    """ask_user_question 续流终态形态构造器。

    镜像 ``ApprovalOutcomeBuilder``，差异：ask_user_question 的 metadata
    无 ticket 子结构，``_apply_status_to_interrupt_metadata`` 仅刷写顶层
    ``metadata.status``。
    """

    @staticmethod
    def _apply_status_to_interrupt_metadata(interrupts: list[dict], status: str) -> None:
        """就地刷写每条 interrupt 的 ``metadata.status``（无 ticket 子结构）。

        与 ``ApprovalOutcomeBuilder._apply_status_to_interrupt_metadata`` 的
        差异：不刷写 ``metadata.ticket.status``（ask_user_question 无工单）。
        """
        for item in interrupts:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                item["metadata"] = metadata
            metadata["status"] = status

    @staticmethod
    def _build_result_from_first_interrupt(first_interrupt: dict) -> dict:
        """将 ``interrupts[0]`` 扁平化为顶层 ``result`` 对象。

        协议 success payload 的 ``payload.answers`` 从 interrupt metadata
        提取（DB-write 路径在用户回答后将 answers 写入 metadata，与
        approval 将 status 写入 metadata 对称）。顶层新增 ``status`` 字段
        （协议 success payload 有此字段）。

        ``reason`` 取 ``reason or interrupt_reason``（防御 raw target 形态：
        D-12 工具直抛只有 ``interrupt_reason``——reason 为 null 时前端
        ``resultRenderers[reason]`` 查无渲染器，已回答卡不渲染）。
        """
        if not isinstance(first_interrupt, dict):
            return {}
        metadata = first_interrupt.get("metadata")
        interrupt_id = first_interrupt.get("id")
        answers = metadata.get("answers") if isinstance(metadata, dict) else None
        return {
            "id": interrupt_id,
            "interruptId": interrupt_id,
            "reason": first_interrupt.get("reason") or first_interrupt.get("interrupt_reason"),
            "message": first_interrupt.get("message"),
            "toolCallId": first_interrupt.get("toolCallId"),
            "status": metadata.get("status") if isinstance(metadata, dict) else None,
            "payload": {"answers": answers if isinstance(answers, list) else []},
        }

    @classmethod
    def upgrade_content_to_success(
        cls,
        content: Any,
        status: str = InterruptStatus.RESOLVED.value,
        resume_answers: list | None = None,
    ) -> dict | None:
        """将 ask_user_question 中断 content 升级为"终态形态"。

        与 ``ApprovalOutcomeBuilder.upgrade_content_to_success`` 对称：
        将 outcome.type 从 interrupt 改为 success，刷写 metadata.status，
        构造 result 字段。用于续流成功后更新 DB 中的 interrupt 记录。

        Args:
            content: 原始 content（dict 或 JSON 字符串）。
            status: 终态状态（resolved / cancelled）。
            resume_answers: 用户本轮 resume 提交的 answers（权威来源）。
                首次中断入库时 metadata 不含 answers（answers 只走 resume payload），
                因此 ``_build_result_from_first_interrupt`` 从 metadata 取到的 answers
                永远为 None。传入此参数后注入到 ``result["payload"]["answers"]``，
                与 SSE 路径（``_build_resume_ask_user_question_finished_event``）对称。
                None 或空列表时保留 builder 默认 ``[]``。

        Returns:
            改写后的 content dict（深拷贝、不污染入参）；结构不识别时返回 None。
        """
        if content is None:
            return None
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (TypeError, ValueError):
                return None
        if not isinstance(content, dict):
            return None
        outcome = content.get("outcome")
        if not isinstance(outcome, dict):
            return None
        if outcome.get("type") not in ("interrupt", "success"):
            return None
        interrupts = outcome.get("interrupts")
        if not isinstance(interrupts, list) or not interrupts:
            return None

        new_content = copy.deepcopy(content)
        new_outcome = new_content["outcome"]
        new_outcome["type"] = "success"
        new_interrupts = new_outcome["interrupts"]
        cls._apply_status_to_interrupt_metadata(new_interrupts, status)
        new_content["result"] = cls._build_result_from_first_interrupt(new_interrupts[0])
        # 与 SSE 路径对称（_build_resume_ask_user_question_finished_event）：resume_answers
        # 是用户刚提交答案的权威来源，覆盖 builder 从 metadata 取到的空 answers。
        if resume_answers and isinstance(new_content["result"], dict):
            new_content["result"]["payload"]["answers"] = list(resume_answers)
        return new_content

    @classmethod
    def build_run_finished_payload(
        cls,
        interrupts: list[dict],
        status: str,
        resume_answers: list | None = None,
    ) -> tuple[dict, dict]:
        """构造续流首条 ``RUN_FINISHED`` 事件需要的 ``(outcome, result)`` 字典对。

        与 ``ApprovalOutcomeBuilder.build_run_finished_payload`` 形态对称：
        ``outcome.type == "success"``，``result`` 为 ``interrupts[0]`` 的
        扁平化版本。差异：``status`` 为 ``"resolved" | "cancelled"``（无审批
        三态），``_apply_status_to_interrupt_metadata`` 不刷写 ticket。

        Args:
            interrupts: ask_user_question 中断记录列表（深拷贝后使用，入参不污染）。
            status: 终态状态（``"resolved" | "cancelled"``）。
            resume_answers: 用户本轮 resume 提交的 answers（权威来源）。
                首次中断入库时 metadata 不含 answers（answers 只走 resume payload），
                因此 ``_build_result_from_first_interrupt`` 从 metadata 取到的 answers
                永远为 None。传入此参数后注入到 ``result["payload"]["answers"]``，
                与 ``upgrade_content_to_success`` 对称。None 或空列表时保留 builder 默认 ``[]``。
        """
        safe_interrupts = copy.deepcopy(interrupts) if interrupts else []
        cls._apply_status_to_interrupt_metadata(safe_interrupts, status)
        outcome = {"type": "success", "interrupts": safe_interrupts}
        result = cls._build_result_from_first_interrupt(safe_interrupts[0]) if safe_interrupts else {}
        # resume_answers 是用户刚提交答案的权威来源（首次中断入库时 metadata 无 answers，
        # answers 只走 resume payload），注入到 result["payload"]["answers"]，与 upgrade_content_to_success 对称。
        # WR-06 防御：interrupts 为空时 result 为 {}，先判 payload 非空再写入，避免 KeyError。
        if resume_answers and isinstance(result, dict) and result.get("payload") is not None:
            result["payload"]["answers"] = list(resume_answers)
        return outcome, result


# ---------------------------------------------------------------------- #
# 独立处理器
# ---------------------------------------------------------------------- #


class AskUserQuestionHandler:
    """ask_user_question interrupt 的独立处理器。

    作为独立类存在（不继承任何 ABC、不注册到 registry），供工具与测试
    直接实例化调用。

    对标 ``ApprovalStateHandler``（``aidev_agent/services/agent/approval.py``）
    ——两者都是「中断/续流状态处理器」，方法一一对应（``extract_builtin_property``
    对 ``_extract_builtin_property``、``hydrate_resume`` 对 ``hydrate_resume_payload``、
    ``should_emit_resume_finished`` 对续流首帧回放判定）。关键协议差异：

    - ``hydrate_resume`` 仅补充 ``status``（来自 db_data），**不覆写 payload**
      （答案由前端直接提交到 ``ResumeItem.payload``）。审批
      ``ApprovalStateHandler.hydrate_resume_payload`` 则会写 ``payload.approved``。
    - ``extract_builtin_property`` 不提取 ``callback_token`` / ``ticket_sn`` /
      ``tool_name``（ask_user_question 无工单）。
    - ``build_payload`` 不创建 ITSM 工单，interrupt id 使用
      ``uuid4().hex[:8]`` 而非 ``ticket_sn``。
    """

    reason = ASK_USER_QUESTION_REASON

    def prepare(
        self,
        interrupt: object,
        ticket_creator: object | None = None,
        **ctx: Any,
    ) -> object:
        """流结束拼装（对齐 ApprovalHandler.prepare，差异：ask_user 无建单副作用）。

        interrupt 为 LangGraph ``Interrupt`` 鸭子类型（``.id`` / ``.value``）。
        **就地 dict 手术作用于 ``interrupt.value``**（若 value 含 ``interrupt_reason``
        键），**不碰 id**（value 中本就无 id 字段）：

        - ``pop("interrupt_reason")`` → 设置顶层 ``reason = ASK_USER_QUESTION_REASON``
        - ``pop("questions")`` → 移入 ``metadata = {type, status=pending, questions, toolArgs}``
          （``toolArgs = {"questions": questions}``，D-15：镜像 approval enrich，供续流
          回填重建 assistant tool_call 时还原 questions 参数）
        - ``message`` / ``toolCallId`` / ``expiresAt`` 顶层**保留**（抛出层已填充）

        非 dict value / 无 ``interrupt_reason`` 键 → 原样返回（旧 checkpoint 兼容）。
        ``ticket_creator`` 由 dispatcher 透传，吸收但忽略不用。

        Args:
            interrupt: LangGraph ``Interrupt`` 鸭子类型对象（``.id`` / ``.value``）。
            ticket_creator: 建单封装（与 ApprovalHandler 签名对齐，ask_user 不使用，忽略）。
            **ctx: 运行时 ctx（忽略）。

        Returns:
            同一 interrupt 对象，其 ``value`` 已被就地 dict 手术（target 形态）或原样
            （完整形态 / 非 dict value）。
        """
        value = getattr(interrupt, "value", None)
        if not isinstance(value, dict):
            return interrupt
        if "interrupt_reason" in value:
            value.pop("interrupt_reason", None)
            value["reason"] = ASK_USER_QUESTION_REASON
            questions = value.pop("questions", [])
            value["metadata"] = {
                "type": "ask_user_question",
                "status": InterruptStatus.PENDING.value,
                "questions": questions if isinstance(questions, list) else [],
                # D-15：镜像 approval ItsmApprovalMetadata(toolArgs=...)，承载 questions
                # 参数供续流回填重建 assistant tool_call（_fetch_tool_call_reconstruction）。
                "toolArgs": {"questions": questions if isinstance(questions, list) else []},
            }
            interrupt.value = value
        return interrupt

    def __init__(
        self,
        *,
        dispatch_skip: Callable[[dict], None] | None = None,
        dispatch_answer: Callable[[dict], None] | None = None,
        resource_manager: object | None = None,
    ) -> None:
        """构造注入两个 bound method（D-14）与 resource_manager（Gap 1 修复：自持回落）。

        Args:
            dispatch_skip: chat.py ``_dispatch_ask_user_skip`` 的 bound method
                （skip 分支事件派发）。
            dispatch_answer: chat.py ``_dispatch_ask_user_answer`` 的 bound method
                （answer 分支事件派发）。
            resource_manager: 鸭子注入（object | None，packages 层不 import services 类型，
                红线合规，同 ApprovalHandler）。供 ``query_resume_status`` 缺省回落自持实例
                查 DB 权威记录（修复纯 ask_user 续流 answers 静默丢失）。
        """
        self._dispatch_skip = dispatch_skip
        self._dispatch_answer = dispatch_answer
        self._resource_manager = resource_manager

    def on_resume(self, resume: Any, *, interrupt_messages: Any, **ctx: Any) -> None:
        """ask_user 三态分流 + chat_history inplace 改写 + 事件派发（skip/answer 经注入 bound method）。

        resume 侧写路径（U-02/D-05/D-16，收编原 ``consume_resume`` 职责）：
        保留 ``is_ask_user_resume`` 判别 / ``validate_resume_consistency`` /
        ``parse_resume_answers`` / skip·answer 决策，事件派发内聚到本方法
        （经构造注入的 ``self._dispatch_skip`` / ``self._dispatch_answer`` 直调，
        D-16：替代返回 dispatch_events 由装配层派发）。返回 None。

        Args:
            resume: 前端续流 resume 值（不可信输入，T-48-01，经
                ``validate_resume_consistency`` 校验）。
            interrupt_messages: 该 interrupt_id 命中的 chat_history 消息内容
                （list[dict]）。本方法主要依赖 ``ctx.chat_history`` 末尾 interrupt
                记录（inplace 改写）。
            **ctx: 运行时 ctx（``chat_history`` / ``turn_id`` / ``input_text``）。

        Raises:
            AgentException: ``validate_resume_consistency`` 校验失败时抛出。
        """
        is_ask_user = AskUserQuestionHandler.is_ask_user_resume(resume)
        if not is_ask_user:
            return
        chat_history = ctx.get("chat_history")
        interrupt = chat_history[-1] if chat_history else None
        AskUserQuestionHandler.validate_resume_consistency(resume, interrupt)
        turn_id = ctx.get("turn_id", "")
        answers = parse_resume_answers(resume) or []
        if ctx.get("input_text") or not answers:
            # skip：改写 interrupt 为 CANCELLED；装配层据此补 tool 记录 + 派发事件
            result = self._handle_skip_path(interrupt, turn_id)
            result["action"] = "skip"
            if self._dispatch_skip is not None:
                self._dispatch_skip(result)
            return
        result = self._handle_answer_path(interrupt, answers, turn_id)
        result["action"] = "answer"
        if self._dispatch_answer is not None:
            self._dispatch_answer(result)

    def query_resume_status(
        self,
        session_code: str,
        pending_interrupt: Any,
        *,
        resource_manager: object | None = None,
    ) -> dict[str, Any]:
        """**全员只读门禁**（D-06，ask_user 实现）：按当前 pending 定位其专属已答记录。

        只读（D-13 读写分离）：不写 DB。镜像
        ``ApprovalStateHandler.query_approval_info_for_interrupt`` 的 per-pending
        定位模式。resume_value 从已答记录的 ``result.payload.answers`` 重建
        ``{interruptId, status, payload: {answers}}``（DB 权威，T-44-01，
        弃前端透传）。与写路径 ``consume_resume`` 职责分离。

        **对偶单元层门禁契约**（供 processor 聚合循环消费）：
        ``{"action": "resolved", "resume_value": {...}}`` 或
        ``{"action": "not_ready", "resume_value": None}``。

        Args:
            session_code: 会话 code。
            pending_interrupt: 当前被门禁的 pending interrupt value dict
                （含 id 或 toolCallId，经 :func:`interrupt_id_of` / ``toolCallId``
                提取）。编排层聚合循环传 ``_get_interrupts_from_tasks`` 的 value
                dict（id 与 value 分离，value 可能无 id 但必有 toolCallId）。
            resource_manager: 鸭子注入（object | None，packages 层不 import
                services 类型）。processor 聚合循环传 ``self._resource_manager``。

        Returns:
            门禁契约 dict（``action`` + ``resume_value``，字段名固定）。
        """
        from aidev_agent.packages.interrupt_manager.approval import ApprovalStateHandler

        # 缺省回落自持实例（Gap 1）：resource_manager kwarg 非 None 且无自持 state_handler
        # 时现构造；否则回落 self._resource_manager 构造的 state_handler（修复 RM 缺失 →
        # not_ready → answers 丢失）。镜像 ApprovalHandler 回落模式（approval.py:1135-1137）。
        state_handler = ApprovalStateHandler(resource_manager=self._resource_manager)
        if resource_manager is not None and state_handler.resource_manager is None:
            state_handler = ApprovalStateHandler(resource_manager=resource_manager)
        pending_id = str(interrupt_id_of(pending_interrupt) or "") if pending_interrupt else ""
        pending_call_id = str(pending_interrupt.get("toolCallId") or "") if isinstance(pending_interrupt, dict) else ""
        if not pending_id and not pending_call_id:
            return {"action": "not_ready", "resume_value": None}
        for record in reversed(state_handler._list_interrupt_records(session_code)):
            elements = state_handler._extract_interrupts_from_content(record.get("content"))
            # per-pending 定位：按 id（interrupt_id_of）或 toolCallId（value 无 id 时，
            # 镜像 approval query_approval_info_for_interrupt :541-543）匹配专属元素。
            matched = next(
                (
                    e
                    for e in elements
                    if isinstance(e, dict)
                    and (
                        (pending_id and str(e.get("id")) == pending_id)
                        or (not pending_id and pending_call_id and str(e.get("toolCallId")) == pending_call_id)
                    )
                ),
                None,
            )
            if matched is None:
                continue
            content = record.get("content") if isinstance(record.get("content"), dict) else {}
            outcome = content.get("outcome") if isinstance(content.get("outcome"), dict) else {}
            outcome_type = outcome.get("type")
            status = (matched.get("metadata") or {}).get("status")
            if outcome_type == "success" or status in ("resolved", "cancelled"):
                result = content.get("result") if isinstance(result := content.get("result"), dict) else {}
                payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
                answers = payload.get("answers", [])
                # resume_value.interruptId 取匹配元素的真实 id（非 pending 的空 id）
                resolved_id = str(matched.get("id") or "") or pending_id
                return {
                    "action": "resolved",
                    "resume_value": {
                        "interruptId": resolved_id,
                        "status": status or "resolved",
                        "payload": {"answers": answers if isinstance(answers, list) else []},
                    },
                }
            # D-γ 修复（ask_user 重复分发死循环）：命中但非终态 → 继续向更旧记录扫描。
            # 同 interrupt id 的较新 pending 记录（分支 A 保守重推产物）不得永久遮蔽
            # 更旧的已答终态记录——reversed 首匹配在 pending 处即返 not_ready 会造成
            # 每轮重推的死循环（id 稳定：xxh3 task ns，同 id 即同一中断）。
            continue
        return {"action": "not_ready", "resume_value": None}

    def _handle_skip_path(self, interrupt: Any, turn_id: str) -> dict[str, Any]:
        """跳过路径：改写 interrupt 为 CANCELLED，返回装配层所需数据（随迁自 chat.py:274）。

        - 从 ``builtin_property`` 取 ``tool_call_id`` / ``questions``；
        - 构造 ``skipped_answers``（``build_skipped_answers``）；
        - 将 ``interrupt.content`` 升级为终态（``status=CANCELLED``）并写回
          ``interrupt.content``（DB 改写）。

        事件派发（``ExtendToolCallResultEvent`` / ``AskUserQuestionFinalized``）
        与 ``ChatPrompt`` TOOL 记录补写属装配层职责，本方法仅返回数据，由调用方
        （chat.py / processor）按 ``action == "skip"`` 派发。
        """
        builtin = getattr(interrupt, "builtin_property", None) or {}
        tool_call_id = builtin.get("tool_call_id", "")
        # questions 读取兼容双形态：bp 直存（extract_builtin_property 写入）与适配层拍平后的
        # 顶层 extras（行 property.builtin_property 为空基底，extract 字段落在行顶层——
        # 2026-09-02 pdb 实证）。只读 bp 会得到空列表 → skipped_answers=[] →
        # result.payload.answers=[] → 前端"回答内容"卡为空。
        questions = builtin.get("questions") or getattr(interrupt, "questions", None) or []
        skipped_answers = build_skipped_answers(questions)
        upgraded = self._upgrade_interrupt(interrupt, status=InterruptStatus.CANCELLED.value, answers=skipped_answers)
        return {
            "interrupt": interrupt,
            "tool_call_id": tool_call_id,
            "status": InterruptStatus.CANCELLED.value,
            "content_id": getattr(interrupt, "id", None),
            "builtin_property": builtin,
            "upgraded_content": upgraded,
            "skipped_answers": skipped_answers,
            "turn_id": turn_id,
        }

    def _handle_answer_path(self, interrupt: Any, answers: list, turn_id: str) -> dict[str, Any]:
        """答题路径：改写 interrupt 为 RESOLVED，返回装配层所需数据（随迁自 chat.py:336）。"""
        upgraded = self._upgrade_interrupt(interrupt, status=InterruptStatus.RESOLVED.value, answers=answers)
        return {
            "interrupt": interrupt,
            "status": InterruptStatus.RESOLVED.value,
            "content_id": getattr(interrupt, "id", None),
            "builtin_property": getattr(interrupt, "builtin_property", None) or {},
            "upgraded_content": upgraded,
            "answers": answers,
            "turn_id": turn_id,
        }

    def _upgrade_interrupt(self, interrupt: Any, *, status: str, answers: list) -> dict | None:
        """把 chat_history 末尾 interrupt 记录改写为终态，返回 upgraded content。

        等价迁移自 chat.py ``_resolve_chat_history_interrupt``：用
        ``AskUserQuestionOutcomeBuilder.upgrade_content_to_success`` 升级
        ``interrupt.content``（DB 改写），结构不识别时返回 None（调用方跳过
        finalize 事件派发）。

        content 升级成功时同步把记录消息级 ``status`` 置 ``"complete"``（与
        DB finalize 写值 base.py handle_ask_user_question_finalize 对齐）：
        首帧 MESSAGES_SNAPSHOT 数据源是本账本，若 status 停留建卡时的
        ``pending``，前端会把快照中的 resolved 卡当作 loading 消息，流末尾
        裸 ``RUN_FINISHED(success)`` 整体覆写 content 丢 ``result``，回显卡
        随之消失（2026-09-02 抓包定位）。

        注意必须**顶层 + builtin_property 双写**：适配层把行 status 回嵌进
        ``builtin_property``，而快照转换器 ``_read_field`` 是 bp 优先读取，
        只改顶层会被 bp 里的旧 pending 压住（2026-09-02 pdb 实证）。
        """
        upgraded = AskUserQuestionOutcomeBuilder.upgrade_content_to_success(
            getattr(interrupt, "content", None),
            status,
            resume_answers=answers,
        )
        if upgraded is not None:
            interrupt.content = upgraded
            interrupt.status = "complete"
            if isinstance(getattr(interrupt, "builtin_property", None), dict):
                interrupt.builtin_property["status"] = "complete"
        return upgraded

    def build_payload(
        self,
        *,
        questions: list[dict],
        tool_call_id: str,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        """构造 ask_user_question interrupt payload。

        顶层复用 AG-UI ``Interrupt`` 模型（``id`` / ``reason`` /
        ``toolCallId`` / ``message`` / ``metadata`` / ``expiresAt``），所有
        ask_user_question 专属字段放入 ``metadata.questions``。

        Args:
            questions: 问题数组，每项为
                ``{"header": str, "multiSelect": bool, "question": str,
                "options": [{"label": str, "description": str?}]}``。
            tool_call_id: 触发该 interrupt 的 tool_call id。
            expires_at: 中断过期时间（ISO 8601 带时区偏移字符串）。
                为 ``None`` 时自动生成当前时间 + 24h。

        Returns:
            interrupt payload dict，顶层结构遵循 AG-UI ``Interrupt`` 模型。
        """
        # id 格式 int-question-{tool_call_id}-{uuid_hex}
        interrupt_id = f"int-question-{tool_call_id}-{uuid.uuid4().hex[:8]}"
        metadata: dict[str, Any] = {
            "type": "ask_user_question",
            "status": InterruptStatus.PENDING.value,
            "questions": questions,
        }
        # expiresAt 顶层字段，未传入时自动生成 24h 后过期
        if expires_at is None:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        return {
            "id": interrupt_id,
            "reason": ASK_USER_QUESTION_REASON,
            "toolCallId": tool_call_id,
            "message": f"需要用户回答：{questions[0]['question']}" if questions else "需要用户回答",
            "expiresAt": expires_at,
            "metadata": metadata,
        }

    @staticmethod
    def hydrate_resume(resume_items: Any, db_data: Any) -> None:
        """仅补充 status，不覆写 payload（支持类级调用，coordinator 混合续流分流用）。

        与审批的差异：审批会写 ``payload.approved``，ask_user_question
        **不动 payload**（答案由前端直接提交到 ``ResumeItem.payload``）。

        Args:
            resume_items: 续流请求项（list[dict|object] / dict / object）。
            db_data: status 字符串（``"resolved" | "cancelled"``）或 ``None``。
                ``None`` 时跳过 hydration（前端已自带 status）。
        """
        if not resume_items or db_data is None:
            return
        if isinstance(resume_items, dict):
            iterable: list = [resume_items]
        elif isinstance(resume_items, list):
            iterable = resume_items
        else:
            return
        for item in iterable:
            if isinstance(item, dict):
                # 仅在未设置 status 时补充，不覆写已有值
                item["status"] = item.get("status") or db_data
                continue
            # 兼容 Pydantic 模型 / 普通对象
            if hasattr(item, "__dict__") or hasattr(type(item), "__slots__"):
                try:
                    if not getattr(item, "status", None):
                        setattr(item, "status", db_data)
                except (AttributeError, TypeError):
                    continue

    def should_emit_resume_finished(self, interrupt_result: Any, interrupt_interrupts: Any) -> bool:
        """判断续流时是否需要 emit 首帧 ``RUN_FINISHED`` 回放。

        ask_user_question 也需要首帧回放（与 approval 对称），触发条件（&，
        全部满足）：

        1. 存在 ``interrupt_result``（上游 chat 入口透传的答案）；
        2. ``interrupt_interrupts`` 非空（DB 解析出原中断）；
        3. ``interrupts[0].reason == ASK_USER_QUESTION_REASON``，限定
           ask_user_question 类型，避免其他 interrupt 类型误触发。
        """
        if not interrupt_result:
            return False
        if not interrupt_interrupts:
            return False
        first = interrupt_interrupts[0] or {}
        return isinstance(first, dict) and first.get("reason") == ASK_USER_QUESTION_REASON

    def extract_builtin_property(self, interrupt_id: str, interrupt: Any, **kwargs: Any) -> dict[str, Any]:
        """[deprecated] 兼容别名：委托模块级纯函数（D-02 纯函数化后保留方法签名兼容）。

        .. note::
            base.py handle_run_finished 已改用模块级纯函数
            ``user_question.extract_builtin_property``；本方法仅为旧调用方（测试 /
            历史引用）提供向后兼容入口，内部委托模块级纯函数。
        """
        return extract_builtin_property(
            interrupt_id,
            interrupt,
            graph_thread_id=kwargs.get("graph_thread_id"),
        )

    @staticmethod
    def is_ask_user_resume(resume: Any) -> bool:
        """判断 resume 是否为 ask_user_question 类型。

        ask_user_question 的 resume payload 含 ``answers`` 字段；
        approval 的 payload 是 ``{approved: bool}``，不含 answers。
        兼容 list / dict 两种 resume 形态（_stream 归一化前可能为 dict）。
        对混合续流（审批 + ask_user 并行中断）遍历全部 items，任一含
        ``answers`` 即判定存在 ask_user 项（WR-02，避免首项为审批时漏判）。
        """
        items = resume if isinstance(resume, list) and resume else [resume]
        for item in items:
            if not isinstance(item, dict):
                continue
            payload = item.get("payload")
            if isinstance(payload, dict) and "answers" in payload:
                return True
        return False

    @staticmethod
    def validate_resume_consistency(resume: Any, interrupt: Any) -> None:
        """校验 resume 与 chat_history 末尾 interrupt 的一致性。

        ask_user_question resume 必须对应一条 pending 的末尾 INTERRUPT 记录，
        且 id 一致、tool_call_id 必存在（无 tool_call_id 说明脏数据写入）：

        - ``interrupt`` 不为 None 且 ``role == PromptRole.INTERRUPT.value``
          （必须是 chat_history 的最后一条，避免已回答的 interrupt 被二次回答）
        - ``interrupt.content`` 解析后 ``outcome.interrupts`` 为非空 list
          （DB 全量落库，多中断会话含全部 pending；SSE 单元素裁剪仅在序列化边界）
        - 存在 ``id`` == resume ``interruptId`` 的元素（按 id 在全量列表中定位）
        - 匹配元素 ``metadata.status`` == pending
        - ``interrupt.builtin_property.tool_call_id`` 必须存在且非空

        不满足时抛 ``AgentException``，错误信息说明哪项校验失败。

        Args:
            resume: ExecuteKwargs.resume（list/dict 形态均可）。
            interrupt: chat_history[-1]（已确保是末尾记录）。
        """
        from aidev_agent.exceptions import AgentException

        item = resume[0] if isinstance(resume, list) and resume else resume
        resume_id = item.get("interruptId") if isinstance(item, dict) else None

        if interrupt is None:
            raise AgentException(message="ask_user resume 缺少对应的 interrupt 记录")
        role = getattr(interrupt, "role", None)
        if role != PromptRole.INTERRUPT.value:
            raise AgentException(message=f"ask_user resume 期望末尾为 INTERRUPT 记录，实际 role={role}")

        content = getattr(interrupt, "content", None)
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (TypeError, ValueError) as exc:
                raise AgentException(message=f"ask_user resume 解析 interrupt content 失败: {exc}") from exc
        if not isinstance(content, dict):
            raise AgentException(message="ask_user resume 的 interrupt content 非合法 dict")

        outcome = content.get("outcome") or {}
        interrupts = outcome.get("interrupts") or []
        if not isinstance(interrupts, list) or not interrupts:
            raise AgentException(
                message=f"ask_user resume 期望 outcome.interrupts 非空 list，实际 {len(interrupts) if isinstance(interrupts, list) else '非 list'}"
            )
        # HI-02 修复后 outcome.interrupts 为 DB 全量落库（多中断会话含全部 pending），
        # 按 resume.interruptId 在全量列表中定位目标元素（SSE 单元素裁剪仅在序列化边界）
        matched = next(
            (intr for intr in interrupts if isinstance(intr, dict) and intr.get("id") == resume_id),
            None,
        )
        if matched is None:
            raise AgentException(message=f"ask_user resume interruptId={resume_id} 与 interrupt 记录所有元素 id 不一致")
        matched_metadata = matched.get("metadata") or {}
        status = matched_metadata.get("status")
        if status is None:
            # 兼容 target 形态历史落库（元素无 metadata，questions 在顶层）：以
            # outcome.type 推导——success=已回答终态（拒绝二次回答），其余视同
            # pending（未回答，新写入经归一化已带标准 metadata，不进此分支）
            status = "resolved" if outcome.get("type") == "success" else InterruptStatus.PENDING.value
        if status != InterruptStatus.PENDING.value:
            raise AgentException(message=f"ask_user resume 期望 interrupt status=pending，实际 status={status}")

        builtin = getattr(interrupt, "builtin_property", None) or {}
        # tool_call_id 容错链：记录级 builtin_property（新写入）→ 匹配元素 toolCallId
        # （兼容旧写入：reason 误归一为 tool_call 时经 DEFAULT_HANDLER 落库，builtin
        # 无 tool_call_id 但元素本身携带 toolCallId，链接关系仍成立）
        element_tool_call_id = matched.get("toolCallId") or matched.get("tool_call_id")
        if not builtin.get("tool_call_id") and not element_tool_call_id:
            raise AgentException(message="ask_user resume 的 interrupt 缺少 tool_call_id，存在脏数据")

    @property
    def outcome_builder(self) -> type:
        """返回 ``AskUserQuestionOutcomeBuilder``，用于构造续流首帧
        ``RUN_FINISHED`` 的 ``(outcome, result)``。"""
        return AskUserQuestionOutcomeBuilder


# ---------------------------------------------------------------------- #
# 协议层纯函数（Phase 14.1 — 从 services/nodes 层下沉的协议解析逻辑）
# ---------------------------------------------------------------------- #


def extract_builtin_property(
    interrupt_id: str,
    interrupt: Any,
    graph_thread_id: str | None = None,
) -> dict[str, Any]:
    """从 ask_user_question interrupt 提取落库用 ``builtin_property`` 字段（D-02 模块级纯函数）。

    由 ``AskUserQuestionHandler.extract_builtin_property`` 提出为模块级纯函数
    （方法体零 ``self`` 引用，逻辑照旧）。提取 ask_user_question 专属字段：
    ``questions`` / ``options`` / ``answers`` / ``multiSelect`` 等（字段名对齐
    协议）。与审批的差异：不提取 ``callback_token`` / ``ticket_sn`` /
    ``tool_name``（ask_user_question 无工单）。

    Args:
        interrupt_id: interrupt id。
        interrupt: interrupt 对象或 dict。
        graph_thread_id: 图线程 id（缺省时由实现按字段兜底）。

    Returns:
        落库用的 ``builtin_property`` dict。
    """
    return {
        "message_id": interrupt_id,
        "type": get_interrupt_value(interrupt, "type") or "ask_user_question",
        "interrupt_id": interrupt_id,
        "reason": get_interrupt_value(interrupt, "reason"),
        "tool_call_id": get_interrupt_value(interrupt, "toolCallId", "tool_call_id"),
        "questions": get_interrupt_value(interrupt, "questions"),
        "options": get_interrupt_value(interrupt, "options"),
        "answers": get_interrupt_value(interrupt, "answers"),
        "multiSelect": get_interrupt_value(interrupt, "multiSelect"),
        "graph_thread_id": graph_thread_id or get_interrupt_value(interrupt, "threadId", "thread_id"),
    }


def extract_message_id(upgraded: dict) -> str:
    """从升级后的 content 提取 message_id（三元 fallback）。

    优先取 ``result.interruptId``，次取 ``outcome.interrupts[0].id``，兜底空串。
    消除 bkplugin cancel/resolve 两处重复的三元表达式。
    """
    return (
        ((upgraded.get("result") or {}).get("interruptId"))
        or ((upgraded.get("outcome") or {}).get("interrupts") or [{}])[0].get("id")
        or ""
    )


def build_skipped_answers(questions: list) -> list[dict]:
    """为每个 question 构造 skipped answer（标记 label="skipped"）。

    消除 bkplugin cancel 内联的 list comprehension。过滤非 dict 元素，
    缺失字段使用默认值（``question`` 默认 ``""``、``multiSelect`` 默认 ``False``）。
    """
    return [
        {
            "question": q.get("question", ""),
            "multiSelect": q.get("multiSelect", False),
            "answer": [{"label": "skipped", "description": ASK_USER_QUESTION_SKIPPED_CONTENT}],
        }
        for q in questions
        if isinstance(q, dict)
    ]


def build_updated_builtin_property(db_item: dict, interrupt_id: str, status: str) -> dict:
    """从 DB item 的 property 构造更新后的 builtin_property 字段。

    保留已有字段，追加/覆写 ``status`` / ``message_id`` / ``interrupt_id``
    / ``reason``（``ASK_USER_QUESTION_REASON``）。用于续流成功后更新 DB
    interrupt 记录。

    Returns:
        更新后的 builtin_property dict（不修改入参 db_item）。
    """
    prop = db_item.get("property") if isinstance(db_item, dict) else None
    if isinstance(prop, str):
        try:
            prop = json.loads(prop)
        except (TypeError, ValueError):
            prop = {}
    if not isinstance(prop, dict):
        prop = {}
    raw_builtin = prop.get("builtin_property")
    if not isinstance(raw_builtin, dict):
        raw_builtin = {}
    updated_builtin = dict(raw_builtin)
    updated_builtin["status"] = status
    updated_builtin["message_id"] = interrupt_id
    updated_builtin["interrupt_id"] = interrupt_id
    updated_builtin["reason"] = ASK_USER_QUESTION_REASON
    return updated_builtin


def filter_ask_user_question_interrupts(tasks: Any) -> list[dict]:
    """从 graph state tasks 过滤 reason == ASK_USER_QUESTION 的 interrupts。

    双层遍历 ``for task in tasks`` → ``for intr in task.interrupts or []``，
    ``intr.value`` 为 str 时 ``json.loads`` 解析，过滤 reason 匹配的 value。

    返回**归一化副本**（浅拷贝，不污染 checkpoint 原值）：D-12 工具直抛的 raw
    target 形态无顶层 ``reason`` / ``id``（只有 ``interrupt_reason``，真实 id 在
    LangGraph ``Interrupt`` 对象上）。直接透传 raw 值会让续流 replay 事件退化
    （``result.reason=null`` → 前端 ``resultRenderers[null]`` 查无渲染器 →
    已回答卡不渲染 → 交互卡关闭后卡片凭空消失）。此处统一补齐 ``reason`` /
    ``id``，对齐回放消费方（``AskUserQuestionOutcomeBuilder`` 扁平化 result）
    期待的 enriched 形态。

    Returns:
        匹配的 interrupt value（dict，含补齐的 ``reason`` / ``id``）列表。
    """
    interrupts: list[dict] = []
    if not tasks:
        return interrupts
    for task in tasks:
        for intr in getattr(task, "interrupts", None) or []:
            value = getattr(intr, "value", intr)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (TypeError, ValueError):
                    continue
            if (
                isinstance(value, dict)
                and (value.get("reason") or value.get("interrupt_reason")) == ASK_USER_QUESTION_REASON
            ):
                normalized = dict(value)
                if not normalized.get("reason"):
                    normalized["reason"] = ASK_USER_QUESTION_REASON
                intr_id = getattr(intr, "id", None)
                if intr_id is not None and not normalized.get("id"):
                    normalized["id"] = intr_id
                interrupts.append(normalized)
    return interrupts


def parse_resume_answers(resume_value: Any) -> Any:  # nosemgrep: aidev-no-bare-any
    """从 interrupt() 的返回值（ResumeItem 列表）中提取用户答案。

    interrupt() 返回 Command(resume=...) 的 resume 值。生产环境中 chat.py
    传入 ``[ResumeItem(...)]`` 列表，每项含 interruptId/status/payload，
    用户答案在 ``payload.answers`` 中。直接 graph.ainvoke(Command(resume=...))
    测试场景中 resume 值可能是裸 answers 字典。

    Returns:
        提取出的用户答案（answers 列表或原始值），供写入 state 供工具函数读取。
    """
    if resume_value is None:
        return None
    if isinstance(resume_value, list) and resume_value:
        first = resume_value[0]
        if isinstance(first, dict):
            payload = first.get("payload")
            if isinstance(payload, dict) and "answers" in payload:
                return payload["answers"]
            if payload is not None:
                return payload
        return first
    if isinstance(resume_value, dict):
        if "answers" in resume_value:
            return resume_value["answers"]
        payload = resume_value.get("payload")
        if isinstance(payload, dict) and "answers" in payload:
            return payload["answers"]
        return resume_value
    return resume_value


__all__ = [
    "ASK_USER_QUESTION_REASON",
    "ASK_USER_QUESTION_SKIPPED_CONTENT",
    "InterruptStatus",
    "AskUserQuestionHandler",
    "AskUserQuestionItem",
    "AskUserQuestionOutcomeBuilder",
    "AskUserQuestionMetadata",
    "AskUserQuestionOption",
    "AskUserQuestionTarget",
    "extract_message_id",
    "build_skipped_answers",
    "build_updated_builtin_property",
    "filter_ask_user_question_interrupts",
    "parse_resume_answers",
    "extract_builtin_property",
]
