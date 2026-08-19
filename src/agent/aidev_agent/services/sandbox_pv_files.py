# -*- coding: utf-8 -*-
"""会话沙箱 PersistentVolume 文件业务层。

三大调用场景共享同一份实现：
1. bk-aidev 平台调试页：Django Service 层薄适配后调用（凭证 = 平台自身）
2. SDK 前端应用：`aidev_bkplugin` View 层调用（凭证 = Agent 应用自身）
3. Agent 运行时：如轮次产物识别节点直接调用（凭证 = executor_info）

Service 层职责：
- 通过 `ResourceManager` 反查 `session_code → volume_id`
- 通过 `ResourceManager` 构造 PaaS Sandbox Client
- 6 个业务方法（upload/list/delete/stat/preview/get_download_url）
- `list_files` 内部分页拉全量 + `time.sleep` 超频保护 + 过滤目录
- PaaS HTTP 错误 → SDK 侧业务异常映射
"""

from __future__ import annotations

import logging
import posixpath
import threading
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import NotRequired, Optional, TypedDict
from uuid import uuid4

from bkapi_client_core.exceptions import HTTPResponseError

from aidev_agent.core.tools.runtime_tools.paas_backend import PaasSandboxBackend
from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 业务异常
# ---------------------------------------------------------------------------
# 按语义分层：调用方可 catch `SandboxFileError` 基类做统一处理，也可按子类做细分。
# Service 层不做 HTTP 状态映射（那是各自 Web 层的职责）。


class SandboxFileError(Exception):
    """会话沙箱 PV 文件操作基类异常。"""


class SandboxFileNotFoundError(SandboxFileError):
    """PV / 文件不存在（含 session 未初始化 sandbox_pv_id 场景）。"""


class SandboxFileInvalidRequestError(SandboxFileError):
    """PaaS 侧拒绝的请求（文件类型不支持、体积过大等）。"""


class SandboxFileInvalidArgumentError(SandboxFileError):
    """PaaS 侧因参数问题拒绝执行的操作。"""


class SandboxFileServerError(SandboxFileError):
    """PaaS / 沙箱服务端错误，或未识别的失败。"""


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# list_files 分页与超频保护
PV_LIST_PAGE_SIZE = 500  # PaaS 上限
PV_LIST_MAX_PAGES = 20  # 保护上限（20 * 500 = 1w 文件）
PV_LIST_PAGE_SLEEP_SECONDS = 0.5  # 翻页前预防性等待，避免打爆 PaaS apigw
SESSION_VOLUME_PATH = "$STORAGE_PATH/session"
SESSION_FILES_DIR = "files"
TEMP_UPLOAD_VOLUME_MOUNT_PATH = "/app/.storage/session"
# 临时上传 sandbox 的 PaaS 存活时长，同时作为进程内复用缓存的过期阈值：
# 复用期内不再建/销毁，到期由 PaaS 自动回收；临界点若命中已回收 sandbox，由 fallback 重建兜底
# PaaS sandbox ttl_seconds 上限为 30 分钟（1800s）
TEMP_UPLOAD_SANDBOX_TTL_SECONDS = 1800
# 前端 <img> / 视觉模型共用的临时 download_url 有效期
IMAGE_DOWNLOAD_URL_EXPIRES_IN = 3600
# 会话 PV 上传限制：平台与 SDK 插件 HTTP 入口共用，只在此维护一份。
MAX_SESSION_UPLOAD_FILES = 9
MAX_SESSION_UPLOAD_FILE_SIZE = int(2.4 * 1024 * 1024)
SESSION_UPLOAD_IMAGE_EXTENSIONS = frozenset({".gif", ".jpeg", ".jpg", ".png", ".webp"})
SESSION_UPLOAD_FILE_EXTENSIONS = (
    frozenset(
        {
            ".bash",
            ".c",
            ".conf",
            ".cpp",
            ".cs",
            ".css",
            ".csv",
            ".doc",
            ".docx",
            ".epub",
            ".go",
            ".h",
            ".hpp",
            ".html",
            ".ini",
            ".java",
            ".js",
            ".json",
            ".jsx",
            ".kt",
            ".log",
            ".md",
            ".mobi",
            ".pdf",
            ".php",
            ".ppt",
            ".pptx",
            ".py",
            ".rb",
            ".rs",
            ".rst",
            ".scss",
            ".sh",
            ".sql",
            ".swift",
            ".toml",
            ".ts",
            ".tsx",
            ".txt",
            ".vue",
            ".xls",
            ".xlsx",
            ".xml",
            ".yaml",
            ".yml",
        }
    )
    | SESSION_UPLOAD_IMAGE_EXTENSIONS
)

