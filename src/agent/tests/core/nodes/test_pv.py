# -*- coding: utf-8 -*-
"""Test module for PV Node (aidev_agent.core.nodes.pv).

测试 PV Node 的核心逻辑：
- add_pv_info reducer 的合并与去重
- make_pv_node 工厂函数生成的 pv_node 闭包逻辑
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

from aidev_agent.pydantic_models import ExecuteKwargs
from langchain_core.messages import AIMessage, HumanMessage

# 直接从 pv.py 文件加载模块，避免 __init__.py 的 NotRequired 兼容性问题

_pv_mod_path = Path(__file__).resolve().parents[3] / "aidev_agent" / "core" / "nodes" / "pv.py"
_spec = importlib.util.spec_from_file_location("aidev_agent.core.nodes.pv", _pv_mod_path)
_pv_mod = importlib.util.module_from_spec(_spec)

# 注册 nodes 包（不触发 __init__.py）
_nodes_pkg = type(sys)("aidev_agent.core.nodes")
_nodes_pkg.__path__ = [str(_pv_mod_path.parent)]
_nodes_pkg.__file__ = str(_pv_mod_path.parent / "__init__.py")
sys.modules["aidev_agent.core.nodes"] = _nodes_pkg

_spec.loader.exec_module(_pv_mod)
sys.modules["aidev_agent.core.nodes.pv"] = _pv_mod

add_pv_info = _pv_mod.add_pv_info
make_pv_node = _pv_mod.make_pv_node


# ---------------------------------------------------------------------------
# add_pv_info reducer 测试
# ---------------------------------------------------------------------------


def test_add_pv_info_empty():
    """空输入返回空列表。"""
    assert add_pv_info([], []) == []


def test_add_pv_info_append():
    """不同 PV 信息应追加到列表。"""
    existing = [{"type": "paas-sbx-pv", "volume_id": "id1", "volume_name": "n1", "mount_path": "session"}]
    new = [{"type": "paas-sbx-pv", "volume_id": "id2", "volume_name": "n2", "mount_path": "agent"}]
    result = add_pv_info(existing, new)
    assert len(result) == 2
    assert result[0]["volume_id"] == "id1"
    assert result[1]["volume_id"] == "id2"


def test_add_pv_info_dedup():
    """完全相同的 PV 信息应去重，仅保留一份。"""
    item = {"type": "paas-sbx-pv", "volume_id": "id1", "volume_name": "n1", "mount_path": "session"}
    result = add_pv_info([item], [item])
    assert len(result) == 1
    assert result[0] == item


def test_add_pv_info_upserts_session_pv():
    """session 级 paas-sbx-pv 按逻辑身份 upsert，仅保留一份。"""
    existing = [
        {
            "type": "paas-sbx-pv",
            "volume_id": "runtime-id",
            "volume_name": "agent-pv-test-thread",
            "mount_path": "session",
            "source": "runtime",
        },
        {"type": "paas-sbx-pv", "volume_id": "agent-id", "volume_name": "agent-pv", "mount_path": "agent"},
    ]
    new = [
        {
            "type": "paas-sbx-pv",
            "volume_id": "platform-id",
            "volume_name": "agent-pv-test-thread",
            "mount_path": "session",
            "source": "platform",
        }
    ]

    result = add_pv_info(existing, new)

    session_pvs = [pv for pv in result if pv.get("type") == "paas-sbx-pv" and pv.get("mount_path") == "session"]
    assert len(session_pvs) == 1
    assert session_pvs[0]["volume_id"] == "platform-id"
    assert session_pvs[0]["source"] == "platform"
    assert result[1]["volume_id"] == "agent-id"


# ---------------------------------------------------------------------------
# make_pv_node 测试
# ---------------------------------------------------------------------------


def _make_mock_client():
    """创建 mock Client，带有 create_agent_sandbox_volume 操作。

    蓝鲸 API 响应格式为 {"code": 0, "message": "OK", "data": {"uuid": "..."}}。
    """
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"code": 0, "message": "OK", "data": {"uuid": "test-volume-uuid"}}
    client.create_agent_sandbox_volume.request.return_value = resp
    return client


def _make_mock_resource_manager():
    """创建带有 chat-session PV 写回方法的 mock resource manager。"""
    resource_manager = MagicMock()
    resource_manager.update_chat_session_sandbox_pv_id.side_effect = lambda _session_code, volume_id: {
        "session_property": {"sandbox_pv_id": volume_id}
    }
    return resource_manager


def _make_ai_message_with_paas_sandbox():
    """创建带有 paas_sandbox tool_call 的 AIMessage。"""
    return AIMessage(
        content="", tool_calls=[{"args": {"target_runtime": "paas_sandbox"}, "id": "tc1", "name": "activate_skill"}]
    )


def _make_ai_message_without_paas_sandbox():
    """创建不包含 paas_sandbox tool_call 的 AIMessage。"""
    return AIMessage(
        content="", tool_calls=[{"args": {"target_runtime": "local"}, "id": "tc2", "name": "activate_skill"}]
    )


def _make_config(thread_id: str = "test-thread", session_code: str | None = None) -> dict:
    """构造带 thread_id 和可选 session_code 的 configurable dict。

    session_code 为 None 时不注入 execute_kwargs，模拟一次性任务场景。
    """
    configurable: dict = {"thread_id": thread_id}
    if session_code is not None:
        configurable["execute_kwargs"] = ExecuteKwargs(session_code=session_code)
    return {"configurable": configurable}


def test_pv_node_skip_existing_platform_session_pv():
    """state 中已有 platform session PV 时，pv_node 不创建、不写回。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "existing-id",
                "volume_name": "existing-name",
                "mount_path": "session",
                "source": "platform",
            }
        ],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config("test-thread", session_code="test-session")

    result = pv_node(state, config)
    assert result == {}
    client.create_agent_sandbox_volume.request.assert_not_called()
    resource_manager.update_chat_session_sandbox_pv_id.assert_not_called()


