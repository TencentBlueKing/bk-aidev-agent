# -*- coding: utf-8 -*-
"""只读回答流：把一次插件执行的 Agent 回答（思考过程、正文），从消息队列只读回放为 SSE。

供标准运维（SOPS）等调用方在节点详情中流式显示插件回答；接口见 ``aidev_bkplugin.views.answer_stream``。

执行结束后队列已清理，改从会话记录（AIDev session_content，小鲸刷新后显示历史用的同一份数据）
按 ``turn_id`` 取出本次执行的思考过程，以同样的 AG-UI 事件返回，供页面在执行结束后继续显示。

本模块不依赖 Django，便于单测。

关联链：BPF ``Schedule.trace_id`` → ``Schedule.data.context.storage.session_code``
→ 消息队列 ``thread_id``（chat Agent 的 ``thread_id == session_code``）。

只读约束：只调用消息队列的 ``has_pending_messages`` / ``get_messages_since``；
不登记消费者、不 ``mark_completed`` / ``clear`` / 取消，不写会话或 Schedule。
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

# BPF State：EMPTY=1 POLL=2 CALLBACK=3 SUCCESS=4 FAIL=5
STATE_POLL = 2
TERMINAL_STATES = frozenset({4, 5})

# aidev_agent.services.messages_handler.constants.StreamMarkers
EOD_MARKER = "<END_OF_STREAM>"
CANCELLED_MARKER = "<CANCELLED>"
STOPPED_MARKER = "<STOPPED>"
END_MARKERS = frozenset({EOD_MARKER, CANCELLED_MARKER, STOPPED_MARKER})

# 默认转发的 AG-UI 事件：正文和思考过程。原样转发，前端用小鲸的消息组件渲染
DEFAULT_EVENT_TYPES = frozenset(
    {
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_CHUNK",
        "TEXT_MESSAGE_END",
        "THINKING_START",
        "THINKING_TEXT_MESSAGE_START",
        "THINKING_TEXT_MESSAGE_CONTENT",
        "THINKING_TEXT_MESSAGE_END",
        "THINKING_END",
    }
)
RUN_STARTED = "RUN_STARTED"
CHAT_AGENT_TYPE = "chat"


class TargetNotFound(Exception):
    """找不到 trace_id 对应的执行。"""


class StreamUnsupported(Exception):
    """执行存在，但不能提供只读回答流。"""


@dataclass(frozen=True)
class StreamTarget:
    trace_id: str
    session_code: str
    # 执行已结束：从会话记录读取历史（需要 turn_id）
    finished: bool = False
    turn_id: str = ""
    username: str = ""


@dataclass(frozen=True)
class StreamSettings:
    output_key: str = "output"
    # 等待 Celery 任务开始写队列的预算
    ready_timeout: float = 30.0
    # 单次读取等待；也是检查 Schedule 状态的最小粒度
    read_timeout: float = 2.0
    # 空闲时发送 SSE 注释保活的间隔
    ping_interval: float = 15.0
    # 复查 Schedule 是否终态的间隔
    state_check_interval: float = 5.0
    # 单连接最长时长
    max_duration: float = 30 * 60.0
    # 转发的 AG-UI 事件类型
    event_types: frozenset = DEFAULT_EVENT_TYPES


def resolve_target(trace_id: str, schedule: Any | None) -> StreamTarget:
    """从 BPF Schedule 记录解析出可订阅的 session_code。

    ``schedule`` 需要有 ``state`` 和 ``data``（JSON 字符串）属性；None 表示不存在。
    """
    if schedule is None:
        raise TargetNotFound(trace_id)
    finished = schedule.state in TERMINAL_STATES
    if not finished and schedule.state != STATE_POLL:
        raise StreamUnsupported("execution is not polling")
    try:
        data = json.loads(schedule.data or "{}")
    except (TypeError, ValueError) as e:
        raise StreamUnsupported("schedule data is not json") from e
    if not isinstance(data, dict):
        raise StreamUnsupported("schedule data is not an object")
    context = data.get("context") or {}
    if not isinstance(context, dict):
        raise StreamUnsupported("schedule context is not an object")
    storage = context.get("storage") or {}
    if not isinstance(storage, dict):
        raise StreamUnsupported("schedule storage is not an object")
    session_code = storage.get("session_code") or ""
    if not isinstance(session_code, str) or not session_code:
        raise StreamUnsupported("no session_code in schedule storage")
    if (storage.get("agent_type") or CHAT_AGENT_TYPE) != CHAT_AGENT_TYPE:
        raise StreamUnsupported("only chat agent is supported")
    if not finished:
        return StreamTarget(trace_id=trace_id, session_code=session_code)
    turn_id = storage.get("turn_id") or ""
    if not isinstance(turn_id, str) or not turn_id:
        raise StreamUnsupported("execution finished")
    username = storage.get("plugin_username") or ""
    if not isinstance(username, str):
        raise StreamUnsupported("invalid plugin_username in schedule storage")
    return StreamTarget(
        trace_id=trace_id,
        session_code=session_code,
        finished=True,
        turn_id=turn_id,
        username=username,
    )


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


SSE_PING = ": ping\n\n"


def parse_frame(message: Any) -> dict | None:
    """解析一条队列消息中的 AG-UI 事件；非 ``data: {...}`` 帧返回 None。"""
    if not isinstance(message, str) or not message.startswith("data: "):
        return None
    try:
        payload = json.loads(message[6:].strip())
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _last_run_start(messages: list[Any]) -> int:
    """返回最后一个 RUN_STARTED 帧的下标；没有时返回 -1。"""
    for index in range(len(messages) - 1, -1, -1):
        frame = parse_frame(messages[index])
        if frame and frame.get("type") == RUN_STARTED:
            return index
    return -1


def _reasoning_texts(content: Any) -> list[str]:
    """会话记录中 reasoning 的 content：列表，或其 JSON 字符串，或普通字符串。"""
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            return [content] if content else []
    if isinstance(content, list):
        return [str(item) for item in content if item]
    return [str(content)] if content else []


def _history_frames(target: StreamTarget, contents: list[dict]) -> Iterator[dict]:
    """只转换当前轮次的历史思考过程；SSE 编码和事件过滤由调用方负责。"""
    for item in contents:
        if item.get("role") != "reasoning" or (item.get("property") or {}).get("turn_id") != target.turn_id:
            continue
        texts = _reasoning_texts(item.get("content"))
        if not texts:
            continue
        yield {"type": "THINKING_START"}
        for text in texts:
            yield {"type": "THINKING_TEXT_MESSAGE_START"}
            yield {"type": "THINKING_TEXT_MESSAGE_CONTENT", "delta": text}
            yield {"type": "THINKING_TEXT_MESSAGE_END"}
        yield {"type": "THINKING_END", "duration": item.get("duration") or 0}


def history_answer(
    target: StreamTarget, contents: list[dict], settings: StreamSettings = StreamSettings()
) -> Iterator[str]:
    """把本轮历史思考过程按允许的 AG-UI 类型编码为 SSE；正文以节点正式输出为准。"""
    yield sse("ready", {"output_key": settings.output_key})
    for frame in _history_frames(target, contents):
        if frame["type"] in settings.event_types:
            yield sse("agui", frame)
    yield sse("end", {"reason": "history"})


def stream_answer(
    target: StreamTarget,
    handler: Any,
    load_state: Callable[[], int | None],
    settings: StreamSettings = StreamSettings(),
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[str]:
    """生成 SSE 文本。

    ``handler``：aidev 消息队列 handler（需支持 replay）。
    ``load_state``：返回当前 Schedule.state，记录不存在时返回 None。
    """
    thread_id = target.session_code
    started = clock()
    last_sent = started
    last_state_check = started

    yield sse("ready", {"output_key": settings.output_key})

    def finished() -> bool:
        state = load_state()
        return state is None or state in TERMINAL_STATES

    # 1. 等队列出现。get_messages_since 会声明队列，队列确认存在前不能调用。
    while not handler.has_pending_messages(thread_id):
        now = clock()
        if now - started >= settings.ready_timeout:
            yield sse("end", {"reason": "not_ready"})
            return
        if now - last_state_check >= settings.state_check_interval:
            last_state_check = now
            if finished():
                yield sse("end", {"reason": "finished"})
                return
        if now - last_sent >= settings.ping_interval:
            last_sent = now
            yield SSE_PING
        sleep(min(1.0, settings.read_timeout))

    # 2. 只读回放
    offset = 0
    first_batch = True
    draining = False  # Schedule 已终态，只再读一次剩余内容
    while True:
        now = clock()
        if now - started >= settings.max_duration:
            yield sse("end", {"reason": "timeout"})
            return

        if not handler.has_pending_messages(thread_id):
            # 队列已被原链路清理（执行已结束）
            yield sse("end", {"reason": "finished"})
            return

        try:
            messages, offset = handler.get_messages_since(thread_id, offset, timeout=settings.read_timeout)
        except TimeoutError:
            messages = []

        if messages:
            if first_batch:
                # 同一 session 复用时，队列里可能还有上一轮内容，从最后一次 RUN_STARTED 开始
                messages = messages[max(_last_run_start(messages), 0) :]
                first_batch = False
            for message in messages:
                if isinstance(message, str) and message in END_MARKERS:
                    yield sse("end", {"reason": "completed"})
                    return
                frame = parse_frame(message)
                if not frame:
                    continue
                frame_type = frame.get("type")
                if frame_type == RUN_STARTED:
                    yield sse("reset", {})
                    last_sent = clock()
                elif frame_type in settings.event_types:
                    yield sse("agui", frame)
                    last_sent = clock()

        if draining:
            yield sse("end", {"reason": "finished"})
            return

        now = clock()
        if now - last_state_check >= settings.state_check_interval:
            last_state_check = now
            if finished():
                draining = True
                continue
        if now - last_sent >= settings.ping_interval:
            last_sent = now
            yield SSE_PING
