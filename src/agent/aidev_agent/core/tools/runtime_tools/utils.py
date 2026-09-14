# -*- coding: utf-8 -*-
"""aidev_agent.core.tools.runtime_tools.utils

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

运行时后端共享工具函数。

该模块包含可被不同 runtime 后端复用的函数与类型：
- 虚拟路径校验与规范化（validate_path）
- 读写/编辑内容辅助（check_empty_content / perform_string_replacement）
- 输出格式化（format_content_with_line_numbers / truncate_if_too_long / format_grep_matches）
- LangGraph 文件系统状态类型（FileData / FilesystemState）
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from typing import Annotated, Callable, Sequence

from typing_extensions import NotRequired, TypedDict

# ========== 常量定义 ==========

EMPTY_CONTENT_WARNING = "系统提示: 文件存在但内容为空"
"""空文件内容警告消息"""

LINE_NUMBER_WIDTH = 6
"""行号显示宽度"""

# ========== 异常类 ==========


class PathValidationError(Exception):
    """路径验证错误异常。

    当路径验证失败时抛出此异常，例如路径遍历攻击检测、
    不支持的路径格式或路径不在允许的前缀列表中。
    """


# ========== TypedDict 类型定义 ==========


class FileData(TypedDict):
    """文件数据结构。

    用于存储文件内容及其元数据信息。

    Attributes:
        content: 文件内容行列表
        created_at: 文件创建时间（ISO 8601 格式）
        modified_at: 文件最后修改时间（ISO 8601 格式）
    """

    content: list[str]
    """文件内容行列表"""

    created_at: str
    """文件创建时间（ISO 8601 格式）"""

    modified_at: str
    """文件最后修改时间（ISO 8601 格式）"""


class FilesystemState(TypedDict):
    """文件系统状态结构。

    用于 LangGraph 状态管理的文件系统状态定义。

    Attributes:
        files: 文件映射字典，键为文件路径，值为 FileData
    """

    files: Annotated[NotRequired[dict[str, FileData]], "_file_data_reducer"]
    """文件映射字典"""


# ========== 工具函数 ==========


def _file_data_reducer(left: dict[str, FileData] | None, right: dict[str, FileData | None]) -> dict[str, FileData]:
    """合并文件数据更新，支持删除操作。

    此 reducer 函数用于 LangGraph 状态管理，通过将 right 字典中的 None 值
    作为删除标记来实现文件删除功能。

    Args:
        left: 现有文件字典，初始化时可能为 None
        right: 要合并的新文件字典，值为 None 表示删除该文件

    Returns:
        合并后的字典，right 覆盖 left 中的同名键，
        right 中值为 None 的键会从结果中删除

    Example:
        >>> existing = {"/file1.txt": FileData(...), "/file2.txt": FileData(...)}
        >>> updates = {"/file2.txt": None, "/file3.txt": FileData(...)}
        >>> result = _file_data_reducer(existing, updates)
        # 结果: {"/file1.txt": FileData(...), "/file3.txt": FileData(...)}
    """
    if left is None:
        return {k: v for k, v in right.items() if v is not None}

    result = {**left}
    for key, value in right.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = value
    return result


def validate_path(path: str, *, allowed_prefixes: Sequence[str] | None = None) -> str:
    r"""验证并规范化文件路径。

    确保路径安全可用，防止目录遍历攻击并强制使用一致的格式。
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
        PathValidationError: 当路径包含遍历序列（`..` 或 `~`）、
            是 Windows 绝对路径（如 C:/...）、或不以允许的前缀开头时抛出

    Example:
        >>> validate_path("foo/bar")
        '/foo/bar'
        >>> validate_path("/./foo//bar")
        '/foo/bar'
        >>> validate_path("../etc/passwd")  # 抛出 PathValidationError
        >>> validate_path(r"C:\\Users\\file.txt")  # 抛出 PathValidationError
        >>> validate_path("/data/file.txt", allowed_prefixes=["/data/"])  # 正常
        >>> validate_path("/etc/file.txt", allowed_prefixes=["/data/"])  # 抛出异常
    """
    if ".." in path or path.startswith("~"):
        msg = f"不允许路径遍历: {path}"
        raise PathValidationError(msg)

    # 拒绝 Windows 绝对路径（如 C:\...、D:/...）
    # 这保持了虚拟文件系统路径的一致性
    if re.match(r"^[a-zA-Z]:", path):
        msg = f"不支持 Windows 绝对路径: {path}。请使用以 / 开头的虚拟路径（如 /workspace/file.txt）"
        raise PathValidationError(msg)

    normalized = os.path.normpath(path)
    normalized = normalized.replace("\\\\", "/")

    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    if allowed_prefixes is not None and not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
        msg = f"路径必须以 {allowed_prefixes} 之一开头: {path}"
        raise PathValidationError(msg)

    return normalized


def check_empty_content(content: str) -> str | None:
    """检查文件内容是否为空。

    用于在读取文件后检测空文件情况，以便向用户提供适当的警告。

    Args:
        content: 文件内容字符串

    Returns:
        如果内容为空或仅包含空白字符，返回警告消息；
        否则返回 None

    Example:
        >>> check_empty_content("")
        '系统提示: 文件存在但内容为空'
        >>> check_empty_content("   \\n\\t  ")
        '系统提示: 文件存在但内容为空'
        >>> check_empty_content("hello world")
        None
    """
    if not content or not content.strip():
        return EMPTY_CONTENT_WARNING
    return None


def format_content_with_line_numbers(lines: list[str], start_line: int = 1) -> str:
    """为文件内容添加行号格式化（**纯展示函数**）。

    将文件行列表格式化为带有行号前缀的字符串，行号右对齐（宽度
    :data:`LINE_NUMBER_WIDTH`）并用制表符分隔，各展示行以 ``"\\n"`` 连接。

    本函数只做展示修饰：**不做脱敏、不做任何文本转换**。
    脱敏必须在调用本函数**之前**由 provider 完成 —— 否则「格式化后的展示字符」
    会被脱敏 guard 当成秘密正文而误报，且跨行掩码压缩行数会让行号错位。

    Args:
        lines: 文件行列表（原始行，不含行号）
        start_line: 片段首行在原文件中的 1-based 行号，默认为 1

    Returns:
        带行号的格式化内容字符串

    Example:
        >>> lines = ["def foo():", "    pass"]
        >>> print(format_content_with_line_numbers(lines))
             1\tdef foo():
             2\t    pass
        >>> print(format_content_with_line_numbers(lines, start_line=10))
            10\tdef foo():
            11\t    pass
    """
    result = []
    for i, line in enumerate(lines):
        line_num = start_line + i
        result.append(f"{line_num:>{LINE_NUMBER_WIDTH}}\t{line}")
    return "\n".join(result)


def perform_string_replacement(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> tuple[str, int]:
    """执行精确字符串替换。

    在内容中查找并替换指定的字符串。支持替换单个匹配项或所有匹配项。
    当存在多个匹配项但未启用全部替换时，会抛出 ValueError 以避免意外修改。

    Args:
        content: 原始内容字符串
        old_string: 要替换的目标字符串
        new_string: 替换后的新字符串
        replace_all: 是否替换所有匹配项，默认为 False

    Returns:
        成功时返回 (新内容, 替换次数) 元组

    Raises:
        ValueError: 当 old_string 为空、old_string 与 new_string 相同、
                   未找到匹配项或找到多个匹配项但未启用全部替换时

    Example:
        >>> perform_string_replacement("hello world", "world", "python")
        ('hello python', 1)
        >>> perform_string_replacement("a b a", "a", "x", replace_all=True)
        ('x b x', 2)
        >>> perform_string_replacement("a b a", "a", "x")
        Traceback (most recent call last):
        ...
        ValueError: 找到 2 个匹配项，请设置 replace_all=True 或提供更精确的匹配字符串
        >>> perform_string_replacement("hello", "", "x")
        Traceback (most recent call last):
        ...
        ValueError: old_string 不能为空
    """
    if not old_string:
        raise ValueError("old_string 不能为空")

    if old_string == new_string:
        raise ValueError("old_string 和 new_string 不能相同")

    if old_string not in content:
        raise ValueError("在文件中未找到匹配的字符串")

    count = content.count(old_string)
    if not replace_all and count > 1:
        raise ValueError(f"找到 {count} 个匹配项，请设置 replace_all=True 或提供更精确的匹配字符串")

    if replace_all:
        new_content = content.replace(old_string, new_string)
        return (new_content, count)
    else:
        new_content = content.replace(old_string, new_string, 1)
        return (new_content, 1)


# ========== 输出格式化函数 ==========

MAX_OUTPUT_LENGTH = 30000
"""输出内容最大长度限制"""


def truncate_if_too_long(content: list[str] | str) -> str:
    """截断过长的输出内容。

    如果内容超过最大长度限制，则截断并添加提示信息。

    Args:
        content: 要处理的内容，可以是字符串或字符串列表

    Returns:
        处理后的字符串，如果需要截断则附带提示信息

    Example:
        >>> truncate_if_too_long(["file1.py", "file2.py"])
        'file1.py\\nfile2.py'
        >>> truncate_if_too_long("short text")
        'short text'
    """
    result = "\n".join(content) if isinstance(content, list) else content
    if len(result) > MAX_OUTPUT_LENGTH:
        truncated = result[:MAX_OUTPUT_LENGTH]
        return f"{truncated}\n\n[输出已截断，超过 {MAX_OUTPUT_LENGTH} 字符限制]"
    return result


def format_grep_matches(
    matches: list[dict],
    output_mode: str = "files_with_matches",
    *,
    transform: Callable[[str], str] | None = None,
) -> str:
    """格式化 grep 搜索结果（**纯展示**：路径与行号前缀最后才拼接）。

    Args:
        matches: GrepMatch 字典列表，每个包含 path、line、text 字段
        output_mode: 输出模式，可选值：
            - "files_with_matches": 仅输出文件路径（默认）
            - "content": 输出匹配行及其内容
            - "count": 输出每个文件的匹配数量
        transform: 可选的**原文**转换回调（通常是脱敏）。在拼接 ``path:line:``
            展示前缀**之前**，对路径与按原文件连续行分组的文本调用；``None``
            时行为与历史逐字一致。``content`` 模式下同文件乱序 / 缺行 / 重复
            行号会断开分组，不跨文件拼接，避免把互不相邻的行误当作一个块。

    Returns:
        格式化后的结果字符串

    Example:
        >>> matches = [
        ...     {"path": "/a.py", "line": 1, "text": "import os"},
        ...     {"path": "/a.py", "line": 5, "text": "import sys"},
        ...     {"path": "/b.py", "line": 2, "text": "import re"},
        ... ]
        >>> format_grep_matches(matches, "files_with_matches")
        '/a.py\\n/b.py'
        >>> format_grep_matches(matches, "count")
        '/a.py: 2\\n/b.py: 1'
    """
    if not matches:
        return "未找到匹配"

    def show(value: str) -> str:
        return transform(value) if transform is not None else value

    if output_mode == "content":
        # 分组仅用于整块原文脱敏；展示顺序仍按原始匹配顺序。
        grouped = _group_consecutive_matches(matches)
        shown: dict[int, str] = {}
        for group in grouped:
            joined = "\n".join(m.get("text", "") for m in group)
            rendered = show(joined).split("\n")
            for member, piece in zip(group, rendered):
                shown[id(member)] = piece
        result = "\n".join(f"{show(m.get('path', ''))}:{m.get('line', 0)}: {shown[id(m)]}" for m in matches)
    elif output_mode == "count":
        # 统计用**原始**路径：脱敏后的显示值碰撞不得合并计数。
        counts: dict[str, int] = {}
        for m in matches:
            p = m.get("path", "")
            counts[p] = counts.get(p, 0) + 1
        result = "\n".join(f"{show(path)}: {count}" for path, count in counts.items())
    else:
        # files_with_matches（含默认回落）：按原始路径去重后再脱敏显示。
        seen = set()
        paths = []
        for m in matches:
            p = m.get("path", "")
            if p and p not in seen:
                seen.add(p)
                paths.append(p)
        result = "\n".join(show(p) for p in paths)

    return result


def _group_consecutive_matches(matches: list[dict]) -> list[list[dict]]:
    """把匹配记录按「同一文件 + 行号连续」分组，供整块脱敏使用。

    仅行号恰好递增 1 才并入同组；换文件、缺行、重复行号一律断开，故不会把
    互不相邻的内容拼成一个块（否则多行 PEM 之类的结构会被误拼）。
    """
    groups: list[list[dict]] = []
    current: list[dict] = []
    for m in matches:
        if current and (m.get("path") != current[-1].get("path") or m.get("line") != current[-1].get("line", 0) + 1):
            groups.append(current)
            current = []
        current.append(m)
    if current:
        groups.append(current)
    return groups


# ========== Skill 打包工具 ==========

# 打包时排除的目录名（模块级常量，作为默认值参考）
_DEFAULT_EXCLUDE_DIRS: set[str] = {"__pycache__", ".git", "node_modules", ".venv"}

# 打包时排除的文件扩展名（模块级常量，作为默认值参考）
_DEFAULT_EXCLUDE_EXTENSIONS: tuple[str, ...] = (".pyc", ".pyo")

# 为向后兼容保留的导出常量
EXCLUDE_DIRS: set[str] = _DEFAULT_EXCLUDE_DIRS
EXCLUDE_EXTENSIONS: tuple[str, ...] = _DEFAULT_EXCLUDE_EXTENSIONS


def package_dir(
    skill_dir: str,
    exclude_dirs: set[str] | None = None,
    exclude_extensions: tuple[str, ...] | None = None,
) -> bytes:
    """将 skill 目录打包为 zip 字节流。

    遍历 *skill_dir* 下的所有文件，排除临时目录和编译产物，
    使用 ``ZIP_DEFLATED`` 压缩后返回完整的 zip 文件字节流。

    Args:
        skill_dir: skill 根目录的本地路径（应包含 SKILL.md、scripts/ 等）。
        exclude_dirs: 打包时排除的目录名集合。默认为 None，使用内置默认值
            {"__pycache__", ".git", "node_modules", ".venv"}。
        exclude_extensions: 打包时排除的文件扩展名元组。默认为 None，使用内置默认值
            (".pyc", ".pyo")。

    Returns:
        zip 文件的 bytes 内容。
    """
    # 使用提供的参数或落回到默认值
    if exclude_dirs is None:
        exclude_dirs = _DEFAULT_EXCLUDE_DIRS
    if exclude_extensions is None:
        exclude_extensions = _DEFAULT_EXCLUDE_EXTENSIONS

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(skill_dir):
            # 就地修改 dirs 以跳过排除目录
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for f in files:
                if f.endswith(exclude_extensions):
                    continue
                filepath = os.path.join(root, f)
                arcname = os.path.relpath(filepath, skill_dir)
                zf.write(filepath, arcname)
    return buffer.getvalue()


# ========== 导出 ==========

__all__ = [
    # 常量
    "EMPTY_CONTENT_WARNING",
    "LINE_NUMBER_WIDTH",
    "MAX_OUTPUT_LENGTH",
    "EXCLUDE_DIRS",
    "EXCLUDE_EXTENSIONS",
    # 异常类
    "PathValidationError",
    # 类型定义
    "FileData",
    "FilesystemState",
    # 函数
    "_file_data_reducer",
    "validate_path",
    "check_empty_content",
    "format_content_with_line_numbers",
    "perform_string_replacement",
    "truncate_if_too_long",
    "format_grep_matches",
    "package_dir",
]
