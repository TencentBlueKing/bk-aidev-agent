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
from collections import deque
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from enum import StrEnum
from logging import getLogger
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from aibot import WSClient, WSClientOptions
from django.conf import settings

from .constants import WS_INSTANCE_LOCK_CACHE_KEY_PREFIX
from .context import THINKING_MSG
from .direct_stream import DirectStreamFrame, iter_direct_stream_frames
from .execution import get_agent_executor, get_agent_executor_snapshot
from .strategies import WECOM_AGENT_RETRY_STRATEGY, resolve_strategy
from .stream_registry import stream_registry
from .views import WxAiBotViewSet, WxBotAgentRequest

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


@dataclass(slots=True)
class ActiveStream:
    frame: dict[str, Any]
    group_id: str
    task: asyncio.Task[None]
    cancel_event: threading.Event
    started_at: float


@dataclass(slots=True)
class PendingStream:
    frame: dict[str, Any]
    request: WxBotAgentRequest
    enqueued_at: float


@dataclass(slots=True)
class StreamMetrics:
    started: int = 0
    completed: int = 0
    cancelled: int = 0
    failed: int = 0
    first_frames: int = 0
    final_frames: int = 0
    first_frame_latency_total: float = 0.0
    final_frame_latency_total: float = 0.0
    send_wait_total: float = 0.0
    sent_frames: int = 0
    queued: int = 0
    dequeued: int = 0
    queue_rejected: int = 0
    peak_queued: int = 0
    queue_wait_total: float = 0.0


class _ProducerDone:
    pass


class _ProducerStarted:
    pass


