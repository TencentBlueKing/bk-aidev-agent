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

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable, Union

from .protocol import HookContext, HookPoint

__all__ = ["HookHandler", "HookSet"]

# 处理器签名：入参 HookContext，返回点位对应的原生对象（消息 / 请求）或 None（不干预）。
HookHandler = Callable[[HookContext], Any]


class HookSet:
    """点位到有序处理器元组的不可变集合。

    构建期校验点位名与可调用性：未知点位名抛 ``ValueError``，非可调用对象抛
    ``TypeError``。实例内不持有模块级可变状态，可按实例隔离。
    """

    def __init__(self, handlers: Mapping[Union[HookPoint, str], Sequence[HookHandler]] | None = None) -> None:
        normalized: dict[HookPoint, tuple[HookHandler, ...]] = {}
        for raw_point, raw_handlers in (handlers or {}).items():
            point = _normalize_point(raw_point)
            normalized[point] = _normalize_handlers(raw_handlers)
        self._handlers = normalized

    def handlers(self, point: HookPoint) -> tuple[HookHandler, ...]:
        """返回该点位的处理器元组；未注册时为空元组。"""
        return self._handlers.get(point, ())

    def __repr__(self) -> str:
        summary = ", ".join(f"{point.value}={len(handlers)}" for point, handlers in self._handlers.items())
        return f"HookSet({summary})"


def _normalize_point(raw_point: Union[HookPoint, str]) -> HookPoint:
    if isinstance(raw_point, HookPoint):
        return raw_point
    try:
        return HookPoint(raw_point)
    except ValueError as error:
        raise ValueError(f"unknown hook point: {raw_point!r}") from error


def _normalize_handlers(raw_handlers: Sequence[HookHandler]) -> tuple[HookHandler, ...]:
    if isinstance(raw_handlers, (str, bytes)) or not isinstance(raw_handlers, Sequence):
        raise TypeError(f"hook handlers must be a sequence, got {type(raw_handlers).__name__}")
    handlers: list[HookHandler] = []
    for handler in raw_handlers:
        if not callable(handler):
            raise TypeError(f"hook handler must be callable, got {type(handler).__name__}")
        handlers.append(handler)
    return tuple(handlers)
