# -*- coding: utf-8 -*-
"""审批通过后，按 binding.executor_identity 切换下游 tool / MCP 调用身份。"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any, Awaitable, Callable

from langchain_mcp_adapters.interceptors import MCPToolCallRequest

logger = logging.getLogger(__name__)

AUTH_HEADER_KEY = "X-Bkapi-Authorization"


class ExecutorIdentity(StrEnum):
    """审批通过后下游 tool / MCP 调用使用的身份。"""

    USER = "user"
    APPROVER = "approver"


# 兼容旧引用
EXECUTOR_IDENTITY_USER = ExecutorIdentity.USER
EXECUTOR_IDENTITY_APPROVER = ExecutorIdentity.APPROVER


def normalize_executor_identity(value: Any, *, approval_enabled: bool = True) -> str:
    """非法值与未启用审批一律回落为智能体使用者身份。"""
    raw = str(value or "").strip()
    if not approval_enabled:
        if raw and raw != ExecutorIdentity.USER:
            logger.info("[ToolApproval] executor_identity=%s 因未启用审批回落为 user", raw)
        return ExecutorIdentity.USER
    if raw == ExecutorIdentity.APPROVER:
        return ExecutorIdentity.APPROVER
    if raw and raw != ExecutorIdentity.USER:
        logger.info("[ToolApproval] 非法 executor_identity=%s，回落为 user", raw)
    return ExecutorIdentity.USER


def make_mcp_identity_ctx() -> dict[str, Any]:
    """MCP interceptor 与续流切换共享的可变上下文。"""
    return {"approved_by": "", "approver_tools": set()}


def build_approver_auth_header(executor_info: dict | None, username: str) -> str:
    """应用态 + bk_username 冒充审批人；不得携带使用者 access_token。"""
    info = executor_info or {}
    return json.dumps(
        {
            "bk_app_code": info.get("app_code") or "",
            "bk_app_secret": info.get("app_secret") or "",
            "bk_username": username,
        }
    )


def find_api_wrapper(tool: Any) -> Any | None:
    """从 StructuredTool 取出 ApiWrapper（兼容闭包包装与直接 func）。"""
    func = getattr(tool, "func", None)
    if func is None:
        return None
    if hasattr(func, "_extra"):
        return func
    for cell in getattr(func, "__closure__", None) or ():
        contents = cell.cell_contents
        if hasattr(contents, "_extra"):
            return contents
    return None


def apply_http_approver_identity(tools: list[Any] | None, executor_info: dict | None, approved_by: str) -> None:
    """就地改写 HTTP 工具的 X-Bkapi-Authorization 为审批人应用态身份。"""
    username = str(approved_by or "").strip()
    if not username:
        logger.warning("[ToolApproval] apply_http_approver_identity: approved_by 为空，跳过 HTTP 身份切换")
        return
    header_value = build_approver_auth_header(executor_info, username)
    switched = 0
    for tool in tools or []:
        approval = (getattr(tool, "metadata", None) or {}).get("approval") or {}
        tool_name = getattr(tool, "name", "")
        if approval.get("executor_identity") != ExecutorIdentity.APPROVER:
            continue
        wrapper = find_api_wrapper(tool)
        extra = getattr(wrapper, "_extra", None) if wrapper is not None else None
        if extra is None:
            logger.warning("[ToolApproval] HTTP 工具 %s 是 approver 身份但找不到 ApiWrapper", tool_name)
            continue
        header = dict(getattr(extra, "header", None) or {})
        header[AUTH_HEADER_KEY] = header_value
        extra.header = header
        switched += 1
        logger.info(
            "[ToolApproval] HTTP 已切换审批人身份: tool=%s, bk_username=%s, has_app_code=%s, has_app_secret=%s",
            tool_name,
            username,
            bool((executor_info or {}).get("app_code")),
            bool((executor_info or {}).get("app_secret")),
        )
    logger.info("[ToolApproval] apply_http_approver_identity: approved_by=%s, switched=%s", username, switched)


def collect_approver_tool_names(tools: list[Any] | None) -> set[str]:
    names: set[str] = set()
    for tool in tools or []:
        approval = (getattr(tool, "metadata", None) or {}).get("approval") or {}
        if approval.get("executor_identity") != ExecutorIdentity.APPROVER:
            continue
        name = getattr(tool, "name", "") or ""
        if name:
            names.add(name)
    logger.info("[ToolApproval] collect_approver_tool_names: %s", names)
    return names


def make_mcp_approver_interceptor(
    ctx: dict[str, Any],
    executor_info: dict | None,
) -> Callable[[MCPToolCallRequest, Callable[[MCPToolCallRequest], Awaitable[Any]]], Awaitable[Any]]:
    """按 tool 名把本次 MCP 调用的 headers 换成审批人应用态身份。"""

    async def interceptor(request: MCPToolCallRequest, handler):
        approved_by = str(ctx.get("approved_by") or "").strip()
        approver_tools = ctx.get("approver_tools") or set()
        will_switch = bool(approved_by and request.name in approver_tools)
        if approved_by:
            logger.info(
                "[ToolApproval] MCP interceptor: tool=%s, approved_by=%s, switch=%s, approver_tools=%s",
                request.name,
                approved_by,
                will_switch,
                approver_tools,
            )
        if will_switch:
            headers = dict(request.headers or {})
            headers[AUTH_HEADER_KEY] = build_approver_auth_header(executor_info, approved_by)
            request = request.override(headers=headers)
        return await handler(request)

    return interceptor