# PaaS 沙箱文件接口错误码 → 语义分组
PV_PAAS_ERROR_NOT_FOUND_CODES = frozenset({"AGENT_SANDBOX_FILE_NOT_FOUND", "VOLUME_NOT_FOUND"})
PV_PAAS_ERROR_NOT_PREVIEWABLE_CODES = frozenset({"AGENT_SANDBOX_FILE_NOT_PREVIEWABLE"})
PV_PAAS_ERROR_TOO_LARGE_CODES = frozenset({"AGENT_SANDBOX_FILE_TOO_LARGE"})
PV_PAAS_ERROR_INVALID_ARG_CODES = frozenset({"AGENT_SANDBOX_FILE_OPERATION_FAILED"})
# 复用上传沙箱被回收：只认 404 / 容器不存在，不认 FILE_TOO_LARGE 等业务错误
PV_PAAS_SANDBOX_GONE_CODES = frozenset({"AGENT_SANDBOX_NOT_FOUND", "SANDBOX_NOT_FOUND"})


# ---------------------------------------------------------------------------
# 进程内复用缓存（sandbox 容器）
# ---------------------------------------------------------------------------
# sandbox 容器按 app_code + session_code + volume_id 缓存 sandbox_id，复用期内不再 create/destroy。
# 凭证（client）每次请求新建，只复用 PaaS 侧的 sandbox 容器，避免缓存过期凭证。
_UPLOAD_SANDBOX_CACHE: dict[tuple[str, str, str], tuple[str, float]] = {}
_UPLOAD_SANDBOX_CACHE_LOCK = threading.Lock()
# 会话级操作锁：串行化同会话的 sandbox exec/upload，避免单容器并发冲突
_UPLOAD_SESSION_LOCKS: dict[str, threading.Lock] = {}
_UPLOAD_SESSION_LOCKS_LOCK = threading.Lock()


def _get_session_op_lock(session_code: str) -> threading.Lock:
    """获取会话级操作锁（懒创建）。"""
    with _UPLOAD_SESSION_LOCKS_LOCK:
        lock = _UPLOAD_SESSION_LOCKS.get(session_code)
        if lock is None:
            lock = threading.Lock()
            _UPLOAD_SESSION_LOCKS[session_code] = lock
        return lock


def _get_cached_upload_sandbox(app_code: str, session_code: str, volume_id: str) -> str:
    """返回未过期的缓存 sandbox_id，无则空串。"""
    cache_key = (app_code, session_code, volume_id)
    with _UPLOAD_SANDBOX_CACHE_LOCK:
        entry = _UPLOAD_SANDBOX_CACHE.get(cache_key)
        if not entry:
            return ""
        sandbox_id, created_at = entry
        if time.monotonic() - created_at >= TEMP_UPLOAD_SANDBOX_TTL_SECONDS:
            _UPLOAD_SANDBOX_CACHE.pop(cache_key, None)
            return ""
        return sandbox_id


