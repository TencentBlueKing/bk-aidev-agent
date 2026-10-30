"""RabbitMQ Stream 数据面的消息处理器。

SSE 事件使用 RabbitMQ Stream 的 append-only log 和原生 offset；生产者锁、
取消信号、停止状态及活跃消费者登记继续复用 RabbitMQ AMQP 0.9.1 控制面。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import pickle
import queue
import threading
import time
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any, Callable, ClassVar, Coroutine, Optional

from environs import Env
from rstream import Consumer, ConsumerOffsetSpecification, OffsetType, OnClosedErrorInfo, Producer
from rstream.connection import ConnectionClosed

from .constants import EOD_CHUNK, HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT, EnvVarNames
from .rabbitmq import RabbitMQMessageHandler
from .telemetry import record_message_publish_metrics

logger = getLogger(__name__)
env = Env()

# OSError 已覆盖 TimeoutError、ConnectionError 等超时和断连异常。
_RECONNECTABLE_ERRORS: tuple[type[BaseException], ...] = (OSError, ConnectionClosed)
# stream 删除等元数据变化也会触发 on_close_handler，但连接本身仍可用。
_METADATA_UPDATE_REASON = "Metadata Update"
# 生产者每个心跳周期至少写入一条消息；订阅连续两个周期没有投递，说明订阅连接可能已失效。
_SUBSCRIPTION_IDLE_TIMEOUT = HEARTBEAT_INTERVAL * 2
# rstream 关闭时每个内部请求最多等 5 秒；后台关闭再加总上限，避免卡住的 socket 长期占用任务。
_STALE_CLIENT_CLOSE_TIMEOUT = 30.0


@dataclass
class _StreamSubscription:
    """一个同步 SSE 消费线程对应的 RabbitMQ Stream 订阅。"""

    consumer: Consumer
    subscriber_id: int
    stream: str
    next_offset: int
    messages: queue.Queue[tuple[int, Any]] = field(default_factory=queue.Queue)
    connection_closed: bool = False
    stream_changed: bool = False
    last_delivery_at: float = field(default_factory=time.monotonic)

    def rebuild_reason(self) -> str | None:
        """返回订阅需要重建的原因。

        stream 被删除或变更后不重建，避免接到新一轮重新创建的同名 stream；
        本地还有未读消息时不算空闲。
        """
        if self.stream_changed:
            return None
        if self.connection_closed:
            return "connection_closed"
        if self.messages.empty() and time.monotonic() - self.last_delivery_at > _SUBSCRIPTION_IDLE_TIMEOUT:
            return "idle"
        return None

    def may_be_broken(self) -> bool:
        return self.stream_changed or self.rebuild_reason() is not None

    def read(self, offset: int, timeout: float | None) -> tuple[list[Any], int]:
        """等待第一条消息，再一次性取走当前已到达的连续批次。"""
        wait_timeout = timeout if timeout is not None else None
        try:
            first = self.messages.get(timeout=wait_timeout)
        except queue.Empty as exc:
            raise TimeoutError("No message available within timeout") from exc

        records = [first]
        while True:
            try:
                records.append(self.messages.get_nowait())
            except queue.Empty:
                break

        records = [record for record in records if record[0] >= offset]
        if not records:
            raise TimeoutError("No message available within timeout")

        self.next_offset = records[-1][0] + 1
        return [message for _, message in records], self.next_offset


class _RabbitMQStreamRuntime:
    """在专用 asyncio loop 中持有 rstream producer 和 consumer。"""

    def __init__(
        self,
        connection_kwargs: dict[str, Any],
        operation_timeout: float,
        max_age_seconds: int,
    ) -> None:
        self._connection_kwargs = connection_kwargs
        self._operation_timeout = operation_timeout
        self._max_age_seconds = max_age_seconds
        self._state_lock = threading.Lock()
        self._subscriptions: dict[tuple[int, str], _StreamSubscription] = {}
        self._known_streams: set[str] = set()
        self._pid = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._producer: Producer | None = None
        self._producer_generation = 0
        self._producer_stale = False
        self._reconnect_lock = threading.Lock()
        self._background_closes: set[asyncio.Task[None]] = set()
        self._startup_event = threading.Event()
        self._startup_error: BaseException | None = None
        self.ensure_alive()

    def ensure_alive(self) -> None:
        """首次初始化以及 Gunicorn fork 后重建事件循环和连接。"""
        current_pid = os.getpid()
        with self._state_lock:
            if self._pid == current_pid and self._thread is not None and self._thread.is_alive():
                return

            self._pid = current_pid
            self._subscriptions = {}
            self._known_streams = set()
            self._background_closes = set()
            self._startup_event = threading.Event()
            self._startup_error = None
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="RabbitMQ-Stream-Loop",
            )
            self._thread.start()

        if not self._startup_event.wait(timeout=self._operation_timeout):
            raise RuntimeError("Timed out starting RabbitMQ Stream client")
        if self._startup_error is not None:
            raise RuntimeError("Failed to initialize RabbitMQ Stream client") from self._startup_error

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_producer())
        except BaseException as exc:
            self._startup_error = exc
            self._startup_event.set()
            self._loop.close()
            return

        self._startup_event.set()
        self._loop.run_forever()
        self._loop.run_until_complete(self._close_async())
        self._loop.close()

    async def _start_producer(self) -> None:
        async def on_close(info: OnClosedErrorInfo) -> None:
            await self._on_producer_closed(producer, info)

        producer = Producer(
            **self._connection_kwargs,
            connection_name="aidev-agent-stream-producer",
            on_close_handler=on_close,
        )
        self._producer = producer
        await producer.start()
        self._known_streams = set()
        self._producer_stale = False
        self._producer_generation += 1

    async def _on_producer_closed(self, producer: Producer, info: OnClosedErrorInfo) -> None:
        # 旧 producer 在后台关闭时也可能回调，只处理当前 producer。
        if producer is not self._producer or info.reason == _METADATA_UPDATE_REASON:
            return
        logger.warning("RabbitMQ Stream producer connection closed reason=%s", info.reason)
        self._producer_stale = True

    def _close_in_background(self, client: Producer | Consumer) -> None:
        """后台关闭旧连接；失效连接的关闭会等满 rstream 内部超时，不应阻塞当前请求。"""
        task = asyncio.get_running_loop().create_task(self._close_quietly(client))
        self._background_closes.add(task)
        task.add_done_callback(self._background_closes.discard)

    async def _close_quietly(self, client: Producer | Consumer) -> None:
        try:
            await asyncio.wait_for(client.close(), timeout=_STALE_CLIENT_CLOSE_TIMEOUT)
        except Exception as error:
            logger.warning("Failed to close stale RabbitMQ Stream %s error=%r", type(client).__name__, error)

    async def _restart_producer(self) -> None:
        # 重建失败时保持失效标记，下一次操作会再次尝试重建。
        self._producer_stale = True
        old_producer, self._producer = self._producer, None
        if old_producer is not None:
            self._close_in_background(old_producer)
        await self._start_producer()

    def _reconnect(self, failed_generation: int, deadline: float | None = None) -> None:
        """重建 producer；并发失败时只由第一个线程重建。

        旧连接在后台关闭；等待锁和新连接建立合计不超过一次操作超时，也不超过调用方的 deadline。
        """
        reconnect_deadline = time.monotonic() + self._operation_timeout
        if deadline is not None:
            reconnect_deadline = min(reconnect_deadline, deadline)
        if not self._reconnect_lock.acquire(timeout=self._remaining(reconnect_deadline)):
            raise TimeoutError("Timed out waiting for RabbitMQ Stream reconnect")
        try:
            if self._producer_generation != failed_generation:
                return
            logger.warning("Reconnecting RabbitMQ Stream producer generation=%s", failed_generation)
            timeout = self._remaining(reconnect_deadline)
            self._submit(self._restart_producer(), timeout=timeout)
        finally:
            self._reconnect_lock.release()

    @staticmethod
    def _remaining(deadline: float, cap: float | None = None) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("RabbitMQ Stream operation budget exhausted")
        return remaining if cap is None else min(remaining, cap)

    def _submit_with_reconnect(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        *,
        timeout: float | None = None,
        retry: bool = True,
    ) -> Any:
        """超时或断连时重建连接；幂等操作再用新协程重试一次。

        整体耗时不超过两倍操作超时：首次操作、重建、重试各自最多一倍，并共享同一个 deadline。
        """
        operation_timeout = timeout or self._operation_timeout
        deadline = time.monotonic() + operation_timeout * 2
        if self._producer_stale:
            self._reconnect(self._producer_generation, deadline)
        generation = self._producer_generation
        try:
            return self._submit_before_deadline(coro_factory, deadline, operation_timeout)
        except _RECONNECTABLE_ERRORS as error:
            logger.warning("RabbitMQ Stream operation failed retry=%s error=%r", retry, error)
            if not retry:
                self._producer_stale = True
                raise
            self._reconnect(generation, deadline)
            return self._submit_before_deadline(coro_factory, deadline, operation_timeout)

    def _submit_before_deadline(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        deadline: float,
        operation_timeout: float,
    ) -> Any:
        # 先检查剩余时间再创建协程，预算耗尽时不留下未执行的协程。
        timeout = self._remaining(deadline, operation_timeout)
        return self._submit(coro_factory(), timeout)

    def _submit(self, coro: Any, timeout: float | None = None) -> Any:
        self.ensure_alive()
        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout or self._operation_timeout)
        except TimeoutError:
            future.cancel()
            raise

    async def _ensure_stream(self, stream: str, max_age_seconds: int) -> None:
        if stream in self._known_streams:
            return
        assert self._producer is not None
        await self._producer.create_stream(
            stream,
            arguments={"max-age": f"{max_age_seconds}s"},
            exists_ok=True,
        )
        self._known_streams.add(stream)

    async def _publish_confirmed(
        self,
        stream: str,
        payloads: list[bytes],
        publisher_name: str,
        max_age_seconds: int,
    ) -> list[int]:
        await self._ensure_stream(stream, max_age_seconds)
        assert self._producer is not None

        confirmation_event = asyncio.Event()
        confirmed: set[int] = set()
        failed: dict[int, int] = {}

        def on_confirm(status: Any) -> None:
            if status.is_confirmed:
                confirmed.add(status.message_id)
            else:
                failed[status.message_id] = status.response_code
            confirmation_event.set()

        publishing_ids = await self._producer.send_batch(
            stream,
            payloads,
            publisher_name=publisher_name,
            on_publish_confirm=on_confirm,
        )
        expected = set(publishing_ids)
        deadline = asyncio.get_running_loop().time() + self._operation_timeout
        while not expected.issubset(confirmed):
            failed_expected = expected.intersection(failed)
            if failed_expected:
                details = {message_id: failed[message_id] for message_id in failed_expected}
                raise RuntimeError(f"RabbitMQ Stream publish was rejected: {details}")
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for RabbitMQ Stream publish confirms")
            # 先清理旧通知再复查状态，避免 confirm 恰好到达时丢失唤醒。
            confirmation_event.clear()
            if expected.issubset(confirmed):
                break
            await asyncio.wait_for(confirmation_event.wait(), timeout=remaining)
        return publishing_ids

    def publish(
        self,
        stream: str,
        payloads: list[bytes],
        publisher_name: str,
        max_age_seconds: int,
    ) -> list[int]:
        # 发布不在此处重试，失败消息由 flush 放回缓冲区后再发，避免同一批次重复投递。
        return self._submit_with_reconnect(
            lambda: self._publish_confirmed(stream, payloads, publisher_name, max_age_seconds),
            timeout=self._operation_timeout + 1,
            retry=False,
        )

    async def _create_subscription(
        self,
        key: tuple[int, str],
        stream: str,
        offset: int,
    ) -> _StreamSubscription:
        async def on_close(info: OnClosedErrorInfo) -> None:
            if info.reason == _METADATA_UPDATE_REASON:
                subscription.stream_changed = True
                return
            logger.warning("RabbitMQ Stream consumer connection closed stream=%s reason=%s", stream, info.reason)
            subscription.connection_closed = True

        async def on_message(message: Any, context: Any) -> None:
            subscription.last_delivery_at = time.monotonic()
            subscription.messages.put((context.offset, message))

        consumer = Consumer(
            **self._connection_kwargs,
            connection_name=f"aidev-agent-stream-consumer-{key[0]}",
            on_close_handler=on_close,
        )
        # 回调只会在 start 之后触发，此时 subscription 已经创建。
        subscription = _StreamSubscription(
            consumer=consumer,
            subscriber_id=-1,
            stream=stream,
            next_offset=offset,
        )
        try:
            await consumer.start()
            subscription.subscriber_id = await consumer.subscribe(
                stream,
                on_message,
                decoder=pickle.loads,
                offset_specification=ConsumerOffsetSpecification(OffsetType.OFFSET, offset),
                initial_credit=10,
            )
        except BaseException:
            # 包括操作超时后的任务取消，避免半建立的 consumer 连接泄漏。
            self._close_in_background(consumer)
            raise
        self._subscriptions[key] = subscription
        return subscription

    async def _discard_subscription(self, subscription: _StreamSubscription) -> None:
        # 失效连接的关闭会等满 rstream 内部超时，改为后台关闭，避免阻塞读取和释放。
        if subscription.may_be_broken():
            self._close_in_background(subscription.consumer)
        else:
            await subscription.consumer.close()

    async def _replace_subscription(
        self,
        key: tuple[int, str],
        stream: str,
        offset: int,
    ) -> _StreamSubscription:
        old_subscription = self._subscriptions.pop(key, None)
        if old_subscription is not None:
            await self._discard_subscription(old_subscription)
        # producer 与 consumer 并发启动时，先创建空 stream，consumer 才能安全等待首条 SSE。
        await self._ensure_stream(stream, self._max_age_seconds)
        return await self._create_subscription(key, stream, offset)

    async def _get_subscription(
        self,
        key: tuple[int, str],
        stream: str,
        offset: int,
    ) -> _StreamSubscription:
        subscription = self._subscriptions.get(key)
        if subscription is None or subscription.stream != stream or subscription.next_offset != offset:
            return await self._replace_subscription(key, stream, offset)
        reason = subscription.rebuild_reason()
        if reason is not None:
            assert self._producer is not None
            if not await self._producer.stream_exists(stream):
                # stream 已被清理时不重新创建空 stream，交给消费循环按心跳超时处理。
                subscription.stream_changed = True
                return subscription
            # 订阅连接断开或长时间没有投递时，从当前 offset 重新订阅，不丢也不重复消息。
            logger.warning(
                "Rebuilding RabbitMQ Stream subscription stream=%s offset=%s reason=%s",
                stream,
                offset,
                reason,
            )
            return await self._replace_subscription(key, stream, offset)
        return subscription

    def get_messages_since(
        self,
        key: tuple[int, str],
        stream: str,
        offset: int,
        timeout: float | None,
    ) -> tuple[list[Any], int]:
        subscription = self._submit_with_reconnect(lambda: self._get_subscription(key, stream, offset))
        return subscription.read(offset, timeout)

    async def _close_subscription(self, key: tuple[int, str]) -> None:
        subscription = self._subscriptions.pop(key, None)
        if subscription is not None:
            await self._discard_subscription(subscription)

    def close_subscription(self, key: tuple[int, str]) -> None:
        self._submit(self._close_subscription(key))

    async def _close_stream_subscriptions(self, stream: str) -> None:
        keys = [key for key, subscription in self._subscriptions.items() if subscription.stream == stream]
        for key in keys:
            await self._close_subscription(key)

    async def _delete_stream(self, stream: str) -> None:
        await self._close_stream_subscriptions(stream)
        assert self._producer is not None
        await self._producer.delete_stream(stream, missing_ok=True)
        self._known_streams.discard(stream)

    def delete_stream(self, stream: str) -> None:
        self._submit_with_reconnect(lambda: self._delete_stream(stream))

    def stream_exists(self, stream: str) -> bool:
        async def check() -> bool:
            assert self._producer is not None
            return await self._producer.stream_exists(stream)

        return bool(self._submit_with_reconnect(check))

    async def _close_async(self) -> None:
        for key in list(self._subscriptions):
            with contextlib.suppress(Exception):
                await self._close_subscription(key)
        if self._producer is not None:
            with contextlib.suppress(Exception):
                await self._producer.close()
        self._producer = None
        background_closes = list(self._background_closes)
        for task in background_closes:
            task.cancel()
        await asyncio.gather(*background_closes, return_exceptions=True)

    def close(self) -> None:
        with self._state_lock:
            loop = self._loop
            thread = self._thread
        if loop is None or thread is None or not thread.is_alive():
            return
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=self._operation_timeout)


class RabbitMQStreamMessageHandler(RabbitMQMessageHandler):
    """RabbitMQ 控制面 + RabbitMQ Stream SSE 日志数据面。"""

    # Stream 按原生 offset 增量读取，不继承 Classic Queue 的 60 秒全量 replay 容忍。
    CONSUMER_HEARTBEAT_TIMEOUT: ClassVar[float] = HEARTBEAT_TIMEOUT
    STREAM_PREFIX: ClassVar[str] = "aidev_agent.stream."
    STREAM_PUBLISH_CONFIRM_TIMEOUT: ClassVar[float] = 10.0
    _instance: Optional["RabbitMQStreamMessageHandler"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def _init_rabbitmq(self) -> None:
        super()._init_rabbitmq()
        self._stream_counts: dict[str, int] = {}
        self._stream_count_lock = threading.Lock()
        self._stream_runtime = _RabbitMQStreamRuntime(
            connection_kwargs=self._get_stream_connection_kwargs(),
            operation_timeout=env.float(
                "RABBITMQ_STREAM_OPERATION_TIMEOUT",
                self.STREAM_PUBLISH_CONFIRM_TIMEOUT,
            ),
            max_age_seconds=max(1, self.QUEUE_TTL_MS // 1000),
        )
        logger.info(
            "RabbitMQ Stream data plane initialized host=%s port=%s",
            env.str(EnvVarNames.RABBITMQ_HOST, "localhost"),
            env.int(EnvVarNames.RABBITMQ_STREAM_PORT),
        )

    def _get_stream_connection_kwargs(self) -> dict[str, Any]:
        return {
            "host": env.str(EnvVarNames.RABBITMQ_HOST, "localhost"),
            "port": env.int(EnvVarNames.RABBITMQ_STREAM_PORT),
            "username": env.str("RABBITMQ_USER", "guest"),
            "password": env.str("RABBITMQ_PASSWORD", "guest"),
            "vhost": env.str("RABBITMQ_VHOST", "/"),
            "heartbeat": env.int("RABBITMQ_STREAM_HEARTBEAT", 60),
            "max_retries": env.int("RABBITMQ_STREAM_MAX_RETRIES", 20),
            "load_balancer_mode": env.bool("RABBITMQ_STREAM_LB_MODE", True),
        }

    def _get_stream_name(self, thread_id: str) -> str:
        return f"{self.STREAM_PREFIX}{thread_id}"

    def _publish_stream_messages(self, thread_id: str, messages: list[Any], *, event_count: int) -> None:
        stream_name = self._get_stream_name(thread_id)
        payloads = [pickle.dumps(message) for message in messages]
        publish_started_at = time.monotonic()
        try:
            publishing_ids = self._stream_runtime.publish(
                stream=stream_name,
                payloads=payloads,
                publisher_name=stream_name,
                max_age_seconds=max(1, self.QUEUE_TTL_MS // 1000),
            )
        except Exception as error:
            record_message_publish_metrics(
                handler_type="rabbitmq_stream",
                messaging_system="rabbitmq",
                event_count=event_count,
                message_sizes=[len(payload) for payload in payloads],
                started_at=publish_started_at,
                error=error,
            )
            raise
        record_message_publish_metrics(
            handler_type="rabbitmq_stream",
            messaging_system="rabbitmq",
            event_count=event_count,
            message_sizes=[len(payload) for payload in payloads],
            started_at=publish_started_at,
        )
        if publishing_ids:
            with self._stream_count_lock:
                self._stream_counts[thread_id] = max(
                    self._stream_counts.get(thread_id, 0),
                    max(publishing_ids) + 1,
                )

    def _flush_one_stream(self, thread_id: str, messages: list[Any], background: bool) -> None:
        messages_to_publish = self._coalesce_sse_messages(messages)
        self._publish_stream_messages(thread_id, messages_to_publish, event_count=len(messages))
        if EOD_CHUNK in messages:
            logger.info(
                "[EOD] RabbitMQ Stream flush thread_id=%s logical=%d published=%d background=%s",
                thread_id,
                len(messages),
                len(messages_to_publish),
                background,
            )
        self._notify_eod_committed(thread_id, messages)
        self._notify_replay_waiters()

    def _flush_messages(self) -> None:
        with self._buffer_lock:
            thread_ids = list(self._message_buffer)

        for thread_id in thread_ids:
            messages: list[Any] = []
            try:
                with self._get_flush_peek_lock(thread_id):
                    with self._buffer_lock:
                        messages = self._message_buffer.pop(thread_id, [])
                    if messages:
                        self._flush_one_stream(thread_id, messages, background=True)
            except Exception:
                logger.exception("Error flushing RabbitMQ Stream messages for thread_id=%s", thread_id)
                if messages:
                    with self._buffer_lock:
                        self._message_buffer[thread_id] = messages + self._message_buffer.get(thread_id, [])

    def flush(self, thread_id: Optional[str] = None) -> None:
        if thread_id is None:
            self._flush_messages()
            return

        with self._get_flush_peek_lock(thread_id):
            with self._buffer_lock:
                messages = self._message_buffer.pop(thread_id, [])
            if not messages:
                return
            try:
                self._flush_one_stream(thread_id, messages, background=False)
            except Exception:
                with self._buffer_lock:
                    self._message_buffer[thread_id] = messages + self._message_buffer.get(thread_id, [])
                raise

    def get_messages_since(
        self,
        thread_id: str,
        offset: int,
        timeout: Optional[float] = None,
    ) -> tuple[list[Any], int]:
        """直接从 RabbitMQ Stream offset 读取，不扫描历史消息。"""
        messages, next_offset = self._stream_runtime.get_messages_since(
            key=(threading.get_ident(), thread_id),
            stream=self._get_stream_name(thread_id),
            offset=max(offset, 0),
            timeout=timeout,
        )
        with self._stream_count_lock:
            self._stream_counts[thread_id] = max(self._stream_counts.get(thread_id, 0), next_offset)
        return self._expand_sse_messages(messages), next_offset

    def release_consumer(self, thread_id: str, consumer_id: str) -> None:
        key = (threading.get_ident(), thread_id)
        with contextlib.suppress(Exception):
            self._stream_runtime.close_subscription(key)
        super().release_consumer(thread_id, consumer_id)

    def has_pending_messages(self, thread_id: str) -> bool:
        with self._buffer_lock:
            if self._message_buffer.get(thread_id):
                return True
        try:
            return self._stream_runtime.stream_exists(self._get_stream_name(thread_id))
        except Exception:
            # 检查失败时按无待续流处理，让本轮对话继续生成而不是中断。
            logger.exception("Error checking RabbitMQ Stream for thread_id=%s, fallback to no pending", thread_id)
            return False

    def _delete_stream_and_control_resources(self, thread_id: str) -> None:
        self._stream_runtime.delete_stream(self._get_stream_name(thread_id))
        with self._with_channel() as channel:
            queue_names = [
                self._get_cancel_queue_name(thread_id),
                self._get_active_consumer_queue_name(thread_id),
                *self._get_signal_queue_names(thread_id),
            ]
            for queue_name in queue_names:
                with contextlib.suppress(Exception):
                    channel.queue_delete(queue=queue_name)

    def mark_completed(self, thread_id: str) -> None:
        with self._buffer_lock:
            self._message_buffer.pop(thread_id, None)
        self._delete_stream_and_control_resources(thread_id)
        with self._stream_count_lock:
            self._stream_counts.pop(thread_id, None)
        with self._flush_peek_locks_guard:
            self._flush_peek_locks.pop(thread_id, None)

    def clear(self, thread_id: str) -> None:
        with self._buffer_lock:
            self._message_buffer.pop(thread_id, None)
        self._stream_runtime.delete_stream(self._get_stream_name(thread_id))
        with self._stream_count_lock:
            self._stream_counts.pop(thread_id, None)
        try:
            with self._with_connection() as connection:
                self._safe_purge_queue(
                    connection,
                    self._get_cancel_queue_name(thread_id),
                    passive_check=True,
                )
        except Exception:
            logger.exception("Error clearing RabbitMQ Stream controls for thread_id=%s", thread_id)

    def get_cached_count(self, thread_id: str) -> int:
        with self._stream_count_lock:
            known_count = self._stream_counts.get(thread_id)
        if known_count is not None:
            return known_count
        return int(self.has_pending_messages(thread_id))

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            if hasattr(self, "_stream_runtime"):
                self._stream_runtime.close()
        super().__del__()
