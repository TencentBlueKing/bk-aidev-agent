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

延迟加载 ``tool_call`` 代理的解包 wrapper（由 ``ToolNodeSettings.use_tool_call_proxy`` 开启）。

解包在链首：把 ``tool_call(name=X, arguments=A)`` 换成对目标工具 X 的直接调用（调用 ID 不变），
其后的审批 / 安全 / 计时 / 截断 / 去重都按目标工具判定、只走一次。改名在解包 wrapper 返回时
原地完成，覆盖不经过工具执行的结果（审批拒绝、去重复用、wrapper 异常转换等）。

链尾不再有改名 wrapper，也不再经 ContextVar 传递代理状态：解包位于链首，返回时即已改名，
最外层事件 wrapper 派发时结果名已是 ``tool_call``。

目标不可执行（不存在 / 不在延迟目录 / 参数形状非法）时不解包，交回 ``ToolCallTool`` 本体报错。
"""

from collections.abc import Awaitable, Callable, Mapping

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCallRequest, ToolCallWrapper
from langgraph.types import Command

from aidev_agent.core.tools.tool_lazy_loading.meta_tools import CALL_TOOL_NAME


def _rename(output: ToolMessage | Command) -> ToolMessage | Command:
    """把结果中的 ToolMessage 名改回代理名（原地修改）。"""
    messages = [output] if isinstance(output, ToolMessage) else []
    if isinstance(output, Command) and isinstance(output.update, dict):
        messages = [m for m in output.update.get("messages", []) or [] if isinstance(m, ToolMessage)]
    for message in messages:
        message.name = CALL_TOOL_NAME
    return output


def _unwrap(request: ToolCallRequest, tools_by_name: Mapping[str, BaseTool]) -> ToolCallRequest | None:
    """代理调用且目标可执行时返回目标请求，否则返回 None（原样执行）。"""
    call = request.tool_call
    args = call.get("args")
    if call.get("name") != CALL_TOOL_NAME or not isinstance(args, dict) or set(args) - {"name", "arguments"}:
        return None
    name, arguments = args.get("name"), args.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, dict) or name not in tools_by_name:
        return None
    catalog = getattr(request.tool, "catalog", None)
    if catalog is None or catalog.executable(name) is None:
        return None
    return request.override(tool_call={**call, "name": name, "args": dict(arguments)}, tool=tools_by_name[name])


def build_tool_call_unwrap_sync_wrapper(tools_by_name: Mapping[str, BaseTool]) -> ToolCallWrapper:
    """链首解包 wrapper；``tools_by_name`` 须与 ToolNode 注册的是同一批实例。"""

    def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], ToolMessage | Command]
    ) -> ToolMessage | Command:
        target = _unwrap(request, tools_by_name)
        if target is None:
            return execute(request)
        return _rename(execute(target))

    return wrapper


def build_tool_call_unwrap_async_wrapper(tools_by_name: Mapping[str, BaseTool]) -> AsyncToolCallWrapper:
    """链首解包 wrapper（异步）。"""

    async def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]
    ) -> ToolMessage | Command:
        target = _unwrap(request, tools_by_name)
        if target is None:
            return await execute(request)
        return _rename(await execute(target))

    return wrapper
