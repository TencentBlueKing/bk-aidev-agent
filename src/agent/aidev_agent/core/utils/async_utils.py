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
from typing import AsyncGenerator

from aidev_agent.core.utils.loop import get_event_loop
from aidev_agent.utils import Empty


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


def async_to_sync_generator(async_gen):
    data_queue = asyncio.Queue()
    error = None

    loop = get_event_loop()

    # 定义异步消费任务
    async def consume_async():
        nonlocal error
        try:
            async for item in async_gen:
                await data_queue.put(item)
        except Exception as e:
            error = e
        finally:
            await data_queue.put(None)  # 结束信号

    # 线程运行函数（仅当需要新线程时启动）
    # 提交异步任务到指定循环
    asyncio.run_coroutine_threadsafe(consume_async(), loop)

    while True:
        item = loop.run_until_complete(data_queue.get())
        if item is None:
            if error is not None:
                raise error
            break
        yield item
