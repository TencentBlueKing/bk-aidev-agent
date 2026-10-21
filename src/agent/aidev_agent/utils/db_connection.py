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

# 数据库连接失效后的一次性重连，仅用于幂等读取。
# SDK 不强制依赖 Django：宿主未安装 Django 时没有可重建的 ORM 连接，所有判断都退化为“不是数据库错误”，
# 调用会原样执行。

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

# 服务端或中间代理关闭空闲连接后，客户端要到下一次使用时才会报出的错误码（pymysql）
CONNECTION_LOST_DATABASE_ERROR_CODES = frozenset({2006, 2013, 2055})


def is_database_error(exc: BaseException) -> bool:
    """判断异常是否来自 Django 数据库层。"""
    database_errors = tuple(error for error in (OperationalError, InterfaceError) if error is not None)
    return isinstance(exc, database_errors)


def is_connection_lost_error(exc: BaseException) -> bool:
    """判断数据库异常是否表示连接已失效：驱动层连接不可用，或连接在使用中被对端关闭。"""
    if InterfaceError is not None and isinstance(exc, InterfaceError):
        return True
    error_code = exc.args[0] if exc.args else None
    return error_code in CONNECTION_LOST_DATABASE_ERROR_CODES


def call_with_reconnect(operation: Callable[[], T], description: str) -> T:
    """执行幂等的数据库读取；连接已失效时丢弃当前线程的默认连接并重试一次。

    重试仍失败，或异常不是连接失效时原样抛出，由调用方决定如何失败；禁止在这里吞成空结果。
    """
    try:
        return operation()
    except Exception as exc:
        if not (is_database_error(exc) and is_connection_lost_error(exc)):
            raise
        _logger.warning("%s：数据库连接已失效，丢弃连接后重试一次，error=%s", description, exc)
        _discard_default_connection()
        return operation()


def _discard_default_connection() -> None:
    """丢弃当前线程的默认数据库连接，下一次使用时会重新建立。"""
    if connection is None:
        return
    # 关闭失败不影响重试：重试时会重新建连，若仍失败由调用方的异常处理负责
    with suppress(Exception):
        connection.close()
