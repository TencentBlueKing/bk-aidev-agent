# -*- coding: utf-8 -*-
"""interrupt_manager 的 side_effects（worker factory 注册表）。

本模块提供 reason → worker factory 的注册表（D-10），供
``services/event_handlers/agui_writer.py`` 查表启动轮询 worker，替代现状的
硬编码 ``if first_reason == "aidev:tool_approval"`` 分流
（agui_writer.py:182-190）。

设计约束：
- **Harness 红线**：本包禁止 ``from aidev_agent.core`` / ``from aidev_agent.services``
  / ``from aidev_agent.api``。worker 实现（如 ``aidev_bkplugin.services.approval_resume``，
  仓库外）**不 import**——工厂内部用函数级延迟导入兜底（对齐
  agui_writer.py:185-186 注释明示的循环依赖链）。D-10 延迟导入在注册时解决。
- 注册的 worker factory **不在此层执行**（仅登记），无数据暴露（T-43-02-02 accept）。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: worker factory 类型：``(session_code, username, graph_thread_id, interrupts) -> callable``
#: 返回可调用的 worker（通常返回已启动的后台任务 / 线程）。
WorkerFactory = Callable[[str, str | None, str | None, list[Any]], Callable[[], Any]]

#: reason 字符串 → worker factory 注册表。
_SIDE_EFFECTS: dict[str, WorkerFactory] = {}


def register_side_effect(reason: str, factory: WorkerFactory) -> None:
    """注册 reason → worker factory。

    Args:
        reason: 中断 reason 字符串（来自 :class:`InterruptReason` 内部常量）。
        factory: 构造器 ``(session_code, username, graph_thread_id, interrupts) -> callable``；
            worker 实现依赖仓库外模块时，factory 内部用函数级延迟导入兜底。
    """
    _SIDE_EFFECTS[reason] = factory
    logger.info("[interrupt_manager] 注册 side_effect factory: reason=%s", reason)


def get_side_effect(reason: str | None) -> WorkerFactory | None:
    """按 reason 查询 worker factory。

    Args:
        reason: 中断 reason 字符串；None 或未注册时返回 None。

    Returns:
        匹配的 factory，未注册返回 None（调用方跳过，不启动后台 worker）。
    """
    if reason is None:
        return None
    return _SIDE_EFFECTS.get(reason)


def registered_side_effects() -> tuple[str, ...]:
    """返回已注册的 side_effect reason 元组（只读快照）。"""
    return tuple(_SIDE_EFFECTS)


__all__ = [
    "WorkerFactory",
    "get_side_effect",
    "register_side_effect",
    "registered_side_effects",
]
