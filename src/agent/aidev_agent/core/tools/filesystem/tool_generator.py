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

工具生成器模块，提供文件系统工具的创建函数。

参考 deepagents 的工具生成器实现：
https://github.com/langchain-ai/deepagents/blob/master/libs/deepagents/deepagents/middleware/filesystem.py
"""

from __future__ import annotations

import os
import re
from typing import Annotated, Callable, Literal

from langchain_core.tools import BaseTool, StructuredTool

from aidev_agent.core.tools.filesystem.backend import FilesystemBackend
from aidev_agent.core.tools.filesystem.utils import format_grep_matches, truncate_if_too_long

# ========== 默认配置 ==========

DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 100


# ========== 工具描述常量 ==========

LIST_FILES_TOOL_DESCRIPTION = """Lists all files in a directory.
This is useful for exploring the filesystem and finding the right file to read or edit.
You should almost ALWAYS use this tool before using the read_file or edit_file tools."""

READ_FILE_TOOL_DESCRIPTION = """Reads a file from the filesystem.
Assume this tool is able to read all files. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- By default, it reads up to 100 lines starting from the beginning of the file
- **IMPORTANT for large files and codebase exploration**: Use pagination with offset and limit parameters to avoid context overflow
- First scan: read_file(path, limit=100) to see file structure
- Read more sections: read_file(path, offset=100, limit=200) for next 200 lines
- Only omit limit (read full file) when necessary for editing
- Specify offset and limit: read_file(path, offset=0, limit=100) reads first 100 lines
- Results are returned using cat -n format, with line numbers starting at 1
- Lines longer than 5,000 characters will be split into multiple lines with continuation markers (e.g., 5.1, 5.2, etc.). When you specify a limit, these continuation lines count towards the limit.
- You have the capability to call multiple tools in a single response. It is always better to speculatively read multiple files as a batch that are potentially useful.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents.
- You should ALWAYS make sure a file has been read before editing it."""

WRITE_FILE_TOOL_DESCRIPTION = """Writes to a new file in the filesystem.

Usage:
- The write_file tool will create the a new file.
- Prefer to edit existing files (with the edit_file tool) over creating new ones when possible.
"""

EDIT_FILE_TOOL_DESCRIPTION = """Performs exact string replacements in files.

Usage:
- You must read the file before editing. This tool will error if you attempt an edit without reading the file first.
- When editing, preserve the exact indentation (tabs/spaces) from the read output. Never include line number prefixes in old_string or new_string.
- ALWAYS prefer editing existing files over creating new ones.
- Only use emojis if the user explicitly requests it."""

GLOB_TOOL_DESCRIPTION = """Find files matching a glob pattern.
Supports standard glob patterns: `*` (any characters), `**` (any directories), `?` (single character).
Returns a list of absolute file paths that match the pattern.

Examples:
- `**/*.py` - Find all Python files
- `*.txt` - Find all text files in root
- `/subdir/**/*.md` - Find all markdown files under /subdir"""

GREP_TOOL_DESCRIPTION = """Search for a text pattern across files.
Searches for literal text (not regex) and returns matching files or content based on output_mode.

Examples:
- Search all files: `grep(pattern="TODO")`
- Search Python files only: `grep(pattern="import", glob="*.py")`
- Show matching lines: `grep(pattern="error", output_mode="content")`"""

EXECUTE_TOOL_DESCRIPTION = """Executes a shell command in an isolated sandbox environment.

Usage:
Executes a given command in the sandbox environment with proper handling and security measures.

Before executing the command, please follow these steps:

1. Directory Verification:
   - If the command will create new directories or files, first use the ls tool to verify the parent directory exists and is the correct location
   - For example, before running "mkdir foo/bar", first use ls to check that "foo" exists and is the intended parent directory

2. Command Execution:
   - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
   - Examples of proper quoting:
     - cd "/Users/name/My Documents" (correct)
     - cd /Users/name/My Documents (incorrect - will fail)
     - python "/path/with spaces/script.py" (correct)
     - python /path/with spaces/script.py (incorrect - will fail)
   - After ensuring proper quoting, execute the command
   - Capture the output of the command

Usage notes:
- Commands run in an isolated sandbox environment
- Returns combined stdout/stderr output with exit code
- If the output is very large, it may be truncated
- VERY IMPORTANT: You MUST avoid using search commands like find and grep. Instead use the grep, glob tools to search. You MUST avoid read tools like cat, head, tail, and use read_file to read files.
- When issuing multiple commands, use the ';' or '&&' operator to separate them. DO NOT use newlines (newlines are ok in quoted strings)
- Use '&&' when commands depend on each other (e.g., "mkdir dir && cd dir")
- Use ';' only when you need to run commands sequentially but don't care if earlier commands fail
- Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of cd

