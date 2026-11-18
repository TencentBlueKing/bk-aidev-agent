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

Handoff 历史检索/读取工具。

两个工具都通过 ``InjectedState`` 读取 ``state["messages"]`` 与 ``state["handoff"]``，
只访问被摘要替换的历史区间，不依赖 runtime backend，也不受 ``enable_runtime_tool`` 影响。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional, Tuple

from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.prebuilt import InjectedState

from aidev_agent.core.nodes.model.handoff_ledger import (
    HANDOFF_READ_TOOL_NAME,
    HANDOFF_SEARCH_TOOL_NAME,
    active_round,
    covered_end,
    find_message_index,
    format_message,
    ledger_messages,
    message_created_at,
    message_header,
    message_role,
    message_text,
)
from aidev_agent.core.tools.runtime_tools.utils import MAX_OUTPUT_LENGTH, truncate_if_too_long

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50
SNIPPET_LENGTH = 120
# 命中点之前保留的片段字符数
SNIPPET_LEADING = 40
# 单条消息分页读取的默认与最大字符数（留出前缀与分页说明的余量，避免触发整体截断）
DEFAULT_PAGE_CHARS = 20000
MAX_PAGE_CHARS = MAX_OUTPUT_LENGTH - 2000

SEARCH_TOOL_DESCRIPTION = (
    "检索已被上下文压缩替换的历史消息。支持按关键词（大小写不敏感）与可选的时间范围过滤，"
    "返回命中消息的账本序号、消息 id、角色、创建时间、命中处片段、命中字符位置 match_offset 与消息总长度 length；"
    "可将 match_offset 作为读取工具的 offset 定位原文。只覆盖压缩前被替换的历史区间。"
)
READ_TOOL_DESCRIPTION = (
    "按消息 id 区间读取已被上下文压缩替换的历史消息原文。区间会裁剪到可访问的历史范围内，结果中会说明实际读取的范围。"
    "只读取单条消息（省略 end_id）时支持按字符分页：offset 为起始字符位置，max_chars 为本次读取字符数，"
    "结果会给出总长度与下一页 offset。"
)


# ============================================================================
# 状态解析
# ============================================================================
def _accessible_ledger(state: Dict[str, Any]) -> Tuple[List[BaseMessage], int]:
    """与模型视图共享同一固定边界，不按条数猜测失效的消息 ID。"""
    ledger = ledger_messages(state)
    current = active_round(state.get("handoff") or {})
    return ledger, covered_end(ledger, current[1]) if current else 0


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        # 无时区的历史时间与查询时间统一按 UTC 解释。
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _in_time_range(created_at: str, start: Optional[datetime], end: Optional[datetime]) -> bool:
    parsed = _parse_time(created_at)
    if parsed is None:
        return True
    if start is not None and parsed < start:
        return False
    return end is None or parsed <= end


# ============================================================================
# 工具实现
# ============================================================================
def search_history(
    keyword: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    *,
    state: Dict[str, Any] = None,
) -> str:
    """在被替换的历史区间内按关键词/时间范围检索。"""
    state = state or {}
    try:
        ledger, upper = _accessible_ledger(state)
    except ValueError as exc:
        return str(exc)
    if upper <= 0:
        return "当前会话没有可检索的已压缩历史。"

    keyword = (keyword or "").strip()
    if not keyword:
        return "关键词不能为空。"

    start_dt, end_dt = _parse_time(start_time), _parse_time(end_time)
    if (start_time is not None and start_dt is None) or (end_time is not None and end_dt is None):
        return "时间参数必须是有效的 ISO 8601 时间。"
    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        return "起始时间不能晚于结束时间。"
    results: List[Dict[str, Any]] = []
    for index in range(upper):
        message = ledger[index]
        text = message_text(message)
        match_offset = text.lower().find(keyword.lower())
        if match_offset < 0:
            continue
        created_at = message_created_at(message)
        if (start_dt or end_dt) and not created_at:
            # 老会话缺时间戳：退化为纯关键词检索
            logger.debug("【Handoff】消息 %s 缺少 created_at，时间范围过滤退化", index)
        elif not _in_time_range(created_at, start_dt, end_dt):
            continue
        results.append(
            {
                "index": index,
                "id": getattr(message, "id", None),
                "role": message_role(message),
                "snippet": _snippet(text, match_offset),
                "match_offset": match_offset,
                "length": len(text),
                "created_at": created_at,
            }
        )
        if len(results) >= min(max(1, limit), MAX_SEARCH_LIMIT):
            break

    if not results:
        return f"在已压缩的历史区间内没有找到包含「{keyword}」的消息。"
    return truncate_if_too_long(json.dumps({"total": len(results), "results": results}, ensure_ascii=False))


