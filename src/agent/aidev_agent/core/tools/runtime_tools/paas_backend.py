# -*- coding: utf-8 -*-
"""aidev_agent.core.tools.paas_sandbox.backend

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

PaasSandboxBackend: 基于蓝鲸 PaaS 平台 Agent Sandbox HTTP API 的远程沙箱后端实现。

该后端统一承担原 PaasSandboxClient 的认证管理、请求构建、响应解析职责，
同时提供与 `FilesystemBackend` 保持一致的公共方法签名，使其可通过
`RuntimeBackendResolver` 注册并路由到远程沙箱环境执行。

注意：本模块仅提供后端实现，不会自动注册运行时。
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import threading
from dataclasses import dataclass
from functools import wraps
from time import sleep
from typing import Any, Optional

from requests.exceptions import HTTPError

from aidev_agent.api.paas_client import BkPaaSSandboxApi
from aidev_agent.config import settings

from .types import (
    EditResult,
    ExecuteResult,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GrepMatch,
    WriteResult,
)
from .utils import check_empty_content, perform_string_replacement

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 辅助函数 & 装饰器
# ---------------------------------------------------------------------------

_NOT_READY_MSG = "AGENT_SANDBOX_SERVICE_NOT_READY"
_NOT_READY_MAX_RETRIES = 5
_NOT_READY_SLEEP_SECONDS = 2


class PaasSandboxError(Exception):
    """PaaS 沙箱操作异常。

    由 ``_paas_error_enhance`` 装饰器抛出，携带面向 LLM 的可读错误消息。
    在 ``default_tool_call_handler``（node.py）中被特殊处理，
    直接将 ``str(error)`` 返回给 LLM，而不走通用异常日志路径。
    """


def _extract_response_message(response) -> str | None:
    """安全地从 response body（JSON）中提取 ``message`` 字段。"""
    if response is None:
        return None
    try:
        body = response.json()
        logger.debug("[_extract_response_message] HTTPError with message: %s", body)
        if isinstance(body, dict) and "message" in body:
            return body.get("message")
        return str(body)
    except Exception:  # noqa: BLE001
        logger.warning("[_extract_response_message] 解析响应体失败", exc_info=True)
    return None


def _paas_error_enhance(func):
    """装饰器：捕获异常并抛出 ``PaasSandboxError``，保留原始异常链。

    放置于上层公开方法（面向 ToolNode/LLM 的方法），统一将异常转为
    ``PaasSandboxError``，由 ``default_tool_call_handler`` 捕获后
    将 ``str(error)`` 直接返回给 LLM。

    - HTTPError：尝试从 response body 提取 message
    - 其他 Exception：直接使用 str(exc)
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPError as exc:
            message = _extract_response_message(exc.response)
            if message:
                logger.warning("[Harness] HTTPError with message: %s", message)
                raise PaasSandboxError(f"[Harness] 出现了{message}的问题") from exc
            logger.warning("[Harness] HTTPError: %s", exc)
            raise PaasSandboxError(f"[Harness] 出现了{exc}的问题") from exc
        except PaasSandboxError:
            raise
        except Exception as exc:
            logger.warning("[Harness] Exception: %s", exc)
            raise PaasSandboxError(f"[Harness] 出现了{exc}的问题") from exc

    return wrapper


