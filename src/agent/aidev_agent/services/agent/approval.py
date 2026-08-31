# -*- coding: utf-8 -*-
"""审批领域处理器。

对外结构：

- :class:`ApproveResult` / :data:`ApproveResultLiteral`：审批结果三态命名空间与字面量
  类型，re-export 自 :mod:`aidev_agent.core.ag_ui.approval`（单一来源）。
- :class:`ApprovalStateHandler`：审批状态读处理器，封装 ``BKAidevApi`` 上的
  interrupt 记录读取、状态规范化、以及 LangGraph 续流 payload 适配。所有调用方
  统一通过实例化此类获取一致的审批状态视图。
"""

import json
import logging
from typing import Any, Optional

from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.core.ag_ui.approval import (
    ApproveResult,
    ApproveResultLiteral,
)
from aidev_agent.enums import PromptRole

logger = logging.getLogger(__name__)


class ApprovalStateHandler:
    """审批状态读处理器。

    封装 ``BKAidevApi`` 上的 interrupt 记录读取、状态规范化逻辑，调用入口（chat
    续流 / approval_resume 后台轮询）通过同一处理器获得一致的审批状态视图。

    无队列状态，方法独立可调用；保留 ``username`` 是为了后续读操作可能透传
    ``X-BKAIDEV-USER`` 标识操作者，当前读路径不消费此字段。

    Attributes:
        username: 操作者用户名，预留 header 透传位（读操作目前不使用）。
    """

    def __init__(self, *, username: str = "") -> None:
        self.username = username

    def _get_client(self) -> BKAidevApi:
        """每次现取 client，避免缓存内部 token 失效。"""
        return BKAidevApi.get_client()

    def check_resume(self, session_code: str) -> bool:
        """检查会话是否需要续流（审批回调后 ``is_resume_session`` 返回 True）。

        Returns:
            True: 需要续流（审批已回调）；False: 尚未回调或查询失败。
        """
        try:
            api_client = self._get_client()
            result = api_client.api.is_resume_session(path_params={"session_code": session_code})
            data = result.get("data", False) if isinstance(result, dict) else False
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
            ``{"approve_result": ApproveResultLiteral, "interrupts": list, "id": int|None, "approved_by": str}``。
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
                "[Approval] fetch_approve_result: interrupt 记录无有效 approve_result, "
                "session_code=%s, raw=%r",
                session_code,
                raw_approve_result,
            )
            return None
        interrupts = self._extract_interrupts_from_content(latest.get("content"))
        approved_by = str(builtin_property.get("approved_by") or latest.get("approved_by") or "").strip()
        logger.info(
            "[Approval] fetch_approve_result: session_code=%s, approve_result=%s, approved_by=%s",
            session_code,
            approve_result,
            approved_by,
        )
        return {
            "approve_result": approve_result,
            "interrupts": interrupts,
            "id": latest.get("id"),
            "approved_by": approved_by,
        }

    def query_approval_info(self, session_code: str) -> Optional[dict]:
        """续流前置查询：获取审批结果及 interrupts 内容。

        采用「DB 优先」策略：

        1. 直接从 interrupt 记录读取 ``approve_result``，命中三态字符串即返回，
           无需依赖 platform ``is_resume_session`` 接口。
           —— 用户主动 cancel 由前端 ``user_operation`` 同步写库，无需等待 platform 信号；
           ITSM 回调写库后通常也会同步翻 ``is_resume``，DB 命中即可续流。
        2. DB 未写入时回退查询 :meth:`check_resume`，True 则再次 :meth:`fetch_approve_result`，
           用于覆盖 ITSM 回调旧实现（先翻 ``is_resume``、稍后异步落 ``approve_result``）。

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

    def get_pending_interrupt_context(self, session_code: str) -> dict[str, Any]:
        """从 ``session_property.pending_interrupt`` 读取待恢复中断上下文。"""
        try:
            api_client = self._get_client()
            result = api_client.api.retrieve_chat_session(path_params={"session_code": session_code})
            data = result.get("data", {}) if isinstance(result, dict) else {}
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
            "[Approval] get_graph_thread_id_from_interrupt_content: graph_thread_id=%s, session_code=%s, "
            "latest_keys=%s",
            graph_thread_id, session_code, list(latest.keys()),
        )
        return graph_thread_id

    def _list_interrupt_records(self, session_code: str) -> list[dict]:
        """获取该 session 全部 ``role=interrupt`` 记录列表（按平台返回顺序）。

        注意：gongfeng content API 不支持 role 过滤，返回该 session 全部记录，
        需要在客户端自行过滤 ``role=interrupt`` 的记录。
        """
        try:
            api_client = self._get_client()
            result = api_client.api.get_chat_session_contents(
                params={"session_code": session_code},
            )
        except Exception:
            logger.exception("[Approval] _list_interrupt_records failed: session_code=%s", session_code)
            return []
        contents = result.get("data", []) if isinstance(result, dict) else []
        if not contents or not isinstance(contents, list):
            return []
        return [
            c for c in contents if isinstance(c, dict) and c.get("role") == PromptRole.INTERRUPT.value
        ]

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
          （由平台 ``user_operation`` 接口或 ITSM 回调路径升级而来）
        """
        if content is None:
            return []
        if isinstance(content, str):
            try:
                content = json.loads(content)
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

        平台 ORM 真实存储位置为 ``property.builtin_property``；gongfeng content API
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
          （cancel 在 LangGraph 层与 reject 行为一致，差异仅体现在 ``approve_result``
          字段供前端区分）

        兼容性：``resume_items`` 同时支持 ``list[dict|object]`` 与 ``dict``（单条）
        两种形态——前端不同版本可能直接传单条 dict（如
        ``{"interruptId": "...", "status": "resolved"}``），此处按单元素列表处理。
        非法或空入参直接返回，不抛异常。
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
