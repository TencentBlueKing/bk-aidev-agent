# -*- coding: utf-8 -*-
"""``SessionManager`` 行为契约：哈希稳定性、幂等取建、save_content kwargs 透传。"""

from unittest.mock import MagicMock

import pytest
from aidev_bkplugin.constants import AGUI_PROTOCOL_VERSION
from aidev_bkplugin.services.agent_session import SessionManager


@pytest.fixture
def session_manager(mock_plugin_rm_client):
    # 依赖 mock_plugin_rm_client 以保证 patch 先于构造生效：
    # SessionManager 在 __init__ 即绑定 resource_manager，晚于构造的 patch 不再起作用。
    return SessionManager(username="alice", agent_code="bk-aidev")


@pytest.mark.parametrize(
    "username, agent_code, thread_id, expected_len",
    [
        ("alice", "bk-aidev", "t-1", 32),
        ("bob", "bk-aidev", "t-1", 32),
    ],
)
def test_generate_session_code_is_stable_md5(username, agent_code, thread_id, expected_len):
    code = SessionManager.generate_session_code(username, agent_code, thread_id)
    assert len(code) == expected_len
    assert SessionManager.generate_session_code(username, agent_code, thread_id) == code


@pytest.mark.parametrize("channel_type", ["popup", "rtx"])
def test_get_or_create_by_thread_id_delegates_to_resource_manager(
    session_manager,
    mock_plugin_rm_client,
    channel_type,
):
    result = session_manager.get_or_create_by_thread_id("t-1", channel_type=channel_type)

    expected = session_manager.generate_session_code("alice", "bk-aidev", "t-1")
    assert result == expected
    mock_plugin_rm_client.resource_manager_mock.get_or_create_session.assert_called_once_with(
        session_code=expected,
        session_name="新会话",
        protocol_version=AGUI_PROTOCOL_VERSION,
        is_temporary=None,
        channel_type=channel_type,
        headers={"X-BKAIDEV-USER": "alice"},
    )


def test_get_or_create_by_session_code_passes_options(session_manager, mock_plugin_rm_client):
    result = session_manager.get_or_create_by_session_code("sc-1", session_name="demo", is_temporary=True)

    assert result == "sc-1"
    call = mock_plugin_rm_client.resource_manager_mock.get_or_create_session.call_args
    assert call.kwargs["session_name"] == "demo"
    assert call.kwargs["is_temporary"] is True


@pytest.mark.parametrize(
    "extra, status, expect_extra",
    [
        (None, "success", False),
        ({"k": "v"}, "error", True),
    ],
)
def test_save_content_passes_extra_and_status(session_manager, mock_plugin_rm_client, extra, status, expect_extra):
    mock_plugin_rm_client.api.create_chat_session_content.return_value = {"data": {"id": 1}}

    session_manager.save_content("sc-1", "user", "hello", extra=extra, status=status, turn_id="turn-1")

    payload = mock_plugin_rm_client.api.create_chat_session_content.call_args.kwargs["json"]
    assert payload["status"] == status
    assert ("extra" in payload) is expect_extra
    assert payload["property"]["turn_id"] == "turn-1"


def test_save_content_generates_turn_id_for_user(session_manager, mock_plugin_rm_client):
    mock_plugin_rm_client.api.create_chat_session_content.return_value = {"data": {"id": 1}}

    saved = session_manager.save_content("sc-1", "user", "hello")

    payload = mock_plugin_rm_client.api.create_chat_session_content.call_args.kwargs["json"]
    assert payload["property"]["turn_id"]
    assert saved["property"]["turn_id"] == payload["property"]["turn_id"]


def test_set_flow_resume_pending_preserves_existing_fields(session_manager, mock_plugin_rm_client):
    """read-modify-write：仅叠加 resume_pending，保留 flow_info 其它字段与同级属性。"""
    mock_plugin_rm_client.api.retrieve_chat_session.return_value = {
        "data": {
            "session_property": {
                "flow_info": {"flow_id": "f1", "flow_version": "v1", "task_id": "t1"},
                "labels": ["x"],
            }
        }
    }

    session_manager.set_flow_resume_pending("sc-1", True)

    call = mock_plugin_rm_client.api.update_chat_session.call_args
    assert call.kwargs["path_params"] == {"session_code": "sc-1"}
    session_property = call.kwargs["json"]["session_property"]
    flow_info = session_property["flow_info"]
    assert flow_info["resume_pending"] is True
    # 既有字段不被覆盖
    assert flow_info["task_id"] == "t1"
    assert flow_info["flow_id"] == "f1"
    assert flow_info["flow_version"] == "v1"
    # session_property 同级其它字段不丢
    assert session_property["labels"] == ["x"]


