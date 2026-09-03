# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import interrupt

from aidev_agent.packages.interrupt_manager.approval import (
    TOOL_APPROVAL_REASON,
    TOOL_APPROVAL_STATE_KEY,
    ApprovalTarget,
    _approval_config,
    _tool_call_id,
    _tool_metadata,
    _tool_name,
    is_approval_configured,
)

logger = logging.getLogger(__name__)

# ``TOOL_APPROVAL_REASON`` / ``TOOL_APPROVAL_STATE_KEY`` / ``ApprovalTarget`` /
# ``is_approval_configured``
# 仍从 ``aidev_agent.packages.interrupt_manager.approval`` re-export（43-03 D-07），
# 此处 re-export 兜底历史 import 路径（43-07 移除 shim 时一并收敛）。
# ``get_itsm_approval_target`` 为抛出层策略辅助，定义于此文件（本文件直接调用）。


def _message_tool_approval_map(message: BaseMessage | None) -> dict[str, dict[str, Any]]:
    if not isinstance(message, AIMessage):
        return {}
    value = message.additional_kwargs.get(TOOL_APPROVAL_STATE_KEY, {})
    return value if isinstance(value, dict) else {}


def get_tool_call_approval_record_from_state(state: Any, tool_call_id: str) -> dict[str, Any] | None:
    messages = []
    if isinstance(state, dict):
        messages = state.get("messages", []) or []
    elif hasattr(state, "messages"):
        messages = getattr(state, "messages", []) or []

    for message in reversed(messages):
        record = _message_tool_approval_map(message).get(tool_call_id)
        if isinstance(record, dict):
            return record
    return None


def _approval_record_status(record: Any) -> bool | None:
    """从单条审批记录提取终态布尔语义（True=approved / False=rejected / None=无终态）。

    恢复自历史实现（commit 3ed929a6），供策略基于 state 审批终态的重复审批短路。
    """
    if not isinstance(record, dict):
        return None
    status = record.get("status")
    if status == "approved":
        return True
    if status == "rejected":
        return False
    return None


def get_tool_call_approval_status_from_state(state: Any, tool_call_id: str) -> bool | None:
    """从 state 读取指定 tool_call 的审批终态语义。

    调用语义（对齐历史 ``_resolve_approval``）：True → 放行（已 approved 直接执行）；
    False → 拒绝短路（已 rejected 返回拒绝）；None → 无终态，需调 interrupt。
    """
    return _approval_record_status(get_tool_call_approval_record_from_state(state, tool_call_id))


def get_itsm_approval_target(request: ToolCallRequest) -> ApprovalTarget | None:
    """从 request 直接识别审批目标（幂等纯函数，相同 request → 完全相同的 ApprovalTarget）。

    ``request.tool`` 由 ToolNode 绑定提供，直接访问（不用 getattr 兜底）。
    审批目标字段解析优先级：``approval.target`` 显式配置 > approval 顶层
    字段 > 工具 metadata > 工具名兜底。
    """
    tool = request.tool
    approval = _approval_config(tool)
    if not approval:
        return None
    metadata = _tool_metadata(tool)
    target = approval.get("target") or {}
    tool_name = _tool_name(request)
    return ApprovalTarget(
        target_type=target.get("type") or approval.get("tool_type") or metadata.get("tool_type") or "tool",
        target_id=_tool_call_id(request),
        target_name=target.get("display_name") or approval.get("tool_name") or metadata.get("tool_name") or tool_name,
        target_code=target.get("code") or approval.get("tool_code") or metadata.get("tool_code") or tool_name,
        args=request.tool_call.get("args") or {},
        approval=approval,
    )


def _is_approved(decision: Any) -> bool:
    logger.info("[ToolApproval] 检查审批结果: decision=%s, type=%s", str(decision)[:500], type(decision).__name__)
    if isinstance(decision, list) and decision:
        decision = decision[0]
    if not isinstance(decision, dict):
        return False
    payload = decision.get("payload") if isinstance(decision.get("payload"), dict) else decision
    if "approved" in payload:
        return payload["approved"] is True
    status = payload.get("status") or decision.get("status")
    return status in (True, "approved", "resolved", "approve")


def _rejected_message(request: ToolCallRequest) -> ToolMessage:
    return ToolMessage(
        content="工具审批未通过，已取消执行。",
        tool_call_id=_tool_call_id(request),
        name=_tool_name(request),
        status="error",
    )


