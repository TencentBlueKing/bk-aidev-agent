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

工具结果长度限制。

当工具返回内容超过 ``result_limit`` 阈值时，将内容整体替换为一行超长提示，
避免上下文被瞬间塞爆。
"""

from __future__ import annotations

from collections.abc import Awaitable
from functools import lru_cache
from typing import Callable

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCallRequest, ToolCallWrapper
from langgraph.types import Command

TOOL_RESULT_TOO_LONG_MESSAGE = "本次工具调用返回结果超长，请重新调整调用参数"


def _tool_msg_content_len(msg: ToolMessage) -> int:
    """计算 ToolMessage 内容的字符串长度。"""
    content = getattr(msg, "content", None)
    if content is None:
        return 0
    return len(str(content))


def _truncate_msg(msg: ToolMessage, result_limit: int, reject_message: str) -> None:
    """对超长 ToolMessage 做整段替换（固定实现）。"""
    msg.content = reject_message
    msg.status = "error"


@lru_cache(maxsize=16)
def build_result_limit_sync_wrapper(
    result_limit: int, reject_message: str = TOOL_RESULT_TOO_LONG_MESSAGE
) -> ToolCallWrapper:
    """构建同步结果长度限制包装器。

    Args:
        result_limit: 结果内容的最大字符数阈值。
        reject_message: 超过阈值时替换的提示消息。

    Returns:
        配置好的同步工具调用包装器。
    """

    def wrapper(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        msg = execute(request)
        if isinstance(msg, ToolMessage) and _tool_msg_content_len(msg) > result_limit:
            _truncate_msg(msg, result_limit, reject_message)
        return msg

    return wrapper


@lru_cache(maxsize=16)
def build_result_limit_async_wrapper(
    result_limit: int, reject_message: str = TOOL_RESULT_TOO_LONG_MESSAGE
) -> AsyncToolCallWrapper:
    """构建异步结果长度限制包装器。"""

    async def wrapper(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        msg = await execute(request)
        if isinstance(msg, ToolMessage) and _tool_msg_content_len(msg) > result_limit:
            _truncate_msg(msg, result_limit, reject_message)
        return msg

    return wrapper
