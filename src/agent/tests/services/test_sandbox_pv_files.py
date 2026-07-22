# -*- coding: utf-8 -*-
"""SandboxPvFileService 单测（迁移自 bk-aidev 阶段一实现，覆盖业务核心逻辑）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bkapi_client_core.exceptions import HTTPResponseError

from aidev_agent.services.sandbox_pv_files import (
    PV_LIST_MAX_PAGES,
    PV_LIST_PAGE_SIZE,
    SandboxFileInvalidArgumentError,
    SandboxFileInvalidRequestError,
    SandboxFileNotFoundError,
    SandboxFileServerError,
    SandboxPvFileService,
)


# ---------------------------------------------------------------------------
# 工具函数 & fixture
# ---------------------------------------------------------------------------


def _mock_http_error(status_code: int, code: str = "") -> HTTPResponseError:
    """构造 PaaS HTTPResponseError（携带 status_code + JSON body 里的 code）。"""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = {"code": code} if code else {}
    exc = HTTPResponseError()
    exc.response = mock_response
    return exc


def _mock_paas_response(json_data=None, headers=None, content: bytes = b""):
    """构造 PaaS 正常响应（含 raise_for_status / json / content / headers）。"""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_data if json_data is not None else {}
    resp.content = content
    resp.headers = headers or {}
    return resp


@pytest.fixture
def mock_client():
    """PaaS Sandbox Client 打桩（每个测试独立）。"""
    return MagicMock()


@pytest.fixture
def resource_manager(mock_client):
    """ResourceManager 打桩：默认返回带 sandbox_pv_id 的 session。"""
    rm = MagicMock()
    rm.retrieve_chat_session.return_value = {"session_property": {"sandbox_pv_id": "vol-abc"}}
    rm.get_paas_sbx_client.return_value = mock_client
    return rm


@pytest.fixture
def service(resource_manager):
    return SandboxPvFileService(
        resource_manager=resource_manager,
        executor_info={"app_code": "test-app", "app_secret": "test-secret"},
    )


@pytest.fixture(autouse=True)
def _no_sleep():
    """所有测试禁用 time.sleep，避免翻页测试变慢。"""
    with patch("aidev_agent.services.sandbox_pv_files.time.sleep") as m:
        yield m


# ---------------------------------------------------------------------------
# _get_volume_id：session 反查 & sandbox_pv_id 缺失
# ---------------------------------------------------------------------------


class TestGetVolumeId:
    def test_missing_sandbox_pv_id_raises(self, service, resource_manager):
        resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
        with pytest.raises(SandboxFileNotFoundError):
            service._get_volume_id("s1")

    def test_empty_session_dict_raises(self, service, resource_manager):
        resource_manager.retrieve_chat_session.return_value = {}
        with pytest.raises(SandboxFileNotFoundError):
            service._get_volume_id("s1")

    def test_returns_pv_id(self, service):
        assert service._get_volume_id("s1") == "vol-abc"


# ---------------------------------------------------------------------------
# _to_iso8601_z / _parse_paas_code / _map_paas_error
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_to_iso8601_z_none_returns_none(self):
        assert SandboxPvFileService._to_iso8601_z(None) is None

    def test_to_iso8601_z_utc_datetime(self):
        dt = datetime(2026, 6, 24, 10, 23, 11, tzinfo=timezone.utc)
        assert SandboxPvFileService._to_iso8601_z(dt) == "2026-06-24T10:23:11Z"

    def test_to_iso8601_z_tz_aware_non_utc(self):
        """带时区偏移的 datetime 应被规范化为 UTC。"""
        cst = timezone(timedelta(hours=8))
        dt = datetime(2026, 6, 24, 18, 23, 11, tzinfo=cst)  # 相当于 UTC 10:23:11
        assert SandboxPvFileService._to_iso8601_z(dt) == "2026-06-24T10:23:11Z"

    def test_to_iso8601_z_truncates_microseconds(self):
        """microseconds 被裁到秒精度，避免 PaaS 收到无法预期的小数秒。"""
        dt = datetime(2026, 6, 24, 10, 23, 11, 123456, tzinfo=timezone.utc)
        assert SandboxPvFileService._to_iso8601_z(dt) == "2026-06-24T10:23:11Z"

    def test_to_iso8601_z_naive_datetime_raises(self):
        """naive datetime 直接报错，避免按运行环境时区隐式假设。"""
        naive = datetime(2026, 6, 24, 10, 23, 11)
        with pytest.raises(SandboxFileInvalidArgumentError):
            SandboxPvFileService._to_iso8601_z(naive)

    def test_parse_paas_code_no_response(self):
        exc = HTTPResponseError()
        exc.response = None
        assert SandboxPvFileService._parse_paas_code(exc) == ""

    def test_parse_paas_code_non_json_body(self):
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("not json")
        exc = HTTPResponseError()
        exc.response = mock_response
        assert SandboxPvFileService._parse_paas_code(exc) == ""


class TestErrorMapping:
    """PaaS 状态码/错误码 → 沙箱文件业务异常映射。"""

    @pytest.mark.parametrize(
        "status, code, expected",
        [
            (404, "AGENT_SANDBOX_FILE_NOT_FOUND", SandboxFileNotFoundError),
            (404, "VOLUME_NOT_FOUND", SandboxFileNotFoundError),
            (404, "", SandboxFileNotFoundError),
            (415, "AGENT_SANDBOX_FILE_NOT_PREVIEWABLE", SandboxFileInvalidRequestError),
            (413, "AGENT_SANDBOX_FILE_TOO_LARGE", SandboxFileInvalidRequestError),
            (400, "AGENT_SANDBOX_FILE_OPERATION_FAILED", SandboxFileInvalidArgumentError),
            (400, "AGENT_SANDBOX_ARCHIVE_FAILED", SandboxFileServerError),
            (502, "AGENT_SANDBOX_SERVICE_NOT_READY", SandboxFileServerError),
            (500, "UNKNOWN_XYZ", SandboxFileServerError),
        ],
    )
    def test_map_paas_error(self, status, code, expected):
        exc = _mock_http_error(status, code)
        mapped = SandboxPvFileService._map_paas_error(exc)
        assert isinstance(mapped, expected)


# ---------------------------------------------------------------------------
# list_files：分页 + 目录过滤 + 参数透传 + 错误映射
# ---------------------------------------------------------------------------


class TestListFiles:
    def test_single_page_no_paging(self, service, mock_client, _no_sleep):
        mock_client.list_files.request.return_value = _mock_paas_response(
            {
                "count": 3,
                "results": [
                    {"path": "a.txt", "is_dir": False},
                    {"path": "b/", "is_dir": True},
                    {"path": "b/c.txt", "is_dir": False},
                ],
            }
        )

        result = service.list_files(session_code="s1")

        # 单页无需 sleep
        assert _no_sleep.call_count == 0
        # 目录被过滤，count 使用过滤后数量
        assert result["count"] == 2
        assert all(not item["is_dir"] for item in result["results"])
        # 调 PaaS 参数：硬编码 is_recursive=True + page_size + page=1
        req_kwargs = mock_client.list_files.request.call_args.kwargs
        assert req_kwargs["path_params"] == {"app_code": "test-app", "volume_id": "vol-abc"}
        params = req_kwargs["params"]
        assert params["is_recursive"] is True
        assert params["page_size"] == PV_LIST_PAGE_SIZE
        assert params["page"] == 1
        assert "since" not in params
        assert "until" not in params

    def test_since_and_until_forwarded(self, service, mock_client):
        mock_client.list_files.request.return_value = _mock_paas_response({"count": 0, "results": []})
        since = datetime(2026, 6, 24, 10, 23, 11, tzinfo=timezone.utc)
        until = datetime(2026, 6, 25, 10, 23, 11, tzinfo=timezone.utc)

        service.list_files(session_code="s1", since=since, until=until)

        params = mock_client.list_files.request.call_args.kwargs["params"]
        assert params["since"] == "2026-06-24T10:23:11Z"
        assert params["until"] == "2026-06-25T10:23:11Z"

    def test_path_forwarded(self, service, mock_client):
        mock_client.list_files.request.return_value = _mock_paas_response({"count": 0, "results": []})
        service.list_files(session_code="s1", path="sub/dir")
        assert mock_client.list_files.request.call_args.kwargs["params"]["path"] == "sub/dir"

    def test_multi_page_accumulates_and_sleeps(self, service, mock_client, _no_sleep):
        page1 = {
            "count": 3,
            "results": [{"path": f"f{i}.txt", "is_dir": False} for i in range(2)],
        }
        page2 = {
            "count": 3,
            "results": [{"path": "f2.txt", "is_dir": False}],
        }
        mock_client.list_files.request.side_effect = [
            _mock_paas_response(page1),
            _mock_paas_response(page2),
        ]

        result = service.list_files(session_code="s1")

        assert result["count"] == 3
        # 翻页 1 次 → sleep 1 次 0.5s
        assert _no_sleep.call_count == 1
        assert _no_sleep.call_args.args[0] == 0.5

    def test_empty_page_terminates(self, service, mock_client):
        mock_client.list_files.request.side_effect = [
            _mock_paas_response({"count": 1000, "results": []}),
        ]
        result = service.list_files(session_code="s1")
        assert result["count"] == 0

    def test_max_pages_truncates(self, service, mock_client):
        """20 页都满页 → 触发 max_pages 保护 + truncated=True。"""
        page_with_500 = {
            "count": 100000,
            "results": [{"path": f"f{i}.txt", "is_dir": False} for i in range(PV_LIST_PAGE_SIZE)],
        }
        mock_client.list_files.request.side_effect = [
            _mock_paas_response(page_with_500)
        ] * PV_LIST_MAX_PAGES
        result = service.list_files(session_code="s1")
        assert result["count"] == PV_LIST_PAGE_SIZE * PV_LIST_MAX_PAGES
        assert result["truncated"] is True

    def test_http_error_maps_to_sandbox_exception(self, service, mock_client):
        mock_client.list_files.request.side_effect = _mock_http_error(404, "VOLUME_NOT_FOUND")
        with pytest.raises(SandboxFileNotFoundError):
            service.list_files(session_code="s1")


# ---------------------------------------------------------------------------
# delete_file / stat_file / preview_file / get_download_url
# ---------------------------------------------------------------------------


class TestOtherServiceMethods:
    def test_delete_file_forwards_path(self, service, mock_client):
        mock_client.delete_file.request.return_value = _mock_paas_response()
        service.delete_file(session_code="s1", path="x.txt")
        kwargs = mock_client.delete_file.request.call_args.kwargs
        assert kwargs["params"] == {"path": "x.txt"}
        assert kwargs["path_params"]["volume_id"] == "vol-abc"

    def test_delete_file_maps_404(self, service, mock_client):
        mock_client.delete_file.request.side_effect = _mock_http_error(404, "AGENT_SANDBOX_FILE_NOT_FOUND")
        with pytest.raises(SandboxFileNotFoundError):
            service.delete_file(session_code="s1", path="x.txt")

    def test_stat_file_returns_paas_body(self, service, mock_client):
        mock_client.stat_file.request.return_value = _mock_paas_response({"exists": True, "size": 42})
        assert service.stat_file(session_code="s1", path="x.txt") == {"exists": True, "size": 42}

    def test_stat_file_exists_false_pass_through(self, service, mock_client):
        """PaaS 用 exists=false 表达不存在时，Service 不应转异常。"""
        mock_client.stat_file.request.return_value = _mock_paas_response({"exists": False})
        assert service.stat_file(session_code="s1", path="x.txt") == {"exists": False}

    def test_preview_file_truncated_true(self, service, mock_client):
        mock_client.preview_file.request.return_value = _mock_paas_response(
            content=b"hello", headers={"X-Truncated": "true"}
        )
        content, truncated = service.preview_file(session_code="s1", path="x.txt")
        assert content == b"hello"
        assert truncated is True

    def test_preview_file_truncated_false_default(self, service, mock_client):
        mock_client.preview_file.request.return_value = _mock_paas_response(content=b"hi", headers={})
        _, truncated = service.preview_file(session_code="s1", path="x.txt")
        assert truncated is False

    def test_preview_file_max_bytes_forwarded(self, service, mock_client):
        mock_client.preview_file.request.return_value = _mock_paas_response(content=b"")
        service.preview_file(session_code="s1", path="x.txt", max_bytes=1024)
        assert mock_client.preview_file.request.call_args.kwargs["params"]["max_bytes"] == 1024

    def test_preview_file_maps_415(self, service, mock_client):
        mock_client.preview_file.request.side_effect = _mock_http_error(
            415, "AGENT_SANDBOX_FILE_NOT_PREVIEWABLE"
        )
        with pytest.raises(SandboxFileInvalidRequestError):
            service.preview_file(session_code="s1", path="x.bin")

    def test_get_download_url_forwards_expires(self, service, mock_client):
        mock_client.get_download_url.request.return_value = _mock_paas_response(
            {"download_url": "https://cdn/x", "preview_url": "https://cdn/x"}
        )
        result = service.get_download_url(session_code="s1", path="x.txt", expires_in=300)
        assert result == {"download_url": "https://cdn/x", "preview_url": "https://cdn/x"}
        params = mock_client.get_download_url.request.call_args.kwargs["params"]
        assert params["expires_in"] == 300
