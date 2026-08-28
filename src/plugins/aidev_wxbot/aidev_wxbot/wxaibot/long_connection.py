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
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from enum import StrEnum
from logging import getLogger
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from aibot import WSClient, WSClientOptions
from aidev_agent.utils.tracing import recording_span
from aidev_bkplugin.services.execution import get_agent_executor, get_agent_executor_snapshot
from django.conf import settings

from .constants import (
    AGENT_STREAM_DRAIN_TIMEOUT,
    BUSY_BY_OTHERS_REPLY,
    BUSY_REPLY,
    PREPARING_REPLY,
    STOP_NO_ACTIVE_REPLY,
    STOP_NOTICE,
    STOP_REPLY,
    STREAM_ERROR_REPLY,
    WS_INSTANCE_LOCK_CACHE_KEY_PREFIX,
)
from .context import THINKING_MSG, stream_msg
from .direct_stream import DirectStreamFrame, iter_direct_stream_frames
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
    username: str
    task: asyncio.Task[None]
    cancel_event: threading.Event
    started_at: float
    # 最后一次发给企微的全量快照。中止时要带上它重发，否则用户已经看到的半截回答会被抹掉
    last_content: str = ""


@dataclass(slots=True)
class StreamMetrics:
    started: int = 0
    completed: int = 0
    approval_pending: int = 0
    cancelled: int = 0
    failed: int = 0
    first_frames: int = 0
    final_frames: int = 0
    first_frame_latency_total: float = 0.0
    final_frame_latency_total: float = 0.0
    send_wait_total: float = 0.0
    sent_frames: int = 0
    rejected_busy: int = 0


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


class _LongConnectionViewSet(WxAiBotViewSet):
    """把 /stop、/new 接到长连接的活跃流登记簿上，并把会话作用域收敛到人。

    命令解析仍复用基类，长连接只覆写「需要中止在跑的流」这两个动作；HTTP 回调
    继续用基类实现，行为不变。
    """

    def __init__(self, service: "WxAiBotLongConnectionService"):
        super().__init__()
        self._service = service

    def _session_scope(self, group_id: str, username: str) -> str:
        """群聊里会话按人轮换。

        上下文本来就是每人一份——平台侧的 session_code 是 MD5(username:agent_code:thread_id)，
        username 参与了哈希。但 thread_id 原先只按群存一行，于是一个人 /new 会把全群
        每个人的上下文一起清掉，30 分钟超时也被别人的活跃度顺带续期。
        单聊的 group_id 就是发起人本身，不必再拼一次。
        """
        return group_id if group_id == username else f"{group_id}:{username}"

    def stop_generation(self, group_id: str, username: str, stream_id: str) -> dict:
        stopped = self._service.request_stop(group_id, username, reason="user_stop")
        return stream_msg(STOP_REPLY if stopped else STOP_NO_ACTIVE_REPLY, True, stream_id)

    def _new_conversation(self, group_id: str, username: str, stream_id: str) -> dict:
        # 开新会话时旧回复还在推，用户会看到两个气泡同时动，先把旧的收掉
        self._service.request_stop(group_id, username, reason="new_conversation")
        return super()._new_conversation(group_id, username, stream_id)


