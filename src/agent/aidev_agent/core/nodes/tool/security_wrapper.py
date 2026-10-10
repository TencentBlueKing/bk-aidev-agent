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

工具结果安全包装器集合。

本模块提供**两个相互独立**的工具结果出口包装器：

1. **结果脱敏**（``build_redaction_*_wrapper``）：对所有工具返回的 ToolMessage 按
   ``MODEL_OUTPUT`` purpose 脱敏凭据（typed sentinel，不保留 secret body）。
2. **不可信工具结果净化**（``build_untrusted_sanitize_*_wrapper``）：对 web / mcp 等
   不可信工具做原型污染键清理 + 注入痕迹扫描 + 不可信内容包裹，引导模型把外部数据
   当作数据处理而非指令执行。

两者由**独立开关**控制（``use_tool_redaction`` / ``use_tool_untrusted_sanitize``），
可分别启用。既有语义等价「两开关全开」：先脱敏、再包裹。

结果脱敏所需的 ``settings``（``SecurityRedactionSettings``，含已知敏感值）由调用方注入。
本模块不读取环境变量 —— 安全配置的唯一入口是 ``AgentConfig.security_settings``。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCallRequest, ToolCallWrapper
from langgraph.types import Command

from aidev_agent.core.tools.runtime_tools.types import _RuntimeRedactionReceipt
from aidev_agent.packages.security.redaction import (
    RedactionPurpose,
    redact_payload,
    redact_text,
)
from aidev_agent.packages.security.threat_patterns import (
    is_untrusted_tool,
    sanitize_pollution_keys,
    scan_for_threats,
    wrap_untrusted_content,
)
from aidev_agent.pydantic_models import SecurityRedactionSettings

logger = logging.getLogger(__name__)

# ============================================================================
# 结果脱敏（后置改写）
# ============================================================================


def _tool_name_from_message(request: ToolCallRequest, msg: ToolMessage) -> str:
    """从 ToolMessage / request 解析工具名（优先 msg.name）。

    优先取已执行结果的 ``msg.name``，仅在缺失时回退到 ``request.tool_call``。
    """
    name = getattr(msg, "name", "") or ""
    if not name:
        name = request.tool_call.get("name", "") if isinstance(request.tool_call, dict) else ""
    return name