def test_pv_node_skip_no_tool_calls():
    """last_message 不是 AIMessage 或无 tool_calls 时，pv_node 返回空。"""
    client = _make_mock_client()
    pv_node = make_pv_node(client=client, app_code="test-app")

    # 无消息
    state = {"runtime_paas_sbx_pv": [], "messages": []}
    config = _make_config()
    result = pv_node(state, config)
    assert result == {}

    # 消息不是 AIMessage（HumanMessage 无 tool_calls）
    human_msg = HumanMessage(content="Hello")
    state2 = {"runtime_paas_sbx_pv": [], "messages": [human_msg]}
    result2 = pv_node(state2, config)
    assert result2 == {}


def test_pv_node_skip_no_paas_sandbox():
    """tool_calls 中无 paas_sandbox target_runtime 时，pv_node 返回空。"""
    client = _make_mock_client()
    pv_node = make_pv_node(client=client, app_code="test-app")

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_without_paas_sandbox()],
    }
    config = _make_config()

    result = pv_node(state, config)
    assert result == {}
    client.create_agent_sandbox_volume.request.assert_not_called()


def test_pv_node_reuses_platform_volume_without_create():
    """创建前读到会话已绑定的卷时，直接复用，不新建。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    resource_manager.retrieve_chat_session.return_value = {
        "session_property": {"sandbox_pv_id": "vol-uploaded"}
    }
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    client.create_agent_sandbox_volume.request.assert_not_called()
    resource_manager.update_chat_session_sandbox_pv_id.assert_not_called()
    assert result == {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "vol-uploaded",
                "volume_name": "",
                "mount_path": "session",
                "source": "platform",
            }
        ]
    }


def test_pv_node_creates_pv_and_writes_back():
    """有 paas_sandbox tool_call 且无现有 PV 时，创建 PV 并写回平台。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    # 验证 API 被调用（volume_name 含随机后缀，用 startswith 检查）
    call_args = client.create_agent_sandbox_volume.request.call_args
    assert call_args.kwargs["path_params"] == {"app_code": "test-app"}
    assert call_args.kwargs["json"]["name"].startswith("agent-pv-test-thread-")
    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("test-session", "test-volume-uuid")

    # 验证返回结果
    assert "runtime_paas_sbx_pv" in result
    pv_list = result["runtime_paas_sbx_pv"]
    assert len(pv_list) == 1
    pv = pv_list[0]
    assert pv["type"] == "paas-sbx-pv"
    assert pv["volume_id"] == "test-volume-uuid"
    assert pv["volume_name"].startswith("agent-pv-test-thread-")
    assert pv["mount_path"] == "session"
    assert pv["source"] == "platform"


