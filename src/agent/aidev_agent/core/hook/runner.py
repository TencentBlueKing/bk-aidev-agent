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

hook 执行器：持有一组处理器，在 6 个点位按注入顺序分发。

执行语义：
- 处理器直接读写原生对象；返回点位对应的对象即生效，返回 ``None`` 表示不干预。
- 同一点位多个处理器依次执行，后一个看到的 payload 是前一个的结果。
- ``tool_pre`` 返回 ``ToolMessage`` / ``Command`` 时短路，工具不再执行。
- 处理器抛异常、超时（``TIMEOUT_SECONDS``）或返回类型不符时按不干预处理并记 warning，
  业务链路继续；``HookAbort`` / ``HookRetry`` 是控制流，原样抛给调用点。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from contextvars import copy_context
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from aidev_agent.core.hook.protocol import (
    HookAbort,
    HookContext,
    HookIdentity,
    HookPoint,
    HookRetry,
)
from aidev_agent.core.hook.registry import HookHandler, HookSet

__all__ = ["HookRunner"]

logger = logging.getLogger(__name__)


def _handler_id(handler: HookHandler) -> str:
    """处理器标识：优先限定名，用于结构化日志与隔离断言。"""
    return getattr(handler, "__qualname__", None) or getattr(handler, "__name__", None) or type(handler).__name__


def _runtime_config(request: ToolCallRequest) -> Any:
    return getattr(getattr(request, "runtime", None), "config", None)


def _identity(config: Any) -> HookIdentity:
    """从 RunnableConfig 解析本轮标识：agent_code / session_code / turn_id。

    ``thread_id`` 是本轮会话（resume 时与中断前一致），``execute_kwargs`` 提供本轮 turn_id；
    两者缺省时留空，不阻断处理器执行。
    """
    configurable = (config or {}).get("configurable") or {} if isinstance(config, dict) else {}
    execute_kwargs = configurable.get("execute_kwargs")
    return HookIdentity(
        agent_code=str(getattr(execute_kwargs, "agent_code", "") or ""),
        session_code=str(configurable.get("thread_id") or getattr(execute_kwargs, "session_code", "") or ""),
        turn_id=str(getattr(execute_kwargs, "turn_id", "") or ""),
    )


