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

FilesystemBackend: 直接从文件系统读写文件的后端实现。

参考 deepagents 的 FilesystemBackend 实现：
https://github.com/langchain-ai/deepagents/blob/master/libs/deepagents/deepagents/backends/filesystem.py
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NotRequired

from typing_extensions import TypedDict

from aidev_agent.core.tools.filesystem.utils import (
    check_empty_content,
    format_content_with_line_numbers,
    perform_string_replacement,
)

# ========== 数据结构定义 ==========


class FileInfo(TypedDict):
    """文件信息结构。

    用于 ls_info 和 glob_info 方法返回的文件元数据。
    只有 path 是必需的，其他字段根据后端能力可选提供。
    """

    path: str
    """文件或目录的路径"""

    is_dir: NotRequired[bool]
    """是否为目录"""

    size: NotRequired[int]
    """文件大小（字节）"""

    modified_at: NotRequired[str]
    """最后修改时间（ISO 8601 格式）"""


class GrepMatch(TypedDict):
    """grep 搜索匹配结果结构。"""

    path: str
    """匹配的文件路径"""

    line: int
    """匹配的行号"""

    text: str
    """匹配的行内容"""


@dataclass
class WriteResult:
    """写操作结果。

    Attributes:
        error: 失败时的错误信息，成功时为 None
        path: 写入的文件路径，失败时为 None
        files_update: 文件更新信息，外部存储时为 None
    """

    error: str | None = None
    path: str | None = None
    files_update: dict | None = None


@dataclass
class EditResult:
    """编辑操作结果。

    Attributes:
        error: 失败时的错误信息，成功时为 None
        path: 编辑的文件路径，失败时为 None
        occurrences: 替换的匹配数量，失败时为 None
        files_update: 文件更新信息，外部存储时为 None
    """

    error: str | None = None
    path: str | None = None
    occurrences: int | None = None
    files_update: dict | None = None


@dataclass
class ExecuteResult:
    """命令执行结果。

    Attributes:
        output: 命令的标准输出和标准错误的合并输出
        exit_code: 命令退出码，None 表示执行过程中发生错误
        truncated: 输出是否因大小限制被截断
    """

    output: str
    exit_code: int | None = None
    truncated: bool = False


class FileUploadResponse(TypedDict):
    """文件上传响应结构。"""

    path: str
    """上传的文件路径"""

    error: str | None
    """错误信息，成功时为 None"""


class FileDownloadResponse(TypedDict):
    """文件下载响应结构。"""

    path: str
    """下载的文件路径"""

    content: bytes | None
    """文件内容，失败时为 None"""

    error: str | None
    """错误信息，成功时为 None"""


# ========== FilesystemBackend 实现 ==========


