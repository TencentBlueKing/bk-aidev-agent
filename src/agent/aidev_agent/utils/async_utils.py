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
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from typing import AsyncGenerator, Awaitable, Callable

from aidev_agent.utils import Empty

_QUEUE_GET_TIMEOUT = 300


async def async_generator_with_timeout(
    gen: AsyncGenerator, timeout: int | float = 1, max_wait_rounds: int = 50
) -> AsyncGenerator:
    try:
        while True:
            next_item = asyncio.create_task(gen.__anext__())
            try:
                for _ in range(max_wait_rounds):
                    try:
                        result = await asyncio.wait_for(asyncio.shield(next_item), timeout=timeout)
                    except TimeoutError:
                        yield Empty
                    else:
                        yield result
                        break
                else:
                    raise TimeoutError("生成器超时")
            finally:
                if not next_item.done():
                    next_item.cancel()
                    await asyncio.gather(next_item, return_exceptions=True)
    except StopAsyncIteration:
        return


def async_to_sync_generator(
    async_gen: AsyncGenerator,
    async_finalizer: Callable[[], Awaitable[None]] | None = None,
):
    """Consume an async generator from synchronous code on an isolated loop.

    The async generator and its optional finalizer always execute on the same
    helper loop. This keeps loop-bound resources out of the caller thread and
    also works when the caller already has a running event loop.
    """
    data_queue = asyncio.Queue()
    error = None

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, name="aidev-async-generator", daemon=True)
    loop_thread.start()

    async def consume_async():
        nonlocal error
        try:
            async for item in async_gen:
                await data_queue.put(item)
        except Exception as e:
            error = e
        finally:
            if async_finalizer is not None:
                try:
                    await async_finalizer()
                except Exception as e:
                    if error is None:
                        error = e
            await data_queue.put(None)

    async def cancel_pending_tasks():
        async def cancel_all():
            current_task = asyncio.current_task()
            pending_tasks = [task for task in asyncio.all_tasks() if task is not current_task]
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)

        await cancel_all()
        await loop.shutdown_asyncgens()
        await cancel_all()

    asyncio.run_coroutine_threadsafe(consume_async(), loop)

    try:
        while True:
            get_future = asyncio.run_coroutine_threadsafe(data_queue.get(), loop)
            try:
                item = get_future.result(timeout=_QUEUE_GET_TIMEOUT)
            except FutureTimeoutError:
                get_future.cancel()
                raise

            if item is None:
                if error is not None:
                    raise error
                break
            yield item
    finally:
        with suppress(FutureTimeoutError):
            asyncio.run_coroutine_threadsafe(cancel_pending_tasks(), loop).result(timeout=1)
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join()
        loop.close()
