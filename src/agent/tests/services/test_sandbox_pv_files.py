# -*- coding: utf-8 -*-
"""SandboxPvFileService 单测（迁移自 bk-aidev 阶段一实现，覆盖业务核心逻辑）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.services import sandbox_pv_files as module
from aidev_agent.services.sandbox_pv_files import (
    MAX_SESSION_UPLOAD_FILE_SIZE,
    MAX_SESSION_UPLOAD_FILES,
    PV_LIST_MAX_PAGES,
    PV_LIST_PAGE_SIZE,
    SandboxFileError,
    SandboxFileInvalidArgumentError,
    SandboxFileInvalidRequestError,
    SandboxFileNotFoundError,
    SandboxFileServerError,
    SandboxPvFileService,
    fill_user_image_urls,
    validate_session_upload_files,
)
from bkapi_client_core.exceptions import HTTPResponseError

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
    resp.ok = True
    resp.status_code = 200
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


DEFAULT_UPLOAD_SNAPSHOT = "mirrors.tencent.com/bkpaas-sandbox/bkaidev/file-kit:0.0.9"


@pytest.fixture
def service(resource_manager):
    return SandboxPvFileService(
        resource_manager=resource_manager,
        executor_info={
            "app_code": "test-app",
            "app_secret": "test-secret",
            "snapshot": DEFAULT_UPLOAD_SNAPSHOT,
        },
    )


@pytest.fixture(autouse=True)
def _no_sleep():
    """所有测试禁用 time.sleep，避免翻页测试变慢。"""
    with patch("aidev_agent.services.sandbox_pv_files.time.sleep") as m:
        yield m


@pytest.fixture(autouse=True)
def _reset_upload_caches():
    """每个测试前清空会话级 sandbox 复用缓存，避免测试间残留。"""
    from aidev_agent.services import sandbox_pv_files as mod

    mod._UPLOAD_SANDBOX_CACHE.clear()
    yield


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


class TestUploadSandboxCache:
    def test_cache_isolated_by_volume(self):
        module._set_cached_upload_sandbox("app-a", "s1", "vol-a", "sandbox-a", created_at=100.0)

        with patch.object(module.time, "monotonic", return_value=100.0):
            assert module._get_cached_upload_sandbox("app-a", "s1", "vol-a") == "sandbox-a"
            assert module._get_cached_upload_sandbox("app-a", "s1", "vol-b") == ""
            assert module._get_cached_upload_sandbox("app-b", "s1", "vol-a") == ""

    def test_successful_reuse_does_not_refresh_creation_time(self):
        module._set_cached_upload_sandbox("app-a", "s1", "vol-a", "sandbox-a", created_at=100.0)
        with patch.object(module.time, "monotonic", return_value=200.0):
            module._set_cached_upload_sandbox("app-a", "s1", "vol-a", "sandbox-a")

        assert module._UPLOAD_SANDBOX_CACHE[("app-a", "s1", "vol-a")] == ("sandbox-a", 100.0)

    def test_cache_expires_from_creation_time(self):
        module._set_cached_upload_sandbox("app-a", "s1", "vol-a", "sandbox-a", created_at=100.0)
        with patch.object(module.time, "monotonic", return_value=100.0 + 1800):
            assert module._get_cached_upload_sandbox("app-a", "s1", "vol-a") == ""


class TestEnsureVolume:
    def test_creates_and_persists_missing_volume(self, service, resource_manager, mock_client):
        resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
        resource_manager.update_chat_session_sandbox_pv_id.return_value = {
            "session_property": {"sandbox_pv_id": "vol-new"}
        }
        mock_client.create_agent_sandbox_volume.request.return_value = _mock_paas_response({"uuid": "vol-new"})

        assert service.ensure_volume("s1") == "vol-new"

        resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("s1", "vol-new")
        mock_client.create_agent_sandbox_volume.request.assert_called_once()
        call_kwargs = mock_client.create_agent_sandbox_volume.request.call_args.kwargs
        assert call_kwargs["path_params"] == {"app_code": "test-app"}
        assert call_kwargs["json"]["name"].startswith("session-pv-s1-")

    def test_creates_volume_from_apigw_wrapped_payload(self, service, resource_manager, mock_client):
        resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
        resource_manager.update_chat_session_sandbox_pv_id.return_value = {
            "session_property": {"sandbox_pv_id": "vol-wrapped"}
        }
        mock_client.create_agent_sandbox_volume.request.return_value = _mock_paas_response(
            {"code": 0, "message": "OK", "data": {"uuid": "vol-wrapped"}}
        )

        assert service.ensure_volume("s1") == "vol-wrapped"
        resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("s1", "vol-wrapped")

    def test_paas_business_error_message_is_surfaced(self, service, resource_manager, mock_client):
        resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
        mock_client.create_agent_sandbox_volume.request.return_value = _mock_paas_response(
            {"result": False, "code": 1640001, "message": "user authentication failed", "data": None}
        )
        with pytest.raises(SandboxFileServerError, match="user authentication failed"):
            service.ensure_volume("s1")

    def test_http_400_payload_is_surfaced(self, service, resource_manager, mock_client):
        resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
        resp = _mock_paas_response({"name": ["This field is required."]})
        resp.ok = False
        resp.status_code = 400
        mock_client.create_agent_sandbox_volume.request.return_value = resp
        with pytest.raises(SandboxFileServerError, match="This field is required"):
            service.ensure_volume("s1")

    def test_concurrent_winner_is_reused_and_orphan_is_deleted(self, service, resource_manager, mock_client):
        resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
        resource_manager.update_chat_session_sandbox_pv_id.return_value = {
            "session_property": {"sandbox_pv_id": "vol-winner"}
        }
        mock_client.create_agent_sandbox_volume.request.return_value = _mock_paas_response({"uuid": "vol-loser"})
        mock_client.delete_agent_sandbox_volume.request.return_value = _mock_paas_response()

        assert service.ensure_volume("s1") == "vol-winner"

        mock_client.delete_agent_sandbox_volume.request.assert_called_once_with(
            path_params={"app_code": "test-app", "volume_id": "vol-loser"}
        )

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

    def test_is_sandbox_gone_only_for_missing_container(self):
        """体积超限等业务错误码含 SANDBOX，但不能当成容器已回收。"""
        assert SandboxPvFileService._is_sandbox_gone(_mock_http_error(404, "AGENT_SANDBOX_NOT_FOUND")) is True
        assert SandboxPvFileService._is_sandbox_gone(_mock_http_error(404, "")) is True
        assert SandboxPvFileService._is_sandbox_gone(_mock_http_error(400, "SANDBOX_NOT_FOUND")) is True
        assert SandboxPvFileService._is_sandbox_gone(_mock_http_error(413, "AGENT_SANDBOX_FILE_TOO_LARGE")) is False
        assert SandboxPvFileService._is_sandbox_gone(_mock_http_error(415, "AGENT_SANDBOX_FILE_NOT_PREVIEWABLE")) is False
        assert SandboxPvFileService._is_sandbox_gone(_mock_http_error(400, "AGENT_SANDBOX_FILE_OPERATION_FAILED")) is False
        assert SandboxPvFileService._is_sandbox_gone(_mock_http_error(502, "AGENT_SANDBOX_SERVICE_NOT_READY")) is False

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


class TestUploadFiles:
    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_batch_creates_one_sandbox_and_caches_for_reuse(
        self, mock_backend_cls, service, resource_manager, _no_sleep
    ):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)

        result = service.upload_files(
            "s1",
            [
                {"name": "报告.pdf", "content": b"pdf", "mime_type": "application/pdf"},
                {"name": "image.png", "content": b"png", "mime_type": "image/png"},
            ],
        )

        assert result["count"] == 2
        assert result["succeeded"] == 2
        assert result["failed"] == 0
        assert all(item["status"] == "success" for item in result["results"])
        assert [item["path"] for item in result["results"]] == ["files/报告.pdf", "files/image.png"]
        assert backend.upload_file.call_count == 2
        assert [call.args[1] for call in backend.upload_file.call_args_list] == [
            "/app/.storage/session/files/报告.pdf",
            "/app/.storage/session/files/image.png",
        ]
        assert backend.create_sandbox.call_count == 1
        # 复用模式下不主动销毁，由 PaaS ttl 兜底回收
        assert backend.destroy_sandbox.call_count == 0
        # 不再固定 sleep 等待就绪，由 exec_command 的 NOT_READY 重试兜底
        assert _no_sleep.call_count == 0
        create_kwargs = backend.create_sandbox.call_args.kwargs
        assert create_kwargs["volume_mounts"] == [{"volume_id": "vol-abc", "mount_path": "/app/.storage/session"}]
        assert create_kwargs["snapshot_entrypoint"] == []
        assert create_kwargs["ttl_seconds"] == 1800
        assert create_kwargs["snapshot"] == DEFAULT_UPLOAD_SNAPSHOT

        # 同会话第二次上传复用已缓存 sandbox，不再 create/destroy
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        service.upload_files("s1", [{"name": "more.txt", "content": b"more"}])
        assert backend.create_sandbox.call_count == 1
        assert backend.destroy_sandbox.call_count == 0

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_reuse_sandbox_gone_falls_back_to_rebuild(self, mock_backend_cls, service, _no_sleep):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)

        # 首次创建并缓存
        service.upload_files("s1", [{"name": "a.txt", "content": b"a"}])
        assert backend.create_sandbox.call_count == 1

        # 模拟缓存的 sandbox 已被 PaaS 回收：exec 报 404，重建后第二次 exec 成功
        backend.create_sandbox.return_value = "sandbox-upload-2"
        backend.exec_command.side_effect = [
            _mock_http_error(404, "AGENT_SANDBOX_NOT_FOUND"),
            SimpleNamespace(stdout="", stderr="", exit_code=0),
        ]
        result = service.upload_files("s1", [{"name": "b.txt", "content": b"b"}])

        # fallback 重建一次
        assert backend.create_sandbox.call_count == 2
        assert result["succeeded"] == 1
        assert backend.destroy_sandbox.call_count == 0

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_upload_http_error_rebuilds_sandbox(self, mock_backend_cls, service):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.side_effect = ["sandbox-upload", "sandbox-upload-2"]
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        backend.upload_file.side_effect = [
            _mock_http_error(404, "AGENT_SANDBOX_NOT_FOUND"),
            None,
        ]

        result = service.upload_files("s1", [{"name": "file.txt", "content": b"content"}])

        assert result["succeeded"] == 1
        assert backend.create_sandbox.call_count == 2
        assert backend.upload_file.call_count == 2

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_file_too_large_does_not_rebuild_sandbox(self, mock_backend_cls, service):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        backend.upload_file.side_effect = _mock_http_error(413, "AGENT_SANDBOX_FILE_TOO_LARGE")

        with pytest.raises(SandboxFileInvalidRequestError):
            service.upload_files("s1", [{"name": "huge.txt", "content": b"x"}])

        assert backend.create_sandbox.call_count == 1

    def test_rejects_unsupported_extension_before_sandbox(self, service, mock_client):
        with pytest.raises(SandboxFileInvalidArgumentError, match=".exe"):
            service.upload_files("s1", [{"name": "payload.exe", "content": b"x"}])
        mock_client.create_agent_sandbox_volume.request.assert_not_called()

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_single_file_failure_does_not_abort_batch(self, mock_backend_cls, service):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        backend.upload_file.side_effect = [RuntimeError("upload failed"), None]

        result = service.upload_files(
            "s1",
            [
                {"name": "bad.txt", "content": b"bad"},
                {"name": "good.txt", "content": b"good"},
            ],
        )

        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert [item["status"] for item in result["results"]] == ["failed", "success"]
        # 复用模式下不主动销毁
        assert backend.destroy_sandbox.call_count == 0

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_setup_failure_does_not_destroy_sandbox(self, mock_backend_cls, service):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.side_effect = RuntimeError("mkdir failed")

        with pytest.raises(SandboxFileServerError, match="临时 sandbox 上传失败"):
            service.upload_files("s1", [{"name": "file.txt", "content": b"content"}])

        # 复用模式下不主动销毁，由 PaaS ttl 兜底回收
        assert backend.destroy_sandbox.call_count == 0
        backend.exec_command.side_effect = None
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        service.upload_files("s1", [{"name": "file.txt", "content": b"content"}])
        assert backend.create_sandbox.call_count == 2

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_attaches_download_url_for_images_only(self, mock_backend_cls, service, mock_client):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        mock_client.get_download_url.request.return_value = _mock_paas_response(
            {"download_url": "https://cdn/image.png", "preview_url": "https://preview/image.png"}
        )

        result = service.upload_files(
            "s1",
            [
                {"name": "note.txt", "content": b"txt", "mime_type": "text/plain"},
                {"name": "image.png", "content": b"png", "mime_type": "image/png"},
            ],
        )

        assert "download_url" not in result["results"][0]
        assert result["results"][1]["download_url"] == "https://cdn/image.png"
        params = mock_client.get_download_url.request.call_args.kwargs["params"]
        assert params == {"path": "files/image.png", "expires_in": 3600}

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_does_not_fallback_to_preview_url(self, mock_backend_cls, service, mock_client):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        mock_client.get_download_url.request.return_value = _mock_paas_response(
            {"preview_url": "https://preview/image.png"}
        )

        result = service.upload_files(
            "s1",
            [{"name": "image.png", "content": b"png", "mime_type": "image/png"}],
        )

        assert "download_url" not in result["results"][0]

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_image_url_failure_does_not_fail_upload(self, mock_backend_cls, service, mock_client):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        mock_client.get_download_url.request.side_effect = _mock_http_error(500, "UNKNOWN_XYZ")

        result = service.upload_files(
            "s1",
            [{"name": "image.png", "content": b"png", "mime_type": "image/png"}],
        )

        assert result["succeeded"] == 1
        assert "download_url" not in result["results"][0]

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_uses_executor_info_snapshot(self, mock_backend_cls, resource_manager, _no_sleep):
        backend = mock_backend_cls.return_value
        backend.create_sandbox.return_value = "sandbox-upload"
        backend.exec_command.return_value = SimpleNamespace(stdout="", stderr="", exit_code=0)
        service = SandboxPvFileService(
            resource_manager=resource_manager,
            executor_info={
                "app_code": "test-app",
                "app_secret": "test-secret",
                "executor": "alice",
                "snapshot": DEFAULT_UPLOAD_SNAPSHOT,
            },
        )

        service.upload_files("s1", [{"name": "file.txt", "content": b"content"}])

        assert backend.create_sandbox.call_args.kwargs["snapshot"] == DEFAULT_UPLOAD_SNAPSHOT

    @patch("aidev_agent.services.sandbox_pv_files.PaasSandboxBackend")
    def test_missing_upload_snapshot_raises_before_creating_sandbox(self, mock_backend_cls, resource_manager):
        service = SandboxPvFileService(
            resource_manager=resource_manager,
            executor_info={"app_code": "test-app", "app_secret": "test-secret"},
        )

        with pytest.raises(SandboxFileInvalidArgumentError, match="file-kit"):
            service.upload_files("s1", [{"name": "file.txt", "content": b"content"}])

        mock_backend_cls.return_value.create_sandbox.assert_not_called()
        resource_manager.update_chat_session_sandbox_pv_id.assert_not_called()


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
        mock_client.list_files.request.side_effect = [_mock_paas_response(page_with_500)] * PV_LIST_MAX_PAGES
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
        mock_client.preview_file.request.side_effect = _mock_http_error(415, "AGENT_SANDBOX_FILE_NOT_PREVIEWABLE")
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


class TestValidateSessionUploadFiles:
    def test_rejects_empty_files(self):
        with pytest.raises(SandboxFileInvalidArgumentError, match="不能为空"):
            validate_session_upload_files([])

    def test_rejects_too_many_files(self):
        files = [{"name": f"{index}.txt", "content": b"x"} for index in range(MAX_SESSION_UPLOAD_FILES + 1)]
        with pytest.raises(SandboxFileInvalidArgumentError, match="不能超过"):
            validate_session_upload_files(files)

    def test_rejects_unsupported_extension(self):
        with pytest.raises(SandboxFileInvalidArgumentError, match=".exe"):
            validate_session_upload_files([{"name": "payload.exe", "content": b"x"}])

    def test_rejects_oversized_file(self):
        with pytest.raises(SandboxFileInvalidArgumentError, match="超过单文件大小限制"):
            validate_session_upload_files(
                [{"name": "large.txt", "content": b"x" * (MAX_SESSION_UPLOAD_FILE_SIZE + 1)}]
            )


class TestFillUserImageUrls:
    def test_fills_missing_image_url(self):
        file_service = MagicMock()
        file_service.get_download_url.return_value = {"download_url": "https://cdn/a.png"}
        payload = {
            "role": "user",
            "session_code": "s1",
            "content": [
                {"type": "text", "text": "hi"},
                {"type": "binary", "mime_type": "image/png", "id": "files/a.png"},
            ],
        }

        fill_user_image_urls(file_service, payload)

        assert payload["content"][1]["url"] == "https://cdn/a.png"
        file_service.get_download_url.assert_called_once_with(
            session_code="s1", path="files/a.png", expires_in=3600
        )

    def test_skips_when_url_exists_or_not_image(self):
        file_service = MagicMock()
        payload = {
            "role": "user",
            "session_code": "s1",
            "content": [
                {"type": "binary", "mime_type": "image/png", "id": "files/a.png", "url": "https://old"},
                {"type": "binary", "mime_type": "application/pdf", "id": "files/a.pdf"},
            ],
        }

        fill_user_image_urls(file_service, payload)

        file_service.get_download_url.assert_not_called()
        assert payload["content"][0]["url"] == "https://old"

    def test_skips_failed_url_issue(self):
        file_service = MagicMock()
        file_service.get_download_url.side_effect = SandboxFileError("boom")
        payload = {
            "role": "user",
            "session_code": "s1",
            "content": [{"type": "binary", "mime_type": "image/png", "path": "files/a.png"}],
        }

        fill_user_image_urls(file_service, payload)

        assert "url" not in payload["content"][0]
