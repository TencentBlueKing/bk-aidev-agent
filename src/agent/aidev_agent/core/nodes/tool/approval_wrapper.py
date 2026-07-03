# -*- coding: utf-8 -*-
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.config import get_config
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command, interrupt

from aidev_agent.api.bk_aidev import BKAidevApi

logger = logging.getLogger(__name__)

TOOL_APPROVAL_REASON = "aidev:tool_approval"
TOOL_APPROVAL_STATE_KEY = "tool_approval"


@dataclass(frozen=True)
class ApprovalTarget:
    """审批对象抽象。

    先统一抽象“审批目标识别”，后续 mcp tool / skill 只需复用同一执行逻辑并扩展识别入口。
    """

    target_type: str
    target_id: str
    target_name: str
    target_code: str
    args: dict[str, Any]
    approval: dict[str, Any]
    tool: Any | None = None


def _get_execute_kwargs(request: ToolCallRequest) -> Any | None:
    runtime = getattr(request, "runtime", None)
    config = getattr(runtime, "config", None) or {}
    if not isinstance(config, dict):
        config = dict(config) if config else {}
    execute_kwargs = config.get("configurable", {}).get("execute_kwargs")
    if execute_kwargs:
        return execute_kwargs

    try:
        ctx_config = get_config()
        if ctx_config:
            execute_kwargs = ctx_config.get("configurable", {}).get("execute_kwargs")
            if execute_kwargs:
                logger.info("[ToolApproval] 从 langgraph 上下文获取到 execute_kwargs")
                return execute_kwargs
    except Exception:
        pass

    logger.info("[ToolApproval] 无法获取 execute_kwargs, runtime=%s, config=%s", runtime, config)
    return None


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


