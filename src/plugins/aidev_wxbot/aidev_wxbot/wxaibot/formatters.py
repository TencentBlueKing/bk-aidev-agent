# -*- coding: utf-8 -*-
"""
Flow Agent 事件格式化。
将 Flow Agent 的结构化 SSE 事件（start / result / end）
格式化为企微渠道可读的文本，写入 LlmChunkMsg。
展示策略：执行过程 → think_content（折叠），最终结果 → content（正文）。
"""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_bkplugin.services.agent_helpers import AgentHelper

from .context import LlmChunkMsg

if TYPE_CHECKING:
    from ..utils.rabbitmq import RabbitMQClient

logger = getLogger(__name__)

# ---------------------------------------------------------------------------
# BKFlow 状态收敛：原始状态 → 中文展示名 + 图标
# ---------------------------------------------------------------------------

# 任务级状态 → 中文
_TASK_STATE_LABELS: dict[str, str] = {
    "CREATED": "执行中",
    "LOOP_READY": "执行中",
    "READY": "执行中",
    "RUNNING": "执行中",
    "SUSPENDED": "挂起",
    "BLOCKED": "执行中",
    "FINISHED": "成功",
    "FAILED": "失败",
    "REVOKED": "终止",
    "ROLLING_BACK": "执行中",
    "ROLL_BACK_SUCCESS": "执行中",
    "ROLL_BACK_FAILED": "失败",
}

# 节点级状态 → 中文（收敛后只有 4 种 + 待执行）
_NODE_STATE_LABELS: dict[str, str] = {
    "FINISHED": "成功",
    "RUNNING": "执行中",
    "FAILED": "失败",
    "REVOKED": "失败",
    "SUSPENDED": "挂起",
    "NODE_SUSPENDED": "挂起",
    "PENDING": "待执行",
    "READY": "执行中",
    "BLOCKED": "执行中",
    "CREATED": "执行中",
}

# 节点级状态 → 图标（圈圈风格）
_NODE_STATE_ICONS: dict[str, str] = {
    "成功": "🟢",
    "执行中": "🔄",
    "失败": "🔴",
    "挂起": "⚪",
    "待执行": "⚪",
}


def _node_display(state: str) -> tuple[str, str]:
    """将节点原始状态转换为 (中文标签, 图标)。"""
    label = _NODE_STATE_LABELS.get(state, "待执行")
    icon = _NODE_STATE_ICONS.get(label, "⚪")
    return label, icon


def _task_state_label(state: str) -> str:
    """将任务原始状态转换为中文标签。"""
    return _TASK_STATE_LABELS.get(state, state)


def handle_flow_custom_event(
    event_name: str,
    chunk_json: dict,
    llm_chunk: LlmChunkMsg,
    rabbitmq_client: RabbitMQClient,
    session_code: str = "",
) -> None:
    """
    分发 Flow Agent 的 CUSTOM 事件到具体处理函数。
    事件分发：
    - flow_agent_start / restart → 缓存 task_id
    - flow_agent_result / update → think_content（节点名称列表）
    - flow_agent_end    → content（最终执行结果 + 小鲸跳转链接）
    """
    value = chunk_json.get("value") or {}

    # 适配数组格式：value 为 list 时取第一个元素
    if isinstance(value, list):
        value = value[0] if value else {}

    if event_name in {CustomMessageType.FLOW_AGENT_START.value, CustomMessageType.FLOW_AGENT_RESTART.value}:
        _on_flow_start(value, llm_chunk, rabbitmq_client)
    elif event_name in {CustomMessageType.FLOW_AGENT_RESULT.value, CustomMessageType.FLOW_AGENT_UPDATE.value}:
        _on_flow_result(value, llm_chunk, rabbitmq_client)
    elif event_name == CustomMessageType.FLOW_AGENT_END.value:
        _on_flow_end(value, llm_chunk, rabbitmq_client, session_code=session_code)
    else:
        logger.debug(f"stream_id:{llm_chunk.stream_id} 未处理的 flow custom event: {event_name}")


def _on_flow_start(value: dict, llm_chunk: LlmChunkMsg, rabbitmq_client: RabbitMQClient) -> None:
    """任务启动时保存 task_id，节点列表在第一次 result 时展示。"""
    task_id = value.get("task_id", "未知")
    llm_chunk._flow_task_id = task_id
    llm_chunk._flow_nodes_initialized = False
    logger.debug(f"stream_id:{llm_chunk.stream_id} flow_agent_start: task_id={task_id}")