def test_pv_node_mounts_persisted_volume_when_concurrent_upload_wins():
    """上传与 Agent 并发创建 PV 时，Agent 必须挂载平台先持久化的上传卷。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
    resource_manager.update_chat_session_sandbox_pv_id.side_effect = None
    resource_manager.update_chat_session_sandbox_pv_id.return_value = {
        "session_property": {"sandbox_pv_id": "upload-volume-id"}
    }
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("test-session", "test-volume-uuid")
    pv = result["runtime_paas_sbx_pv"][0]
    assert pv["volume_id"] == "upload-volume-id"
    assert pv["volume_name"] == ""
    assert pv["source"] == "platform"
    client.delete_agent_sandbox_volume.request.assert_called_once_with(
        path_params={"app_code": "test-app", "volume_id": "test-volume-uuid"}
    )


def test_pv_node_writeback_failure_keeps_runtime_source():
    """写回失败不抛出，创建的 PV 以 runtime source 留在 state。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    resource_manager.update_chat_session_sandbox_pv_id.side_effect = RuntimeError("writeback failed")
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("test-session", "test-volume-uuid")
    pv = result["runtime_paas_sbx_pv"][0]
    assert pv["volume_id"] == "test-volume-uuid"
    assert pv["source"] == "runtime"


def test_pv_node_retries_runtime_source_without_recreate():
    """已有 runtime session PV 时补写平台，成功后更新 source 且不重新创建。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "runtime-volume-id",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "runtime",
            }
        ],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    client.create_agent_sandbox_volume.request.assert_not_called()
    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("test-session", "runtime-volume-id")
    assert result == {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "runtime-volume-id",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "platform",
            }
        ]
    }


def test_pv_node_creates_pv_direct_format():
    """API 响应直接在顶层返回 uuid（非标准蓝鲸包装格式）时也能正确处理。"""
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"uuid": "direct-uuid"}
    client.create_agent_sandbox_volume.request.return_value = resp

    pv_node = make_pv_node(client=client, app_code="test-app")
    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config()

    result = pv_node(state, config)
    pv = result["runtime_paas_sbx_pv"][0]
    assert pv["volume_id"] == "direct-uuid"
    assert pv["source"] == "runtime"


def test_pv_node_returns_empty_when_uuid_missing():
    """API 响应中无 uuid 字段时，pv_node 返回空 dict 而非抛异常。"""
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"code": 0, "data": {"name": "no-uuid"}}
    client.create_agent_sandbox_volume.request.return_value = resp

    pv_node = make_pv_node(client=client, app_code="test-app")
    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config()

    result = pv_node(state, config)
    assert result == {}


def test_pv_node_returns_empty_when_data_null():
    """API 响应 data 为 null 时，pv_node 返回空 dict 而非抛异常。"""
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"code": 0, "message": "OK", "data": None}
    client.create_agent_sandbox_volume.request.return_value = resp

    pv_node = make_pv_node(client=client, app_code="test-app")
    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config()

    result = pv_node(state, config)
    assert result == {}


def test_pv_node_retries_missing_source_session_pv():
    """已有 session PV 但缺少 source 字段时，应触发写回重试（D-10）。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "stale-id",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                # source 字段缺失 — 应视为非 platform，触发重试
            }
        ],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    client.create_agent_sandbox_volume.request.assert_not_called()
    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("test-session", "stale-id")
    assert result == {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "stale-id",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "platform",
            }
        ]
    }


