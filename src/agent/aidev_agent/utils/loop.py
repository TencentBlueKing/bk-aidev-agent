# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import asyncio
import atexit
import contextlib
import threading
from logging import getLogger

logger = getLogger(__name__)

# Thread-local storage for event loops
_thread_local = threading.local()


def get_event_loop():
    """
    Get the current event loop for this thread, create one if it doesn't exist.

    Returns:
        asyncio.AbstractEventLoop: The current event loop for this thread.
    """
    # Try to get the running loop first — it takes priority over the cached one
    try:
        running_loop = asyncio.get_running_loop()
        if hasattr(_thread_local, "loop") and _thread_local.loop is not running_loop:
            # Cached loop is stale (e.g. pytest created a new loop), update cache
            _thread_local.loop = running_loop
        return running_loop
    except RuntimeError:
        pass

    # Check if we have a cached loop for this thread
    if hasattr(_thread_local, "loop") and _thread_local.loop is not None and not _thread_local.loop.is_closed():
        return _thread_local.loop

    # No running loop, try to get the event loop for this thread
    try:
        current_loop = asyncio.get_event_loop()
        # Check if this loop is running
        if current_loop.is_running():
            # If the loop is running, we can't use run_until_complete on it
            # Create a new loop for this thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            _thread_local.loop = new_loop
            # Register cleanup function for this thread's loop
            atexit.register(_cleanup_thread_loop, new_loop)
            return new_loop
        else:
            _thread_local.loop = current_loop
            return current_loop
    except RuntimeError:
        # No event loop exists, create a new one
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        _thread_local.loop = new_loop
        # Register cleanup function for this thread's loop
        atexit.register(_cleanup_thread_loop, new_loop)
        return new_loop


def close_thread_loop() -> None:
    """Close and clear the cached event loop for the current thread."""
    loop = getattr(_thread_local, "loop", None)
    if loop is None:
        return

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is loop:
        return

    _cleanup_thread_loop(loop)
    with contextlib.suppress(Exception):
        asyncio.set_event_loop(None)
    _thread_local.loop = None


def run_coro_sync(coro, timeout=None):
    """Run a coroutine synchronously in the current thread's event loop.

    若当前线程没有 running loop，复用线程局部 loop 跑（保持 loop 开启以便
    long-lived async client 复用连接）；若当前线程已有 running loop（嵌套调用
    场景，如 async→sync 桥接、gevent monkey patch），不能 run_until_complete，
    否则抛 "This event loop is already running"，此时在独立线程里用 asyncio.run
    执行协程。

    Note: 正常分支下 event loop 故意保持开启，long-lived async client（如
    httpx.AsyncClient）可跨多次调用复用连接；清理由 atexit 与
    async_to_sync_generator 的 finally 块负责。
    """
    loop = get_event_loop()
    if loop.is_running():
        # 当前线程已有 running loop，run_until_complete 会抛 already running，
        # 委托给独立线程跑一个全新的 loop
        logger.warning(
            "[LOOP] run_coro_sync: running loop detected, delegate to new thread, thread=%s",
            threading.current_thread().name,
        )
        return _run_coro_in_new_thread(coro, timeout)

    if timeout is not None:
        coro = asyncio.wait_for(coro, timeout=timeout)
    try:
        return loop.run_until_complete(coro)
    except RuntimeError as e:
        if "already running" in str(e):
            logger.error(
                "[LOOP] run_coro_sync failed: event loop already running. thread=%s, loop=%s",
                threading.current_thread().name,
                loop,
            )
        raise


def _run_coro_in_new_thread(coro, timeout=None):
    """在独立线程里用 asyncio.run 执行协程，返回结果或重新抛出异常。

    用于 run_coro_sync 检测到当前线程已有 running loop 的兜底场景：
    协程对象本身不绑定 loop，可安全跨线程传递，由新线程的全新 loop 消费。
    """
    box: dict = {}

    def _runner():
        try:
            if timeout is not None:
                box["value"] = asyncio.run(asyncio.wait_for(coro, timeout=timeout))
            else:
                box["value"] = asyncio.run(coro)
        except BaseException as err:  # noqa: BLE001
            box["error"] = err

    worker = threading.Thread(target=_runner, name="run-coroutine-sync", daemon=True)
    worker.start()
    worker.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _cleanup_thread_loop(loop):
    """Cleanup function to properly close a thread's event loop on exit."""
    if loop is not None and not loop.is_closed():
        try:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Run until all tasks are cancelled if the loop is not running
            if pending and not loop.is_running():
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            with contextlib.suppress(AttributeError, RuntimeError):
                loop.run_until_complete(loop.shutdown_asyncgens())
            with contextlib.suppress(AttributeError, RuntimeError):
                loop.run_until_complete(loop.shutdown_default_executor())

            # Close the loop
            loop.close()
        except Exception:
            # Ignore exceptions during cleanup
            pass