def _set_cached_upload_sandbox(
    app_code: str,
    session_code: str,
    volume_id: str,
    sandbox_id: str,
    created_at: float | None = None,
) -> None:
    cache_key = (app_code, session_code, volume_id)
    with _UPLOAD_SANDBOX_CACHE_LOCK:
        if created_at is None:
            existing = _UPLOAD_SANDBOX_CACHE.get(cache_key)
            if existing and existing[0] == sandbox_id:
                return
            created_at = time.monotonic()
        _UPLOAD_SANDBOX_CACHE[cache_key] = (sandbox_id, created_at)


def _invalidate_cached_upload_sandbox(app_code: str, session_code: str, volume_id: str) -> None:
    cache_key = (app_code, session_code, volume_id)
    with _UPLOAD_SANDBOX_CACHE_LOCK:
        _UPLOAD_SANDBOX_CACHE.pop(cache_key, None)


class SandboxUploadFile(TypedDict):
    """上传到会话 PV 的文件。"""

    name: str
    content: bytes
    mime_type: NotRequired[str]


def validate_session_upload_files(files: list[SandboxUploadFile]) -> None:
    """校验上传数量、扩展名和单文件大小。HTTP 入口与 Service 共用。"""
    if not files:
        raise SandboxFileInvalidArgumentError("上传文件不能为空")
    if len(files) > MAX_SESSION_UPLOAD_FILES:
        raise SandboxFileInvalidArgumentError(f"单次上传文件不能超过 {MAX_SESSION_UPLOAD_FILES} 个")
    for upload_file in files:
        name = str(upload_file.get("name") or "")
        extension = PurePosixPath(name.replace("\\", "/")).suffix.lower()
        if extension not in SESSION_UPLOAD_FILE_EXTENSIONS:
            raise SandboxFileInvalidArgumentError(f"文件类型 {extension or '无扩展名'} 不支持")
        if len(upload_file.get("content") or b"") > MAX_SESSION_UPLOAD_FILE_SIZE:
            raise SandboxFileInvalidArgumentError(
                f"文件 {name} 超过单文件大小限制 {MAX_SESSION_UPLOAD_FILE_SIZE} 字节"
            )


def iter_user_images_missing_url(payload: dict):
    """找出用户消息里缺展示 URL 的图片 binary。"""
    if payload.get("role") != "user":
        return
    content = payload.get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "binary" or item.get("url"):
            continue
        if not str(item.get("mime_type") or "").startswith("image/"):
            continue
        if item.get("id") or item.get("path"):
            yield item


def fill_user_image_urls(file_service: "SandboxPvFileService", payload: dict) -> None:
    """给缺 url 的用户图片 binary 签发 download_url。"""
    session_code = payload.get("session_code") or ""
    if not session_code:
        return
    for item in iter_user_images_missing_url(payload):
        path = item.get("id") or item.get("path")
        try:
            url_data = file_service.get_download_url(
                session_code=session_code,
                path=path,
                expires_in=IMAGE_DOWNLOAD_URL_EXPIRES_IN,
            )
        except SandboxFileError:
            logger.exception("签发用户图片 URL 失败: session=%s path=%s", session_code, path)
            continue
        url = url_data.get("download_url")
        if url:
            item["url"] = url