def _paas_retry_on_not_ready(func):
    """装饰器：对 NOT_READY 错误自动重试，最多 ``SBX_PAAS_NOT_READY_MAX_RETRIES`` 次。

    重试耗尽后 raise 最后捕获的异常，让异常向上传播到公开方法层的
    ``@_paas_error_enhance`` 处理。
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exc: HTTPError | None = None
        for attempt in range(settings.SBX_PAAS_NOT_READY_MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except HTTPError as exc:
                message = _extract_response_message(exc.response)
                if not (message and _NOT_READY_MSG in message):
                    raise
                last_exc = exc
                logger.warning(
                    "沙箱服务未就绪 (%s)，重试 %d/%d",
                    message,
                    attempt + 1,
                    settings.SBX_PAAS_NOT_READY_MAX_RETRIES,
                )
                if attempt < settings.SBX_PAAS_NOT_READY_MAX_RETRIES:
                    sleep(settings.SBX_PAAS_NOT_READY_SLEEP_SECONDS)
        # 重试耗尽，raise 最后的异常
        raise last_exc  # type: ignore[misc]

    return wrapper


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class ExecResult:
    """命令执行结果。"""

    stdout: str
    stderr: str
    exit_code: int | None


# ---------------------------------------------------------------------------
# PaasSandboxBackend
# ---------------------------------------------------------------------------


class PaasSandboxBackend:
    """蓝鲸 PaaS Sandbox 远程沙箱后端。

    统一承担认证管理、HTTP 请求构建与响应解析（原 PaasSandboxClient 职责），
    以及在远程沙箱环境中执行文件系统操作与命令执行（原 PaasSandboxBackend 职责）。

    设计要点：
    - 与 `FilesystemBackend` 保持相同的方法签名和返回类型
    - 惰性创建沙箱实例（首次调用任一方法时创建）
    - 提供 `kill()` 方法显式销毁沙箱
    - 所有配置项均通过构造函数显式注入，不依赖任何环境变量

    认证策略：
    - 通过 ``bk_username`` 初始化 paas_client，由 bkapi_client_core 自动处理鉴权。

    Args:
        app_code: 应用编码，用于 API 鉴权和 URL 路径拼接，可选（默认 ``""``）。
        app_secret: 应用密钥，与 app_code 配合用于 API 鉴权，可选（默认 ``""``）。
            当 app_code 和 app_secret 同时提供时，优先使用显式凭证创建 Client，
            而非依赖 Django settings 全局配置。这在等平台进程中尤为重要——
            Django settings 的 BK_APP_CODE 是平台的凭证，而非 Agent 应用的凭证。
        bk_username: 蓝鲸用户名，用于 ``X-Bkapi-Authorization`` 请求头，可选（默认 ``""``）。
        access_token: 访问令牌，用于 ``X-Bkapi-Authorization`` 请求头，可选（默认 ``""``）。
        snapshot: 沙箱基础镜像快照名，必填。
        snapshot_entrypoint: 快照入口命令列表（如 ``["python", "-m", "server"]``），必填。
        env_vars: 沙箱启动时注入的环境变量字典，必填。
        sandbox_id: 已有沙箱 UUID，可选。传入后跳过创建流程，直接复用该沙箱。

    注意：
        沙箱环境内命令执行与文件操作均为远程操作，性能与失败模式与本地不同。
    """

    def __init__(
        self,
        *,
        app_code: str = "",
        app_secret: str = "",
        bk_username: str = "",
        access_token: str = "",
        snapshot: str,
        snapshot_entrypoint: list[str],
        env_vars: dict,
        sandbox_id: str | None = None,
    ) -> None:
        """初始化 PaaS Sandbox 后端。

        Args:
            app_code: 应用编码，可选（默认 ``""``）。
            app_secret: 应用密钥，可选（默认 ``""``）。
                同时提供 app_code 和 app_secret 时，使用显式凭证创建 Client。
            bk_username: 蓝鲸用户名，可选（默认 ``""``）。
            access_token: 访问令牌，可选（默认 ``""``）。
            snapshot: 沙箱基础镜像快照名，必填。
            snapshot_entrypoint: 快照入口命令列表，必填。
            env_vars: 沙箱启动时注入的环境变量字典，必填。
            sandbox_id: 已有沙箱 UUID，可选。传入后跳过创建流程，直接复用该沙箱。
        """

        # 认证属性
        self._app_code = app_code
        self._app_secret = app_secret
        self._bk_username = bk_username
        self._access_token = access_token
        logger.info(
            f"[credential] PaasSandboxBackend.__init__: "
            f"app_code={app_code!r}, has_app_secret={bool(app_secret)}, "
            f"bk_username={bk_username!r}, has_access_token={bool(access_token)}, "
            f"will_use_explicit_credential={bool(app_code and app_secret)}"
        )
        # 优先使用显式凭证（app_code + app_secret）创建 Client，
        # 避免平台进程中 Django settings 全局凭证与 Agent app_code 不匹配 即可能会使用到平台的凭证
        if app_code and app_secret:
            self.client = BkPaaSSandboxApi.get_client(app_code=app_code, app_secret=app_secret)
        else:
            logger.warning(
                f"[credential] PaasSandboxBackend.__init__: "
                f"fallback to get_client_by_username('{bk_username}'), "
                f"this may use Django settings credential (bkaidev) instead of agent app_code!"
            )
            self.client = BkPaaSSandboxApi.get_client_by_username(bk_username)
        self.client.update_bkapi_authorization(access_token=access_token or None, bk_username=bk_username or "")
        # 沙箱属性
        self._sandbox_id: str | None = sandbox_id
        self._snapshot = snapshot
        self._snapshot_entrypoint = snapshot_entrypoint
        self._env_vars = env_vars
        self._sandbox_lock = threading.Lock()
        self._home_dir: str | None = None

    # ---- PaaS HTTP API（原 PaasSandboxClient 公开方法） ----

    @_paas_retry_on_not_ready
    def create_sandbox(
        self,
        name: Optional[str] = None,
        env_vars: Optional[dict[str, str]] = None,
        snapshot: Optional[str] = None,
        snapshot_entrypoint: Optional[list[str]] = None,
    ) -> str:
        """创建沙箱。

        Args:
            name: 沙箱名称（可选）。
            env_vars: 环境变量（可选）。
            snapshot: 镜像文件
            snapshot_entrypoint: 启动入口(可选)

        Returns:
            创建的沙箱 UUID。

        Raises:
            ValueError: app_code 未配置或返回格式异常。
            HTTPError: API 请求失败。
        """

        if not self._app_code:
            raise ValueError("app_code 未配置（请通过构造函数 app_code 参数传入）")

        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if env_vars is not None:
            payload["env_vars"] = env_vars
        if snapshot is not None:
            payload["snapshot"] = snapshot
        if snapshot_entrypoint is not None:
            payload["snapshot_entrypoint"] = snapshot_entrypoint
        response = self.client.create_sandbox.request(json=payload, path_params={"app_code": self._app_code})
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("uuid"):
            return str(data["uuid"])
        raise ValueError(f"创建沙箱返回格式异常: {data}")

    @_paas_retry_on_not_ready
    def destroy_sandbox(self, sandbox_id: str) -> None:
        """销毁沙箱。

        Args:
            sandbox_id: 沙箱 UUID。
        """
        response = self.client.delete_sandbox.request(path_params={"sandbox_id": sandbox_id})
        response.raise_for_status()

    @_paas_retry_on_not_ready
    def exec_command(
        self,
        sandbox_id: str,
        cmd: str | list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecResult:
        """在沙箱中执行命令。

        Args:
            sandbox_id: 沙箱 UUID。
            cmd: 要执行的命令（字符串或命令列表）。
            cwd: 工作目录（可选）。
            env: 环境变量（可选）。
            timeout: 命令超时时间秒（可选）。

        Returns:
            ExecResult 包含 stdout, stderr, exit_code。
        """
        response = self.client.exec_command.request(
            json={"cmd": cmd},
            path_params={"sandbox_id": sandbox_id},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return ExecResult(
                stdout=str(data.get("stdout") or ""),
                stderr=str(data.get("stderr") or ""),
                exit_code=data.get("exit_code"),
            )
        # 兼容：如果 data 不是 dict，将其作为 stdout
        return ExecResult(stdout=str(data or ""), stderr="", exit_code=None)

    @_paas_retry_on_not_ready
    def upload_file(self, sandbox_id: str, path: str, content: bytes) -> None:
        """上传文件到沙箱。

        Args:
            sandbox_id: 沙箱 UUID。
            path: 远程文件路径（调用方应确保已展开 ``~``）。
            content: 文件内容（字节）。
        """
        filename = path.rsplit("/", 1)[-1] or "upload"
        # 注意：不能使用 data={"path": path}，因为 bkapi_client_core 的
        # RequestContextBuilder.build_data() 会将 POST 请求的 data 转为 json，
        # 导致 files 参数被忽略，服务端收到 JSON 而非 multipart/form-data 返回 400。
        # 解决方案：将 path 字段以 (None, value) 形式嵌入 files 参数，
        # 使其作为 multipart 表单字段发送。
        response = self.client.upload_file.request(
            files={"file": (filename, content), "path": (None, path)},
            path_params={"sandbox_id": sandbox_id},
        )
        response.raise_for_status()

    @_paas_retry_on_not_ready
    def download_file(self, sandbox_id: str, path: str) -> bytes:
        """从沙箱下载文件。

        Args:
            sandbox_id: 沙箱 UUID。
            path: 远程文件路径（调用方应确保已展开 ``~``）。

        Returns:
            文件内容字节。
        """
        response = self.client.download_file.request(
            params={"path": path},
            path_params={"sandbox_id": sandbox_id},
        )
        response.raise_for_status()
        return response.content

    # ---- 沙箱生命周期 ----

    def _ensure_sandbox(self) -> str:
        """确保沙箱实例已创建（惰性初始化，线程安全）。

        使用双重检查锁定模式：外层快速路径不持锁，锁内二次检查防止竞态。

        Returns:
            沙箱 UUID。

        Raises:
            异常由 create_sandbox 向上传播。
        """

        if self._sandbox_id is not None:
            return self._sandbox_id

        with self._sandbox_lock:
            if self._sandbox_id is not None:
                return self._sandbox_id

            self._sandbox_id = self.create_sandbox(
                snapshot=self._snapshot,
                snapshot_entrypoint=self._snapshot_entrypoint,
                env_vars=self._env_vars,
            )
            sleep(settings.SBX_PAAS_NOT_READY_SLEEP_SECONDS)
            logger.info("PaaS Sandbox 已创建: %s", self._sandbox_id)
            return self._sandbox_id

    def _run(self, command: str | list, timeout: int | None = None) -> ExecResult:
        """在远程沙箱中执行 shell 命令并返回结果。"""

        sandbox_id = self._ensure_sandbox()
        return self.exec_command(sandbox_id, command, timeout=timeout)

    def _resolve_path(self, path: str) -> str:
        """将 ``~`` 展开为绝对路径。

        在每个公开方法入口处调用，确保后续所有操作（shell 命令和 HTTP API）
        都只看到绝对路径。
        """
        if not path.startswith("~"):
            return path
        if self._home_dir is None:
            res = self._run(["bash", "-c", "echo $HOME"])
            self._home_dir = res.stdout.strip() or "/root"  # PaaS 沙箱默认以 root 用户运行
        return self._home_dir + path[1:] if len(path) > 1 else self._home_dir

    def kill(self) -> None:
        """销毁沙箱实例。

        调用后会将内部沙箱 ID 置为 None，以便后续操作重新创建沙箱。
        """

        if getattr(self, "_sandbox_id", None) is None:
            return

        try:
            self.destroy_sandbox(self._sandbox_id)
            logger.info("PaaS Sandbox 已销毁: %s", self._sandbox_id)
        except Exception:  # noqa: BLE001
            logger.warning("销毁 PaaS Sandbox 失败: %s", self._sandbox_id, exc_info=True)
        finally:
            self._sandbox_id = None

    # ---- 文件系统操作 ----

    @_paas_error_enhance
    def ls_info(self, path: str) -> list[FileInfo]:
        """列出目录中的文件和目录（非递归）。"""

        path = self._resolve_path(path)
        qpath = shlex.quote(path)
        cmd = f"ls -1pA -- {qpath}"
        res = self._run(["bash", "-c", cmd])
        if res.exit_code not in (0, None):
            logger.warning("ls_info 执行失败: path=%r, stdout=%r, exit_code=%s", path, res.stdout[:200], res.exit_code)
            return []

        base = path.rstrip("/") if path != "/" else "/"
        results: list[FileInfo] = []
        for line in res.stdout.splitlines():
            if not line:
                continue
            is_dir = line.endswith("/")
            name = line[:-1] if is_dir else line
            full = (f"/{name}" if name else "/") if base == "/" else f"{base}/{name}"
            if is_dir and not full.endswith("/"):
                full += "/"
            results.append({"path": full, "is_dir": bool(is_dir)})

        results.sort(key=lambda x: x.get("path", ""))
        return results

    @_paas_error_enhance
    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """读取文件内容（带行号）。"""

        file_path = self._resolve_path(file_path)
        qfile = shlex.quote(file_path)

        # 1) 存在性检查
        exists = self._run(f"test -f {qfile}")
        if exists.exit_code not in (0, None):
            return f"Error: File '{file_path}' not found"

        # 2) 行数检查（awk END{print NR} 正确计算无尾换行文件的行数，wc -l 不行）
        wc = self._run(f"awk 'END{{print NR}}' {qfile}")
        try:
            total_lines = int(wc.stdout.strip() or "0")
        except ValueError:
            total_lines = 0

        if total_lines == 0:
            return check_empty_content("") or ""

        if offset >= total_lines:
            return f"Error: Line offset {offset} exceeds file length ({total_lines} lines)"

        # 3) 输出带行号的分页内容（offset 为 0-indexed）
        start_line = int(offset) + 1
        end_exclusive = start_line + int(limit)
        awk_prog = 'NR>=start && NR<end { printf "%6d\\t%s\\n", NR, $0 }'
        cmd = f"awk -v start={start_line} -v end={end_exclusive} '{awk_prog}' {qfile}"
        out = self._run(cmd)
        return out.stdout

    @_paas_error_enhance
    def write(self, file_path: str, content: str) -> WriteResult:
        """创建新文件并写入内容。"""

        file_path = self._resolve_path(file_path)
        qfile = shlex.quote(file_path)

        # 文件已存在则失败
        exists = self._run(f"test -e {qfile}")
        if exists.exit_code in (0, None):
            return WriteResult(
                error=(
                    f"Cannot write to {file_path} because it already exists. "
                    "Read and then make an edit, or write to a new path."
                )
            )

        # 创建父目录
        sandbox_id = self._ensure_sandbox()
        dirname = os.path.dirname(file_path)
        if dirname:
            self._run(f"mkdir -p {shlex.quote(dirname)}")

        # 通过文件上传 API 写入
        file_bytes = content.encode("utf-8")
        if not file_bytes:
            return WriteResult(
                error="Cannot write empty content. Provide non-empty content or use execute to create the file."
            )
        self.upload_file(sandbox_id, file_path, file_bytes)

        return WriteResult(path=file_path, files_update=None)

    @_paas_error_enhance
    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        """通过替换字符串编辑文件。"""

        file_path = self._resolve_path(file_path)
        # 1) 通过 shell 读取文件内容（兼容中文路径，download_file API 对非 ASCII 路径不稳定）
        qfile = shlex.quote(file_path)
        cat = self._run(f"cat {qfile}")
        if cat.exit_code not in (0, None):
            return EditResult(error=f"Error: File '{file_path}' not found")
        content = cat.stdout

        # 2) 执行字符串替换
        result = perform_string_replacement(content, old_string, new_string, replace_all)
        if isinstance(result, str):
            return EditResult(error=result)

        new_content, occurrences = result

        # 3) 写回文件（先删后传，使用 shell 命令删除而非不存在的网关 API）
        sandbox_id = self._ensure_sandbox()
        self._run(f"rm -f {qfile}")
        self.upload_file(sandbox_id, file_path, new_content.encode("utf-8"))

        return EditResult(path=file_path, files_update=None, occurrences=int(occurrences))

    @_paas_error_enhance
    def grep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list[GrepMatch] | str:
        """在文件中搜索正则表达式模式（远程执行）。"""

        try:
            re.compile(pattern)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        base_path = self._resolve_path(path) if path else "/"
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

    @_paas_error_enhance
    def glob_info(self, pattern: str, path: str = "/") -> list[FileInfo]:
        """查找匹配 glob 模式的文件（远程执行）。"""

        base = self._resolve_path(path) if path else "/"
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

    @_paas_error_enhance
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """上传多个文件到沙箱文件系统。"""

        sandbox_id = self._ensure_sandbox()
        responses: list[FileUploadResponse] = []

        for path, content in files:
            try:
                resolved = self._resolve_path(path)
                self.upload_file(sandbox_id, resolved, content)
                responses.append({"path": path, "error": None})
            except Exception as e:  # noqa: BLE001
                responses.append({"path": path, "error": str(e)})

        return responses

    @_paas_error_enhance
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从沙箱文件系统下载多个文件。"""

        sandbox_id = self._ensure_sandbox()
        responses: list[FileDownloadResponse] = []

        for path in paths:
            try:
                resolved = self._resolve_path(path)
                content_bytes = self.download_file(sandbox_id, resolved)
                responses.append({"path": path, "content": content_bytes, "error": None})
            except Exception as e:  # noqa: BLE001
                error_msg = "file_not_found" if "404" in str(e) else str(e)
                responses.append({"path": path, "content": None, "error": error_msg})

        return responses

    @_paas_error_enhance
    def execute(self, command: str, timeout: int = 120, max_output_size: int = 100000) -> ExecuteResult:
        """在沙箱中执行 shell 命令。"""

        res: ExecResult = self._run(["bash", "-c", command], timeout=int(timeout))
        logger.info(
            f"[credential] PaasSandboxBackend.execute: "
            f"app_code={self._app_code!r}, has_access_token={bool(self._access_token)}, "
            f"bk_username={self._bk_username!r}, command={command[:80]!r}"
        )

        output = res.stdout
        if res.stderr:
            output = f"{output}\n{res.stderr}" if output else res.stderr

        if not output:
            logger.warning("命令执行返回空输出: command=%r, exit_code=%s", command[:200], res.exit_code)

        truncated = False
        if len(output) > max_output_size:
            output = output[:max_output_size]
            truncated = True

        return ExecuteResult(output=output, exit_code=res.exit_code, truncated=truncated)

    async def aexecute(self, command: str, timeout: int = 120, max_output_size: int = 100000) -> ExecuteResult:
        """异步执行 shell 命令。"""

        import asyncio

        return await asyncio.to_thread(self.execute, command, timeout, max_output_size)

    def __del__(self):
        self.kill()
