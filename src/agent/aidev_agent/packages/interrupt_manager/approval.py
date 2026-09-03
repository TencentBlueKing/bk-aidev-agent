# -*- coding: utf-8 -*-
"""审批续流（tool approval interrupt resume）相关的 AG-UI 协议适配 + 抛出层策略辅助。

本模块由原 ag_ui 侧 approval 实现（审批三态字面量与终态形态构造，shim 已随 43-07
移除）与 ``core/nodes/tool/approval_wrapper.py``（抛出层策略辅助：``ApprovalTarget`` /
``is_approval_configured``）整块迁移而来（43-03 D-07），是审批相关
**工厂函数与命名空间常量的单一来源**，被以下调用方共享，确保 SSE 输出与
DB 落库结构同源：

- ``aidev_agent.core.ag_ui.aidev_agent.AidevAGUIAgent``：续流时的首条
  ``RUN_FINISHED`` 事件构造。
- ``bk-aidev`` 项目侧 ``resource/agent/services/approval.py``（``ToolApprovalResultService``）
  / ``resource/chat/services/user_operation.py``：ITSM 回调与用户主动取消两条
  写库路径的 content 升级写回（``ToolApprovalResultService.write_approval_result``
  内部调用 :meth:`ApprovalOutcomeBuilder.upgrade_content_to_success`）。

模块边界设计：
- ``types.py`` 仅承载纯类型定义（Pydantic / TypedDict / Enum / reason 常量）；
  本模块承载与审批相关的工厂函数与命名空间常量，避免业务逻辑污染类型层。
- 抛出层策略辅助（``is_approval_configured``）与审批目标构造
  （``core/nodes/tool/approval_wrapper.py``）消费；首跑单格式 payload 构造
  已内联进 :meth:`ApprovalHandler._build_first_run_interrupt`（原模块级
  ``_interrupt_payload_from_target`` 收敛）。建单副作用经注入的
  :class:`ItsmTicketCreator` 收敛（D-06/D-01），抛出层与 core 层不再直调 BKAidevApi。

单格式化（D-04/D-16）：首跑 interrupt payload 顶层不再放 ``callbackToken`` /
``ticketSn`` / ``ticket_sn`` 双键，以 ``metadata.ticket``（snake_case 子字段
id/sn/submit_time/url/status/title/approvers）为单一来源。

协议对齐 Pydantic 定义：本模块定义 ``ItsmApprovalTicket`` / ``ItsmApprovalMetadata`` /
``ItsmApprovalInterrupt`` / ``ItsmApprovalPayload`` / ``ItsmApprovalResult`` 五个协议
模型（中断态 interrupt value + 终态扁平化 result 两大形态），镜像
``ask_user_question.py`` 的 ``AskUserQuestion*`` 定位。**其中 ``ItsmApprovalInterrupt`` /
``ItsmApprovalMetadata`` 参与生产构造**（首跑 payload 构造与 enrich 校验），非仅文档：
:meth:`ApprovalHandler._build_first_run_interrupt` 用 ``ItsmApprovalInterrupt`` +
``ItsmApprovalMetadata`` 构造后 ``model_dump(by_alias=True)`` 产出首跑 payload；
:meth:`ApprovalHandler.prepare` 建单成功后经 ``ItsmApprovalMetadata.model_validate``
校验并刷写 enrich 字段后合并写回。

建单平台侧知识收敛：本模块新增 :class:`ItsmTicketCreator`，封装建单所需的全部
平台侧信息（``resource_manager`` 引用 + ``username`` / ``approvers`` +
``session_code``），经鸭子类型注入（对齐 ``ApprovalStateHandler`` 注入模式），
使 :meth:`ApprovalHandler.prepare` 只关心审批语义而非平台调用，与
``resource_manager`` 解耦。

Harness 依赖方向：本模块依赖标准库 / pydantic / langgraph（ToolCallRequest 第三方） /
包内 ``types.py``，不 import core/services/api。
"""

from __future__ import annotations

import copy
import json as _json
import logging
import uuid
from typing import Any, Literal, Optional

from langgraph.prebuilt.tool_node import ToolCallRequest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager.types import CREATE_TICKET_ERROR, TOOL_APPROVAL_REASON

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------- #
# 由于 itsm 审批导致的中断统一使用本格式，Agent 内部遇到需要审批的时候抛出
# ---------------------------------------------------------------------- #
#: 审批状态在 assistant message additional_kwargs 中的存储 key。
TOOL_APPROVAL_STATE_KEY = "tool_approval"


