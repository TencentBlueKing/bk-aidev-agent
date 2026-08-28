"""Bkplugin 统一后台执行器测试。"""

import threading

from aidev_bkplugin.services import execution
from aidev_bkplugin.services.execution import BoundedDaemonExecutor
from django.conf import settings


def test_bounded_executor_rejects_tasks_over_active_and_pending_capacity():
    executor = BoundedDaemonExecutor(max_workers=1, max_pending=1, thread_name_prefix="aidev-test")
    started = threading.Event()
    release = threading.Event()

    def blocking_task() -> None:
        started.set()
        release.wait()

    try:
        assert executor.submit(blocking_task)
        assert started.wait(timeout=1)
        assert executor.submit(blocking_task)
        assert not executor.submit(blocking_task)
        assert (executor.snapshot().active, executor.snapshot().pending) == (1, 1)
    finally:
        release.set()
        executor.shutdown(wait=True)


def test_shared_executor_defaults_to_16_workers_and_32_pending(monkeypatch):
    monkeypatch.delattr(settings, "AIDEV_AGENT_MAX_WORKERS", raising=False)
    monkeypatch.delattr(settings, "AIDEV_AGENT_MAX_PENDING", raising=False)
    monkeypatch.setattr(execution, "_agent_executor", None)

    executor = execution.get_agent_executor()
    try:
        snapshot = executor.snapshot()
        assert (snapshot.max_workers, snapshot.max_pending, snapshot.capacity) == (16, 32, 48)
    finally:
        executor.shutdown(wait=True)
        execution._agent_executor = None
