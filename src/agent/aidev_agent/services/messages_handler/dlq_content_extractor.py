# -*- coding: utf-8 -*-
"""
死信队列内容提取器

从 DLQ 中的 AG-UI 事件提取完整的消息内容。
用于在用户暂停对话时，获取已发送给前端的完整内容进行回写。

"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Any, Final

from ag_ui.core import EventType

from .base import EOD_CHUNK, HEARTBEAT_CHUNK

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = getLogger(__name__)

# SSE 数据前缀
_SSE_DATA_PREFIX: Final[str] = "data: "
_SSE_DATA_PREFIX_LEN: Final[int] = len(_SSE_DATA_PREFIX)

# 默认的未知消息 ID
_UNKNOWN_MESSAGE_ID: Final[str] = "unknown"


@dataclass(slots=True)
class ExtractedContent:
    """从 DLQ 提取的消息内容

    使用 slots=True 减少内存占用，提升属性访问速度。

    Attributes:
        assistant_content: 当前 assistant 消息的完整内容
        assistant_message_id: 当前 assistant 消息的 message_id
        reasoning_content: reasoning 内容列表（如 deepseek-reasoner 的思考过程）
        has_output: 是否有任何有效输出
    """

    assistant_content: str = ""
    assistant_message_id: str = ""
    reasoning_content: list[str] = field(default_factory=list)
    has_output: bool = False

    def is_empty(self) -> bool:
        """检查是否为空内容"""
        return not self.has_output and not self.assistant_content and not self.reasoning_content


class DLQContentExtractor:
    """从死信队列消息中提取完整内容

    DLQ 中存储的是 SSE 编码后的字符串（格式：data: {...}\n\n），
    需要先解析 SSE 格式，再处理 AG-UI 事件来重建完整的消息内容。

    支持的事件类型:
        - TEXT_MESSAGE_START: 标记消息开始，记录 message_id
        - TEXT_MESSAGE_CONTENT: 包含 delta，累积内容
        - TEXT_MESSAGE_END: 标记消息结束
        - THINKING_TEXT_MESSAGE_CONTENT: 包含 reasoning delta

    设计原则:
        - 使用 __slots__ 减少内存占用
        - 缓存常用的事件类型判断
        - 使用列表累积后一次性 join，避免字符串拼接开销
        - 提供清晰的日志用于问题排查

    使用示例:
        >>> extractor = DLQContentExtractor()
        >>> result = extractor.extract(dlq_messages)
        >>> if result.has_output:
        ...     print(f"内容: {result.assistant_content[:100]}...")
    """

    __slots__ = ()  # 无实例属性，节省内存

    def extract(self, messages: Sequence[Any]) -> ExtractedContent:
        """从 DLQ 消息列表中提取内容

        使用流式处理方式，逐条解析消息并累积内容。
        支持处理未正常结束的消息流（例如用户中途停止）。

        Args:
            messages: DLQ 中的消息列表（SSE 编码字符串或 AG-UI 事件对象）

        Returns:
            提取的内容对象，包含 assistant_content 和 reasoning_content

        Note:
            - 即使消息流未正常结束（无 TEXT_MESSAGE_END），也会返回已累积的内容
            - 如果没有 message_id，会使用 "unknown" 作为默认值
        """
        result = ExtractedContent()

        # 使用局部变量避免重复属性查找
        current_message_id: str = ""
        current_content_parts: list[str] = []
        reasoning_parts: list[str] = []

        # 统计信息（用于日志）
        processed_count = 0
        skipped_count = 0

        for msg in messages:
            # 快速跳过特殊标记
            if msg in (EOD_CHUNK, HEARTBEAT_CHUNK):
                skipped_count += 1
                continue

            # 解析消息
            parsed_msg = self._parse_message(msg)
            if parsed_msg is None:
                continue

            # 获取事件类型
            event_type = self._get_event_type(parsed_msg)
            if event_type is None:
                continue

            processed_count += 1

            # 根据事件类型分发处理（使用 if-elif 链，因为事件类型有限）
            if event_type is EventType.TEXT_MESSAGE_CONTENT:
                # 最常见的事件类型，放在第一位
                delta = self._get_delta(parsed_msg)
                if delta:
                    current_content_parts.append(delta)
                    result.has_output = True
                    # 延迟获取 message_id
                    if not current_message_id:
                        current_message_id = self._get_message_id(parsed_msg) or _UNKNOWN_MESSAGE_ID

            elif event_type is EventType.THINKING_TEXT_MESSAGE_CONTENT:
                # reasoning 内容（第二常见）
                delta = self._get_delta(parsed_msg)
                if delta:
                    reasoning_parts.append(delta)
                    result.has_output = True

            elif event_type is EventType.TEXT_MESSAGE_START:
                # 开始新消息，保存之前的内容
                message_id = self._get_message_id(parsed_msg)
                if message_id:
                    if current_message_id and current_content_parts:
                        # 保存之前的消息
                        result.assistant_content = "".join(current_content_parts)
                        result.assistant_message_id = current_message_id
                        result.has_output = True
                    # 重置为新消息
                    current_message_id = message_id
                    current_content_parts = []

            elif event_type is EventType.TEXT_MESSAGE_END:
                # 消息结束，立即保存
                if current_content_parts:
                    result.assistant_content = "".join(current_content_parts)
                    result.assistant_message_id = current_message_id or _UNKNOWN_MESSAGE_ID
                    result.has_output = True

        # 处理未正常结束的消息流
        if current_content_parts and not result.assistant_content:
            result.assistant_content = "".join(current_content_parts)
            result.assistant_message_id = current_message_id or _UNKNOWN_MESSAGE_ID
            result.has_output = True

        # 合并 reasoning 内容
        if reasoning_parts:
            result.reasoning_content = ["".join(reasoning_parts)]

        # 记录提取结果日志
        logger.debug(
            "DLQ content extracted: has_output=%s, assistant_len=%d, reasoning_len=%d, "
            "processed=%d, skipped=%d, total=%d",
            result.has_output,
            len(result.assistant_content),
            len(result.reasoning_content),
            processed_count,
            skipped_count,
            len(messages),
        )

        return result

    def _parse_message(self, msg: Any) -> dict[str, Any] | Any | None:
        """解析消息，支持多种格式

        支持的格式:
            - SSE 字符串: "data: {...}\n\n"
            - 纯 JSON 字符串: "{...}"
            - 已解析的字典: {...}
            - AG-UI 事件对象: 具有 type 属性

        Args:
            msg: 原始消息（可能是 SSE 字符串、dict 或事件对象）

        Returns:
            解析后的字典或事件对象，解析失败返回 None

        Performance:
            - 优先检查最常见的情况（dict 和事件对象）
            - 使用 startswith 快速判断 SSE 格式
            - 避免重复的类型检查
        """
        # 快速路径：已经是字典或事件对象
        if isinstance(msg, dict):
            return msg
        if hasattr(msg, "type"):
            return msg

        # 字符串处理
        if isinstance(msg, str):
            return self._parse_string_message(msg)

        # bytes 处理
        if isinstance(msg, bytes):
            try:
                return self._parse_string_message(msg.decode("utf-8"))
            except (UnicodeDecodeError, AttributeError):
                return None

        return None

    def _parse_string_message(self, msg: str) -> dict[str, Any] | None:
        """解析字符串格式的消息

        Args:
            msg: 字符串消息

        Returns:
            解析后的字典，失败返回 None
        """
        # SSE 格式: "data: {...}"
        if msg.startswith(_SSE_DATA_PREFIX):
            json_str = msg[_SSE_DATA_PREFIX_LEN:].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return None

        # 尝试直接解析 JSON
        try:
            return json.loads(msg)
        except json.JSONDecodeError:
            return None

    def _get_event_type(self, msg: Any) -> EventType | None:
        """获取事件类型

        Args:
            msg: 已解析的消息（dict 或事件对象）

        Returns:
            EventType 枚举值，未找到返回 None
        """
        # AG-UI 事件对象有 type 属性
        if hasattr(msg, "type"):
            return msg.type

        # 字典形式
        if isinstance(msg, dict):
            type_value = msg.get("type")
            if type_value is not None:
                try:
                    return EventType(type_value)
                except ValueError:
                    return None

        return None

    def _get_message_id(self, msg: Any) -> str:
        """获取消息 ID

        Args:
            msg: 已解析的消息

        Returns:
            消息 ID 字符串，未找到返回空字符串
        """
        if hasattr(msg, "message_id"):
            return msg.message_id or ""

        if isinstance(msg, dict):
            return msg.get("message_id", "") or ""

        return ""

    def _get_delta(self, msg: Any) -> str:
        """获取 delta 内容

        Args:
            msg: 已解析的消息

        Returns:
            delta 内容字符串，未找到返回空字符串
        """
        if hasattr(msg, "delta"):
            return msg.delta or ""

        if isinstance(msg, dict):
            return msg.get("delta", "") or ""

        return ""
