"""有界、守护线程式的 wxbot Agent 后台执行器。"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from logging import getLogger
from typing import Any

from django.conf import settings

logger = getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExecutorSnapshot:
    active: int
    pending: int
    capacity: int


class BoundedDaemonExecutor:
    """固定数量守护线程，并限制活跃与排队任务总数。"""

    def __init__(self, max_workers: int, max_pending: int, thread_name_prefix: str = "wxbot-agent"):
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than zero")
        if max_pending < 0:
            raise ValueError("max_pending must not be negative")

        self._capacity = max_workers + max_pending
        self._slots = threading.BoundedSemaphore(self._capacity)
        self._tasks: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]] | None] = queue.Queue()
        self._lock = threading.Lock()
        self._active = 0
        self._pending = 0
        self._shutdown = False
        self._threads = [
            threading.Thread(target=self._worker, name=f"{thread_name_prefix}-{index + 1}", daemon=True)
            for index in range(max_workers)
        ]
        for thread in self._threads:
            thread.start()

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> bool:
        """非阻塞提交；达到总容量时返回 False。"""
        with self._lock:
            if self._shutdown:
                return False
        if not self._slots.acquire(blocking=False):
            return False

        with self._lock:
            if self._shutdown:
                self._slots.release()
                return False
            self._pending += 1
        self._tasks.put((fn, args, kwargs))
        return True

    def snapshot(self) -> ExecutorSnapshot:
        with self._lock:
            return ExecutorSnapshot(active=self._active, pending=self._pending, capacity=self._capacity)

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
        for _ in self._threads:
            self._tasks.put(None)
        if wait:
            for thread in self._threads:
                thread.join()

    def _worker(self) -> None:
        while True:
            task = self._tasks.get()
            if task is None:
                return

            fn, args, kwargs = task
            with self._lock:
                self._pending -= 1
                self._active += 1
            try:
                fn(*args, **kwargs)
            except Exception:
                logger.exception("event=wxbot_agent_executor task_failed=true")
            finally:
                with self._lock:
                    self._active -= 1
                self._slots.release()


_executor_lock = threading.Lock()
_agent_executor: BoundedDaemonExecutor | None = None


def get_agent_executor() -> BoundedDaemonExecutor:
    global _agent_executor
    with _executor_lock:
        if _agent_executor is None:
            _agent_executor = BoundedDaemonExecutor(
                max_workers=int(getattr(settings, "WXAIBOT_AGENT_MAX_WORKERS", 2)),
                max_pending=int(getattr(settings, "WXAIBOT_AGENT_MAX_PENDING", 16)),
            )
        return _agent_executor


def get_agent_executor_snapshot() -> ExecutorSnapshot:
    with _executor_lock:
        executor = _agent_executor
    if executor is None:
        return ExecutorSnapshot(active=0, pending=0, capacity=0)
    return executor.snapshot()