class WxAiBotLongConnectionService:
    """通过官方 Python SDK 建立企微机器人长连接，并复用现有消息处理逻辑。"""

    def __init__(self, config: WxAiBotLongConnectionConfig | None = None):
        self._config = config or WxAiBotLongConnectionConfig.from_settings()
        self._view = _LongConnectionViewSet(self)
        self._active_streams: dict[str, ActiveStream] = {}
        self._group_streams: dict[str, str] = {}
        self._metrics = StreamMetrics()
        self._instance_guard: SingleInstanceGuard | None = None
        self._signal_handlers: dict[int, Any] = {}
        self._state_lock = threading.Lock()
        self._service_state = ServiceState.INITIALIZED
        self._shutdown_requested = False
        self._accepting_messages = True
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
            authenticated_before = bool(self._authenticated_event and self._authenticated_event.is_set())
            self._set_service_state(ServiceState.RUNNING if authenticated_before else ServiceState.READY)
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
        if request.stream_id in self._active_streams:
            logger.info("event=wxbot_ws_stream_duplicate stream_id=%s ignored=true", request.stream_id)
            return

        # 同一个群只允许一条流。排队会让用户等一段没有反馈的时间，且拿到的回答未必还
        # 切题；直接拒绝并告诉他怎么办，比默默排队更好。
        if active_stream_id := self._group_streams.get(request.group_id):
            self._metrics.rejected_busy += 1
            # /stop 只能停自己的，占着名额的是别人时不能让他去停
            occupied_by_self = self._active_streams[active_stream_id].username == request.username
            logger.info(
                "event=wxbot_ws_stream_rejected stream_id=%s group_id=%s reason=group_busy "
                "active_stream_id=%s by_self=%s",
                request.stream_id,
                request.group_id,
                active_stream_id,
                occupied_by_self,
            )
            notice = BUSY_REPLY if occupied_by_self else BUSY_BY_OTHERS_REPLY
            await self._send_stream_reply(frame, request.stream_id, notice, True)
            return

        self._launch_direct_stream(frame, request)

    def _launch_direct_stream(self, frame: dict[str, Any], request: WxBotAgentRequest) -> None:
        cancel_event = threading.Event()
        task = asyncio.create_task(self._consume_direct_stream(frame, request, cancel_event))
        active = ActiveStream(
            frame=frame,
            group_id=request.group_id,
            username=request.username,
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

                    content = item.content or ("回答完成" if item.finish else THINKING_MSG)
                    send_wait = await self._send_stream_reply(frame, request.stream_id, content, item.finish)
                    if active := self._active_streams.get(request.stream_id):
                        active.last_content = content
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
                        if item.pending_approval:
                            self._metrics.approval_pending += 1
                        elif item.failed:
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
                    await self._send_stream_reply(frame, request.stream_id, STREAM_ERROR_REPLY, True)
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
        """worker 线程入口：执行 Agent 并把生成帧转发到事件循环。"""
        with recording_span(
            "wxbot.long_connection.session",
            attributes={
                "aidev.channel": "rtx",
                "aidev.transport": "websocket",
            },
            root=True,
        ):
            self._produce_agent_frames(request, loop, output_queue, cancel_event)

    def _produce_agent_frames(
        self,
        request: WxBotAgentRequest,
        loop: asyncio.AbstractEventLoop,
        output_queue: asyncio.Queue,
        cancel_event: threading.Event,
    ) -> None:
        agent_stream = None
        frames = None
        try:
            if not self._put_from_worker(loop, output_queue, _PRODUCER_STARTED, cancel_event):
                return
            thread_id = self._view._get_or_create_thread_id(
                self._view._session_scope(request.group_id, request.username)
            )
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
                if stream_frame.finish:
                    break
        except Exception as error:
            if not cancel_event.is_set():
                self._put_from_worker(loop, output_queue, error, cancel_event)
        finally:
            if frames is not None:
                self._drain_stream_frames(frames, request.stream_id)
            stream_registry.unregister(request.stream_id)
            if not cancel_event.is_set():
                self._put_from_worker(loop, output_queue, _PRODUCER_DONE, cancel_event)

    @staticmethod
    def _drain_stream_frames(frames, stream_id: str) -> None:
        """在独立守护线程中排空统一流接口，让 Agent 自己完成收尾。

        长连接不操作消息处理器或缓存。正常读到 Agent 流末尾后，SDK 会按自己的
        生命周期释放资源。排空放到独立线程后，即使某次 ``next()`` 永久阻塞，调用方
        也只等待配置的上限，不会继续占住 wxbot Agent worker。
        """
        completed = threading.Event()

        def _drain() -> None:
            try:
                for _ in frames:
                    pass
            except Exception as error:
                logger.debug("event=wxbot_ws_stream_drain_aborted stream_id=%s error=%s", stream_id, error)
            finally:
                if hasattr(frames, "close"):
                    with contextlib.suppress(Exception):
                        frames.close()
                completed.set()

        threading.Thread(
            target=_drain,
            daemon=True,
            name=f"wxbot-stream-drain-{stream_id[:8]}",
        ).start()
        if not completed.wait(timeout=max(0.0, AGENT_STREAM_DRAIN_TIMEOUT)):
            logger.warning("event=wxbot_ws_stream_drain_timeout stream_id=%s", stream_id)

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
        if task.cancelled():
            return
        if error := task.exception():
            logger.error("event=wxbot_ws_stream_task_failed stream_id=%s error=%s", stream_id, error)

    def request_stop(self, group_id: str, username: str, *, reason: str) -> bool:
        """中止该发起人正在生成的流，返回是否确有流被中止。

        只停自己那条：群里每个人的上下文是独立的，谁都能掐掉别人的回复不合理。
        并发名额仍是群级的，所以这里先按群取到唯一那条流，再核对归属。

        由解析线程（prepare_agent_request 跑在 to_thread 里）调用，因此这里只做
        线程安全的动作：置取消位、通知 Agent 侧停生成，再把收尾丢回事件循环。
        置位必须同步完成，否则用户会在 /stop 回执之后继续看到旧回复刷出来。
        """
        stream_id = self._group_streams.get(group_id, "")
        active = self._active_streams.get(stream_id) if stream_id else None
        if active is None or active.username != username:
            return False

        active.cancel_event.set()
        stream_registry.cancel(stream_id)
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._cancel_active_stream(stream_id, reason=reason, notice=STOP_NOTICE),
                self._loop,
            )
        return True

    async def _cancel_active_stream(
        self,
        stream_id: str,
        *,
        reason: str,
        notice: str | None = None,
    ) -> None:
        """中止这条流。notice 非空时补一个终态帧说明中止原因。

        终态帧必须带上已经推给用户的内容再重发：企微的 stream 协议收到的是全量快照，
        只发一句说明会把用户已经看到的半截回答整个替换掉。
        """
        active = self._active_streams.get(stream_id)
        if active is None:
            return
        active.cancel_event.set()
        stream_registry.cancel(stream_id)
        active.task.cancel()
        await asyncio.gather(active.task, return_exceptions=True)
        self._metrics.cancelled += 1
        logger.info("event=wxbot_ws_stream_cancelled stream_id=%s reason=%s", stream_id, reason)
        if notice:
            delivered = active.last_content or PREPARING_REPLY
            with contextlib.suppress(Exception):
                await self._send_stream_reply(active.frame, stream_id, f"{delivered}\n\n{notice}", True)

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
        final_frames = max(1, self._metrics.final_frames)
        first_frames = max(1, self._metrics.first_frames)
        sent_frames = max(1, self._metrics.sent_frames)
        logger.info(
            "event=wxbot_ws_health state=%s connected=%s accepting=%s active_streams=%s "
            "agent_active=%s agent_pending=%s agent_workers=%s agent_pending_limit=%s agent_capacity=%s "
            "agent_submitted=%s agent_rejected=%s agent_peak_active=%s agent_peak_pending=%s "
            "streams_started=%s streams_completed=%s streams_approval_pending=%s "
            "streams_cancelled=%s streams_failed=%s streams_rejected_busy=%s "
            "avg_first_frame_ms=%.3f avg_final_frame_ms=%.3f avg_send_wait_ms=%.3f",
            self._service_state,
            bool(getattr(self._client, "is_connected", False)),
            self._accepting_messages,
            len(self._active_streams),
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
            self._metrics.approval_pending,
            self._metrics.cancelled,
            self._metrics.failed,
            self._metrics.rejected_busy,
            self._metrics.first_frame_latency_total / first_frames * 1000,
            self._metrics.final_frame_latency_total / final_frames * 1000,
            self._metrics.send_wait_total / sent_frames * 1000,
        )

    async def _shutdown_async(self, reason: str) -> None:
        logger.info("[WxAiBot-WS] 执行停机清理: %s", reason)
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()

        try:
            await asyncio.wait_for(
                self._graceful_shutdown(),
                timeout=self._config.shutdown_grace_period_sec,
            )
        except asyncio.TimeoutError:
            logger.warning("[WxAiBot-WS] 优雅停机等待超时，开始强制取消未完成任务")
        finally:
            with contextlib.suppress(Exception):
                self._client.disconnect()
            await self._cancel_stream_tasks()
            self._set_service_state(ServiceState.STOPPED)
            if self._loop and self._loop.is_running():
                self._loop.stop()

    async def _graceful_shutdown(self) -> None:
        await self._cancel_stream_tasks(notice="（服务正在停机，本次回复已中断）")
        with contextlib.suppress(Exception):
            self._client.disconnect()
        await self._wait_for_client_disconnected()

    async def _wait_for_client_disconnected(self) -> None:
        while self._client.is_connected:
            await asyncio.sleep(0.1)

    async def _cancel_stream_tasks(self, notice: str | None = None) -> None:
        await asyncio.gather(
            *(
                self._cancel_active_stream(stream_id, reason="service_shutdown", notice=notice)
                for stream_id in list(self._active_streams)
            ),
            return_exceptions=True,
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
