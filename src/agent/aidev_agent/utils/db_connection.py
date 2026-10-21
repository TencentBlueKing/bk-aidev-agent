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

# 数据库连接失效或建连失败时的有限次重连，仅用于幂等读取。
# SDK 不强制依赖 Django：宿主未安装 Django 时没有可重建的 ORM 连接，所有判断都退化为“不是数据库错误”，
# 调用会原样执行。

import time
from collections.abc import Callable
from contextlib import suppress
from logging import getLogger
from typing import TypeVar

try:
    from django.db import InterfaceError, OperationalError, connection
except ImportError:
    InterfaceError = OperationalError = connection = None

_logger = getLogger(__name__)

T = TypeVar("T")

# 可重连的错误码（pymysql）：
# 2006 / 2013 / 2055 是服务端或中间代理关闭空闲连接后，下一次使用时才报出的错误；
# 2002 / 2003 是建连失败，常见于服务重启或主机短暂不可达，重试窗口需要覆盖它们，否则重试对这类故障无效。
RECONNECTABLE_DATABASE_ERROR_CODES = frozenset({2002, 2003, 2006, 2013, 2055})

# 重连策略（与插件读路径保持一致）：首次重试立即发起，丢弃的失效连接换成新连接通常即可恢复；之后指数退避。
# 若下一次等待会使自首次尝试起的总耗时超过 RECONNECT_BUDGET_SECONDS，则停止重试。单次建连耗时另计：
# pymysql 默认 connect_timeout=10 秒，主机黑洞式不可达时单次尝试本身就会耗尽窗口。
RECONNECT_MAX_ATTEMPTS = 5
RECONNECT_BASE_DELAY_SECONDS = 0.5
RECONNECT_BUDGET_SECONDS = 5.0


def is_database_error(exc: BaseException) -> bool:
    """判断异常是否来自 Django 数据库层。"""
    database_errors = tuple(error for error in (OperationalError, InterfaceError) if error is not None)
    return isinstance(exc, database_errors)


def is_reconnectable_error(exc: BaseException) -> bool:
    """判断数据库异常能否通过丢弃连接后重试解决：驱动层连接不可用、连接被对端关闭，或建连失败。"""
    if InterfaceError is not None and isinstance(exc, InterfaceError):
        return True
    error_code = exc.args[0] if exc.args else None
    return error_code in RECONNECTABLE_DATABASE_ERROR_CODES


def _retry_delay(attempt: int) -> float:
    """第 attempt 次尝试失败后，发起下一次尝试前的等待秒数：依次为 0、0.5、1、2 ..."""
    if attempt == 1:
        return 0.0
    return RECONNECT_BASE_DELAY_SECONDS * (2 ** (attempt - 2))


def call_with_reconnect(operation: Callable[[], T], description: str) -> T:
    """执行幂等的数据库读取；连接失效或建连失败时丢弃当前线程的默认连接，在时间窗口内有限次重试。

    最多尝试 RECONNECT_MAX_ATTEMPTS 次；若下一次等待会使总耗时超过 RECONNECT_BUDGET_SECONDS，则不再重试。
    全部失败后原样抛出最后一次异常，由调用方决定如何失败；禁止在这里吞成空结果。
    """
    started = time.monotonic()
    attempt = 1
    while True:
        try:
            return operation()
        except Exception as exc:
            if not (is_database_error(exc) and is_reconnectable_error(exc)):
                raise
            delay = _retry_delay(attempt)
            elapsed = time.monotonic() - started
            if attempt >= RECONNECT_MAX_ATTEMPTS or elapsed + delay > RECONNECT_BUDGET_SECONDS:
                raise
            _logger.warning(
                "%s：数据库连接失效或不可用，第 %s 次尝试失败，%.1f 秒后重试，error=%s",
                description,
                attempt,
                delay,
                exc,
            )
            _discard_default_connection()
            if delay:
                time.sleep(delay)
            attempt += 1


def _discard_default_connection() -> None:
    """丢弃当前线程的默认数据库连接，下一次使用时会重新建立。"""
    if connection is None:
        return
    # 关闭失败不影响重试：重试时会重新建连，若仍失败由调用方的异常处理负责
    with suppress(Exception):
        connection.close()
