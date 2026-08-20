# -*- coding: utf-8 -*-
"""兼容性 re-export shim：``core.ag_ui.approval`` 旧导入路径保护。

实现单一来源已迁移至 :mod:`aidev_agent.packages.interrupt_manager.approval`
（43-03 迁移、43-07 移除旧 shim；现经本 shim 恢复外部消费者历史导入路径）。
**勿在本模块新增实现**，新调用方一律直接 import packages 单源模块。
"""

from aidev_agent.packages.interrupt_manager.approval import (
    ApprovalOutcomeBuilder,
    ApproveResult,
    ApproveResultLiteral,
)

__all__ = [
    "ApproveResultLiteral",
    "ApproveResult",
    "ApprovalOutcomeBuilder",
]
