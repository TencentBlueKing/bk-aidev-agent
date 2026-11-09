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

Handoff 上下文压缩

该模块负责：
- 触发判定（沿用 llm_token_limit - token_limit_margin 预算口径）
- 结构化交接生成（模型输出 JSON；已有交接条目与关键原文按编号续留，用户输入原文拼接）
- LLM 输入视图替换（交接文本 + 原始结构的尾部消息，账本只读）
- 摘要与偏移随会话 state 持久化（多轮追加）
- 失败重试与 INFO 事件
- 历史检索/读取工具的可见性过滤
"""

from __future__ import annotations

import concurrent.futures
import contextvars
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from aidev_agent.core.ag_ui.types import (
    CONTEXT_COMPRESSION_TAG,
    CustomMessageType,
    InfoMessage,
)
from aidev_agent.packages.langgraph.streaming.utils import conditional_dispatch_custom_event
from aidev_agent.packages.opentelemetry.context_obs import (
    CompressionCall,
    observe_compression_call,
    record_compression_skipped,
    resolve_model_name,
)
from aidev_agent.pydantic_models import HandoffSettings

from .basic_middleware import extract_tool_calls_from_messages
from .handoff_ledger import (
    HANDOFF_READ_TOOL_NAME,
    HANDOFF_TOOL_NAMES,
    active_round,
    covered_end,
    format_message,
    ledger_messages,
    message_header,
    message_text,
)
from .pydantic_models import NextFunction, ProcessorContext
from .token_compression import BaseCompressionMiddleware, _compression_executor

logger = logging.getLogger(__name__)

# 交接条目所属区块（顺序即输出顺序）
HANDOFF_ITEM_SECTIONS: Tuple[Tuple[str, str], ...] = (
    ("completed", "已完成事项"),
    ("in_progress", "进行中事项"),
    ("todo", "待办事项"),
    ("key_context", "关键上下文"),
)
_ITEM_SECTION_KEYS = frozenset(key for key, _ in HANDOFF_ITEM_SECTIONS)

_REQUIRED_SUMMARY_KEYS = frozenset({"task_goal", "items", "key_message_indexes"})
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)

HANDOFF_DONE_TEXT = "上下文已压缩（Handoff）"
HANDOFF_FAILED_TEXT = "上下文压缩失败，请重试"


_CJK_RE = re.compile(r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]")


def _estimate_tokens(text: str) -> int:
    """粗略估算 token：中日韩字符按 1 个/token，其余按 4 字符/token。"""
    cjk = len(_CJK_RE.findall(text))
    return cjk + (len(text) - cjk + 3) // 4


# 本地估算低于预算的该比例时不做精确计数：估算对代码/JSON 可能偏低，留足余量避免漏触发
_ESTIMATE_SKIP_RATIO = 0.7


def _estimate_tool_tokens(tools: Sequence[BaseTool]) -> int:
    """估算绑定给模型的工具定义 token；工具列表在构造期固定，只估算一次。"""
    schemas = []
    for tool in tools:
        try:
            schemas.append(convert_to_openai_tool(tool))
        except Exception:  # noqa: BLE001 - 个别工具无法转换时不影响整体估算
            logger.warning("【Handoff】工具 %s 无法转换为 schema，不计入 token 估算", getattr(tool, "name", tool))
    return _estimate_tokens(json.dumps(schemas, ensure_ascii=False)) if schemas else 0


def _skip(reason: str) -> None:
    record_compression_skipped(compression_type="handoff", reason=reason)


@dataclass(frozen=True)
class HandoffBudget:
    """单次压缩的 token 预算。

    total: 整个上下文上限（token_limit - token_margin）
    base: 空交接、空尾部时的视图 token，即系统提示词、工具描述等固定开销
    summary: 交接文本预算，(total - base) × summary_ratio
    tail: 保留尾部预算，total - base - summary
    """

    total: int
    base: int
    summary: int
    tail: int


class HandoffCompressionError(RuntimeError):
    """压缩未提交替换。

    reason 为低基数原因码，用于跳过指标与压缩 span 的 context.compression.reason。
    _compress 内抛出的该异常由 _run 吸收：回到原视图并套用已生效的交接；其余异常视为压缩失败。
    """

    retryable = True

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


SUMMARY_SYSTEM_PROMPT = """你是一个会话交接（Handoff）生成器。用户与智能体的会话即将达到上下文预算上限，\
需要你把输入中的历史压缩成结构化交接数据，供智能体此后继续任务时使用。