def _on_flow_result(value: dict, llm_chunk: LlmChunkMsg, rabbitmq_client: RabbitMQClient) -> None:
    """轮询中间状态：第一次收到时展示节点列表（无状态），后续保持内容供轮询。

    每次轮询都缓存最新的 nodes 和 task_state 到 llm_chunk，
    供 _on_flow_end 使用（因为 flow_agent_end 事件本身不携带这些字段）。
    """
    task_state = value.get("task_state", value.get("state", ""))
    stream_id = llm_chunk.stream_id

    # 获取并缓存 nodes，供 _on_flow_end 展示最终状态及首次展示节点列表使用
    nodes = value.get("nodes") or {}
    if nodes:
        llm_chunk._flow_nodes_cache = nodes
    if task_state:
        llm_chunk._flow_last_task_state = task_state

    # 第一次收到 result 时，展示节点列表（无状态）
    if not llm_chunk._flow_nodes_initialized:
        task_id = llm_chunk._flow_task_id or value.get("task_id", "未知")

        logger.debug(f"[WxBotFlow] stream_id:{stream_id} 第一次result, task_id={task_id}, nodes_count={len(nodes)}")

        lines: list[str] = [f"流程任务已启动 (任务ID: {task_id})"]

        # 收集节点名称列表
        node_names: list[str] = []
        if isinstance(nodes, dict):
            for node_info in nodes.values():
                if isinstance(node_info, dict):
                    name = node_info.get("name", "")
                    if name:
                        node_names.append(name)

        if node_names:
            lines.append(f"共包含{len(node_names)}个节点：")
            for name in node_names:
                lines.append(f"- {name}")

        llm_chunk.think_content += "\n".join(lines) + "\n\n"
        llm_chunk._flow_nodes_initialized = True
        logger.debug(f"[WxBotFlow] stream_id:{stream_id} 已写入think_content, len={len(llm_chunk.think_content)}")

    # 每次都调用 append_to_cache，确保企微轮询时能获取到内容
    llm_chunk.append_to_cache(rabbitmq_client)
    logger.debug(f"[WxBotFlow] stream_id:{stream_id} result状态: {task_state}")


def _on_flow_end(
    value: dict,
    llm_chunk: LlmChunkMsg,
    rabbitmq_client: RabbitMQClient,
    session_code: str = "",
) -> None:
    """最终结果写入正式内容，思考内容更新为带状态的节点列表，附带小鲸跳转链接。

    nodes 和 task_state 从 llm_chunk 缓存获取（由 _on_flow_result 轮询时缓存），
    不依赖 flow_agent_end 事件携带这些字段，避免修改 agent 层通用协议。
    """
    task_id = value.get("task_id") or llm_chunk._flow_task_id
    is_error = value.get("error", False)
    # 优先使用 event 中的 state（失败时 agent 会携带），否则用轮询缓存的最新状态
    task_state = value.get("state", "") or llm_chunk._flow_last_task_state
    task_state_cn = _task_state_label(task_state)
    task_outputs = value.get("task_outputs", {})
    # nodes 从轮询缓存获取（flow_agent_end 事件不携带 nodes）
    nodes = llm_chunk._flow_nodes_cache

    # 思考内容：节点执行状态列表
    lines: list[str] = [f"流程任务执行{task_state_cn} (任务ID: {task_id})"]

    # 节点详情
    if isinstance(nodes, dict):
        node_items = []
        for node_info in nodes.values():
            if not isinstance(node_info, dict):
                continue
            name = node_info.get("name", "")
            state = node_info.get("state", "PENDING")
            elapsed = node_info.get("elapsed_time", 0)
            label, icon = _node_display(state)
            time_str = f" ({elapsed}s)" if elapsed else ""
            node_items.append((name, f"{icon} {name}: {label}{time_str}"))

        if node_items:
            lines.append(f"\n共{len(node_items)}个节点：")
            for _, display in node_items:
                lines.append(f"- {display}")

    llm_chunk.think_content = "\n".join(lines) + "\n"

    # 正式内容
    if is_error:
        llm_chunk.content = f"流程任务执行{task_state_cn}\n任务ID: {task_id}"
    else:
        outputs_text = format_task_outputs(task_outputs)
        llm_chunk.content = f"流程任务执行完成\n任务ID: {task_id}"
        if outputs_text:
            llm_chunk.content += f"\n\n执行结果:\n{outputs_text}"

    # 拼接小鲸跳转链接
    if session_code:
        detail_url = AgentHelper.build_session_detail_url(session_code)
        if detail_url:
            llm_chunk.content += f"\n\n[查看详情]({detail_url})"

    llm_chunk.is_finish = True
    llm_chunk.append_to_cache(rabbitmq_client)
    logger.info(f"stream_id:{llm_chunk.stream_id} flow_agent_end: task_id={task_id}, state={task_state_cn}")


def format_task_outputs(task_outputs: list | dict | str | None) -> str:
    """将 task_outputs 格式化为可读文本。兼容 list[dict] / dict / str。"""
    if not task_outputs:
        return ""

    parts: list[str] = []
    if isinstance(task_outputs, list):
        for item in task_outputs:
            if isinstance(item, dict):
                key = item.get("key", "")
                val = item.get("value", "")
                parts.append(f"- {key}: {val}" if key else f"- {val}")
            else:
                parts.append(f"- {item}")
    elif isinstance(task_outputs, dict):
        for key, val in task_outputs.items():
            parts.append(f"- {key}: {val}")
    else:
        parts.append(str(task_outputs))
    return "\n".join(parts)
