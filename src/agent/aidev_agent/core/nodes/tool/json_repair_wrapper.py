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

import json
from collections.abc import Awaitable
from logging import getLogger
from typing import Any, Callable

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

_logger = getLogger(__name__)

_VALIDATION_ERROR_MARKER = "The input is not valid."


def _try_parse_json_string(value: str) -> tuple[bool, Any]:
    """尝试将字符串解析为 JSON 对象/数组。

    策略：
    1. 先用标准 ``json.loads()``，成功则直接返回解析结果。
    2. 若失败（JSONDecodeError），说明字符串可能是损坏的 JSON，
       再尝试用 ``json_repair.loads()`` 修复。
       修复后会做**类型一致性校验**：以 ``{`` 开头的字符串期望得到 dict，
       以 ``[`` 开头的期望得到 list；类型不符则视为误修复，放弃。

    Returns:
        (changed, result)：changed 为 True 时表示成功解析/修复，result 为解析结果。
    """
    stripped = value.lstrip()
    expected_type: type = dict if stripped[:1] == "{" else list

    try:
        parsed = json.loads(value)
        return True, parsed
    except json.JSONDecodeError:
        pass

    try:
        from json_repair import loads as repair_loads

        repaired = repair_loads(value)
        if isinstance(repaired, expected_type):
            return True, repaired
    except ImportError:
        _logger.warning("json_repair is not installed, skipping args repair")
    except Exception:  # noqa: BLE001
        pass

    return False, value


def _repair_args(args: dict[str, Any]) -> dict[str, Any]:
    """对工具调用参数中的字符串值尝试 JSON 解析/修复。

    ``args`` 本身是已解析的 Python dict，其值可以是任意类型。
    仅对满足以下条件的字符串值进行处理：
    - 去除首尾空白后以 ``{`` 或 ``[`` 开头（看起来像 JSON 对象/数组）；
    - 能被标准 ``json.loads`` 解析，或经 ``json_repair`` 修复后得到
      与首字符对应的 dict/list 类型。

    本函数在已知参数校验失败的场景下调用，因此不做字段类型限制。

    Returns:
        修复后的参数字典；当所有值均无需修复时返回原对象（节省内存分配）。
    """
    repaired: dict[str, Any] = {}
    changed = False
    for key, value in args.items():
        if isinstance(value, str) and value.lstrip()[:1] in ("{", "["):
            ok, parsed = _try_parse_json_string(value)
            if ok:
                repaired[key] = parsed
                changed = True
                _logger.debug("json_repair_wrapper: repaired arg '%s': %r -> %r", key, value, parsed)
            else:
                repaired[key] = value
        else:
            repaired[key] = value

    return repaired if changed else args


def _is_validation_error(msg: ToolMessage | Command) -> bool:
    """判断 ToolMessage 内容是否为参数校验失败。"""
    return isinstance(msg, ToolMessage) and isinstance(msg.content, str) and _VALIDATION_ERROR_MARKER in msg.content


def _build_repaired_request(request: ToolCallRequest) -> ToolCallRequest | None:
    """尝试对 request 的 args 进行 json_repair，若无变化则返回 None。"""
    repaired_args = _repair_args(request.tool_call.get("args", {}))
    if repaired_args is request.tool_call.get("args"):
        return None
    return request.override(tool_call={**request.tool_call, "args": repaired_args})


def json_repair_on_error_sync_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """同步响应式 hook：工具因参数校验失败时自动用 json_repair 修复并重试一次。

    执行流程：
    1. 正常调用工具；
    2. 若返回 ``"The input is not valid."`` 错误，尝试修复 args；
    3. args 有变化则重试一次并返回重试结果；
    4. args 无变化（无法修复）则返回原始错误。
    """
    msg = execute(request)

    if not _is_validation_error(msg):
        return msg

    new_request = _build_repaired_request(request)
    if new_request is None:
        _logger.error("json_repair_on_error: no repairable args found, returning original error")
        return msg

    _logger.info(
        "json_repair_on_error: validation error detected for tool '%s', retrying with repaired args",
        request.tool_call.get("name", "unknown"),
    )
    return execute(new_request)


async def json_repair_on_error_async_wrapper(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
) -> ToolMessage | Command:
    """异步响应式 hook：工具因参数校验失败时自动用 json_repair 修复并重试一次。

    执行流程同 :func:`json_repair_on_error_sync_wrapper`。
    """
    msg = await execute(request)
    if not _is_validation_error(msg):
        return msg

    new_request = _build_repaired_request(request)
    if new_request is None:
        _logger.error("json_repair_on_error: no repairable args found, returning original error")
        return msg

    _logger.info(
        "json_repair_on_error: validation error detected for tool '%s', retrying with repaired args",
        request.tool_call.get("name", "unknown"),
    )
    return await execute(new_request)
