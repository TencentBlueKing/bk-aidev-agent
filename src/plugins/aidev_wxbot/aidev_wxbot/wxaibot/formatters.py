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


def format_flow_progress(task_id: str, task_state: str, nodes) -> str:
    """渲染任务级状态 + 节点级进度。

    长连接与 HTTP 轮询共用这一份渲染：每收到一次 result / update 就整体重绘，
    而不是只在首帧写一次，否则节点状态在任务结束前不会变化。
    """
    label = _task_state_label(task_state)
    # 执行中的中文标签本身就以「执行」开头，再拼一次会变成「执行执行中」。
    headline = f"流程任务{label}" if label.startswith("执行") else f"流程任务执行{label}"
    lines = [f"{headline} (任务ID: {task_id or '未知'})"]
    node_lines: list[str] = []
    for node in nodes.values() if isinstance(nodes, dict) else []:
        if not isinstance(node, dict):
            continue
        label, icon = _node_display(node.get("state", "PENDING"))
        elapsed = node.get("elapsed_time", 0)
        node_lines.append(f"- {icon} {node.get('name', '')}: {label}{f' ({elapsed}s)' if elapsed else ''}")
    if node_lines:
        lines.append(f"\n共{len(node_lines)}个节点：")
        lines.extend(node_lines)
    return "\n".join(lines) + "\n"


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
    - flow_agent_start / flow_agent_restart → think_content（任务启动信息）
    - flow_agent_result / flow_agent_update → think_content（轮询中间状态，重绘节点进度）
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
    """任务启动时保存 task_id，节点进度在每次 result 时重绘。"""
    task_id = value.get("task_id") or llm_chunk._flow_task_id or "未知"
    llm_chunk._flow_task_id = task_id
    logger.debug(f"stream_id:{llm_chunk.stream_id} flow_agent_start: task_id={task_id}")


def _on_flow_result(value: dict, llm_chunk: LlmChunkMsg, rabbitmq_client: RabbitMQClient) -> None:
    """轮询中间状态：每次都按最新 nodes 重绘节点进度。

    同时缓存 nodes 和 task_state 到 llm_chunk，
    供 _on_flow_end 使用（因为 flow_agent_end 事件本身不携带这些字段）。
    """
    task_state = value.get("task_state", value.get("state", ""))
    stream_id = llm_chunk.stream_id

    # 获取并缓存 nodes，供 _on_flow_end 展示最终状态使用
    nodes = value.get("nodes") or {}
    if nodes:
        llm_chunk._flow_nodes_cache = nodes
    if task_state:
        llm_chunk._flow_last_task_state = task_state
    if value.get("task_id"):
        llm_chunk._flow_task_id = value["task_id"]

    llm_chunk.think_content = format_flow_progress(
        llm_chunk._flow_task_id,
        llm_chunk._flow_last_task_state,
        llm_chunk._flow_nodes_cache,
    )

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
    llm_chunk.think_content = format_flow_progress(task_id, task_state, llm_chunk._flow_nodes_cache)

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
