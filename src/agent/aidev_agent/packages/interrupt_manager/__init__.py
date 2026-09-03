# -*- coding: utf-8 -*-
"""interrupt_manager：统一中断处理机制的**唯一承载**（接口 + 引擎 + 类型落位）。

本包集中（D-05）：

- :mod:`~aidev_agent.packages.interrupt_manager.types` —— ``InterruptReason`` 枚举
  （reason 字符串目标落位）、``ProcessorContext`` / ``ResumeInputResult`` 容器、
  两段纯 Protocol 契约（``InterruptStrategy`` / ``InterruptHandler``，含
  ``on_resume`` 写路径；原 registry.py 已并入）。
- :mod:`~aidev_agent.packages.interrupt_manager.side_effects` —— worker factory
  注册表（供 agui_writer 查表启动轮询 worker）。

本包**不做模块级注册装配**（D-01：注册表机制删除）。reason → handler 的绑定
由装配层（chat.py execute 入口）以 ``InterruptProcessor(handlers={reason: handler})``
dict 显式注入（D-03），``ApprovalHandler()`` / ``AskUserQuestionHandler()`` 不再
作为模块级单例存在。仅经
``from aidev_agent.packages.interrupt_manager import ...`` 顶层导入纯类型 /
Protocol / handler 类。

Harness 依赖方向：本包只允许依赖标准库 / pydantic / 自家包内模块，
禁止 ``from aidev_agent.core`` / ``from aidev_agent.services`` / ``from aidev_agent.api``。
"""

from __future__ import annotations

import logging

from aidev_agent.packages.interrupt_manager.approval import (
    TOOL_APPROVAL_REASON,
    TOOL_APPROVAL_STATE_KEY,
    ApprovalHandler,
    ApprovalOutcomeBuilder,
    ApprovalStateHandler,
    ApprovalTarget,
    ApproveResult,
    ApproveResultLiteral,
    ItsmApprovalInterrupt,
    ItsmApprovalMetadata,
    ItsmApprovalPayload,
    ItsmApprovalResult,
    ItsmApprovalTicket,
    ItsmTicketCreator,
    _approval_config,
    is_approval_configured,
)
from aidev_agent.packages.interrupt_manager.ask_user_question import (
    ASK_USER_QUESTION_SKIPPED_CONTENT,
    AskUserQuestionHandler,
    AskUserQuestionItem,
    AskUserQuestionMetadata,
    AskUserQuestionOption,
    AskUserQuestionOutcomeBuilder,
    AskUserQuestionTarget,
    InterruptStatus,
    build_skipped_answers,
    build_updated_builtin_property,
    extract_message_id,
    filter_ask_user_question_interrupts,
    parse_resume_answers,
)
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from aidev_agent.packages.interrupt_manager.side_effects import (
    WorkerFactory,
    get_side_effect,
    register_side_effect,
    registered_side_effects,
)
from aidev_agent.packages.interrupt_manager.types import (
    ASK_USER_QUESTION_REASON,
    CREATE_TICKET_ERROR,
    InterruptHandler,
    InterruptReason,
    InterruptStrategy,
)
from aidev_agent.packages.interrupt_manager.utils import get_interrupt_value, unwrap_interrupt_source

logger = logging.getLogger(__name__)

__all__ = [
    # 类型 / reason 常量
    "InterruptReason",
    "TOOL_APPROVAL_REASON",
    "ASK_USER_QUESTION_REASON",
    # 两段 Protocol（原 registry.py 并入 types）
    "InterruptStrategy",
    "InterruptHandler",
    # 注册表（worker factory，side_effects 独立机制，保留）
    "WorkerFactory",
    "get_side_effect",
    "register_side_effect",
    "registered_side_effects",
    # 审批实现（单源落位本包，原 ag_ui 侧 approval 与 approval_wrapper，shim 已随 43-07 移除）
    "ApproveResultLiteral",
    "ApproveResult",
    "ApprovalOutcomeBuilder",
    "ItsmApprovalInterrupt",
    "ItsmApprovalMetadata",
    "ItsmApprovalPayload",
    "ItsmApprovalResult",
    "ItsmApprovalTicket",
    "ApprovalStateHandler",
    "TOOL_APPROVAL_STATE_KEY",
    "ApprovalTarget",
    "is_approval_configured",
    "ItsmTicketCreator",
    "_approval_config",
    # 统一中断编排（44 D-02，取代 InterruptDispatcher + ResumeCoordinator）
    "InterruptProcessor",
    "CREATE_TICKET_ERROR",
    # 流结束统一处理层（43-06 D-09）
    "ApprovalHandler",
    # ask_user_question 实现（单源落位本包，原 ag_ui 侧实现，shim 已随 43-07 移除）
    "ASK_USER_QUESTION_SKIPPED_CONTENT",
    "InterruptStatus",
    "AskUserQuestionHandler",
    "AskUserQuestionItem",
    "AskUserQuestionOutcomeBuilder",
    "AskUserQuestionMetadata",
    "AskUserQuestionOption",
    "AskUserQuestionTarget",
    "extract_message_id",
    "build_skipped_answers",
    "build_updated_builtin_property",
    "filter_ask_user_question_interrupts",
    "parse_resume_answers",
    # 读路径工具（迁移自 core/ag_ui/utils.py）
    "get_interrupt_value",
    "unwrap_interrupt_source",
]
