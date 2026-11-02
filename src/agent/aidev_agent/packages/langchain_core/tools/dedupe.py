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

工具重名去重模块

工具来自多个来源（平台工具、MCP Server、内置工具、middleware 注入等），
同名工具会让模型请求被网关拒绝（400 duplicate tool name），也会让 tool_node
按名路由时互相覆盖。本模块在工具收集完成、装配进图之前统一消除重名。

两级分组：

1. 按工具名分组（内置工具名一并计入）：组内只有一个工具时不改名；
2. 同名组内按来源再分组（优先级从高到低）：

   - 内置工具：default 组，不加前缀、不改名、不拷贝，名字直接在占用表里预留；
     default 组只能有一个工具；
   - 带审批：独立成组，前缀 ``mcp-<完整 Server 名>``，无 Server 名时 ``approval001`` ...；
     审批配置各自生效，不能被合并；
   - MCP 工具：同一 MCP 服务合并为一组（同服务多端点暴露的是同一份能力），只保留首个，
     前缀 ``mcp-<service>-prod``；Server 名中 ``-prod-`` 不是恰好出现一次时用完整 Server 名；
   - 其余：每个工具独立成组，前缀 ``Tool001`` / ``Tool002`` ...

   再分组后只剩一个组（例如全部来自同一 MCP 服务）时冲突已被合并消解，保留原名。

改名结果为 ``<前缀>__<工具名>``。与已占用的名字（内置名、其他工具原名、已分配的新名）冲突时：
序号前缀（``ToolNNN`` / ``approvalNNN``）取同名组内下一个序号；其余前缀依次追加 ``2``、``3`` ...
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import count
from typing import Collection, Dict, Iterable, Iterator, List, Sequence

from langchain_core.tools import BaseTool

from aidev_agent.packages.interrupt_manager.approval import is_approval_configured

logger = logging.getLogger(__name__)

# 改名分隔符：``<前缀>__<工具名>``
TOOL_NAME_SEP = "__"
# 工具名最大长度，超长按摘要截断
MAX_TOOL_NAME_LEN = 64
# 模型侧工具名字符集（OpenAI function name 约定）之外的字符
INVALID_CHAR_RE = re.compile(r"[^A-Za-z0-9_-]")
# MCP 分组名前缀，后接 MCP Server 名或服务名
MCP_GROUP_PREFIX = "mcp-"
# MCP Server 名中服务名与环境后缀的分隔段：``msdk-console-prod-mcp`` -> ``mcp-msdk-console-prod``
MCP_PROD_SEP = "-prod-"
# 序号前缀：无法合并、也没有来源名可用的工具按同名组内出现顺序编号
DEFAULT_SEQ_PREFIX = "Tool"
APPROVAL_SEQ_PREFIX = "approval"


@dataclass(frozen=True)
class _Slot:
    """第二级分组中需要改名的一个外部工具组。"""

    tool: BaseTool
    prefix: str
    numbered: bool


def _classify(tool: BaseTool) -> tuple[str, bool, bool]:
    """外部工具的 (前缀, 是否序号前缀, 是否可合并)，对应模块文档的优先级表。

    审批判定与 tool_node 的审批 wrapper 同源（``interrupt_manager.approval``），
    保证"会弹审批的工具"和"独立成组的工具"是同一批。
    """
    metadata = tool.metadata if isinstance(tool.metadata, dict) else {}
    mcp_name = metadata.get("mcp_name") or ""
    if is_approval_configured(tool):
        if mcp_name:
            return MCP_GROUP_PREFIX + mcp_name, False, False
        return APPROVAL_SEQ_PREFIX, True, False
    if mcp_name:
        parts = mcp_name.split(MCP_PROD_SEP)
        service = f"{parts[0]}-prod" if len(parts) == 2 and parts[0] else mcp_name
        return MCP_GROUP_PREFIX + service, False, True
    return DEFAULT_SEQ_PREFIX, True, False


