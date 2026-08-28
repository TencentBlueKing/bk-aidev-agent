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
    finally:
        release.set()
        executor.shutdown(wait=True)

    assert completed == ["active", "pending"]


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
