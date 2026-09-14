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

BubblewrapFilesystemBackend: 以 bubblewrap 子进程提供内核级文件隔离的运行时后端。

与 :class:`~.local_backend.FilesystemBackend`（纯同进程 ``os.open``/``Path``
读写）并列的独立后端实现，经 resolver 以 runtime 类型名 ``bubblewrap`` 注册。
read/write/ls/glob/grep/edit/execute/upload/download 全部在同进程之外的内核
沙箱中执行。

本类同时承载「bwrap 执行器」与「RuntimeBackend 契约」两项职责：argv 组装、
子进程执行、路径安全、契约映射、序列化全部内聚于一个类，不委派任何外部
sandbox 对象。低层原语（``_run``/``_read_text``/…）刻意保持私有，公开方法
只暴露 RuntimeBackend 契约，防止原语泄漏为后端公共 API。

四条围栏（对齐 Claude Code / Langdata 中心化沙箱的设计原则）：

1. **默认什么都不给**：沙箱根是空 tmpfs，仅显式挂载 ``readonly_paths``
   （默认 ``/usr,/bin,/lib,/lib64``，提供 cat/find/rg/python3 等命令所需的
   可执行文件与动态库）与工作区（``cwd``）。``/etc``、``/root``、``/home``
   等敏感目录**不挂载**，沙箱内「不存在」而非「无权限」。
2. **能只读绝不给写**：系统目录 ``--ro-bind``，仅工作区可写（``--bind``）；
   read 类操作工作区也以 ``--ro-bind`` 暴露。
3. **默认关闭网络**：``--unshare-net``，read/write 默认无网，阻断外泄/SSRF。
4. **进程隔离 + 共存亡**：``--die-with-parent``，沙箱内进程随调用方退出而终止。
   ``--unshare-pid`` 未使用（受限容器内与 ``--proc`` 挂载冲突）。

fail-open 语义：本模块**不抛异常**。``is_available()`` 探测 bwrap 二进制是否
存在且能创建沙箱；不可用或执行失败时，由调用方决定退回同进程现状路径，
仅记录日志——评估阶段关闭开关即可观测行为差异。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from aidev_agent.pydantic_models import SandboxPolicy

from .local_backend import resolve_sandbox_path, to_virtual_path
from .types import (
    EditResult,
    ExecuteResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    ReadResult,
    RuntimeBackend,
    WriteResult,
)
from .utils import (
    check_empty_content,
    perform_string_replacement,
)

logger = logging.getLogger(__name__)

# 默认只读挂载的系统目录：提供常用命令（cat/find/rg/python3/sh）及动态库，
# 不含 /etc、/root、/home 等敏感路径（按需最小暴露）。
DEFAULT_READONLY_PATHS = "/usr,/bin,/lib,/lib64"


@dataclass
class BwrapResult:
    """bwrap 子进程执行结果。

    Attributes:
        output: 合并后的 stdout + stderr（stdout 优先，stderr 追加）。
        exit_code: 退出码；``None`` 表示执行过程异常（如超时/未启动）。
    """

    output: str = ""
    exit_code: int | None = None


