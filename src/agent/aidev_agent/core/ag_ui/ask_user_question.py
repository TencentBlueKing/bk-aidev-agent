# -*- coding: utf-8 -*-
"""兼容性 re-export shim：``core.ag_ui.ask_user_question`` 旧导入路径保护。

实现单一来源已迁移至 :mod:`aidev_agent.packages.interrupt_manager.ask_user_question`
（43-03 迁移、43-07 移除旧 shim；现经本 shim 恢复外部消费者历史导入路径）。
**勿在本模块新增实现**，新调用方一律直接 import packages 单源模块。
"""

from aidev_agent.packages.interrupt_manager.ask_user_question import (
    ASK_USER_QUESTION_REASON,
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

__all__ = [
    "ASK_USER_QUESTION_REASON",
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
]
