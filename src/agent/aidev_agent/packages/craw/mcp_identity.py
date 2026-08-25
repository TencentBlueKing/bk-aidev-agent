# -*- coding: utf-8 -*-
"""请求级用户 access_token：换票、归一、contextvar、MCP 出口租约。

身份 token 只影响 MCP（对齐 bkai-cli 池模式）：
- 聊天入口换到的用户 token 经 ``X-Bkai-Access-Token`` 交给内核侧；
- 单内核 OpenClaw 不会把对话头透进 MCP，故由本机 egress 按租约注入
  ``X-Bkapi-Authorization``。共享槽 + 租约串行，避免多线程串号。
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_logger = logging.getLogger(__name__)

_BOUND_TOKEN: ContextVar[str] = ContextVar("bkai_craw_user_access_token", default="")

SHARED_IDENTITY_ID = "shared"
EGRESS_URL_ENV = "BKAI_MCP_EGRESS_URL"
IDENTITY_HEADER = "X-Bkai-Access-Token"
IDENTITY_HEADER_ALIAS = "X-Aidev-Access-Token"


def normalize_access_token(raw: Optional[str]) -> str:
    """剥空白 / 外层引号 / Bearer 前缀，避免粘贴污染分裂身份。"""
    token = (raw or "").strip()
    if not token:
        return ""
    if (token[0] == token[-1]) and token[0] in {"'", '"'}:
        token = token[1:-1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
        if (token[0] == token[-1]) and token and token[0] in {"'", '"'}:
            token = token[1:-1].strip()
    return token.replace("\n", "").replace("\r", "")


def bind_user_access_token(token: str) -> None:
    """把本请求的用户 token 挂到 contextvar，供 craw 装配身份。不入日志。"""
    _BOUND_TOKEN.set(normalize_access_token(token))


def get_bound_user_access_token() -> str:
    return normalize_access_token(_BOUND_TOKEN.get())


def resolve_user_access_token(username: str = "", resource_manager=None) -> str:
    """优先请求级 bind，其次 resource_manager.resolve_access_token。"""
    bound = get_bound_user_access_token()
    if bound:
        return bound
    if resource_manager is None:
        return ""
    try:
        return normalize_access_token(resource_manager.resolve_access_token(username) or "")
    except Exception as exc:
        _logger.warning("[CRAW] resolve_access_token(%s) 失败: %s", username, exc)
        return ""


@contextmanager
def mcp_identity_lease(token: str) -> Iterator[None]:
    """对话期间占用 egress 共享槽。未配置 egress 或无 token 时为空操作。"""
    base = (os.getenv(EGRESS_URL_ENV) or "").rstrip("/")
    token = normalize_access_token(token)
    if not base or not token:
        yield
        return
    try:
        import httpx
    except ImportError:
        _logger.warning("[CRAW] httpx 不可用，跳过 MCP 身份租约")
        yield
        return
    timeout = float(os.getenv("BKAI_MCP_EGRESS_LEASE_TIMEOUT", "30"))
    with httpx.Client(timeout=timeout) as client:
        try:
            response = client.post(f"{base}/internal/acquire", json={"token": token})
            response.raise_for_status()
        except Exception as exc:
            _logger.warning("[CRAW] MCP 身份租约获取失败（对话继续，MCP 可能仍是上一身份或空凭证）: %s", exc)
            yield
            return
        try:
            yield
        finally:
            try:
                client.post(f"{base}/internal/release")
            except Exception as exc:
                _logger.warning("[CRAW] MCP 身份租约释放失败: %s", exc)
