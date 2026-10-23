"""``BaseResourceManager`` 智能体授权状态与权限申请契约测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol


class _StubResourceManager(BaseResourceManager):
    def __init__(self):
        super().__init__(app_code="agent", app_secret="y")
        self.client = MagicMock()
        self.client.api.get_agent_access_status.return_value = {
            "data": {"status": "authorization_pending", "apply_url": "https://iam.example.com/apply"}
        }
        self.client.api.apply_agent_access.return_value = {"data": {"apply_url": "https://iam.example.com/apply"}}

    def get_client(self, **kwargs):
        return self.client


def test_get_agent_access_status_passes_user_header():
    rm = _StubResourceManager()

    result = rm.get_agent_access_status("alice")

    assert result == {"status": "authorization_pending", "apply_url": "https://iam.example.com/apply"}
    rm.client.api.get_agent_access_status.assert_called_once_with(headers={"X-BKAIDEV-USER": "alice"})


def test_apply_agent_access_passes_user_header():
    rm = _StubResourceManager()

    result = rm.apply_agent_access("alice", headers={"X-Trace": "1"})

    assert result == {"apply_url": "https://iam.example.com/apply"}
    rm.client.api.apply_agent_access.assert_called_once_with(
        data={}, headers={"X-Trace": "1", "X-BKAIDEV-USER": "alice"}
    )


def test_resource_manager_protocol_includes_access_methods():
    assert isinstance(_StubResourceManager(), ResourceManagerProtocol)