class FilesystemBackend:
    """直接从文件系统读写文件的后端。

    文件使用其实际的文件系统路径访问。相对路径相对于当前工作目录解析。
    内容以纯文本形式读写，元数据（时间戳）从文件系统统计信息获取。

    !!! warning "安全警告"
        此后端授予 Agent 直接的文件系统读写访问权限。
        请谨慎使用，仅在适当的环境中使用。

    **适用场景:**
    - 本地开发 CLI（编码助手、开发工具）
    - CI/CD 流水线（注意安全考虑）

    **不适用场景:**
    - Web 服务器或 HTTP API - 请使用 StateBackend、StoreBackend 或 SandboxBackend

    **安全风险:**
    - Agent 可以读取任何可访问的文件，包括密钥（API keys、credentials、.env 文件）
    - 结合网络工具，密钥可能通过 SSRF 攻击被泄露
    - 文件修改是永久且不可逆的

    **推荐的安全措施:**
    1. 启用人工审核（HITL）中间件来审查敏感操作
    2. 排除包含敏感信息的路径（尤其是在 CI/CD 中）
    3. 在需要文件系统交互的生产环境中使用 SandboxBackend
    4. **始终** 使用 `virtual_mode=True` 配合 `root_dir` 启用基于路径的访问限制
       （阻止 `..`、`~` 和根目录外的绝对路径）。注意默认的
       `virtual_mode=False` 即使设置了 `root_dir` 也不提供安全性。

    Args:
        root_dir: 可选的根目录。如果未提供，默认为当前工作目录。
            - 当 `virtual_mode=False`（默认）：仅影响相对路径解析。
              **不提供安全性** - Agent 可以使用绝对路径或 `..` 序列访问任何文件。
            - 当 `virtual_mode=True`：所有路径都被限制在此目录内，启用遍历保护。
        virtual_mode: 启用基于路径的访问限制。
            当为 `True` 时，所有路径都被视为锚定到 `root_dir` 的虚拟路径。
            路径遍历（`..`、`~`）被阻止，所有解析后的路径都会验证是否在 `root_dir` 内。

            当为 `False`（默认）时，**不提供安全性**：
            - 绝对路径（如 `/etc/passwd`）完全绕过 `root_dir`
            - 带 `..` 的相对路径可以逃逸 `root_dir`
            - Agent 拥有无限制的文件系统访问权限

            **安全说明：** `virtual_mode=True` 提供基于路径的访问控制，
            而非进程隔离。它限制哪些文件可以通过路径访问，
            但不会沙箱化 Python 进程本身。
        max_file_size_mb: 操作（如 grep 的 Python 回退搜索）的最大文件大小（MB）。
            超过此限制的文件在搜索时会被跳过。默认为 10 MB。

    Example:
        >>> backend = FilesystemBackend(root_dir="/workspace", virtual_mode=True)
        >>> infos = backend.ls_info("/src")
        >>> content = backend.read("/src/main.py", offset=0, limit=100)
    """

    def __init__(
        self,
        root_dir: str | Path | None = None,
        virtual_mode: bool = False,
        max_file_size_mb: int = 10,
    ) -> None:
        """初始化文件系统后端。

        Args:
            root_dir: 文件操作的根目录。如果未提供，默认为当前工作目录。
                - 当 `virtual_mode=False`（默认）：仅影响相对路径解析。
                  **不提供安全性** - Agent 可以使用绝对路径或 `..` 序列访问任何文件。
                - 当 `virtual_mode=True`：所有路径都被限制在此目录内，启用遍历保护。
            virtual_mode: 启用基于路径的访问限制。
                当为 `True` 时，所有路径都被视为锚定到 `root_dir` 的虚拟路径。
                路径遍历被阻止，所有解析后的路径都会验证是否在 `root_dir` 内。

                当为 `False`（默认）时，**不提供安全性**：
                - 绝对路径（如 `/etc/passwd`）完全绕过 `root_dir`
                - 带 `..` 的相对路径可以逃逸 `root_dir`
                - Agent 拥有无限制的文件系统访问权限

                **安全说明：** `virtual_mode=True` 提供基于路径的访问控制，
                而非进程隔离。
            max_file_size_mb: grep 搜索时的最大文件大小限制（MB）。
                超过此限制的文件在搜索时会被跳过。默认为 10 MB。
        """
        self.cwd = Path(root_dir).resolve() if root_dir else Path.cwd()
        self.virtual_mode = virtual_mode
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def _resolve_path(self, key: str) -> Path:
        """解析文件路径并进行安全检查。

        当 `virtual_mode=True` 时，将传入路径视为 `self.cwd` 下的虚拟绝对路径，
        禁止遍历（`..`、`~`）并确保解析后的路径保持在根目录内。

        当 `virtual_mode=False` 时，保持传统行为：绝对路径直接使用；
        相对路径在 cwd 下解析。

        Args:
            key: 文件路径（绝对路径、相对路径，或当 `virtual_mode=True` 时为虚拟路径）

        Returns:
            解析后的绝对 `Path` 对象

        Raises:
            ValueError: 当在 `virtual_mode` 下尝试路径遍历，
                或解析后的路径逃逸根目录时抛出
        """
        if self.virtual_mode:
            vpath = key if key.startswith("/") else "/" + key
            if ".." in vpath or vpath.startswith("~"):
                raise ValueError("不允许路径遍历")
            full = (self.cwd / vpath.lstrip("/")).resolve()
            try:
                full.relative_to(self.cwd)
            except ValueError:
                raise ValueError(f"路径 {full} 超出根目录范围: {self.cwd}") from None
            return full

        path = Path(key)
        if path.is_absolute():
            return path
        return (self.cwd / path).resolve()

    def ls_info(self, path: str) -> list[FileInfo]:
        """列出目录中的文件和目录（非递归）。

        Args:
            path: 要列出内容的目录路径

        Returns:
            FileInfo 字典列表，包含目录中文件和目录的信息。
            目录的路径以 '/' 结尾，is_dir=True。
        """
        try:
            dir_path = self._resolve_path(path)
        except ValueError:
            return []

        if not dir_path.exists() or not dir_path.is_dir():
            return []

        results: list[FileInfo] = []
        # 转换 cwd 为字符串用于比较
        cwd_str = str(self.cwd)
        if not cwd_str.endswith("/"):
            cwd_str += "/"

        # 仅列出直接子项（非递归）
        try:
            for child_path in dir_path.iterdir():
                try:
                    is_file = child_path.is_file()
                    is_dir = child_path.is_dir()
                except OSError:
                    continue

                abs_path = str(child_path)

                if not self.virtual_mode:
                    # 非虚拟模式：使用绝对路径
                    if is_file:
                        try:
                            st = child_path.stat()
                            results.append(
                                {
                                    "path": abs_path,
                                    "is_dir": False,
                                    "size": int(st.st_size),
                                    "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                                }
                            )
                        except OSError:
                            results.append({"path": abs_path, "is_dir": False})
                    elif is_dir:
                        try:
                            st = child_path.stat()
                            results.append(
                                {
                                    "path": abs_path + "/",
                                    "is_dir": True,
                                    "size": 0,
                                    "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                                }
                            )
                        except OSError:
                            results.append({"path": abs_path + "/", "is_dir": True})
                else:
                    # 虚拟模式：去除 cwd 前缀
                    if abs_path.startswith(cwd_str):
                        relative_path = abs_path[len(cwd_str) :]
                    elif abs_path.startswith(str(self.cwd)):
                        # 处理 cwd 不以 / 结尾的情况
                        relative_path = abs_path[len(str(self.cwd)) :].lstrip("/")
                    else:
                        # 路径在 cwd 外，原样返回或跳过
                        relative_path = abs_path

                    virt_path = "/" + relative_path

                    if is_file:
                        try:
                            st = child_path.stat()
                            results.append(
                                {
                                    "path": virt_path,
                                    "is_dir": False,
                                    "size": int(st.st_size),
                                    "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                                }
                            )
                        except OSError:
                            results.append({"path": virt_path, "is_dir": False})
                    elif is_dir:
                        try:
                            st = child_path.stat()
                            results.append(
                                {
                                    "path": virt_path + "/",
                                    "is_dir": True,
                                    "size": 0,
                                    "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                                }
                            )
                        except OSError:
                            results.append({"path": virt_path + "/", "is_dir": True})
        except (OSError, PermissionError):
            pass

        # 按路径排序保持确定性顺序
        results.sort(key=lambda x: x.get("path", ""))
        return results

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> str:
        """读取文件内容（带行号）。

        Args:
            file_path: 文件路径（绝对或相对）
            offset: 起始行号（0-indexed）
            limit: 最大读取行数

        Returns:
            带行号格式化的文件内容，或错误信息
        """
        try:
            resolved_path = self._resolve_path(file_path)
        except ValueError as e:
            return f"Error: {e}"

        if not resolved_path.exists() or not resolved_path.is_file():
            return f"Error: File '{file_path}' not found"

        try:
            # 使用 O_NOFOLLOW 避免符号链接遍历（如果操作系统支持）
            fd = os.open(resolved_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                content = f.read()

            empty_msg = check_empty_content(content)
            if empty_msg:
                return empty_msg

            lines = content.splitlines()
            start_idx = offset
            end_idx = min(start_idx + limit, len(lines))

            if start_idx >= len(lines):
                return f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"

            selected_lines = lines[start_idx:end_idx]
            return format_content_with_line_numbers(selected_lines, start_line=start_idx + 1)
        except (OSError, UnicodeDecodeError) as e:
            return f"Error reading file '{file_path}': {e}"

    def write(
        self,
        file_path: str,
        content: str,
    ) -> WriteResult:
        """创建新文件并写入内容。

        Args:
            file_path: 新文件的路径
            content: 要写入的文本内容

        Returns:
            WriteResult，成功时包含路径，失败时包含错误信息。
            外部存储时 files_update=None。
        """
        try:
            resolved_path = self._resolve_path(file_path)
        except ValueError as e:
            return WriteResult(error=str(e))

        if resolved_path.exists():
            return WriteResult(
                error=f"Cannot write to {file_path} because it already exists. "
                "Read and then make an edit, or write to a new path."
            )

        try:
            # 如果需要则创建父目录
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

            # 优先使用 O_NOFOLLOW 避免通过符号链接写入
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW

            fd = os.open(resolved_path, flags, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)

            return WriteResult(path=file_path, files_update=None)
        except (OSError, UnicodeEncodeError) as e:
            return WriteResult(error=f"Error writing file '{file_path}': {e}")

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        """通过替换字符串编辑文件。

        Args:
            file_path: 要编辑的文件路径
            old_string: 要搜索和替换的文本
            new_string: 替换后的文本
            replace_all: 如果为 True，替换所有出现。如果为 False（默认），
                只有当 old_string 在文件中唯一时才替换。

        Returns:
            EditResult，成功时包含路径和替换次数，失败时包含错误信息。
            外部存储时 files_update=None。
        """
        try:
            resolved_path = self._resolve_path(file_path)
        except ValueError as e:
            return EditResult(error=str(e))

        if not resolved_path.exists() or not resolved_path.is_file():
            return EditResult(error=f"Error: File '{file_path}' not found")

        try:
            # 安全读取
            fd = os.open(resolved_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as f:
                content = f.read()

            result = perform_string_replacement(content, old_string, new_string, replace_all)
            if isinstance(result, str):
                return EditResult(error=result)

            new_content, occurrences = result

            # 安全写入
            flags = os.O_WRONLY | os.O_TRUNC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW

            fd = os.open(resolved_path, flags)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new_content)

            return EditResult(path=file_path, files_update=None, occurrences=int(occurrences))
        except (OSError, UnicodeDecodeError, UnicodeEncodeError) as e:
            return EditResult(error=f"Error editing file '{file_path}': {e}")

    def grep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ) -> list[GrepMatch] | str:
        """在文件中搜索正则表达式模式。

        如果可用则使用 ripgrep，否则回退到 Python 正则表达式搜索。

        Args:
            pattern: 要搜索的正则表达式模式
            path: 要搜索的目录或文件路径。默认为当前目录。
            glob: 可选的 glob 模式，用于过滤要搜索的文件

        Returns:
            GrepMatch 字典列表，包含路径、行号和匹配文本。
            如果正则表达式模式无效，返回错误字符串。
        """
        # 验证正则表达式
        try:
            re.compile(pattern)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        # 解析基础路径
        try:
            base_full = self._resolve_path(path or ".")
        except ValueError:
            return []

        if not base_full.exists():
            return []

        # 优先尝试 ripgrep
        results = self._ripgrep_search(pattern, base_full, glob)
        if results is None:
            results = self._python_search(pattern, base_full, glob)

        matches: list[GrepMatch] = []
        for fpath, items in results.items():
            for line_num, line_text in items:
                matches.append({"path": fpath, "line": int(line_num), "text": line_text})

        return matches

    def _ripgrep_search(
        self, pattern: str, base_full: Path, include_glob: str | None
    ) -> dict[str, list[tuple[int, str]]] | None:
        """使用 ripgrep 进行 JSON 输出解析的搜索。

        Args:
            pattern: 要搜索的正则表达式模式
            base_full: 解析后的基础搜索路径
            include_glob: 可选的文件过滤 glob 模式

        Returns:
            字典，映射文件路径到 `(行号, 行文本)` 元组列表。
            如果 ripgrep 不可用或超时，返回 `None`。
        """
        cmd = ["rg", "--json"]
        if include_glob:
            cmd.extend(["--glob", include_glob])
        cmd.extend(["--", pattern, str(base_full)])

        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

        results: dict[str, list[tuple[int, str]]] = {}
        for line in proc.stdout.splitlines():
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if data.get("type") != "match":
                continue

            pdata = data.get("data", {})
            ftext = pdata.get("path", {}).get("text")
            if not ftext:
                continue

            p = Path(ftext)
            if self.virtual_mode:
                try:
                    virt = "/" + str(p.resolve().relative_to(self.cwd))
                except Exception:
                    continue
            else:
                virt = str(p)

            ln = pdata.get("line_number")
            lt = pdata.get("lines", {}).get("text", "").rstrip("\n")
            if ln is None:
                continue

            results.setdefault(virt, []).append((int(ln), lt))

        return results

    def _python_search(
        self,
        pattern: str,
        base_full: Path,
        include_glob: str | None,
    ) -> dict[str, list[tuple[int, str]]]:
        """当 ripgrep 不可用时使用 Python 正则表达式进行回退搜索。

        递归搜索文件，遵守 `max_file_size_bytes` 限制。

        Args:
            pattern: 要搜索的正则表达式模式
            base_full: 解析后的基础搜索路径
            include_glob: 可选的文件名 glob 模式过滤

        Returns:
            字典，映射文件路径到 `(行号, 行文本)` 元组列表
        """
        try:
            regex = re.compile(pattern)
        except re.error:
            return {}

        results: dict[str, list[tuple[int, str]]] = {}
        root = base_full if base_full.is_dir() else base_full.parent

        for fp in root.rglob("*"):
            try:
                if not fp.is_file():
                    continue
            except (PermissionError, OSError):
                continue

            # 应用 glob 过滤
            if include_glob and not fnmatch.fnmatch(fp.name, include_glob):
                continue

            # 检查文件大小限制
            try:
                if fp.stat().st_size > self.max_file_size_bytes:
                    continue
            except OSError:
                continue

            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue

            for line_num, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    if self.virtual_mode:
                        try:
                            virt_path = "/" + str(fp.resolve().relative_to(self.cwd))
                        except Exception:
                            continue
                    else:
                        virt_path = str(fp)
                    results.setdefault(virt_path, []).append((line_num, line))

        return results

    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        """查找匹配 glob 模式的文件。

        Args:
            pattern: 要匹配的 glob 模式（如 `'*.py'`、`'**/*.txt'`）
            path: 搜索的基础目录。默认为根目录（`/`）。

        Returns:
            匹配文件的 FileInfo 字典列表，按路径排序。
            每个字典包含 `path`、`is_dir`、`size` 和 `modified_at` 字段。
        """
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")

        search_path = self.cwd if path == "/" else self._resolve_path(path)
        if not search_path.exists() or not search_path.is_dir():
            return []

        results: list[FileInfo] = []
        try:
            # 使用递归 globbing 匹配子目录中的文件
            for matched_path in search_path.rglob(pattern):
                try:
                    is_file = matched_path.is_file()
                except (PermissionError, OSError):
                    continue

                if not is_file:
                    continue

                abs_path = str(matched_path)

                if not self.virtual_mode:
                    try:
                        st = matched_path.stat()
                        results.append(
                            {
                                "path": abs_path,
                                "is_dir": False,
                                "size": int(st.st_size),
                                "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                            }
                        )
                    except OSError:
                        results.append({"path": abs_path, "is_dir": False})
                else:
                    cwd_str = str(self.cwd)
                    if not cwd_str.endswith("/"):
                        cwd_str += "/"
                    if abs_path.startswith(cwd_str):
                        relative_path = abs_path[len(cwd_str) :]
                    elif abs_path.startswith(str(self.cwd)):
                        relative_path = abs_path[len(str(self.cwd)) :].lstrip("/")
                    else:
                        relative_path = abs_path

                    virt = "/" + relative_path
                    try:
                        st = matched_path.stat()
                        results.append(
                            {
                                "path": virt,
                                "is_dir": False,
                                "size": int(st.st_size),
                                "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                            }
                        )
                    except OSError:
                        results.append({"path": virt, "is_dir": False})
        except (OSError, ValueError):
            pass

        results.sort(key=lambda x: x.get("path", ""))
        return results

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传多个文件到文件系统。

        Args:
            files: (路径, 内容) 元组列表，其中内容为 bytes

        Returns:
            FileUploadResponse 对象列表，每个输入文件一个。
            响应顺序与输入顺序匹配。
        """
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                resolved_path = self._resolve_path(path)

                # 如果需要则创建父目录
                resolved_path.parent.mkdir(parents=True, exist_ok=True)

                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                fd = os.open(resolved_path, flags, 0o644)
                with os.fdopen(fd, "wb") as f:
                    f.write(content)

                responses.append({"path": path, "error": None})
            except FileNotFoundError:
                responses.append({"path": path, "error": "file_not_found"})
            except PermissionError:
                responses.append({"path": path, "error": "permission_denied"})
            except (ValueError, OSError) as e:
                # ValueError 来自 _resolve_path 的路径遍历检测，OSError 来自其他文件错误
                if isinstance(e, ValueError) or "invalid" in str(e).lower():
                    responses.append({"path": path, "error": "invalid_path"})
                else:
                    # 通用错误回退
                    responses.append({"path": path, "error": "invalid_path"})

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从文件系统下载多个文件。

        Args:
            paths: 要下载的文件路径列表

        Returns:
            FileDownloadResponse 对象列表，每个输入路径一个。
        """
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                resolved_path = self._resolve_path(path)

                # 如果操作系统支持，使用 O_NOFOLLOW 防止符号链接跟随
                fd = os.open(resolved_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "rb") as f:
                    content = f.read()

                responses.append({"path": path, "content": content, "error": None})
            except FileNotFoundError:
                responses.append({"path": path, "content": None, "error": "file_not_found"})
            except PermissionError:
                responses.append({"path": path, "content": None, "error": "permission_denied"})
            except IsADirectoryError:
                responses.append({"path": path, "content": None, "error": "is_directory"})
            except ValueError:
                responses.append({"path": path, "content": None, "error": "invalid_path"})
            # 其他错误让其传播

        return responses

    def execute(
        self,
        command: str,
        timeout: int = 120,
        max_output_size: int = 100000,
    ) -> ExecuteResult:
        """在沙箱环境中执行 shell 命令。

        Args:
            command: 要执行的 shell 命令
            timeout: 命令超时时间（秒），默认 120 秒
            max_output_size: 输出最大字符数，超过则截断，默认 100000

        Returns:
            ExecuteResult，包含输出、退出码和截断标志
        """
        try:
            proc = subprocess.run(  # noqa: S602
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.cwd),
            )

            # 合并 stdout 和 stderr
            output = proc.stdout
            if proc.stderr:
                if output:
                    output += "\n" + proc.stderr
                else:
                    output = proc.stderr

            # 检查是否需要截断
            truncated = False
            if len(output) > max_output_size:
                output = output[:max_output_size]
                truncated = True

            return ExecuteResult(
                output=output,
                exit_code=proc.returncode,
                truncated=truncated,
            )
        except subprocess.TimeoutExpired:
            return ExecuteResult(
                output=f"Error: Command timed out after {timeout} seconds",
                exit_code=None,
                truncated=False,
            )
        except OSError as e:
            return ExecuteResult(
                output=f"Error executing command: {e}",
                exit_code=None,
                truncated=False,
            )

    async def aexecute(
        self,
        command: str,
        timeout: int = 120,
        max_output_size: int = 100000,
    ) -> ExecuteResult:
        """异步执行 shell 命令。

        Args:
            command: 要执行的 shell 命令
            timeout: 命令超时时间（秒），默认 120 秒
            max_output_size: 输出最大字符数，超过则截断，默认 100000

        Returns:
            ExecuteResult，包含输出、退出码和截断标志
        """
        import asyncio

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.cwd),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ExecuteResult(
                    output=f"Error: Command timed out after {timeout} seconds",
                    exit_code=None,
                    truncated=False,
                )

            # 解码输出
            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            # 合并 stdout 和 stderr
            output = stdout_str
            if stderr_str:
                if output:
                    output += "\n" + stderr_str
                else:
                    output = stderr_str

            # 检查是否需要截断
            truncated = False
            if len(output) > max_output_size:
                output = output[:max_output_size]
                truncated = True

            return ExecuteResult(
                output=output,
                exit_code=proc.returncode,
                truncated=truncated,
            )
        except OSError as e:
            return ExecuteResult(
                output=f"Error executing command: {e}",
                exit_code=None,
                truncated=False,
            )
