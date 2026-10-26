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
按名路由时互相覆盖。本模块在工具收集完成、装配进图之前统一消除重名，
不同名的工具永远不受影响。
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter, defaultdict
from typing import Dict, List

from langchain_core.tools import BaseTool

from aidev_agent.packages.interrupt_manager.approval import is_approval_configured

logger = logging.getLogger(__name__)

# 改名分隔符：``<前缀>__<工具名>``
TOOL_NAME_SEP = "__"
# 工具名最大长度，超长按摘要截断
MAX_TOOL_NAME_LEN = 64
# 模型侧工具名字符集（OpenAI function name 约定）之外的字符
INVALID_CHAR_RE = re.compile(r"[^A-Za-z0-9_-]")
# MCP 分组名前缀，后接 MCP Server 名（审批组用完整 Server 名，其余用服务名）
MCP_GROUP_PREFIX = "mcp-"
# MCP Server 名中服务名与环境后缀的分隔段：``msdk-console-prod-mcp`` -> ``msdk-console``
MCP_SERVICE_SEP = "-prod-"


def resolve_group(tool: BaseTool) -> str | None:
    """计算同名工具的分组名，``None`` 表示 default 组。

    - 带审批：``mcp-<mcp_name>``，审批配置各自生效，不能被别的实例合并覆盖，
      所以用完整 Server 名（无 mcp_name 时退回工具名）让它独立成组；
    - MCP 工具：``mcp-<service>``，service 取 Server 名 ``-prod-`` 之前的部分；
      没有或有多个 ``-prod-`` 段时解析不出服务名，退回完整 Server 名；
    - 其余：``None``，即 default 组。

    审批判定与 tool_node 的审批 wrapper 同源（``interrupt_manager.approval``），
    保证"会弹审批的工具"和"独立成组的工具"是同一批。
    """
    metadata = tool.metadata if isinstance(tool.metadata, dict) else {}
    mcp_name = metadata.get("mcp_name") or ""
    if is_approval_configured(tool):
        return MCP_GROUP_PREFIX + (mcp_name or tool.name)
    if not mcp_name:
        return None
    parts = mcp_name.split(MCP_SERVICE_SEP)
    service = parts[0] if len(parts) == 2 and parts[0] else mcp_name
    return MCP_GROUP_PREFIX + service


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


def dedupe_same_name(name: str, tools: List[BaseTool]) -> List[BaseTool]:
    """处理一组同名工具，返回组内顺序的结果（被合并的实例已剔除）。

    - default 组的同名工具来自不同来源、各自可执行，不合并，依次改名为
      ``<tool>`` / ``Tool001__<tool>`` / ``Tool002__<tool>``；
    - 有分组名的改名为 ``<group>__<tool>``；分组名相同即同一 MCP 服务的多个端点，
      暴露的是同一份后端能力，只保留第一个实例，被合并的 Server 名记入
      ``metadata["merged_mcp_servers"]``。

    只对发生变动的工具做 ``model_copy`` 浅拷贝，调用方持有的原对象不被修改；
    原工具名写入 ``metadata["original_name"]`` 供排查与审批匹配。
    """
    result: List[BaseTool] = []
    # 分组名 -> 该分组保留者在 result 中的下标
    anchors: Dict[str, int] = {}
    default_count = 0
    for tool in tools:
        group = resolve_group(tool)
        if group is None:
            new_name = name if default_count == 0 else compose_name(f"Tool{default_count:03d}", name)
            default_count += 1
        elif group in anchors:
            anchor = result[anchors[group]]
            merged_server = (tool.metadata or {}).get("mcp_name")
            if merged_server:
                metadata = dict(anchor.metadata or {})
                metadata["merged_mcp_servers"] = [*metadata.get("merged_mcp_servers", []), merged_server]
                result[anchors[group]] = anchor.model_copy(update={"metadata": metadata})
            logger.info(f"[ToolDedupe] 同组工具合并: tool={name}, group={group}, merged_server={merged_server}")
            continue
        else:
            anchors[group] = len(result)
            new_name = compose_name(group, name)

        if new_name != name:
            metadata = dict(tool.metadata) if isinstance(tool.metadata, dict) else {}
            metadata["original_name"] = name
            tool = tool.model_copy(update={"name": new_name, "metadata": metadata})
        result.append(tool)
    logger.info(f"[ToolDedupe] 工具重名已处理: original={name}, result={[each.name for each in result]}")
    return result


def dedupe_tool_names(tools: List[BaseTool]) -> List[BaseTool]:
    """消除工具重名，保证模型请求中的工具名唯一。

    按工具名分组，只有一个实例的原样保留，同名的交给 :func:`dedupe_same_name` 处理。
    分组字典按工具名首次出现的顺序插入，顺序遍历即可保持输入顺序。

    返回前再扫一遍结果，若仍存在重名则抛 ``ValueError``——名字唯一是模型请求能被
    接受的前提，宁可装配阶段报错也不把非法请求发给模型。

    Args:
        tools: 已按装配顺序排好的工具列表。

    Returns:
        处理后的工具列表，保持输入顺序（被合并的实例移除，改名的保持原位）。
    """
    groups: Dict[str, List[BaseTool]] = defaultdict(list)
    for tool in tools:
        if not tool.name:
            # name 是 BaseTool 的必填字段，缺失说明装配链路有问题
            raise ValueError(f"工具缺少 name，无法参与重名去重: {tool!r}")
        groups[tool.name].append(tool)

    result: List[BaseTool] = []
    for name, same_name in groups.items():
        result.extend(same_name if len(same_name) == 1 else dedupe_same_name(name, same_name))

    duplicated = {name: count for name, count in Counter(each.name for each in result).items() if count > 1}
    if duplicated:
        raise ValueError(f"工具去重后仍存在重名工具: {duplicated}")
    return result
