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

Handoff 共享账本规则。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from aidev_agent.core.ag_ui.types import ActivityMessage, InfoMessage, ReasoningLangChainMessage

HANDOFF_SEARCH_TOOL_NAME = "handoff_search_history"
HANDOFF_READ_TOOL_NAME = "handoff_read_history"
HANDOFF_TOOL_NAMES = (HANDOFF_SEARCH_TOOL_NAME, HANDOFF_READ_TOOL_NAME)


def _is_internal_message(message: Any) -> bool:
    """Info/Activity/Reasoning 消息不进入模型视图，也不参与 handoff 账本。"""
    return isinstance(message, (ActivityMessage, InfoMessage, ReasoningLangChainMessage))


def ledger_messages(state: Dict[str, Any]) -> List[BaseMessage]:
    """从会话 state 中取出参与 handoff 的消息账本（过滤内部通知消息）。"""
    messages = state.get("messages") or []
    return [msg for msg in messages if not _is_internal_message(msg)]


def message_role(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, ToolMessage):
        return "tool"
    if isinstance(message, SystemMessage):
        return "system"
    return str(getattr(message, "type", "unknown"))


def message_text(message: BaseMessage) -> str:
    content = message.content
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    if isinstance(message, AIMessage) and message.tool_calls:
        calls = json.dumps(
            [{"name": call.get("name"), "args": call.get("args")} for call in message.tool_calls],
            ensure_ascii=False,
        )
        text = f"{text}\n(tool_calls: {calls})".strip()
    return text


def message_created_at(message: BaseMessage) -> str:
    kwargs = getattr(message, "additional_kwargs", None) or {}
    return str(kwargs.get("created_at") or "")


def find_message_index(messages: List[BaseMessage], message_id: str) -> int:
    if not message_id:
        return -1
    for idx, message in enumerate(messages):
        if getattr(message, "id", None) == message_id:
            return idx
    return -1


def tool_call_label(ledger: List[BaseMessage], index: int) -> str:
    """回查 tool 消息对应的调用，渲染为 工具名(参数)；查不到时返回空串。"""
    call_id = getattr(ledger[index], "tool_call_id", "")
    if not call_id:
        return ""
    for message in reversed(ledger[:index]):
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls:
            if call.get("id") == call_id:
                return f"{call.get('name')}({json.dumps(call.get('args') or {}, ensure_ascii=False)})"
    return ""


def message_header(ledger: List[BaseMessage], index: int) -> str:
    """消息前缀 [#序号|消息id|角色|创建时间]；tool 消息附带对应调用。"""
    message = ledger[index]
    created_at = message_created_at(message) or "-"
    header = f"[#{index}|{getattr(message, 'id', None) or '-'}|{message_role(message)}|{created_at}] "
    if isinstance(message, ToolMessage):
        label = tool_call_label(ledger, index)
        if label:
            header += f"(返回自: {label})\n"
    return header


def format_message(ledger: List[BaseMessage], index: int) -> str:
    """把账本第 index 条消息渲染为消息前缀 + 内容。"""
    return message_header(ledger, index) + message_text(ledger[index])


def active_round(handoff: Dict[str, Any]) -> Optional[Tuple[int, Dict[str, Any]]]:
    rounds = handoff.get("rounds") or []
    if not rounds:
        return None
    index = handoff.get("active_round")
    if not isinstance(index, int) or not 0 <= index < len(rounds):
        index = len(rounds) - 1
    return index, rounds[index]


def covered_end(messages: List[BaseMessage], round_data: Dict[str, Any]) -> int:
    """返回替换区间的排他上界，同时作为原文加载起点。失效 ID 不回退。"""
    until_id = round_data.get("searchable_until")
    if not until_id:
        return 0
    index = find_message_index(messages, until_id)
    if index < 0:
        raise ValueError("压缩偏移已失效，无法恢复上下文")
    return index + 1