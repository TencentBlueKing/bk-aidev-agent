# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

工具点位 wrapper：在链上调用 ``HookRunner``。

- ``tool_pre``：位于代理解包之后、不可信净化 / 脱敏 / ITSM 审批之前。处理器返回
  ``ToolMessage`` / ``Command`` 时直接作为工具结果返回，工具不再执行。
- ``tool_post``：位于 wrapper 链最内层（``deduplicate`` 与 ``_content_error`` 之内），
  处理器直接改写原生 ``ToolMessage``，结果继续流经既有净化链路。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCallRequest, ToolCallWrapper
from langgraph.types import Command

from aidev_agent.core.hook.runner import HookRunner

__all__ = [
    "build_tool_post_async_wrapper",
    "build_tool_post_sync_wrapper",
    "build_tool_pre_async_wrapper",
    "build_tool_pre_sync_wrapper",
]


def _config(request: ToolCallRequest):
    return getattr(getattr(request, "runtime", None), "config", None)


def _apply_tool_post(hook_runner: HookRunner, request: ToolCallRequest, result: ToolMessage | Command):
    """对工具结果中的每条 ``ToolMessage`` 执行 ``tool_post``，返回可能被替换的结果。"""
    config = _config(request)
    if isinstance(result, ToolMessage):
        hooked = hook_runner.tool_post(config, result)
        return result if hooked is None else hooked

    if isinstance(result, Command) and isinstance(result.update, dict):
        messages = result.update.get("messages") or []
        replaced = []
        for message in messages:
            hooked = hook_runner.tool_post(config, message) if isinstance(message, ToolMessage) else None
            replaced.append(message if hooked is None else hooked)
        if any(new is not old for new, old in zip(replaced, messages)):
            result.update["messages"] = replaced
    return result


def build_tool_pre_sync_wrapper(hook_runner: HookRunner) -> ToolCallWrapper:
    """``tool_pre`` wrapper（同步）。"""

    def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], ToolMessage | Command]
    ) -> ToolMessage | Command:
        applied = hook_runner.tool_pre(request)
        if isinstance(applied, (ToolMessage, Command)):
            return applied
        return execute(applied)

    return wrapper


def build_tool_pre_async_wrapper(hook_runner: HookRunner) -> AsyncToolCallWrapper:
    """``tool_pre`` wrapper（异步）。"""

    async def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]
    ) -> ToolMessage | Command:
        applied = await asyncio.to_thread(hook_runner.tool_pre, request)
        if isinstance(applied, (ToolMessage, Command)):
            return applied
        return await execute(applied)

    return wrapper


def build_tool_post_sync_wrapper(hook_runner: HookRunner) -> ToolCallWrapper:
    """``tool_post`` wrapper（同步，位于链最内层）。"""

    def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], ToolMessage | Command]
    ) -> ToolMessage | Command:
        return _apply_tool_post(hook_runner, request, execute(request))

    return wrapper


def build_tool_post_async_wrapper(hook_runner: HookRunner) -> AsyncToolCallWrapper:
    """``tool_post`` wrapper（异步，位于链最内层）。"""

    async def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]
    ) -> ToolMessage | Command:
        result = await execute(request)
        return await asyncio.to_thread(_apply_tool_post, hook_runner, request, result)

    return wrapper