def _approval_target_metadata(
    tool: Any | None,
    tool_name: str,
    approval: dict[str, Any],
    *,
    tool_call: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = _tool_metadata(tool)
    target = approval.get("target") or {}
    target_type = target.get("type") or approval.get("tool_type") or metadata.get("tool_type") or "tool"
    target_code = target.get("code") or approval.get("tool_code") or metadata.get("tool_code") or tool_name
    if target_type == "mcp":
        target_code = target.get("code") or approval.get("tool_code") or metadata.get("tool_code") or tool_name
    return {
        "type": target_type,
        "id": target.get("id") or approval.get("id") or metadata.get("tool_id"),
        "name": target.get("name") or tool_name,
        "display_name": target.get("display_name")
        or approval.get("tool_name")
        or metadata.get("tool_name")
        or tool_name,
        "code": target_code,
        "mcp_name": target.get("mcp_name") or approval.get("mcp_code") or metadata.get("mcp_name"),
    }


def identify_tool_approval_target(request: ToolCallRequest) -> ApprovalTarget | None:
    tool = getattr(request, "tool", None)
    approval = _approval_config(tool)
    if not approval:
        return None
    target_meta = _approval_target_metadata(tool, _tool_name(request), approval, tool_call=request.tool_call)
    return ApprovalTarget(
        target_type=target_meta["type"],
        target_id=_tool_call_id(request),
        target_name=target_meta["display_name"],
        target_code=target_meta["code"],
        args=request.tool_call.get("args") or {},
        approval=approval,
        tool=tool,
    )


def identify_message_approval_targets(
    tool_calls: Sequence[dict[str, Any]],
    tool_map: Mapping[str, Any],
) -> list[ApprovalTarget]:
    targets: list[ApprovalTarget] = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        tool = tool_map.get(tool_name)
        approval = _approval_config(tool)
        if not approval:
            continue
        target_meta = _approval_target_metadata(
            tool,
            tool_name or getattr(tool, "name", ""),
            approval,
            tool_call=tool_call,
        )
        targets.append(
            ApprovalTarget(
                target_type=target_meta["type"],
                target_id=tool_call.get("id") or "",
                target_name=target_meta["display_name"],
                target_code=target_meta["code"],
                args=tool_call.get("args") or {},
                approval=approval,
                tool=tool,
            )
        )
    return targets


def _approval_record_status(record: Any) -> bool | None:
    if not isinstance(record, dict):
        return None
    status = record.get("status")
    if status == "approved":
        return True
    if status == "rejected":
        return False
    return None


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


def get_tool_call_approval_status_from_state(state: Any, tool_call_id: str) -> bool | None:
    return _approval_record_status(get_tool_call_approval_record_from_state(state, tool_call_id))


def update_tool_call_approval_record(
    message: AIMessage,
    target: ApprovalTarget,
    *,
    status: str,
    interrupt_payload: dict[str, Any] | None = None,
) -> AIMessage:
    approval_map = dict(_message_tool_approval_map(message))
    record = {
        "type": target.target_type,
        "status": status,
        "toolCallId": target.target_id,
        "toolName": target.target_name,
        "toolCode": target.target_code,
    }
    if interrupt_payload:
        record["interrupt"] = interrupt_payload
    approval_map[target.target_id] = record
    additional_kwargs = dict(message.additional_kwargs)
    additional_kwargs[TOOL_APPROVAL_STATE_KEY] = approval_map
    return message.model_copy(update={"additional_kwargs": additional_kwargs})


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


def _resolve_mcp_name(target: ApprovalTarget) -> str:
    """解析 MCP 服务名，非 mcp 类型返回空字符串。"""
    if target.target_type != "mcp":
        return ""
    approval = target.approval or {}
    target_info = approval.get("target") or {}
    if mcp_code := approval.get("mcp_code"):
        return str(mcp_code)
    if mcp_name := target_info.get("mcp_name"):
        return str(mcp_name)
    metadata = _tool_metadata(target.tool)
    if mcp_name := metadata.get("mcp_name"):
        return str(mcp_name)
    return ""


def _create_approval_from_target(target: ApprovalTarget, execute_kwargs: Any | None) -> dict[str, Any]:
    client = BKAidevApi.get_client()
    session_code = ""
    thread_id = ""
    username = None
    if execute_kwargs:
        session_code = getattr(execute_kwargs, "session_code", None) or ""
        thread_id = getattr(execute_kwargs, "thread_id", None) or ""
        username = getattr(execute_kwargs, "executor", None) or getattr(execute_kwargs, "caller_executor", None)

    approvers = target.approval.get("approvers") or ([username] if username else [])
    payload = {
        "thread_id": thread_id,
        "session_code": session_code,
        "run_id": target.target_id,
        "tool_call_id": target.target_id,
        "tool_type": target.target_type,
        "tool_name": target.target_name,
        "tool_code": target.target_code,
        "mcp_name": _resolve_mcp_name(target),
        "tool_args": target.args,
        "approvers": approvers,
        "ticket_title": f"执行「{target.target_name}」需要审批",
    }
    logger.info("[ToolApproval] 当前用户: %s, approvers: %s", username, approvers)
    try:
        result = client.api.create_tool_approval(
            json=payload,
            headers={"X-BKAIDEV-USER": username} if username else {},
        )
        logger.info("[ToolApproval] 审批工单创建结果: %s", result)
    except Exception as error:
        logger.error("[ToolApproval] 创建审批工单失败: %s: %s", type(error).__name__, error, exc_info=True)
        raise
    return result.get("data", result)


def _interrupt_payload_from_target(
    target: ApprovalTarget,
    approval_data: dict[str, Any] | None = None,
    *,
    execute_kwargs: Any | None = None,
) -> dict[str, Any]:
    approval_data = approval_data or {}
    ticket = dict(approval_data.get("ticket", {}))
    callback_token = approval_data.get("callback_token", "")
    ticket_sn = ticket.get("sn", "")
    # 工具调用参数随 interrupt 一并落库，供续流/历史回填重建 assistant.tool_calls 时使用
    tool_args = dict(target.args) if isinstance(target.args, dict) else {}
    # 使用唯一后缀避免同一工具多次触发审批时 id 重复
    interrupt_id_suffix = f"-{ticket_sn}" if ticket_sn else f"-{uuid.uuid4().hex[:8]}"
    payload = {
        "id": f"int-approval-{target.target_id}{interrupt_id_suffix}",
        "reason": TOOL_APPROVAL_REASON,
        "toolCallId": target.target_id,
        "message": approval_data.get("message") or f"执行「{target.target_name}」前需要人工审批。",
        "callbackToken": callback_token,
        "ticketSn": ticket_sn,
        "ticket_sn": ticket_sn,
        "type": "tool_approval",
        "toolName": target.target_name,
        "toolCode": target.target_code,
        "toolArgs": tool_args,
        "metadata": {
            "type": "tool_approval",
            "status": "pending",
            "callbackToken": callback_token,
            "ticketSn": ticket_sn,
            "toolName": target.target_name,
            "toolCode": target.target_code,
            "toolArgs": tool_args,
            "ticket": ticket,
        },
    }
    logger.info(
        "[ToolApproval] _interrupt_payload_from_target: tool=%s, callback_token=%s, ticket_sn=%s, payload_keys=%s",
        target.target_name,
        callback_token[:8] + "..." if callback_token else "<EMPTY>",
        ticket_sn,
        list(payload.keys()),
    )
    return payload


def request_approval_decision(
    target: ApprovalTarget,
    *,
    execute_kwargs: Any | None,
    is_resuming: bool,
    on_interrupt: Callable[[dict[str, Any]], None] | None = None,
    interrupt_payload: dict[str, Any] | None = None,
) -> bool:
    payload = interrupt_payload
    if payload is None:
        approval_data = None if is_resuming else _create_approval_from_target(target, execute_kwargs)
        payload = _interrupt_payload_from_target(target, approval_data, execute_kwargs=execute_kwargs)
    if not is_resuming and on_interrupt is not None:
        on_interrupt(payload)
    decision = interrupt(payload)
    logger.info(
        "[ToolApproval] interrupt() 返回: tool=%s, tool_call_id=%s, decision=%s, type=%s",
        target.target_name,
        target.target_id,
        str(decision)[:500],
        type(decision).__name__,
    )
    return _is_approved(decision)


def _log_tool_context(request: ToolCallRequest) -> None:
    tool = getattr(request, "tool", None)
    approval = _approval_config(tool) or {}
    logger.info(
        "[ToolApproval] tool metadata: name=%s, approval_enabled=%s, tool_id=%s",
        getattr(tool, "name", "N/A") if tool else "N/A",
        approval.get("approval_enabled"),
        id(tool) if tool else None,
    )


def _resolve_approval(request: ToolCallRequest) -> ToolMessage | None:
    """同步处理审批决策。

    Returns:
        None: 审批通过（或无需审批），由调用方继续执行工具。
        ToolMessage: 审批拒绝，调用方应直接返回该消息。
    """
    target = identify_tool_approval_target(request)
    logger.info(
        "[ToolApproval] ===== 进入 approval wrapper, tool=%s, tool_call_id=%s =====",
        _tool_name(request),
        _tool_call_id(request),
    )
    _log_tool_context(request)
    if target is None:
        return None

    approval_status = get_tool_call_approval_status_from_state(request.state, target.target_id)
    if approval_status is True:
        logger.info("[ToolApproval] 审批已通过，直接执行: tool_call_id=%s", target.target_id)
        return None
    if approval_status is False:
        logger.info("[ToolApproval] 审批已拒绝，返回拒绝消息: tool_call_id=%s", target.target_id)
        return _rejected_message(request)

    execute_kwargs = _get_execute_kwargs(request)
    approved = request_approval_decision(
        target,
        execute_kwargs=execute_kwargs,
        is_resuming=bool(getattr(execute_kwargs, "resume", None)),
    )
    if not approved:
        return _rejected_message(request)
    return None


def approval_sync_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    rejected = _resolve_approval(request)
    if rejected is not None:
        return rejected
    return execute(request)


async def approval_async_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    rejected = _resolve_approval(request)
    if rejected is not None:
        return rejected
    return await execute(request)
