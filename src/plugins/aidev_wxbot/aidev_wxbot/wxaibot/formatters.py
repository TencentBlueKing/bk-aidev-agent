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
    icon = _NODE_STATE_ICONS.get(label, "⏸")
    return label, icon


def _task_state_label(state: str) -> str:
    """将任务原始状态转换为中文标签。"""
    return _TASK_STATE_LABELS.get(state, state)


def handle_flow_custom_event(
    event_name: str,
    chunk_json: dict,
    llm_chunk: LlmChunkMsg,
    rabbitmq_client: RabbitMQClient,
) -> None:
    """
    分发 Flow Agent 的 CUSTOM 事件到具体处理函数。
    事件分发：
    - flow_agent_start  → think_content（任务启动信息）
    - flow_agent_result → think_content（轮询中间状态，追加节点进度）
    - flow_agent_end    → content（最终执行结果）
    """
    value = chunk_json.get("value") or {}

    if event_name == CustomMessageType.FLOW_AGENT_START.value:
        _on_flow_start(value, llm_chunk, rabbitmq_client)
    elif event_name == CustomMessageType.FLOW_AGENT_RESULT.value:
        _on_flow_result(value, llm_chunk, rabbitmq_client)
    elif event_name == CustomMessageType.FLOW_AGENT_END.value:
        _on_flow_end(value, llm_chunk, rabbitmq_client)
    else:
        logger.debug(f"stream_id:{llm_chunk.stream_id} 未处理的 flow custom event: {event_name}")


def _on_flow_start(value: dict, llm_chunk: LlmChunkMsg, rabbitmq_client: RabbitMQClient) -> None:
    """任务启动信息写入思考内容，并记录前缀长度供 result 覆盖用。"""
    task_id = value.get("task_id", "未知")
    llm_chunk.think_content += f"流程任务已启动 (任务ID: {task_id})\n执行中，请稍候...\n\n"
    # 记录 start 阶段的 think_content 长度，后续 result 从此位置覆盖
    llm_chunk._flow_start_prefix_len = len(llm_chunk.think_content)
    llm_chunk.append_to_cache(rabbitmq_client)
    logger.info(f"stream_id:{llm_chunk.stream_id} flow_agent_start: task_id={task_id}")


def _on_flow_result(value: dict, llm_chunk: LlmChunkMsg, rabbitmq_client: RabbitMQClient) -> None:
    """轮询中间状态：覆盖式刷新节点进度（不累积历史，只保留最新快照）。"""
    task_state = value.get("task_state", value.get("state", ""))
    task_state_cn = _task_state_label(task_state)
    statistics = value.get("statistics") or {}

    # 统计摘要：成功 N / 总数 M
    total = statistics.get("total", 0)
    state_counts = statistics.get("state_counts") or {}
    finished_count = state_counts.get("FINISHED", 0)
    summary_parts: list[str] = []
    if finished_count:
        summary_parts.append(f"成功: {finished_count}")
    running_count = state_counts.get("RUNNING", 0)
    if running_count:
        summary_parts.append(f"执行中: {running_count}")
    pending_count = total - finished_count - running_count - state_counts.get("FAILED", 0)
    if pending_count > 0:
        summary_parts.append(f"待执行: {pending_count}")
    failed_count = state_counts.get("FAILED", 0) + state_counts.get("REVOKED", 0)
    if failed_count:
        summary_parts.append(f"失败: {failed_count}")
    summary_str = "  ".join(summary_parts) if summary_parts else ""

    lines: list[str] = [f"--- 执行情况: {task_state_cn} ---"]
    if summary_str:
        lines.append(summary_str)

    # 节点详情
    nodes = value.get("nodes") or {}
    if isinstance(nodes, dict):
        for node_info in nodes.values():
            if not isinstance(node_info, dict):
                continue
            name = node_info.get("name", "")
            state = node_info.get("state", "PENDING")
            elapsed = node_info.get("elapsed_time", 0)
            label, icon = _node_display(state)
            time_str = f" (耗时 {elapsed}s)" if elapsed else ""
            lines.append(f"  {icon} {name}: {label}{time_str}")

    snapshot = "\n".join(lines) + "\n"

    # 覆盖式刷新：保留 start 前缀 + 最新轮询快照
    prefix_len = getattr(llm_chunk, "_flow_start_prefix_len", 0)
    llm_chunk.think_content = llm_chunk.think_content[:prefix_len] + snapshot
    llm_chunk.append_to_cache(rabbitmq_client)
    logger.debug(f"stream_id:{llm_chunk.stream_id} flow_agent_result: state={task_state}")


def _on_flow_end(value: dict, llm_chunk: LlmChunkMsg, rabbitmq_client: RabbitMQClient) -> None:
    """最终结果写入正式内容（content），思考内容追加结束标记。"""
    task_id = value.get("task_id", "")
    is_error = value.get("error", False)
    task_state = value.get("state", "")
    task_state_cn = _task_state_label(task_state)
    task_outputs = value.get("task_outputs", {})

    # 思考内容：结束标记
    llm_chunk.think_content += f"[完成] 任务 {task_id} 执行{task_state_cn}\n"

    # 正式内容
    if is_error:
        llm_chunk.content = f"流程任务执行{task_state_cn}\n任务ID: {task_id}"
    else:
        outputs_text = format_task_outputs(task_outputs)
        llm_chunk.content = f"流程任务执行完成\n任务ID: {task_id}"
        if outputs_text:
            llm_chunk.content += f"\n\n执行结果:\n{outputs_text}"

    llm_chunk.is_finish = True
    llm_chunk.append_to_cache(rabbitmq_client)
    logger.info(f"stream_id:{llm_chunk.stream_id} flow_agent_end: task_id={task_id}, error={is_error}")


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