def _tool_metadata(request: ToolCallRequest) -> dict:
    """从 request.tool 读取工具元数据（MCP 工具的 mcp_name 在此）。"""
    tool = getattr(request, "tool", None)
    metadata = getattr(tool, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _untrusted_scan_text(content: Any) -> str:
    """汇总用于防御性扫描的文本：块列表取各 text 块，其余形态走 ``str()``。

    块列表（MCP ``CallToolResult`` 形态）不能整体 ``str()``——那会把块语法噪声
    （``{'type': 'text', ...}``）与文本内容混在一起扫描。这里只取 text 块的
    ``text`` 字段并按 ``\\n`` 拼接，扫描面对齐真实外部数据。
    """
    if isinstance(content, list):
        texts = [
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
        ]
        if texts:
            return "\n".join(texts)
    return str(content)


def _runtime_result_already_redacted(msg: ToolMessage, settings: SecurityRedactionSettings) -> bool:
    """判断该结果是否已由 runtime 工具在「展示格式化之前」完成脱敏。

    只认**内部结果凭据**：必须同时满足类型正确、内容摘要未变、配置摘要一致
    （见 ``runtime_tools.types``）。异常、被其他 wrapper 改写过的内容、
    配置变更后的旧凭据一律返回 False，继续走完整检测。
    """
    if getattr(msg, "status", "success") != "success":
        return False
    artifact = getattr(msg, "artifact", None)
    if not isinstance(artifact, _RuntimeRedactionReceipt):
        return False
    if isinstance(msg.content, (list, tuple, dict)):
        return False
    return artifact.matches(msg.content, settings)


def _redact_message_content(msg: ToolMessage, settings: SecurityRedactionSettings | None = None) -> None:
    """对 ToolMessage 内容执行脱敏（不落明文到模型上下文）。

    工具结果 → 模型上下文，使用 ``MODEL_OUTPUT`` purpose：掩码走 typed sentinel，
    不保留 secret body（避免模型把 ``ghp_ab...xyz`` 误认为可用 token 并写回配置）。

    已知敏感值随 ``settings`` 下发（``SecurityRedactionSettings.known_sensitive_values``）——
    str 与结构化两种形态都透传，避免 dict/list 形态出现覆盖缺口。
    """
    content = msg.content
    if isinstance(content, str):
        msg.content = redact_text(content, purpose=RedactionPurpose.MODEL_OUTPUT, settings=settings)
    elif isinstance(content, (list, tuple, dict)):
        # 结构化 / 多模态块统一走递归脱敏
        msg.content = redact_payload(content, purpose=RedactionPurpose.MODEL_OUTPUT, settings=settings)


def _redact_tool_message(
    request: ToolCallRequest, msg: ToolMessage | Command, settings: SecurityRedactionSettings | None = None
) -> ToolMessage | Command:
    """按 ``MODEL_OUTPUT`` purpose 脱敏工具结果。非 ToolMessage（如 Command）原样透传。

    runtime 工具已在「展示格式化之前」处理过原文，且携带与当前配置匹配的内部凭据 ——
    此时再扫一遍会把行号等展示字符当成正文（空 PEM 块会因此被误遮），故跳过重复检测。
    未携带凭据、凭据不匹配、内容已被改写、异常结果一律照常检测（fail-closed）。

    ``settings`` 由调用方注入，本函数**不自建** ``SecurityRedactionSettings``：
    - ``settings`` 非 None 时才做凭据跳过判定（凭据摘要须与配置比对）；
    - ``settings`` 为 None 时不做跳过判定，直接脱敏 —— ``redact_text`` / ``redact_payload``
      内部各自处理 None 回落，配置来源保持单一（装配层）。
    """
    if not isinstance(msg, ToolMessage):
        return msg
    if settings is not None and _runtime_result_already_redacted(msg, settings):
        return msg
    _redact_message_content(msg, settings)
    return msg


# ============================================================================
# 不可信工具结果净化（后置改写）
# ============================================================================


def _sanitize_untrusted_tool_message(request: ToolCallRequest, msg: ToolMessage | Command) -> ToolMessage | Command:
    """对不可信工具（web / mcp 等外部数据）结果做净化 + 包裹。

    非 ToolMessage（如 Command）原样透传。仅 ``is_untrusted_tool`` 命中的工具结果被处理：
    1. 原型污染键清理（MCP 返回 JSON 净化，阻断 __proto__/constructor/prototype）；
    2. 防御性扫描（scope=all）：扫的文本由 ``_untrusted_scan_text`` 汇总——块列表只取各
       text 块的 ``text``（避免把块语法噪声当正文），其余形态走 ``str(content)``；
       命中高置信注入痕迹仅告警，包裹本身是第一道防线；
    3. 不可信内容包裹（str 输入整体包裹；块列表按 text 块分别包裹，非文本块如 image_url
       保持原结构），引导模型当作数据处理。
    """
    if not isinstance(msg, ToolMessage):
        return msg

    tool_name = _tool_name_from_message(request, msg)
    tool_metadata = _tool_metadata(request)
    if is_untrusted_tool(tool_name, metadata=tool_metadata):
        # 1. 原型污染键清理
        msg.content = sanitize_pollution_keys(msg.content)
        # 2. 防御性扫描（scope=all；块列表只扫各 text 块的文本）
        findings = scan_for_threats(_untrusted_scan_text(msg.content), scope="all")
        if findings:
            logger.warning(
                "[SecurityGuard] untrusted tool=%s returned %d suspicious pattern(s): %s",
                tool_name,
                len(findings),
                [f.pattern_name for f in findings],
            )
        # 3. 不可信内容包裹
        msg.content = wrap_untrusted_content(msg.content, source=tool_name)

    return msg


# ============================================================================
# 包装器构造（两个独立职责，各 4 个构造函数）
# ============================================================================


def build_redaction_sync_wrapper(settings: SecurityRedactionSettings | None = None) -> ToolCallWrapper:
    """构建同步**结果脱敏**包装器。

    这是**后置**改写：先执行原工具，再对返回结果按 ``MODEL_OUTPUT`` purpose 脱敏。

    Args:
        settings: 脱敏配置（含已知敏感值 / 掩码阈值 / 开关），由调用方从
            ``AgentConfig.security_settings.redaction`` 投影后传入。``None`` ⇒ 走
            ``SecurityRedactionSettings()`` 默认工厂（已知值为空、仍保留模式规则脱敏）。
    """

    def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], ToolMessage | Command]
    ) -> ToolMessage | Command:
        return _redact_tool_message(request, execute(request), settings)

    return wrapper


def build_redaction_async_wrapper(settings: SecurityRedactionSettings | None = None) -> AsyncToolCallWrapper:
    """构建异步**结果脱敏**包装器。参数语义同同步版本。"""

    async def wrapper(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        return _redact_tool_message(request, await execute(request), settings)

    return wrapper


def build_untrusted_sanitize_sync_wrapper() -> ToolCallWrapper:
    """构建同步**不可信工具结果净化**包装器（原型污染清理 + 扫描 + 包裹）。

    这是**后置**改写：先执行原工具，再对不可信工具结果净化。无需脱敏配置。
    """

    def wrapper(
        request: ToolCallRequest, execute: Callable[[ToolCallRequest], ToolMessage | Command]
    ) -> ToolMessage | Command:
        return _sanitize_untrusted_tool_message(request, execute(request))

    return wrapper


def build_untrusted_sanitize_async_wrapper() -> AsyncToolCallWrapper:
    """构建异步**不可信工具结果净化**包装器。语义同同步版本。"""

    async def wrapper(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        return _sanitize_untrusted_tool_message(request, await execute(request))

    return wrapper


__all__ = [
    "build_redaction_sync_wrapper",
    "build_redaction_async_wrapper",
    "build_untrusted_sanitize_sync_wrapper",
    "build_untrusted_sanitize_async_wrapper",
]
