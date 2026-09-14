# -*- coding: utf-8 -*-
"""遍历器契约测试脚手架：对一段文本做**一次** ``bashlex.parse`` + ``walk_nodes``。

这些 helper 原先住在 ``command_security.py``（生产模块）内，但**不参与任何生产判定路径**
——公开校验入口是 :func:`validate_command`。放在生产模块里既要为测试 import ``bashlex``，
又容易让人误以为它们是判定链的一部分，故迁到测试目录。

本模块不是测试文件本身（无 ``test_`` 前缀，不会被 pytest 收集），只提供共享 helper。

所有输入都是测试代码内的字符串，仅用于 ``bashlex.parse``，**从不执行**。
"""

from __future__ import annotations

from typing import Any

import bashlex
from aidev_agent.packages.security.command.command_definitions import CommandSource
from aidev_agent.packages.security.command.command_parser import WalkBudget, WalkResult, walk_nodes
from aidev_agent.pydantic_models import SecurityCommandSettings


def _budget_settings(settings: SecurityCommandSettings | None = None, **budget_overrides: int) -> WalkBudget:
    """构造预算：取自 ``settings``，缺省时在**调用时刻**构造模型默认（唯一真源）。

    ``budget_overrides`` 仅覆盖单个上限。
    """
    resolved = settings if settings is not None else SecurityCommandSettings()
    limits: dict[str, Any] = {
        "max_command_length": resolved.max_command_length,
        "max_nodes": resolved.max_nodes,
        "max_depth": resolved.max_depth,
        "max_reparse_depth": resolved.max_reparse_depth,
    }
    limits.update(budget_overrides)
    return WalkBudget(**limits)


def _walk_source_text(
    text: str, *, settings: SecurityCommandSettings | None = None, **budget_overrides: int
) -> tuple[WalkResult, WalkBudget]:
    """对一段文本做**一次** ``bashlex.parse`` + :func:`walk_nodes`，返回遍历结果与预算。"""
    budget = _budget_settings(settings, **budget_overrides)
    source = CommandSource(source_id=0, parent_id=None, origin_span=None, text=text)
    walked = WalkResult(source=source)
    walk_nodes(bashlex.parse(text), source=source, budget=budget, result=walked)
    return walked, budget


def _walk_with_budget(text: str, **budget_overrides: int) -> WalkBudget:
    """:func:`_walk_source_text` 的预算视图（返回计费状态）。"""
    return _walk_source_text(text, **budget_overrides)[1]


def _walk_shared(texts: list[str], **budget_overrides: int) -> WalkBudget:
    """多个文本共用**同一个** budget 依次遍历（验证共享计费）。"""
    budget = _budget_settings(**budget_overrides)
    for index, text in enumerate(texts):
        source = CommandSource(source_id=index, parent_id=None, origin_span=None, text=text)
        walk_nodes(bashlex.parse(text), source=source, budget=budget, result=WalkResult(source=source))
    return budget
