# -*- coding: utf-8 -*-
"""aidev_agent.core.tools.e2b_sandbox.backend

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

E2BSandboxBackend: 基于 E2B Code Interpreter 的远程沙箱后端实现。

该后端的公共方法签名与 `FilesystemBackend` 保持一致，使其可通过
`RuntimeBackendResolver` 注册并路由到远程沙箱环境执行。

注意：本模块仅提供后端实现，不会自动注册运行时。
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
from dataclasses import dataclass
from typing import Any, Dict, Optional

from e2b.api.client.types import Unset
from e2b.connection_config import ConnectionConfig
from e2b.exceptions import SandboxNotFoundException
from e2b.sandbox.commands.command_handle import CommandExitException
from e2b.sandbox.filesystem.filesystem import FileType
from e2b_code_interpreter import Sandbox  # type: ignore
from langchain_core.runnables import RunnableConfig
from packaging.version import Version

from .types import (
    EditResult,
    ExecuteResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    RuntimeBackend,
    WriteResult,
)
from .utils import check_empty_content, package_dir, perform_string_replacement

logger = logging.getLogger(__name__)


@dataclass
class _CommandResult:
    """统一命令执行返回结构。

    该结构用于将 E2B SDK 命令执行结果（可能是对象或字典）规范化为同一形态。
    """

    stdout: str
    stderr: str
    exit_code: int | None


def _normalize_command_result(result: Any) -> _CommandResult:
    """将不同形态的命令执行结果统一为 _CommandResult。"""

    # 常见形态：对象属性
    stdout = getattr(result, "stdout", None)
    stderr = getattr(result, "stderr", None)
    exit_code = getattr(result, "exit_code", None)

    # 字典形态
    if isinstance(result, dict):
        stdout = result.get("stdout", stdout)
        stderr = result.get("stderr", stderr)
        exit_code = result.get("exit_code", exit_code)

    return _CommandResult(
        stdout=str(stdout or ""),
        stderr=str(stderr or ""),
        exit_code=None if exit_code is None else int(exit_code),
    )


class E2BSandboxBackend(RuntimeBackend):
    """E2B 远程沙箱后端。

    通过 E2B Code Interpreter SDK 在远程隔离环境中执行文件系统操作与命令执行。

    设计要点：
    - 与 `FilesystemBackend` 保持相同的方法签名和返回类型
    - 惰性创建沙箱实例（首次调用任一方法时创建）
    - 支持通过实例方法 ``load(sandbox_info)`` 挂载已有沙箱（绕过 connect API）
    - 提供 `kill()` 方法显式销毁沙箱

    Args:
        template: E2B 沙箱模板 ID。
        timeout: 沙箱超时时间（秒）。
        api_key: E2B API Key。未提供时从环境变量 `E2B_API_KEY` 读取。
        domain: E2B Domain。未提供时从环境变量 `E2B_DOMAIN` 读取。
        envs: 沙箱创建时注入的环境变量。

    注意：
        沙箱环境内命令执行与文件操作均为远程操作，性能与失败模式与本地不同。
    """

    def __init__(
        self,
        template: str = "sdt-hcomwqox",
        timeout: int = 600,
        api_key: str | None = None,
        domain: str | None = None,
        envs: Optional[Dict[str, str]] = None,
    ) -> None:
        """初始化 E2B 沙箱后端。

        Args:
            template: E2B 沙箱模板 ID。
            timeout: 沙箱超时时间（秒）。
            api_key: E2B API Key。未提供时从环境变量 ``E2B_API_KEY`` 读取。
            domain: E2B Domain。未提供时从环境变量 ``E2B_DOMAIN`` 读取。
            envs: 沙箱创建时注入的环境变量。在首次 ``_ensure_sandbox()`` 时
                传入 ``Sandbox.create(envs=...)``。
                若包含 ``SKILL_DIR`` 和 ``SKILL_NAME``，沙箱创建后会自动
                执行 skill 打包上传解压，完成 runtime 环境准备。
        """

        self._template = template
        self._timeout = int(timeout)
        self._api_key = api_key or os.getenv("E2B_API_KEY")
        self._domain = domain or os.getenv("E2B_DOMAIN")
        self._sandbox: Any | None = None
        self._pending_sandbox_env: Dict[str, str] | None = envs if envs else None

    @classmethod
    def from_sandbox_info(
        cls,
        sandbox_info: Dict[str, str],
        api_key: str | None = None,
        domain: str | None = None,
    ) -> "E2BSandboxBackend":
        """从已有沙箱连接信息重建后端实例，绕过 ``Sandbox.connect`` API。

        自定义 E2B 部署可能未实现 ``/sandboxes/{id}/connect`` 端点，
        此方法允许使用 ``sandbox_info`` 属性导出的连接信息直接重建
        ``Sandbox`` 实例，无需调用 connect API。

        Args:
            sandbox_info: 由 ``sandbox_info`` 属性返回的字典，包含以下字段：
                - ``sandbox_id``: 沙箱唯一标识
                - ``sandbox_domain``: 沙箱域名
                - ``envd_access_token``: envd 认证 token
                - ``envd_version``: envd 协议版本
                - ``traffic_access_token``: 流量代理 token（可选）
            api_key: E2B API Key。未提供时从环境变量 ``E2B_API_KEY`` 读取。
            domain: E2B Domain。未提供时从环境变量 ``E2B_DOMAIN`` 读取。

        Returns:
            已连接到指定沙箱的 E2BSandboxBackend 实例。
        """
        instance = cls.__new__(cls)
        instance._template = ""
        instance._timeout = 0
        instance._api_key = api_key or os.getenv("E2B_API_KEY")
        instance._domain = domain or os.getenv("E2B_DOMAIN")
        instance._pending_sandbox_env = None
        instance._sandbox = cls._build_sandbox_from_info(
            sandbox_info, api_key=instance._api_key, domain=instance._domain
        )
        return instance

    @staticmethod
    def _build_sandbox_from_info(
        sandbox_info: Dict[str, str],
        *,
        api_key: str | None = None,
        domain: str | None = None,
    ):
        """由 sandbox_info 构造 ``Sandbox`` 实例（复现 ``Sandbox._create`` 的头信息逻辑）。

        自定义 E2B 部署可能未实现 ``/sandboxes/{id}/connect`` 端点，
        直接使用 sandbox_info 导出的连接信息构造 ``Sandbox``，
        无需调用 connect API。
        """
        sandbox_id = sandbox_info["sandbox_id"]
        sandbox_domain = sandbox_info["sandbox_domain"]
        envd_access_token = sandbox_info.get("envd_access_token")
        envd_version = sandbox_info.get("envd_version", "0.1.0")
        traffic_access_token = sandbox_info.get("traffic_access_token")

        # 构造 sandbox_headers，复现 Sandbox._create 的逻辑
        extra_sandbox_headers: Dict[str, str] = {}
        if envd_access_token is not None and not isinstance(envd_access_token, Unset):
            extra_sandbox_headers["X-Access-Token"] = envd_access_token
        extra_sandbox_headers["E2b-Sandbox-Id"] = sandbox_id
        extra_sandbox_headers["E2b-Sandbox-Port"] = str(ConnectionConfig.envd_port)

        config_kwargs: Dict[str, Any] = {"extra_sandbox_headers": extra_sandbox_headers}
        if api_key:
            config_kwargs["api_key"] = api_key
        if domain:
            config_kwargs["domain"] = domain

        connection_config = ConnectionConfig(**config_kwargs)

        return Sandbox(
            sandbox_id=sandbox_id,
            sandbox_domain=sandbox_domain,
            connection_config=connection_config,
            envd_version=Version(envd_version),
            envd_access_token=envd_access_token,
            traffic_access_token=traffic_access_token,
        )

    def _ensure_sandbox(self):
        """确保沙箱实例已创建（惰性初始化）。

        首次调用时创建沙箱。如果 ``__init__`` 提供了 ``envs``：
        - ``envs`` 会作为 ``Sandbox.create(envs=...)`` 参数注入到沙箱环境。
        - 若 ``envs`` 中包含 ``SKILL_DIR`` 和 ``SKILL_NAME``，沙箱创建后
          会自动打包上传解压 skill 目录，完成 runtime 环境准备。
        """
        if self._sandbox is not None:
            return self._sandbox

        # 尽量通过参数传递；若 SDK 不支持，则回退到环境变量配置。
        kwargs: dict[str, Any] = {"template": self._template, "timeout": self._timeout}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._domain:
            kwargs["domain"] = self._domain
        if self._pending_sandbox_env:
            kwargs["envs"] = self._pending_sandbox_env

        try:
            self._sandbox = Sandbox.create(**kwargs)
        except TypeError:
            # 回退：部分版本 SDK 可能不支持 domain/api_key/envs 形参
            if self._api_key:
                os.environ["E2B_API_KEY"] = self._api_key
            if self._domain:
                os.environ["E2B_DOMAIN"] = self._domain
            self._sandbox = Sandbox.create(template=self._template, timeout=self._timeout)

        self._log_sandbox_info()

        # 沙箱创建后，若 envs 中包含 skill 信息则执行打包上传解压
        if self._pending_sandbox_env:
            skill_dir = self._pending_sandbox_env.get("SKILL_DIR")
            skill_name = self._pending_sandbox_env.get("SKILL_NAME")
            if skill_dir and skill_name:
                self._prepare_skill_runtime(skill_dir, skill_name)

        return self._sandbox

    @property
    def sandbox_info(self) -> Dict[str, Any] | None:
        """返回当前沙箱的连接信息，可用于实例方法 ``load()`` 挂载复用。

        Returns:
            包含 sandbox_id、sandbox_domain、envd_access_token、envd_version、
            traffic_access_token 的字典。若沙箱尚未创建则返回 None。
        """
        if self._sandbox is None:
            return None

        traffic_token = self._sandbox.traffic_access_token
        if isinstance(traffic_token, Unset):
            traffic_token = None

        return {
            "sandbox_id": self._sandbox.sandbox_id,
            "sandbox_domain": self._sandbox.sandbox_domain,
            "envd_access_token": self._sandbox._envd_access_token,
            "envd_version": str(self._sandbox._envd_version),
            "traffic_access_token": traffic_token,
        }

    # ---- 沙箱复用序列化 ----

    def save(self) -> dict:
        """导出 E2B 沙箱挂载 payload（写入共享存储用）。

        即「保存 sandbox_info 的内容」：返回 ``sandbox_info`` 字典，
        由实例方法 ``load`` 就地挂载复用。沙箱未创建时 ``sandbox_info`` 为
        None，默认导出 ``{}``（不抛异常），表示该槽位此前没有真正拉起过沙箱。

        Returns:
            sandbox_info 字典（sandbox_id/sandbox_domain/envd_access_token/
            envd_version/traffic_access_token），未创建沙箱时为 ``{}``。
        """
        info = self.sandbox_info
        if info is None:
            return {}
        return info

    def load(self, payload: dict) -> None:
        """挂载到既有 E2B 沙箱（实例方法，就地覆盖 ``self._sandbox``）。

        CR：payload 即 sandbox_info（save 导出内容），经
        ``_build_sandbox_from_info`` 用连接信息直接构造 ``Sandbox``（跳过
        ``Sandbox.create``）；client/凭据保持本实例构造时来源。
        payload 为 ``{}`` 说明原沙箱之前没有真正拉起来过，保持 lazy（不创建沙箱）。

        Args:
            payload: 由 ``save()`` 导出的 sandbox_info 字典。
        """
        if not payload:
            return
        self._sandbox = self._build_sandbox_from_info(payload, api_key=self._api_key, domain=self._domain)
        # 已挂载既有沙箱，构造时预留的创建参数不再适用
        self._pending_sandbox_env = None
        # 挂载即续期：远端沙箱生命周期从创建时刻起算，续期到本 backend 配置的
        # timeout，保证复用期间远端存活；失败不阻断挂载，交由自愈兜底
        try:
            self._sandbox.set_timeout(self._timeout)
        except Exception:  # noqa: BLE001
            logger.warning("E2B sandbox set_timeout 失败（挂载继续）", exc_info=True)
        logger.info(
            "E2B sandbox reattached | sandbox_id=%s",
            payload.get("sandbox_id"),
        )

    def _log_sandbox_info(self) -> None:
        """输出沙箱连接信息到日志（INFO 级别）。

        若沙箱对象缺少必要属性（如测试中的 mock 对象），则静默跳过。
        """
        try:
            info = self.sandbox_info
        except (AttributeError, TypeError):
            return
        if info is None:
            return
        logger.info(
            "E2B sandbox created | sandbox_id=%s, domain=%s, envd_api_url=%s, envd_access_token=%s, envd_version=%s",
            info["sandbox_id"],
            info["sandbox_domain"],
            getattr(self._sandbox, "envd_api_url", "N/A"),
            info["envd_access_token"],
            info["envd_version"],
        )

    def _prepare_skill_runtime(self, skill_dir: str, skill_name: str) -> str:
        """在沙箱中准备 skill 运行时环境（打包上传解压）。

        该方法仅在 ``_ensure_sandbox()`` 内部调用，此时沙箱已创建。

        Args:
            skill_dir: skill 根目录路径（包含 SKILL.md 的目录）。
            skill_name: skill 名称，用于构造远程路径。

        Returns:
            skill scripts 在远程沙箱中的路径。
        """
        zip_data = package_dir(skill_dir)
        remote_base = "/home/user"
        remote_zip = f"{remote_base}/{skill_name}.zip"
        self.upload_files([(remote_zip, zip_data)])
        remote_dir = f"{remote_base}/{skill_name}"
        self.execute(f"mkdir -p {remote_dir} && unzip -o {remote_zip} -d {remote_dir}")
        return f"{remote_dir}/scripts"

    def _run(self, command: str, timeout: int | None = None) -> _CommandResult:
        """在远程沙箱中执行 shell 命令并返回规范化结果。

        E2B SDK 在命令以非零退出码结束时会抛出 ``CommandExitException``，
        本方法会捕获该异常并将其转换为 ``_CommandResult``，使调用方可以
        通过 ``exit_code`` 字段判断命令执行结果，而非面临未处理的异常。

        挂载复用的原沙箱可能已被平台 TTL / 外部销毁（记录仍 ACTIVE）：
        首次执行遇到 ``SandboxNotFoundException`` 时丢弃失效沙箱引用并重建，
        重试一次（CR-A 首用失败自愈）。重建的新沙箱经 release save() 重新登记。
        """

        def _exec() -> _CommandResult:
            sandbox = self._ensure_sandbox()
            res = (
                sandbox.commands.run(command, timeout=timeout) if timeout is not None else sandbox.commands.run(command)
            )
            return _normalize_command_result(res)

        try:
            return _exec()
        except SandboxNotFoundException:
            logger.warning(
                "E2B sandbox 已失效（NotFound），丢弃并重建后重试一次",
                exc_info=True,
            )
            self._sandbox = None  # 丢弃死沙箱引用，_ensure_sandbox 走全新创建
            return _exec()
        except CommandExitException as exc:
            return _CommandResult(stdout=exc.stdout, stderr=exc.stderr, exit_code=exc.exit_code)

    def kill(self) -> None:
        """销毁沙箱实例。

        调用后会将内部沙箱引用置为 None，以便后续操作重新创建沙箱。
        """

        if self._sandbox is None:
            return

        try:
            self._sandbox.kill()
        finally:
            self._sandbox = None

    def close(self) -> None:
        """释放 E2B Sandbox 远程资源。"""
        self.kill()

    def ls_info(self, path: str, *, config: RunnableConfig | None = None, state: dict | None = None) -> list[FileInfo]:
        """列出目录中的文件和目录（非递归）。"""

        sandbox = self._ensure_sandbox()
        try:
            entries = sandbox.files.list(path, depth=1)
        except Exception:  # noqa: BLE001
            return []

        results: list[FileInfo] = []
        for entry in entries:
            is_dir = entry.type == FileType.DIR
            full = entry.path
            if is_dir and not full.endswith("/"):
                full += "/"
            results.append({"path": full, "is_dir": is_dir})

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
    ) -> str:
        """读取文件内容（带行号）。"""

        sandbox = self._ensure_sandbox()

        # 1) 存在性检查
        if not sandbox.files.exists(file_path):
            return f"Error: File '{file_path}' not found"

        # 2) 读取文件全文
        try:
            content = sandbox.files.read(file_path, format="text")
        except Exception:  # noqa: BLE001
            return f"Error: File '{file_path}' not found"

        if not content:
            return check_empty_content("") or ""

        lines = content.splitlines()
        total_lines = len(lines)

        if total_lines == 0:
            return check_empty_content("") or ""

        if offset >= total_lines:
            return f"Error: Line offset {offset} exceeds file length ({total_lines} lines)"

        # 3) 输出带行号的分页内容（offset 为 0-indexed）
        end = min(offset + limit, total_lines)
        result_lines: list[str] = []
        for i in range(offset, end):
            result_lines.append(f"{i + 1:6d}\t{lines[i]}")
        return "\n".join(result_lines)

    def write(
        self, file_path: str, content: str, *, config: RunnableConfig | None = None, state: dict | None = None
    ) -> WriteResult:
        """创建新文件并写入内容。"""

        sandbox = self._ensure_sandbox()

        # 文件已存在则失败
        if sandbox.files.exists(file_path):
            return WriteResult(
                error=(
                    f"Cannot write to {file_path} because it already exists. "
                    "Read and then make an edit, or write to a new path."
                )
            )

        try:
            sandbox.files.write(file_path, content)
        except Exception as e:  # noqa: BLE001
            return WriteResult(error=f"Error writing file '{file_path}': {e}")

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
        """通过替换字符串编辑文件。"""

        sandbox = self._ensure_sandbox()

        if not sandbox.files.exists(file_path):
            return EditResult(error=f"Error: File '{file_path}' not found")

        try:
            content = sandbox.files.read(file_path, format="text")
        except Exception as e:  # noqa: BLE001
            return EditResult(error=f"Error reading file '{file_path}': {e}")

        result = perform_string_replacement(content, old_string, new_string, replace_all)
        if isinstance(result, str):
            return EditResult(error=result)

        new_content, occurrences = result

        try:
            sandbox.files.write(file_path, new_content)
        except Exception as e:  # noqa: BLE001
            return EditResult(error=f"Error editing file '{file_path}': {e}")

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
        """在文件中搜索正则表达式模式（远程执行）。"""

        try:
            re.compile(pattern)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        base_path = path or "/"
        qpattern = shlex.quote(pattern)
        qbase = shlex.quote(base_path)

        parts = [
            "grep",
            "-RInE",
            "--binary-files=without-match",
        ]
        if glob:
            parts.append(f"--include={shlex.quote(glob)}")

        cmd = " ".join(parts) + f" -- {qpattern} {qbase}"
        res = self._run(cmd)
        if res.exit_code not in (0, 1, None):
            return []

        matches: list[GrepMatch] = []
        for line in res.stdout.splitlines():
            # 期望格式：path:line:text
            if not line or ":" not in line:
                continue
            first, rest = line.split(":", 1)
            if ":" not in rest:
                continue
            line_num_str, text = rest.split(":", 1)
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue
            matches.append({"path": first, "line": line_num, "text": text.lstrip()})

        return matches

    def glob_info(
        self, pattern: str, path: str = "/", *, config: RunnableConfig | None = None, state: dict | None = None
    ) -> list[FileInfo]:
        """查找匹配 glob 模式的文件（远程执行）。"""

        base = path or "/"
        qbase = shlex.quote(base)

        p = pattern.lstrip("/")

        # 简单实现：优先使用 -name；若包含目录分隔符则使用 -path。
        if "/" not in p and "**" not in p:
            qname = shlex.quote(p)
            cmd = f"find {qbase} -type f -name {qname}"
        else:
            base_prefix = base.rstrip("/") if base != "/" else "/"
            # 在任意深度匹配该 pattern
            qpathpat = shlex.quote(f"{base_prefix}/{p}")
            cmd = f"find {qbase} -type f -path {qpathpat}"

        res = self._run(cmd)
        if res.exit_code not in (0, None):
            return []

        results: list[FileInfo] = []
        for line in res.stdout.splitlines():
            if not line:
                continue
            results.append({"path": line, "is_dir": False})

        results.sort(key=lambda x: x.get("path", ""))
        return results

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传多个文件到沙箱文件系统。"""

        sandbox = self._ensure_sandbox()
        responses: list[FileUploadResponse] = []

        for path, content in files:
            try:
                sandbox.files.write(path, content)
                responses.append({"path": path, "error": None})
            except Exception as e:  # noqa: BLE001
                responses.append({"path": path, "error": str(e)})

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从沙箱文件系统下载多个文件。"""

        sandbox = self._ensure_sandbox()
        responses: list[FileDownloadResponse] = []

        for path in paths:
            try:
                content = sandbox.files.read(path, format="bytes")
                content_bytes = bytes(content)
                responses.append({"path": path, "content": content_bytes, "error": None})
            except FileNotFoundError:
                responses.append({"path": path, "content": None, "error": "file_not_found"})
            except Exception as e:  # noqa: BLE001
                responses.append({"path": path, "content": None, "error": str(e)})

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
        """在沙箱中执行 shell 命令。"""

        res = self._run(command, timeout=int(timeout))

        output = res.stdout
        if res.stderr:
            output = f"{output}\n{res.stderr}" if output else res.stderr

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
        """异步执行 shell 命令。"""

        return await asyncio.to_thread(self.execute, command, timeout, max_output_size)