class SandboxPvFileService:
    """会话沙箱 PV 文件业务层。

    :param resource_manager: 资源管理器实例，需实现 `retrieve_chat_session` / `get_paas_sbx_client`
    :param executor_info: 传给 `get_paas_sbx_client` 的凭证信息，键：
        - app_code / app_secret：应用凭证（首选）
        - executor：用户名，用于 X-Bkapi-Authorization
        - access_token：可选
    """

    def __init__(self, resource_manager: ResourceManagerProtocol, executor_info: dict) -> None:
        self._rm = resource_manager
        self._executor_info = executor_info

    # ------------------------------------------------------------------
    # 反查 & Client 构造
    # ------------------------------------------------------------------

    def _get_volume_id(self, session_code: str) -> str:
        """从 `ChatSession.session_property.sandbox_pv_id` 读取 volume_id，缺失即报错。"""
        session = self._rm.retrieve_chat_session(session_code) or {}
        session_property = session.get("session_property") or {}
        volume_id = session_property.get("sandbox_pv_id")
        if not volume_id:
            raise SandboxFileNotFoundError(
                f"session {session_code} 未初始化沙箱 PersistentVolume（sandbox_pv_id 缺失）"
            )
        return volume_id

    def _get_client(self):
        return self._rm.get_paas_sbx_client(self._executor_info)

    def _build_path_params(self, volume_id: str) -> dict:
        app_code = self._executor_info.get("app_code") or ""
        return {"app_code": app_code, "volume_id": volume_id}

    @staticmethod
    def _extract_volume_id(session: dict) -> str:
        volume_id = ((session or {}).get("session_property") or {}).get("sandbox_pv_id")
        return str(volume_id) if volume_id else ""

    @staticmethod
    def _extract_created_volume_id(payload) -> str:
        """兼容 PaaS 直出 `{"uuid": ...}` 与 APIGW 信封 `{"data": {"uuid": ...}}`。"""
        if not isinstance(payload, dict):
            return ""
        # data 为 null / 空时退回顶层，与 pv 节点解析保持一致
        data = payload.get("data") or payload
        if not isinstance(data, dict):
            return ""
        return str(data.get("uuid") or "")

    @staticmethod
    def _delete_volume_quietly(client, app_code: str, volume_id: str) -> None:
        try:
            response = client.delete_agent_sandbox_volume.request(
                path_params={"app_code": app_code, "volume_id": volume_id}
            )
            response.raise_for_status()
        except Exception:  # noqa: BLE001
            logger.warning("清理未关联的 sandbox PV 失败: volume_id=%s", volume_id, exc_info=True)

    def ensure_volume(self, session_code: str, *, cached_volume_id: str | None = None) -> str:
        """幂等获取会话 PV；不存在时创建并写回会话。

        ``cached_volume_id`` 非 None 表示调用方已读过会话：
        - 非空：直接使用，不再 retrieve
        - 空串：已知尚未初始化，跳过 retrieve 直接创建
        """
        if cached_volume_id:
            return cached_volume_id
        if cached_volume_id is None:
            try:
                return self._get_volume_id(session_code)
            except SandboxFileNotFoundError:
                pass

        client = self._get_client()
        app_code = self._executor_info.get("app_code") or ""
        created_volume_id = ""
        try:
            volume_name = f"session-pv-{session_code}-{uuid4().hex[:8]}"
            response = client.create_agent_sandbox_volume.request(
                json={"name": volume_name},
                path_params={"app_code": app_code},
            )
            if not response.ok:
                create_payload = {}
                try:
                    create_payload = response.json()
                except Exception:  # noqa: BLE001
                    create_payload = {}
                logger.error(
                    "create_agent_sandbox_volume failed: status=%s payload=%s",
                    getattr(response, "status_code", None),
                    create_payload,
                )
                paas_message = ""
                if isinstance(create_payload, dict):
                    paas_message = str(create_payload.get("message") or create_payload)
                raise SandboxFileServerError(
                    paas_message or f"创建 sandbox PV 失败: HTTP {getattr(response, 'status_code', '')}"
                )

            create_payload = response.json()
            created_volume_id = self._extract_created_volume_id(create_payload)
            if not created_volume_id:
                logger.error("create_agent_sandbox_volume response missing uuid: %s", create_payload)
                paas_message = ""
                if isinstance(create_payload, dict):
                    paas_message = str(create_payload.get("message") or "")
                raise SandboxFileServerError(paas_message or "创建 sandbox PV 返回格式异常")

            updated_session = self._rm.update_chat_session_sandbox_pv_id(
                session_code,
                created_volume_id,
            )
            persisted_volume_id = self._extract_volume_id(updated_session)
            if not persisted_volume_id:
                persisted_volume_id = self._extract_volume_id(self._rm.retrieve_chat_session(session_code))
            if not persisted_volume_id:
                raise SandboxFileServerError(f"会话 {session_code} 的 sandbox PV 写回失败")

            if persisted_volume_id != created_volume_id:
                self._delete_volume_quietly(client, app_code, created_volume_id)
            return persisted_volume_id
        except HTTPResponseError as exc:
            if created_volume_id:
                self._delete_volume_quietly(client, app_code, created_volume_id)
            self._raise_mapped_paas_error("ensure_volume", exc)
        except SandboxFileError:
            if created_volume_id:
                self._delete_volume_quietly(client, app_code, created_volume_id)
            raise
        except Exception as exc:
            if created_volume_id:
                self._delete_volume_quietly(client, app_code, created_volume_id)
            raise SandboxFileServerError(f"创建会话 sandbox PV 失败: {exc}") from exc

    # ------------------------------------------------------------------
    # 错误映射
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_paas_code(exc: HTTPResponseError) -> str:
        response = getattr(exc, "response", None)
        if response is None:
            return ""
        try:
            body = response.json()
        except Exception:  # noqa: BLE001 - 响应体可能不是 JSON
            return ""
        if not isinstance(body, dict):
            return ""
        return str(body.get("code") or "")

    @classmethod
    def _is_sandbox_gone(cls, exc: HTTPResponseError) -> bool:
        """复用路径上判断 sandbox 容器是否已被 PaaS 回收。

        只认 HTTP 404 或明确的容器不存在错误码，避免 FILE_TOO_LARGE 等业务错误触发重建。
        """
        status_code = getattr(getattr(exc, "response", None), "status_code", 0) or 0
        if status_code == 404:
            return True
        return cls._parse_paas_code(exc) in PV_PAAS_SANDBOX_GONE_CODES

    @classmethod
    def _map_paas_error(cls, exc: HTTPResponseError) -> SandboxFileError:
        """PaaS HTTP 错误 → 沙箱文件业务异常（表驱动）。

        规则：(match_status_code, matched_paas_codes, exception_cls)
        - status_code 命中 或 paas_code 命中 即归到该规则
        - match_status_code=None 时仅按 paas_code 匹配（400 系不能按 status 盲判）
        未命中的错误统一归 `SandboxFileServerError`。
        """
        status_code = getattr(getattr(exc, "response", None), "status_code", 0) or 0
        paas_code = cls._parse_paas_code(exc)
        message = f"PaaS 沙箱文件接口调用失败: status={status_code} code={paas_code or '-'}"

        rules: tuple[tuple[Optional[int], frozenset[str], type[SandboxFileError]], ...] = (
            (404, PV_PAAS_ERROR_NOT_FOUND_CODES, SandboxFileNotFoundError),
            (415, PV_PAAS_ERROR_NOT_PREVIEWABLE_CODES, SandboxFileInvalidRequestError),
            (413, PV_PAAS_ERROR_TOO_LARGE_CODES, SandboxFileInvalidRequestError),
            (None, PV_PAAS_ERROR_INVALID_ARG_CODES, SandboxFileInvalidArgumentError),
        )
        for match_status, code_set, exc_cls in rules:
            if (match_status is not None and match_status == status_code) or paas_code in code_set:
                return exc_cls(message)
        return SandboxFileServerError(message)

    @classmethod
    def _raise_mapped_paas_error(cls, action: str, exc: HTTPResponseError) -> None:
        mapped = cls._map_paas_error(exc)
        logger.warning("call paas sandbox file api failed: action=%s error=%s", action, mapped, exc_info=True)
        raise mapped from exc

    # ------------------------------------------------------------------
    # 参数组装
    # ------------------------------------------------------------------

    @staticmethod
    def _to_iso8601_z(value: Optional[datetime]) -> Optional[str]:
        """tz-aware datetime → PaaS ISO 8601 UTC 秒精度格式：`2026-06-24T10:23:11Z`。

        - 只接受 tz-aware datetime；naive datetime 直接报错（避免按运行环境时区隐式假设）
        - 强制秒精度，microseconds 被裁掉
        """
        if value is None:
            return None
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise SandboxFileInvalidArgumentError("since/until 必须是 tz-aware datetime（含时区信息）")
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _call_single(self, action: str, session_code: str, params: dict):
        """调用 PaaS 单个操作（非分页），返回原始 Response。

        `action` 同时用作 Client 属性名与错误日志 tag（当前所有单请求方法都对齐）。
        """
        volume_id = self._get_volume_id(session_code)
        client = self._get_client()
        try:
            resp = getattr(client, action).request(
                path_params=self._build_path_params(volume_id),
                params=params,
            )
            resp.raise_for_status()
            return resp
        except HTTPResponseError as exc:
            self._raise_mapped_paas_error(action, exc)

    # ------------------------------------------------------------------
    # 6 个业务方法
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_file_name(name: str) -> str:
        file_name = PurePosixPath(name.replace("\\", "/")).name
        if not file_name or file_name in {".", ".."}:
            raise SandboxFileInvalidArgumentError("文件名不能为空")
        return file_name

    def _resolve_upload_snapshot(self) -> str:
        """读取平台注入的 snapshot；未注入则报错。"""
        snapshot = str(self._executor_info.get("snapshot") or "").strip()
        if snapshot:
            return snapshot
        raise SandboxFileInvalidArgumentError("创建临时 sandbox 需要 file-kit Skill 的已构建镜像")

    def _create_upload_sandbox(
        self,
        session_code: str,
        volume_id: str,
        snapshot: str,
        backend: PaasSandboxBackend,
    ) -> tuple[str, float]:
        """创建临时上传 sandbox，并返回 sandbox_id 与创建时间。"""
        started = time.monotonic()
        sandbox_id = backend.create_sandbox(
            name=f"aidev-upload-{uuid4().hex[:12]}",
            ttl_seconds=TEMP_UPLOAD_SANDBOX_TTL_SECONDS,
            snapshot=snapshot,
            snapshot_entrypoint=[],
            volume_mounts=[{"volume_id": volume_id, "mount_path": TEMP_UPLOAD_VOLUME_MOUNT_PATH}],
        )
        created_at = time.monotonic()
        logger.info(
            "[pv_files] create_sandbox session=%s sandbox_id=%s elapsed=%.2fs",
            session_code,
            sandbox_id,
            created_at - started,
        )
        return sandbox_id, created_at

    def _write_files_to_sandbox(
        self,
        session_code: str,
        sandbox_id: str,
        backend: PaasSandboxBackend,
        files_dir: str,
        absolute_files_dir: str,
        files: list[SandboxUploadFile],
    ) -> list[dict]:
        """在指定 sandbox 的统一 files 目录内上传文件，返回每文件结果。

        不再固定 sleep 等待 sandbox 就绪：exec_command 自带 NOT_READY 重试，
        沙箱未就绪时会自动重试，就绪快时省去固定等待。
        """
        mkdir_result = backend.exec_command(sandbox_id, ["mkdir", "-p", absolute_files_dir])
        if mkdir_result.exit_code not in (0, None):
            raise SandboxFileServerError(
                f"创建上传目录失败: exit_code={mkdir_result.exit_code}, stderr={mkdir_result.stderr}"
            )

        used_names: set[str] = set()
        results: list[dict] = []
        for upload_file in files:
            original_name = upload_file["name"]
            file_name = self._safe_file_name(original_name)
            if file_name in used_names:
                stem, suffix = posixpath.splitext(file_name)
                file_name = f"{stem}-{uuid4().hex[:8]}{suffix}"
            used_names.add(file_name)
            relative_path = posixpath.join(files_dir, file_name)
            absolute_path = posixpath.join(TEMP_UPLOAD_VOLUME_MOUNT_PATH, relative_path)
            result = {
                "type": "file",
                "id": relative_path,
                "path": relative_path,
                "name": original_name,
                "mime_type": upload_file.get("mime_type", ""),
                "size": len(upload_file["content"]),
            }
            try:
                backend.upload_file(sandbox_id, absolute_path, upload_file["content"])
                result["status"] = "success"
            except HTTPResponseError:
                raise
            except Exception as exc:  # noqa: BLE001 单文件失败不阻断同批其他文件
                logger.warning(
                    "上传文件到会话 PV 失败: session_code=%s, file=%s",
                    session_code,
                    original_name,
                    exc_info=True,
                )
                result.update(status="failed", error=str(exc))
            results.append(result)
        return results

    def upload_files(
        self,
        session_code: str,
        files: list[SandboxUploadFile],
        *,
        cached_volume_id: str | None = None,
    ) -> dict:
        """通过会话级复用的临时 sandbox 将一批文件写入会话 PV。

        sandbox 容器按 app_code、session_code 和 volume_id 缓存复用（ttl=TEMP_UPLOAD_SANDBOX_TTL_SECONDS），
        复用期内不再 create/destroy，到期由 PaaS 自动回收；复用失败（容器已被回收）
        时 fallback 重建一次。同会话操作加锁串行化，避免单容器并发冲突。
        """
        validate_session_upload_files(files)

        snapshot = self._resolve_upload_snapshot()
        volume_id = self.ensure_volume(session_code, cached_volume_id=cached_volume_id)
        client = self._get_client()
        backend = PaasSandboxBackend(
            app_code=self._executor_info.get("app_code") or "",
            bk_username=self._executor_info.get("executor") or "",
            client=client,
            snapshot=snapshot,
            snapshot_entrypoint=[],
            env_vars={},
        )
        files_dir = SESSION_FILES_DIR
        absolute_files_dir = posixpath.join(TEMP_UPLOAD_VOLUME_MOUNT_PATH, files_dir)

        # 会话级操作锁：串行化同会话的 sandbox exec/upload，避免单容器并发冲突
        with _get_session_op_lock(session_code):
            app_code = self._executor_info.get("app_code") or ""
            sandbox_id = _get_cached_upload_sandbox(app_code, session_code, volume_id)
            sandbox_created_at: float | None = None
            if not sandbox_id:
                sandbox_id, sandbox_created_at = self._create_upload_sandbox(session_code, volume_id, snapshot, backend)

            try:
                results = self._write_files_to_sandbox(
                    session_code, sandbox_id, backend, files_dir, absolute_files_dir, files
                )
                _set_cached_upload_sandbox(
                    app_code,
                    session_code,
                    volume_id,
                    sandbox_id,
                    created_at=sandbox_created_at,
                )
            except HTTPResponseError as exc:
                if self._is_sandbox_gone(exc):
                    # 缓存的 sandbox 已被 PaaS 回收，清缓存重建一次后重试
                    logger.warning(
                        "[pv_files] reuse sandbox gone, fallback rebuild session=%s sandbox_id=%s",
                        session_code,
                        sandbox_id,
                    )
                    _invalidate_cached_upload_sandbox(app_code, session_code, volume_id)
                    sandbox_id, sandbox_created_at = self._create_upload_sandbox(
                        session_code, volume_id, snapshot, backend
                    )
                    results = self._write_files_to_sandbox(
                        session_code, sandbox_id, backend, files_dir, absolute_files_dir, files
                    )
                    _set_cached_upload_sandbox(
                        app_code,
                        session_code,
                        volume_id,
                        sandbox_id,
                        created_at=sandbox_created_at,
                    )
                else:
                    self._raise_mapped_paas_error("upload_files", exc)
            except SandboxFileError:
                raise
            except Exception as exc:
                raise SandboxFileServerError(f"临时 sandbox 上传失败: {exc}") from exc

        succeeded = sum(item["status"] == "success" for item in results)
        self._attach_image_download_urls(session_code, results)
        return {
            "count": len(results),
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
            "results": results,
        }

    def _attach_image_download_urls(self, session_code: str, results: list[dict]) -> None:
        """给成功上传的图片签发 download_url，供输入框和首条 user 消息展示。"""
        for item in results:
            if item.get("status") != "success":
                continue
            if not str(item.get("mime_type") or "").startswith("image/"):
                continue
            path = item.get("path")
            if not path:
                continue
            try:
                url_data = self.get_download_url(
                    session_code, path, expires_in=IMAGE_DOWNLOAD_URL_EXPIRES_IN
                )
            except SandboxFileError:
                logger.exception("签发上传图片 URL 失败: session=%s path=%s", session_code, path)
                continue
            url = url_data.get("download_url")
            if url:
                item["download_url"] = url

    def list_files(
        self,
        session_code: str,
        path: str = "",
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> dict:
        """列出会话 PV 内所有非目录文件（内部分页拉全量）。

        - 硬编码 `is_recursive=True`，对前端不暴露
        - 循环拉 PaaS 全量（page_size=500，max_pages=20 保护）
        - 翻页前 `time.sleep(0.5)` 预防性等待
        - 过滤 `is_dir=false`，`count` 使用过滤后数量

        返回结构：
            {
                "count": int,               # 过滤后文件数 (= len(results))
                "results": list[dict],      # 仅文件，不含目录
                "truncated": true,          # 仅在触达 max_pages 上限时附加
            }
        """
        volume_id = self._get_volume_id(session_code)
        client = self._get_client()
        path_params = self._build_path_params(volume_id)

        base_params: dict = {
            "path": path or "",
            "is_recursive": True,
            "page_size": PV_LIST_PAGE_SIZE,
        }
        since_str = self._to_iso8601_z(since)
        if since_str:
            base_params["since"] = since_str
        until_str = self._to_iso8601_z(until)
        if until_str:
            base_params["until"] = until_str

        all_results: list = []
        truncated = False
        for page in range(1, PV_LIST_MAX_PAGES + 1):
            if page >= 2:
                time.sleep(PV_LIST_PAGE_SLEEP_SECONDS)

            params = dict(base_params, page=page)
            try:
                resp = client.list_files.request(path_params=path_params, params=params)
                resp.raise_for_status()
                data = resp.json() or {}
            except HTTPResponseError as exc:
                self._raise_mapped_paas_error("list_files", exc)

            page_items = data.get("results") or []
            all_results.extend(page_items)
            total = int(data.get("count") or 0)
            if not page_items or len(all_results) >= total:
                break
        else:
            truncated = True
            logger.warning(
                "list_files hit max_pages=%d for volume=%s session=%s, truncated at %d items",
                PV_LIST_MAX_PAGES,
                volume_id,
                session_code,
                len(all_results),
            )

        files_only = [item for item in all_results if not item.get("is_dir")]
        result: dict = {"count": len(files_only), "results": files_only}
        if truncated:
            result["truncated"] = True
        return result

    def delete_file(self, session_code: str, path: str) -> None:
        """删除 PV 内指定文件（幂等）。"""
        self._call_single("delete_file", session_code, {"path": path})

    def stat_file(self, session_code: str, path: str) -> dict:
        """查询文件/目录元数据（不存在时 PaaS 返回 `exists=false`，透传）。"""
        resp = self._call_single("stat_file", session_code, {"path": path})
        return resp.json() or {}

    def preview_file(self, session_code: str, path: str, max_bytes: int = 65536) -> tuple[bytes, bool]:
        """返回文件前 max_bytes 字节纯文本内容，及是否被截断（`X-Truncated` header）。"""
        resp = self._call_single(
            "preview_file", session_code, {"path": path, "max_bytes": max_bytes}
        )
        truncated = str(resp.headers.get("X-Truncated", "false")).lower() == "true"
        return resp.content, truncated

    def get_download_url(self, session_code: str, path: str, expires_in: int = 600) -> dict:
        """签发临时 download_url / preview_url。"""
        resp = self._call_single(
            "get_download_url", session_code, {"path": path, "expires_in": expires_in}
        )
        return resp.json() or {}
