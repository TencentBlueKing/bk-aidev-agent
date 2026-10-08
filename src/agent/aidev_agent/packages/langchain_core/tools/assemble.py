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

from logging import getLogger
from typing import Any, Sequence

logger = getLogger(__name__)


def _tool_name(tool: Any) -> str | None:
    if isinstance(tool, dict):
        name = tool.get("name")
    else:
        name = getattr(tool, "name", None)
    if name is None:
        return None
    name = str(name)
    return name or None


def _tool_source(tool: Any) -> str:
    """告警定位：优先 mcp_name，其次 tool_code。"""
    if isinstance(tool, dict):
        metadata = tool.get("metadata") or {}
        mcp_name = tool.get("mcp_name") or metadata.get("mcp_name")
        tool_code = tool.get("tool_code") or metadata.get("tool_code")
    else:
        metadata = getattr(tool, "metadata", None) or {}
        mcp_name = metadata.get("mcp_name")
        tool_code = metadata.get("tool_code")
    if mcp_name:
        return str(mcp_name)
    if tool_code:
        return str(tool_code)
    return "unknown"


def assemble_bound_tools(tools: Sequence[Any] | None) -> list[Any]:
    """按 tool.name 去重并保留先到者。

    绑定模型前的唯一去重入口。无名工具原样保留；重名时丢弃后者并打 warning。
    """
    assembled: list[Any] = []
    seen: dict[str, str] = {}
    for tool in tools or []:
        name = _tool_name(tool)
        if not name:
            assembled.append(tool)
            continue
        source = _tool_source(tool)
        if name in seen:
            logger.warning(
                "assemble_bound_tools: drop duplicate tool name=%s keep_source=%s drop_source=%s",
                name,
                seen[name],
                source,
            )
            continue
        seen[name] = source
        assembled.append(tool)
    return assembled
