"""``BaseResourceManager`` chat-session PV metadata contract tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from aidev_agent.packages.resource_manager.base import BaseResourceManager


class _StubResourceManager(BaseResourceManager):
    """Resource manager with a mocked platform API client."""

    def __init__(self):
        super().__init__(app_code="x", app_secret="y")
        self.client = MagicMock()
        self.client.api.retrieve_chat_session.return_value = {
            "data": {"session_code": "session-1", "session_property": {"sandbox_pv_id": "pv-1"}}
        }
        self.client.api.update_chat_session.return_value = {"data": {"session_code": "session-1"}}

    def get_client(self, **kwargs):
        return self.client


def test_retrieve_chat_session_returns_data_and_uses_session_code():
    rm = _StubResourceManager()

    result = rm.retrieve_chat_session("session-1")

    assert result == {"session_code": "session-1", "session_property": {"sandbox_pv_id": "pv-1"}}
    rm.client.api.retrieve_chat_session.assert_called_once_with(path_params={"session_code": "session-1"})


def test_update_chat_session_sandbox_pv_id_writes_only_sandbox_pv_id():
    rm = _StubResourceManager()

    result = rm.update_chat_session_sandbox_pv_id("session-1", "pv-1")

    assert result == {"session_code": "session-1"}
    rm.client.api.update_chat_session.assert_called_once_with(
        path_params={"session_code": "session-1"},
        json={"session_property": {"sandbox_pv_id": "pv-1"}},
    )
    _, kwargs = rm.client.api.update_chat_session.call_args
    assert set(kwargs["json"].keys()) == {"session_property"}
    assert set(kwargs["json"]["session_property"].keys()) == {"sandbox_pv_id"}


def test_update_chat_session_caller_context_writes_only_caller_context():
    rm = _StubResourceManager()

    result = rm.update_chat_session_caller_context("session-1", {"executor": "user", "caller_bk_app_code": "app-001"})

    assert result == {"session_code": "session-1"}
    rm.client.api.update_chat_session.assert_called_once_with(
        path_params={"session_code": "session-1"},
        json={"session_property": {"caller_context": {"executor": "user", "caller_bk_app_code": "app-001"}}},
    )


def test_update_chat_session_sandbox_pv_id_passes_kwargs():
    rm = _StubResourceManager()

    rm.update_chat_session_sandbox_pv_id("session-1", "pv-1", headers={"X-Test": "1"})

    rm.client.api.update_chat_session.assert_called_once_with(
        path_params={"session_code": "session-1"},
        json={"session_property": {"sandbox_pv_id": "pv-1"}},
        headers={"X-Test": "1"},
    )


def test_get_chat_session_contents_uses_query_params():
    rm = _StubResourceManager()
    rm.client.api.get_chat_session_contents.return_value = {"data": [{"id": 1, "role": "user", "content": "hi"}]}

    result = rm.get_chat_session_contents("session-1")

    assert result == [{"id": 1, "role": "user", "content": "hi"}]
    rm.client.api.get_chat_session_contents.assert_called_once_with(params={"session_code": "session-1"})
