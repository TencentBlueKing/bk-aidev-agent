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
from threading import Thread
from typing import AsyncGenerator, Optional

from aidev_agent.utils import Empty


async def async_generator_with_timeout(
    gen: AsyncGenerator, timeout: Optional[int | float], max_wait_rounds: int = 15
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


def async_to_sync_generator(async_gen, loop=None):
    data_queue = queue.Queue()
    error = None
    new_loop_created = False

    # 判断是否使用现有循环
    if loop is None:
        loop = asyncio.new_event_loop()
        new_loop_created = True

    # 定义异步消费任务
    async def consume_async():
        nonlocal error
        try:
            async for item in async_gen:
                data_queue.put(item)
        except Exception as e:
            error = e
        finally:
            data_queue.put(None)  # 结束信号

    # 线程运行函数（仅当需要新线程时启动）
    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    # 根据循环状态决定是否启动新线程
    if not loop.is_running() and new_loop_created:
        event_loop_thread = Thread(target=run_loop, daemon=True)
        event_loop_thread.start()

    # 提交异步任务到指定循环
    asyncio.run_coroutine_threadsafe(consume_async(), loop)

    try:
        while True:
            item = data_queue.get()
            if item is None:
                if error is not None:
                    raise error
                break
            yield item
    finally:
        # 仅清理自己创建的循环
        if new_loop_created:
            loop.call_soon_threadsafe(loop.stop)
            if event_loop_thread.is_alive():
                event_loop_thread.join(timeout=1)
