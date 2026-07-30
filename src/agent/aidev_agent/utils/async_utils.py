# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import asyncio
import queue
import threading
from contextlib import suppress
from contextvars import copy_context
from logging import getLogger
from typing import AsyncGenerator, Awaitable, Callable

from aidev_agent.utils import Empty

logger = getLogger(__name__)


async def async_generator_with_timeout(
    gen: AsyncGenerator, timeout: int | float = 1, max_wait_rounds: int = 50
) -> AsyncGenerator:
    try:
        while True:
            tasks = [asyncio.create_task(gen.__anext__()), asyncio.create_task(asyncio.sleep(timeout))]
            for _ in range(max_wait_rounds):
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                if tasks[0] in done:
                    result = tasks[0].result()
                    yield result
                    break
                else:
                    tasks[1] = asyncio.create_task(asyncio.sleep(timeout))
                    yield Empty
            else:
                raise TimeoutError("生成器超时")
    except StopAsyncIteration:
        return


def async_to_sync_generator(
    async_gen: AsyncGenerator,
    async_finalizer: Callable[[], Awaitable[None]] | None = None,
):
    """在独立 loop 中消费异步生成器，并在同一 loop 执行 finalizer。"""
    data_queue = queue.Queue()
    end = object()
    error = None

    loop = asyncio.new_event_loop()
    context = copy_context()
    task_ready = threading.Event()
    consumer_task = None

    async def consume_async():
        nonlocal error
        try:
            async for item in async_gen:
                data_queue.put(item)
        except Exception as e:
            logger.warning(f"[ASYNC] consume_async error: {e}", exc_info=True)
            error = e
        finally:
            if async_finalizer is not None:
                try:
                    await async_finalizer()
                except Exception as e:
                    if error is None:
                        error = e
            data_queue.put(end)

    def run_loop():
        nonlocal consumer_task
        asyncio.set_event_loop(loop)
        consumer_task = context.run(loop.create_task, consume_async())
        task_ready.set()
        try:
            loop.run_until_complete(consumer_task)
        except asyncio.CancelledError:
            pass
        finally:
            pending_tasks = asyncio.all_tasks(loop)
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
            with suppress(RuntimeError):
                loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    loop_thread = threading.Thread(target=run_loop, name="aidev-async-generator", daemon=True)
    loop_thread.start()
    task_ready.wait()
    try:
        while True:
            item = data_queue.get()
            if item is end:
                if error is not None:
                    raise error
                break
            yield item
    finally:
        if not consumer_task.done():
            loop.call_soon_threadsafe(consumer_task.cancel)
        loop_thread.join()
