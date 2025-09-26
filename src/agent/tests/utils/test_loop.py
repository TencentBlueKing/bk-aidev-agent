import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

# Add the src directory to the path so we can import the module
from aidev_agent.core.utils.loop import get_event_loop


def test_get_event_loop():
    """Test that get_event_loop returns a valid event loop."""
    # Import the thread local storage to reset it
    from aidev_agent.core.utils.loop import _thread_local

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
    from aidev_agent.core.utils.loop import _thread_local

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