_PRODUCER_DONE = _ProducerDone()
_PRODUCER_STARTED = _ProducerStarted()


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
        self._active_streams: dict[str, ActiveStream] = {}
        self._group_streams: dict[str, str] = {}
        self._group_pending_streams: dict[str, deque[PendingStream]] = {}
        self._queued_stream_ids: set[str] = set()
        self._metrics = StreamMetrics()
        self._instance_guard: SingleInstanceGuard | None = None
        self._signal_handlers: dict[int, Any] = {}
        self._state_lock = threading.Lock()
        self._service_state = ServiceState.INITIALIZED
        self._shutdown_requested = False
        self._accepting_messages = True
        self._draining_streams = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self._health_task: asyncio.Task[None] | None = None
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
            self._ensure_health_task()

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
            error_message = str(error)
            normalized_error = error_message.lower()
            if "max reconnect attempts exceeded" in normalized_error:
                logger.error("event=wxbot_ws_error kind=reconnect_exhausted error=%s", error_message)
                self._mark_startup_failure(RuntimeError(f"长连接重连次数耗尽: {error_message}"))
                return
            if "authentication failed" in normalized_error or "invalid credential" in normalized_error:
                logger.error("event=wxbot_ws_error kind=authentication error=%s", error_message)
                self._mark_startup_failure(RuntimeError(f"长连接认证失败: {error_message}"))
                return

            if self._authenticated_event and not self._authenticated_event.is_set():
                self._set_service_state(ServiceState.RECONNECTING, f"transient_startup_error={error_message}")
                logger.warning("event=wxbot_ws_error kind=transient_startup error=%s", error_message)
                return
            logger.error("event=wxbot_ws_error kind=runtime error=%s", error_message)

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

    def run(self, register_signal_handlers: bool = True) -> None:
        logger.info("[WxAiBot-WS] 启动长连接服务")
        runtime_initialized = False
        try:
            self._setup_runtime(register_signal_handlers=register_signal_handlers)
            runtime_initialized = True
            self._loop.run_until_complete(self._start_client())
            self._set_service_state(ServiceState.RUNNING)
            self._loop.run_forever()
        finally:
            if runtime_initialized:
                self._teardown_runtime()

        if self._startup_error:
            raise self._startup_error

    def _setup_runtime(self, register_signal_handlers: bool = True) -> None:
        self._acquire_instance_guard()
        if register_signal_handlers:
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
            if payload.get("msgtype") == "text":
                response, request = await asyncio.to_thread(self._view.prepare_agent_request, payload)
                if response is not None:
                    await self._dispatch_immediate_response(frame, payload, response)
                    return
                if request is not None:
                    await self._start_direct_stream(frame, request)
                return

            if payload.get("msgtype") == "stream":
                stream_id = (payload.get("stream") or {}).get("id", "")
                if stream_id:
                    await self._send_stream_reply(frame, stream_id, "长连接模式无需轮询流式结果", True)
                return

            response = await asyncio.to_thread(self._view._reply_wxaibot, payload)
            await self._dispatch_immediate_response(frame, payload, response)

    async def _dispatch_immediate_response(
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
            logger.debug("[WxAiBot-WS] 空 stream 帧跳过发送, stream_id=%s finish=%s", stream_id, finish)
            return

        await self._send_stream_reply(frame, stream_id, content, finish)

    async def _reply_text(self, frame: dict[str, Any], payload: dict[str, Any], response: dict[str, Any]) -> None:
        event_type = payload.get("event", {}).get("eventtype")
        if payload.get("msgtype") == "event" and event_type == "enter_chat":
            await self._client.reply_welcome(frame, response)
            return
        await self._client.reply(frame, response)

    async def _start_direct_stream(self, frame: dict[str, Any], request: WxBotAgentRequest) -> None:
        if request.stream_id in self._active_streams or request.stream_id in self._queued_stream_ids:
            logger.info("event=wxbot_ws_stream_duplicate stream_id=%s ignored=true", request.stream_id)
            return

        pending = self._group_pending_streams.get(request.group_id)
        if request.group_id in self._group_streams or pending:
            await self._enqueue_group_stream(frame, request)
            if request.group_id not in self._group_streams:
                self._start_next_group_stream(request.group_id)
            return

        self._launch_direct_stream(frame, request)

    async def _enqueue_group_stream(self, frame: dict[str, Any], request: WxBotAgentRequest) -> None:
        queue = self._group_pending_streams.setdefault(request.group_id, deque())
        queue_limit = max(1, int(getattr(settings, "WXAIBOT_WS_GROUP_QUEUE_SIZE", 10)))
        if len(queue) >= queue_limit:
            self._metrics.queue_rejected += 1
            logger.warning(
                "event=wxbot_ws_group_queue_rejected stream_id=%s group_id=%s queue_depth=%s queue_limit=%s",
                request.stream_id,
                request.group_id,
                len(queue),
                queue_limit,
            )
            await self._send_stream_reply(frame, request.stream_id, "当前会话排队请求已满，请稍后重试", True)
            return

        queue.append(PendingStream(frame=frame, request=request, enqueued_at=time.monotonic()))
        self._queued_stream_ids.add(request.stream_id)
        self._metrics.queued += 1
        total_queued = self._queued_stream_count()
        self._metrics.peak_queued = max(self._metrics.peak_queued, total_queued)
        logger.info(
            "event=wxbot_ws_group_stream_queued stream_id=%s group_id=%s group_queue_depth=%s queued_streams=%s",
            request.stream_id,
            request.group_id,
            len(queue),
            total_queued,
        )
        await self._send_stream_reply(
            frame,
            request.stream_id,
            f"当前会话正在处理上一条请求，已进入队列（前方 {len(queue)} 条）",
            False,
        )

    def _launch_direct_stream(self, frame: dict[str, Any], request: WxBotAgentRequest) -> None:
        cancel_event = threading.Event()
        task = asyncio.create_task(self._consume_direct_stream(frame, request, cancel_event))
        active = ActiveStream(
            frame=frame,
            group_id=request.group_id,
            task=task,
            cancel_event=cancel_event,
            started_at=time.monotonic(),
        )
        self._active_streams[request.stream_id] = active
        self._group_streams[request.group_id] = request.stream_id
        self._metrics.started += 1
        task.add_done_callback(lambda finished, sid=request.stream_id: self._cleanup_stream_task(sid, finished))
        logger.info(
            "event=wxbot_ws_stream_started stream_id=%s group_id=%s active_streams=%s",
            request.stream_id,
            request.group_id,
            len(self._active_streams),
        )

    def _start_next_group_stream(self, group_id: str) -> None:
        if self._shutdown_requested or self._draining_streams or group_id in self._group_streams:
            return
        queue = self._group_pending_streams.get(group_id)
        if not queue:
            self._group_pending_streams.pop(group_id, None)
            return

        pending = queue.popleft()
        self._queued_stream_ids.discard(pending.request.stream_id)
        if not queue:
            self._group_pending_streams.pop(group_id, None)
        queue_wait = time.monotonic() - pending.enqueued_at
        self._metrics.dequeued += 1
        self._metrics.queue_wait_total += queue_wait
        logger.info(
            "event=wxbot_ws_group_stream_dequeued stream_id=%s group_id=%s queue_wait_ms=%.3f queued_streams=%s",
            pending.request.stream_id,
            group_id,
            queue_wait * 1000,
            self._queued_stream_count(),
        )
        self._launch_direct_stream(pending.frame, pending.request)

    def _queued_stream_count(self) -> int:
        return sum(len(queue) for queue in self._group_pending_streams.values())

    async def _consume_direct_stream(
        self,
        frame: dict[str, Any],
        request: WxBotAgentRequest,
        cancel_event: threading.Event,
    ) -> None:
        queue_size = max(1, int(getattr(settings, "WXAIBOT_WS_STREAM_BUFFER_SIZE", 4)))
        output_queue: asyncio.Queue[DirectStreamFrame | Exception | _ProducerDone | _ProducerStarted] = asyncio.Queue(
            maxsize=queue_size
        )
        loop = asyncio.get_running_loop()
        submitted = get_agent_executor().submit(
            self._produce_direct_stream,
            request,
            loop,
            output_queue,
            cancel_event,
        )
        if not submitted:
            self._metrics.failed += 1
            await self._send_stream_reply(frame, request.stream_id, "当前请求较多，请稍后重试", True)
            return

        first_frame = True
        terminal_received = False
        try:
            queue_timeout = max(1, int(getattr(settings, "WXAIBOT_AGENT_QUEUE_TIMEOUT_SEC", 300)))
            started_item = await asyncio.wait_for(output_queue.get(), timeout=queue_timeout)
            if started_item is not _PRODUCER_STARTED:
                raise RuntimeError("Agent 执行器启动协议异常")
            timeout = max(1, int(getattr(settings, "WXAIBOT_WS_STREAM_TIMEOUT_SEC", settings.MAX_MESSAGE_TIME)))
            async with asyncio.timeout(timeout):
                while True:
                    item = await output_queue.get()
                    if item is _PRODUCER_DONE:
                        if not terminal_received:
                            raise RuntimeError("Agent 流未产生终态")
                        return
                    if isinstance(item, Exception):
                        raise item

                    send_wait = await self._send_stream_reply(
                        frame,
                        request.stream_id,
                        item.content or ("回答完成" if item.finish else THINKING_MSG),
                        item.finish,
                    )
                    now = time.monotonic()
                    sse_to_send = now - item.observed_at
                    self._metrics.send_wait_total += send_wait
                    self._metrics.sent_frames += 1
                    if first_frame:
                        first_frame = False
                        self._metrics.first_frames += 1
                        self._metrics.first_frame_latency_total += sse_to_send
                        phase = "first"
                    elif item.finish:
                        phase = "final"
                    else:
                        phase = "middle"
                    logger.info(
                        "event=wxbot_ws_stream_frame stream_id=%s phase=%s finish=%s "
                        "sse_to_wecom_ms=%.3f send_wait_ms=%.3f",
                        request.stream_id,
                        phase,
                        item.finish,
                        sse_to_send * 1000,
                        send_wait * 1000,
                    )
                    if item.finish:
                        terminal_received = True
                        self._metrics.final_frames += 1
                        if item.failed:
                            self._metrics.failed += 1
                        else:
                            self._metrics.completed += 1
                        self._metrics.final_frame_latency_total += sse_to_send
                        logger.info(
                            "event=wxbot_ws_stream_finished stream_id=%s failed=%s duration_ms=%.3f",
                            request.stream_id,
                            item.failed,
                            (now - self._active_streams[request.stream_id].started_at) * 1000,
                        )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._metrics.failed += 1
            logger.exception("event=wxbot_ws_stream_failed stream_id=%s error=%s", request.stream_id, error)
            if self._client.is_connected:
                with contextlib.suppress(Exception):
                    await self._send_stream_reply(frame, request.stream_id, f"请求处理失败: {error}", True)
        finally:
            if not terminal_received:
                stream_registry.cancel(request.stream_id)
            cancel_event.set()

    def _produce_direct_stream(
        self,
        request: WxBotAgentRequest,
        loop: asyncio.AbstractEventLoop,
        output_queue: asyncio.Queue,
        cancel_event: threading.Event,
    ) -> None:
        agent_stream = None
        try:
            if not self._put_from_worker(loop, output_queue, _PRODUCER_STARTED, cancel_event):
                return
            thread_id = self._view._get_or_create_thread_id(request.group_id)
            strategy = resolve_strategy(request.username)
            agent_stream = strategy.open_stream(
                content=request.content,
                username=request.username,
                thread_id=thread_id,
                group_id=request.group_id,
                retry_strategy=WECOM_AGENT_RETRY_STRATEGY,
            )
            stream_registry.register(request.stream_id, agent_stream.session_code)
            frames = iter_direct_stream_frames(
                agent_stream,
                request.stream_id,
                on_run_started=lambda run_id: stream_registry.set_run_id(request.stream_id, run_id),
            )
            for stream_frame in frames:
                if cancel_event.is_set() or stream_registry.is_cancel_requested(request.stream_id):
                    break
                if not self._put_from_worker(loop, output_queue, stream_frame, cancel_event):
                    break
        except Exception as error:
            if not cancel_event.is_set():
                self._put_from_worker(loop, output_queue, error, cancel_event)
        finally:
            if agent_stream is not None and hasattr(agent_stream.generator, "close"):
                with contextlib.suppress(Exception):
                    agent_stream.generator.close()
            stream_registry.unregister(request.stream_id)
            if not cancel_event.is_set():
                self._put_from_worker(loop, output_queue, _PRODUCER_DONE, cancel_event)

    @staticmethod
    def _put_from_worker(
        loop: asyncio.AbstractEventLoop,
        output_queue: asyncio.Queue,
        item: Any,
        cancel_event: threading.Event,
    ) -> bool:
        if cancel_event.is_set() or loop.is_closed():
            return False
        future = asyncio.run_coroutine_threadsafe(output_queue.put(item), loop)
        while not cancel_event.is_set():
            try:
                future.result(timeout=0.1)
                return True
            except FutureTimeoutError:
                continue
            except Exception:
                return False
        future.cancel()
        return False

    def _cleanup_stream_task(self, stream_id: str, task: asyncio.Task[None]) -> None:
        active = self._active_streams.get(stream_id)
        if active is not None and active.task is task:
            self._active_streams.pop(stream_id, None)
            if self._group_streams.get(active.group_id) == stream_id:
                self._group_streams.pop(active.group_id, None)
            self._start_next_group_stream(active.group_id)
        if task.cancelled():
            return
        if error := task.exception():
            logger.error("event=wxbot_ws_stream_task_failed stream_id=%s error=%s", stream_id, error)

    async def _cancel_active_stream(
        self,
        stream_id: str,
        *,
        reason: str,
        terminal_content: str | None = None,
    ) -> None:
        active = self._active_streams.get(stream_id)
        if active is None:
            return
        active.cancel_event.set()
        stream_registry.cancel(stream_id)
        active.task.cancel()
        await asyncio.gather(active.task, return_exceptions=True)
        self._metrics.cancelled += 1
        logger.info("event=wxbot_ws_stream_cancelled stream_id=%s reason=%s", stream_id, reason)
        if terminal_content:
            with contextlib.suppress(Exception):
                await self._send_stream_reply(active.frame, stream_id, terminal_content, True)

    async def _send_stream_reply(self, frame: dict[str, Any], stream_id: str, content: str, finish: bool) -> float:
        started_at = time.monotonic()
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
                return time.monotonic() - started_at
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

    def _ensure_health_task(self) -> None:
        if not self._loop or not self._loop.is_running():
            return
        self._loop.call_soon_threadsafe(self._start_health_task)

    def _start_health_task(self) -> None:
        interval = int(getattr(settings, "WXAIBOT_WS_HEALTH_LOG_INTERVAL_SEC", 60))
        if interval <= 0 or self._shutdown_requested:
            return
        if self._health_task and not self._health_task.done():
            return
        self._health_task = asyncio.create_task(self._log_health_periodically(interval))

    async def _log_health_periodically(self, interval: int) -> None:
        while not self._shutdown_requested:
            self._log_health()
            await asyncio.sleep(interval)

    def _log_health(self) -> None:
        executor = get_agent_executor_snapshot()
        queued_streams = self._queued_stream_count()
        final_frames = max(1, self._metrics.final_frames)
        first_frames = max(1, self._metrics.first_frames)
        sent_frames = max(1, self._metrics.sent_frames)
        logger.info(
            "event=wxbot_ws_health state=%s connected=%s accepting=%s active_streams=%s queued_streams=%s "
            "agent_active=%s agent_pending=%s agent_workers=%s agent_pending_limit=%s agent_capacity=%s "
            "agent_submitted=%s agent_rejected=%s agent_peak_active=%s agent_peak_pending=%s "
            "streams_started=%s streams_completed=%s "
            "streams_cancelled=%s streams_failed=%s streams_queued=%s streams_dequeued=%s "
            "queue_rejected=%s peak_queued=%s avg_queue_wait_ms=%.3f "
            "avg_first_frame_ms=%.3f avg_final_frame_ms=%.3f avg_send_wait_ms=%.3f",
            self._service_state,
            bool(getattr(self._client, "is_connected", False)),
            self._accepting_messages,
            len(self._active_streams),
            queued_streams,
            executor.active,
            executor.pending,
            executor.max_workers,
            executor.max_pending,
            executor.capacity,
            executor.submitted,
            executor.rejected,
            executor.peak_active,
            executor.peak_pending,
            self._metrics.started,
            self._metrics.completed,
            self._metrics.cancelled,
            self._metrics.failed,
            self._metrics.queued,
            self._metrics.dequeued,
            self._metrics.queue_rejected,
            self._metrics.peak_queued,
            self._metrics.queue_wait_total / max(1, self._metrics.dequeued) * 1000,
            self._metrics.first_frame_latency_total / first_frames * 1000,
            self._metrics.final_frame_latency_total / final_frames * 1000,
            self._metrics.send_wait_total / sent_frames * 1000,
        )

    async def _shutdown_async(self, reason: str) -> None:
        logger.info("[WxAiBot-WS] 执行停机清理: %s", reason)
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
        await self._cancel_stream_tasks(terminal_content="服务正在停机，当前请求已取消")
        with contextlib.suppress(Exception):
            self._client.disconnect()

        waiters: list[asyncio.Future[Any] | asyncio.Task[Any] | Any] = [self._wait_for_client_disconnected()]

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

    async def _wait_for_client_disconnected(self) -> None:
        while self._client.is_connected:
            await asyncio.sleep(0.1)

    async def _cancel_stream_tasks(self, terminal_content: str | None = None) -> None:
        self._draining_streams = True
        for stream_id in list(self._active_streams):
            await self._cancel_active_stream(
                stream_id,
                reason="service_shutdown",
                terminal_content=terminal_content,
            )
        await self._cancel_pending_streams(terminal_content)

    async def _cancel_pending_streams(self, terminal_content: str | None = None) -> None:
        pending_streams = [pending for queue in self._group_pending_streams.values() for pending in queue]
        self._group_pending_streams.clear()
        self._queued_stream_ids.clear()
        self._metrics.cancelled += len(pending_streams)
        for pending in pending_streams:
            logger.info(
                "event=wxbot_ws_stream_cancelled stream_id=%s reason=service_shutdown state=queued",
                pending.request.stream_id,
            )
            if terminal_content:
                with contextlib.suppress(Exception):
                    await self._send_stream_reply(
                        pending.frame,
                        pending.request.stream_id,
                        terminal_content,
                        True,
                    )

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
            previous_state = self._service_state
            changed = self._service_state != state
            self._service_state = state
        if changed or detail:
            logger.info(
                "event=wxbot_ws_state previous=%s current=%s connected=%s accepting=%s active_streams=%s detail=%s",
                previous_state,
                state,
                bool(getattr(self._client, "is_connected", False)),
                self._accepting_messages,
                len(self._active_streams),
                detail,
            )

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
        self._active_streams.clear()
        self._group_streams.clear()
        self._group_pending_streams.clear()
        self._queued_stream_ids.clear()
        self._shutdown_task = None
        self._health_task = None
        self._authenticated_event = None
        self._startup_failed_event = None

        for sig, handler in self._signal_handlers.items():
            signal.signal(sig, handler)
        self._signal_handlers.clear()

        if self._instance_guard:
            self._instance_guard.release()
            self._instance_guard = None
