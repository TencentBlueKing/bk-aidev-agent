# -*- coding: utf-8 -*-

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
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
base_mod.client = SimpleNamespace(api=MagicMock())
base_mod.logger = MagicMock()
sys.modules["aidev_bkplugin.views.base"] = base_mod

agent_config_mod = types.ModuleType("aidev_bkplugin.services.agent_config")
agent_config_mod.AgentConfigFetcher = MagicMock()
sys.modules["aidev_bkplugin.services.agent_config"] = agent_config_mod

from aidev_bkplugin.constants import AGUI_PROTOCOL_VERSION  # noqa: E402
from aidev_bkplugin.views import session as session_mod  # noqa: E402


def _request(query_params=None, username="alice", data=None):
    return SimpleNamespace(
        query_params=query_params or {},
        user=SimpleNamespace(username=username),
        data=data or {},
    )


def _session(session_code, protocol_version=AGUI_PROTOCOL_VERSION):
    return {"session_code": session_code, "protocol_version": protocol_version}


def test_list_without_pagination_returns_legacy_array(monkeypatch):
    api = MagicMock()
    api.list_chat_session.return_value = {"data": [_session("v2"), _session("v1", "v1")]}
    monkeypatch.setattr(session_mod, "client", SimpleNamespace(api=api))
    view = session_mod.ChatSessionViewSet()

    response = view.list(_request())

    assert response.data == [_session("v2")]
    api.list_chat_session.assert_called_once_with(
        headers={"X-BKAIDEV-USER": "alice"},
        params={"session_type": view.session_type, "protocol_version": AGUI_PROTOCOL_VERSION},
    )


def test_list_with_pagination_returns_paginated_data(monkeypatch):
    api = MagicMock()
    # 平台已按 protocol_version 过滤，返回纯 v2 分页结构，Agent 侧原样透传
    paginated = {
        "page": 1,
        "num_pages": 1,
        "count": 1,
        "results": [_session("v2")],
    }
    api.list_chat_session.return_value = {"data": paginated}
    monkeypatch.setattr(session_mod, "client", SimpleNamespace(api=api))
    view = session_mod.ChatSessionViewSet()

    response = view.list(_request({"page": "1", "page_size": "20"}))

    assert response.data == paginated
    api.list_chat_session.assert_called_once_with(
        headers={"X-BKAIDEV-USER": "alice"},
        params={
            "session_type": view.session_type,
            "protocol_version": AGUI_PROTOCOL_VERSION,
            "page": 1,
            "page_size": 20,
        },
    )


def test_list_with_pagination_handles_legacy_backend_array(monkeypatch):
    api = MagicMock()
    api.list_chat_session.return_value = {"data": [_session("v2"), _session("v1", "v1")]}
    monkeypatch.setattr(session_mod, "client", SimpleNamespace(api=api))

    response = session_mod.ChatSessionViewSet().list(_request({"page": "1", "page_size": "20"}))

    assert response.data == [_session("v2")]


def test_list_pagination_params_invalid_fallback_to_default(monkeypatch):
    """非法分页参数（0、负数、非数字）回退默认值，并以整数透传给平台"""
    api = MagicMock()
    api.list_chat_session.return_value = {"data": [_session("v2")]}
    monkeypatch.setattr(session_mod, "client", SimpleNamespace(api=api))
    view = session_mod.ChatSessionViewSet()

    # page=0、page_size=abc 均非法，应回退默认值
    view.list(_request({"page": "0", "page_size": "abc"}))

    api.list_chat_session.assert_called_once_with(
        headers={"X-BKAIDEV-USER": "alice"},
        params={
            "session_type": view.session_type,
            "protocol_version": AGUI_PROTOCOL_VERSION,
            "page": session_mod.DEFAULT_SESSION_PAGE,
            "page_size": session_mod.DEFAULT_SESSION_PAGE_SIZE,
        },
    )


@pytest.mark.parametrize("run_id", ["run-current", None])
def test_stop_clears_stale_notification_before_sending_cancel(monkeypatch, run_id):
    """每轮 stop 先清旧通知，并兼容不传 run_id 的旧前端。"""
    session_code = "session-stop-order"
    call_order = []
    handler = MagicMock()
    handler.clear_cancelled_signal.side_effect = lambda code, run_id=None: call_order.append(("clear", code, run_id))
    handler.wait_for_consumer_cancelled.side_effect = lambda code, timeout, run_id=None: (
        call_order.append(("wait", code, run_id)) or True
    )
    api = MagicMock()
    api.stop_chat_session_content.return_value = {"data": {"stopped": True}}

    monkeypatch.setattr(session_mod.message_handler_factory, "get", lambda: handler)
    monkeypatch.setattr(
        session_mod.GeneratorStreamingHelper,
        "cancel",
        lambda code, message_handler=None, run_id=None: (
            call_order.append(("cancel", code, message_handler, run_id)) or True
        ),
    )
    monkeypatch.setattr(session_mod.AgentConfigFetcher, "get_info", lambda **kwargs: {"agent_type": "chat"})
    monkeypatch.setattr(session_mod, "client", SimpleNamespace(api=api))

    request_data = {"session_code": session_code, **({"run_id": run_id} if run_id else {})}
    response = session_mod.ChatSessionContentViewSet().stop(_request(data=request_data))

    assert response.data == {"stopped": True}
    assert call_order == [
        ("clear", session_code, run_id),
        ("cancel", session_code, handler, run_id),
        ("wait", session_code, run_id),
    ]
    api.stop_chat_session_content.assert_called_once_with(
        json={"session_code": session_code},
        headers={"X-BKAIDEV-USER": "alice"},
    )
    handler.mark_stopped.assert_not_called()