def test_set_flow_resume_pending_creates_flow_info_when_absent(session_manager, mock_plugin_rm_client):
    """session_property / flow_info 缺失时，仅写入 resume_pending，不报错。"""
    mock_plugin_rm_client.api.retrieve_chat_session.return_value = {"data": {}}

    session_manager.set_flow_resume_pending("sc-1", False)

    session_property = mock_plugin_rm_client.api.update_chat_session.call_args.kwargs["json"]["session_property"]
    assert session_property["flow_info"] == {"resume_pending": False, "resume_action": ""}


@pytest.mark.parametrize(
    "data, expected",
    [
        (
            {"session_property": {"flow_info": {"task_id": "t1", "resume_pending": True}}},
            {"task_id": "t1", "resume_pending": True},
        ),
        ({"session_property": {}}, {}),
        ({}, {}),
    ],
)
def test_get_flow_info(session_manager, mock_plugin_rm_client, data, expected):
    """缺失 session_property / flow_info 时返回空 dict，否则原样返回。"""
    mock_plugin_rm_client.api.retrieve_chat_session.return_value = {"data": data}
    assert session_manager.get_flow_info("sc-1") == expected


def test_prepare_session_turn_inherits_user_turn_id_without_input(session_manager, mock_plugin_rm_client, monkeypatch):
    mock_plugin_rm_client.api.retrieve_chat_session.return_value = {"data": {"session_code": "sc-1"}}
    monkeypatch.setattr(
        session_manager,
        "list_session_contents",
        lambda _session_code: [
            {"role": "user", "property": {"turn_id": "turn-existing"}},
        ],
    )

    session_code, turn_id = session_manager.prepare_session_turn("thread-1", input_text="", channel_type="rtx")

    assert session_code
    assert turn_id == "turn-existing"
    assert mock_plugin_rm_client.resource_manager_mock.get_or_create_session.call_args.kwargs["channel_type"] == "rtx"
    mock_plugin_rm_client.api.create_chat_session_content.assert_not_called()


class _ProtocolOnlyResourceManager:
    """只按 ``ResourceManagerProtocol`` 实现的最小自定义 RM。

    刻意不继承 ``AgentResourceManager``：普通类访问未定义的属性会直接 AttributeError，
    因此本类同时充当"SessionManager 不得依赖协议之外方法"的探针。
    """

    def __init__(self):
        self.client = MagicMock()
        self.created: list[tuple] = []

    def get_client(self, **kwargs):
        return self.client

    def get_or_create_session(
        self,
        session_code: str,
        session_name: str,
        *,
        protocol_version: str = "",
        is_temporary: bool = False,
        session_type: str = "",
        channel_type: str = "",
        **kwargs,
    ) -> dict:
        self.created.append((session_code, session_name, protocol_version, channel_type))
        return {"session_code": session_code}


def test_session_manager_runs_through_protocol_only_resource_manager():
    """按公开协议实现的自定义 RM 必须能贯穿建会话流程。

    ``get_or_create_session`` 曾缺失于 ``ResourceManagerProtocol`` 声明，
    照协议实现的 RM 会在这里 AttributeError。
    """
    rm = _ProtocolOnlyResourceManager()
    manager = SessionManager(username="alice", agent_code="bk-aidev", resource_manager=rm)

    session_code = manager.get_or_create_by_thread_id("t-1")

    assert session_code == SessionManager.generate_session_code("alice", "bk-aidev", "t-1")
    assert rm.created == [(session_code, "新会话", AGUI_PROTOCOL_VERSION, "popup")]


@pytest.mark.parametrize("method_name", ["get_client", "get_or_create_session"])
def test_protocol_declares_every_method_session_manager_calls(method_name):
    """SessionManager 调用的 rm 方法都必须在协议里声明，否则自定义 RM 无从实现。"""
    from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol

    assert hasattr(ResourceManagerProtocol, method_name)
