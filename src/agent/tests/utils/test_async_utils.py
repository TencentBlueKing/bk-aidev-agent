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

import pytest
from aidev_agent.core.utils.async_utils import async_generator_with_timeout, async_to_sync_generator
from aidev_agent.core.utils.local import request_local
from aidev_agent.utils import (
    Empty,
)


async def gen(interval: int = 0.2):
    run_id = getattr(request_local, "run_id", "")
    for i in range(3):
        await asyncio.sleep(i * interval)
        yield f"{run_id}-{i}"


def test_async_to_sync_generator():
    request_local.run_id = "run_id"
    _aiter = async_generator_with_timeout(gen(), timeout=0.18)
    _iter = async_to_sync_generator(_aiter)
    result = [each for each in _iter]
    assert result == ["run_id-0", Empty, "run_id-1", Empty, Empty, "run_id-2"]

    _aiter = async_generator_with_timeout(gen(), timeout=10)
    _iter = async_to_sync_generator(_aiter)
    result = [each for each in _iter]
    assert result == ["run_id-0", "run_id-1", "run_id-2"]


async def test_async_gen_with_timeout():
    request_local.run_id = "run_id"
    result = [each async for each in async_generator_with_timeout(gen(), timeout=0.18)]
    assert result == ["run_id-0", Empty, "run_id-1", Empty, Empty, "run_id-2"]

    # 迭代器超时没有返回则需要返回超时异常
    with pytest.raises(TimeoutError):
        result = [each async for each in async_generator_with_timeout(gen(100), timeout=0.1)]
