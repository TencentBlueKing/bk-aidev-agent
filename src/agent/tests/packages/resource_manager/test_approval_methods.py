"""``BaseResourceManager`` approval-related method contract tests.

覆盖 D-06 所需的三个审批方法：
- ``create_tool_approval``（POST json + ``X-BKAIDEV-USER`` header）
- ``is_resume_session``（GET path_params 模式）
- ``get_chat_session_contents``（GET query ``params=`` 模式，无路径占位符）

同时校验 base.py 与 registry.py 双写完整性（``@runtime_checkable`` isinstance 检查）。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol


class _StubResourceManager(BaseResourceManager):
    """Resource manager with a mocked platform API client."""

    def __init__(self):
        super().__init__(app_code="x", app_secret="y")
        self.client = MagicMock()
        self.client.api.create_tool_approval.return_value = {"data": {}}

    def get_client(self, **kwargs):
        return self.client


def test_create_tool_approval_posts_payload_and_user_header():
    rm = _StubResourceManager()
    payload = {"ticket": "t-1", "tool_args": {"x": 1}}

    result = rm.create_tool_approval(payload, username="u1")

    assert result == {}
    rm.client.api.create_tool_approval.assert_called_once_with(json=payload, headers={"X-BKAIDEV-USER": "u1"})


def test_create_tool_approval_without_username_posts_no_headers():
    rm = _StubResourceManager()
    payload = {"ticket": "t-1"}

    rm.create_tool_approval(payload)

    rm.client.api.create_tool_approval.assert_called_once_with(json=payload)


def test_is_resume_session_uses_path_params_and_returns_data():
    rm = _StubResourceManager()
    rm.client.api.is_resume_session.return_value = {"data": True}

    result = rm.is_resume_session("session-1")

    assert result is True
    rm.client.api.is_resume_session.assert_called_once_with(path_params={"session_code": "session-1"})


def test_get_chat_session_contents_uses_query_params_and_returns_list():
    rm = _StubResourceManager()
    rm.client.api.get_chat_session_contents.return_value = {"data": [{"id": 1}]}

    result = rm.get_chat_session_contents("session-1")

    assert result == [{"id": 1}]
    rm.client.api.get_chat_session_contents.assert_called_once_with(params={"session_code": "session-1"})


def test_base_implementation_satisfies_protocol_dual_write():
    rm = _StubResourceManager()

    assert isinstance(rm, ResourceManagerProtocol)
