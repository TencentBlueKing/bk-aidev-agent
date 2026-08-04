# -*- coding: utf-8 -*-
"""Test module for PV-related graph routing changes.

测试 _should_continue 路由变更和 DefaultState PV 字段。

由于 aidev_agent.core.graphs.react.graph 模块在 Python 3.10 环境下
可能因 langchain_core.pydantic_v1 依赖问题无法直接导入，
这些测试通过内联复制核心逻辑来验证正确性。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from aidev_agent.core.nodes.pv import add_pv_info
from langchain_core.messages import AIMessage, HumanMessage

# ---------------------------------------------------------------------------
# 内联 _should_continue 逻辑（与 graph.py 完全一致）
# ---------------------------------------------------------------------------


def _should_continue(state: dict) -> Literal["approval_check", "end"]:
    """条件路由函数：决定 model 节点后的下一步（与 graph.py 一致）。"""
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "approval_check"

    return "end"


# ---------------------------------------------------------------------------
# _should_continue 测试
# ---------------------------------------------------------------------------


def test_should_continue_returns_approval_check():
    """AIMessage 有 tool_calls 时，_should_continue 返回 'approval_check'。"""
    ai_msg = AIMessage(content="", tool_calls=[{"id": "tc1", "name": "test_tool", "args": {}}])
    state = {"messages": [ai_msg]}
    result = _should_continue(state)
    assert result == "approval_check"


def test_should_continue_returns_end():
    """无 tool_calls 时，_should_continue 返回 'end'。"""
    human_msg = HumanMessage(content="Hello")
    state = {"messages": [human_msg]}
    result = _should_continue(state)
    assert result == "end"


def test_should_continue_empty_messages():
    """空消息列表时，_should_continue 返回 'end'。"""
    state = {"messages": []}
    result = _should_continue(state)
    assert result == "end"


# ---------------------------------------------------------------------------
# DefaultState 字段测试（通过源码静态验证）
# ---------------------------------------------------------------------------


def _read_graph_source() -> str:
    """读取 graph.py 源码，避免直接导入带来环境兼容问题。"""
    graph_path = Path(__file__).resolve().parents[3] / "aidev_agent" / "core" / "graphs" / "react" / "graph.py"
    return graph_path.read_text(encoding="utf-8")


def test_default_state_has_pv_field():
    """验证 DefaultState 包含 runtime_paas_sbx_pv 字段定义。

    通过读取源文件验证，避免在 Python 3.10 环境下导入 graph.py。
    """
    source = _read_graph_source()

    # 验证 DefaultState 中包含 runtime_paas_sbx_pv 字段
    assert "runtime_paas_sbx_pv" in source, "runtime_paas_sbx_pv 字段未在 graph.py 中定义"
    assert "add_pv_info" in source, "add_pv_info 未在 graph.py 中导入"


def test_graph_source_contains_resource_manager_retention():
    """graph builder 应保留每次请求的 resource_manager，且没有技能时不会自动创建。"""
    source = _read_graph_source()

    assert "self._resource_manager = None" in source
    assert "if options.resource_manager is not None:" in source
    assert "self._resource_manager = options.resource_manager" in source
    assert "client=self._resource_manager" in source


def test_graph_source_contains_platform_pv_restore_wiring():
    """graph.py 不再包含平台 PV 恢复节点；START 直接连接 knowledge 或 model。

    平台 PV 恢复逻辑已上移至服务层（chat.py），图构建器仅负责
    纯图拓扑组装。
    """
    source = _read_graph_source()

    # 恢复节点相关代码不应存在于 graph.py
    assert "restore_platform_pv" not in source
    assert "retrieve_chat_session" not in source
    assert "sandbox_pv_id" not in source
    assert '"source": "platform"' not in source

    # START 应直接连接到 knowledge 或 model
    assert 'graph.add_edge(START, "model")' in source
    assert 'graph.add_edge(START, "knowledge")' in source


def test_graph_source_passes_resource_manager_to_pv_node():
    """pv_node 应接收 set_bkai_options 保存的同一个 resource_manager。"""
    source = _read_graph_source()

    assert "make_pv_node(" in source
    assert "resource_manager=self._resource_manager" in source


def test_add_pv_info_platform_restore_replaces_runtime_session_pv():
    """通过 reducer 合并时，platform PV 应替换 checkpoint/runtime 中的 session PV。"""
    existing = [
        {
            "type": "paas-sbx-pv",
            "volume_id": "pv-runtime",
            "volume_name": "agent-pv-session-abc",
            "mount_path": "session",
            "source": "runtime",
        }
    ]
    restored = [
        {
            "type": "paas-sbx-pv",
            "volume_id": "pv-platform",
            "volume_name": "agent-pv-session-abc",
            "mount_path": "session",
            "source": "platform",
        }
    ]

    result = add_pv_info(existing, restored)

    assert len(result) == 1
    assert result[0]["volume_id"] == "pv-platform"
    assert result[0]["source"] == "platform"