class ApprovalTarget(BaseModel):
    """审批目标抽象（Pydantic 承载，alias 协议名对齐 AG-UI）。

    以 alias 协议名（toolCallId / toolName / toolCode / toolArgs）承载审批目标的
    协议形态，同时保留原名（target_id / target_name / ...）供内部属性访问。
    ``populate_by_name=True`` 保证既有 kwargs 构造（target_id=...）与别名构造
    （toolCallId=...）双通道可用。
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)
    target_type: str = Field(default="tool")
    target_id: str = Field(default="", alias="toolCallId")
    target_name: str = Field(default="", alias="toolName")
    target_code: str = Field(default="", alias="toolCode")
    args: dict[str, Any] = Field(default_factory=dict, alias="toolArgs")
    approval: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------- #
# 审批消息落地统一模型
# ---------------------------------------------------------------------- #


ApproveResultLiteral = Literal["approved", "rejected", "cancelled"]


class InvalidApprovalInterruptError(ValueError):
    """审批 interrupt value 协议/程序错误（fail fast，绝不静默兜底或虚构）。

    prepare 收到非 target 形态 / 校验失败的 value 时抛出——生产中 approval
    中断 value 恒为策略直抛的 ApprovalTarget 形态（checkpoint 保存原始抛出值），
    其他形态属程序错误：静默拦截或虚构 ApprovalTarget 建单（空审批人工单）
    都是生产事故，必须抛出让上层显式失败。
    """


class ApproveResult:
    """审批结果三态命名空间。

    使用类属性而非 Enum 是为了让字面量值直接是字符串（兼容 DB / JSON 存储），
    同时通过 ``ALL`` 集合提供集中校验入口。
    """

    APPROVED: ApproveResultLiteral = "approved"
    REJECTED: ApproveResultLiteral = "rejected"
    CANCELLED: ApproveResultLiteral = "cancelled"
    ALL: frozenset = frozenset({"approved", "rejected", "cancelled"})


class ItsmApprovalTicket(BaseModel):
    """ITSM 工单子结构（metadata.ticket，snake_case 单一事实来源，模块 docstring）。

    字段对齐模块 docstring：id / sn / submit_time / url / status / title / approvers。
    ``id`` 为平台建单返回的 ITSM 工单数字 id（真实抓包 harness/ref-interrupt/stream3
    等均有；亦嵌于 ``url`` 的 ``ticketId`` 参数）。全字段有默认值以兼容首跑空
    ticket（``ticket={}``）。
    """

    id: str = Field(default="")
    sn: str = Field(default="")
    submit_time: str = Field(default="")
    url: str = Field(default="")
    status: str = Field(default="")
    title: str = Field(default="")
    approvers: list[str] = Field(default_factory=list)


class ItsmApprovalMetadata(BaseModel):
    """approval interrupt 的 metadata 块（对应 AskUserQuestionMetadata）。

    status 初始 ``"pending"``，终态被 ApprovalOutcomeBuilder 刷写为
    ApproveResultLiteral 三态（approved/rejected/cancelled）。
    """

    type: Literal["tool_approval"] = Field(default="tool_approval")
    status: Literal["pending", "approved", "rejected", "cancelled"] = Field(default="pending")
    callbackToken: str = Field(default="")
    ticketSn: str = Field(default="")
    toolName: str = Field(default="")
    toolCode: str = Field(default="")
    toolArgs: dict[str, Any] = Field(default_factory=dict)
    ticket: ItsmApprovalTicket = Field(default_factory=ItsmApprovalTicket)
    create_ticket_error: bool = Field(default=False)


class ItsmApprovalInterrupt(BaseModel):
    """approval 单格式化 interrupt value（D-04/D-16，顶层协议字段完整记录）。

    顶层携带 type/toolName/toolCode/toolArgs 协议字段（ask_user 顶层无专属字段
    故无对应层），approval 特有；reason 默认 TOOL_APPROVAL_REASON。
    """

    id: str
    reason: str = Field(default=TOOL_APPROVAL_REASON)
    toolCallId: str = Field(default="")
    message: str = Field(default="")
    type: Literal["tool_approval"] = Field(default="tool_approval")
    toolName: str = Field(default="")
    toolCode: str = Field(default="")
    toolArgs: dict[str, Any] = Field(default_factory=dict)
    metadata: ItsmApprovalMetadata = Field(default_factory=ItsmApprovalMetadata)


class ItsmApprovalPayload(BaseModel):
    """终态 ``result.payload`` 容器（真实形态仅含 metadata 整体透传）。

    对齐 ``ApprovalOutcomeBuilder._build_result_from_first_interrupt`` 的
    ``payload`` 构造与真实抓包（harness/ref-interrupt/stream3 的 ``result.payload``
    仅含 ``metadata`` 键）。注意与 resume 的 ``ResumeItem.payload``（``{"approved":
    bool}``）不同物，勿混用。
    """

    metadata: ItsmApprovalMetadata = Field(default_factory=ItsmApprovalMetadata)


class ItsmApprovalResult(BaseModel):
    """审批续流终态的扁平化 result（``interrupts[0]`` 的扁平化版本）。

    对应 :meth:`ApprovalOutcomeBuilder.upgrade_content_to_success` 写入 content
    的 ``result`` 字段与 :meth:`ApprovalOutcomeBuilder.build_run_finished_payload`
    返回的 ``(outcome, result)`` 中的 result：``id`` / ``interruptId`` 同值
    （供前端按中断 id 关联续流结果），``payload.metadata`` 为 interrupts[0]
    的 metadata 整体透传（已刷写终态 status）。真实抓包形态见
    harness/ref-interrupt/stream3 的 ``result`` 块。
    """

    id: str = Field(default="")
    interruptId: str = Field(default="")
    reason: str = Field(default=TOOL_APPROVAL_REASON)
    message: str = Field(default="")
    toolCallId: str = Field(default="")
    payload: ItsmApprovalPayload = Field(default_factory=ItsmApprovalPayload)


class ApprovalOutcomeBuilder:
    """审批续流终态形态构造器。

    将原始的"中断态" content（``outcome.type == "interrupt"``）升级为"成功态"
    （``outcome.type == "success"`` + 顶层 ``result`` 字段），供：

    - DB ``ChatSessionContent.content`` 字段回写
    - 续流 SSE 首条 ``RUN_FINISHED`` 事件的 ``outcome`` / ``result`` 字段

    目标 content 形态::

        {
            "outcome": {
                "type": "success",
                "interrupts": [
                    {
                        ...,
                        "metadata": {
                            "status": <approve_result>,
                            "ticket": {"status": <approve_result>, ...},
                            ...
                        }
                    }
                ]
            },
            "result": {
                "id": ..., "interruptId": <与 id 同值>,
                "reason": ..., "message": ..., "toolCallId": ...,
                "payload": {"metadata": <interrupts[0].metadata 整体透传>}
            }
        }
    """

    # ------------------------------------------------------------------ #
    # 内部 helper
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_status_to_interrupt_metadata(
        interrupts: list[dict],
        approve_result: ApproveResultLiteral,
    ) -> None:
        """就地刷写每条 interrupt 的 ``metadata.status`` 与
        ``metadata.ticket.status`` 字段。

        ticket 子结构可能不存在；不存在时仅刷写顶层 status，不强行创建。
        """
        for item in interrupts:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
                item["metadata"] = metadata
            metadata["status"] = approve_result
            ticket = metadata.get("ticket")
            if isinstance(ticket, dict):
                ticket["status"] = approve_result

    @staticmethod
    def _build_result_from_first_interrupt(first_interrupt: dict) -> dict:
        """将 ``interrupts[0]`` 扁平化为顶层 ``result`` 对象。

        规则：
        - 顶层保留 ``id`` / ``interruptId`` / ``reason`` / ``message`` /
          ``toolCallId`` 字段；其中 ``interruptId`` 与 ``id`` 同值，供前端按
          中断 id 关联续流结果。
        - 原 ``metadata`` 整体（不裁剪）移入 ``payload.metadata``
        """
        if not isinstance(first_interrupt, dict):
            return {}
        metadata = first_interrupt.get("metadata")
        interrupt_id = first_interrupt.get("id")
        return {
            "id": interrupt_id,
            "interruptId": interrupt_id,
            "reason": first_interrupt.get("reason"),
            "message": first_interrupt.get("message"),
            "toolCallId": first_interrupt.get("toolCallId"),
            "payload": {"metadata": metadata if isinstance(metadata, dict) else {}},
        }

    # ------------------------------------------------------------------ #
    # 对外 API
    # ------------------------------------------------------------------ #

    @classmethod
    def upgrade_content_to_success(
        cls,
        content: Any,
        approve_result: ApproveResultLiteral,
    ) -> dict | None:
        """将审批中断 content 升级为"终态形态"。

        Args:
            content: 原始 content，可以是 dict 或 JSON 字符串。
            approve_result: 三态审批结果。

        Returns:
            改写后的 content dict（深拷贝、不污染入参）。如果 content 结构
            不识别（非 dict / 不含 outcome / outcome.type 既不是 interrupt
            也不是 success / interrupts 为空），返回 ``None``，告知调用方
            无需把 content 字段回写 DB。

        幂等性：对已是 ``success`` 形态的 content 再次传入，会按当前
        ``approve_result`` 重新刷写 ``metadata.status`` / ``ticket.status``
        与顶层 ``result`` 字段。
        """
        if content is None:
            return None
        if isinstance(content, str):
            try:
                content = _json.loads(content)
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
        cls._apply_status_to_interrupt_metadata(new_interrupts, approve_result)
        new_content["result"] = cls._build_result_from_first_interrupt(new_interrupts[0])
        return new_content

    @classmethod
    def build_run_finished_payload(
        cls,
        interrupts: list[dict],
        approve_result: ApproveResultLiteral,
    ) -> tuple[dict, dict]:
        """构造续流首条 ``RUN_FINISHED`` 事件需要的 ``(outcome, result)`` 字典对。

        与 :meth:`upgrade_content_to_success` 保持完全一致的形态，差异仅在于
        本方法接受 ``interrupts`` 列表（来自
        ``ApprovalStateHandler.fetch_approve_result`` 的返回），返回 tuple
        便于事件构造。

        Args:
            interrupts: 中断列表（dict 形式），允许已包含终态 status 的快照。
            approve_result: 三态字符串，会再次刷写 metadata.status /
                ticket.status，保证一致。

        Returns:
            ``(outcome, result)`` —— ``outcome.type == "success"``；
            ``result`` 为 ``interrupts[0]`` 的扁平化版本。
        """
        safe_interrupts = copy.deepcopy(interrupts) if interrupts else []
        cls._apply_status_to_interrupt_metadata(safe_interrupts, approve_result)
        outcome = {
            "type": "success",
            "interrupts": safe_interrupts,
        }
        result = cls._build_result_from_first_interrupt(safe_interrupts[0]) if safe_interrupts else {}
        return outcome, result


def _tool_call_id(request: ToolCallRequest) -> str:
    return request.tool_call.get("id") or ""


def _tool_name(request: ToolCallRequest) -> str:
    tool = getattr(request, "tool", None)
    return getattr(tool, "name", "") or request.tool_call.get("name") or ""


def _tool_metadata(tool: Any | None) -> dict[str, Any]:
    metadata = getattr(tool, "metadata", None) or {}
    return metadata if isinstance(metadata, dict) else {}


def _approval_config(tool: Any | None) -> dict[str, Any] | None:
    metadata = _tool_metadata(tool)
    approval = metadata.get("approval") or {}
    if not isinstance(approval, dict) or not approval:
        return None
    if approval.get("enabled") is True or approval.get("required") is True or approval.get("approval_enabled") is True:
        return approval

    target = approval.get("target")
    has_target_identity = isinstance(target, dict) and any(
        target.get(key) for key in ("type", "id", "code", "mcp_name", "display_name")
    )
    has_direct_identity = any(
        approval.get(key) for key in ("tool_type", "tool_code", "tool_name", "mcp_code", "approvers")
    )
    return approval if has_target_identity or has_direct_identity else None


def is_approval_configured(tool: Any | None) -> bool:
    return _approval_config(tool) is not None


# ---------------------------------------------------------------------- #
# 审批状态读处理器（迁移自 services/agent/approval.py，43-05 D-11）
# ---------------------------------------------------------------------- #


class ApprovalStateHandler:
    """审批状态读处理器（resource_manager 注入，D-06 收敛）。

    由 ``services/agent/approval.py`` 整块迁移而来（43-05），封装审批中断
    记录读取、状态规范化、以及 LangGraph 续流 payload 适配。数据访问统一经
    :meth:`_get_client` 获取客户端：基类返回构造注入的 ``resource_manager``
    （鸭子类型，mock 友好，对齐 D-06：interrupt_manager 三层通过注入 rm 实例
    调用平台 API）；旧格式兼容层（``services/agent/approval.py``）覆写
    ``_get_client`` 直连 ``BKAidevApi.get_client().api``。

    ``resource_manager`` 需提供以下方法（resource_manager/base.py 均已提供）：
    ``is_resume_session(session_code) -> bool`` / ``get_chat_session_contents(session_code)
    -> list[dict]`` / ``retrieve_chat_session(session_code) -> dict``。

    纯逻辑静态方法（``_extract_interrupts_from_content`` / ``_extract_builtin_property`` /
    ``_extract_graph_thread_id_from_interrupt_record`` / ``hydrate_resume_payload``）原样保留。

    Attributes:
        resource_manager: 注入的资源管理器实例（鸭子类型，mock 友好）。
    """

    def __init__(self, resource_manager: object | None = None) -> None:
        self.resource_manager = resource_manager

    def _get_client(self) -> object:
        """返回数据访问客户端（鸭子类型扩展点）。

        基类返回构造注入的 ``resource_manager``；未注入时抛明确错误供上层
        定位（原 ``_require_rm`` 语义收编）。旧格式兼容层（services/agent/approval.py）
        覆写本方法直连平台 API 客户端，绕过 resource_manager。

        Raises:
            RuntimeError: 基类路径未注入 resource_manager 且调用了需要数据访问的方法。
        """
        if self.resource_manager is None:
            raise RuntimeError(
                "ApprovalStateHandler 需要 resource_manager，但未注入。"
                "请在构造时传入 resource_manager 实例；旧格式直连 BKAidevApi 请使用"
                " services/agent/approval.ApprovalStateHandler（覆写 _get_client）。"
            )
        return self.resource_manager

    def check_resume(self, session_code: str) -> bool:
        """检查会话是否需要续流（审批回调后 ``is_resume_session`` 返回 True）。

        Returns:
            True: 需要续流（审批已回调）；False: 尚未回调或查询失败。
        """
        try:
            rm = self._get_client()
            data = rm.is_resume_session(session_code)
            logger.info("[Approval] check_resume: session_code=%s, is_resume=%s", session_code, data)
            return bool(data)
        except Exception:
            logger.exception("[Approval] check_resume failed: session_code=%s", session_code)
            return False

    def fetch_approve_result(self, session_code: str) -> Optional[dict]:
        """从最新一条 ``role=interrupt`` 记录读取审批结果及 ``interrupts`` 内容。

        ``approve_result`` 真实存储在 ``property.builtin_property``；部分 API 返回会把
        ``builtin_property`` 平铺到记录顶层。读取按"嵌套优先 + 顶层兜底"处理。

        Returns:
            ``{"approve_result": ApproveResultLiteral, "interrupts": list, "id": int|None}``。
            未找到 interrupt 记录或记录尚未写入审批结果时返回 None。
        """
        latest = self._get_latest_interrupt_record(session_code)
        if latest is None:
            logger.warning("[Approval] fetch_approve_result: 无 interrupt 记录, session_code=%s", session_code)
            return None
        builtin_property = self._extract_builtin_property(latest)
        raw_approve_result = builtin_property.get("approve_result")
        approve_result: Optional[ApproveResultLiteral] = (
            raw_approve_result if raw_approve_result in ApproveResult.ALL else None
        )
        if approve_result is None:
            logger.warning(
                "[Approval] fetch_approve_result: interrupt 记录无有效 approve_result, session_code=%s, raw=%r",
                session_code,
                raw_approve_result,
            )
            return None
        interrupts = self._extract_interrupts_from_content(latest.get("content"))
        logger.info(
            "[Approval] fetch_approve_result: session_code=%s, approve_result=%s",
            session_code,
            approve_result,
        )
        return {
            "approve_result": approve_result,
            "interrupts": interrupts,
            "id": latest.get("id"),
        }

    def query_approval_info(self, session_code: str) -> Optional[dict]:
        """续流前置查询：获取审批结果及 interrupts 内容。

        采用「DB 优先」策略：

        1. 直接从 interrupt 记录读取 ``approve_result``，命中三态字符串即返回，
           无需依赖 platform ``is_resume_session`` 接口。
        2. DB 未写入时回退查询 :meth:`check_resume`，True 则再次 :meth:`fetch_approve_result`。

        Returns:
            ``{"approve_result": ApproveResultLiteral, "interrupts": list, "id": int|None}``
            或 None（尚未回调）。
        """
        info = self.fetch_approve_result(session_code)
        if info is not None:
            return info
        if not self.check_resume(session_code):
            return None
        return self.fetch_approve_result(session_code)

    def query_approval_info_for_interrupt(self, session_code: str, pending_interrupt: Any) -> Optional[dict]:
        """按当前 pending interrupt 定位其**专属**记录并读取审批结果（串行多中断门禁）。

        与 :meth:`query_approval_info`（会话级「最新一条记录」）的差异：串行语义下
        会话存在多条 interrupt 记录（每中断一条），最新一条可能是**其他**中断的
        终态记录（如前序审批已回调）——用它校验当前 pending 会误放行（UAT 回归：
        每次 resume 都拉起图）。本方法按 pending 的 ``toolCallId`` 在全部
        interrupt 记录中（从最新往旧）定位匹配记录，读**它**的 approve_result。

        Args:
            session_code: 会话 code。
            pending_interrupt: 当前被门禁的 pending interrupt value dict
                （含 ``toolCallId``）。

        Returns:
            ``{"approve_result": ApproveResultLiteral, "interrupts": list, "id": int|None}``
            或 None（该 interrupt 无记录 / 记录未回调终态 → not_ready）。
        """
        if not isinstance(pending_interrupt, dict):
            return self.query_approval_info(session_code)
        pending_call_id = pending_interrupt.get("toolCallId")
        if not pending_call_id:
            return self.query_approval_info(session_code)
        records = self._list_interrupt_records(session_code)
        for record in reversed(records):
            builtin = self._extract_builtin_property(record)
            record_call_id = builtin.get("tool_call_id")
            if record_call_id != pending_call_id:
                # 次选：content 内 interrupts 元素的 toolCallId（builtin 缺失时）
                if record_call_id:
                    continue
                elements = self._extract_interrupts_from_content(record.get("content"))
                if not any(isinstance(item, dict) and item.get("toolCallId") == pending_call_id for item in elements):
                    continue
            approve_result = builtin.get("approve_result")
            if approve_result not in ApproveResult.ALL:
                logger.info(
                    "[Approval] query_approval_info_for_interrupt: 当前 pending 记录未回调终态, "
                    "session_code=%s, tool_call_id=%s, raw=%r",
                    session_code,
                    pending_call_id,
                    approve_result,
                )
                return None
            interrupts = self._extract_interrupts_from_content(record.get("content"))
            logger.info(
                "[Approval] query_approval_info_for_interrupt: session_code=%s, tool_call_id=%s, approve_result=%s",
                session_code,
                pending_call_id,
                approve_result,
            )
            return {"approve_result": approve_result, "interrupts": interrupts, "id": record.get("id")}
        logger.info(
            "[Approval] query_approval_info_for_interrupt: 无该 pending 的记录, session_code=%s, tool_call_id=%s",
            session_code,
            pending_call_id,
        )
        return None

    def get_pending_interrupt_context(self, session_code: str) -> dict[str, Any]:
        """从 ``session_property.pending_interrupt`` 读取待恢复中断上下文。"""
        try:
            rm = self._get_client()
            data = rm.retrieve_chat_session(session_code)
            session_property = data.get("session_property", {}) if isinstance(data, dict) else {}
            pending_interrupt = (
                session_property.get("pending_interrupt", {}) if isinstance(session_property, dict) else {}
            )
            return pending_interrupt if isinstance(pending_interrupt, dict) else {}
        except Exception:
            logger.exception("[Approval] get_pending_interrupt_context failed: session_code=%s", session_code)
            return {}

    def get_graph_thread_id_from_interrupt_content(self, session_code: str) -> Optional[str]:
        """从当前会话最新一条 ``role=interrupt`` 记录获取 ``graph_thread_id``。

        优先读取 ``property.builtin_property.graph_thread_id``；若查询接口已将
        ``builtin_property`` 平铺到一级字段，则回退读取顶层 ``graph_thread_id``。
        """
        latest = self._get_latest_interrupt_record(session_code)
        if latest is None:
            logger.info(
                "[Approval] get_graph_thread_id_from_interrupt_content: 无 interrupt 记录, session_code=%s",
                session_code,
            )
            return None
        graph_thread_id = self._extract_graph_thread_id_from_interrupt_record(latest)
        logger.info(
            "[Approval] get_graph_thread_id_from_interrupt_content: graph_thread_id=%s, session_code=%s",
            graph_thread_id,
            session_code,
        )
        return graph_thread_id

    def _list_interrupt_records(self, session_code: str) -> list[dict]:
        """获取该 session 全部 ``role=interrupt`` 记录列表（按平台返回顺序）。

        注意：content API 不支持 role 过滤，返回该 session 全部记录，
        需要在客户端自行过滤 ``role=interrupt`` 的记录。
        """
        try:
            rm = self._get_client()
            contents = rm.get_chat_session_contents(session_code)
        except Exception:
            logger.exception("[Approval] _list_interrupt_records failed: session_code=%s", session_code)
            return []
        if not contents or not isinstance(contents, list):
            return []
        return [c for c in contents if isinstance(c, dict) and c.get("role") == PromptRole.INTERRUPT.value]

    def _get_latest_interrupt_record(self, session_code: str) -> Optional[dict]:
        """获取该 session 最新一条 ``role=interrupt`` 记录原始 dict。"""
        interrupts = self._list_interrupt_records(session_code)
        if not interrupts:
            return None
        return interrupts[-1]

    @staticmethod
    def _extract_interrupts_from_content(content: Any) -> list:
        """从 interrupt 记录的 ``content`` 字段抽取 interrupts 数组。

        兼容两种形态：

        - 中断未完成：``{"outcome": {"type": "interrupt", "interrupts": [...]}}``
        - 中断已完成：``{"outcome": {"type": "success", "interrupts": [...]}, "result": ...}``
        """
        if content is None:
            return []
        if isinstance(content, str):
            try:
                content = _json.loads(content)
            except (TypeError, ValueError):
                return []
        if not isinstance(content, dict):
            return []
        outcome = content.get("outcome")
        if not isinstance(outcome, dict) or outcome.get("type") not in ("interrupt", "success"):
            return []
        interrupts = outcome.get("interrupts")
        return interrupts if isinstance(interrupts, list) else []

    @staticmethod
    def _extract_builtin_property(record: dict) -> dict:
        """从单条 interrupt 记录提取 ``builtin_property``，兼容嵌套与平铺两种返回结构。

        平台 ORM 真实存储位置为 ``property.builtin_property``；content API
        在某些版本会把 ``builtin_property`` 平铺到记录顶层。两种结构都需要兼容。
        """
        if not isinstance(record, dict):
            return {}
        property_obj = record.get("property")
        if isinstance(property_obj, dict):
            builtin_property = property_obj.get("builtin_property")
            if isinstance(builtin_property, dict):
                return builtin_property
        # 平铺到顶层时无独立 builtin_property 容器，直接以记录本身作为兜底容器
        return record

    @staticmethod
    def _extract_graph_thread_id_from_interrupt_record(record: dict) -> Optional[str]:
        """从单条 interrupt 会话内容记录提取 ``graph_thread_id``。"""
        builtin_property = ApprovalStateHandler._extract_builtin_property(record)
        graph_thread_id = builtin_property.get("graph_thread_id")
        if graph_thread_id:
            return graph_thread_id
        # 极端兜底：嵌套与顶层都没有时，尝试记录顶层
        return record.get("graph_thread_id") or None

    @staticmethod
    def _is_truthy_approval(value: Any) -> bool:
        """判断 ``approve_result`` 是否表示「通过」。

        cancelled / rejected 在 LangGraph 续流时与 rejected 等价（走未通过分支）。
        """
        return value == ApproveResult.APPROVED

    @staticmethod
    def hydrate_resume_payload(
        resume_items: Any,
        approve_result: Optional[ApproveResultLiteral],
    ) -> None:
        """根据审批结果就地填充 ``resume_items`` 的 ``status`` / ``payload.approved`` 字段。

        LangGraph 续流层语义：

        - approved → ``status="resolved", payload.approved=True``
        - rejected / cancelled → ``status="cancelled", payload.approved=False``

        兼容性：``resume_items`` 同时支持 ``list[dict|object]`` 与 ``dict``（单条）
        两种形态。非法或空入参直接返回，不抛异常。
        """
        if not resume_items or approve_result is None:
            return

        # 单条 dict 归一为 [dict]，仅对原对象就地填充
        if isinstance(resume_items, dict):
            iterable: list = [resume_items]
        elif isinstance(resume_items, list):
            iterable = resume_items
        else:
            # 未知形态（如字符串等）不处理，避免 setattr 异常
            return

        approved = ApprovalStateHandler._is_truthy_approval(approve_result)
        resolved_status = "resolved" if approved else "cancelled"
        for item in iterable:
            if isinstance(item, dict):
                item["status"] = item.get("status") or resolved_status
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                payload["approved"] = approved
                item["payload"] = payload
                continue
            # 非 dict 且非具备属性赋值能力的对象（如 str）直接跳过，避免 AttributeError
            if not hasattr(item, "__dict__") and not hasattr(type(item), "__slots__"):
                continue
            try:
                payload = getattr(item, "payload", None) if isinstance(getattr(item, "payload", None), dict) else {}
                payload["approved"] = approved
                setattr(item, "payload", payload)
                if not getattr(item, "status", None):
                    setattr(item, "status", resolved_status)
            except (AttributeError, TypeError):
                # 不可写属性（如内建不可变对象）跳过，保持鲁棒性
                continue


# ---------------------------------------------------------------------- #
# 建单平台侧封装（D-06/D-01 收敛，鸭子类型注入）
# ---------------------------------------------------------------------- #


class ItsmTicketCreator:
    """封装平台侧建单所需全部信息（rm 引用 + username/approvers + session_code），鸭子类型注入。

    将建单平台侧知识（``resource_manager`` 引用 + ``username`` / ``approvers`` +
    ``session_code``）收敛进本类，使 :meth:`ApprovalHandler.prepare` 与
    ``resource_manager`` 解耦——prepare 只关心审批语义，经 ``ticket_creator``
    （上游注入）间接完成建单。对齐 ``ApprovalStateHandler`` 的注入模式；
    harness 红线：packages 层不 import core/services/api。

    Args:
        resource_manager: 鸭子类型 rm（需 ``create_tool_approval(payload, *, username=...)``）。
        username: 建单请求身份（仅注入 ``X-BKAIDEV-USER`` 头）；审批人取
            ``target.approval.approvers``（工具审批配置），绝非此值——提单人
            不可成为审批人（禁止自审批）。
        session_code: 静态会话码（建单 ``session_code`` 字段）。
    """

    def __init__(
        self,
        resource_manager: object,
        *,
        username: str | None = None,
        session_code: str | None = None,
    ) -> None:
        self._resource_manager = resource_manager
        self._username = username
        self._session_code = session_code

    def __call__(self, target: Any, **ctx: Any) -> dict:
        """组装完整平台建单 payload 并调 ``resource_manager.create_tool_approval``。

        Args:
            target: :class:`ApprovalTarget`（审批目标，鸭子类型访问其属性）。建单
                字段**直接取 target**（target_id/target_name/target_code/target_type/
                args），不经中间 dict 转换——历史 bug：经落库 payload 反取字段
                （_extract_tool_info），``target.approval`` 在首跑单格式构造时丢失
                → approvers 错取 username/空。配置审批人取
                ``target.approval.approvers``（工具审批配置的 ITSM 审批人，绝非
                提单人自己——UAT 严重错误裁定；username 仅注入 X-BKAIDEV-USER 头）。
            **ctx: 运行时 ctx（``thread_id`` / ``run_id``；``run_id`` 缺省回落
                ``target.target_id``，保持现行为）。

        Returns:
            建单结果 dict（含 ``ticket`` / ``callback_token``）。payload 字段集 =
            旧 ``ApprovalHandler._build_approval_payload`` 整体搬移。
        """
        tool_call_id = str(getattr(target, "target_id", "") or "")
        tool_name = str(getattr(target, "target_name", "") or "")
        tool_code = str(getattr(target, "target_code", "") or tool_name)
        tool_type = str(getattr(target, "target_type", "") or "tool")
        tool_args = getattr(target, "args", None)
        if not isinstance(tool_args, dict):
            tool_args = {}
        approval_cfg = getattr(target, "approval", None)
        approval_cfg = approval_cfg if isinstance(approval_cfg, dict) else {}
        approvers = [str(a) for a in approval_cfg.get("approvers") or [] if a]
        run_id = str(ctx.get("run_id") or "") or tool_call_id
        payload: dict[str, Any] = {
            "thread_id": str(ctx.get("thread_id") or ""),
            "session_code": self._session_code or "",
            "run_id": run_id,
            "tool_call_id": tool_call_id,
            "tool_type": tool_type,
            "tool_name": tool_name,
            "tool_code": tool_code,
            "mcp_name": str(approval_cfg.get("mcp_code") or ""),
            "tool_args": tool_args,
            "approvers": approvers,
            "ticket_title": f"执行「{tool_name}」需要审批" if tool_name else "执行工具需要审批",
        }
        return self._resource_manager.create_tool_approval(payload, username=self._username)


# ---------------------------------------------------------------------- #
# 流结束 handler（D-09/D-01/D-10）
# ---------------------------------------------------------------------- #


def extract_builtin_property(
    interrupt_id: str,
    interrupt: Any,
    graph_thread_id: str | None = None,
) -> dict[str, Any]:
    """从审批 interrupt 提取落库用 ``builtin_property`` 字段集（D-02 模块级纯函数）。

    由 ``ApprovalHandler.extract_builtin_property`` 提出为模块级纯函数（方法体零
    ``self`` 引用，逐行不变）。收编 ``base.py handle_run_finished`` 原 approval 40
    行内联构造（base.py:659-674），字段集与原内联段完全一致：``message_id`` /
    ``type`` / ``interrupt_id`` / ``reason`` / ``tool_call_id`` / ``tool_name`` /
    ``tool_args`` / ``callback_token`` / ``ticket_sn`` / ``graph_thread_id``。

    Args:
        interrupt_id: interrupt id。
        interrupt: interrupt 对象或 dict（序列化后的 single-format payload）。
        graph_thread_id: 图线程 id（缺省时由实现兜底）。

    Returns:
        落库用的 ``builtin_property`` dict。
    """
    serialized = interrupt.model_dump(by_alias=True) if hasattr(interrupt, "model_dump") else interrupt
    if not isinstance(serialized, dict):
        serialized = {}
    metadata = serialized.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    ticket = metadata.get("ticket")
    ticket = ticket if isinstance(ticket, dict) else {}
    # 工具入参：优先取 metadata.toolArgs，兜底取顶层 toolArgs
    tool_args = metadata.get("toolArgs")
    if not isinstance(tool_args, dict):
        tool_args = serialized.get("toolArgs")
    if not isinstance(tool_args, dict):
        tool_args = {}
    return {
        "message_id": interrupt_id,
        "type": metadata.get("type") or serialized.get("type") or "tool_approval",
        "interrupt_id": interrupt_id,
        "reason": serialized.get("reason"),
        "tool_call_id": serialized.get("toolCallId") or serialized.get("tool_call_id"),
        "tool_name": metadata.get("toolName") or serialized.get("toolName") or serialized.get("toolName"),
        "tool_args": tool_args,
        "callback_token": metadata.get("callbackToken") or serialized.get("callbackToken"),
        "ticket_sn": ticket.get("sn") or metadata.get("ticketSn") or serialized.get("ticketSn"),
        "graph_thread_id": graph_thread_id or serialized.get("threadId") or serialized.get("thread_id") or "",
    }


class ApprovalHandler:
    """审批的流结束 handler + resume 对偶单元（实现 :class:`InterruptHandler` 契约）。

    作为审批 reason 的**per-reason 对偶单元**，承担两段操作（用户原话
    「ITSM 建单 ↔ 审批检查是一对」）：

    - :meth:`prepare` —— **建单副作用落点（D-01）**：在流结束（首跑）时经注入的
      ``ticket_creator``（如 :class:`ItsmTicketCreator`，封装 ``resource_manager``）
      建 ITSM 工单并 enrich interrupt 的 ``metadata.ticket``。resume 重跑不再建单
      （建单只在首跑触发）。**失败降级**：interrupt 照发 + ``metadata.create_ticket_error``
      标记（D-01/D-15，coordinator gather 阶段视为 rejected 短路），logger.exception
      但**不含完整 callback_token/ticket_sn**（T-43-06-02 mitigate）。
    - :meth:`query_resume_status` —— **resume 只读门禁（D-07/D-08/D-10）**：查 DB
      审批权威记录（经组合持有的 :class:`ApprovalStateHandler`，
      ``query_approval_info`` / ``query_approval_info_for_interrupt``）→ 返回
      对偶单元层契约 dict。**绝不在 resume 侧建单**（D-08，对偶方法分离天然满足，
      query_resume_status 内不注入 ticket_creator）。审批 resume 值以 DB 权威记录
      为准，不信任前端 approved（T-44-01 mitigate）。
    - :meth:`extract_builtin_property` —— 提取落库用字段集（D-10 查表化），
      收编 ``base.py handle_run_finished`` 的 40 行 approval 内联构造，字段集与
      原内联段（base.py:659-674）完全一致。

    ``resource_manager`` 经构造注入（鸭子类型，对齐 D-06），组合持有
    :class:`ApprovalStateHandler` 实例供 query_resume_status 查 DB 权威记录（文件
    组织属 Claude's Discretion，保留 ``ApprovalStateHandler`` 类定义供 base.py 落库
    查表消费，避免破坏现有 import）。

    注意：本类**不注册**到 ``registry._HANDLERS``（由 :mod:`__init__` 的 ``_setup``
    装配，对齐 43-02 预留）；harness 红线 —— 本模块不 import core/services/api，
    ``resource_manager`` 经 :class:`ItsmTicketCreator` / ``ApprovalStateHandler``
    鸭子类型注入（prepare 与 ``resource_manager`` 解耦）。

    Attributes:
        resource_manager: 注入的 resource_manager（鸭子类型，mock 友好）；供
            query_resume_status 查 DB 审批权威记录（D-06）。``None`` 时
            query_resume_status 的 DB 访问方法抛明确错误（resume 侧未装配 RM 属
            装配错误）。
    """

    reason = TOOL_APPROVAL_REASON

    def __init__(
        self,
        resource_manager: object | None = None,
        *,
        ticket_creator: object | None = None,
    ) -> None:
        self.resource_manager = resource_manager
        # U-01：建单依赖由 handler 自持（D-03 后 processor 不再携带 resource_manager /
        # ticket_creator 构造参数）。Plan 02 chat.py 构造时传入 ItsmTicketCreator。
        self._ticket_creator = ticket_creator
        # 组合持有 StateHandler：query_resume_status 的 resume 校验 / DB 权威记录查询复用
        # 既有 ApprovalStateHandler 实现（44-02 对偶单元定型，D-08/D-10）。
        self._state_handler = ApprovalStateHandler(resource_manager=resource_manager)

    def on_resume(self, resume: Any, *, interrupt_messages: Any, **ctx: Any) -> None:
        """审批终态由审批平台回调写 DB（前端直调 user_operation / ITSM 回调），agent 侧纯读。"""
        return None

    def prepare(
        self,
        interrupt: object,
        ticket_creator: object | None = None,
        **ctx: Any,
    ) -> object:
        """流结束建单 + enrich（D-01 副作用落点，只执行一次）。

        interrupt 为 LangGraph ``Interrupt`` 鸭子类型（``.id`` / ``.value``）。
        **就地 enrich ``interrupt.value``**（可整体替换 value，如 target 形态 →
        首跑单格式 payload），**绝不读写 value 内的 id**——记录的 interrupt_id
        一律取 ``getattr(interrupt, "id", None)``（缺省回落
        ``_build_first_run_interrupt`` 的 ``int-approval-`` 前缀生成）。

        Args:
            interrupt: LangGraph ``Interrupt`` 鸭子类型对象（``.id`` / ``.value``）。
            ticket_creator: 建单封装（如 :class:`ItsmTicketCreator`），鸭子类型注入；
                ``None`` → 记 warning 跳过建单副作用、interrupt 照发（D-01 不吞中断）。
            **ctx: 运行时 ctx（``thread_id`` / ``run_id`` 等建单所需字段；透传给
                ``ticket_creator``）。

        Returns:
            同一 interrupt 对象，其 ``value`` 已被就地 enrich。建单成功 → ``metadata``
            补 ``ticket`` / ``ticketSn`` / ``callbackToken``；失败 → 记
            ``metadata.create_ticket_error`` 并原样返回（不吞中断）。非 dict value
            防御性原样返回。
        """
        value = getattr(interrupt, "value", None)
        if not isinstance(value, dict):
            # 协议/程序错误：fail fast（绝不静默兜底——虚构审批数据是生产事故）
            raise InvalidApprovalInterruptError(f"approval interrupt value 非 dict: {type(value).__name__}")
        # target 形态（策略直抛 ApprovalTarget alias + reason）：无 metadata、含 approval。
        # 审批中断 value **必须**为 target 形态（生产路径 checkpoint 保存原始抛出值，
        # approval 配置块随行）——非 target 形态属协议/程序错误，直接抛异常，
        # 绝不虚构 ApprovalTarget 建单（空审批人工单是生产事故）。
        if "metadata" in value or "approval" not in value:
            raise InvalidApprovalInterruptError(
                f"approval interrupt value 非法 target 形态（须含 approval 配置块且无 metadata）: keys={sorted(value.keys())}"
            )
        target: ApprovalTarget | None = None
        try:
            target = ApprovalTarget.model_validate(value)
        except ValidationError as exc:
            raise InvalidApprovalInterruptError(f"approval interrupt value ApprovalTarget 校验失败: {exc}") from exc
        # 生产路径（经 dispatcher）审批记录 id 用 intr.id（LangGraph 真实 id）；
        # _build_first_run_interrupt 缺省回落 int-approval- 前缀。
        interrupt.value = self._build_first_run_interrupt(target, interrupt_id=getattr(interrupt, "id", None))
        value = interrupt.value

        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
        if not isinstance(value.get("metadata"), dict):
            value["metadata"] = metadata

        if ticket_creator is None:
            # U-01（48）：未显式传 ticket_creator 时回落 handler 自持的 _ticket_creator
            # （D-03 后建单依赖由 handler 自持，processor.dispatch_interrupts 不再注入）。
            ticket_creator = self._ticket_creator
        if ticket_creator is None:
            # 未注入 ticket_creator：跳过建单副作用（D-01 语义：不因建单能力缺失吞中断）
            logger.warning(
                "[ApprovalHandler] 未注入 ticket_creator，跳过建单副作用: tool=%s",
                metadata.get("toolName") or value.get("toolName"),
            )
            return interrupt

        # 幂等防重（D-01/D-02 边界落实）：resume 重跑 / 非 resume 重放时，
        # 流结束 prepare 会对 pending interrupt 再次全量执行——若已 enrich 过
        # （ticketSn 存在或 ticket 已含 sn，即真实建单产物）或已标记建单失败
        # （create_ticket_error），直接跳过建单，避免产生重复 ITSM 工单。属
        # D-01「resume 重跑不建单」的轻量语义落实（metadata 防重），非 D-02
        # 拒绝的完整幂等键（tool_call_id 去重）。
        _ticket = metadata.get("ticket")
        _ticket_sn = _ticket.get("sn") if isinstance(_ticket, dict) else ""
        if metadata.get("ticketSn") or _ticket_sn:
            logger.info(
                "[ApprovalHandler] 已建单（ticketSn/ticket 已 enrich），跳过重复建单: tool=%s, tool_call_id=%s",
                metadata.get("toolName") or value.get("toolName"),
                value.get("toolCallId"),
            )
            return interrupt
        if metadata.get(CREATE_TICKET_ERROR):
            logger.info(
                "[ApprovalHandler] 已标记建单失败，跳过重复建单: tool=%s, tool_call_id=%s",
                metadata.get("toolName") or value.get("toolName"),
                value.get("toolCallId"),
            )
            return interrupt

        # 建单直接传 ApprovalTarget（审批配置——含配置审批人——随 target 到达
        # ticket_creator；历史 bug：经落库 payload 反取字段（_extract_tool_info），
        # target.approval 在首跑单格式构造时丢失 → 建单 approvers 错取 username/空）
        try:
            result = ticket_creator(target, **ctx)
        except Exception:
            # 建单失败降级（D-01/D-15）：interrupt 照发 + create_ticket_error 标记
            # 日志脱敏（T-43-06-02）：不含完整 callback_token / ticket_sn
            logger.exception(
                "[ApprovalHandler] 建单失败，interrupt 照发 + create_ticket_error 标记: tool=%s, tool_call_id=%s",
                metadata.get("toolName") or value.get("toolName"),
                value.get("toolCallId"),
            )
            metadata[CREATE_TICKET_ERROR] = True
            return interrupt

        ticket = result.get("ticket") if isinstance(result, dict) else {}
        if not isinstance(ticket, dict):
            ticket = {}
        ticket_sn = str(ticket.get("sn") or "")
        callback_token = result.get("callback_token") if isinstance(result, dict) else ""
        # enrich 经 ItsmApprovalMetadata 模型构造/校验（T-260828-02）：
        # 合并写回而非整体替换，避免 pydantic 默认丢弃未知键造成数据丢失。
        try:
            approved = ItsmApprovalMetadata.model_validate({**metadata, "ticket": ticket})
        except ValidationError:
            logger.warning(
                "[ApprovalHandler] enrich 经 ItsmApprovalMetadata 校验失败，走手写写回: tool=%s",
                metadata.get("toolName") or value.get("toolName"),
            )
            approved = None
        if approved is not None:
            approved.status = "pending"
            if ticket_sn:
                approved.ticketSn = ticket_sn
            if callback_token:
                approved.callbackToken = callback_token
            enriched = approved.model_dump(by_alias=True)
            metadata = {**metadata, **enriched}
        else:
            # 模型校验失败降级：保留既有手写写回语义（不丢数据）
            metadata["status"] = "pending"
            metadata["ticket"] = ticket
            if ticket_sn:
                metadata["ticketSn"] = ticket_sn
            if callback_token:
                metadata["callbackToken"] = callback_token
        # 确保写回的是 interrupt.value 引用的同一 dict 对象
        value["metadata"] = metadata
        interrupt.value = value
        logger.info(
            "[ApprovalHandler] 建单成功: tool=%s, tool_call_id=%s, ticket_sn=%s",
            metadata.get("toolName") or value.get("toolName"),
            value.get("toolCallId"),
            ticket_sn,
        )
        return interrupt

    def query_resume_status(
        self,
        session_code: str,
        pending_interrupt: Any,
        *,
        resource_manager: object | None = None,
    ) -> dict[str, Any]:
        """resume **只读门禁**（D-07）：查 DB 审批权威记录 → 返回对偶单元层契约 dict。

        **对偶单元层契约（返回 dict 字段名固定，与 processor 编排层契约不同）**：
        返回值必须为 dict 且含 ``action`` 键，供 processor 聚合循环编排。字段名
        固定为::

            {
                "action": "approved" | "rejected" | "cancelled" | "not_ready",
                "resume_value": Any | None,   # 经 DB 权威校验后的 resume 值；not_ready 时 None
            }

        ``action`` 取值对应 D-04 终态（approved/rejected/cancelled 均为「上一单
        完成」），``not_ready`` 表示未就绪（processor 侧据此返回 ``{"action":
        "interrupt"}``）。**两层契约映射**：对偶单元层 ``action ∈ {approved,
        rejected, cancelled, not_ready}`` → processor 编排层 ``action ∈ {resume,
        interrupt, rejected}``（见 44-04-PLAN Task 2）。

        **D-08 硬约束**：本方法内**绝不注入 ``ticket_creator`` 建单副作用**（resume
        侧绝不建单，对偶方法分离天然满足）。**T-44-01/T-44-02 mitigate**：resume
        值以 DB 权威记录为准（经 ``query_approval_info_for_interrupt`` 查询，而非
        信任前端 ``approved``）；approve_result 映射到 ``action`` 时不直接采信前端
        resume。

        Args:
            session_code: 会话 code（DB 审批权威记录查询用）。
            pending_interrupt: 当前被门禁的 pending interrupt value dict（含
                ``toolCallId``）。编排层聚合循环恒传。按它定位**专属** DB 记录校验
                终态——会话级「最新一条记录」在串行多中断下会误读其他中断的终态
                导致门禁误放行（UAT 回归：每次 resume 都拉起图）。
            resource_manager: 鸭子注入（``object | None``，packages 层不 import
                services 类型）。processor 聚合循环传 ``self._resource_manager``。
                非 None 且 self._state_handler 未注入 RM 时用其现构造 StateHandler。

        Returns:
            对偶单元层契约 dict（``action`` + ``resume_value``）。``not_ready`` 时
            ``resume_value`` 为 None；就绪时 ``resume_value`` 为 DB 提取的 interrupts
            （LangGraph 续流 resume 值的权威来源）。
        """
        # processor 聚合循环经 get_handler(reason) 查表调用本方法时，注入编排层
        # resource_manager（processor 构造期携带，chat.py 装配点注入）。优先用
        # resource_manager 关键字参数构造 StateHandler 查 DB 权威记录；缺省回落
        # self._state_handler。
        state_handler = self._state_handler
        if resource_manager is not None and state_handler.resource_manager is None:
            state_handler = ApprovalStateHandler(resource_manager=resource_manager)
        if pending_interrupt is not None:
            info = state_handler.query_approval_info_for_interrupt(session_code, pending_interrupt)
        else:
            info = state_handler.query_approval_info(session_code)
        if info is None:
            logger.info(
                "[ApprovalHandler] query_resume_status: 审批未回调（DB 无权威结果），not_ready: session_code=%s",
                session_code,
            )
            return {"action": "not_ready", "resume_value": None}
        approve_result = info.get("approve_result")
        interrupts = info.get("interrupts") or []
        # D-04 终态映射：approved/rejected/cancelled 均为「上一单完成」，not_ready 表示未就绪。
        action = approve_result if approve_result in ApproveResult.ALL else "not_ready"
        logger.info(
            "[ApprovalHandler] query_resume_status: session_code=%s, approve_result=%s",
            session_code,
            approve_result,
        )
        return {"action": action, "resume_value": interrupts}

    def _build_first_run_interrupt(self, target: ApprovalTarget, interrupt_id: str | None = None) -> dict:
        """由 :class:`ApprovalTarget` 构造首跑单格式 payload。

        内联自旧模块级 ``_interrupt_payload_from_target``（quick 260828-gcn 收敛）；
        用 ``ItsmApprovalInterrupt`` / ``ItsmApprovalMetadata`` 模型构造后
        ``model_dump(by_alias=True)`` 得 dict（参与生产构造，非仅文档）。

        Args:
            target: 审批目标。
            interrupt_id: 生产路径（经 dispatcher）注入的 LangGraph 真实 interrupt id；
                缺省（直接调用/测试）回落生成 ``int-approval-{target_id}-{uuid8}``。

        Returns:
            单格式化 interrupt payload dict。生产路径（经 dispatcher）approval 记录
            id 变为真实 interrupt id（用户"记录的 interrupt_id 不错误"的通用要求）。
        """
        tool_args = dict(target.args) if isinstance(target.args, dict) else {}
        # 唯一后缀仅用于缺省回落（直接调用/测试）；生产路径用 dispatcher 注入的真实 id
        interrupt_id_suffix = f"-{uuid.uuid4().hex[:8]}"
        model = ItsmApprovalInterrupt(
            id=interrupt_id if interrupt_id else f"int-approval-{target.target_id}{interrupt_id_suffix}",
            reason=TOOL_APPROVAL_REASON,
            toolCallId=target.target_id,
            message=f"执行「{target.target_name}」前需要人工审批。",
            toolName=target.target_name,
            toolCode=target.target_code,
            toolArgs=tool_args,
            metadata=ItsmApprovalMetadata(
                type="tool_approval",
                status="pending",
                toolName=target.target_name,
                toolCode=target.target_code,
                toolArgs=tool_args,
            ),
        )
        payload = model.model_dump(by_alias=True)
        logger.info(
            "[ToolApproval] _build_first_run_interrupt: tool=%s, payload_keys=%s",
            target.target_name,
            list(payload.keys()),
        )
        return payload


__all__ = [
    "ApproveResultLiteral",
    "ApproveResult",
    "ApprovalOutcomeBuilder",
    "ItsmApprovalInterrupt",
    "ItsmApprovalMetadata",
    "ItsmApprovalPayload",
    "ItsmApprovalResult",
    "ItsmApprovalTicket",
    "TOOL_APPROVAL_STATE_KEY",
    "ApprovalTarget",
    "TOOL_APPROVAL_REASON",
    "is_approval_configured",
    "_approval_config",
    "ApprovalStateHandler",
    "ItsmTicketCreator",
    "ApprovalHandler",
    "extract_builtin_property",
]