def compose_name(prefix: str, tool_name: str) -> str:
    """拼 ``<prefix>__<tool>`` 并清洗为模型侧合法工具名。

    超长时截断前缀并追加 sha1 摘要（摘要取自清洗后的完整名，不同前缀不会撞车）；
    连工具名自身都放不下时退化为"截断的工具名 + 摘要"。
    """
    tool_segment = INVALID_CHAR_RE.sub("_", tool_name)
    prefix_segment = INVALID_CHAR_RE.sub("_", prefix)
    name = f"{prefix_segment}{TOOL_NAME_SEP}{tool_segment}"
    if len(name) <= MAX_TOOL_NAME_LEN:
        return name
    digest = "_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    budget = MAX_TOOL_NAME_LEN - len(digest) - len(TOOL_NAME_SEP) - len(tool_segment)
    if budget >= 1:
        return f"{prefix_segment[:budget]}{TOOL_NAME_SEP}{tool_segment}{digest}"
    return f"{tool_segment[: MAX_TOOL_NAME_LEN - len(digest)]}{digest}"


def _plan(externals: List[BaseTool]) -> List[_Slot]:
    """同名组内外部工具的第二级分组，可合并的同组工具只保留首个。

    内置工具（default 组）不需要改名，其名字已在名字占用表里预留，不参与这里的分组。
    """
    slots: List[_Slot] = []
    merged: set[str] = set()
    for tool in externals:
        prefix, numbered, mergeable = _classify(tool)
        if mergeable and prefix in merged:
            logger.info("[ToolDedupe] 同服务工具合并: %s <- %s", prefix, (tool.metadata or {}).get("mcp_name"))
            continue
        if mergeable:
            merged.add(prefix)
        slots.append(_Slot(tool, prefix, numbered))
    return slots


class _NameAllocator:
    """全局唯一的名字占用表。序号前缀在同名组内共用计数，其余前缀冲突时追加 2、3 ..."""

    def __init__(self, taken: Iterable[str]):
        self._taken = set(taken)

    def allocate(self, slot: _Slot, name: str, seq: Dict[str, Iterator[int]]) -> str:
        prefix = slot.prefix
        if slot.numbered:
            counter = seq.setdefault(prefix, count(1))
            candidates = (compose_name(f"{prefix}{n:03d}", name) for n in counter)
        else:
            candidates = (compose_name(prefix if n == 1 else f"{prefix}{n}", name) for n in count(1))
        candidate = next(each for each in candidates if each not in self._taken)
        self._taken.add(candidate)
        return candidate


def dedupe_tool_names(
    tools: List[BaseTool], *, builtin_tools: Sequence[BaseTool] = (), reserved_names: Collection[str] = ()
) -> List[BaseTool]:
    """返回去重后的外部工具；内置工具占 default 组、原样保留，不进入返回列表。

    ``reserved_names`` 是尚未构造实例的内置工具名（如延迟加载元工具），与内置工具同等占位。
    内置实例被原样混入外部列表时（续跑等路径）直接剔除。
    """
    reserved = set(reserved_names)
    for tool in builtin_tools:
        if not tool.name or tool.name in reserved:
            raise ValueError(f"SDK 内置工具名必须非空且唯一，不能改名: {tool.name}")
        reserved.add(tool.name)
    builtin_ids = {id(tool) for tool in builtin_tools}
    buckets: Dict[str, List[BaseTool]] = defaultdict(list)
    for tool in tools:
        if not tool.name:
            raise ValueError(f"工具缺少 name，无法参与重名去重: {tool!r}")
        if id(tool) not in builtin_ids:
            buckets[tool.name].append(tool)

    allocator = _NameAllocator([*reserved, *buckets])
    result: List[BaseTool] = []
    for name, externals in buckets.items():
        if len(externals) == 1 and name not in reserved:
            result.extend(externals)
            continue
        slots = _plan(externals)
        if len(slots) == 1 and name not in reserved:
            result.append(slots[0].tool)
            continue
        seq: Dict[str, Iterator[int]] = {}
        renamed = [slot.tool.model_copy(update={"name": allocator.allocate(slot, name, seq)}) for slot in slots]
        logger.info("[ToolDedupe] 工具重名已处理: original=%s, result=%s", name, [tool.name for tool in renamed])
        result.extend(renamed)
    names = Counter([*reserved, *(tool.name for tool in result)])
    assert all(n == 1 for n in names.values()), f"工具去重后仍存在重名工具: {names}"
    return result
