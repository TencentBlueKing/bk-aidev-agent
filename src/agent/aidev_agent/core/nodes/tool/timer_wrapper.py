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

工具执行元数据（计时）与工具结果事件（``on_tool_node_finish``）两个互不依赖的 wrapper。

- 计时 wrapper 只写 ``duration`` / ``description`` 元数据，由 ``use_timer`` 控制是否计时；
  关闭时不装配计时 wrapper，不添加计时元数据。
- 事件 wrapper 只管派发，没有开关：装配时置于 wrapper 链最外层，审批拒绝结果不派发，
  故派发时脱敏、限长、错误标记、代理改名、循环守卫判定都已完成。interrupt / 终止
  以异常形式抛出，没有返回值可派发，因此天然不会产生结果事件。
"""

import time
import uuid
from collections.abc import Awaitable
from typing import Callable

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from aidev_agent.packages.interrupt_manager.approval import TOOL_APPROVAL_REJECTED_KEY

TOOL_RESULT_EVENT = "on_tool_node_finish"


def _add_metadata_to_tool_message(
    msg: ToolMessage,
    duration: int,
    description: str | None,
) -> None:
    """为 ToolMessage 添加执行元数据。

    向 ToolMessage 的 additional_kwargs 中添加执行时长和工具描述，
    并确保消息具有唯一 ID。

    Args:
        msg: 要添加元数据的 ToolMessage 对象。
        duration: 工具执行时长（毫秒）。
        description: 工具的描述信息，可为 None。
    """
    msg.additional_kwargs.setdefault("duration", duration)
    if description:
        msg.additional_kwargs.setdefault("description", description)
    if not msg.id:
        msg.id = uuid.uuid4().hex


def _iter_result_messages(msg: ToolMessage | Command) -> list[ToolMessage]:
    """取出结果中需要附加元数据 / 派发事件的 ToolMessage。

    Args:
        msg: 工具执行的返回值，可能是单个 ToolMessage 或携带 messages 的 Command。

    Returns:
        ToolMessage 列表；非上述形状时为空列表。
    """
    if isinstance(msg, ToolMessage):
        return [msg]
    if isinstance(msg, Command) and isinstance(msg.update, dict):
        return [each for each in msg.update.get("messages", []) or [] if isinstance(each, ToolMessage)]
    return []


def _apply_timing_metadata(
    request: ToolCallRequest,
    msg: ToolMessage | Command,
    duration: int,
    include_description: bool = True,
) -> None:
    """把执行时长与工具描述写入结果的 ToolMessage。

    Args:
        request: 工具调用请求，用于取目标工具的 description。
        msg: 工具执行的返回值。
        duration: 工具执行时长（毫秒）；不计时时由调用方传 0。
        include_description: 是否写入工具描述（不计时时保持不写）。
    """
    description = getattr(request.tool, "description", None) if request.tool and include_description else None
    for each in _iter_result_messages(msg):
        _add_metadata_to_tool_message(each, duration, description)


def dispatch_tool_result_event(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """执行工具并派发结果事件，审批拒绝消息仅返回、不派发。

    ``execute`` 抛出异常（含 interrupt、循环终止）时不返回、也不派发任何事件。
    """
    msg = execute(request)
    for each in _iter_result_messages(msg):
        if each.additional_kwargs.get(TOOL_APPROVAL_REJECTED_KEY) is True:
            continue
        dispatch_custom_event(TOOL_RESULT_EVENT, data=each, config=request.runtime.config)
    return msg


async def dispatch_tool_result_event_async(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    """异步版：语义与 ``dispatch_tool_result_event`` 一致。"""
    msg = await execute(request)
    for each in _iter_result_messages(msg):
        if each.additional_kwargs.get(TOOL_APPROVAL_REJECTED_KEY) is True:
            continue
        dispatch_custom_event(TOOL_RESULT_EVENT, data=each, config=request.runtime.config)
    return msg


def timer_sync_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    # 使用 time.monotonic() 替代 time.time()，使用 time.time() 计算耗时可能受系统时间调整影响导致负值
    t1 = int(time.monotonic() * 1000)
    msg = execute(request)
    _apply_timing_metadata(request, msg, int(time.monotonic() * 1000) - t1)
    return msg


async def timer_async_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    t1 = int(time.monotonic() * 1000)
    msg = await execute(request)
    _apply_timing_metadata(request, msg, int(time.monotonic() * 1000) - t1)
    return msg
