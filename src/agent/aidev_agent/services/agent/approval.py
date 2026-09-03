# -*- coding: utf-8 -*-
"""审批领域处理器（旧格式兼容层，wxbot 插件唯一审批入口）。

``ApprovalStateHandler`` 实现单一来源在
:mod:`aidev_agent.packages.interrupt_manager.approval`（43-05 迁移，构造注入
resource_manager）。本模块对外暴露的 :class:`ApprovalStateHandler` 为其**旧格式
子类**：构造签名保持 ``username=``，数据访问经 :meth:`ApprovalStateHandler._get_client`
每次现取 ``BKAidevApi.get_client()``（避免缓存内部 token 失效），不依赖
resource_manager 装配；平台调用方法按旧格式覆写（``client.api.X`` +
``path_params``/``params`` + ``data`` 信封解包）。纯逻辑静态方法与
``hydrate_resume_payload`` 全部继承基类零漂移。

与基类的行为差异（插件侧契约，勿单方面改动）：

- :meth:`fetch_approve_result` **旧版富返回**：在三键基础上追加
  ``graph_thread_id``（取自同一条 interrupt 记录）。插件 ``approval_resume``
  在部分平台不保留 ``session_property.pending_interrupt`` 时，依赖同记录的
  ``graph_thread_id`` 兜底续流上下文，不能新建线程或从其他审批拼接。

**内部代码勿引用本模块**（wxbot 兼容层契约）；新调用方一律使用 packages 单源实现。

对外兼容导出（历史 import 路径保护）：
- :class:`ApprovalStateHandler`（旧格式子类）
- :class:`ApproveResult` / ``ApproveResultLiteral``（re-export 自 packages 单源）
"""

import logging
from typing import Any, Optional

from aidev_agent.api.bk_aidev import BKAidevApi, Client
from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager import (
    ApprovalStateHandler as _ResourceManagedApprovalStateHandler,
)
from aidev_agent.packages.interrupt_manager import (
    ApproveResult,
    ApproveResultLiteral,
)

logger = logging.getLogger(__name__)


class ApprovalStateHandler(_ResourceManagedApprovalStateHandler):
    """旧格式审批状态读处理器：直连 ``BKAidevApi`` 平台 API（无 resource_manager）。

    与基类（resource_manager 注入）的差异仅在数据访问层：

    - ``__init__(username=...)``：保留旧构造签名（读路径暂不消费，预留
      ``X-BKAIDEV-USER`` header 透传位）。
    - :meth:`_get_client`：每次现取 ``BKAidevApi.get_client()``。
    - ``check_resume`` / ``get_pending_interrupt_context`` / ``_list_interrupt_records``：
      按旧格式（``client.api.X`` + ``data`` 信封解包）调用，返回形态与基类一致。
    - :meth:`fetch_approve_result`：富返回，追加 ``graph_thread_id``。
    """

    def __init__(self, *, username: str = "") -> None:
        super().__init__(resource_manager=None)
        self.username = username

    def _get_client(self) -> Client:
        """每次现取 client，避免缓存内部 token 失效。"""
        return BKAidevApi.get_client()

    def check_resume(self, session_code: str) -> bool:
        """检查会话是否需要续流（审批回调后 ``is_resume_session`` 返回 True）。

        Returns:
            True: 需要续流（审批已回调）；False: 尚未回调或查询失败。
        """
        try:
            result = self._get_client().api.is_resume_session(path_params={"session_code": session_code})
            data = result.get("data", False) if isinstance(result, dict) else False
            logger.info("[Approval] check_resume: session_code=%s, is_resume=%s", session_code, data)
            return bool(data)
        except Exception:
            logger.exception("[Approval] check_resume failed: session_code=%s", session_code)
            return False

    def fetch_approve_result(self, session_code: str) -> Optional[dict]:
        """从最新一条 ``role=interrupt`` 记录读取审批结果及 ``interrupts`` 内容。

        旧版富返回：``{"approve_result", "interrupts", "id", "graph_thread_id",
        "approval_trace_context"}``。``graph_thread_id`` 取自同一条记录（嵌套
        ``property.builtin_property`` 优先，平铺顶层兜底），供插件在平台不保留
        ``pending_interrupt`` 时兜底续流上下文；``approval_trace_context`` 为回调
        落库的父 trace 载体（企微跨进程续流恢复链路用），缺失时为 None。

        Returns:
            富返回 dict；未找到 interrupt 记录或记录尚未写入审批结果时返回 None。
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
            "graph_thread_id": self._extract_graph_thread_id_from_interrupt_record(latest),
            # 回调落库的父 trace 载体（嵌套/平铺经 _extract_builtin_property 统一读取），
            # 插件后台续流经 propagated_trace_context 恢复，保证 trace 回连审批回调
            "approval_trace_context": builtin_property.get("approval_trace_context"),
        }

    def get_pending_interrupt_context(self, session_code: str) -> dict[str, Any]:
        """从 ``session_property.pending_interrupt`` 读取待恢复中断上下文。"""
        try:
            result = self._get_client().api.retrieve_chat_session(path_params={"session_code": session_code})
            data = result.get("data", {}) if isinstance(result, dict) else {}
            session_property = data.get("session_property", {}) if isinstance(data, dict) else {}
            pending_interrupt = (
                session_property.get("pending_interrupt", {}) if isinstance(session_property, dict) else {}
            )
            return pending_interrupt if isinstance(pending_interrupt, dict) else {}
        except Exception:
            logger.exception("[Approval] get_pending_interrupt_context failed: session_code=%s", session_code)
            return {}

    def _list_interrupt_records(self, session_code: str) -> list[dict]:
        """获取该 session 全部 ``role=interrupt`` 记录列表（按平台返回顺序）。

        注意：content API 不支持 role 过滤，返回该 session 全部记录，
        需要在客户端自行过滤 ``role=interrupt`` 的记录。
        """
        try:
            result = self._get_client().api.get_chat_session_contents(params={"session_code": session_code})
        except Exception:
            logger.exception("[Approval] _list_interrupt_records failed: session_code=%s", session_code)
            return []
        contents = result.get("data", []) if isinstance(result, dict) else []
        if not contents or not isinstance(contents, list):
            return []
        return [c for c in contents if isinstance(c, dict) and c.get("role") == PromptRole.INTERRUPT.value]


__all__ = [
    "ApprovalStateHandler",
    "ApproveResult",
    "ApproveResultLiteral",
]
