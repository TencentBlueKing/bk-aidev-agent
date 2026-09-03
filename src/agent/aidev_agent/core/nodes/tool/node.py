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

import logging
from collections.abc import Awaitable, Sequence
from typing import Callable

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.errors import GraphBubbleUp
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCallRequest, ToolCallWrapper
from langgraph.types import Command

from .approval_wrapper import itsm_approval_async_wrapper, itsm_approval_sync_wrapper
from .json_repair_wrapper import json_repair_on_error_async_wrapper, json_repair_on_error_sync_wrapper
from .pydantic_models import ToolNodeSettings
from .result_limit_wrapper import build_result_limit_async_wrapper, build_result_limit_sync_wrapper
from .timer_wrapper import timer_async_wrapper, timer_sync_wrapper

logger = logging.getLogger(__name__)


def default_tool_call_handler(error: Exception) -> str:
    """处理工具执行异常，返回不包含异常类型的错误消息。

    GraphBubbleUp（GraphInterrupt 基类）在此重新抛出，确保 interrupt() 不被
    ToolNode 的 ``except Exception`` 吞掉。此 handler 作为 ``handle_tool_errors``
    的默认值传入 ToolNode，在 ``_handle_tool_error`` 的 callable 路径中被调用，
    异常会穿过 ``except Exception`` 块正确传播。

    Args:
        error: 捕获的异常对象

    Returns:
        去除类型信息的异常消息字符串

    Example:
        handler = ToolErrorHandler()
        # ValueError: Invalid input -> "Invalid input"
        # KeyError: 'missing_key' -> "'missing_key'"
    """
    # GraphBubbleUp（GraphInterrupt 基类）必须透传，不能被转为 error ToolMessage
    if isinstance(error, GraphBubbleUp):
        raise error
    logger.exception("Tool execution error: %s", error)
    error_message = str(error)

    # 如果异常消息为空，尝试获取异常的 args
    if not error_message and hasattr(error, "args") and error.args:
        error_message = str(error.args[0]) if len(error.args) == 1 else str(error.args)

    # 如果仍然为空，返回通用错误消息
    if not error_message:
        error_message = "工具执行失败"

    return error_message


# ============================================================================
# 工具节点中间件相关函数
# ============================================================================
def _chain_tool_call_wrappers(
    wrappers: Sequence[ToolCallWrapper],
) -> ToolCallWrapper | None:
    """将多个工具调用包装器组合为中间件栈（第一个为最外层）。

    Args:
        wrappers: 按中间件顺序排列的包装器序列。

    Returns:
        组合后的包装器，如果列表为空则返回 None。

    Example:
        wrapper = _chain_tool_call_wrappers([auth, cache, retry])
        # 请求流向: auth -> cache -> retry -> tool
        # 响应流向: tool -> retry -> cache -> auth
    """
    if not wrappers:
        return None

    if len(wrappers) == 1:
        return wrappers[0]

    def compose_two(outer: ToolCallWrapper, inner: ToolCallWrapper) -> ToolCallWrapper:
        """组合两个包装器，outer 包装 inner。"""

        def composed(
            request: ToolCallRequest,
            execute: Callable[[ToolCallRequest], ToolMessage | Command],
        ) -> ToolMessage | Command:
            # 创建一个可调用对象，使用原始 execute 调用 inner
            def call_inner(req: ToolCallRequest) -> ToolMessage | Command:
                return inner(req, execute)

            # outer 可以多次调用 call_inner
            return outer(request, call_inner)

        return composed

    # 链式组合所有包装器: first -> second -> ... -> last
    result = wrappers[-1]
    for wrapper in reversed(wrappers[:-1]):
        result = compose_two(wrapper, result)

    return result


def _chain_async_tool_call_wrappers(
    wrappers: Sequence[AsyncToolCallWrapper],
) -> AsyncToolCallWrapper | None:
    """将多个异步工具调用包装器组合为中间件栈（第一个为最外层）。

    Args:
        wrappers: 按中间件顺序排列的异步包装器序列。

    Returns:
        组合后的异步包装器，如果列表为空则返回 None。
    """
    if not wrappers:
        return None

    if len(wrappers) == 1:
        return wrappers[0]

    def compose_two(
        outer: AsyncToolCallWrapper,
        inner: AsyncToolCallWrapper,
    ) -> AsyncToolCallWrapper:
        """组合两个异步包装器，outer 包装 inner。"""

        async def composed(
            request: ToolCallRequest,
            execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
        ) -> ToolMessage | Command:
            # 创建一个异步可调用对象，使用原始 execute 调用 inner
            async def call_inner(req: ToolCallRequest) -> ToolMessage | Command:
                return await inner(req, execute)

            # outer 可以多次调用 call_inner
            return await outer(request, call_inner)

        return composed

    # 链式组合所有包装器: first -> second -> ... -> last
    result = wrappers[-1]
    for wrapper in reversed(wrappers[:-1]):
        result = compose_two(wrapper, result)

    return result


