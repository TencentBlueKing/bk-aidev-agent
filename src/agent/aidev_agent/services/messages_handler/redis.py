"""基于 Redis Streams 的可回放消息处理器。"""

import contextlib
import hashlib
import json
import logging
import threading
import time
import uuid
import weakref
from typing import Any, ClassVar, Optional

import redis
from environs import Env
from redis import Redis
from redis.exceptions import RedisError

from .base import BaseMessageQueueHandler
from .constants import EOD_CHUNK, EnvVarNames, QueueTTLConfig
from .replay_buffer_mixin import ReplayBufferMixin

logger = logging.getLogger(__name__)
env = Env()


class RedisMessageHandler(ReplayBufferMixin, BaseMessageQueueHandler):
    """使用 Redis Streams 保存会话事件并按游标增量回放。

    该实现仅依赖 Redis 6.2 的普通数据命令，不调用 ``INFO``、``CONFIG``、
    ``COMMAND``、``SCAN`` 等管理或全局遍历命令。每个会话使用独立 hash tag，
    便于后续接入 Redis Cluster 时将同一会话的 Stream 和控制键放在同一 slot。
    """

    MIN_SERVER_VERSION: ClassVar[tuple[int, int, int]] = (6, 2, 0)
    BUFFER_FLUSH_INTERVAL: ClassVar[float] = 0.5
    BUFFER_MAX_MESSAGES: ClassVar[int] = 100
    SSE_PUBLISH_CHUNK_MAX_BYTES: ClassVar[int] = 256 * 1024
    STREAM_READ_COUNT: ClassVar[int] = 256
    CURSOR_SEQUENCE_FACTOR: ClassVar[int] = 1_000_000
    CANCEL_CHECK_MIN_INTERVAL: ClassVar[float] = 0.2

    _RELEASE_LOCK_SCRIPT: ClassVar[str] = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
    """
    _RENEW_LOCK_SCRIPT: ClassVar[str] = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('pexpire', KEYS[1], ARGV[2])
        end
        return 0
    """
    _DELETE_IF_VALUE_SCRIPT: ClassVar[str] = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        end
        return 0
    """
    _REPLACE_IF_VALUE_SCRIPT: ClassVar[str] = """
        if redis.call('get', KEYS[1]) ~= ARGV[1] then
            return 0
        end
        local ttl = redis.call('pttl', KEYS[1])
        if ttl > 0 then
            redis.call('set', KEYS[1], ARGV[2], 'PX', ttl)
        else
            redis.call('set', KEYS[1], ARGV[2])
        end
        return 1
    """
    _TOUCH_CONSUMER_SCRIPT: ClassVar[str] = """
        redis.call('zadd', KEYS[1], ARGV[2], ARGV[1])
        redis.call('expire', KEYS[1], ARGV[3])
        if redis.call('exists', KEYS[2]) == 0 then
            redis.call('expire', KEYS[3], ARGV[4])
            redis.call('expire', KEYS[4], ARGV[4])
        end
        return 1
    """
    _COUNT_ACTIVE_CONSUMERS_SCRIPT: ClassVar[str] = """
        redis.call('zremrangebyscore', KEYS[1], '-inf', ARGV[1])
        return redis.call('zcard', KEYS[1])
    """
    _LEGACY_SIGNAL_VALUES: ClassVar[frozenset[bytes]] = frozenset({b"", b"1"})

    _instance: Optional["RedisMessageHandler"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> "RedisMessageHandler":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._init_redis()
                    cls._instance = instance
        return cls._instance

    def _init_redis(self) -> None:
        redis_url = env.str(EnvVarNames.REDIS_URL, "")
        if not redis_url:
            raise RuntimeError(f"Redis handler requires {EnvVarNames.REDIS_URL}")

        socket_timeout = env.float(EnvVarNames.REDIS_SOCKET_TIMEOUT, 10.0)
        connect_timeout = env.float(EnvVarNames.REDIS_CONNECT_TIMEOUT, 5.0)
        self._client: Redis = redis.Redis.from_url(
            redis_url,
            decode_responses=False,
            socket_timeout=socket_timeout,
            socket_connect_timeout=connect_timeout,
            health_check_interval=30,
        )
        try:
            self._server_version = self._validate_server()
        except Exception:
            self._client.close()
            raise
        self._queue_ttl_seconds = max(1, QueueTTLConfig.QUEUE_EXPIRE_MS // 1000)
        self._producer_lock_ttl_ms = env.int(EnvVarNames.REDIS_PRODUCER_LOCK_TTL_SECONDS, 60) * 1000
        self._producer_lock_renew_interval = max(
            1.0,
            min(
                env.float(EnvVarNames.REDIS_PRODUCER_LOCK_RENEW_INTERVAL, 20.0),
                self._producer_lock_ttl_ms / 3000,
            ),
        )
        self._consumer_stale_seconds = env.float(EnvVarNames.REDIS_CONSUMER_STALE_SECONDS, 90.0)
        self._completed_stream_ttl_seconds = env.int(EnvVarNames.REDIS_COMPLETED_STREAM_TTL_SECONDS, 90)

        self._message_buffer: dict[str, list[Any]] = {}
        self._buffer_lock = threading.Lock()
        # flush 完成后不再永久持有每个历史 session 的锁，避免长生命周期 worker 随会话数持续增长。
        self._flush_locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
        self._flush_locks_guard = threading.Lock()
        self._producer_tokens: dict[str, bytes] = {}
        self._producer_last_renewed: dict[str, float] = {}
        self._lost_producer_locks: set[str] = set()
        self._producer_lock_guard = threading.Lock()
        self._eod_commit_events: dict[str, set[threading.Event]] = {}
        self._eod_commit_events_lock = threading.Lock()
        self._cancel_check_cache: dict[tuple[str, str], float] = {}
        self._cancel_check_cache_lock = threading.Lock()

        self._daemon_thread: Optional[threading.Thread] = None
        self._daemon_running = False
        self._daemon_stop_event = threading.Event()
        self._start_daemon()

        logger.info("Redis message handler initialized: server=%s", ".".join(map(str, self._server_version)))

    @property
    def server_version(self) -> tuple[int, int, int]:
        return self._server_version

    @staticmethod
    def _parse_hello_response(response: Any) -> tuple[int, int, int]:
        if isinstance(response, dict):
            raw_version = response.get(b"version", response.get("version"))
        elif isinstance(response, (list, tuple)):
            values = dict(zip(response[::2], response[1::2]))
            raw_version = values.get(b"version", values.get("version"))
        else:
            raw_version = None

        if isinstance(raw_version, bytes):
            raw_version = raw_version.decode("ascii", errors="strict")
        if not isinstance(raw_version, str):
            raise RuntimeError("Redis HELLO response does not contain a valid server version")

        try:
            version_parts = raw_version.split(".")[:3]
            version = tuple(int(part.split("-")[0]) for part in version_parts)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Invalid Redis server version: {raw_version!r}") from exc
        if len(version) != 3:
            raise RuntimeError(f"Invalid Redis server version: {raw_version!r}")
        return version

    def _validate_server(self) -> tuple[int, int, int]:
        """校验版本和所需数据命令，不使用管理类命令。"""
        try:
            version = self._parse_hello_response(self._client.execute_command("HELLO", 2))
        except RedisError as exc:
            raise RuntimeError("Redis handler requires HELLO permission to validate Redis 6.2+") from exc

        if version < self.MIN_SERVER_VERSION:
            actual = ".".join(map(str, version))
            raise RuntimeError(f"Redis handler requires Redis >= 6.2.0, got {actual}")

        probe_tag = uuid.uuid4().hex
        probe_stream = f"aidev_agent:probe:{{{probe_tag}}}:stream"
        probe_lock = f"aidev_agent:probe:{{{probe_tag}}}:lock"
        probe_consumers = f"aidev_agent:probe:{{{probe_tag}}}:consumers"
        try:
            self._client.set(probe_lock, b"probe", ex=5)
            if self._client.getdel(probe_lock) != b"probe":
                raise RuntimeError("GETDEL capability probe returned an unexpected value")

            pipeline = self._client.pipeline(transaction=True)
            pipeline.xadd(probe_stream, {b"data": b"probe"})
            pipeline.expire(probe_stream, 5)
            pipeline.zadd(probe_consumers, {b"probe": time.time()})
            pipeline.expire(probe_consumers, 5)
            pipeline.execute()

            records = self._client.xread({probe_stream: "0-0"}, count=1, block=1)
            if not records:
                raise RuntimeError("XREAD capability probe returned no data")

            self._client.set(probe_lock, b"probe", px=5000)
            released = self._client.eval(self._RELEASE_LOCK_SCRIPT, 1, probe_lock, b"probe")
            if released != 1:
                raise RuntimeError("EVAL capability probe failed to release its lock")
        except (RedisError, RuntimeError) as exc:
            raise RuntimeError("Redis 6.2 data-command capability probe failed") from exc
        finally:
            with contextlib.suppress(RedisError):
                self._client.delete(probe_stream, probe_lock, probe_consumers)

        return version

    @staticmethod
    def _thread_tag(thread_id: str) -> str:
        return hashlib.sha256(thread_id.encode("utf-8")).hexdigest()

    def _key(self, thread_id: str, suffix: str) -> str:
        return f"aidev_agent:{{{self._thread_tag(thread_id)}}}:{suffix}"

    def _stream_key(self, thread_id: str) -> str:
        return self._key(thread_id, "stream")

    def _producer_lock_key(self, thread_id: str) -> str:
        return self._key(thread_id, "producer_lock")

    def _active_consumers_key(self, thread_id: str) -> str:
        return self._key(thread_id, "active_consumers")

    def _cancel_signal_key(self, thread_id: str) -> str:
        return self._key(thread_id, "cancel_signal")

    def _cancelled_signal_key(self, thread_id: str) -> str:
        return self._key(thread_id, "cancelled_signal")

    def _stopped_key(self, thread_id: str) -> str:
        return self._key(thread_id, "stopped")

    def _replay_run_key(self, thread_id: str) -> str:
        return self._key(thread_id, "replay_run")

    @staticmethod
    def _signal_value(run_id: str | None) -> bytes:
        return run_id.encode("utf-8") if run_id else b""

    @classmethod
    def _signal_matches(cls, value: bytes | None, run_id: str | None) -> bool:
        if value is None:
            return False
        if run_id is None:
            return True
        return value in cls._LEGACY_SIGNAL_VALUES or value == cls._signal_value(run_id)

    def _clear_signal(self, key: str, run_id: str | None) -> None:
        if run_id is None:
            self._client.delete(key)
            return

        value = self._client.get(key)
        if self._signal_matches(value, run_id):
            self._client.eval(self._DELETE_IF_VALUE_SCRIPT, 1, key, value)

    def _invalidate_cancel_check_cache(self, thread_id: str) -> None:
        with self._cancel_check_cache_lock:
            stale_keys = [cache_key for cache_key in self._cancel_check_cache if cache_key[0] == thread_id]
            for cache_key in stale_keys:
                self._cancel_check_cache.pop(cache_key, None)

    def _session_data_keys(self, thread_id: str) -> list[str]:
        """返回新 Run 启动时应清理的数据键。

        当前消费者和跨进程取消信号必须保留：consumer 在 ``clear()`` 之前
        已完成注册，stop 请求也可能由另一个进程同时写入。它们由独立 TTL
        和 run_id 负责回收、隔离。
        """
        return [
            self._stream_key(thread_id),
            self._stopped_key(thread_id),
            self._replay_run_key(thread_id),
        ]

    def _get_flush_lock(self, thread_id: str) -> threading.Lock:
        with self._flush_locks_guard:
            return self._flush_locks.setdefault(thread_id, threading.Lock())

    @classmethod
    def _encode_cursor(cls, stream_id: bytes | str) -> int:
        if isinstance(stream_id, bytes):
            stream_id = stream_id.decode("ascii")
        milliseconds, sequence = (int(part) for part in stream_id.split("-", 1))
        if sequence >= cls.CURSOR_SEQUENCE_FACTOR:
            raise RuntimeError(f"Redis Stream sequence is too large to encode: {stream_id}")
        return milliseconds * cls.CURSOR_SEQUENCE_FACTOR + sequence

    @classmethod
    def _decode_cursor(cls, cursor: int) -> str:
        milliseconds, sequence = divmod(max(cursor, 0), cls.CURSOR_SEQUENCE_FACTOR)
        return f"{milliseconds}-{sequence}"

    def _start_daemon(self) -> None:
        if self._daemon_thread and self._daemon_thread.is_alive():
            return
        self._daemon_running = True
        self._daemon_stop_event.clear()
        self._daemon_thread = threading.Thread(target=self._daemon_worker, name="redis-message-flusher", daemon=True)
        self._daemon_thread.start()

    def _ensure_daemon_alive(self) -> None:
        if not self._daemon_thread or not self._daemon_thread.is_alive():
            logger.warning("Redis message daemon is not alive; restarting after process fork")
            self._start_daemon()

    def _daemon_worker(self) -> None:
        while self._daemon_running:
            if self._daemon_stop_event.wait(self.BUFFER_FLUSH_INTERVAL):
                break
            self._flush_messages()
            self._renew_producer_locks()
        with contextlib.suppress(Exception):
            self._flush_messages()

    def _stop_daemon(self) -> None:
        self._daemon_running = False
        self._daemon_stop_event.set()
        if self._daemon_thread and self._daemon_thread.is_alive():
            self._daemon_thread.join(timeout=2.0)

    def _renew_producer_locks(self) -> None:
        now = time.monotonic()
        with self._producer_lock_guard:
            tokens = list(self._producer_tokens.items())
        for thread_id, token in tokens:
            with self._producer_lock_guard:
                last_renewed = self._producer_last_renewed.get(thread_id, 0.0)
            if now - last_renewed < self._producer_lock_renew_interval:
                continue
            try:
                renewed = self._client.eval(
                    self._RENEW_LOCK_SCRIPT,
                    1,
                    self._producer_lock_key(thread_id),
                    token,
                    self._producer_lock_ttl_ms,
                )
                with self._producer_lock_guard:
                    if renewed == 1:
                        self._producer_last_renewed[thread_id] = now
                    else:
                        self._lost_producer_locks.add(thread_id)
                        logger.error("Redis producer lock lost for thread_id=%s", thread_id)
            except RedisError:
                logger.exception("Failed to renew Redis producer lock for thread_id=%s", thread_id)

    def _flush_thread(self, thread_id: str) -> bool:
        flush_lock = self._get_flush_lock(thread_id)
        with flush_lock:
            with self._buffer_lock:
                messages = self._message_buffer.pop(thread_id, [])
            if not messages:
                return False

            published_messages = self._coalesce_sse_messages(messages)
            stream_key = self._stream_key(thread_id)
            try:
                pipeline = self._client.pipeline(transaction=True)
                for message in published_messages:
                    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    pipeline.xadd(stream_key, {b"data": payload})
                pipeline.expire(stream_key, self._queue_ttl_seconds)
                pipeline.execute()
            except Exception:
                with self._buffer_lock:
                    self._message_buffer[thread_id] = messages + self._message_buffer.get(thread_id, [])
                logger.exception("Failed to flush Redis messages for thread_id=%s", thread_id)
                raise

            if EOD_CHUNK in messages:
                logger.info(
                    "[EOD] Redis flush thread_id=%s logical=%d published=%d",
                    thread_id,
                    len(messages),
                    len(published_messages),
                )
            self._notify_eod_committed(thread_id, messages)
            return True

    def _flush_messages(self) -> None:
        with self._buffer_lock:
            thread_ids = list(self._message_buffer)
        for thread_id in thread_ids:
            try:
                self._flush_thread(thread_id)
            except Exception:
                continue

    def put(self, thread_id: str, message: Any) -> None:
        self._ensure_daemon_alive()
        with self._producer_lock_guard:
            if thread_id in self._lost_producer_locks:
                raise RuntimeError(f"Redis producer lock lost for thread_id={thread_id}")
        should_flush = False
        with self._buffer_lock:
            messages = self._message_buffer.setdefault(thread_id, [])
            messages.append(message)
            should_flush = len(messages) >= self.BUFFER_MAX_MESSAGES
        if should_flush:
            self.flush(thread_id)

    def flush(self, thread_id: Optional[str] = None) -> None:
        if thread_id is None:
            self._flush_messages()
        else:
            self._flush_thread(thread_id)

    def supports_replay_from_start(self) -> bool:
        return True

    def get_messages_since(
        self,
        thread_id: str,
        offset: int,
        timeout: Optional[float] = None,
    ) -> tuple[list[Any], int]:
        stream_key = self._stream_key(thread_id)
        cursor = self._decode_cursor(offset)
        deadline = time.monotonic() + timeout if timeout is not None else None

        while True:
            if deadline is None:
                block_ms = 1000
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("No message available within timeout")
                block_ms = max(1, int(remaining * 1000))

            records = self._client.xread({stream_key: cursor}, count=self.STREAM_READ_COUNT, block=block_ms)
            if records:
                entries = records[0][1]
                messages = []
                for _, fields in entries:
                    payload = fields.get(b"data", fields.get("data"))
                    if payload is None:
                        raise RuntimeError(f"Redis Stream entry is missing data for thread_id={thread_id}")
                    messages.append(json.loads(payload))
                next_offset = self._encode_cursor(entries[-1][0])
                return self._expand_sse_messages(messages), next_offset

            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("No message available within timeout")

    def has_pending_messages(self, thread_id: str) -> bool:
        with self._buffer_lock:
            if self._message_buffer.get(thread_id):
                return True
        return self._client.xlen(self._stream_key(thread_id)) > 0

    def mark_completed(self, thread_id: str) -> None:
        """标记完成并保留短暂 replay 窗口，避免首个消费者删除其他消费者的历史。"""
        with self._buffer_lock:
            self._message_buffer.pop(thread_id, None)
        pipeline = self._client.pipeline(transaction=True)
        pipeline.expire(self._stream_key(thread_id), self._completed_stream_ttl_seconds)
        pipeline.expire(self._active_consumers_key(thread_id), self._completed_stream_ttl_seconds)
        pipeline.expire(self._replay_run_key(thread_id), self._completed_stream_ttl_seconds)
        pipeline.delete(
            self._cancel_signal_key(thread_id),
            self._cancelled_signal_key(thread_id),
            self._stopped_key(thread_id),
        )
        pipeline.execute()
        self._invalidate_cancel_check_cache(thread_id)

    def arm_completed_replay_expiry(self, thread_id: str) -> bool:
        """立即设置完成态 TTL；活跃消费者心跳会在回放期间持续续期。

        Producer 可能先于 stop waiter 完成，因此这里保留 ``cancelled_signal``；
        最终 Consumer cleanup 仍会先清理旧信号、再发送本轮完成通知。
        """
        pipeline = self._client.pipeline(transaction=True)
        pipeline.expire(self._stream_key(thread_id), self._completed_stream_ttl_seconds)
        pipeline.expire(self._active_consumers_key(thread_id), self._completed_stream_ttl_seconds)
        pipeline.expire(self._replay_run_key(thread_id), self._completed_stream_ttl_seconds)
        pipeline.delete(
            self._cancel_signal_key(thread_id),
            self._stopped_key(thread_id),
        )
        pipeline.execute()
        self._invalidate_cancel_check_cache(thread_id)
        return True

    def bind_replay_run(self, thread_id: str, run_id: str) -> None:
        self._client.set(
            self._replay_run_key(thread_id),
            run_id.encode("utf-8"),
            ex=self._queue_ttl_seconds,
        )

    def replay_belongs_to_run(self, thread_id: str, run_id: str) -> bool:
        replay_run = self._client.get(self._replay_run_key(thread_id))
        # 滚动发布期间旧 worker 没有写 replay_run，保留原 session 级 replay 行为。
        return replay_run is None or replay_run == run_id.encode("utf-8")

    def has_active_producer(self, thread_id: str) -> bool:
        return bool(self._client.exists(self._producer_lock_key(thread_id)))

    def clear(self, thread_id: str) -> None:
        with self._buffer_lock:
            self._message_buffer.pop(thread_id, None)
        self._client.delete(*self._session_data_keys(thread_id))
        self._invalidate_cancel_check_cache(thread_id)

    def acquire_producer(self, thread_id: str) -> bool:
        token = uuid.uuid4().hex.encode()
        with self._producer_lock_guard:
            if thread_id in self._producer_tokens:
                return False
        acquired = self._client.set(
            self._producer_lock_key(thread_id),
            token,
            nx=True,
            px=self._producer_lock_ttl_ms,
        )
        if not acquired:
            return False
        with self._producer_lock_guard:
            self._producer_tokens[thread_id] = token
            self._producer_last_renewed[thread_id] = time.monotonic()
            self._lost_producer_locks.discard(thread_id)
        return True

    def release_producer(self, thread_id: str) -> None:
        with self._producer_lock_guard:
            token = self._producer_tokens.pop(thread_id, None)
            self._producer_last_renewed.pop(thread_id, None)
            self._lost_producer_locks.discard(thread_id)
        if token is not None:
            try:
                self._client.eval(self._RELEASE_LOCK_SCRIPT, 1, self._producer_lock_key(thread_id), token)
            except RedisError:
                logger.exception("Failed to release Redis producer lock for thread_id=%s", thread_id)

    def acquire_consumer(self, thread_id: str) -> str:
        consumer_id = uuid.uuid4().hex
        self._touch_consumer(thread_id, consumer_id)
        return consumer_id

    def wait_for_previous_consumer(self, thread_id: str, timeout: float = 3.0) -> bool:
        return True

    def check_consumer(self, thread_id: str, consumer_id: str) -> None:
        self._touch_consumer(thread_id, consumer_id)

    def _touch_consumer(self, thread_id: str, consumer_id: str) -> None:
        self._client.eval(
            self._TOUCH_CONSUMER_SCRIPT,
            4,
            self._active_consumers_key(thread_id),
            self._producer_lock_key(thread_id),
            self._stream_key(thread_id),
            self._replay_run_key(thread_id),
            consumer_id,
            time.time(),
            self._queue_ttl_seconds,
            self._completed_stream_ttl_seconds,
        )

    def release_consumer(self, thread_id: str, consumer_id: str) -> None:
        self._client.zrem(self._active_consumers_key(thread_id), consumer_id)

    def has_active_consumer(self, thread_id: str) -> bool:
        key = self._active_consumers_key(thread_id)
        stale_before = time.time() - self._consumer_stale_seconds
        count = self._client.eval(self._COUNT_ACTIVE_CONSUMERS_SCRIPT, 1, key, stale_before)
        return bool(count)

    def get_cached_count(self, thread_id: str) -> int:
        return self._client.xlen(self._stream_key(thread_id))

    def set_cancel_signal(self, thread_id: str, run_id: str | None = None) -> bool:
        result = bool(self._client.set(self._cancel_signal_key(thread_id), self._signal_value(run_id), ex=30))
        if result:
            self._invalidate_cancel_check_cache(thread_id)
        return result

    def check_cancel_signal(self, thread_id: str, run_id: str | None = None) -> bool:
        cache_key = (thread_id, run_id or "")
        now = time.monotonic()
        with self._cancel_check_cache_lock:
            last_negative_check = self._cancel_check_cache.get(cache_key)
        if last_negative_check is not None and now - last_negative_check < self.CANCEL_CHECK_MIN_INTERVAL:
            return False

        key = self._cancel_signal_key(thread_id)
        value = self._client.get(key)
        if run_id and value in self._LEGACY_SIGNAL_VALUES:
            # 旧前端只按 session 发送 stop。当前 run 首次命中后立即将信号绑定到
            # 实际 run_id，避免 producer 清理前同 session 的下一轮误继承。
            replacement = self._signal_value(run_id)
            if self._client.eval(self._REPLACE_IF_VALUE_SCRIPT, 1, key, value, replacement):
                value = replacement
            else:
                value = self._client.get(key)
        matched = self._signal_matches(value, run_id)
        with self._cancel_check_cache_lock:
            if matched:
                self._cancel_check_cache.pop(cache_key, None)
            else:
                self._cancel_check_cache[cache_key] = time.monotonic()
        return matched

    def clear_cancel_signal(self, thread_id: str, run_id: str | None = None) -> None:
        self._clear_signal(self._cancel_signal_key(thread_id), run_id)
        self._invalidate_cancel_check_cache(thread_id)

    def notify_consumer_cancelled(self, thread_id: str, run_id: str | None = None) -> bool:
        return bool(self._client.set(self._cancelled_signal_key(thread_id), self._signal_value(run_id), ex=30))

    def wait_for_consumer_cancelled(
        self,
        thread_id: str,
        timeout: float = 3.0,
        run_id: str | None = None,
    ) -> bool:
        key = self._cancelled_signal_key(thread_id)
        if run_id is None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self._client.getdel(key) is not None:
                    return True
                time.sleep(0.1)
            return False

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self._client.get(key)
            if self._signal_matches(value, run_id):
                deleted = self._client.eval(self._DELETE_IF_VALUE_SCRIPT, 1, key, value)
                if deleted:
                    return True
            time.sleep(0.1)
        return False

    def clear_cancelled_signal(self, thread_id: str, run_id: str | None = None) -> None:
        self._clear_signal(self._cancelled_signal_key(thread_id), run_id)

    def mark_stopped(self, thread_id: str) -> None:
        self._client.set(self._stopped_key(thread_id), b"1", ex=600)

    def is_stopped(self, thread_id: str) -> bool:
        return bool(self._client.exists(self._stopped_key(thread_id)))

    def clear_stopped(self, thread_id: str) -> None:
        self._client.delete(self._stopped_key(thread_id))

    def list_thread_ids(self) -> list[str]:
        """仅返回本进程缓冲区中的会话；不使用 SCAN 遍历 Redis。"""
        with self._buffer_lock:
            return list(self._message_buffer)

    def close(self) -> None:
        self._stop_daemon()
        with self._producer_lock_guard:
            thread_ids = list(self._producer_tokens)
        for thread_id in thread_ids:
            with contextlib.suppress(Exception):
                self.release_producer(thread_id)
        with contextlib.suppress(Exception):
            self._client.close()

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.close()


__all__ = ["RedisMessageHandler"]
