"""关联 wxbot stream 与 Agent run，用于跨线程超时取消。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from logging import getLogger

from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper

logger = getLogger(__name__)


@dataclass(slots=True)
class AgentRun:
    session_code: str
    run_id: str = ""


class StreamRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, AgentRun] = {}
        self._cancel_requested: set[str] = set()

    def register(self, stream_id: str, session_code: str) -> bool:
        """注册 Agent 会话；返回该 stream 是否已先收到取消请求。"""
        with self._lock:
            self._runs[stream_id] = AgentRun(session_code=session_code)
            cancelled = stream_id in self._cancel_requested
        if cancelled:
            self._cancel_run(stream_id)
        return cancelled

    def set_run_id(self, stream_id: str, run_id: str) -> None:
        if not run_id:
            return
        with self._lock:
            run = self._runs.get(stream_id)
            if run:
                run.run_id = run_id
                cancelled = stream_id in self._cancel_requested
            else:
                cancelled = False
        if cancelled:
            self._cancel_run(stream_id)

    def cancel(self, stream_id: str) -> bool:
        with self._lock:
            self._cancel_requested.add(stream_id)
            registered = stream_id in self._runs
        return self._cancel_run(stream_id) if registered else False

    def is_cancel_requested(self, stream_id: str) -> bool:
        with self._lock:
            return stream_id in self._cancel_requested

    def unregister(self, stream_id: str) -> None:
        with self._lock:
            self._runs.pop(stream_id, None)
            self._cancel_requested.discard(stream_id)

    def _cancel_run(self, stream_id: str) -> bool:
        with self._lock:
            run = self._runs.get(stream_id)
            if run is None:
                return False
            session_code = run.session_code
            run_id = run.run_id or None
        try:
            cancelled = GeneratorStreamingHelper.cancel(session_code, run_id=run_id)
            logger.info(
                "event=wxbot_agent_cancel stream_id=%s session_code=%s run_id=%s delivered=%s",
                stream_id,
                session_code,
                run_id or "",
                cancelled,
            )
            return cancelled
        except Exception:
            logger.exception(
                "event=wxbot_agent_cancel stream_id=%s session_code=%s run_id=%s delivered=false",
                stream_id,
                session_code,
                run_id or "",
            )
            return False


stream_registry = StreamRegistry()
