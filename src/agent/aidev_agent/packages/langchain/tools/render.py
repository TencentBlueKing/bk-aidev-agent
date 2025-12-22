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

from inspect import signature
from typing import Callable

from langchain_core.tools.base import BaseTool
from pydantic.v1 import BaseModel as BaseModelV1

ToolsRenderer = Callable[[list[BaseTool]], str]


def render_text_description(tools: list[BaseTool]) -> str:
    """Render the tool name and description in plain text.

    Args:
        tools: The tools to render.

    Returns:
        The rendered text.

    Output will be in the format of:

    .. code-block:: markdown

        search: This tool is used for search
        calculator: This tool is used for math
    """
    descriptions = []
    for tool in tools:
        if hasattr(tool, "func") and tool.func:
            sig = signature(tool.func)
            description = f"{tool.name}{sig} - {tool.description}"
        else:
            description = f"{tool.name} - {tool.description}"

        descriptions.append(description)
    return "\n".join(descriptions)


def render_text_description_and_args(tools: list[BaseTool]) -> str:
    """Render the tool name, description, and args in plain text.

    Args:
        tools: The tools to render.

    Returns:
        The rendered text.

    Output will be in the format of:

    .. code-block:: markdown

        search: This tool is used for search, args: {"query": {"type": "string"}}
        calculator: This tool is used for math, \
args: {"expression": {"type": "string"}}
    """
    tool_strings = []
    for tool in tools:
        args_schema = str(get_args(tool))
        if hasattr(tool, "func") and tool.func:
            sig = signature(tool.func)
            description = f"{tool.name}{sig} - {tool.description}"
        else:
            description = f"{tool.name} - {tool.description}"
        tool_strings.append(f"{description}, args: {args_schema}")
    return "\n".join(tool_strings)


def get_args(tool) -> dict:
    """Get the tool's input arguments schema.

    Returns:
        Dictionary containing the tool's argument properties.
    """
    if isinstance(tool.args_schema, dict):
        json_schema = tool.args_schema
    elif tool.args_schema and issubclass(tool.args_schema, BaseModelV1):
        json_schema = tool.args_schema.schema()
    else:
        input_schema = tool.get_input_schema()
        json_schema = input_schema.model_json_schema()
    # 安全地获取properties
    properties = json_schema.get("properties")

    # 确保返回的是字典（如果没有properties或不是字典，返回空字典）
    if isinstance(properties, dict):
        return properties
    else:
        return {}  # 或者根据需求返回空字典
