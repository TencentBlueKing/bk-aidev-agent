"""Agent SSE 到企微长连接 stream 帧的纯内存转换。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generator

from ag_ui.core.events import EventType
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_bkplugin.services.agent_helpers import AgentHelper

from .context import CHUNK_FLUSH_THRESHOLD, _escape_markdown_text, _normalize_url
from .formatters import _node_display, _task_state_label, format_task_outputs
from .stream import iter_sse_lines


@dataclass(frozen=True, slots=True)
class DirectStreamFrame:
    """企微长连接待发送的累计快照。"""

    content: str
    finish: bool
    failed: bool = False
    observed_at: float = field(default_factory=time.monotonic)


@dataclass(frozen=True, slots=True)
class AgentStream:
    """Chat/Flow 对长连接暴露的统一原始流。"""

    kind: str
    generator: Generator
    session_code: str
    is_stream: bool = True


def iter_direct_stream_frames(
    agent_stream: AgentStream,
    stream_id: str,
    on_run_started=None,
) -> Generator[DirectStreamFrame, None, None]:
    """把 Chat/Flow SSE 统一转换为企微累计 stream 帧。"""
    if not agent_stream.is_stream:
        result = agent_stream.generator
        content = ""
        if isinstance(result, dict):
            choices = result.get("choices") or [{}]
            content = (choices[0].get("delta") or {}).get("content", "") or ""
        yield DirectStreamFrame(content=content or "未获取到回答内容", finish=True)
        return

    if agent_stream.kind == "flow":
        yield from _iter_flow_frames(agent_stream, stream_id, on_run_started)
        return
    yield from _iter_chat_frames(agent_stream, stream_id, on_run_started)


def _iter_chat_frames(agent_stream: AgentStream, stream_id: str, on_run_started) -> Generator[DirectStreamFrame]:
    content = ""
    thinking = ""
    documents: list[dict] = []
    finished = False
    pending_chars = 0

    for event in iter_sse_lines(agent_stream.generator, stream_id):
        event_type = event.get("type", "")
        if event_type == EventType.RUN_STARTED and on_run_started:
            on_run_started(str(event.get("run_id", "")))
        elif event_type == EventType.THINKING_TEXT_MESSAGE_CONTENT:
            delta = event.get("delta", "")
            if delta and delta != "正在思考...":
                thinking += delta
                pending_chars += len(delta)
                if pending_chars >= CHUNK_FLUSH_THRESHOLD:
                    yield DirectStreamFrame(content=_render_chat(thinking, content), finish=False)
                    pending_chars = 0
        elif event_type == EventType.TEXT_MESSAGE_CONTENT:
            delta = event.get("delta", "")
            if delta and delta != "正在思考...":
                content += delta
                pending_chars += len(delta)
                if pending_chars >= CHUNK_FLUSH_THRESHOLD:
                    yield DirectStreamFrame(content=_render_chat(thinking, content), finish=False)
                    pending_chars = 0
        elif event_type == EventType.CUSTOM:
            for document in event.get("documents", []):
                if isinstance(document, dict) and isinstance(document.get("metadata"), dict):
                    documents.append(document["metadata"])
        elif event_type == EventType.RUN_ERROR:
            message = event.get("message", event)
            yield DirectStreamFrame(content=f"处理请求时发生错误: {message}", finish=True, failed=True)
            finished = True
            break
        elif event_type == EventType.RUN_FINISHED:
            yield DirectStreamFrame(
                content=_render_chat(thinking, content) + _format_documents(documents),
                finish=True,
            )
            finished = True
            break

    if not finished:
        partial = _render_chat(thinking, content) + _format_documents(documents)
        yield DirectStreamFrame(
            content=f"{partial}\n\n回答生成提前结束，请重试" if partial else "回答生成提前结束，请重试",
            finish=True,
            failed=True,
        )


@dataclass(slots=True)
class _FlowState:
    task_id: str = ""
    nodes_initialized: bool = False
    nodes: dict = field(default_factory=dict)
    last_task_state: str = ""
    thinking: str = ""
    content: str = ""


def _iter_flow_frames(agent_stream: AgentStream, stream_id: str, on_run_started) -> Generator[DirectStreamFrame]:
    state = _FlowState()
    finished = False

    for event in iter_sse_lines(agent_stream.generator, stream_id):
        event_type = event.get("type", "")
        if event_type == EventType.RUN_STARTED and on_run_started:
            on_run_started(str(event.get("run_id", "")))
        elif event_type == EventType.CUSTOM:
            frame = _format_flow_event(event.get("name", ""), event.get("value"), state, agent_stream.session_code)
            if frame:
                yield frame
                if frame.finish:
                    finished = True
                    break
        elif event_type == EventType.RUN_ERROR:
            yield DirectStreamFrame(
                content=f"流程执行出错: {event.get('message', '未知错误')}",
                finish=True,
                failed=True,
            )
            finished = True
            break
        elif event_type == EventType.RUN_FINISHED:
            yield DirectStreamFrame(content=_render_flow(state), finish=True)
            finished = True
            break

    if not finished:
        partial = _render_flow(state)
        yield DirectStreamFrame(
            content=f"{partial}\n\n流程响应提前结束，请重试" if partial else "流程响应提前结束，请重试",
            finish=True,
            failed=True,
        )


def _format_flow_event(event_name: str, raw_value, state: _FlowState, session_code: str) -> DirectStreamFrame | None:
    value = raw_value or {}
    if isinstance(value, list):
        value = value[0] if value else {}

    if event_name == CustomMessageType.FLOW_AGENT_START.value:
        state.task_id = value.get("task_id", "未知")
        state.nodes_initialized = False
        return None

    if event_name == CustomMessageType.FLOW_AGENT_RESULT.value:
        task_state = value.get("task_state", value.get("state", ""))
        nodes = value.get("nodes") or {}
        if nodes:
            state.nodes = nodes
        if task_state:
            state.last_task_state = task_state
        if not state.nodes_initialized:
            task_id = state.task_id or value.get("task_id", "未知")
            lines = [f"流程任务已启动 (任务ID: {task_id})"]
            names = [node.get("name", "") for node in nodes.values() if isinstance(node, dict) and node.get("name")]
            if names:
                lines.append(f"共包含{len(names)}个节点：")
                lines.extend(f"- {name}" for name in names)
            state.thinking = "\n".join(lines) + "\n\n"
            state.nodes_initialized = True
        return DirectStreamFrame(content=_render_flow(state), finish=False)

    if event_name != CustomMessageType.FLOW_AGENT_END.value:
        return None

    task_id = value.get("task_id") or state.task_id
    task_state = value.get("state", "") or state.last_task_state
    task_state_cn = _task_state_label(task_state)
    lines = [f"流程任务执行{task_state_cn} (任务ID: {task_id})"]
    node_lines = []
    for node in state.nodes.values() if isinstance(state.nodes, dict) else []:
        if not isinstance(node, dict):
            continue
        name = node.get("name", "")
        label, icon = _node_display(node.get("state", "PENDING"))
        elapsed = node.get("elapsed_time", 0)
        node_lines.append(f"- {icon} {name}: {label}{f' ({elapsed}s)' if elapsed else ''}")
    if node_lines:
        lines.append(f"\n共{len(node_lines)}个节点：")
        lines.extend(node_lines)
    state.thinking = "\n".join(lines) + "\n"

    if value.get("error", False):
        state.content = f"流程任务执行{task_state_cn}\n任务ID: {task_id}"
    else:
        outputs = format_task_outputs(value.get("task_outputs", {}))
        state.content = f"流程任务执行完成\n任务ID: {task_id}"
        if outputs:
            state.content += f"\n\n执行结果:\n{outputs}"
    if session_code:
        detail_url = AgentHelper.build_session_detail_url(session_code)
        if detail_url:
            state.content += f"\n\n[查看详情]({detail_url})"
    return DirectStreamFrame(
        content=_render_flow(state),
        finish=True,
        failed=bool(value.get("error", False)),
    )


def _render_chat(thinking: str, content: str) -> str:
    return f"<think>{thinking}</think>{content}" if thinking else content


def _render_flow(state: _FlowState) -> str:
    return _render_chat(state.thinking, state.content)


def _format_documents(documents: list[dict]) -> str:
    if not documents:
        return ""
    lines = ["\n当前回答参考的文档如下:"]
    for index, document in enumerate(documents):
        display_name = _escape_markdown_text(str(document.get("display_name", "")))
        path = _normalize_url(str(document.get("path", "")))
        lines.append(f"[{index + 1}][{display_name}]({path})")
    return "\n".join(lines) + "\n"