def test_pv_node_retry_writeback_failure_returns_empty():
    """已有 runtime session PV 补写失败时，返回 {} 不阻断执行（D-09/D-10）。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    resource_manager.update_chat_session_sandbox_pv_id.side_effect = RuntimeError("retry failed")
    pv_node = make_pv_node(client=client, app_code="test-app", resource_manager=resource_manager)

    state = {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "runtime-vol-id",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "runtime",
            }
        ],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    client.create_agent_sandbox_volume.request.assert_not_called()
    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("test-session", "runtime-vol-id")
    assert result == {}


# ---------------------------------------------------------------------------
# 辅助函数：subagent tool_call 测试
# ---------------------------------------------------------------------------


def _make_ai_message_with_agent_tool(tool_name: str = "Agent"):
    """创建带有 Agent 工具调用的 AIMessage。"""
    return AIMessage(content="", tool_calls=[{"name": tool_name, "args": {"message": "test"}, "id": "tc3"}])


# ---------------------------------------------------------------------------
# execute_kwargs source 处理测试
# ---------------------------------------------------------------------------


def test_pv_node_retries_execute_kwargs_session_pv():
    """state 中已有 source='execute_kwargs' session PV 时，仍需写回平台。

    只有 platform 来源才跳过回写；execute_kwargs 等其他来源都应触发回写，
    成功后 source 升级为 platform 并返回更新后的 PV。
    """
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    pv_node = make_pv_node(
        client=client,
        app_code="test-app",
        resource_manager=resource_manager,
        enable_pv_by_subagent=True,
    )

    state = {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "ek-vol-id",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "execute_kwargs",
            }
        ],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config(session_code="test-session")

    result = pv_node(state, config)

    # 不应重新创建 PV
    client.create_agent_sandbox_volume.request.assert_not_called()
    # 应触发写回
    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once_with("test-session", "ek-vol-id")
    # 写回成功后 source 升级为 platform
    assert result == {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "ek-vol-id",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "platform",
            }
        ]
    }


# ---------------------------------------------------------------------------
# subagent tool_call 检测测试
# ---------------------------------------------------------------------------


def test_pv_node_subagent_reuses_existing_pv():
    """enable_pv_by_subagent=True 且 Agent tool_call 检测到，已有 session PV 时直接复用。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    pv_node = make_pv_node(
        client=client,
        app_code="test-app",
        resource_manager=resource_manager,
        enable_pv_by_paas_runtime=False,
        enable_pv_by_subagent=True,
    )

    state = {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "existing-vol",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "runtime",
            }
        ],
        "messages": [_make_ai_message_with_agent_tool("Agent")],
    }
    config = _make_config(session_code="test-session")

    pv_node(state, config)
    # 已有 session PV，不应创建新的
    client.create_agent_sandbox_volume.request.assert_not_called()
    # runtime source 应尝试写回
    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once()


def test_pv_node_subagent_sendmessages_reuses_existing_pv():
    """enable_pv_by_subagent=True 且 sendMessages tool_call 检测到，已有 session PV 时复用。"""
    client = _make_mock_client()
    resource_manager = _make_mock_resource_manager()
    pv_node = make_pv_node(
        client=client,
        app_code="test-app",
        resource_manager=resource_manager,
        enable_pv_by_paas_runtime=False,
        enable_pv_by_subagent=True,
    )

    state = {
        "runtime_paas_sbx_pv": [
            {
                "type": "paas-sbx-pv",
                "volume_id": "existing-vol-2",
                "volume_name": "agent-pv-test-thread",
                "mount_path": "session",
                "source": "runtime",
            }
        ],
        "messages": [_make_ai_message_with_agent_tool("sendMessages")],
    }
    config = _make_config(session_code="test-session")

    pv_node(state, config)
    client.create_agent_sandbox_volume.request.assert_not_called()
    resource_manager.update_chat_session_sandbox_pv_id.assert_called_once()


def test_pv_node_subagent_creates_pv_when_none_exists():
    """enable_pv_by_subagent=True，Agent tool_call 检测到，无现有 PV 时创建新 PV。"""
    client = _make_mock_client()
    pv_node = make_pv_node(
        client=client,
        app_code="test-app",
        enable_pv_by_paas_runtime=False,
        enable_pv_by_subagent=True,
    )

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_agent_tool("Agent")],
    }
    config = _make_config()

    result = pv_node(state, config)
    client.create_agent_sandbox_volume.request.assert_called_once()
    pv = result["runtime_paas_sbx_pv"][0]
    assert pv["type"] == "paas-sbx-pv"
    assert pv["mount_path"] == "session"
    assert pv["source"] == "runtime"


def test_pv_node_subagent_disabled_ignores_agent_tool():
    """enable_pv_by_subagent=False 时，Agent tool_call 被忽略，返回 {}。"""
    client = _make_mock_client()
    pv_node = make_pv_node(
        client=client,
        app_code="test-app",
        enable_pv_by_subagent=False,
    )

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_agent_tool("Agent")],
    }
    config = _make_config()

    result = pv_node(state, config)
    assert result == {}
    client.create_agent_sandbox_volume.request.assert_not_called()


def test_pv_node_paas_runtime_disabled_ignores_paas_sandbox():
    """enable_pv_by_paas_runtime=False 时，paas_sandbox tool_call 被忽略。"""
    client = _make_mock_client()
    pv_node = make_pv_node(
        client=client,
        app_code="test-app",
        enable_pv_by_paas_runtime=False,
        enable_pv_by_subagent=False,
    )

    state = {
        "runtime_paas_sbx_pv": [],
        "messages": [_make_ai_message_with_paas_sandbox()],
    }
    config = _make_config()

    result = pv_node(state, config)
    assert result == {}
    client.create_agent_sandbox_volume.request.assert_not_called()
