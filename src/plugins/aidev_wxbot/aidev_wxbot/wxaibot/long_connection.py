"""企业微信机器人长连接接入服务。"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import os
import re
import signal
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from logging import getLogger
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from aibot import WSClient, WSClientOptions
from django.conf import settings

from .constants import WS_INSTANCE_LOCK_CACHE_KEY_PREFIX
from .context import THINKING_MSG, LlmChunkMsg
from .views import WxAiBotViewSet
from ..utils.rabbitmq import rabbitmq_client

logger = getLogger(__name__)


class LongConnectionConfigError(ValueError):
    """长连接配置缺失或非法。"""


class LongConnectionInstanceLockError(RuntimeError):
    """长连接实例锁获取失败。"""


class ServiceState(StrEnum):
    """长连接服务生命周期状态。"""

    INITIALIZED = "initialized"
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class SingleInstanceGuard:
    """基于本地文件锁的单活实例锁。"""

    def __init__(self, lock_key: str):
        self._lock_key = lock_key
        self._token = f"{os.getpid()}:{threading.get_native_id()}:{time.time()}"
        safe_lock_key = re.sub(r"[^A-Za-z0-9_.-]", "_", lock_key)
        self._lock_file_path = Path(gettempdir()) / f"{safe_lock_key}.lock"
        self._lock_file: Any | None = None

    def acquire(self) -> None:
        self._lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self._lock_file_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            holder = self._read_lock_file_holder(lock_file)
            lock_file.close()
            raise LongConnectionInstanceLockError(
                f"长连接实例锁已被占用: key={self._lock_key}, holder={holder}"
            ) from error

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(self._token)
        lock_file.flush()
        os.fsync(lock_file.fileno())
        self._lock_file = lock_file

    def release(self) -> None:
        if self._lock_file:
            with contextlib.suppress(OSError):
                self._lock_file.seek(0)
                self._lock_file.truncate()
                self._lock_file.flush()
            with contextlib.suppress(OSError):
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            with contextlib.suppress(OSError):
                self._lock_file.close()
            self._lock_file = None

    @staticmethod
    def _read_lock_file_holder(lock_file: Any) -> str:
        with contextlib.suppress(OSError):
            lock_file.seek(0)
            return lock_file.read().strip()
        return ""


@dataclass(slots=True)
class WxAiBotLongConnectionConfig:
    bot_id: str
    secret: str
    ws_url: str = ""
    reconnect_interval_ms: int = 1000
    max_reconnect_attempts: int = -1
    heartbeat_interval_ms: int = 30000
    request_timeout_ms: int = 10000
    single_instance_enabled: bool = True
    startup_timeout_sec: int = 30
    shutdown_grace_period_sec: int = 10

    @classmethod
    def from_settings(cls, **overrides: Any) -> "WxAiBotLongConnectionConfig":
        max_reconnect_attempts = overrides.get("max_reconnect_attempts")
        config = cls(
            bot_id=overrides.get("bot_id") or getattr(settings, "WXAIBOT_WS_BOT_ID", ""),
            secret=overrides.get("secret") or getattr(settings, "WXAIBOT_WS_SECRET", ""),
            ws_url=overrides.get("ws_url") or getattr(settings, "WXAIBOT_WS_URL", ""),
            reconnect_interval_ms=int(
                overrides.get("reconnect_interval_ms") or getattr(settings, "WXAIBOT_WS_RECONNECT_INTERVAL_MS", 1000)
            ),
            max_reconnect_attempts=int(
                max_reconnect_attempts
                if max_reconnect_attempts is not None
                else getattr(settings, "WXAIBOT_WS_MAX_RECONNECT_ATTEMPTS", -1)
            ),
            heartbeat_interval_ms=int(
                overrides.get("heartbeat_interval_ms") or getattr(settings, "WXAIBOT_WS_HEARTBEAT_INTERVAL_MS", 30000)
            ),
            request_timeout_ms=int(
                overrides.get("request_timeout_ms") or getattr(settings, "WXAIBOT_WS_REQUEST_TIMEOUT_MS", 10000)
            ),
            single_instance_enabled=bool(getattr(settings, "WXAIBOT_WS_SINGLE_INSTANCE_ENABLED", True)),
            startup_timeout_sec=int(getattr(settings, "WXAIBOT_WS_STARTUP_TIMEOUT_SEC", 30)),
            shutdown_grace_period_sec=int(getattr(settings, "WXAIBOT_WS_SHUTDOWN_GRACE_PERIOD_SEC", 10)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.bot_id:
            raise LongConnectionConfigError("缺少企微长连接配置: BKAPP_WXAIBOT_WS_BOT_ID")
        if not self.secret:
            raise LongConnectionConfigError("缺少企微长连接配置: BKAPP_WXAIBOT_WS_SECRET")
        if self.reconnect_interval_ms <= 0:
            raise LongConnectionConfigError("WXAIBOT_WS_RECONNECT_INTERVAL_MS 必须大于 0")
        if self.heartbeat_interval_ms <= 0:
            raise LongConnectionConfigError("WXAIBOT_WS_HEARTBEAT_INTERVAL_MS 必须大于 0")
        if self.request_timeout_ms <= 0:
            raise LongConnectionConfigError("WXAIBOT_WS_REQUEST_TIMEOUT_MS 必须大于 0")
        if self.startup_timeout_sec <= 0:
            raise LongConnectionConfigError("WXAIBOT_WS_STARTUP_TIMEOUT_SEC 必须大于 0")
        if self.shutdown_grace_period_sec <= 0:
            raise LongConnectionConfigError("WXAIBOT_WS_SHUTDOWN_GRACE_PERIOD_SEC 必须大于 0")


class WxAiBotLongConnectionService:
    """通过官方 Python SDK 建立企微机器人长连接，并复用现有消息处理逻辑。"""

    def __init__(self, config: WxAiBotLongConnectionConfig | None = None):
        self._config = config or WxAiBotLongConnectionConfig.from_settings()
        self._view = WxAiBotViewSet()
        self._stream_tasks: dict[str, asyncio.Task[None]] = {}
        self._instance_guard: SingleInstanceGuard | None = None
        self._signal_handlers: dict[int, Any] = {}
        self._state_lock = threading.Lock()
        self._service_state = ServiceState.INITIALIZED
        self._shutdown_requested = False
        self._accepting_messages = True
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self._authenticated_event: asyncio.Event | None = None
        self._startup_failed_event: asyncio.Event | None = None
        self._startup_error: Exception | None = None
        self._frame_semaphore = asyncio.Semaphore(int(getattr(settings, "WXAIBOT_WS_MAX_INFLIGHT_FRAMES", 16)))
        self._client = WSClient(
            WSClientOptions(
                bot_id=self._config.bot_id,
                secret=self._config.secret,
                reconnect_interval=self._config.reconnect_interval_ms,
                max_reconnect_attempts=self._config.max_reconnect_attempts,
                heartbeat_interval=self._config.heartbeat_interval_ms,
                request_timeout=self._config.request_timeout_ms,
                ws_url=self._config.ws_url,
                logger=logger,
            )
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._client.on("authenticated")
        def _on_authenticated() -> None:
            self._set_service_state(ServiceState.READY)
            logger.info("[WxAiBot-WS] 长连接认证成功")
            self._set_async_event(self._authenticated_event)

        @self._client.on("disconnected")
        def _on_disconnected(reason: str) -> None:
            if not self._shutdown_requested:
                self._set_service_state(ServiceState.DISCONNECTED, reason)
            logger.warning("[WxAiBot-WS] 长连接断开: %s", reason)

        @self._client.on("reconnecting")
        def _on_reconnecting(attempt: int) -> None:
            self._set_service_state(ServiceState.RECONNECTING, f"attempt={attempt}")
            logger.warning("[WxAiBot-WS] 尝试重连，第 %s 次", attempt)

        @self._client.on("error")
        def _on_error(error: Exception) -> None:
            logger.error("[WxAiBot-WS] SDK 错误: %s", error)
            error_message = str(error)
            if self._authenticated_event and not self._authenticated_event.is_set():
                self._mark_startup_failure(RuntimeError(f"长连接启动失败: {error_message}"))
                return
            if "Max reconnect attempts exceeded" in error_message:
                self._mark_startup_failure(RuntimeError(f"长连接重连次数耗尽: {error_message}"))

        @self._client.on("message")
        async def _on_message(frame: dict[str, Any]) -> None:
            await self._handle_frame(frame)

        @self._client.on("event")
        async def _on_event(frame: dict[str, Any]) -> None:
            await self._handle_frame(frame)

        @self._client.on("event.disconnected_event")
        async def _on_disconnected_event(frame: dict[str, Any]) -> None:
            logger.warning(
                "[WxAiBot-WS] 收到 disconnected_event，通常表示存在另一个同 BotID 的连接: %s",
                frame,
            )
            self._mark_startup_failure(RuntimeError("收到 disconnected_event，连接被同 BotID 的其他连接顶掉"))

    def run(self) -> None:
        logger.info("[WxAiBot-WS] 启动长连接服务")
        runtime_initialized = False
        try:
            self._setup_runtime()
            runtime_initialized = True
            self._loop.run_until_complete(self._start_client())
            self._set_service_state(ServiceState.RUNNING)
            self._loop.run_forever()
        finally:
            if runtime_initialized:
                self._teardown_runtime()

        if self._startup_error:
            raise self._startup_error

    def _setup_runtime(self) -> None:
        self._acquire_instance_guard()
        self._register_signal_handlers()
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._authenticated_event = asyncio.Event()
        self._startup_failed_event = asyncio.Event()

    def _teardown_runtime(self) -> None:
        self._close_event_loop()
        self._cleanup_runtime()

    async def _start_client(self) -> None:
        self._set_service_state(ServiceState.STARTING)
        await self._client.connect()
        await self._wait_for_startup()

    async def _wait_for_startup(self) -> None:
        if not self._authenticated_event or not self._startup_failed_event:
            raise RuntimeError("长连接启动状态未初始化")

        authenticated_task = asyncio.create_task(self._authenticated_event.wait())
        failed_task = asyncio.create_task(self._startup_failed_event.wait())
        done, pending = await asyncio.wait(
            {authenticated_task, failed_task},
            timeout=self._config.startup_timeout_sec,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for pending_task in pending:
            pending_task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        if failed_task in done:
            raise self._startup_error or RuntimeError("长连接启动失败")

        if authenticated_task not in done:
            timeout_error = RuntimeError(f"长连接在 {self._config.startup_timeout_sec}s 内未完成认证")
            self._startup_error = timeout_error
            with contextlib.suppress(Exception):
                self._client.disconnect()
            raise timeout_error

    async def _handle_frame(self, frame: dict[str, Any]) -> None:
        if self._shutdown_requested or not self._accepting_messages:
            logger.info("[WxAiBot-WS] 服务停机中，忽略新消息")
            return

        payload = frame.get("body") or {}
        if not payload:
            logger.warning("[WxAiBot-WS] 收到空帧，已忽略: %s", frame)
            return

        async with self._frame_semaphore:
            if self._shutdown_requested:
                return
            response = await asyncio.to_thread(self._view._reply_wxaibot, payload)
            await self._dispatch_response(frame, payload, response)

    async def _dispatch_response(
        self, frame: dict[str, Any], payload: dict[str, Any], response: dict[str, Any]
    ) -> None:
        msg_type = response.get("msgtype")
        if msg_type == "text":
            await self._reply_text(frame, payload, response)
            return

        if msg_type != "stream":
            await self._client.reply(frame, response)
            return

        stream = response.get("stream") or {}
        stream_id = stream.get("id", "")
        content = stream.get("content", "")
        finish = bool(stream.get("finish", False))

        if not stream_id:
            logger.warning("[WxAiBot-WS] 流式响应缺少 stream_id，已忽略: %s", response)
            return

        if not content:
            if finish:
                logger.debug("[WxAiBot-WS] 空结束帧跳过发送, stream_id=%s", stream_id)
                return
            logger.debug("[WxAiBot-WS] 空中间帧跳过发送, stream_id=%s", stream_id)
            self._start_stream_forwarder(frame, stream_id)
            return

        await self._send_stream_reply(frame, stream_id, content, finish)
        if not finish:
            self._start_stream_forwarder(frame, stream_id)

    async def _reply_text(self, frame: dict[str, Any], payload: dict[str, Any], response: dict[str, Any]) -> None:
        event_type = payload.get("event", {}).get("eventtype")
        if payload.get("msgtype") == "event" and event_type == "enter_chat":
            await self._client.reply_welcome(frame, response)
            return
        await self._client.reply(frame, response)

    def _start_stream_forwarder(self, frame: dict[str, Any], stream_id: str) -> None:
        existing_task = self._stream_tasks.get(stream_id)
        if existing_task and not existing_task.done():
            logger.debug("[WxAiBot-WS] stream forwarder 已存在, stream_id=%s", stream_id)
            return

        task = asyncio.create_task(self._forward_stream_replies(frame, stream_id))
        task.add_done_callback(lambda finished_task, sid=stream_id: self._cleanup_stream_task(sid, finished_task))
        self._stream_tasks[stream_id] = task

    def _cleanup_stream_task(self, stream_id: str, task: asyncio.Task[None]) -> None:
        self._stream_tasks.pop(stream_id, None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("[WxAiBot-WS] stream forwarder 异常退出, stream_id=%s, error=%s", stream_id, exc)

    async def _forward_stream_replies(self, frame: dict[str, Any], stream_id: str) -> None:
        last_signature: tuple[str, bool] | None = None

        while not self._shutdown_requested:
            response = await asyncio.to_thread(self._poll_stream_response, stream_id)
            stream = response.get("stream") or {}
            content = stream.get("content", "")
            finish = bool(stream.get("finish", False))
            signature = (content, finish)

            if content == THINKING_MSG:
                await asyncio.sleep(0.5)
                continue

            if not content:
                if finish:
                    return
                await asyncio.sleep(0.5)
                continue

            if signature == last_signature:
                await asyncio.sleep(0.5)
                continue

            last_signature = signature
            await self._send_stream_reply(frame, stream_id, content, finish)

            if finish:
                return

    @staticmethod
    def _poll_stream_response(stream_id: str) -> dict[str, Any]:
        return LlmChunkMsg(stream_id=stream_id).wxaibot_msg_json_from_cache(rabbitmq_client)

    async def _send_stream_reply(self, frame: dict[str, Any], stream_id: str, content: str, finish: bool) -> None:
        deadline = time.monotonic() + getattr(settings, "MAX_MESSAGE_TIME", 300)
        last_error: Exception | None = None

        while time.monotonic() < deadline:
            if self._shutdown_requested and not self._client.is_connected:
                raise asyncio.CancelledError()
            if not self._client.is_connected:
                await asyncio.sleep(1)
                continue

            try:
                await self._client.reply_stream(frame, stream_id, content, finish)
                return
            except Exception as error:
                last_error = error
                logger.warning(
                    "[WxAiBot-WS] 发送流式消息失败，等待重试 | stream_id=%s finish=%s error=%s",
                    stream_id,
                    finish,
                    error,
                )
                await asyncio.sleep(1)

        raise RuntimeError(f"stream_id={stream_id} 在重连窗口内未能发送成功，最后错误: {last_error}")

    def _acquire_instance_guard(self) -> None:
        if not self._config.single_instance_enabled:
            return

        lock_key = f"{WS_INSTANCE_LOCK_CACHE_KEY_PREFIX}{self._config.bot_id}"
        self._instance_guard = SingleInstanceGuard(lock_key=lock_key)
        self._instance_guard.acquire()
        logger.info("[WxAiBot-WS] 已获取单活实例锁: %s", lock_key)

    def _register_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._signal_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        signal_name = signal.Signals(signum).name
        logger.warning("[WxAiBot-WS] 收到退出信号: %s", signal_name)
        self._request_shutdown(signal_name)

    def _request_shutdown(self, reason: str) -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._accepting_messages = False
        logger.warning("[WxAiBot-WS] 开始优雅停机: %s", reason)
        self._set_service_state(ServiceState.STOPPING, reason)
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._ensure_shutdown_task, reason)
            return
        with contextlib.suppress(Exception):
            self._client.disconnect()

    def _ensure_shutdown_task(self, reason: str) -> None:
        if self._shutdown_task and not self._shutdown_task.done():
            return
        self._shutdown_task = asyncio.create_task(self._shutdown_async(reason))

    async def _shutdown_async(self, reason: str) -> None:
        logger.info("[WxAiBot-WS] 执行停机清理: %s", reason)
        with contextlib.suppress(Exception):
            self._client.disconnect()

        waiters: list[asyncio.Future[Any] | asyncio.Task[Any] | Any] = [self._client.wait_for_complete()]
        active_stream_tasks = [task for task in self._stream_tasks.values() if not task.done()]
        if active_stream_tasks:
            waiters.append(asyncio.gather(*active_stream_tasks, return_exceptions=True))

        try:
            await asyncio.wait_for(
                asyncio.gather(*waiters, return_exceptions=True),
                timeout=self._config.shutdown_grace_period_sec,
            )
        except asyncio.TimeoutError:
            logger.warning("[WxAiBot-WS] 优雅停机等待超时，开始强制取消未完成任务")
        finally:
            await self._cancel_stream_tasks()
            self._set_service_state(ServiceState.STOPPED)
            asyncio.get_running_loop().stop()

    async def _cancel_stream_tasks(self) -> None:
        active_tasks = [task for task in self._stream_tasks.values() if not task.done()]
        for stream_id, task in list(self._stream_tasks.items()):
            if task.done():
                continue
            task.cancel()
            logger.info("[WxAiBot-WS] 取消 stream forwarder: %s", stream_id)
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)

    def _mark_startup_failure(self, error: Exception) -> None:
        if self._startup_error is None:
            self._startup_error = error
        self._set_service_state(ServiceState.FAILED, str(error))
        self._set_async_event(self._startup_failed_event)
        self._request_shutdown(str(error))

    def _set_async_event(self, event: asyncio.Event | None) -> None:
        if event is None:
            return
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(event.set)

    def _set_service_state(self, state: ServiceState, detail: str = "") -> None:
        with self._state_lock:
            changed = self._service_state != state
            self._service_state = state
        if changed or detail:
            if detail:
                logger.info("[WxAiBot-WS] 服务状态 => %s (%s)", state, detail)
            else:
                logger.info("[WxAiBot-WS] 服务状态 => %s", state)

    def _close_event_loop(self) -> None:
        if not self._loop:
            return

        pending_tasks = [task for task in asyncio.all_tasks(self._loop) if not task.done()]
        for task in pending_tasks:
            task.cancel()
        if pending_tasks:
            self._loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
        self._loop.close()
        asyncio.set_event_loop(None)
        self._loop = None

    def _cleanup_runtime(self) -> None:
        self._stream_tasks.clear()
        self._shutdown_task = None
        self._authenticated_event = None
        self._startup_failed_event = None

        for sig, handler in self._signal_handlers.items():
            signal.signal(sig, handler)
        self._signal_handlers.clear()

        if self._instance_guard:
            self._instance_guard.release()
            self._instance_guard = None
