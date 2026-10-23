# -*- coding: utf-8 -*-
"""aidev_bkplugin ChatSessionShareView 分享接口单测。

覆盖点：
- create / retrieve 透传 X-BKAIDEV-USER；分享者票据以 AIDEV-TICKET 透传（cookie 优先，header 兜底，缺失则不带）
- 产物下载 action 透传 path 与身份；上游 404 映射为本地 404 并保留提示；上游信封缺失时给通用提示；其它上游错误原样抛出
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from bkapi_client_core.exceptions import HTTPResponseError
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEFAULT_CHARSET="utf-8",
        INSTALLED_APPS=[],
        PLATFORM_CODE="00",
        REST_FRAMEWORK={},
        USE_I18N=False,
    )

base_mod = types.ModuleType("aidev_bkplugin.views.base")
base_mod.IgnoreClientContentNegotiation = object
base_mod.PluginResourceManager = MagicMock()
base_mod.PluginViewSet = object
base_mod.logger = MagicMock()
sys.modules["aidev_bkplugin.views.base"] = base_mod

agent_config_mod = types.ModuleType("aidev_bkplugin.services.agent_config")
agent_config_mod.AgentConfigFetcher = MagicMock()
sys.modules["aidev_bkplugin.services.agent_config"] = agent_config_mod

from aidev_bkplugin.views import session as session_mod  # noqa: E402
from blueapps.core.exceptions import ResourceNotFound  # noqa: E402


def _request(username="alice", cookies=None, meta=None, query_params=None, data=None):
    return SimpleNamespace(
        user=SimpleNamespace(username=username),
        COOKIES=cookies or {},
        META=meta or {},
        query_params=query_params or {},
        data=data or {},
    )


def _view(api):
    """构造分享视图并注入 mock client；``PluginViewSet`` 是假基类，``client`` 可直接赋值。"""
    view = session_mod.ChatSessionShareView()
    view.client = SimpleNamespace(api=api)
    return view


def _upstream_error(status_code, message):
    """bkapi 上游错误：响应体为 bk-aidev 错误信封 ``{"error": {"message": ...}}``。"""
    response = SimpleNamespace(status_code=status_code, json=lambda: {"error": {"message": message}})
    return HTTPResponseError(response=response)


@pytest.fixture
def bkticket_cookie(settings):
    settings.BKAUTH_BACKEND_TYPE = "bk_ticket"
    return settings


class TestShareIdentityHeaders:
    def test_cookie_ticket_takes_precedence_over_header(self, bkticket_cookie):
        request = _request(
            username="alice",
            cookies={"bk_ticket": "from-cookie"},
            meta={"HTTP_AIDEV_TICKET": "from-header"},
        )
        assert session_mod._share_identity_headers(request) == {
            "X-BKAIDEV-USER": "alice",
            "AIDEV-TICKET": "from-cookie",
        }

    def test_header_ticket_is_fallback_when_cookie_missing(self, bkticket_cookie):
        request = _request(username="alice", meta={"HTTP_AIDEV_TICKET": "from-header"})
        assert session_mod._share_identity_headers(request) == {
            "X-BKAIDEV-USER": "alice",
            "AIDEV-TICKET": "from-header",
        }

    def test_missing_ticket_omits_aidev_ticket(self, bkticket_cookie):
        assert session_mod._share_identity_headers(_request(username="alice")) == {"X-BKAIDEV-USER": "alice"}


class TestChatSessionShareView:
    def test_create_forwards_body_and_identity(self, bkticket_cookie):
        api = MagicMock()
        api.share_chat_session.return_value = {"data": {"share_token": "tok"}}
        body = {"session_code": "s1", "content_ids": [1], "expired_at": 0}

        response = _view(api).create(_request(username="alice", cookies={"bk_ticket": "t"}, data=body))

        api.share_chat_session.assert_called_once_with(
            json=body,
            headers={"X-BKAIDEV-USER": "alice", "AIDEV-TICKET": "t"},
        )
        assert response.data == {"share_token": "tok"}

    def test_retrieve_forwards_identity_so_sharer_can_reopen_window(self, bkticket_cookie):
        api = MagicMock()
        api.get_shared_chat.return_value = {"data": {"session_contents": []}}

        _view(api).retrieve(_request(username="alice", meta={"HTTP_AIDEV_TICKET": "t"}), pk="tok")

        api.get_shared_chat.assert_called_once_with(
            path_params={"share_token": "tok"},
            headers={"X-BKAIDEV-USER": "alice", "AIDEV-TICKET": "t"},
        )

    def test_download_url_forwards_path_and_identity(self, bkticket_cookie):
        api = MagicMock()
        api.get_shared_chat_download_url.return_value = {"data": {"download_url": "https://signed"}}

        response = _view(api).pv_files_download_url(
            _request(username="bob", query_params={"path": "files/a.png"}),
            pk="tok",
        )

        api.get_shared_chat_download_url.assert_called_once_with(
            path_params={"share_token": "tok"},
            params={"path": "files/a.png"},
            headers={"X-BKAIDEV-USER": "bob"},
        )
        assert response.data == {"download_url": "https://signed"}

    def test_download_url_maps_upstream_404_to_not_found_with_hint(self):
        api = MagicMock()
        api.get_shared_chat_download_url.side_effect = _upstream_error(
            404, "图片和产物已过期，请分享人重新打开此分享链接签发"
        )

        with pytest.raises(ResourceNotFound) as exc_info:
            _view(api).pv_files_download_url(_request(query_params={"path": "files/a.png"}), pk="tok")

        assert exc_info.value.message == "图片和产物已过期，请分享人重新打开此分享链接签发"

    def test_download_url_uses_generic_hint_when_upstream_body_is_not_envelope(self):
        api = MagicMock()
        broken_response = SimpleNamespace(status_code=404, json=MagicMock(side_effect=ValueError("not json")))
        api.get_shared_chat_download_url.side_effect = HTTPResponseError(response=broken_response)

        with pytest.raises(ResourceNotFound) as exc_info:
            _view(api).pv_files_download_url(_request(query_params={"path": "files/a.png"}), pk="tok")

        assert exc_info.value.message == "分享文件不可用"

    def test_download_url_reraises_other_upstream_errors(self):
        api = MagicMock()
        api.get_shared_chat_download_url.side_effect = _upstream_error(500, "boom")

        with pytest.raises(HTTPResponseError):
            _view(api).pv_files_download_url(_request(query_params={"path": "files/a.png"}), pk="tok")
