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

文件系统工具模块。

提供一组用于文件系统操作的 LangChain 工具，包括：
- ls: 列出目录内容
- read_file: 读取文件内容
- write_file: 创建新文件
- edit_file: 编辑现有文件
- glob_search: 使用 glob 模式搜索文件
- grep_search: 在文件中搜索文本

模块结构：
- prompts: 工具描述常量
- backend: FilesystemBackend 实现
- utils: 辅助函数和类型定义
- tool_generator: 工具生成器函数

使用示例：
    >>> tools = make_filesystem_tools(allowed_prefixes=["/workspace"])
    >>> # tools 现在包含 ls, read_file, glob_search, grep_search, write_file, edit_file

参考实现：
- https://github.com/langchain-ai/deepagents/blob/master/libs/deepagents/deepagents/middleware/filesystem.py
- https://github.com/langchain-ai/deepagents/blob/master/libs/deepagents/deepagents/backends/filesystem.py
"""

from __future__ import annotations

# 从各子模块导入公共 API
from aidev_agent.core.tools.filesystem.backend import (
    EditResult,
    FileInfo,
    FilesystemBackend,
    GrepMatch,
    WriteResult,
)
from aidev_agent.core.tools.filesystem.tool_generator import (
    get_filesystem_tools,
)

__all__ = [
    # 主要公共 API
    "get_filesystem_tools",
    # 后端类和数据结构
    "FilesystemBackend",
    "FileInfo",
    "GrepMatch",
    "WriteResult",
    "EditResult",
]
