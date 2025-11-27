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

import logging
import time
import traceback
from datetime import datetime
from functools import wraps

import pytz

from aidev_agent.core.extend.intent.utils import logger

logger = logging.getLogger(__name__)


def get_beijing_now():
    utc_now = datetime.now(pytz.utc)
    beijing_now = utc_now.astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y年%m月%d日 %H时%M分%S秒")
    return beijing_now


def timeit(message=""):
    """
    平移 core.extend.intent 中的代码
    :param message:
    :return:
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not kwargs.pop("disable_timeit", False):
                st_time = time.time()
                result = func(*args, **kwargs)
                elapsed_time = time.time() - st_time
                logger.info(f"=====> {message}耗时 ({func.__name__}): {elapsed_time:.2f}s")
                return result
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def retry(max_retries=5, max_seconds=1800):
    def _retry(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try_cnt = 0
            start_time = time.time()
            while try_cnt < max_retries and (time.time() - start_time) < max_seconds:
                try:
                    try_cnt += 1
                    return func(*args, **kwargs)
                except Exception:  # noqa: PERF203
                    logger.info(
                        f"\n\n=====\n>>>>> 执行出错，重试中。当前尝试次数: {try_cnt}。"
                        f"详细错误情况：\n{traceback.format_exc()}\n=====\n\n"
                    )
                    if try_cnt >= max_retries or (time.time() - start_time) >= max_seconds:
                        # 如果达到最大重试次数或者超过最大时间限制，最后一次重试的异常将被抛出。
                        # 这样可以确保在所有重试都失败的情况下，异常会被正确地抛出并处理。
                        raise
                    continue

        return wrapper

    return _retry