class HookRunner:
    """持有处理器集合并提供 6 个点位入口。"""

    TIMEOUT_SECONDS = 5.0

    def __init__(self, handlers: HookSet | None = None) -> None:
        self._handlers = handlers or HookSet()

    # ------------------------------------------------------------------
    # 点位入口
    # ------------------------------------------------------------------
    def turn_start(self, config: Any, messages: list[BaseMessage]) -> list[BaseMessage] | None:
        """``turn_start``：收到用户请求、开始处理前触发；可返回新的消息列表。"""
        return self._apply_message_list(HookPoint.TURN_START, config, messages)

    def model_pre(self, ctx: Any) -> None:
        """``model_pre``：每次模型链调用前触发，入参是模型调用的 ``ProcessorContext``。

        处理器可直接改 ``ctx.messages``，也可返回新列表；两者都会成为本次发送内容。
        """
        for handler in self._handlers.handlers(HookPoint.MODEL_PRE):
            result = self._invoke(HookPoint.MODEL_PRE, ctx.config, ctx, handler)
            if isinstance(result, list):
                ctx.messages = result
            elif result is not None:
                self._invalid(HookPoint.MODEL_PRE, handler, "list[BaseMessage]")

    def model_post(self, ctx: Any) -> None:
        """``model_post``：每次模型调用成功后触发，入参是模型调用的 ``ProcessorContext``。

        处理器可直接改 ``ctx.response``，也可返回新 ``AIMessage``；抛 ``HookRetry`` 要求重新调用模型。
        """
        for handler in self._handlers.handlers(HookPoint.MODEL_POST):
            result = self._invoke(HookPoint.MODEL_POST, ctx.config, ctx, handler)
            if isinstance(result, AIMessage):
                ctx.response = result
            elif result is not None:
                self._invalid(HookPoint.MODEL_POST, handler, "AIMessage")

    def tool_pre(self, request: ToolCallRequest) -> ToolCallRequest | ToolMessage | Command:
        """``tool_pre``：每次工具调用前触发。

        返回 ``ToolMessage`` / ``Command`` 时直接作为工具结果返回，工具不再执行；
        返回 ``ToolCallRequest`` 时按改写后的请求执行。
        """
        config = _runtime_config(request)
        current = request
        for handler in self._handlers.handlers(HookPoint.TOOL_PRE):
            result = self._invoke(HookPoint.TOOL_PRE, config, current, handler)
            if isinstance(result, (ToolMessage, Command)):
                return result
            if isinstance(result, ToolCallRequest):
                current = result
            elif result is not None:
                self._invalid(HookPoint.TOOL_PRE, handler, "ToolCallRequest | ToolMessage | Command")
        return current

    def tool_post(self, config: Any, message: ToolMessage) -> ToolMessage | None:
        """``tool_post``：每次工具调用后触发；可返回新的 ``ToolMessage``。"""
        return self._apply_object(HookPoint.TOOL_POST, config, message, ToolMessage)

    def turn_end(self, config: Any) -> None:
        """``turn_end``：本轮走到终点时触发，返回值忽略。"""
        for handler in self._handlers.handlers(HookPoint.TURN_END):
            self._invoke(HookPoint.TURN_END, config, None, handler)

    # ------------------------------------------------------------------
    # 结果合并
    # ------------------------------------------------------------------
    def _apply_message_list(
        self, point: HookPoint, config: Any, messages: list[BaseMessage]
    ) -> list[BaseMessage] | None:
        current = messages
        for handler in self._handlers.handlers(point):
            result = self._invoke(point, config, current, handler)
            if result is None:
                continue
            if not isinstance(result, list):
                self._invalid(point, handler, "list[BaseMessage]")
                continue
            current = result
        return None if current is messages else current

    def _apply_object(self, point: HookPoint, config: Any, value: Any, expected: type) -> Any:
        current = value
        for handler in self._handlers.handlers(point):
            result = self._invoke(point, config, current, handler)
            if result is None:
                continue
            if not isinstance(result, expected):
                self._invalid(point, handler, expected.__name__)
                continue
            current = result
        return None if current is value else current

    # ------------------------------------------------------------------
    # 低层执行
    # ------------------------------------------------------------------
    def _invoke(self, point: HookPoint, config: Any, payload: Any, handler: HookHandler) -> Any:
        context = HookContext(point=point, identity=_identity(config), payload=payload)
        started = time.monotonic()
        try:
            result = self._call_with_timeout(handler, context)
        except (HookAbort, HookRetry) as error:
            self._log(point, context.identity, handler, type(error).__name__, started)
            raise
        except TimeoutError:
            self._log(point, context.identity, handler, "timeout", started)
            return None
        except Exception:
            logger.warning(
                "[Hook] degraded point=%s handler=%s reason=exception",
                point.value,
                _handler_id(handler),
                exc_info=True,
            )
            self._log(point, context.identity, handler, "exception", started)
            return None
        self._log(point, context.identity, handler, "ok", started)
        return result

    @classmethod
    def _call_with_timeout(cls, handler: HookHandler, context: HookContext) -> Any:
        """在独立线程执行处理器，超过 ``TIMEOUT_SECONDS`` 按超时处理。

        线程无法被强杀：超时后仅放弃等待（fail-open 保证业务不受影响）。线程内以
        ``copy_context().run`` 执行，处理器可见调用方的 contextvars（追踪等）。
        """
        box: dict[str, Any] = {}

        def invoke() -> None:
            try:
                box["value"] = cls._resolve_awaitable(handler(context))
            except Exception as error:  # noqa: BLE001 - 原样回传给等待线程；BaseException 不穿透 fail-open
                box["error"] = error

        thread = threading.Thread(target=copy_context().run, args=(invoke,), name="aidev-hook-handler", daemon=True)
        thread.start()
        thread.join(cls.TIMEOUT_SECONDS)
        if thread.is_alive():
            raise TimeoutError(f"hook handler exceeded {cls.TIMEOUT_SECONDS}s")
        if "error" in box:
            raise box["error"]
        return box.get("value")

    @staticmethod
    def _resolve_awaitable(value: Any) -> Any:
        """同步线程里遇到协程处理器时，用独立事件循环执行。"""
        if not inspect.isawaitable(value):
            return value

        async def consume() -> Any:
            return await value

        return asyncio.run(consume())

    @staticmethod
    def _invalid(point: HookPoint, handler: HookHandler, expected: str) -> None:
        logger.warning(
            "[Hook] ignored point=%s handler=%s reason=invalid_result expected=%s",
            point.value,
            _handler_id(handler),
            expected,
        )

    @staticmethod
    def _log(point: HookPoint, identity: HookIdentity, handler: HookHandler, status: str, started: float) -> None:
        logger.info(
            "[Hook] point=%s handler=%s status=%s duration_ms=%s agent=%s session=%s turn=%s",
            point.value,
            _handler_id(handler),
            status,
            int((time.monotonic() - started) * 1000),
            identity.agent_code,
            identity.session_code,
            identity.turn_id,
        )