class BubblewrapFilesystemBackend(RuntimeBackend):
    """以 bubblewrap 子进程执行文件操作的运行时后端。

    组合（而非继承）:class:`~.local_backend.FilesystemBackend` 的路径语义：
    复用模块级路径 helper（:func:`~.local_backend.resolve_sandbox_path` /
    :func:`~.local_backend.to_virtual_path`）保证「虚拟路径映射 + 敏感路径拒绝」
    与同进程后端一致。

    本类自行持有 :class:`SandboxPolicy`（不再经由独立的执行器对象），同时承担
    bwrap argv 组装（``_prefix``）与子进程执行（``_run`` 及文件原语）。

    !!! warning "安全警告"
        此后端为 Agent 提供受内核隔离约束的文件系统访问能力。沙箱内仅可见工作区
        与显式只读挂载的系统目录，``/etc``、``/root``、``/home`` 等敏感目录**不挂载**。

    Args:
        root_dir: 工作区根目录（沙箱内唯一数据挂载点）。未提供时默认为当前工作目录。
        virtual_mode: 启用基于路径的访问限制（所有路径锚定到 `root_dir`）。
        max_file_size_mb: grep 搜索时的最大文件大小限制（MB）。
        envs: 环境变量字典；包含 ``SKILL_DIR`` 时自动切换到 skill 目录。
        sandbox_policy: 平台无关沙箱策略（:class:`SandboxPolicy`）。提供时优先于
            ``bwrap_readonly_paths`` / ``bwrap_allow_network``。
        bwrap_readonly_paths: bwrap 沙箱只读挂载的系统目录（逗号分隔）。
            默认 ``DEFAULT_READONLY_PATHS``（/usr,/bin,/lib,/lib64），
            不含 /etc、/root、/home 等敏感目录（按需最小暴露）。
        bwrap_allow_network: bwrap 沙箱是否保留网络。默认 False（关网）。
        bwrap_path: bwrap 二进制路径，默认 ``bwrap``。

    Example:
        >>> backend = BubblewrapFilesystemBackend(root_dir="/workspace", virtual_mode=True)
        >>> infos = backend.ls_info("/src")
        >>> result = backend.read("/src/main.py", offset=0, limit=100)  # ReadResult 或错误文案
    """

    def __init__(
        self,
        root_dir: str | Path | None = None,
        virtual_mode: bool = False,
        max_file_size_mb: int = 10,
        envs: dict[str, str] | None = None,
        sandbox_policy: SandboxPolicy | None = None,
        bwrap_readonly_paths: str = DEFAULT_READONLY_PATHS,
        bwrap_allow_network: bool = False,
        bwrap_path: str = "bwrap",
    ) -> None:
        self.cwd = Path(root_dir).resolve() if root_dir else Path.cwd()
        self.virtual_mode = virtual_mode
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.envs = envs
        # 若 envs 中包含 skill 信息，自动切换 cwd 到 skill 目录
        if envs:
            skill_dir = envs.get("SKILL_DIR")
            if skill_dir:
                scripts_dir = os.path.join(skill_dir, "scripts")
                target = scripts_dir if os.path.isdir(scripts_dir) else skill_dir
                self.cwd = Path(target).resolve()
        if sandbox_policy is None:
            # 兼容旧接口：从 bwrap_readonly_paths / bwrap_allow_network 构建默认策略。
            rp = bwrap_readonly_paths if bwrap_readonly_paths is not None else DEFAULT_READONLY_PATHS
            sandbox_policy = SandboxPolicy(
                readonly_paths=[p.strip() for p in rp.split(",") if p.strip()],
                allow_network=bool(bwrap_allow_network),
            )
        # model_copy 隔离：探测降级（改 allow_network）只影响自身拷贝，不污染调用方传入对象。
        self._policy = sandbox_policy.model_copy()
        self._bwrap_path = bwrap_path
        # 构造期探测一次并缓存（本后端内部**不**据此绕回宿主机；由调用方决定
        # 是否降级——见 is_available()）。
        self._available: bool = self._probe()

    def is_available(self) -> bool:
        """bwrap 是否可用（构造期探测并缓存）。

        本后端**不**在内部 fail-open 绕回同进程路径：bwrap 不可用时文件操作会
        失败返回空/错误（不泄露宿主机内容）。调用方（``_prepare_skills``）应据
        此判定是否改用同进程 ``FilesystemBackend`` 降级。
        """
        return self._available

    # --- bwrap 执行器（argv 组装 + 子进程执行） ---

    def _probe(self) -> bool:
        if shutil.which(self._bwrap_path) is None:
            logger.warning("bwrap 不可用：未找到二进制 %s，文件能力将降级为同进程执行", self._bwrap_path)
            return False
        # 探测核心能力：user namespace + mount namespace + 只读 bind。
        # 显式 --unshare-user 是关键：容器/受限环境下（无有效 CAP_SYS_ADMIN，
        # 或被 seccomp 拦 mount namespace）仍需靠 user namespace 获得 mount 权限。
        try:
            proc = subprocess.run(  # noqa: S603
                [self._bwrap_path, "--unshare-user", "--ro-bind", "/", "/", "/bin/true"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            logger.warning("bwrap 探测失败，文件能力将降级为同进程执行", exc_info=True)
            return False
        if proc.returncode != 0:
            logger.warning(
                "bwrap 探测返回非零（%s）：%s，文件能力将降级为同进程执行",
                proc.returncode,
                (proc.stderr or b"").decode("utf-8", errors="replace").strip(),
            )
            return False
        # 若需关网，进一步探测 net namespace；不可用则降级为保留网络（文件隔离仍在）。
        if not self._policy.allow_network:
            try:
                proc_net = subprocess.run(  # noqa: S603
                    [self._bwrap_path, "--unshare-user", "--unshare-net", "--ro-bind", "/", "/", "/bin/true"],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                proc_net = None
            if proc_net is None or proc_net.returncode != 0:
                logger.warning("bwrap net namespace 不可用，网络隔离降级为放行（文件隔离仍生效）")
                self._policy.allow_network = True
        return True

    def _prefix(self, writable: bool) -> list[str]:
        """组装 bwrap 命令前缀（不含具体命令）。

        Args:
            writable: True 时工作区以 ``--bind`` 可写挂载，False 时 ``--ro-bind``。
        """
        root_dir = str(self.cwd)
        prefix = [self._bwrap_path, "--unshare-user"]
        for d in self._policy.readonly_paths:
            if os.path.isdir(d):
                prefix += ["--ro-bind", d, d]
        # 进程内依赖的虚拟文件系统（/proc 提供 procfs；/dev 提供 /dev/null 等）。
        # 注意：受限容器内 --unshare-pid 与 --proc 挂载会冲突，故不用 pid namespace，
        # 由 --die-with-parent 保证沙箱子进程随调用方退出。
        prefix += ["--proc", "/proc", "--dev", "/dev"]
        # 工作区：唯一数据挂载点
        flag = "--bind" if writable else "--ro-bind"
        prefix += [flag, root_dir, root_dir]
        prefix += ["--chdir", root_dir]
        if not self._policy.allow_network:
            prefix += ["--unshare-net"]
        prefix += ["--die-with-parent"]
        return prefix

    def _run(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        timeout: int = 120,
        writable: bool = True,
    ) -> BwrapResult:
        """在 bwrap 沙箱内执行命令。

        Args:
            args: 具体命令及其参数（如 ``["cat", path]``、``["sh", "-c", cmd]``）。
            input_text: 通过 stdin 传入的文本（write 类操作使用）。
            timeout: 超时秒数。
            writable: 工作区是否可写挂载。

        Returns:
            BwrapResult（不抛异常；超时/启动失败返回 exit_code=None）。
        """
        cmd = self._prefix(writable=writable) + ["--"] + args
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return BwrapResult(output=f"Error: command timed out after {timeout} seconds", exit_code=None)
        except OSError as e:
            return BwrapResult(output=f"Error executing in bwrap sandbox: {e}", exit_code=None)

        output = proc.stdout or ""
        if proc.stderr:
            output = output + ("\n" + proc.stderr if output else proc.stderr)
        return BwrapResult(output=output, exit_code=proc.returncode)

    # --- 高层文件操作原语（供 RuntimeBackend 方法复用） ---

    def _read_text(self, path: str) -> str | None:
        """读取文件全文；失败返回 None。"""
        res = self._run(["cat", path], writable=False)
        if res.exit_code != 0:
            return None
        return res.output

    def _write_text(self, path: str, content: str) -> bool:
        """写入文件（创建/覆盖），通过 stdin 传内容；返回是否成功。"""
        res = self._run(["sh", "-c", f"cat > {shlex.quote(path)}"], input_text=content, writable=True)
        return res.exit_code == 0

    def _read_bytes(self, path: str) -> bytes | None:
        """读取文件原始字节；失败返回 None（二进制模式，供 upload/download 复用）。"""
        cmd = self._prefix(writable=False) + ["--", "cat", path]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)  # noqa: S603
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout

    def _write_bytes(self, path: str, content: bytes) -> bool:
        """写入原始字节（创建/覆盖），通过 stdin 传内容；返回是否成功。"""
        cmd = self._prefix(writable=True) + ["--", "sh", "-c", f"cat > {shlex.quote(path)}"]
        try:
            proc = subprocess.run(cmd, input=content, capture_output=True, timeout=120, check=False)  # noqa: S603
        except (subprocess.TimeoutExpired, OSError):
            return False
        return proc.returncode == 0

    def _list_entries(self, path: str) -> list[dict]:
        """非递归列目录，返回 ``[{"path","is_dir","size","modified_at"}]``。"""
        res = self._run(
            ["find", path, "-maxdepth", "1", "-mindepth", "1", "-printf", "%y\t%p\t%s\t%T@\n"],
            writable=False,
        )
        if res.exit_code != 0:
            return []
        entries: list[dict] = []
        for line in res.output.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            typ, p, size, mtime = parts[0], parts[1], parts[2], parts[3]
            is_dir = typ == "d"
            try:
                modified_at = datetime.fromtimestamp(float(mtime)).isoformat()
            except (ValueError, OSError):
                modified_at = None
            entries.append(
                {"path": p, "is_dir": is_dir, "size": int(size) if not is_dir else 0, "modified_at": modified_at}
            )
        return entries

    def _glob_entries(self, path: str, pattern: str) -> list[dict]:
        """递归 glob 匹配文件，返回 ``[{"path","size","modified_at"}]``。

        ``find -name`` 匹配的是 basename，故此处将 ``**/*.py``、``subdir/*.py``
        这类带目录的 pattern 归一为最后一段（``*.py``）；``find`` 本身默认递归，
        语义与 ``rglob('*.py')`` 一致。
        """
        name = pattern.rsplit("/", 1)[-1] if "/" in pattern else pattern
        res = self._run(
            ["find", path, "-type", "f", "-name", name, "-printf", "%p\t%s\t%T@\n"],
            writable=False,
        )
        if res.exit_code != 0:
            return []
        entries: list[dict] = []
        for line in res.output.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            p, size, mtime = parts[0], parts[1], parts[2]
            try:
                modified_at = datetime.fromtimestamp(float(mtime)).isoformat()
            except (ValueError, OSError):
                modified_at = None
            entries.append({"path": p, "size": int(size), "modified_at": modified_at})
        return entries

    def _grep(self, pattern: str, path: str, glob: str | None = None) -> list[tuple[str, int, str]] | None:
        """用 ripgrep 搜索，返回 ``[(path, line_no, line_text)]``；rg 不可用返回 None。"""
        cmd = ["rg", "--json"]
        if glob:
            cmd += ["--glob", glob]
        cmd += ["--", pattern, path]
        res = self._run(cmd, writable=False)
        if res.exit_code not in (0, 1):
            # 非 0/1 表示 rg 启动失败或参数错误（1 = 无匹配）
            return None
        matches: list[tuple[str, int, str]] = []
        for line in res.output.splitlines():
            try:
                import json

                data = json.loads(line)
            except (ValueError, ImportError):
                continue
            if data.get("type") != "match":
                continue
            pdata = data.get("data", {})
            ftext = pdata.get("path", {}).get("text")
            ln = pdata.get("line_number")
            lt = pdata.get("lines", {}).get("text", "").rstrip("\n")
            if not ftext or ln is None:
                continue
            matches.append((ftext, int(ln), lt))
        return matches

    def _run_shell(self, command: str, timeout: int = 120) -> BwrapResult:
        """在沙箱内执行 shell 命令（execute 工具的核心）。"""
        return self._run(["sh", "-c", command], timeout=timeout, writable=True)

    # --- 路径解析（复用同进程后端的共享 helper） ---

    def _resolve_path(self, key: str) -> Path:
        """解析文件路径并进行安全检查（复用模块级共享实现）。"""
        return resolve_sandbox_path(self.cwd, self.virtual_mode, key)

    def _to_virtual_path(self, abs_path: str) -> str:
        """将绝对路径映射为虚拟路径（复用模块级共享实现）。"""
        return to_virtual_path(self.cwd, self.virtual_mode, abs_path)

    @staticmethod
    def _select_lines(content: str, offset: int, limit: int) -> tuple[list[str] | None, str | None]:
        """按原文 offset/limit 选行，返回 ``(lines, error)``。

        切分用 ``content.split("\\n")`` 而非 ``splitlines()``：后者会丢掉末尾
        空行，破坏「``"\\n".join(lines)`` 无损还原片段」的契约
        （见 :class:`~.types.ReadResult`）。

        ``lines`` 为 ``None`` 表示选中失败，此时 ``error`` 为返回型错误文案。
        """
        lines = content.split("\n")
        if offset >= len(lines):
            return None, f"Error: Line offset {offset} exceeds file length ({len(lines)} lines)"
        return lines[offset : offset + limit], None

    # --- RuntimeBackend 接口实现（直接走 bwrap 子进程，无同进程分流） ---

    def ls_info(self, path: str, *, config: RunnableConfig | None = None, state: dict | None = None) -> list[FileInfo]:
        """列出目录中的文件和目录（非递归，在 bwrap 子进程内执行）。"""
        try:
            dir_path = self._resolve_path(path)
        except ValueError:
            return []
        results: list[FileInfo] = []
        for e in self._list_entries(str(dir_path)):
            virt = self._to_virtual_path(e["path"])
            display = virt + "/" if e["is_dir"] else virt
            results.append({"path": display, "is_dir": e["is_dir"], "size": e["size"], "modified_at": e["modified_at"]})
        results.sort(key=lambda x: x.get("path", ""))
        return results

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> ReadResult | str:
        """读取文件（bwrap 子进程内），返回选定片段的**原始行数据**。"""
        try:
            resolved_path = self._resolve_path(file_path)
        except ValueError as e:
            return f"Error: {e}"
        content = self._read_text(str(resolved_path))
        if content is None:
            return f"Error: File '{file_path}' not found"
        empty_msg = check_empty_content(content)
        if empty_msg:
            return empty_msg
        lines, error = self._select_lines(content, offset, limit)
        if lines is None:
            return error  # type: ignore[return-value]
        return ReadResult(lines=lines, start_line=offset + 1)

    def write(
        self,
        file_path: str,
        content: str,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> WriteResult:
        """创建新文件并写入内容（bwrap 子进程内）。"""
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
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return WriteResult(error=f"Error writing file '{file_path}': {e}")
        ok = self._write_text(str(resolved_path), content)
        if not ok:
            return WriteResult(error=f"Error writing file '{file_path}'")
        return WriteResult(path=file_path, files_update=None)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> EditResult:
        """通过替换字符串编辑文件（bwrap 子进程内）。"""
        try:
            resolved_path = self._resolve_path(file_path)
        except ValueError as e:
            return EditResult(error=str(e))
        content = self._read_text(str(resolved_path))
        if content is None:
            return EditResult(error=f"Error: File '{file_path}' not found")
        try:
            new_content, occurrences = perform_string_replacement(content, old_string, new_string, replace_all)
        except ValueError as e:
            return EditResult(error=str(e))
        ok = self._write_text(str(resolved_path), new_content)
        if not ok:
            return EditResult(error=f"Error editing file '{file_path}'")
        return EditResult(path=file_path, files_update=None, occurrences=int(occurrences))

    def grep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> list[GrepMatch] | str:
        """在沙箱内用 ripgrep 搜索正则表达式模式。

        与同进程后端不同，此处**不回退**到宿主机搜索：沙箱内 rg 不可用时
        返回空列表，避免「沙箱不可用就绕出去」的隐含逃逸。

        Args:
            pattern: 要搜索的正则表达式模式
            path: 要搜索的目录或文件路径。默认为当前目录。
            glob: 可选的 glob 模式，用于过滤要搜索的文件

        Returns:
            GrepMatch 字典列表，包含路径、行号和匹配文本。
            如果正则表达式模式无效，返回错误字符串。
        """
        import re

        try:
            re.compile(pattern)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        try:
            base_full = self._resolve_path(path or ".")
        except ValueError:
            return []

        if not base_full.exists():
            return []

        matches = self._grep(pattern, str(base_full), glob)
        if matches is None:
            return []

        result: list[GrepMatch] = []
        for fpath, line_num, line_text in matches:
            result.append({"path": self._to_virtual_path(fpath), "line": int(line_num), "text": line_text})
        return result

    def glob_info(
        self, pattern: str, path: str = "/", *, config: RunnableConfig | None = None, state: dict | None = None
    ) -> list[FileInfo]:
        """查找匹配 glob 模式的文件（bwrap 子进程内）。"""
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")
        try:
            search_path = self.cwd if path == "/" else self._resolve_path(path)
        except ValueError:
            return []
        results: list[FileInfo] = []
        for e in self._glob_entries(str(search_path), pattern):
            virt = self._to_virtual_path(e["path"])
            results.append({"path": virt, "is_dir": False, "size": e["size"], "modified_at": e["modified_at"]})
        results.sort(key=lambda x: x.get("path", ""))
        return results

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传多个文件到沙箱（bytes 经 stdin 传入 bwrap 子进程）。"""
        responses: list[FileUploadResponse] = []
        for path, content in files:
            try:
                resolved_path = self._resolve_path(path)
                resolved_path.parent.mkdir(parents=True, exist_ok=True)
                ok = self._write_bytes(str(resolved_path), content)
                responses.append({"path": path, "error": None if ok else "write_failed"})
            except FileNotFoundError:
                responses.append({"path": path, "error": "file_not_found"})
            except PermissionError:
                responses.append({"path": path, "error": "permission_denied"})
            except (ValueError, OSError):
                responses.append({"path": path, "error": "invalid_path"})

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从沙箱下载多个文件（bytes 二进制模式）。"""
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                resolved_path = self._resolve_path(path)
                content = self._read_bytes(str(resolved_path))
                if content is None:
                    responses.append({"path": path, "content": None, "error": "file_not_found"})
                else:
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
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> ExecuteResult:
        """在 bwrap 沙箱内执行 shell 命令。"""
        res = self._run_shell(command, timeout=timeout)
        output = res.output
        truncated = False
        if len(output) > max_output_size:
            output = output[:max_output_size]
            truncated = True
        return ExecuteResult(output=output, exit_code=res.exit_code, truncated=truncated)

    async def aexecute(
        self,
        command: str,
        timeout: int = 120,
        max_output_size: int = 100000,
        *,
        config: RunnableConfig | None = None,
        state: dict | None = None,
    ) -> ExecuteResult:
        """在 bwrap 沙箱内异步执行 shell 命令（委托到线程）。"""
        return await asyncio.to_thread(self.execute, command, timeout, max_output_size)

    def close(self) -> None:
        """空操作（与 :class:`~.local_backend.FilesystemBackend` 一致）。"""

    # --- 沙箱复用序列化契约（save/load） ---

    def save(self) -> dict:
        """导出挂载 BubblewrapFilesystemBackend 所需的 payload。

        本地后端的实际状态就是文件系统本身（随 pod 持久化），只需保存构造参数：
        ``cwd`` 已包含 ``envs`` 中 SKILL_DIR 触发的目录切换结果，envs 无需单独序列化。

        Returns:
            JSON 可序列化的挂载 payload 字典。
        """
        return {
            "root_dir": str(self.cwd),
            "virtual_mode": self.virtual_mode,
            "max_file_size_mb": int(self.max_file_size_bytes // (1024 * 1024)),
        }

    def load(self, payload: dict) -> None:
        """挂载到既有本地目录（实例方法，就地覆盖 cwd/virtual_mode/max_file_size）。

        Args:
            payload: ``save()`` 产出的 dict。
        """
        root_dir = payload.get("root_dir")
        if root_dir:
            self.cwd = Path(root_dir).resolve()
        if "virtual_mode" in payload:
            self.virtual_mode = payload["virtual_mode"]
        if "max_file_size_mb" in payload:
            self.max_file_size_bytes = int(payload["max_file_size_mb"]) * 1024 * 1024


__all__ = [
    "BubblewrapFilesystemBackend",
    "BwrapResult",
    "DEFAULT_READONLY_PATHS",
]
