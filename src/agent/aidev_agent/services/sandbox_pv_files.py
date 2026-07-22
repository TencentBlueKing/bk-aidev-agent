# -*- coding: utf-8 -*-
"""会话沙箱 PersistentVolume 文件业务层。

三大调用场景共享同一份实现：
1. bk-aidev 平台调试页：Django Service 层薄适配后调用（凭证 = 平台自身）
2. SDK 前端应用：`aidev_bkplugin` View 层调用（凭证 = Agent 应用自身）
3. Agent 运行时：如轮次产物识别节点直接调用（凭证 = executor_info）

Service 层职责：
- 通过 `ResourceManager` 反查 `session_code → volume_id`
- 通过 `ResourceManager` 构造 PaaS Sandbox Client
- 5 个业务方法（list/delete/stat/preview/get_download_url）
- `list_files` 内部分页拉全量 + `time.sleep` 超频保护 + 过滤目录
- PaaS HTTP 错误 → SDK 侧业务异常映射
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from bkapi_client_core.exceptions import HTTPResponseError

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

# PaaS 沙箱文件接口错误码 → 语义分组
PV_PAAS_ERROR_NOT_FOUND_CODES = frozenset({"AGENT_SANDBOX_FILE_NOT_FOUND", "VOLUME_NOT_FOUND"})
PV_PAAS_ERROR_NOT_PREVIEWABLE_CODES = frozenset({"AGENT_SANDBOX_FILE_NOT_PREVIEWABLE"})
PV_PAAS_ERROR_TOO_LARGE_CODES = frozenset({"AGENT_SANDBOX_FILE_TOO_LARGE"})
PV_PAAS_ERROR_INVALID_ARG_CODES = frozenset({"AGENT_SANDBOX_FILE_OPERATION_FAILED"})


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
        logger.warning(
            "call paas sandbox file api failed: action=%s error=%s", action, mapped, exc_info=True
        )
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
            raise SandboxFileInvalidArgumentError(
                "since/until 必须是 tz-aware datetime（含时区信息）"
            )
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
    # 5 个业务方法
    # ------------------------------------------------------------------

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
