"""``BaseResourceManager`` Flow 方法透传 ``X-BKAIDEV-USER``。"""

from __future__ import annotations

from unittest.mock import MagicMock

from aidev_agent.packages.resource_manager.base import BaseResourceManager


class _StubResourceManager(BaseResourceManager):
    """带 mock 平台 client 的 ResourceManager。"""

    def __init__(self, username: str = ""):
        super().__init__(app_code="app", app_secret="s", username=username)
        self.client = MagicMock()
        self.client.api.flow_agent_start.return_value = {"data": {"task_id": "1"}}
        self.client.api.flow_agent_task_info.return_value = {"data": {"task_id": "1"}}
        self.client.api.flow_agent_retry_node.return_value = {"data": {"ok": True}}
        self.client.api.flow_agent_skip_node.return_value = {"data": {"ok": True}}
        self.client.api.flow_agent_task_stop.return_value = {"data": {"ok": True}}
        self.client.api.flow_agent_task_pause.return_value = {"data": {"ok": True}}
        self.client.api.flow_agent_task_resume.return_value = {"data": {"ok": True}}
        self.client.api.flow_agent_task_node_info.return_value = {"data": {"ok": True}}

    def get_client(self, **kwargs):
        return self.client


def test_start_flow_agent_injects_user_header():
    rm = _StubResourceManager(username="alice")

    result = rm.start_flow_agent(data={"session_code": "sc1"})

    assert result == {"task_id": "1"}
    rm.client.api.flow_agent_start.assert_called_once_with(
        data={"session_code": "sc1"}, headers={"X-BKAIDEV-USER": "alice"}
    )


def test_start_flow_agent_skips_header_when_username_empty():
    rm = _StubResourceManager(username="")

    rm.start_flow_agent(data={"session_code": "sc1"})

    rm.client.api.flow_agent_start.assert_called_once_with(data={"session_code": "sc1"})


def test_start_flow_agent_keeps_explicit_user_header():
    rm = _StubResourceManager(username="alice")

    rm.start_flow_agent(data={"session_code": "sc1"}, headers={"X-BKAIDEV-USER": "bob"})

    rm.client.api.flow_agent_start.assert_called_once_with(
        data={"session_code": "sc1"}, headers={"X-BKAIDEV-USER": "bob"}
    )


def test_other_flow_methods_inject_user_header():
    rm = _StubResourceManager(username="alice")
    expected = {"headers": {"X-BKAIDEV-USER": "alice"}}

    rm.get_flow_agent_task_info("t1")
    rm.retry_flow_agent_node("sc1", "n1")
    rm.skip_flow_agent_node("sc1", "n1")
    rm.stop_flow_agent_task("sc1")
    rm.pause_flow_agent_task("sc1")
    rm.resume_flow_agent_task("sc1")
    rm.get_flow_agent_task_node_info("t1", "n1")

    rm.client.api.flow_agent_task_info.assert_called_once_with(path_params={"task_id": "t1"}, **expected)
    rm.client.api.flow_agent_retry_node.assert_called_once_with(
        path_params={"session_code": "sc1", "node_id": "n1"}, **expected
    )
    rm.client.api.flow_agent_skip_node.assert_called_once_with(
        path_params={"session_code": "sc1", "node_id": "n1"}, **expected
    )
    rm.client.api.flow_agent_task_stop.assert_called_once_with(data={"session_code": "sc1"}, **expected)
    rm.client.api.flow_agent_task_pause.assert_called_once_with(data={"session_code": "sc1"}, **expected)
    rm.client.api.flow_agent_task_resume.assert_called_once_with(data={"session_code": "sc1"}, **expected)
    rm.client.api.flow_agent_task_node_info.assert_called_once_with(
        path_params={"task_id": "t1", "node_id": "n1"}, **expected
    )