Examples:
Good examples:
- execute(command="pytest /foo/bar/tests")
- execute(command="python /path/to/script.py")
- execute(command="npm install && npm test")

Bad examples (avoid these):
- execute(command="cd /foo/bar && pytest tests") # Use absolute path instead
- execute(command="cat file.txt") # Use read_file tool instead
- execute(command="find . -name '*.py'") # Use glob tool instead
- execute(command="grep -r 'pattern' .") # Use grep tool instead
"""


# ========== 路径验证函数 ==========


def _validate_path(path: str, *, allowed_prefixes: list[str] | None = None) -> str:
    r"""验证并规范化文件路径以确保安全。

    通过防止目录遍历攻击和强制一致格式来确保路径安全可用。
    所有路径都会被规范化为使用正斜杠并以前导斜杠开头。

    此函数设计用于虚拟文件系统路径，会拒绝 Windows 绝对路径
    （如 C:/...、F:/...）以保持一致性并防止路径格式歧义。

    Args:
        path: 要验证和规范化的路径
        allowed_prefixes: 可选的允许路径前缀列表。如果提供，
                         规范化后的路径必须以其中一个前缀开头

    Returns:
        规范化的标准路径，以 `/` 开头并使用正斜杠

    Raises:
        ValueError: 当路径包含遍历序列（`..` 或 `~`）、
                   是 Windows 绝对路径（如 C:/...）、或不以允许的前缀开头时抛出
    """
    if ".." in path or path.startswith("~"):
        msg = f"Path traversal not allowed: {path}"
        raise ValueError(msg)

    # 拒绝 Windows 绝对路径（如 C:\...、D:/...）
    if re.match(r"^[a-zA-Z]:", path):
        msg = (
            f"Windows absolute paths are not supported: {path}. "
            "Please use virtual paths starting with / (e.g., /workspace/file.txt)"
        )
        raise ValueError(msg)

    normalized = os.path.normpath(path)
    normalized = normalized.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    if allowed_prefixes is not None and not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
        msg = f"Path must start with one of {allowed_prefixes}: {path}"
        raise ValueError(msg)

    return normalized


# ========== 后端获取辅助函数 ==========


def _get_backend(
    backend: FilesystemBackend | Callable[[], FilesystemBackend],
) -> FilesystemBackend:
    """从后端实例或工厂函数获取解析后的后端实例。

    Args:
        backend: 后端实例或返回后端的工厂函数

    Returns:
        解析后的后端实例
    """
    if callable(backend):
        return backend()
    return backend


# ========== 工具生成器函数 ==========


def _ls_tool_generator(
    backend: FilesystemBackend,
    custom_description: str | None = None,
) -> BaseTool:
    """生成 ls（列出文件）工具。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数
        custom_description: 可选的自定义工具描述

    Returns:
        配置好的 ls 工具，使用后端列出文件
    """
    tool_description = custom_description or LIST_FILES_TOOL_DESCRIPTION

    def ls(
        path: Annotated[str, "Absolute path to the directory to list. Must be absolute, not relative."],
    ) -> str:
        """列出目录中的文件。"""
        resolved_backend = backend
        validated_path = _validate_path(path)
        infos = resolved_backend.ls_info(validated_path)
        paths = [fi.get("path", "") for fi in infos]
        result = truncate_if_too_long(paths)
        return str(result)

    return StructuredTool.from_function(
        name="ls",
        description=tool_description,
        func=ls,
    )


def _read_file_tool_generator(
    backend: FilesystemBackend,
    custom_description: str | None = None,
) -> BaseTool:
    """生成 read_file 工具。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数
        custom_description: 可选的自定义工具描述

    Returns:
        配置好的 read_file 工具，使用后端读取文件
    """
    tool_description = custom_description or READ_FILE_TOOL_DESCRIPTION

    def read_file(
        file_path: Annotated[str, "Absolute path to the file to read. Must be absolute, not relative."],
        offset: Annotated[
            int, "Line number to start reading from (0-indexed). Use for pagination of large files."
        ] = DEFAULT_READ_OFFSET,
        limit: Annotated[
            int, "Maximum number of lines to read. Use for pagination of large files."
        ] = DEFAULT_READ_LIMIT,
    ) -> str:
        """读取文件内容。"""
        resolved_backend = backend
        validated_path = _validate_path(file_path)
        result = resolved_backend.read(validated_path, offset=offset, limit=limit)
        lines = result.splitlines(keepends=True)
        if len(lines) > limit:
            lines = lines[:limit]
        result = "".join(lines)
        return result

    return StructuredTool.from_function(
        name="read_file",
        description=tool_description,
        func=read_file,
    )


def _write_file_tool_generator(
    backend: FilesystemBackend | Callable[[], FilesystemBackend],
    custom_description: str | None = None,
) -> BaseTool:
    """生成 write_file 工具。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数
        custom_description: 可选的自定义工具描述

    Returns:
        配置好的 write_file 工具，使用后端创建新文件
    """
    tool_description = custom_description or WRITE_FILE_TOOL_DESCRIPTION

    def write_file(
        file_path: Annotated[
            str,
            "Absolute path where the file should be created. Must be absolute, not relative.",
        ],
        content: Annotated[str, "The text content to write to the file. This parameter is required."],
    ) -> str:
        """创建新文件。"""
        resolved_backend = backend
        validated_path = _validate_path(file_path)
        res = resolved_backend.write(validated_path, content)
        if res.error:
            return res.error
        return f"Updated file {res.path}"

    return StructuredTool.from_function(
        name="write_file",
        description=tool_description,
        func=write_file,
    )


def _edit_file_tool_generator(
    backend: FilesystemBackend | Callable[[], FilesystemBackend],
    custom_description: str | None = None,
) -> BaseTool:
    """生成 edit_file 工具。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数
        custom_description: 可选的自定义工具描述

    Returns:
        配置好的 edit_file 工具，使用后端进行字符串替换编辑文件
    """
    tool_description = custom_description or EDIT_FILE_TOOL_DESCRIPTION

    def edit_file(
        file_path: Annotated[str, "Absolute path to the file to edit. Must be absolute, not relative."],
        old_string: Annotated[
            str,
            "The exact text to find and replace. Must be unique in the file unless replace_all is True.",
        ],
        new_string: Annotated[str, "The text to replace old_string with. Must be different from old_string."],
        replace_all: Annotated[
            bool,
            "If True, replace all occurrences of old_string. If False (default), old_string must be unique.",
        ] = False,
    ) -> str:
        """通过字符串替换编辑文件。"""
        resolved_backend = _get_backend(backend)
        validated_path = _validate_path(file_path)
        res = resolved_backend.edit(validated_path, old_string, new_string, replace_all=replace_all)
        if res.error:
            return res.error
        return f"Successfully replaced {res.occurrences} instance(s) of the string in '{res.path}'"

    return StructuredTool.from_function(
        name="edit_file",
        description=tool_description,
        func=edit_file,
    )


def _glob_tool_generator(
    backend: FilesystemBackend | Callable[[], FilesystemBackend],
    custom_description: str | None = None,
) -> BaseTool:
    """生成 glob 工具。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数
        custom_description: 可选的自定义工具描述

    Returns:
        配置好的 glob 工具，使用后端按模式查找文件
    """
    tool_description = custom_description or GLOB_TOOL_DESCRIPTION

    def glob(
        pattern: Annotated[str, "Glob pattern to match files (e.g., '**/*.py', '*.txt', '/subdir/**/*.md')."],
        path: Annotated[str, "Base directory to search from. Defaults to root '/'."] = "/",
    ) -> str:
        """查找匹配 glob 模式的文件。"""
        resolved_backend = backend
        infos = resolved_backend.glob_info(pattern, path=path)
        paths = [fi.get("path", "") for fi in infos]
        result = truncate_if_too_long(paths)
        return str(result)

    return StructuredTool.from_function(
        name="glob",
        description=tool_description,
        func=glob,
    )


def _grep_tool_generator(
    backend: FilesystemBackend | Callable[[], FilesystemBackend],
    custom_description: str | None = None,
) -> BaseTool:
    """生成 grep 工具。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数
        custom_description: 可选的自定义工具描述

    Returns:
        配置好的 grep 工具，使用后端在文件中搜索模式
    """
    tool_description = custom_description or GREP_TOOL_DESCRIPTION

    def grep(
        pattern: Annotated[str, "Text pattern to search for (literal string, not regex)."],
        path: Annotated[str | None, "Directory to search in. Defaults to current working directory."] = None,
        glob: Annotated[str | None, "Glob pattern to filter which files to search (e.g., '*.py')."] = None,
        output_mode: Annotated[
            Literal["files_with_matches", "content", "count"],
            "Output format: 'files_with_matches' (file paths only, default), 'content' (matching lines with context), 'count' (match counts per file).",
        ] = "files_with_matches",
    ) -> str:
        """在文件中搜索文本模式。"""
        resolved_backend = backend
        raw = resolved_backend.grep_raw(pattern, path=path, glob=glob)
        if isinstance(raw, str):
            return raw
        formatted = format_grep_matches(raw, output_mode)
        return truncate_if_too_long(formatted)

    return StructuredTool.from_function(
        name="grep",
        description=tool_description,
        func=grep,
    )


def _execute_tool_generator(
    backend: FilesystemBackend | Callable[[], FilesystemBackend],
    custom_description: str | None = None,
) -> BaseTool:
    """生成 execute 工具用于执行 shell 命令。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数
        custom_description: 可选的自定义工具描述

    Returns:
        配置好的 execute 工具，使用后端执行 shell 命令
    """
    tool_description = custom_description or EXECUTE_TOOL_DESCRIPTION

    def execute(
        command: Annotated[str, "Shell command to execute in the sandbox environment."],
    ) -> str:
        """在沙箱环境中执行 shell 命令。"""
        resolved_backend = _get_backend(backend)

        result = resolved_backend.execute(command)

        # 格式化输出供 LLM 消费
        parts = [result.output]
        if result.exit_code is not None:
            status = "succeeded" if result.exit_code == 0 else "failed"
            parts.append(f"\n[Command {status} with exit code {result.exit_code}]")
        if result.truncated:
            parts.append("\n[Output was truncated due to size limits]")

        return "".join(parts)

    async def async_execute(
        command: Annotated[str, "Shell command to execute in the sandbox environment."],
    ) -> str:
        """异步执行 shell 命令。"""
        resolved_backend = _get_backend(backend)

        result = await resolved_backend.aexecute(command)

        # 格式化输出供 LLM 消费
        parts = [result.output]
        if result.exit_code is not None:
            status = "succeeded" if result.exit_code == 0 else "failed"
            parts.append(f"\n[Command {status} with exit code {result.exit_code}]")
        if result.truncated:
            parts.append("\n[Output was truncated due to size limits]")

        return "".join(parts)

    return StructuredTool.from_function(
        name="execute",
        description=tool_description,
        func=execute,
        coroutine=async_execute,
    )


# ========== 工具生成器注册表 ==========

TOOL_GENERATORS: dict[str, Callable[..., BaseTool]] = {
    "ls": _ls_tool_generator,
    "read_file": _read_file_tool_generator,
    "write_file": _write_file_tool_generator,
    "edit_file": _edit_file_tool_generator,
    "glob": _glob_tool_generator,
    "grep": _grep_tool_generator,
    "execute": _execute_tool_generator,
}


# ========== 工厂函数 ==========


def get_filesystem_tools(
    backend: FilesystemBackend | Callable[[], FilesystemBackend] | None = None,
    custom_tool_descriptions: dict[str, str] | None = None,
) -> list[BaseTool]:
    """获取文件系统工具列表。

    Args:
        backend: 用于文件存储的后端，或返回后端的工厂函数。
                如果未提供，默认使用当前工作目录的 FilesystemBackend。
        custom_tool_descriptions: 可选的自定义工具描述字典。
                                 键为工具名（ls、read_file、write_file、
                                 edit_file、glob、grep）。

    Returns:
        配置好的工具列表：ls、read_file、write_file、edit_file、glob、grep。

    Example:
        ```python
        # 使用默认后端创建完整工具集
        tools = get_filesystem_tools()

        # 使用自定义后端创建
        backend = FilesystemBackend(root_dir="/workspace", virtual_mode=True)
        tools = get_filesystem_tools(backend=backend)

        # 使用自定义描述创建
        tools = get_filesystem_tools(
            custom_tool_descriptions={
                "ls": "Custom description for ls tool",
            }
        )
        ```
    """
    if backend is None:
        backend = FilesystemBackend()

    if custom_tool_descriptions is None:
        custom_tool_descriptions = {}

    tools = []
    for tool_name, tool_generator in TOOL_GENERATORS.items():
        tool = tool_generator(backend, custom_tool_descriptions.get(tool_name))
        tools.append(tool)

    return tools
