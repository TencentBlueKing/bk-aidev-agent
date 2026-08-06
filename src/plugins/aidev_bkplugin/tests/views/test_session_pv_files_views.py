# -*- coding: utf-8 -*-
"""aidev_bkplugin ChatSessionViewSet.pv_files* action 单测。

覆盖点：
- 构造沙箱文件 Service 时正确注入 PluginResourceManager + executor_info
- 5 个 action 参数透传（GET list / DELETE / stat / preview / download_url）
- 沙箱文件异常 → HTTP 状态码映射（404 / 400 / 500）
- preview 返回 HttpResponse(text/plain) + X-Truncated 头透传
- path/max_bytes/expires_in 缺失或默认值回退
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.http import HttpResponse

if not settings.configured:
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        INSTALLED_APPS=[],
        PLATFORM_CODE="00",
        REST_FRAMEWORK={},
        USE_I18N=False,
        BK_APP_CODE="app-code",
        BK_APP_SECRET="app-secret",
        BKAUTH_BACKEND_TYPE="bk_ticket",
    )
else:
    # 显式补齐相关配置，供 _make_pv_file_service 读取
    setattr(settings, "BK_APP_CODE", getattr(settings, "BK_APP_CODE", "app-code"))
    setattr(settings, "BK_APP_SECRET", getattr(settings, "BK_APP_SECRET", "app-secret"))
    setattr(settings, "BKAUTH_BACKEND_TYPE", getattr(settings, "BKAUTH_BACKEND_TYPE", "bk_ticket"))


base_mod = types.ModuleType("aidev_bkplugin.views.base")
base_mod.IgnoreClientContentNegotiation = object
base_mod.PluginResourceManager = MagicMock()
base_mod.PluginResourceManager.return_value.resolve_access_token.return_value = None
base_mod.PluginViewSet = object
base_mod.client = SimpleNamespace(api=MagicMock())
base_mod.logger = MagicMock()
sys.modules["aidev_bkplugin.views.base"] = base_mod

agent_config_mod = types.ModuleType("aidev_bkplugin.services.agent_config")
agent_config_mod.AgentConfigFetcher = MagicMock()
sys.modules["aidev_bkplugin.services.agent_config"] = agent_config_mod

from aidev_agent.services.sandbox_pv_files import (  # noqa: E402
    SandboxFileError,
    SandboxFileInvalidArgumentError,
    SandboxFileInvalidRequestError,
    SandboxFileNotFoundError,
    SandboxFileServerError,
)
from aidev_bkplugin.views import session as session_mod  # noqa: E402


def _request(query_params=None, username="alice", method="GET", cookies=None, meta=None, path="/pv-files"):
    return SimpleNamespace(
        query_params=query_params or {},
        user=SimpleNamespace(username=username),
        method=method,
        COOKIES=cookies or {},
        META=meta or {},
        path=path,
    )


@pytest.fixture
def view():
    return session_mod.ChatSessionViewSet()


@pytest.fixture
def mock_svc():
    """打桩沙箱文件 Service 实例；测试点：view 层是否正确构造 + 参数透传。"""
    with patch.object(session_mod, "SandboxPvFileService") as svc_cls:
        instance = MagicMock()
        svc_cls.return_value = instance
        yield instance, svc_cls


@pytest.fixture(autouse=True)
def _reset_retrieve_chat_session_mock():
    """base_mod.client 是 module 级 mock，跨测试共享；每个用例前重置 retrieve_chat_session
    的 side_effect / return_value / call_history，避免 TestCheckSessionOwner 里配的
    side_effect 泄露到后续 TestPvFiles* 用例（那些用例默认应"归属校验通过"）。
    """
    session_mod.client.api.retrieve_chat_session.reset_mock(side_effect=True, return_value=True)
    yield


# ---------------------------------------------------------------------------
# _make_pv_file_service：构造凭证注入
# ---------------------------------------------------------------------------


class TestMakePvFileService:
    def test_injects_rm_and_executor_info(self, view, mock_svc):
        """默认场景：cookie/meta 均无 ticket，executor_info 里 bk_ticket_value 为空串。"""
        instance, svc_cls = mock_svc
        result = view._make_pv_file_service(_request())
        assert result is instance
        # PluginResourceManager 应以 username 构造
        session_mod.PluginResourceManager.assert_called_with(username="alice")
        # 沙箱文件 Service 构造参数验证
        call_kwargs = svc_cls.call_args.kwargs
        assert call_kwargs["resource_manager"] is session_mod.PluginResourceManager.return_value
        assert call_kwargs["executor_info"] == {
            "app_code": settings.BK_APP_CODE,
            "app_secret": settings.BK_APP_SECRET,
            "executor": "alice",
            "bk_ticket_key": "bk_ticket",
            "bk_ticket_value": "",
        }

    def test_reads_bk_ticket_from_cookie(self, view, mock_svc):
        """前端直调路径：cookie 里的 bk_ticket 被读取并透传到 executor_info。"""
        _, svc_cls = mock_svc
        view._make_pv_file_service(_request(cookies={"bk_ticket": "cookie-ticket-abc"}))
        call_kwargs = svc_cls.call_args.kwargs
        assert call_kwargs["executor_info"]["bk_ticket_key"] == "bk_ticket"
        assert call_kwargs["executor_info"]["bk_ticket_value"] == "cookie-ticket-abc"

    def test_falls_back_to_meta_header_when_cookie_missing(self, view, mock_svc):
        """兜底：cookie 无 ticket 时读 HTTP_AIDEV_TICKET header。"""
        _, svc_cls = mock_svc
        view._make_pv_file_service(_request(meta={"HTTP_AIDEV_TICKET": "meta-ticket-xyz"}))
        call_kwargs = svc_cls.call_args.kwargs
        assert call_kwargs["executor_info"]["bk_ticket_value"] == "meta-ticket-xyz"

    def test_cookie_wins_over_meta_when_both_present(self, view, mock_svc):
        """优先级：cookie > meta header。"""
        _, svc_cls = mock_svc
        view._make_pv_file_service(
            _request(
                cookies={"bk_ticket": "cookie-wins"},
                meta={"HTTP_AIDEV_TICKET": "meta-loser"},
            )
        )
        call_kwargs = svc_cls.call_args.kwargs
        assert call_kwargs["executor_info"]["bk_ticket_value"] == "cookie-wins"

    def test_uses_bk_token_key_for_open_env(self, view, mock_svc, monkeypatch):
        """外部环境：BKAUTH_BACKEND_TYPE=bk_token 时读 cookie[bk_token]。"""
        monkeypatch.setattr(settings, "BKAUTH_BACKEND_TYPE", "bk_token")
        _, svc_cls = mock_svc
        view._make_pv_file_service(_request(cookies={"bk_token": "open-token-123"}))
        call_kwargs = svc_cls.call_args.kwargs
        assert call_kwargs["executor_info"]["bk_ticket_key"] == "bk_token"
        assert call_kwargs["executor_info"]["bk_ticket_value"] == "open-token-123"


# ---------------------------------------------------------------------------
# pv_files (GET / DELETE)
# ---------------------------------------------------------------------------


class TestPvFilesGet:
    def test_list_forwards_path_and_returns_data(self, view, mock_svc):
        instance, _ = mock_svc
        instance.list_files.return_value = {"count": 1, "results": [{"path": "a.txt"}]}
        response = view.pv_files(_request({"path": "sub/"}), pk="s1")
        assert response.data == {"count": 1, "results": [{"path": "a.txt"}]}
        instance.list_files.assert_called_once_with(session_code="s1", path="sub/", since=None, until=None)

    def test_list_translates_not_found(self, view, mock_svc):
        instance, _ = mock_svc
        instance.list_files.side_effect = SandboxFileNotFoundError("nf")
        response = view.pv_files(_request(), pk="s1")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# _check_session_owner：归属校验（透传平台 AIDevObjectOwnerPermission 结果）
# ---------------------------------------------------------------------------


class TestCheckSessionOwner:
    @staticmethod
    def _make_http_error(status: int):
        """构造带 response.status_code 的 HTTPResponseError（bkapi_client_core 走 requests.RequestException 签名）。"""
        from bkapi_client_core.exceptions import HTTPResponseError

        response = MagicMock()
        response.status_code = status
        # RequestException 支持 response=... 作为构造 kwarg
        exc = HTTPResponseError(response=response)
        return exc

    def test_owner_ok_passes_through(self, view):
        """归属校验通过：调 client.api.retrieve_chat_session 无异常，不抛。"""
        # base_mod.client.api 默认是 MagicMock，任意调用返回新 MagicMock；autouse 已重置 side_effect
        view._check_session_owner(_request(username="alice"), "s1")
        session_mod.client.api.retrieve_chat_session.assert_called_once_with(
            path_params={"session_code": "s1"},
            headers={"X-BKAIDEV-USER": "alice"},
        )

    @pytest.mark.parametrize("status", [403, 404])
    def test_owner_denied_or_not_found_translates_to_client_error(self, view, status):
        """403（非归属）/ 404（会话不存在）→ ClientBlueException，附带对应 code。"""
        session_mod.client.api.retrieve_chat_session.side_effect = self._make_http_error(status)

        from blueapps.core.exceptions import ClientBlueException

        with pytest.raises(ClientBlueException) as excinfo:
            view._check_session_owner(_request(username="alice"), "s1")
        assert str(status) == excinfo.value.code

    def test_owner_other_http_error_reraises(self, view):
        """非 403/404 的 HTTPResponseError 原样抛出，不被吞掉。"""
        from bkapi_client_core.exceptions import HTTPResponseError

        session_mod.client.api.retrieve_chat_session.side_effect = self._make_http_error(500)

        with pytest.raises(HTTPResponseError):
            view._check_session_owner(_request(username="alice"), "s1")

    def test_owner_denied_blocks_pv_files_action(self, view, mock_svc):
        """集成：403 会在 pv_files action 顶部就拒掉，不会调用 Service。"""
        session_mod.client.api.retrieve_chat_session.side_effect = self._make_http_error(403)

        instance, _ = mock_svc
        from blueapps.core.exceptions import ClientBlueException

        with pytest.raises(ClientBlueException):
            view.pv_files(_request(username="alice"), pk="s1")
        instance.list_files.assert_not_called()


# ---------------------------------------------------------------------------
# pv_files_stat
# ---------------------------------------------------------------------------


class TestPvFilesStat:
    def test_stat_forwards_path(self, view, mock_svc):
        instance, _ = mock_svc
        instance.stat_file.return_value = {"exists": True, "size": 42}
        response = view.pv_files_stat(_request({"path": "x.txt"}), pk="s1")
        assert response.data == {"exists": True, "size": 42}
        instance.stat_file.assert_called_once_with(session_code="s1", path="x.txt")

    def test_stat_requires_path(self, view, mock_svc):
        from blueapps.core.exceptions import ClientBlueException

        with pytest.raises(ClientBlueException):
            view.pv_files_stat(_request({}), pk="s1")

    def test_stat_translates_invalid_arg(self, view, mock_svc):
        instance, _ = mock_svc
        instance.stat_file.side_effect = SandboxFileInvalidArgumentError("ia")
        response = view.pv_files_stat(_request({"path": "x.txt"}), pk="s1")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# pv_files_preview
# ---------------------------------------------------------------------------


class TestPvFilesPreview:
    def test_preview_returns_text_plain_with_x_truncated_true(self, view, mock_svc):
        instance, _ = mock_svc
        instance.preview_file.return_value = (b"hello", True)
        response = view.pv_files_preview(_request({"path": "x.txt"}), pk="s1")
        assert isinstance(response, HttpResponse)
        assert response["Content-Type"].startswith("text/plain")
        assert response["X-Truncated"] == "true"
        assert response.content == b"hello"
        instance.preview_file.assert_called_once_with(session_code="s1", path="x.txt", max_bytes=65536)

    def test_preview_x_truncated_false_default(self, view, mock_svc):
        instance, _ = mock_svc
        instance.preview_file.return_value = (b"hi", False)
        response = view.pv_files_preview(_request({"path": "x.txt"}), pk="s1")
        assert response["X-Truncated"] == "false"

    def test_preview_max_bytes_forwarded(self, view, mock_svc):
        instance, _ = mock_svc
        instance.preview_file.return_value = (b"", False)
        view.pv_files_preview(_request({"path": "x.txt", "max_bytes": "1024"}), pk="s1")
        assert instance.preview_file.call_args.kwargs["max_bytes"] == 1024

    def test_preview_max_bytes_invalid_fallback(self, view, mock_svc):
        instance, _ = mock_svc
        instance.preview_file.return_value = (b"", False)
        view.pv_files_preview(_request({"path": "x.txt", "max_bytes": "abc"}), pk="s1")
        assert instance.preview_file.call_args.kwargs["max_bytes"] == 65536

    def test_preview_translates_415(self, view, mock_svc):
        instance, _ = mock_svc
        instance.preview_file.side_effect = SandboxFileInvalidRequestError("415")
        response = view.pv_files_preview(_request({"path": "x.bin"}), pk="s1")
        assert response.status_code == 400

    def test_preview_requires_path(self, view, mock_svc):
        from blueapps.core.exceptions import ClientBlueException

        with pytest.raises(ClientBlueException):
            view.pv_files_preview(_request({}), pk="s1")


# ---------------------------------------------------------------------------
# pv_files_download_url
# ---------------------------------------------------------------------------


class TestPvFilesDownloadUrl:
    def test_download_url_forwards_expires(self, view, mock_svc):
        instance, _ = mock_svc
        instance.get_download_url.return_value = {"download_url": "https://cdn/x"}
        response = view.pv_files_download_url(_request({"path": "x.txt", "expires_in": "300"}), pk="s1")
        assert response.data == {"download_url": "https://cdn/x"}
        instance.get_download_url.assert_called_once_with(session_code="s1", path="x.txt", expires_in=300)

    def test_download_url_expires_default(self, view, mock_svc):
        instance, _ = mock_svc
        instance.get_download_url.return_value = {"download_url": "https://x"}
        view.pv_files_download_url(_request({"path": "x.txt"}), pk="s1")
        assert instance.get_download_url.call_args.kwargs["expires_in"] == 600

    def test_download_url_translates_server_error(self, view, mock_svc):
        instance, _ = mock_svc
        instance.get_download_url.side_effect = SandboxFileServerError("boom")
        response = view.pv_files_download_url(_request({"path": "x.txt"}), pk="s1")
        assert response.status_code == 500

    def test_download_url_requires_path(self, view, mock_svc):
        from blueapps.core.exceptions import ClientBlueException

        with pytest.raises(ClientBlueException):
            view.pv_files_download_url(_request({}), pk="s1")


# ---------------------------------------------------------------------------
# 异常映射：SandboxFileError 基类兜底为 500
# ---------------------------------------------------------------------------


class TestExceptionMapping:
    def test_base_error_fallback_to_500(self):
        response = session_mod.ChatSessionViewSet._pv_exc_to_response(SandboxFileError("unknown"))
        assert response.status_code == 500

    def test_not_found_error_maps_to_404(self):
        response = session_mod.ChatSessionViewSet._pv_exc_to_response(SandboxFileNotFoundError("nf"))
        assert response.status_code == 404

    def test_invalid_argument_maps_to_400(self):
        response = session_mod.ChatSessionViewSet._pv_exc_to_response(SandboxFileInvalidArgumentError("ia"))
        assert response.status_code == 400

    def test_invalid_request_maps_to_400(self):
        response = session_mod.ChatSessionViewSet._pv_exc_to_response(SandboxFileInvalidRequestError("ir"))
        assert response.status_code == 400
