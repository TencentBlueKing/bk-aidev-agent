"""Agent SSE 到企微长连接 stream 帧的纯内存转换。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generator

from ag_ui.core.events import EventType
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_bkplugin.services.agent_helpers import AgentHelper

from .approval_cards import build_pending_approval_card
from .constants import STREAM_ERROR_REPLY
from .context import CHUNK_FLUSH_THRESHOLD, _escape_markdown_text, _normalize_url
from .flow_cards import build_flow_action_card
from .formatters import _task_state_label, format_flow_progress, format_task_outputs
from .question_cards import build_pending_question_card, pending_question, question_prompt
from .stream import iter_sse_lines
from .tool_blocks import ChatSegments, is_tool_event
from .tracing import wxbot_span


@dataclass(frozen=True, slots=True)
class DirectStreamFrame:
    """企微长连接待发送的累计快照。"""

    content: str
    finish: bool
    failed: bool = False
    pending_approval: bool = False
    pending_question: bool = False
    template_card: dict | None = None
    observed_at: float = field(default_factory=time.monotonic)


@dataclass(frozen=True, slots=True)
class AgentStream:
    """Chat/Flow 对长连接暴露的统一原始流。"""

    kind: str
    generator: Generator
    session_code: str
    is_stream: bool = True
    resume_interrupt_id: str = ""


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


def _run_id_of(event: dict) -> str:
    """取 RUN_STARTED 的 run id。

    AG-UI 的 SSE 按 camelCase 别名序列化，字段是 runId；只读 run_id 会永远取到空，
    导致后续取消退化成 session 级信号，把同会话的下一轮一起毒死。
    """
    return str(event.get("runId") or event.get("run_id") or "")


def _iter_chat_frames(agent_stream: AgentStream, stream_id: str, on_run_started) -> Generator[DirectStreamFrame]:
    segments = ChatSegments(stream_id)
    thinking = ""
    documents: list[dict] = []
    finished = False
    pending_chars = 0
    run_started = False

    for event in iter_sse_lines(agent_stream.generator, stream_id):
        if finished:
            continue
        event_type = event.get("type", "")
        if event_type == EventType.RUN_STARTED:
            run_started = True
        if not run_started and event_type == EventType.RUN_FINISHED and agent_stream.resume_interrupt_id:
            outcome = event.get("outcome") or {}
            if outcome.get("type") == "success" and any(
                isinstance(item, dict) and item.get("id") == agent_stream.resume_interrupt_id
                for item in outcome.get("interrupts") or []
            ):
                # SDK replays the resolved interrupt BEFORE the resumed RUN_STARTED.
                # This is not completion of the new run and contains no new answer.
                continue
        if event_type == EventType.RUN_STARTED and on_run_started:
            on_run_started(_run_id_of(event))
        elif is_tool_event(event_type):
            # 工具状态变化要立刻推给用户：卡住时至少看得到卡在哪个工具上
            if segments.apply_tool_event(event_type, event):
                yield DirectStreamFrame(content=_render_chat(thinking, segments.render()), finish=False)
                pending_chars = 0
        elif event_type == EventType.THINKING_TEXT_MESSAGE_CONTENT:
            delta = event.get("delta", "")
            if delta and delta != "正在思考...":
                thinking += delta
                pending_chars += len(delta)
                if pending_chars >= CHUNK_FLUSH_THRESHOLD:
                    yield DirectStreamFrame(content=_render_chat(thinking, segments.render()), finish=False)
                    pending_chars = 0
        elif event_type == EventType.TEXT_MESSAGE_CONTENT:
            delta = event.get("delta", "")
            if delta and delta != "正在思考...":
                segments.append_text(delta)
                pending_chars += len(delta)
                if pending_chars >= CHUNK_FLUSH_THRESHOLD:
                    yield DirectStreamFrame(content=_render_chat(thinking, segments.render()), finish=False)
                    pending_chars = 0
        elif event_type == EventType.CUSTOM:
            for document in event.get("documents", []):
                if isinstance(document, dict) and isinstance(document.get("metadata"), dict):
                    documents.append(document["metadata"])
        elif event_type == EventType.RUN_ERROR:
            yield DirectStreamFrame(content=STREAM_ERROR_REPLY, finish=True, failed=True)
            finished = True
        elif event_type == EventType.RUN_FINISHED:
            with wxbot_span("wxbot.approval_card.build") as span:
                approval_card = build_pending_approval_card(event, agent_stream.session_code)
                question_card = build_pending_question_card(event, agent_stream.session_code)
                question = pending_question(event)
                span.set_attribute("wxbot.approval.pending", approval_card is not None)
            if approval_card or question:
                current_content = _render_chat(thinking, segments.render())
                if question:
                    prompt = question_prompt(question, has_card=question_card is not None)
                    current_content = "\n\n".join(filter(None, [current_content, prompt]))
                yield DirectStreamFrame(
                    content=current_content or ("等待工具审批" if approval_card else "请回答卡片中的问题"),
                    finish=True,
                    pending_approval=approval_card is not None,
                    pending_question=question is not None,
                    template_card=approval_card or question_card,
                )
                finished = True
                continue
            yield DirectStreamFrame(
                content=_render_chat(thinking, segments.render()) + _format_documents(documents),
                finish=True,
            )
            finished = True

    if not finished:
        partial = _render_chat(thinking, segments.render()) + _format_documents(documents)
        yield DirectStreamFrame(
            content=f"{partial}\n\n回答生成提前结束，请重试" if partial else "回答生成提前结束，请重试",
            finish=True,
            failed=True,
        )


@dataclass(slots=True)
class _FlowState:
    task_id: str = ""
    nodes: dict = field(default_factory=dict)
    last_task_state: str = ""
    thinking: str = ""
    content: str = ""


def _iter_flow_frames(agent_stream: AgentStream, stream_id: str, on_run_started) -> Generator[DirectStreamFrame]:
    state = _FlowState()
    finished = False
    # BKFlow 默认 0.5s 轮询一次，进度没变化时不必再向企微重发一模一样的内容。
    last_content = ""

    for event in iter_sse_lines(agent_stream.generator, stream_id):
        if finished:
            continue
        event_type = event.get("type", "")
        if event_type == EventType.RUN_STARTED and on_run_started:
            on_run_started(_run_id_of(event))
        elif event_type == EventType.CUSTOM:
            frame = _format_flow_event(event.get("name", ""), event.get("value"), state, agent_stream.session_code)
            if frame and (frame.finish or frame.content != last_content):
                last_content = frame.content
                yield frame
                if frame.finish:
                    finished = True
        elif event_type == EventType.RUN_ERROR:
            yield DirectStreamFrame(content=STREAM_ERROR_REPLY, finish=True, failed=True)
            finished = True
        elif event_type == EventType.RUN_FINISHED:
            yield DirectStreamFrame(content=_render_flow(state), finish=True)
            finished = True

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

    if event_name in {
        CustomMessageType.FLOW_AGENT_START.value,
        CustomMessageType.FLOW_AGENT_RESTART.value,
    }:
        # 不在这里塞「未知」占位：task_id 还要决定能否发重试/跳过卡片，展示兜底交给渲染层。
        state.task_id = value.get("task_id") or state.task_id
        return None

    if event_name in {CustomMessageType.FLOW_AGENT_RESULT.value, CustomMessageType.FLOW_AGENT_UPDATE.value}:
        task_state = value.get("task_state", value.get("state", ""))
        nodes = value.get("nodes") or {}
        if nodes:
            state.nodes = nodes
        if task_state:
            state.last_task_state = task_state
        if value.get("task_id"):
            state.task_id = value["task_id"]
        state.thinking = format_flow_progress(state.task_id, state.last_task_state, state.nodes)
        return DirectStreamFrame(content=_render_flow(state), finish=False)

    if event_name != CustomMessageType.FLOW_AGENT_END.value:
        return None

    task_id = value.get("task_id") or state.task_id
    task_state = value.get("state", "") or state.last_task_state
    task_state_cn = _task_state_label(task_state)
    state.thinking = format_flow_progress(task_id, task_state, state.nodes)

    is_error = bool(value.get("error", False))
    if is_error:
        state.content = f"流程任务执行{task_state_cn}\n任务ID: {task_id or '未知'}"
    else:
        outputs = format_task_outputs(value.get("task_outputs", {}))
        state.content = f"流程任务执行完成\n任务ID: {task_id or '未知'}"
        if outputs:
            state.content += f"\n\n执行结果:\n{outputs}"
    if session_code:
        detail_url = AgentHelper.build_session_detail_url(session_code)
        if detail_url:
            state.content += f"\n\n[查看详情]({detail_url})"
    card = None
    if is_error and session_code:
        card = build_flow_action_card(session_code=session_code, task_id=task_id, nodes=state.nodes)
    return DirectStreamFrame(content=_render_flow(state), finish=True, failed=is_error, template_card=card)


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
