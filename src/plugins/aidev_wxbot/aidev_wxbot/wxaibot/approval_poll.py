"""审批结果指数退避轮询。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from logging import getLogger
from typing import Any

from aidev_agent.core.ag_ui.approval import ApproveResult

from .constants import (
    APPROVAL_POLL_INITIAL_SECONDS,
    APPROVAL_POLL_MAX_INTERVAL_SECONDS,
    APPROVAL_POLL_MAX_SECONDS,
)

logger = getLogger(__name__)


def approval_poll_intervals(
    *,
    initial: float = APPROVAL_POLL_INITIAL_SECONDS,
    cap: float = APPROVAL_POLL_MAX_INTERVAL_SECONDS,
    max_seconds: float = APPROVAL_POLL_MAX_SECONDS,
) -> list[float]:
    """首查之后的等待序列：间隔指数翻倍并封顶，总和不超过 ``max_seconds``。"""
    waits: list[float] = []
    elapsed = 0.0
    interval = initial
    while elapsed < max_seconds:
        wait = min(interval, cap, max_seconds - elapsed)
        waits.append(wait)
        elapsed += wait
        interval *= 2
    return waits


def is_final_approve_result(info: Any) -> bool:
    return isinstance(info, dict) and info.get("approve_result") in ApproveResult.ALL


async def wait_for_approval_result(
    query: Callable[[], Awaitable[Any]],
    *,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    intervals: list[float] | None = None,
    session_code: str = "",
    is_live: Callable[[], Awaitable[bool]] | None = None,
) -> dict | None:
    """立即查一次，未终态则按指数间隔继续查，直到命中三态、会话失效或用尽时长。"""
    info = await query()
    if is_final_approve_result(info):
        return info
    for wait in intervals if intervals is not None else approval_poll_intervals():
        logger.info(
            "event=wxbot_card_poll_backoff session_code=%s interval_seconds=%s",
            session_code,
            wait,
        )
        await sleep(wait)
        # /new 之后这张卡对应的会话已经换了 thread，没必要再把剩下的退避表跑完。
        if is_live is not None and not await is_live():
            logger.info("event=wxbot_card_poll_abandoned session_code=%s", session_code)
            return None
        info = await query()
        if is_final_approve_result(info):
            return info
    return None
