import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

# Add the src directory to the path so we can import the module
from aidev_agent.utils.loop import get_event_loop, run_coro_sync


def test_get_event_loop():
    """Test that get_event_loop returns a valid event loop."""
    # Import the thread local storage to reset it
    from aidev_agent.utils.loop import _thread_local

    # Reset the thread-local loop reference
    if hasattr(_thread_local, "loop"):
        delattr(_thread_local, "loop")

    # Get the event loop
    loop = get_event_loop()

    # Verify it's a valid event loop
    assert loop is not None
    assert isinstance(loop, asyncio.AbstractEventLoop)

    # Verify we get the same loop on subsequent calls
    loop2 = get_event_loop()
    assert loop is loop2


def test_loop_creation():
    """Test that a new loop is created if one doesn't exist."""
    # Import the thread local storage to reset it
    from aidev_agent.utils.loop import _thread_local

    # Reset the thread-local loop reference
    if hasattr(_thread_local, "loop"):
        delattr(_thread_local, "loop")

    # Get the event loop
    loop = get_event_loop()

    # Verify it's a valid event loop
    assert loop is not None
    assert isinstance(loop, asyncio.AbstractEventLoop)


async def sample_async_task(value):
    """A simple async task for testing."""
    await asyncio.sleep(0.01)
    return value * 2


async def run_task(t: float):
    """A simple async task for testing."""
    await asyncio.sleep(t)
    return 1 * t


def test_run_async_task():
    """Test that we can run async tasks using the event loop."""
    # Get the event loop
    loop = get_event_loop()

    # Run an async task
    result = loop.run_until_complete(sample_async_task(5))

    # Verify the result
    assert result == 10


def test_multiple_async_tasks():
    """Test that we can run multiple async tasks using the event loop."""
    # Get the event loop
    loop = get_event_loop()

    # Create multiple tasks
    tasks = [sample_async_task(1), sample_async_task(2), sample_async_task(3)]

    # Run all tasks concurrently
    results = loop.run_until_complete(asyncio.gather(*tasks))

    # Verify the results
    assert results == [2, 4, 6]


def test_run_async_task_multi_threading():
    """Test that we can run async tasks using the event loop."""

    def _f(t):
        # Get the event loop
        loop = get_event_loop()

        # Run an async task
        result = loop.run_until_complete(run_task(t))

        # Verify the result
        assert result == t * 1
        return result

    results = []
    with ThreadPoolExecutor(10) as pool:
        results = [pool.submit(_f, _i * 0.1) for _i in range(10)]

    assert [each.result() for each in results] == [_i * 0.1 for _i in range(10)]


@pytest.mark.asyncio
async def test_async_context():
    """Test that the loop works in an async context."""
    # Get the event loop
    loop = get_event_loop()

    # Verify it's the same as the current loop
    current_loop = asyncio.get_running_loop()
    assert loop is current_loop

    # Run a task
    result = await sample_async_task(7)
    assert result == 14


def test_run_coro_sync_preserves_worker_thread_loop():
    from aidev_agent.utils.loop import _thread_local

    def _f():
        result = run_coro_sync(sample_async_task(5))
        has_loop = hasattr(_thread_local, "loop") and _thread_local.loop is not None
        return result, has_loop

    with ThreadPoolExecutor(1) as pool:
        result, has_loop = pool.submit(_f).result()

    assert result == 10
    assert has_loop is True


@pytest.mark.asyncio
async def test_run_coro_sync_with_running_loop_delegates_to_new_thread():
    """已有 running loop 时，run_coro_sync 应委托独立线程执行，不抛 already running。

    复现 construct_mcp 在 async→sync 桥接上下文被调用导致
    "This event loop is already running" 的场景。
    """
    result = run_coro_sync(sample_async_task(5))
    assert result == 10


@pytest.mark.asyncio
async def test_run_coro_sync_with_running_loop_propagates_exception():
    """已有 running loop 时，协程抛出的异常应原样冒泡到调用方。"""
    async def _boom():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_coro_sync(_boom())