def build_tool_node(
    tools: Sequence[BaseTool | Callable],
    *,
    name: str = "tools",
    tags: list[str] | None = None,
    handle_tool_errors: bool
    | str
    | Callable[..., str]
    | type[Exception]
    | tuple[type[Exception], ...] = default_tool_call_handler,
    messages_key: str = "messages",
    node_options: ToolNodeSettings | None = None,
    wrappers: Sequence[ToolCallWrapper] | None = None,
    async_wrappers: Sequence[AsyncToolCallWrapper] | None = None,
) -> ToolNode:
    """构造带有中间件支持的 ToolNode。

    该函数会自动添加计时包装器，为每次工具调用收集执行时长和工具描述，
    并将这些元数据添加到 ToolMessage 的 additional_kwargs 中。

    Args:
        tools: 可供此节点调用的工具序列。支持 BaseTool 实例和普通函数。
        name: 节点在图中的名称标识符。
        tags: 可选的元数据标签。
        handle_tool_errors: 错误处理配置。True 表示捕获所有错误并返回包含错误信息的 ToolMessage。
        messages_key: 状态字典中包含消息列表的键名。
        node_options: ToolNodeSettings，用于控制内置包装器开关。
        wrappers: 可选的自定义同步包装器列表，会在内置包装器之后执行。
        async_wrappers: 可选的自定义异步包装器列表，会在内置包装器之后执行。

    Returns:
        配置了中间件的 ToolNode 实例。

    Example:
        # 基本用法
        tool_node = build_tool_node(tools=[my_tool])

        # 添加自定义包装器
        def my_wrapper(request, execute):
            logger.info(f"Calling tool: {request.tool_call['name']}")
            return execute(request)

        tool_node = build_tool_node(tools=[my_tool], wrappers=[my_wrapper])

        # 忽略所有错误
        tool_node = build_tool_node(tools=[my_tool], handle_tool_errors=True)
    """

    node_options = node_options or ToolNodeSettings()

    # 组合包装器：内置包装器 + 用户自定义包装器
    # ITSM 审批 wrapper（直插函数），ask_user 由工具本体直调 interrupt（D-12）
    sync_wrapper_list: list[ToolCallWrapper] = [
        itsm_approval_sync_wrapper,
    ]
    async_wrapper_list: list[AsyncToolCallWrapper] = [
        itsm_approval_async_wrapper,
    ]
    # 是否启用参数校验失败时自动修复重试（响应式）
    if node_options.use_json_repair_on_error:
        sync_wrapper_list.append(json_repair_on_error_sync_wrapper)
        async_wrapper_list.append(json_repair_on_error_async_wrapper)

    # 是否启用工具计时
    if node_options.use_timer:
        sync_wrapper_list.append(timer_sync_wrapper)
        async_wrapper_list.append(timer_async_wrapper)
    # 是否启用返回结果超长限制
    if node_options.use_result_limit:
        sync_wrapper_list.append(build_result_limit_sync_wrapper(node_options.result_limit_thrd))
        async_wrapper_list.append(build_result_limit_async_wrapper(node_options.result_limit_thrd))
    # 其他外部传入的
    if wrappers:
        sync_wrapper_list.extend(wrappers)
    if async_wrappers:
        async_wrapper_list.extend(async_wrappers)
    # 构建wrapper链
    final_sync_wrapper = _chain_tool_call_wrappers(sync_wrapper_list)
    final_async_wrapper = _chain_async_tool_call_wrappers(async_wrapper_list)
    return ToolNode(
        tools=tools,
        name=name,
        tags=tags,
        handle_tool_errors=handle_tool_errors,
        messages_key=messages_key,
        wrap_tool_call=final_sync_wrapper,
        awrap_tool_call=final_async_wrapper,
    )
