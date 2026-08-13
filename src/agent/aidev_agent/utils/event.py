# -*- coding: utf-8 -*-
"""
AG-UI 事件工具模块
提供统一的事件发送方法和常量定义
"""

import time
from typing import Callable, Literal

from ag_ui.core import EventType, RunErrorEvent, RunFinishedEvent
from ag_ui.encoder import EventEncoder

from aidev_agent.core.ag_ui.types import RunFinishedSuccessOutcome, serialize_run_finished_outcome


# Run ID 常量定义
RunIdType = Literal["cancelled", "stopped"]


class RunId:
    """Run ID 常量定义

    在不同场景下使用标准化的 run_id 标识符，
    便于前端识别和统一处理。

    Attributes:
        CANCELLED: 用户主动取消场景
        STOPPED: 会话停止/超时场景
        CANCELLED_MESSAGE: 用户取消提示文本
    """

    CANCELLED: RunIdType = "cancelled"
    STOPPED: RunIdType = "stopped"
    CANCELLED_MESSAGE: str = "用户已取消"


def wall_clock_ms() -> int:
    """当前墙钟，毫秒。"""
    return int(time.time() * 1000)


def stamp_round_end_event(event: RunFinishedEvent | RunErrorEvent) -> None:
    """为本轮对话收尾事件写入墙钟毫秒。

    续流回放（resume_replay=True）不打戳。终态 checkpoint 重放不要调用本函数。
    """
    if getattr(event, "resume_replay", False):
        return
    if event.timestamp is None:
        event.timestamp = wall_clock_ms()


def emit_run_finished_event(
    thread_id: str,
    run_id: str,
    event_handler: Callable[[RunFinishedEvent], None] | None = None,
) -> str:
    """
    发送 RUN_FINISHED 事件
    统一的 RUN_FINISHED 事件发送方法，确保前端收到标准的结束事件。

    Args:
        thread_id: 会话线程 ID
        run_id: 运行标识，可使用 RunId.CANCELLED 或 RunId.STOPPED 等常量
        event_handler: 可选的事件处理器回调，用于分发事件

    Returns:
        SSE 编码的事件字符串

    Example:
        ```python
        # 取消场景
        yield emit_run_finished_event(thread_id="session-xxx", run_id=RunId.CANCELLED)

        # 停止场景
        yield emit_run_finished_event(thread_id="session-xxx", run_id=RunId.STOPPED)

        # 正常完成
        yield emit_run_finished_event(thread_id="session-xxx", run_id="run-123")

        # 带事件处理器
        yield emit_run_finished_event(
            thread_id="session-xxx",
            run_id=RunId.CANCELLED,
            event_handler=self._dispatch_event
        )
        ```
    """
    encoder = EventEncoder()
    finished_event = RunFinishedEvent(
        type=EventType.RUN_FINISHED,
        thread_id=thread_id,
        run_id=run_id,
        outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
    )
    stamp_round_end_event(finished_event)

    # 如果提供了事件处理器，调用它分发事件
    if event_handler:
        try:
            event_handler(finished_event)
        except Exception:
            # 事件处理器的异常不应影响流式响应，由调用方决定是否记录日志
            pass

    return encoder.encode(finished_event)
