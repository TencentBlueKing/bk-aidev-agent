"""``BaseResourceManager`` 智能体授权状态与权限申请契约测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

from aidev_agent.packages.resource_manager.base import BaseResourceManager


class _StubResourceManager(BaseResourceManager):
    def __init__(self):
        super().__init__(app_code="agent", app_secret="y")
        self.client = MagicMock()

    def get_client(self, **kwargs):
        return self.client


def test_access_methods_pass_user_header():
    rm = _StubResourceManager()
    rm.client.api.get_agent_access_status.return_value = {"data": {"status": "authorized"}}
    rm.client.api.apply_agent_access.return_value = {"data": {"apply_url": "https://iam.example.com/apply"}}

    assert rm.get_agent_access_status("alice") == {"status": "authorized"}
    assert rm.apply_agent_access("alice") == {"apply_url": "https://iam.example.com/apply"}
    rm.client.api.get_agent_access_status.assert_called_once_with(headers={"X-BKAIDEV-USER": "alice"})
    rm.client.api.apply_agent_access.assert_called_once_with(data={}, headers={"X-BKAIDEV-USER": "alice"})
