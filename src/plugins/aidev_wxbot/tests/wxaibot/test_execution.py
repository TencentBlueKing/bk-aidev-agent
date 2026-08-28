"""wxbot 后台并发与 Agent 取消注册表测试。"""

import threading
from unittest.mock import patch

from aidev_wxbot.wxaibot.execution import BoundedDaemonExecutor
from aidev_wxbot.wxaibot.stream_registry import StreamRegistry


def test_bounded_executor_rejects_tasks_over_active_and_pending_capacity():
    executor = BoundedDaemonExecutor(max_workers=1, max_pending=1, thread_name_prefix="wxbot-test")
    started = threading.Event()
    release = threading.Event()
    completed: list[str] = []

    def blocking_task(name: str) -> None:
        started.set()
        release.wait()
        completed.append(name)

    try:
        assert executor.submit(blocking_task, "active")
        assert started.wait(timeout=1)
        assert executor.submit(blocking_task, "pending")
        assert not executor.submit(blocking_task, "rejected")
        snapshot = executor.snapshot()
        assert snapshot.active == 1
        assert snapshot.pending == 1
        assert snapshot.capacity == 2
        assert snapshot.submitted == 2
        assert snapshot.rejected == 1
        assert snapshot.peak_active == 1
        assert snapshot.peak_pending == 1
    finally:
        release.set()
        executor.shutdown(wait=True)

    assert completed == ["active", "pending"]


def test_bounded_executor_runs_ten_sessions_concurrently():
    executor = BoundedDaemonExecutor(max_workers=10, max_pending=16, thread_name_prefix="wxbot-ten")
    release = threading.Event()
    all_started = threading.Event()
    lock = threading.Lock()
    active = 0

    def blocking_task() -> None:
        nonlocal active
        with lock:
            active += 1
            if active == 10:
                all_started.set()
        release.wait(timeout=2)

    try:
        assert all(executor.submit(blocking_task) for _ in range(10))
        assert all_started.wait(timeout=1)
        snapshot = executor.snapshot()
        assert (snapshot.active, snapshot.pending, snapshot.peak_active) == (10, 0, 10)
        assert (snapshot.max_workers, snapshot.max_pending, snapshot.capacity) == (10, 16, 26)
    finally:
        release.set()
        executor.shutdown(wait=True)


def test_stream_registry_cancels_exact_registered_run():
    registry = StreamRegistry()
    registry.register("stream-1", "session-1")
    registry.set_run_id("stream-1", "run-1")

    with patch(
        "aidev_wxbot.wxaibot.stream_registry.GeneratorStreamingHelper.cancel",
        return_value=True,
    ) as cancel:
        assert registry.cancel("stream-1")

    cancel.assert_called_once_with("session-1", run_id="run-1")
    assert registry.is_cancel_requested("stream-1")
    registry.unregister("stream-1")
    assert not registry.is_cancel_requested("stream-1")


def test_stream_registry_delivers_cancel_when_agent_registers_late():
    registry = StreamRegistry()
    assert not registry.cancel("stream-1")

    with patch(
        "aidev_wxbot.wxaibot.stream_registry.GeneratorStreamingHelper.cancel",
        return_value=True,
    ) as cancel:
        assert registry.register("stream-1", "session-1")

    cancel.assert_called_once_with("session-1", run_id=None)
