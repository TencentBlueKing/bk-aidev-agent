"""有界、守护线程式的 wxbot Agent 后台执行器。"""

from __future__ import annotations

import contextvars
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
    max_workers: int
    max_pending: int
    capacity: int
    submitted: int
    rejected: int
    peak_active: int
    peak_pending: int


class BoundedDaemonExecutor:
    """固定数量守护线程，并限制活跃与排队任务总数。"""

    def __init__(self, max_workers: int, max_pending: int, thread_name_prefix: str = "wxbot-agent"):
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than zero")
        if max_pending < 0:
            raise ValueError("max_pending must not be negative")

        self._max_workers = max_workers
        self._max_pending = max_pending
        self._capacity = max_workers + max_pending
        self._slots = threading.BoundedSemaphore(self._capacity)
        self._tasks: queue.Queue[
            tuple[contextvars.Context, Callable[..., Any], tuple[Any, ...], dict[str, Any]] | None
        ] = queue.Queue()
        self._lock = threading.Lock()
        self._active = 0
        self._pending = 0
        self._submitted = 0
        self._rejected = 0
        self._peak_active = 0
        self._peak_pending = 0
        self._shutdown = False
        self._threads = [
            threading.Thread(target=self._worker, name=f"{thread_name_prefix}-{index + 1}", daemon=True)
            for index in range(max_workers)
        ]
        for thread in self._threads:
            thread.start()

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> bool:
        """非阻塞提交；达到总容量时返回 False。

        任务在提交方的 contextvars 快照里执行。worker 是常驻线程，如果直接裸调，
        任务内 attach 的 OTel context 一旦漏了 detach 就会污染后续落到同一线程的
        所有任务，表现为不同请求共用同一个 trace id。
        """
        with self._lock:
            if self._shutdown:
                self._rejected += 1
                return False
        if not self._slots.acquire(blocking=False):
            with self._lock:
                self._rejected += 1
            return False

        with self._lock:
            if self._shutdown:
                self._slots.release()
                self._rejected += 1
                return False
            self._pending += 1
            self._submitted += 1
            self._peak_pending = max(self._peak_pending, self._pending)
        self._tasks.put((contextvars.copy_context(), fn, args, kwargs))
        return True

    def snapshot(self) -> ExecutorSnapshot:
        with self._lock:
            return ExecutorSnapshot(
                active=self._active,
                pending=self._pending,
                max_workers=self._max_workers,
                max_pending=self._max_pending,
                capacity=self._capacity,
                submitted=self._submitted,
                rejected=self._rejected,
                peak_active=self._peak_active,
                peak_pending=self._peak_pending,
            )

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

            context, fn, args, kwargs = task
            with self._lock:
                self._pending -= 1
                self._active += 1
                self._peak_active = max(self._peak_active, self._active)
            try:
                context.run(fn, *args, **kwargs)
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
                max_workers=int(getattr(settings, "WXAIBOT_AGENT_MAX_WORKERS", 10)),
                max_pending=int(getattr(settings, "WXAIBOT_AGENT_MAX_PENDING", 16)),
            )
        return _agent_executor


def get_agent_executor_snapshot() -> ExecutorSnapshot:
    with _executor_lock:
        executor = _agent_executor
    if executor is None:
        return ExecutorSnapshot(
            active=0,
            pending=0,
            max_workers=0,
            max_pending=0,
            capacity=0,
            submitted=0,
            rejected=0,
            peak_active=0,
            peak_pending=0,
        )
    return executor.snapshot()