class ItsmApprovalStrategy:
    """ITSM 审批中断策略（**无状态**）—— 从 tool_call 直接构造审批对象。

    Send 分派后每个 task 只含一个 tool_call，无需 for 循环逐个审批。
    策略从 request.tool 构造 ApprovalTarget（不依赖工具 metadata 转来转去）。
    审批结果由 interrupt() 获取，resume 后验证 toolCallId 匹配当前 tool_call。

    历史形态（InterruptionStrategy Protocol + strategies 列表 + build_*_wrapper
    工厂）已收敛：唯一实现的策略无状态化，wrapper 降为直插 ToolNode 的两个
    直接函数（itsm_approval_sync/async_wrapper）。
    """

    reason = TOOL_APPROVAL_REASON

    def interrupt(self, request: ToolCallRequest) -> ToolMessage | None:
        # 从 request.tool 直接识别审批目标（get_itsm_approval_target 幂等纯函数）
        approval_target = get_itsm_approval_target(request)
        if approval_target is None:
            return None  # 无需审批

        # 恢复重复审批检查（避免重复审批）：基于 state 审批终态短路。
        # True → 已 approved 直接执行；False → 已 rejected 拒绝短路；
        # None → 无终态，才调 interrupt(value)。
        approval_status = get_tool_call_approval_status_from_state(request.state, approval_target.target_id)
        if approval_status is True:
            return None  # 已通过，直接执行
        if approval_status is False:
            return _rejected_message(request)  # 已拒绝，短路

        # 直抛 ApprovalTarget（alias 协议名 + reason），不在抛出层构造 payload：
        # 单据未创建时 callback_token 拿不到，建单与 payload 构造移交流结束 prepare。
        value = {**approval_target.model_dump(by_alias=True), "reason": self.reason}
        decision = interrupt(value)

        # 验证 decision 的 toolCallId 与当前 target.target_id 一致
        decision_tool_call_id = _extract_tool_call_id_from_decision(decision)
        if decision_tool_call_id is not None and decision_tool_call_id != approval_target.target_id:
            # resume 值不对应当前 tool_call，不能直接使用，视为拒绝
            return _rejected_message(request)

        if not _is_approved(decision):
            return _rejected_message(request)  # 返回拒绝 ToolMessage
        return None  # 通过，wrapper 继续 execute(request)


def _extract_tool_call_id_from_decision(decision: Any) -> str | None:
    """从 interrupt() 返回的 decision 中提取 toolCallId。

    decision 可能是 dict、list[dict]（取首元素）、或 ResumeItem。
    返回 toolCallId 字符串，无法提取时返回 None。
    """
    if isinstance(decision, list) and decision:
        decision = decision[0]
    if not isinstance(decision, dict):
        return None
    # toolCallId 在顶层或 payload 内
    tool_call_id = decision.get("toolCallId")
    if tool_call_id is None:
        payload = decision.get("payload")
        if isinstance(payload, dict):
            tool_call_id = payload.get("toolCallId")
    return tool_call_id


# 无状态单例：sync/async 两个直插 wrapper 共享同一策略实例。
_ITSM_APPROVAL_STRATEGY = ItsmApprovalStrategy()


def itsm_approval_sync_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage],
) -> ToolMessage:
    """ITSM 审批同步 wrapper（ToolNode ``wrap_tool_call`` 直插函数）。

    无需审批 / 审批通过 → execute(request)；审批拒绝 → 短路返回拒绝 ToolMessage。
    返回 ToolMessage（不返回 Command）。
    """
    result = _ITSM_APPROVAL_STRATEGY.interrupt(request)
    if result is not None:
        return result  # 审批拒绝 → 返回拒绝 ToolMessage
    return execute(request)  # 通过 → 执行工具


async def itsm_approval_async_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], Awaitable[ToolMessage]],
) -> ToolMessage:
    """ITSM 审批异步 wrapper（ToolNode ``awrap_tool_call`` 直插函数）。返回 ToolMessage（不返回 Command）。"""
    result = _ITSM_APPROVAL_STRATEGY.interrupt(request)
    if result is not None:
        return result
    return await execute(request)


__all__ = [
    "ItsmApprovalStrategy",
    "itsm_approval_sync_wrapper",
    "itsm_approval_async_wrapper",
    "ApprovalTarget",
    "TOOL_APPROVAL_REASON",
    "TOOL_APPROVAL_STATE_KEY",
    "is_approval_configured",
    "get_itsm_approval_target",
    "get_tool_call_approval_record_from_state",
    "get_tool_call_approval_status_from_state",
]
