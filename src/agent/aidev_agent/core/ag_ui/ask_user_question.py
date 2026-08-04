# -*- coding: utf-8 -*-
"""ask_user_question interrupt 处理器 — 通用「向用户提问」交互工具的独立处理器。

本模块是 ask_user_question 工具的 interrupt 处理层，作为独立类存在
于 ``core/ag_ui/ask_user_question.py``，提供：

- ``AskUserQuestionHandler`` —— 独立类（不继承任何 ABC），实现 4 个方法
  + ``outcome_builder`` 属性，供工具与测试直接实例化调用。
- ``AskUserQuestionOutcomeBuilder`` —— 续流终态形态 ``(outcome, result)``
  构造器（与 ``ApprovalOutcomeBuilder`` 对称，差异：无 ticket 子结构）。
- ``AskUserQuestionMetadata`` / ``AskUserQuestionOption`` /
  ``AskUserQuestionItem`` —— 协议对齐的 Pydantic 定义
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel

from aidev_agent.core.ag_ui.utils import get_interrupt_value
from aidev_agent.enums import PromptRole

# ---------------------------------------------------------------------- #
# 常量
# ---------------------------------------------------------------------- #

ASK_USER_QUESTION_REASON = "aidev:user_question"
"""ask_user_question interrupt 的 reason 字符串。

该字段是 AGUI 协议中断标识，用于区分 ask_user_question 与 ``tool_approval``，
驱动路由分发与 DB 查询过滤。必须显式设置，否则 ``_normalize_interrupt_value``
会 fallback 到 ``"tool_call"``（研究报告 6.4 节风险点）。
"""


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

    header: str
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
        """
        if not isinstance(first_interrupt, dict):
            return {}
        metadata = first_interrupt.get("metadata")
        interrupt_id = first_interrupt.get("id")
        answers = metadata.get("answers") if isinstance(metadata, dict) else None
        return {
            "id": interrupt_id,
            "interruptId": interrupt_id,
            "reason": first_interrupt.get("reason"),
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
        if resume_answers and isinstance(result, dict):
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

    def hydrate_resume(self, resume_items: Any, db_data: Any) -> None:
        """仅补充 status，不覆写 payload。

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
        """从 ask_user_question interrupt 提取落库用的 ``builtin_property`` 字段。

        提取 ask_user_question 专属字段：``questions`` / ``options`` /
        ``answers`` / ``multiSelect`` 等（ 字段名对齐协议）。与审批的差异：
        不提取 ``callback_token`` / ``ticket_sn`` / ``tool_name``
        （ask_user_question 无工单）。

        Args:
            interrupt_id: interrupt id。
            interrupt: interrupt 对象或 dict。
            **kwargs: 可包含 ``graph_thread_id``。
        """
        graph_thread_id = kwargs.get("graph_thread_id")
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

    @staticmethod
    def is_ask_user_resume(resume: Any) -> bool:
        """判断 resume 是否为 ask_user_question 类型。

        ask_user_question 的 resume payload 含 ``answers`` 字段；
        approval 的 payload 是 ``{approved: bool}``，不含 answers。
        兼容 list / dict 两种 resume 形态（_stream 归一化前可能为 dict）。
        """
        item = resume[0] if isinstance(resume, list) and resume else resume
        if not isinstance(item, dict):
            return False
        payload = item.get("payload")
        return isinstance(payload, dict) and "answers" in payload

    @staticmethod
    def validate_resume_consistency(resume: Any, interrupt: Any) -> None:
        """校验 resume 与 chat_history 末尾 interrupt 的一致性。

        ask_user_question resume 必须对应一条 pending 的末尾 INTERRUPT 记录，
        且 id 一致、tool_call_id 必存在（无 tool_call_id 说明脏数据写入）：

        - ``interrupt`` 不为 None 且 ``role == PromptRole.INTERRUPT.value``
          （必须是 chat_history 的最后一条，避免已回答的 interrupt 被二次回答）
        - ``interrupt.content`` 解析后 ``outcome.interrupts`` 仅一个元素
        - 元素 ``id`` == resume 的 ``interruptId``
        - 元素 ``metadata.status`` == pending
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
        if not isinstance(interrupts, list) or len(interrupts) != 1:
            raise AgentException(
                message=f"ask_user resume 期望 outcome.interrupts 仅一个元素，实际 {len(interrupts) if isinstance(interrupts, list) else '非 list'}"
            )
        first = interrupts[0] if isinstance(interrupts[0], dict) else {}
        if first.get("id") != resume_id:
            raise AgentException(
                message=f"ask_user resume interruptId={resume_id} 与 chat_history interrupt id={first.get('id')} 不一致"
            )
        status = (first.get("metadata") or {}).get("status")
        if status != InterruptStatus.PENDING.value:
            raise AgentException(message=f"ask_user resume 期望 interrupt status=pending，实际 status={status}")

        builtin = getattr(interrupt, "builtin_property", None) or {}
        if not builtin.get("tool_call_id"):
            raise AgentException(message="ask_user resume 的 interrupt 缺少 tool_call_id，存在脏数据")

    @property
    def outcome_builder(self) -> type:
        """返回 ``AskUserQuestionOutcomeBuilder``，用于构造续流首帧
        ``RUN_FINISHED`` 的 ``(outcome, result)``。"""
        return AskUserQuestionOutcomeBuilder


# ---------------------------------------------------------------------- #
# 协议层纯函数（Phase 14.1 — 从 services/nodes 层下沉的协议解析逻辑）
# ---------------------------------------------------------------------- #


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

    Returns:
        匹配的 interrupt value（dict）列表。
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
            if isinstance(value, dict) and value.get("reason") == ASK_USER_QUESTION_REASON:
                interrupts.append(value)
    return interrupts


def parse_resume_answers(resume_value: Any) -> Any:
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
    "extract_message_id",
    "build_skipped_answers",
    "build_updated_builtin_property",
    "filter_ask_user_question_interrupts",
    "parse_resume_answers",
]
