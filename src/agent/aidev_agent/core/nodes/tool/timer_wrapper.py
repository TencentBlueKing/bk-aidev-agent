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
"""

import time
import uuid
from collections.abc import Awaitable
from typing import Callable

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command


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


def _process_result(
    request: ToolCallRequest,
    msg: ToolMessage | Command,
    duration: int,
) -> ToolMessage | Command:
    """处理工具执行结果，添加元数据并派发事件"""
    description = getattr(request.tool, "description", None) if request.tool else None

    if isinstance(msg, ToolMessage):
        _add_metadata_to_tool_message(msg, duration, description)
    elif isinstance(msg, Command) and msg.update:
        for each in msg.update.get("messages", []):
            if isinstance(each, ToolMessage):
                _add_metadata_to_tool_message(each, duration, description)

    dispatch_custom_event("on_tool_node_finish", data=msg, config=request.runtime.config)
    return msg


def timer_sync_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    # 使用 time.monotonic() 替代 time.time()，使用 time.time() 计算耗时可能受系统时间调整影响导致负值
    t1 = int(time.monotonic() * 1000)
    msg = execute(request)
    duration = int(time.monotonic() * 1000) - t1
    return _process_result(request, msg, duration)


async def timer_async_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    t1 = int(time.monotonic() * 1000)
    msg = await execute(request)
    duration = int(time.monotonic() * 1000) - t1
    return _process_result(request, msg, duration)