输入说明：
- 「已有交接条目」每行以 [条目ID|区块] 开头；「用户输入原文」「已保留的关键原文」与「新增原文」每条消息以 \
[#序号|消息id|角色|创建时间] 开头，序号全局唯一。
- 最近几条用户输入会由系统原文保留，无需转述，也不要放入 key_message_indexes。
- 「移出原文保留的用户输入」是此前由系统原文保留、本次起不再自动保留的用户输入，其中的约束与参数不能丢失：\
需要原文的列入 key_message_indexes，其余提炼为条目并在 source_indexes 标注来源。

只输出一个 JSON 对象，不要输出解释、Markdown 或额外前后缀，格式如下：
{{
  "task_goal": "当前任务目标",
  "items": [{{"id": "R1-3"}}, {{"section": "completed", "text": "...", "source_indexes": [12]}}],
  "key_message_indexes": [5, 47]
}}

要求：
1. items：交接条目列表，输出顺序即展示顺序。
   - 保留已有交接条目：只写 {{"id": "条目ID"}}，系统按 ID 原样复制，不要附带 section/text；\
已无用或已被取代的条目不要列出。需要修改已有条目时，不写其 id，改为新增一条。
   - 新增条目：写 {{"section": ..., "text": ...}}，不写 id；section 只能是 completed（已完成事项）、\
in_progress（进行中事项）、todo（待办事项）、key_context（关键决策、约束、参数、文件/工具状态等），text 不能为空。
   - source_indexes（可选）：条目概括自的原文 #序号（任意角色），系统会附上通过历史读取工具查看全文的提示；\
概括了较长原文、后续可能需要细节时应填写。
2. 新增条目只记录新增原文中产生的信息，不要复述已保留条目。
3. key_message_indexes：需要原文保留的消息 #序号，只能取自「已保留的关键原文」「移出原文保留的用户输入」或「新增原文」，\
例如关键工具输出；已保留的关键原文若不再列出即被丢弃。被选中的原文会直接拼接，无需在条目中复述。
   以下原文需要列入 key_message_indexes（含已保留的同类原文）：
   - activate_skill 工具返回的技能文档（技能激活结果）
   - tool_describe 工具返回的工具说明
4. task_goal 是用户当前仍在推进的目标：交接是在同一任务进行中发生的，「当前任务目标」默认继续有效，\
仅当用户输入明确变更目标或任务已全部完成时才修改，不要因为发生过交接就把它视为过去的目标。
5. 只保留后续确实需要的信息，不要编造输入中不存在的事实。
6. 数量与名单（如资源数量、实例/对象列表）必须按资源逐项列出，每项标注数据来源 #序号；\
tool 消息开头的「(返回自: 工具名(参数))」标明了该返回对应的调用，按它归属资源；同一资源多次查询时以最后一次返回为准。
7. assistant 消息中的推断、结论或对工具返回的描述，若无工具返回原文直接佐证，必须以「助手判断：」开头写入条目，\
并标注来源 #序号，不能写成事实。
8. 第 6、7 条的来源 #序号写入该条目的 source_indexes，无需列入 key_message_indexes。
9. 交接总长度（含关键原文）控制在约 {target_tokens} token 以内。"""

SUMMARY_USER_PROMPT = """以下是需要交接的会话历史：

{transcript}

请输出交接 JSON。"""

SUMMARY_RETRY_SUFFIX = (
    "\n\n上一版交接内容约 {tokens} token，超过目标上限 {target_tokens} token，"
    "请精简新增条目文字并减少 items 与 key_message_indexes，仍只输出 JSON。"
    "activate_skill 和 tool_describe 根据当前进度考虑和相关性考虑改写为条目"
)


# ============================================================================
# 交接解析与渲染
# ============================================================================
def parse_handoff_summary(
    text: Any,
    *,
    previous_items: Dict[str, Dict[str, str]],
    valid_indexes: Set[int],
    round_no: int,
    source_limit: int = 0,
) -> Optional[Dict[str, Any]]:
    """解析模型输出的交接 JSON。

    返回 {"task_goal", "items", "key_message_indexes"}；带 id 的条目按 ID 原样复制已有内容，不带 id 的为新条目。
    新条目的 source_indexes 只保留 [0, source_limit) 内的序号（历史读取工具可访问的区间）。
    结构不符时返回 None（调用方按「响应无法解析」重试）；未知条目 ID、越界序号直接丢弃。
    """
    if not isinstance(text, str) or not text.strip():
        return None
    fenced = _JSON_FENCE_RE.match(text)
    try:
        data = json.loads(fenced.group(1) if fenced else text.strip())
    except ValueError:
        return None
    # 三个字段必须出现（值可为空）；缺失视为无效响应进入重试，避免 {} 或 {"error": ...} 被当成空交接提交
    if not isinstance(data, dict) or not _REQUIRED_SUMMARY_KEYS.issubset(data):
        return None
    task_goal = data["task_goal"]
    raw_items = data["items"]
    indexes = data["key_message_indexes"]
    if not isinstance(task_goal, str) or not isinstance(raw_items, list) or not isinstance(indexes, list):
        return None

    items: List[Dict[str, str]] = []
    kept: Set[str] = set()
    created = 0
    for item in raw_items:
        if not isinstance(item, dict):
            return None
        item_id = item.get("id")
        if item_id is not None:
            # 带 id 一律按已有条目原样复制，忽略模型附带内容；未知或重复 id 丢弃
            if item_id in previous_items and item_id not in kept:
                kept.add(item_id)
                items.append(dict(previous_items[item_id]))
            continue
        text_value = item.get("text")
        if item.get("section") not in _ITEM_SECTION_KEYS or not isinstance(text_value, str) or not text_value.strip():
            return None
        created += 1
        new_item: Dict[str, Any] = {
            "id": f"R{round_no}-{created}",
            "section": item["section"],
            "text": text_value.strip(),
        }
        sources = item.get("source_indexes")
        if isinstance(sources, list):
            sources = sorted({index for index in sources if _valid_index(index) and 0 <= index < source_limit})
            if sources:
                new_item["source_indexes"] = sources
        items.append(new_item)
    return {
        "task_goal": task_goal.strip(),
        "items": items,
        "key_message_indexes": sorted({index for index in indexes if _valid_index(index) and index in valid_indexes}),
    }


def _valid_index(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _item_text(ledger: List[BaseMessage], item: Dict[str, Any]) -> str:
    """条目文本；带来源时附上来源序号与读取工具提示。"""
    refs = [f'#{index}(id="{getattr(ledger[index], "id", None) or "-"}")' for index in item.get("source_indexes") or []]
    if not refs:
        return item["text"]
    return f"{item['text']}（原文 {'、'.join(refs)}，可用 {HANDOFF_READ_TOOL_NAME} 查看全文）"


def _key_message_text(ledger: List[BaseMessage], index: int, char_limit: int) -> str:
    """关键原文超过 char_limit 时截断，并提示通过历史读取工具续读。"""
    text = message_text(ledger[index])
    if len(text) <= char_limit:
        return format_message(ledger, index)
    message_id = getattr(ledger[index], "id", None) or "-"
    return (
        message_header(ledger, index)
        + text[:char_limit]
        + f'…（已截断，共 {len(text)} 字符，可用 {HANDOFF_READ_TOOL_NAME}(start_id="{message_id}", '
        + f"offset={char_limit}) 续读）"
    )


def render_handoff_summary(
    parsed: Dict[str, Any],
    ledger: List[BaseMessage],
    user_indexes: List[int],
    key_message_char_limit: int = 30000,
) -> str:
    """把交接数据渲染为模型可读文本：条目区块 + 关键原文 + 最近用户输入原文。"""
    blocks = [f"## 任务目标\n{parsed['task_goal'] or '无'}"]
    for section, title in HANDOFF_ITEM_SECTIONS:
        body = "\n".join(f"- {_item_text(ledger, item)}" for item in parsed["items"] if item["section"] == section)
        blocks.append(f"## {title}\n{body or '无'}")
    key_indexes = [index for index in parsed["key_message_indexes"] if index not in user_indexes]
    if key_indexes:
        blocks.append(
            "## 关键原文\n"
            + "\n".join(_key_message_text(ledger, index, key_message_char_limit) for index in key_indexes)
        )
    if user_indexes:
        blocks.append("## 最近用户输入\n" + "\n".join(format_message(ledger, index) for index in user_indexes))
    return "\n\n".join(blocks)


def recent_user_indexes(ledger: List[BaseMessage], limit: int, end: int) -> List[int]:
    """整个账本中最近 limit 条用户输入里，位于保留尾部之前（< end）的序号。"""
    if limit <= 0:
        return []
    users = [index for index, message in enumerate(ledger) if isinstance(message, HumanMessage)][-limit:]
    return [index for index in users if index < end]


# ============================================================================
# 交接轮次的读写：持久化用消息 id（跨请求时账本可能被重建），单次处理内账本不变，全程用序号
# ============================================================================
@dataclass
class LoadedRound:
    """上一轮交接按当前账本换算为序号后的视图。"""

    task_goal: str
    items: Dict[str, Dict[str, Any]]
    key_indexes: List[int]
    covered_end: int
    context_end: int


def load_round(ledger: List[BaseMessage], round_data: Dict[str, Any]) -> LoadedRound:
    """读入边界：一次性把上一轮存储的消息 id 换成当前账本序号，找不到的 id 丢弃。"""
    index_of = {str(message.id): index for index, message in enumerate(ledger) if getattr(message, "id", None)}

    def to_indexes(message_ids: Any) -> List[int]:
        return sorted({index_of[mid] for mid in message_ids or [] if mid in index_of})

    items: Dict[str, Dict[str, Any]] = {}
    for item in round_data.get("items") or []:
        loaded = {key: value for key, value in item.items() if key != "source_ids"}
        sources = to_indexes(item.get("source_ids"))
        if sources:
            loaded["source_indexes"] = sources
        items[item["id"]] = loaded
    return LoadedRound(
        task_goal=round_data.get("task_goal") or "",
        items=items,
        key_indexes=to_indexes(round_data.get("key_message_ids")),
        covered_end=covered_end(ledger, round_data),
        context_end=index_of.get(round_data.get("context_end_id") or "", len(ledger) - 1),
    )


def dump_round(
    ledger: List[BaseMessage], parsed: Dict[str, Any], summary: str, start: int, trigger_tokens: int
) -> Dict[str, Any]:
    """写回边界：把本轮交接中的序号统一换成消息 id 持久化。"""

    def to_id(index: int) -> str:
        return str(getattr(ledger[index], "id", None) or "")

    def to_ids(indexes: List[int]) -> List[str]:
        return [message_id for message_id in map(to_id, indexes) if message_id]

    items = []
    for item in parsed["items"]:
        stored = {key: value for key, value in item.items() if key != "source_indexes"}
        if item.get("source_indexes"):
            stored["source_ids"] = to_ids(item["source_indexes"])
        items.append(stored)
    return {
        "summary": summary,
        "task_goal": parsed["task_goal"],
        "items": items,
        "key_message_ids": to_ids(parsed["key_message_indexes"]),
        "searchable_until": to_id(start - 1) if start else "",
        "context_end_id": to_id(len(ledger) - 1) if ledger else "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trigger_tokens": trigger_tokens,
    }


def _previous_round_input(
    ledger: List[BaseMessage], previous: LoadedRound, user_indexes: List[int], dropped_users: List[int]
) -> Tuple[Dict[str, Dict[str, Any]], List[int], str]:
    """返回已有交接条目（按 ID）、模型可引用的已有原文序号，以及供模型阅读的编号文本。

    user_indexes 为已覆盖区间内仍在原文保留窗口的用户输入，以原文给出，使模型从用户原话确认当前目标；
    dropped_users 为上一轮原文保留、本轮移出窗口的用户输入，单独列出交由模型续留或提炼。
    """
    items, key_indexes = previous.items, previous.key_indexes
    lines = [f"## 当前任务目标（进行中，默认继续有效）\n{previous.task_goal or '无'}"]
    if user_indexes:
        lines.append("\n## 用户输入原文\n" + "\n".join(format_message(ledger, index) for index in user_indexes))
    lines.append("\n## 已有交接条目")
    lines.extend(f"[{item['id']}|{item['section']}] {_item_text(ledger, item)}" for item in items.values())
    if not items:
        lines.append("无")
    lines.append("\n## 已保留的关键原文")
    lines.extend(format_message(ledger, index) for index in key_indexes)
    if not key_indexes:
        lines.append("无")
    if dropped_users:
        lines.append("\n## 移出原文保留的用户输入")
        lines.extend(format_message(ledger, index) for index in dropped_users)
    return items, [*key_indexes, *dropped_users], "\n".join(lines)


# ============================================================================
# 视图构建
# ============================================================================


def _snapshot_view(ctx: ProcessorContext) -> Callable[[], None]:
    """记录当前视图，返回把 variables 与 _handoff_applied 还原到该时刻的函数。"""
    previous_variables = dict(ctx.variables)
    previous_applied = ctx.metadata.get("_handoff_applied", False)
    previous_tool_messages = ctx.metadata.get("tool_messages")

    def restore() -> None:
        ctx.variables.clear()
        ctx.variables.update(previous_variables)
        ctx.metadata["_handoff_applied"] = previous_applied
        if previous_tool_messages is None:
            ctx.metadata.pop("tool_messages", None)
        else:
            ctx.metadata["tool_messages"] = previous_tool_messages

    return restore


def _set_handoff_view(ctx: ProcessorContext, summary: str, ledger: List[BaseMessage], start: int) -> None:
    """交接视图：交接文本作为首条用户消息，ledger[start:] 保持原始消息结构。

    尾部按最后一条用户消息拆分：之前进入 chat_history，之后的 AI/Tool 进入 agent_scratchpad；
    尾部没有用户消息时交接文本即为 query，工具循环照常以原始消息继续。
    """
    tail = [message for message in ledger[start:] if not isinstance(message, SystemMessage)]
    last_human = next((index for index in range(len(tail) - 1, -1, -1) if isinstance(tail[index], HumanMessage)), -1)
    if last_human < 0:
        history: List[BaseMessage] = []
        query: Any = summary
    else:
        history = [HumanMessage(content=summary), *tail[:last_human]]
        query = tail[last_human].content
    tool_messages = tail[last_human + 1 :]
    structured = isinstance(ctx.variables.get("agent_scratchpad"), str)
    ctx.variables["chat_history"] = history
    ctx.variables["query"] = query
    ctx.variables["agent_scratchpad"] = extract_tool_calls_from_messages(tool_messages) if structured else tool_messages
    ctx.metadata["tool_messages"] = tool_messages
    ctx.metadata["_handoff_applied"] = True


# ============================================================================
# 历史检索工具可见性
# ============================================================================
class HandoffToolsMiddleware:
    """本次上下文未被交接替换时，把历史检索/读取工具从可用工具列表中剔除。

    依据交接压缩中间件设置的 _handoff_applied 标记（variable 链先于 tool 链执行），
    覆盖已有交接与本次刚生成的交接两种情况，不读写 ctx.state。
    """

    def __init__(self, tool_names: Tuple[str, ...] = HANDOFF_TOOL_NAMES) -> None:
        self.tool_names = set(tool_names)

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        if not ctx.metadata.get("_handoff_applied"):
            ctx.tools = [tool for tool in ctx.tools if getattr(tool, "name", None) not in self.tool_names]
        next()


# ============================================================================
# Handoff 压缩中间件
# ============================================================================
class HandoffCompressionMiddleware(BaseCompressionMiddleware):
    """Handoff 压缩中间件：触发判定、摘要生成、视图替换与状态提交。

    由模型节点在启用 Handoff 时注册，替代原有压缩链路。

    Args:
        settings: Handoff 配置
        token_limit / token_margin: 与既有压缩同口径的预算
        timeout: 单次摘要请求等待上限（秒）
    """

    def __init__(
        self,
        settings: HandoffSettings,
        *,
        token_limit: Optional[int] = None,
        token_margin: int = 100,
        timeout: float = 60,
        tools: Sequence[BaseTool] = (),
    ) -> None:
        super().__init__(token_limit=token_limit, token_margin=token_margin)
        self.settings = settings
        self.timeout = timeout
        # 工具定义同样占用上下文：计入触发判断、预算与前后 token
        self.tool_tokens = _estimate_tool_tokens(tools)

    def _count_tokens(self, ctx: ProcessorContext) -> Optional[int]:
        """当前视图的上下文 token：消息精确计数 + 工具定义估算。"""
        tokens = self._try_get_token_len(ctx)
        return None if tokens is None else tokens + self.tool_tokens

    def _estimate_context_tokens(self, ctx: ProcessorContext) -> Optional[int]:
        """本地粗略估算当前视图 token（不调用模型计数），渲染失败时返回 None。"""
        if ctx.chat_prompt_template is None:
            return None
        try:
            messages = ctx.chat_prompt_template._format_prompt_with_error_handling(ctx.variables).messages
        except Exception:  # noqa: BLE001 - 估算失败时退回精确计数
            return None
        return sum(_estimate_tokens(message_text(message)) for message in messages) + self.tool_tokens

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------
    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        restore = _snapshot_view(ctx)
        # 单次处理内账本与已有交接状态都不变，只取一次；提交新一轮时整体替换 state["handoff"]，不原地修改
        ledger = ledger_messages(ctx.state)
        handoff = ctx.state.get("handoff") or {}
        try:
            if not self._run(ctx, ledger, handoff):
                # 本轮交接未提交：回到原视图，再套用已生效的交接
                restore()
                self._apply_view(ctx, ledger, handoff)
        except Exception as exc:
            restore()
            _emit_info(ctx, HANDOFF_FAILED_TEXT, persist=False)
            raise HandoffCompressionError("handoff_failed", "Handoff 压缩失败，原上下文未替换，请重试") from exc
        next()

    def _run(self, ctx: ProcessorContext, ledger: List[BaseMessage], handoff: Dict[str, Any]) -> bool:
        """返回 False 表示尝试了压缩但未提交，由调用方统一恢复视图。"""
        self._apply_view(ctx, ledger, handoff)
        if self.token_limit is None:
            return True
        budget = self.token_limit - self.token_margin
        # 先用本地估算粗筛，明显未接近预算时不发起精确计数，避免每次模型调用都请求计数服务
        estimated = self._estimate_context_tokens(ctx)
        if estimated is not None and estimated < budget * _ESTIMATE_SKIP_RATIO:
            return True
        trigger_tokens = self._count_tokens(ctx)
        if trigger_tokens is None:
            _skip("token_count_unavailable")
            return True
        if trigger_tokens < budget:
            return True
        # 一次压缩记录一个 span：未提交时上下文保持原样，前后 token 相同
        # 未交接的异常穿过 span，使其标记为 ERROR 并记录 exception 事件；error.type 取原因码
        try:
            with observe_compression_call(module="handoff", model=resolve_model_name(ctx.llm)) as call:
                call.set_result(applied=False, before_tokens=trigger_tokens, after_tokens=trigger_tokens)
                try:
                    self._compress(ctx, ledger, handoff, trigger_tokens, call)
                except HandoffCompressionError as exc:
                    call.set_error(exc.reason)
                    raise
        except HandoffCompressionError as exc:
            _skip(exc.reason)
            logger.info("【Handoff】本轮未交接（%s）：%s", exc.reason, exc)
            return False
        return True

    @staticmethod
    def _apply_view(ctx: ProcessorContext, ledger: List[BaseMessage], handoff: Dict[str, Any]) -> None:
        """存在已生效的交接时套用其视图。"""
        if not handoff.get("rounds"):
            return
        _, current_round = active_round(handoff)
        _set_handoff_view(ctx, current_round.get("summary") or "", ledger, covered_end(ledger, current_round))

    def _measure(self, ctx: ProcessorContext, ledger: List[BaseMessage], summary: str, start: int) -> int:
        """以给定交接文本与尾部起点设置视图并计 token；不可计数时放弃本轮交接。"""
        _set_handoff_view(ctx, summary, ledger, start)
        tokens = self._count_tokens(ctx)
        if tokens is None:
            raise HandoffCompressionError("compressed_token_count_unavailable", "交接视图无法计算 token")
        return tokens

    def _tail_start(self, ledger: List[BaseMessage], groups: List[int], minimum: int, tail_budget: int) -> int:
        """确定保留尾部的起点：先取最后 keep_last 个完整消息组（不早于 minimum），
        再从前往后整组剔除，直到尾部同时满足字符上限与估算 token 不超过 tail_budget。

        token 按字符粗略估算，不调用模型计数，避免高并发下逐次渲染计数的开销；最终整体超限由提交前校验兜底。
        """
        keep_last = self.settings.keep_last
        start = groups[max(0, len(groups) - keep_last)] if keep_last > 0 else len(ledger)
        start = max(start, minimum)
        # 逐条长度 + 换行分隔，从前向后剔除整组，避免每次重新拼接尾部
        texts = [
            "" if isinstance(message, SystemMessage) else format_message(ledger, index)
            for index, message in enumerate(ledger)
        ]
        chars = [len(text) + 1 if text else 0 for text in texts]
        tokens = [_estimate_tokens(text) for text in texts]
        total_chars, total_tokens = sum(chars[start:]), sum(tokens[start:])

        def fits() -> bool:
            return total_chars <= self.settings.tail_char_limit + 1 and total_tokens <= tail_budget

        for group_start in groups:
            if fits():
                break
            if group_start <= start:
                continue
            total_chars -= sum(chars[start:group_start])
            total_tokens -= sum(tokens[start:group_start])
            start = group_start
        else:
            if not fits():
                start = len(ledger)
        return start

    def _plan_budget(self, ctx: ProcessorContext, ledger: List[BaseMessage]) -> HandoffBudget:
        """压缩开始时一次性确定预算，后续尾部选择、摘要目标与最终校验都只读这一份。"""
        base = self._measure(ctx, ledger, "", len(ledger))
        total = self.token_limit - self.token_margin
        summary = int((total - base) * self.settings.summary_ratio)
        if summary <= 0:
            # 固定开销（系统提示词、工具描述等）本身已占满预算，压缩历史无法解决
            raise HandoffCompressionError("token_budget_exceeded", "固定开销已占满上下文预算")
        return HandoffBudget(total=total, base=base, summary=summary, tail=total - base - summary)

    # ------------------------------------------------------------------
    # 摘要生成
    # ------------------------------------------------------------------
    def _compress(
        self,
        ctx: ProcessorContext,
        ledger: List[BaseMessage],
        handoff: Dict[str, Any],
        trigger_tokens: int,
        call: CompressionCall,
    ) -> None:
        """先按预留摘要预算确定保留尾部，再只对尾部之前的区间生成交接，两者互不重叠。

        任一环节无法完成交接时抛出 HandoffCompressionError（带原因码），由 _run 吸收。
        """
        # 消息分组起点：每条非 System/Tool 消息开启一组，AI 调用与后续 Tool 结果保持完整；
        # 账本不变，只算一次，供尾部选择与候选起点共用
        groups = [
            index for index, message in enumerate(ledger) if not isinstance(message, (SystemMessage, ToolMessage))
        ]
        if not groups:
            raise HandoffCompressionError("no_context", "没有可交接的上下文")
        rounds: List[Dict[str, Any]] = handoff.get("rounds") or []
        previous = load_round(ledger, active_round(handoff)[1]) if rounds else None
        summary_start = previous.covered_end if previous else 0
        budget = self._plan_budget(ctx, ledger)
        start = self._tail_start(ledger, groups, summary_start, budget.tail)
        # 无新增区间时，若存在上一轮交接则仅对其重新筛选，否则无可压缩内容
        if start <= summary_start and not rounds:
            raise HandoffCompressionError("nothing_to_compress", "没有新增可交接区间")

        result = self._summarize_with_retry(
            ctx, ledger, budget.summary, len(rounds) + 1, summary_start, start, previous
        )
        if result is None:
            raise HandoffCompressionError("summary_retry_exhausted", "摘要生成重试耗尽")
        summary, parsed = result
        compressed_tokens = self._measure(ctx, ledger, summary, start)
        if compressed_tokens > budget.total:
            raise HandoffCompressionError("token_budget_exceeded", "交接后上下文仍超出预算")

        call.set_result(applied=True, before_tokens=trigger_tokens, after_tokens=compressed_tokens)
        new_round = dump_round(ledger, parsed, summary, start, trigger_tokens)
        handoff = {**handoff, "rounds": [*rounds, new_round], "active_round": len(rounds)}
        ctx.metadata["_handoff_state_update"] = handoff
        self._record_compression(ctx, "Handoff", trigger_tokens - compressed_tokens)
        _emit_info(ctx, HANDOFF_DONE_TEXT, persist=True)
        logger.info("【Handoff】交接完成：覆盖 %d 条，%d -> %d token", start, trigger_tokens, compressed_tokens)

    def _summarize_with_retry(
        self,
        ctx: ProcessorContext,
        ledger: List[BaseMessage],
        target_tokens: int,
        round_no: int,
        start: int,
        end: int,
        previous: Optional[LoadedRound],
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """对上一轮交接 + ledger[start:end] 生成交接 JSON，返回渲染文本与解析结果。"""
        user_indexes = recent_user_indexes(ledger, self.settings.keep_user_messages, end)
        previous_items: Dict[str, Dict[str, Any]] = {}
        valid_indexes = set(range(start, end))
        sections: List[str] = []
        if previous:
            # 上一轮的原文保留窗口由当时的账本末尾与覆盖边界（即 start）重算，无需持久化
            previous_window = recent_user_indexes(
                ledger[: previous.context_end + 1], self.settings.keep_user_messages, start
            )
            dropped_users = [index for index in previous_window if index not in user_indexes]
            previous_items, previous_keys, previous_text = _previous_round_input(
                ledger, previous, [index for index in user_indexes if index < start], dropped_users
            )
            valid_indexes.update(previous_keys)
            sections.append(previous_text)
        sections.append(
            "## 新增原文\n" + ("\n".join(format_message(ledger, index) for index in range(start, end)) or "无")
        )
        user_prompt = SUMMARY_USER_PROMPT.format(transcript="\n\n".join(sections))

        def parse(text: Any) -> Optional[Dict[str, Any]]:
            return parse_handoff_summary(
                text,
                previous_items=previous_items,
                valid_indexes=valid_indexes,
                round_no=round_no,
                source_limit=end,
            )

        last_error: Optional[Exception] = None
        parsed: Optional[Dict[str, Any]] = None
        for attempt in range(self.settings.max_retries + 1):
            if attempt and not isinstance(last_error, ValueError):
                # 仅接口报错时退避；响应无法解析时立即重试
                time.sleep(attempt)
            try:
                text = self._invoke_llm(ctx, target_tokens, user_prompt)
            except HandoffCompressionError:
                raise
            except Exception as exc:  # noqa: BLE001 - 接口报错统一走重试
                last_error = exc
                logger.warning("【Handoff】摘要生成第 %d 次调用失败: %s", attempt + 1, exc)
                continue
            parsed = parse(text)
            if parsed is None:
                last_error = ValueError("摘要响应无法解析")
                logger.warning("【Handoff】摘要生成第 %d 次响应无法解析", attempt + 1)
                continue
            break

        if parsed is None:
            logger.warning("【Handoff】摘要生成失败: %s", last_error)
            return None

        summary = render_handoff_summary(parsed, ledger, user_indexes, self.settings.key_message_char_limit)
        summary_tokens = self._summary_token_len(ctx, summary)
        if summary_tokens is None or summary_tokens <= target_tokens:
            return summary, parsed

        logger.warning("【Handoff】摘要 %d token 超过目标 %d，尝试压缩一次", summary_tokens, target_tokens)
        retry_prompt = user_prompt + SUMMARY_RETRY_SUFFIX.format(tokens=summary_tokens, target_tokens=target_tokens)
        try:
            shrunk = parse(self._invoke_llm(ctx, target_tokens, retry_prompt))
        except Exception as exc:  # noqa: BLE001 - 二次压缩失败时沿用首版摘要
            logger.warning("【Handoff】摘要二次压缩失败，沿用首版摘要: %s", exc)
            shrunk = None
        if shrunk is None:
            _skip("summary_shrink_failed")
            return summary, parsed
        summary = render_handoff_summary(shrunk, ledger, user_indexes, self.settings.key_message_char_limit)
        shrunk_tokens = self._summary_token_len(ctx, summary)
        if shrunk_tokens is not None and shrunk_tokens > target_tokens:
            _skip("summary_target_exceeded")
        return summary, shrunk

    @staticmethod
    def _summary_token_len(ctx: ProcessorContext, text: str) -> Optional[int]:
        try:
            tokens = ctx.llm.get_num_tokens(text) if ctx.llm is not None else None
        except Exception:  # noqa: BLE001 - 不支持计数的模型不应阻断交接。
            tokens = None
        if tokens is None:
            _skip("summary_token_count_unavailable")
        return tokens

    def _invoke_llm(self, ctx: ProcessorContext, target_tokens: int, user_prompt: str) -> str:
        llm = ctx.llm
        if llm is None:
            raise RuntimeError("Handoff 摘要生成缺少可用的 LLM")
        messages = [
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT.format(target_tokens=target_tokens)),
            HumanMessage(content=user_prompt),
        ]
        # 调用方已处于压缩 span 内，复制 context 使摘要 LLM 调用挂在该 span 下
        future = _compression_executor.submit(
            contextvars.copy_context().run, llm.invoke, messages, config={"tags": [CONTEXT_COMPRESSION_TAG]}
        )
        try:
            response = future.result(timeout=self.timeout)
        except concurrent.futures.TimeoutError as exc:
            # 运行中的线程无法强制终止，不继续重试以免堆积摘要请求。
            future.cancel()
            raise HandoffCompressionError("summary_timeout", "Handoff 摘要请求等待超时") from exc
        content = getattr(response, "content", response)
        return content if isinstance(content, str) else str(content)


def _emit_info(ctx: ProcessorContext, text: str, *, persist: bool) -> None:
    """发送 INFO 自定义事件；成功消息由模型节点返回值提交。

    事件发送失败（例如脱离 LangGraph run 上下文）只记日志，不影响压缩结果。
    """
    message_id = str(uuid.uuid4())
    try:
        conditional_dispatch_custom_event(
            CustomMessageType.INFO.value,
            {"messageId": message_id, "content": text},
            enable_custom_event=ctx.metadata.get("enable_custom_event", True),
        )
    except Exception as exc:  # noqa: BLE001 - 事件链路异常不能打挂压缩
        logger.warning("【Handoff】发送 INFO 事件失败: %s", exc)
    if not persist:
        return
    ctx.metadata.setdefault("_handoff_messages", []).append(InfoMessage(message_id=message_id, content=text))
