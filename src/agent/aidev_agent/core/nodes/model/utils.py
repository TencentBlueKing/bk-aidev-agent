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

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from .tool_call_repair import parse_standalone_plain_text_tool_call_blocks

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 思考块与截断辅助函数
# ---------------------------------------------------------------------------

# 匹配完整的 think/thinking/reasoning 块，支持多行内容。
_THINK_BLOCK_RE = re.compile(
    r"<(think|thinking|reasoning)>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

_THINK_OPEN_TAG_RE = re.compile(
    r"<(?:think|thinking|reasoning)>",
    re.IGNORECASE,
)


def strip_think_blocks(content: str) -> str:
    """从内容中移除 ``<think>...</think>``、``<thinking>...</thinking>`` 和
    ``<reasoning>...</reasoning>`` 标签块。
    """
    return _THINK_BLOCK_RE.sub("", content).strip()


def has_inline_thinking(content: str) -> bool:
    """如果内容包含开启的推理/思考标签，返回 ``True``。"""
    return bool(_THINK_OPEN_TAG_RE.search(content))


def has_content_after_think_block(content: str) -> bool:
    """如果内容在 think 块外有非空文本，返回 ``True``。"""
    if not content:
        return False
    stripped = strip_think_blocks(content)
    return bool(stripped)


def detect_thinking_exhaustion(content: str) -> bool:
    """如果内容有 think 标签但剔除后无内容，返回 ``True``。

    这表明模型将所有输出 token 用于推理。
    """
    if not content:
        return False
    return has_inline_thinking(content) and not has_content_after_think_block(content)


def is_truncated(message: AIMessage) -> bool:
    """如果消息被截断（finish_reason == ``"length"``），返回 ``True``。"""
    finish_reason = message.response_metadata.get("finish_reason", "")
    return finish_reason == "length"


def has_prior_tool_results(messages: list[BaseMessage]) -> bool:
    """如果最近消息中有 ToolMessage 条目，返回 ``True``。"""
    for msg in reversed(messages[:-1]):
        if isinstance(msg, ToolMessage):
            return True
        if isinstance(msg, HumanMessage):
            break
    return False


# ---------------------------------------------------------------------------
# 纯文本工具调用提升
# ---------------------------------------------------------------------------


def extract_text_from_content(content: Any) -> str | None:
    """从消息内容中提取文本，同时处理字符串和列表格式。

    参数：
        content: 普通字符串或内容块列表。

    返回：
        去除首尾空白后的文本内容；如果没有文本则返回 None。
    """
    if isinstance(content, str):
        text = content.strip()
        return text if text else None

    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                block_text = block.get("text", "")
                if isinstance(block_text, str):
                    text_parts.append(block_text)
        joined = "".join(text_parts).strip()
        return joined if joined else None

    return None


def should_promote_message(message: AIMessage, allowed_tool_names: set[str]) -> bool:
    """判断纯文本工具调用是否应提升为原生 tool_calls。

    参数：
        message: 待评估的 AI 消息。
        allowed_tool_names: 有效工具名称集合，用于大小写不敏感匹配。

    返回：
        如果消息看起来包含应提升的纯文本工具调用，则返回 True；否则 False。
    """
    if not allowed_tool_names:
        return False

    if not isinstance(message, AIMessage):
        return False

    # 仅在消息有文本内容但没有原生 tool_calls 时提升。
    if message.tool_calls:
        return False

    text = extract_text_from_content(message.content)
    if not text:
        return False

    # 仅在停止原因表明未使用工具时提升。当模型已经打算使用工具时，
    # 通常会将 finish_reason 设为 "tool_calls" 或类似值；这种情况下无需提升。
    finish_reason = ""
    if message.response_metadata:
        finish_reason = str(message.response_metadata.get("finish_reason", "")).lower()
    return finish_reason not in ("tool_calls", "tool_call", "function_call")


def promote_plain_text_tool_call_message(
    message: AIMessage,
    allowed_tool_names: set[str],
) -> AIMessage:
    """尝试将 *message* 中的纯文本工具调用提升为原生 ``tool_calls``。

    如果提升成功，返回一个新的 ``AIMessage``，其中：
    - ``content`` 保留原始内容。
    - ``tool_calls`` 填充解析出的工具调用。
    - ``response_metadata`` 更新为包含 ``promoted_from_plain_text: True``。

    如果提升失败（或不适用），则原样返回 *message*。

    参数：
        message: 可能需要提升的 AI 消息。
        allowed_tool_names: 用于匹配的有效工具名称集合。

    返回：
        包含已提升 tool_calls 的新 AIMessage，或原始消息。
    """
    if not should_promote_message(message, allowed_tool_names):
        return message

    text = extract_text_from_content(message.content)
    if text is None:
        return message

    parsed = parse_standalone_plain_text_tool_call_blocks(text, allowed_tool_names)
    if parsed is None:
        logger.debug("promote: no plain-text tool calls found in message")
        return message

    # 构建 tool_calls 列表。
    tool_calls: list[dict[str, Any]] = []
    for p in parsed:
        tool_calls.append(
            {
                "name": p.name,
                "args": p.arguments,
                "id": f"call_{uuid.uuid4().hex[:24]}",
            }
        )

    # 保留原始内容；字符串保持字符串，列表内容块保持列表。
    content = message.content

    # 标记 response_metadata，便于下游识别提升来源。
    new_metadata = {**(message.response_metadata or {}), "promoted_from_plain_text": True}

    new_message = AIMessage(
        content=content,
        tool_calls=tool_calls,
        response_metadata=new_metadata,
        id=message.id,
    )

    logger.info(
        "promote: promoted %d plain-text tool call(s) to native format",
        len(tool_calls),
    )
    return new_message