def _snippet(text: str, match_offset: int) -> str:
    """以命中点为中心截取片段，前后被省略时用 … 标记。"""
    start = max(0, match_offset - SNIPPET_LEADING)
    end = start + SNIPPET_LENGTH
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def _read_page(ledger: List[BaseMessage], index: int, offset: int, max_chars: int) -> str:
    """读取单条消息 [offset, offset + max_chars) 区间，附总长度与续读位置。"""
    text = message_text(ledger[index])
    total = len(text)
    if offset >= total and total:
        return f"offset 超出消息长度（共 {total} 字符）。"
    end = min(total, offset + max_chars)
    output = message_header(ledger, index) + text[offset:end]
    if offset == 0 and end == total:
        return output
    tail = f"下一页 offset={end}" if end < total else "已读到末尾"
    return f"{output}\n\n[字符 {offset}-{end} / 共 {total}；{tail}]"


def read_history(
    start_id: str,
    end_id: str = "",
    offset: int = 0,
    max_chars: int = DEFAULT_PAGE_CHARS,
    *,
    state: Dict[str, Any] = None,
) -> str:
    """按消息 id 区间读取被替换历史区间的原文；单条读取时支持按字符分页。"""
    state = state or {}
    try:
        ledger, upper = _accessible_ledger(state)
    except ValueError as exc:
        return str(exc)
    if upper <= 0:
        return "当前会话没有可读取的已压缩历史。"

    start_index = find_message_index(ledger, start_id)
    if start_index < 0:
        return f"未找到消息 id: {start_id}"
    end_index = find_message_index(ledger, end_id) if end_id else start_index
    if end_index < 0:
        return f"未找到消息 id: {end_id}"
    if end_index < start_index:
        start_index, end_index = end_index, start_index
    single = start_index == end_index
    if offset < 0 or max_chars <= 0:
        return "offset 不能为负数，max_chars 必须大于 0。"
    if offset and not single:
        return "offset 仅支持单条消息读取，请省略 end_id。"

    if start_index >= upper:
        return f"请求区间不在已压缩历史内（可访问范围 [#0-#{upper - 1}]），该部分原文仍在当前上下文中。"
    clipped_start = start_index
    clipped_end = min(end_index, upper - 1)
    notes: List[str] = []
    if clipped_end != end_index:
        notes.append(f"请求区间已裁剪到可访问范围 [#{clipped_start}-#{clipped_end}]")

    if single:
        return _read_page(ledger, start_index, offset, min(max_chars, MAX_PAGE_CHARS))

    output = "\n\n".join(format_message(ledger, index) for index in range(clipped_start, clipped_end + 1))
    if len(output) > MAX_OUTPUT_LENGTH:
        notes.append("内容超长，可逐条读取（省略 end_id）并用 offset 分页")
    if notes:
        output = f"{output}\n\n[{'；'.join(notes)}]"
    return truncate_if_too_long(output)


# ============================================================================
# 工具构造
# ============================================================================
def make_handoff_search_history_tool() -> BaseTool:
    def handoff_search_history(
        keyword: Annotated[str, "要检索的关键词"],
        limit: Annotated[int, "最多返回的命中条数"] = DEFAULT_SEARCH_LIMIT,
        start_time: Annotated[Optional[str], "可选，起始时间（ISO 8601）"] = None,
        end_time: Annotated[Optional[str], "可选，结束时间（ISO 8601）"] = None,
        state: Annotated[dict, InjectedState] = None,
    ) -> str:
        """检索已被上下文压缩替换的历史消息。"""
        return search_history(keyword, limit, start_time, end_time, state=state)

    return StructuredTool.from_function(
        name=HANDOFF_SEARCH_TOOL_NAME,
        description=SEARCH_TOOL_DESCRIPTION,
        func=handoff_search_history,
    )


def make_handoff_read_history_tool() -> BaseTool:
    def handoff_read_history(
        start_id: Annotated[str, "起始消息 id（含）"],
        end_id: Annotated[str, "结束消息 id（含），省略时只读取单条"] = "",
        offset: Annotated[int, "单条读取时的起始字符位置"] = 0,
        max_chars: Annotated[int, f"单条读取时本次读取的字符数，上限 {MAX_PAGE_CHARS}"] = DEFAULT_PAGE_CHARS,
        state: Annotated[dict, InjectedState] = None,
    ) -> str:
        """按消息 id 区间读取已被上下文压缩替换的历史原文。"""
        return read_history(start_id, end_id, offset, max_chars, state=state)

    return StructuredTool.from_function(
        name=HANDOFF_READ_TOOL_NAME,
        description=READ_TOOL_DESCRIPTION,
        func=handoff_read_history,
    )
