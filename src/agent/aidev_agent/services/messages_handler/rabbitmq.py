import contextlib
import json
import pickle
import queue
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from logging import getLogger
from typing import TYPE_CHECKING, Any, ClassVar, Optional

if TYPE_CHECKING:
    import pika.channel
from urllib.parse import quote

import pika
from environs import Env

from .base import BaseMessageQueueHandler, QueueTTLConfig
from .constants import EOD_CHUNK, QueueNamePrefixes
from .multi_process_mixin import MultiProcessMixin

logger = getLogger(__name__)

env = Env()


class RabbitMQConnectionPool:
    """RabbitMQ 连接池

    管理 RabbitMQ 连接的创建、复用和销毁，避免频繁创建和关闭连接。

    特点：
    - 连接池大小可配置
    - 自动检测并移除失效连接
    - 线程安全
    - 支持上下文管理器方式获取连接
    """

    def __init__(self, rabbitmq_url: str, pool_size: int = 5, connection_timeout: float = 10.0):
        """
        Args:
            rabbitmq_url: RabbitMQ 连接 URL
            pool_size: 连接池大小
            connection_timeout: 获取连接的超时时间（秒）
        """
        self._rabbitmq_url = rabbitmq_url
        self._pool_size = pool_size
        self._connection_timeout = connection_timeout

        # 使用 queue.Queue 作为连接池，线程安全
        self._pool: queue.Queue[pika.BlockingConnection] = queue.Queue(maxsize=pool_size)
        self._lock = threading.Lock()

        # 跟踪已创建的连接数量
        self._created_count = 0
        self._created_lock = threading.Lock()

        # 连接池是否已关闭
        self._closed = False

    def _create_connection(self) -> pika.BlockingConnection:
        """创建新的 RabbitMQ 连接"""
        params = pika.URLParameters(self._rabbitmq_url)
        params.heartbeat = 60  # 心跳间隔
        params.blocked_connection_timeout = 300  # 阻塞超时
        return pika.BlockingConnection(params)

    def _is_connection_valid(self, connection: pika.BlockingConnection) -> bool:
        """检查连接是否有效
        除了检查 is_open 状态外，还尝试执行一个轻量级操作来验证连接真正可用。
        """
        try:
            if not connection.is_open:
                return False
            # 尝试处理一下 I/O 事件，可以帮助检测连接是否真正有效
            # 如果连接已断开，这里可能会触发异常
            connection.process_data_events(time_limit=0)
            return connection.is_open
        except Exception:
            return False

    def get_connection(self) -> pika.BlockingConnection:
        """从连接池获取连接

        如果池中有可用连接，则返回；否则创建新连接（如果未达到上限）。

        Returns:
            RabbitMQ 连接

        Raises:
            RuntimeError: 连接池已关闭
            queue.Empty: 获取连接超时
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        # 尝试从池中获取连接
        try:
            connection = self._pool.get_nowait()
            # 检查连接是否有效
            if self._is_connection_valid(connection):
                return connection
            else:
                # 连接失效，减少计数并创建新连接
                with self._created_lock:
                    self._created_count = max(0, self._created_count - 1)
                logger.debug("Removed invalid connection from pool")
        except queue.Empty:
            pass

        # 池中没有可用连接，尝试创建新连接
        with self._created_lock:
            if self._created_count < self._pool_size:
                self._created_count += 1
                try:
                    connection = self._create_connection()
                    logger.debug(f"Created new connection, total: {self._created_count}")
                    return connection
                except Exception:
                    self._created_count -= 1
                    raise

        # 已达到连接上限，等待池中连接释放
        try:
            connection = self._pool.get(timeout=self._connection_timeout)
            if self._is_connection_valid(connection):
                return connection
            else:
                # 连接失效，减少计数并重试
                with self._created_lock:
                    self._created_count = max(0, self._created_count - 1)
                return self.get_connection()
        except queue.Empty:
            raise TimeoutError(f"Failed to get connection within {self._connection_timeout} seconds")

    def release_connection(self, connection: pika.BlockingConnection) -> None:
        """将连接归还到连接池

        如果连接有效且池未满，则放回池中；否则关闭连接。

        Args:
            connection: 要归还的连接
        """
        if self._closed:
            # 连接池已关闭，直接关闭连接
            self._close_connection(connection)
            return

        if self._is_connection_valid(connection):
            try:
                self._pool.put_nowait(connection)
                return
            except queue.Full:
                # 池已满，关闭连接
                pass

        # 连接失效或池已满，关闭连接
        self._close_connection(connection)
        with self._created_lock:
            self._created_count = max(0, self._created_count - 1)

    def _close_connection(self, connection: pika.BlockingConnection) -> None:
        """安全关闭连接"""
        try:
            if connection.is_open:
                connection.close()
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")

    @contextmanager
    def connection(self):
        """上下文管理器方式获取连接

        使用示例：
            with pool.connection() as conn:
                channel = conn.channel()
                # 使用 channel...

        Yields:
            RabbitMQ 连接

        Raises:
            pika.exceptions.AMQPConnectionError: 连接失败时抛出
        """
        conn = None
        max_retries = 2  # 最多重试 2 次（共 3 次尝试）
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                conn = self.get_connection()
                yield conn
                # 成功完成，正常归还连接
                self.release_connection(conn)
                conn = None
                return
            except (
                pika.exceptions.StreamLostError,
                pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError,
                ConnectionResetError,
                BrokenPipeError,
                OSError,
            ) as e:
                # 连接相关的异常，标记连接失效并重试
                last_error = e
                if conn:
                    self._close_connection(conn)
                    with self._created_lock:
                        self._created_count = max(0, self._created_count - 1)
                    conn = None

                if attempt < max_retries:
                    logger.warning(
                        f"RabbitMQ connection error (attempt {attempt + 1}/{max_retries + 1}): {e}, retrying..."
                    )
                    continue
                else:
                    logger.error(f"RabbitMQ connection error after {max_retries + 1} attempts: {e}")
                    raise
            except Exception:
                # 其他非连接相关异常，不重试，标记连接失效
                if conn:
                    self._close_connection(conn)
                    with self._created_lock:
                        self._created_count = max(0, self._created_count - 1)
                    conn = None
                raise
            finally:
                # 如果 conn 还在，说明是正常退出或者需要归还
                if conn:
                    self.release_connection(conn)

        # 如果执行到这里，说明所有重试都失败了
        if last_error:
            raise last_error

    def close(self) -> None:
        """关闭连接池，释放所有连接"""
        self._closed = True

        # 关闭池中所有连接
        while True:
            try:
                connection = self._pool.get_nowait()
                self._close_connection(connection)
            except queue.Empty:
                break

        with self._created_lock:
            self._created_count = 0

        logger.info("Connection pool closed")

    @property
    def pool_size(self) -> int:
        """获取连接池大小"""
        return self._pool_size

    @property
    def available_count(self) -> int:
        """获取池中可用连接数量"""
        return self._pool.qsize()

    @property
    def created_count(self) -> int:
        """获取已创建的连接数量"""
        with self._created_lock:
            return self._created_count


class RabbitMQMessageHandler(MultiProcessMixin, BaseMessageQueueHandler):
    """基于RabbitMQ的消息处理器（多进程版本）

    使用 RabbitMQ 作为远端存储，支持分布式场景下的流式消息处理。
    每个 thread_id 对应一个持久化主队列，消费者按 offset 非破坏性 replay。

    工作流程：
    1. 生产者将消息放入主队列
    2. 消费者从自己的 offset 读取主队列，消息始终保留在主队列
    3. 消费者断开重连时从主队列开头独立 replay
    4. 流完成时（mark_completed）清理主队列及控制资源

    特点：
    - 多端消费者互不抢占消息，各自完整回放
    - offset 未变化时只读取队列深度，避免反复全量扫描
    - 后台守护线程每隔 0.5 秒批量推送消息，减少连接开销
    """

    # 使用统一的队列名称前缀和 TTL 配置
    QUEUE_PREFIX: ClassVar[str] = QueueNamePrefixes.MESSAGE_QUEUE
    CANCEL_QUEUE_PREFIX: ClassVar[str] = QueueNamePrefixes.CANCEL_REQUEST
    PRODUCER_LOCK_PREFIX: ClassVar[str] = "aidev_agent.producer_lock."
    REPLAY_LOCK_PREFIX: ClassVar[str] = "aidev_agent.replay_lock."
    ACTIVE_CONSUMER_PREFIX: ClassVar[str] = "aidev_agent.consumer_active."
    QUEUE_TTL_MS: ClassVar[int] = QueueTTLConfig.QUEUE_EXPIRE_MS
    BUFFER_FLUSH_INTERVAL: ClassVar[float] = 0.5
    SSE_PUBLISH_CHUNK_MAX_BYTES: ClassVar[int] = 256 * 1024
    REPLAY_LOCK_RETRY_INTERVAL: ClassVar[float] = 0.05
    REPLAY_MESSAGE_RETRY_INTERVAL: ClassVar[float] = 0.5

    _instance: Optional["RabbitMQMessageHandler"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> "RabbitMQMessageHandler":
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_rabbitmq()
        return cls._instance

    def _init_rabbitmq(self):
        """初始化 RabbitMQ 连接"""
        self._rabbitmq_url = self._get_rabbitmq_url()

        # 创建连接池
        pool_size = env.int("RABBITMQ_POOL_SIZE", 5)
        connection_timeout = env.float("RABBITMQ_CONNECTION_TIMEOUT", 10.0)
        self._connection_pool = RabbitMQConnectionPool(
            rabbitmq_url=self._rabbitmq_url,
            pool_size=pool_size,
            connection_timeout=connection_timeout,
        )
        logger.info(f"RabbitMQ connection pool initialized with size={pool_size}")

        # 消息缓冲队列：用于批量推送
        self._message_buffer: dict[str, list[Any]] = {}
        self._buffer_lock = threading.Lock()
        self._replay_wait_condition = threading.Condition()
        self._producer_lock_connections: dict[str, pika.BlockingConnection] = {}
        self._producer_lock_guard = threading.Lock()

        # flush 与 replay peek 的互斥锁（per thread_id，进程内）
        # 避免 replay 读取到本进程尚未完整发布的 flush 批次
        self._flush_peek_locks: dict[str, threading.Lock] = {}
        self._flush_peek_locks_guard = threading.Lock()

        # producer 只有在 EOD 已提交到 RabbitMQ 后才能写外部会话终态。
        # 同步 flush 失败时，后台 daemon 补发成功会唤醒同进程 producer。
        self._eod_commit_events: dict[str, set[threading.Event]] = {}
        self._eod_commit_events_lock = threading.Lock()

        # 后台守护线程
        self._daemon_thread: Optional[threading.Thread] = None
        self._daemon_running = False
        self._daemon_stop_event = threading.Event()

        # 启动守护线程
        self._start_daemon()

    def _get_rabbitmq_url(self) -> str:
        """构建 RabbitMQ 连接 URL"""
        host = env.str("RABBITMQ_HOST", "localhost")
        port = env.int("RABBITMQ_PORT", 5672)
        user = env.str("RABBITMQ_USER", "guest")
        password = env.str("RABBITMQ_PASSWORD", "guest")
        vhost = env.str("RABBITMQ_VHOST", "/")

        # vhost 需要 URL 编码
        if vhost.startswith("/"):
            vhost = vhost[1:]
        vhost_enc = quote(vhost, safe="")

        return f"amqp://{user}:{password}@{host}:{port}/{vhost_enc}"

    @contextmanager
    def _with_connection(self):
        """上下文管理器方式获取连接"""
        with self._connection_pool.connection() as conn:
            yield conn

    def _get_queue_name(self, thread_id: str) -> str:
        """获取 thread_id 对应的主队列名"""
        return f"{self.QUEUE_PREFIX}{thread_id}"

    def _get_cancel_queue_name(self, thread_id: str) -> str:
        """获取 thread_id 对应的取消请求队列名"""
        return f"{self.CANCEL_QUEUE_PREFIX}{thread_id}"

    def _get_producer_lock_queue_name(self, thread_id: str) -> str:
        """获取生产者互斥队列名。"""
        return f"{self.PRODUCER_LOCK_PREFIX}{thread_id}"

    def _get_replay_lock_queue_name(self, thread_id: str) -> str:
        """获取会话日志 replay 互斥队列名。"""
        return f"{self.REPLAY_LOCK_PREFIX}{thread_id}"

    def _get_active_consumer_queue_name(self, thread_id: str) -> str:
        """获取多消费者活跃状态队列名。"""
        return f"{self.ACTIVE_CONSUMER_PREFIX}{thread_id}"

    def _get_flush_peek_lock(self, thread_id: str) -> threading.Lock:
        """获取指定 thread_id 的 flush/peek 互斥锁（进程内，惰性创建）。"""
        with self._flush_peek_locks_guard:
            if thread_id not in self._flush_peek_locks:
                self._flush_peek_locks[thread_id] = threading.Lock()
            return self._flush_peek_locks[thread_id]

    def _create_dedicated_connection(self) -> pika.BlockingConnection:
        """创建不进入连接池的 RabbitMQ 连接，用于 exclusive queue 生命周期。"""
        params = pika.URLParameters(self._rabbitmq_url)
        params.heartbeat = 60
        params.blocked_connection_timeout = 300
        return pika.BlockingConnection(params)

    def _declare_exclusive_queue_on_connection(
        self,
        connection: pika.BlockingConnection,
        queue_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        """在独占连接上声明 exclusive queue，并关闭临时 channel。

        exclusive queue 的生命周期绑定 connection，而不是单个 channel。
        因此这里不能复用连接池里的 _with_channel()：连接池会把连接归还给其他
        RabbitMQ 操作，无法表达“持有该 exclusive queue 即持有锁”的生命周期。
        """
        channel = connection.channel()
        try:
            channel.queue_declare(
                queue=queue_name,
                exclusive=True,
                auto_delete=True,
                durable=False,
                arguments=arguments,
            )
        finally:
            if getattr(channel, "is_open", False):
                with contextlib.suppress(Exception):
                    channel.close()

    def _acquire_dedicated_exclusive_queue_connection(
        self,
        queue_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> pika.BlockingConnection:
        """创建 dedicated connection 并在其上持有一个 exclusive queue。"""
        connection = self._create_dedicated_connection()
        try:
            self._declare_exclusive_queue_on_connection(connection, queue_name, arguments=arguments)
            return connection
        except Exception:
            if getattr(connection, "is_open", False):
                with contextlib.suppress(Exception):
                    connection.close()
            raise

    def _notify_replay_waiters(self) -> None:
        """唤醒等待 replay lock 或新消息的本进程消费者。"""
        with self._replay_wait_condition:
            self._replay_wait_condition.notify_all()

    def register_eod_commit_event(self, thread_id: str, event: threading.Event) -> None:
        """注册 EOD 提交确认事件，供 producer 等待同步/后台 flush 的最终结果。"""
        with self._eod_commit_events_lock:
            self._eod_commit_events.setdefault(thread_id, set()).add(event)

    def unregister_eod_commit_event(self, thread_id: str, event: threading.Event) -> None:
        """移除尚未被 EOD 成功提交消费的确认事件。"""
        with self._eod_commit_events_lock:
            events = self._eod_commit_events.get(thread_id)
            if events is None:
                return
            events.discard(event)
            if not events:
                self._eod_commit_events.pop(thread_id, None)

    def _notify_eod_committed(self, thread_id: str, messages: list[Any]) -> None:
        """仅在包含 EOD 的完整批次成功发布后确认提交。"""
        if EOD_CHUNK not in messages:
            return
        with self._eod_commit_events_lock:
            events = self._eod_commit_events.pop(thread_id, set())
        for event in events:
            event.set()

    def _wait_for_replay_retry(self, deadline: float | None, interval: float) -> None:
        """等待下一次 replay 检查。

        本进程内有 buffer 写入或 replay lock 释放时会提前唤醒；跨进程 RabbitMQ 写入
        无法通过本地 Condition 感知，因此仍保留短超时作为兜底重试。
        """
        wait_time = interval
        if deadline is not None:
            remaining = deadline - time.time()
            if remaining <= 0:
                return
            wait_time = min(wait_time, remaining)

        with self._replay_wait_condition:
            self._replay_wait_condition.wait(timeout=wait_time)

    def _ensure_queue(self, channel: Any, thread_id: str) -> str:
        """确保持久化主队列存在，不创建 DLX/DLQ。"""
        main_queue_name = self._get_queue_name(thread_id)
        channel.queue_declare(
            queue=main_queue_name,
            durable=True,
            arguments={"x-expires": self.QUEUE_TTL_MS},
        )
        return main_queue_name

    def _delete_legacy_dead_letter_resources(self, thread_id: str) -> None:
        """删除旧实现遗留的 DLQ/DLX，不读取或恢复其中的历史消息。"""
        dlq_name = f"{QueueNamePrefixes.DEAD_LETTER_QUEUE}{thread_id}"
        dlx_exchange_name = f"aidev_agent.dlx.{thread_id}"
        connection = None
        channel = None
        try:
            connection = self._connection_pool.get_connection()
            for resource_type, resource_name in (("queue", dlq_name), ("exchange", dlx_exchange_name)):
                channel = connection.channel()
                try:
                    if resource_type == "queue":
                        channel.queue_delete(queue=resource_name)
                    else:
                        channel.exchange_delete(exchange=resource_name)
                except pika.exceptions.ChannelClosedByBroker as e:
                    if e.reply_code != 404:
                        raise
                finally:
                    if getattr(channel, "is_open", False):
                        channel.close()
                channel = None
        except Exception as e:
            logger.warning(f"Failed to delete legacy dead-letter resources for thread_id={thread_id}: {e}")
        finally:
            if channel is not None and getattr(channel, "is_open", False):
                with contextlib.suppress(Exception):
                    channel.close()
            if connection is not None:
                self._connection_pool.release_connection(connection)

    def _migrate_queue_if_needed(self, thread_id: str) -> bool:
        """检查并迁移不兼容的旧队列

        旧主队列携带 DLX 参数，RabbitMQ 不允许原地修改队列参数。
        发现不兼容声明时删除旧主队列，并清理遗留 DLQ/DLX；后续写入会按新参数重建。
        这个方法应该在首次使用队列时调用一次。

        Args:
            thread_id: 线程ID

        Returns:
            True 表示进行了迁移，False 表示无需迁移
        """
        main_queue_name = self._get_queue_name(thread_id)
        migrated = False
        connection = None
        channel = None

        try:
            # Queue 参数冲突会由 broker 主动关闭 channel。这里显式管理连接，避免
            # RabbitMQConnectionPool.connection() 把业务 channel 异常当成连接重试，
            # 继而在同一个 contextmanager 中二次 yield。
            connection = self._connection_pool.get_connection()
            channel = connection.channel()
            try:
                channel.queue_declare(
                    queue=main_queue_name,
                    durable=True,
                    arguments={"x-expires": self.QUEUE_TTL_MS},
                )
            except pika.exceptions.ChannelClosedByBroker as e:
                if e.reply_code != 406:
                    raise
                logger.warning(f"Queue {main_queue_name} has incompatible arguments, will be deleted")
                channel = connection.channel()
                channel.queue_delete(queue=main_queue_name)
                logger.info(f"Deleted incompatible queue {main_queue_name}")
                migrated = True

        except Exception as e:
            logger.error(f"Error during queue migration check: {e}")
        finally:
            if channel is not None and getattr(channel, "is_open", False):
                with contextlib.suppress(Exception):
                    channel.close()
            if connection is not None:
                self._connection_pool.release_connection(connection)
            if migrated:
                self._delete_legacy_dead_letter_resources(thread_id)

        return migrated

    # ================== replay-from-start / 并发控制 ==================

    def supports_replay_from_start(self) -> bool:
        """声明 RabbitMQ backend 支持从会话日志开头独立 replay。

        这个能力位供 GeneratorStreamingHelper 选择消费策略：RabbitMQ 返回 True，
        旧的 in-memory/默认 handler 返回 False，继续使用竞争消费与兼容恢复语义。
        """
        return True

    def acquire_producer(self, thread_id: str) -> bool:
        """使用 RabbitMQ exclusive queue 获取会话级生产者写入权。"""
        lock_queue = self._get_producer_lock_queue_name(thread_id)
        with self._producer_lock_guard:
            if thread_id in self._producer_lock_connections:
                return False

            connection = None
            try:
                connection = self._acquire_dedicated_exclusive_queue_connection(lock_queue)
                self._producer_lock_connections[thread_id] = connection
                logger.info("[RabbitMQ] producer lock acquired thread_id=%s queue=%s", thread_id, lock_queue)
                return True
            except Exception as e:
                logger.info("[RabbitMQ] producer lock busy thread_id=%s queue=%s error=%s", thread_id, lock_queue, e)
                if connection and getattr(connection, "is_open", False):
                    with contextlib.suppress(Exception):
                        connection.close()
                return False

    def release_producer(self, thread_id: str) -> None:
        """释放会话级生产者写入权。"""
        lock_queue = self._get_producer_lock_queue_name(thread_id)
        with self._producer_lock_guard:
            connection = self._producer_lock_connections.pop(thread_id, None)

        if not connection:
            logger.info(
                "[RabbitMQ] producer lock release skipped (no connection) thread_id=%s queue=%s",
                thread_id,
                lock_queue,
            )
            return

        logger.info(
            "[RabbitMQ] release_producer enter thread_id=%s queue=%s connection_is_open=%s",
            thread_id,
            lock_queue,
            getattr(connection, "is_open", None),
        )
        channel = None
        connection_already_closed = False
        try:
            if getattr(connection, "is_open", False):
                try:
                    channel = connection.channel()
                    with contextlib.suppress(Exception):
                        channel.queue_delete(queue=lock_queue)
                except Exception as e:
                    # 连接已被对端重置/关闭：exclusive queue 随连接断开自动删除，
                    # 无需再 queue_delete，降级走连接清理路径，不让异常冒泡
                    connection_already_closed = True
                    channel = None
                    logger.warning(
                        "[RabbitMQ] producer lock connection already closed, skip queue_delete "
                        "thread_id=%s queue=%s error=%s",
                        thread_id,
                        lock_queue,
                        e,
                    )
        finally:
            if channel and getattr(channel, "is_open", False):
                with contextlib.suppress(Exception):
                    channel.close()
            if getattr(connection, "is_open", False):
                with contextlib.suppress(Exception):
                    connection.close()
            logger.info(
                "[RabbitMQ] producer lock released thread_id=%s queue=%s connection_already_closed=%s",
                thread_id,
                lock_queue,
                connection_already_closed,
            )

    def _ensure_active_consumer_queue(self, channel: Any, thread_id: str) -> str:
        queue_name = self._get_active_consumer_queue_name(thread_id)
        channel.queue_declare(
            queue=queue_name,
            durable=True,
            arguments={"x-expires": self.QUEUE_TTL_MS},
        )
        return queue_name

    def acquire_consumer(self, thread_id: str) -> str:
        """注册一个活跃消费者；多个 consumer 可以同时存在。"""
        consumer_id = uuid.uuid4().hex
        with self._with_channel() as channel:
            queue_name = self._ensure_active_consumer_queue(channel, thread_id)
            payload = json.dumps({"consumer_id": consumer_id, "ts": time.time()}).encode()
            channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=payload,
                properties=pika.BasicProperties(delivery_mode=2),
            )
        logger.info("[RabbitMQ] consumer acquired thread_id=%s consumer_id=%s", thread_id, consumer_id[:8])
        return consumer_id

    def wait_for_previous_consumer(self, thread_id: str, timeout: float = 3.0) -> bool:
        """多端 replay 模式下消费者互不抢占，无需等待旧消费者退出。"""
        return True

    def check_consumer(self, thread_id: str, consumer_id: str) -> None:
        """多端 replay 模式下消费者互不抢占。"""

    def release_consumer(self, thread_id: str, consumer_id: str) -> None:
        """释放当前消费者登记，保留其他活跃消费者。"""
        try:
            with self._with_replay_lock(thread_id):
                self._release_consumer_locked(thread_id, consumer_id)
        except Exception:
            logger.exception(
                "[RabbitMQ] failed to release consumer thread_id=%s consumer_id=%s",
                thread_id,
                consumer_id[:8],
            )

    def _release_consumer_locked(self, thread_id: str, consumer_id: str) -> None:
        """在会话互斥锁内释放当前消费者登记。"""
        with self._with_channel() as channel:
            try:
                queue_name = self._ensure_active_consumer_queue(channel, thread_id)
                queue_info = channel.queue_declare(queue=queue_name, durable=True, passive=True)
            except Exception:
                logger.info(
                    "[RabbitMQ] consumer released thread_id=%s consumer_id=%s reason=missing_queue",
                    thread_id,
                    consumer_id[:8],
                )
                return

            remaining_bodies: list[bytes] = []
            removed = False
            for _ in range(queue_info.method.message_count):
                method_frame, _, body = channel.basic_get(queue=queue_name, auto_ack=True)
                if not method_frame:
                    break
                try:
                    data = json.loads(body)
                    if data.get("consumer_id") == consumer_id:
                        removed = True
                        continue
                except (json.JSONDecodeError, KeyError):
                    pass
                remaining_bodies.append(body)

            for body in remaining_bodies:
                channel.basic_publish(
                    exchange="",
                    routing_key=queue_name,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )

        logger.info(
            "[RabbitMQ] consumer released thread_id=%s consumer_id=%s removed=%s",
            thread_id,
            consumer_id[:8],
            removed,
        )

    def has_active_consumer(self, thread_id: str) -> bool:
        """检查指定 thread_id 是否有任意活跃消费者。"""
        try:
            with self._with_channel() as channel:
                queue_name = self._get_active_consumer_queue_name(thread_id)
                try:
                    queue_info = channel.queue_declare(queue=queue_name, durable=True, passive=True)
                except Exception:
                    return False
                return queue_info.method.message_count > 0
        except Exception as e:
            logger.warning(f"Error checking active consumers for thread_id={thread_id}: {e}")
            return False

    @contextmanager
    def _with_replay_lock(self, thread_id: str, timeout: float = 3.0) -> Iterator[Any]:
        """串行化同一会话的非破坏性 replay，避免并发 peek 分摊消息。"""
        deadline = time.time() + timeout
        lock_queue = self._get_replay_lock_queue_name(thread_id)

        while True:
            connection = None
            channel = None
            try:
                connection = self._acquire_dedicated_exclusive_queue_connection(
                    lock_queue,
                    arguments={"x-expires": self.QUEUE_TTL_MS},
                )
                channel = connection.channel()
            except Exception:
                if channel and getattr(channel, "is_open", False):
                    with contextlib.suppress(Exception):
                        channel.close()
                if connection and getattr(connection, "is_open", False):
                    with contextlib.suppress(Exception):
                        connection.close()
                connection = None
                channel = None
                if time.time() >= deadline:
                    raise
                self._wait_for_replay_retry(deadline, self.REPLAY_LOCK_RETRY_INTERVAL)
                continue

            try:
                yield channel
            finally:
                if channel and getattr(channel, "is_open", False):
                    with contextlib.suppress(Exception):
                        channel.close()
                if connection and getattr(connection, "is_open", False):
                    with contextlib.suppress(Exception):
                        connection.close()
                self._notify_replay_waiters()
            return

    # ================== 守护线程管理 ==================

    def _start_daemon(self) -> None:
        """启动后台守护线程"""
        if self._daemon_running and self._daemon_thread and self._daemon_thread.is_alive():
            return

        self._daemon_running = True
        self._daemon_stop_event.clear()
        self._daemon_thread = threading.Thread(target=self._daemon_worker, daemon=True, name="RabbitMQ-Daemon")
        self._daemon_thread.start()
        logger.info("RabbitMQ daemon thread started")

    def _stop_daemon(self) -> None:
        """停止后台守护线程"""
        if not self._daemon_running:
            return

        self._daemon_running = False
        self._daemon_stop_event.set()

        if self._daemon_thread and self._daemon_thread.is_alive():
            self._daemon_thread.join(timeout=2.0)
            logger.info("RabbitMQ daemon thread stopped")

    def _daemon_worker(self) -> None:
        """后台守护线程工作函数：每隔 0.5 秒批量推送消息到 RabbitMQ"""
        while self._daemon_running:
            try:
                # 等待批量刷新周期或直到停止事件触发
                if self._daemon_stop_event.wait(timeout=self.BUFFER_FLUSH_INTERVAL):
                    break

                # 批量推送消息
                self._flush_messages()
            except Exception as e:
                logger.error(f"Error in daemon worker: {e}")

        # 线程退出前，最后一次刷新所有消息
        try:
            self._flush_messages()
        except Exception as e:
            logger.error(f"Error flushing messages on daemon exit: {e}")

    @classmethod
    def _coalesce_sse_messages(cls, messages: list[Any]) -> list[Any]:
        """合并相邻 SSE 帧，减少 RabbitMQ 物理消息数并保持原始协议字节流。"""
        coalesced_messages: list[Any] = []
        sse_parts: list[str] = []
        sse_size = 0

        def flush_sse_parts() -> None:
            nonlocal sse_size
            if not sse_parts:
                return
            coalesced_messages.append("".join(sse_parts))
            sse_parts.clear()
            sse_size = 0

        for message in messages:
            if not isinstance(message, str) or not message.startswith("data: "):
                flush_sse_parts()
                coalesced_messages.append(message)
                continue

            message_size = len(message.encode("utf-8"))
            if sse_parts and sse_size + message_size > cls.SSE_PUBLISH_CHUNK_MAX_BYTES:
                flush_sse_parts()
            if message_size > cls.SSE_PUBLISH_CHUNK_MAX_BYTES:
                coalesced_messages.append(message)
                continue
            sse_parts.append(message)
            sse_size += message_size

        flush_sse_parts()
        return coalesced_messages

    @staticmethod
    def _expand_sse_messages(messages: list[Any]) -> list[Any]:
        """将 RabbitMQ 中合并的 SSE 字节流还原为调用方原有的逐帧消息。"""
        expanded_messages: list[Any] = []
        for message in messages:
            if not isinstance(message, str) or not message.startswith("data: ") or "\n\ndata: " not in message:
                expanded_messages.append(message)
                continue

            parts = message.split("\n\n")
            if parts[-1] or any(not part.startswith("data: ") for part in parts[:-1]):
                expanded_messages.append(message)
                continue
            expanded_messages.extend(f"{part}\n\n" for part in parts[:-1])
        return expanded_messages

    def _flush_messages(self) -> None:
        """批量推送缓冲区中的所有消息到 RabbitMQ

        对每个 thread_id，在 _flush_peek_lock 内完成"取出 buffer + publish"的原子操作，
        确保与 get_messages_since 的 queue peek 互斥，避免 replay 观察到未完整发布的 flush 批次。
        """
        # 快速检查是否有消息需要 flush
        with self._buffer_lock:
            if not self._message_buffer:
                return
            thread_ids_to_flush = list(self._message_buffer.keys())

        # 按 thread_id 逐个 flush，每个 thread_id 在 flush_peek_lock 内完成
        # "取出 buffer + publish" 的原子操作
        any_flushed = False
        for thread_id in thread_ids_to_flush:
            flush_peek_lock = self._get_flush_peek_lock(thread_id)
            try:
                with flush_peek_lock:
                    # 在 flush_peek_lock 内取出该 thread_id 的 buffer
                    with self._buffer_lock:
                        messages = self._message_buffer.pop(thread_id, [])
                    if not messages:
                        continue
                    messages_to_publish = self._coalesce_sse_messages(messages)

                    # 在同一个 flush_peek_lock 内 publish 到 RabbitMQ
                    with self._with_channel() as channel:
                        queue_name = self._ensure_queue(channel, thread_id)
                        for message in messages_to_publish:
                            body = pickle.dumps(message)
                            channel.basic_publish(
                                exchange="",
                                routing_key=queue_name,
                                body=body,
                                properties=pika.BasicProperties(delivery_mode=2),
                            )
                    logger.debug(
                        "Flushed %d logical messages as %d RabbitMQ messages to queue %s",
                        len(messages),
                        len(messages_to_publish),
                        queue_name,
                    )
                    if EOD_CHUNK in messages:
                        logger.info(
                            "[EOD] flush thread_id=%s logical=%d published=%d (background)",
                            thread_id,
                            len(messages),
                            len(messages_to_publish),
                        )
                    self._notify_eod_committed(thread_id, messages)
                    any_flushed = True
            except Exception as e:
                logger.error(f"Error flushing messages for thread_id={thread_id}: {e}")
                # 推送失败，将消息放回缓冲区（放到前面保持顺序）
                with self._buffer_lock:
                    if thread_id not in self._message_buffer:
                        self._message_buffer[thread_id] = []
                    self._message_buffer[thread_id] = messages + self._message_buffer[thread_id]

        if any_flushed:
            self._notify_replay_waiters()

    # ================== BaseMessageQueueHandler 接口实现 ==================

    def _ensure_daemon_alive(self) -> None:
        """确保守护线程存活（处理 Gunicorn fork 场景）

        在 Gunicorn 多进程模式下，Worker 进程 fork 后，守护线程不会被继承。
        此方法检查守护线程是否存活，如果不存活则重新启动。
        """
        is_alive = self._daemon_thread.is_alive() if self._daemon_thread else False
        if not self._daemon_thread or not is_alive:
            logger.warning("RabbitMQ daemon thread not alive, restarting...")
            self._start_daemon()

    def put(self, thread_id: str, message: Any) -> None:
        """向指定 thread_id 的队列中添加消息

        消息会先添加到本地缓冲区，由后台守护线程每隔 0.5 秒批量推送到 RabbitMQ。
        """
        # 确保守护线程存活（处理 Gunicorn fork 场景）
        self._ensure_daemon_alive()

        # 添加到缓冲区
        with self._buffer_lock:
            if thread_id not in self._message_buffer:
                self._message_buffer[thread_id] = []
            self._message_buffer[thread_id].append(message)
        self._notify_replay_waiters()

    def flush(self, thread_id: Optional[str] = None) -> None:
        """立即推送缓冲区中的消息到 RabbitMQ

        Args:
            thread_id: 如果指定，只推送该 thread_id 的消息；否则推送所有消息
        """
        if thread_id:
            # 只推送指定 thread_id 的消息，在 flush_peek_lock 内原子完成
            flush_peek_lock = self._get_flush_peek_lock(thread_id)
            with flush_peek_lock:
                with self._buffer_lock:
                    messages_to_flush = self._message_buffer.pop(thread_id, [])

                if not messages_to_flush:
                    return

                logger.debug("[Streaming] rabbitmq flush thread_id=%s, count=%d", thread_id, len(messages_to_flush))
                messages_to_publish = self._coalesce_sse_messages(messages_to_flush)

                try:
                    with self._with_channel() as channel:
                        queue_name = self._ensure_queue(channel, thread_id)

                        for message in messages_to_publish:
                            body = pickle.dumps(message)
                            channel.basic_publish(
                                exchange="",
                                routing_key=queue_name,
                                body=body,
                                properties=pika.BasicProperties(delivery_mode=2),
                            )
                    if EOD_CHUNK in messages_to_flush:
                        logger.info(
                            "[EOD] flush thread_id=%s logical=%d published=%d",
                            thread_id,
                            len(messages_to_flush),
                            len(messages_to_publish),
                        )
                    self._notify_eod_committed(thread_id, messages_to_flush)
                    self._notify_replay_waiters()
                except Exception as e:
                    logger.error(f"Error flushing messages for {thread_id}: {e}")
                    # 推送失败，放回缓冲区
                    with self._buffer_lock:
                        if thread_id not in self._message_buffer:
                            self._message_buffer[thread_id] = []
                        self._message_buffer[thread_id] = messages_to_flush + self._message_buffer[thread_id]
                    self._notify_replay_waiters()
                    raise
        else:
            # 推送所有消息
            self._flush_messages()

    def _peek_queue_messages(self, channel: Any, queue_name: str) -> list[Any]:
        """非破坏性读取队列中的全部消息，仅在读取或 requeue 异常时记录诊断。"""
        messages = []
        delivery_tags = []
        message_count = 0
        nack_error = None

        try:
            queue_info = channel.queue_declare(queue=queue_name, durable=True, passive=True)
            message_count = queue_info.method.message_count
            for _ in range(message_count):
                method_frame, _, body = channel.basic_get(queue=queue_name, auto_ack=False)
                if not method_frame:
                    break
                delivery_tags.append(method_frame.delivery_tag)
                msg = pickle.loads(body)
                messages.append(msg)
        finally:
            for tag in delivery_tags:
                try:
                    channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception as e:
                    nack_error = e
            if message_count != len(messages) or nack_error is not None:
                logger.warning(
                    "[EOD] _peek_queue_messages queue=%s declared=%d got=%d nack_error=%s peek_eod=%s",
                    queue_name,
                    message_count,
                    len(messages),
                    nack_error,
                    EOD_CHUNK in messages,
                )

        return messages

    def get_messages_since(self, thread_id: str, offset: int, timeout: Optional[float] = None) -> tuple[list[Any], int]:
        """从会话日志的指定 offset 开始读取消息，读取后不删除底层缓存。"""
        start_time = time.time()
        deadline = start_time + timeout if timeout is not None else None
        offset = max(offset, 0)
        flush_peek_lock = self._get_flush_peek_lock(thread_id)

        while True:
            try:
                with self._with_replay_lock(thread_id) as channel:
                    main_queue_name = self._ensure_queue(channel=channel, thread_id=thread_id)

                    # replay offset 只描述 RabbitMQ 已提交队列，不能包含本地未发布 buffer。
                    # flush_peek_lock 避免读取到本进程尚未完整发布的 flush 批次。
                    with flush_peek_lock:
                        queue_info = channel.queue_declare(queue=main_queue_name, durable=True, passive=True)
                        committed_count = queue_info.method.message_count

                        # 没有新消息时避免反复 basic_get/basic_nack 全量扫描历史队列。
                        all_messages = (
                            self._peek_queue_messages(channel, main_queue_name) if committed_count > offset else None
                        )

                if all_messages is not None:
                    next_offset = len(all_messages)
                    if next_offset > offset:
                        return self._expand_sse_messages(all_messages[offset:]), next_offset
            except Exception:
                logger.exception("Error in get_messages_since for thread_id=%s", thread_id)

            if deadline is not None and time.time() >= deadline:
                raise TimeoutError("No message available within timeout")

            self._wait_for_replay_retry(deadline, self.REPLAY_MESSAGE_RETRY_INTERVAL)

    def get(self, thread_id: str, timeout: Optional[float] = None) -> list[Any]:
        """RabbitMQ replay 必须携带 offset，禁止使用破坏性旧消费接口。"""
        raise NotImplementedError("RabbitMQMessageHandler requires get_messages_since(thread_id, offset, timeout)")

    def has_pending_messages(self, thread_id: str) -> bool:
        """检查是否有未消费的消息（用于判断是否需要创建生产者）

        检查主队列以及本地缓冲区是否有消息。
        如果有消息，说明已有生产者在工作或已完成但消息未消费完，不需要创建新的生产者。

        Args:
            thread_id: 线程ID

        Returns:
            True 表示有未消费的消息，不需要创建新的生产者
            False 表示没有消息，需要创建生产者
        """
        # 检查本地缓冲区
        with self._buffer_lock:
            if thread_id in self._message_buffer and self._message_buffer[thread_id]:
                return True

        # 检查 RabbitMQ 主队列。
        try:
            main_queue_name = self._get_queue_name(thread_id)
            with self._with_channel() as channel:
                try:
                    queue_info = channel.queue_declare(queue=main_queue_name, durable=True, passive=True)
                    return queue_info.method.message_count > 0
                except Exception:
                    return False
        except Exception as e:
            logger.error(f"Error checking pending messages for thread_id={thread_id}: {e}")
            return False

    def restore_messages(self, thread_id: str) -> int:
        """Replay 模式不移动消息，无需恢复。"""
        return 0

    def _safe_purge_queue(self, connection: Any, queue_name: str, passive_check: bool = False) -> bool:
        """安全清空队列（内部方法）

        使用独立 channel 执行操作，避免 passive declare 触发 RabbitMQ 404
        channel error 后导致 channel 被关闭，影响后续操作。

        Args:
            connection: RabbitMQ connection
            queue_name: 队列名
            passive_check: 是否先进行被动声明检查队列是否存在

        Returns:
            True 表示成功清空，False 表示失败或队列不存在
        """
        channel = None
        try:
            channel = connection.channel()
            if passive_check:
                channel.queue_declare(queue=queue_name, durable=True, passive=True)
            channel.queue_purge(queue=queue_name)
            logger.debug(f"Purged queue {queue_name}")
            return True
        except Exception as e:
            if not passive_check:  # 非被动检查模式下才记录警告
                logger.warning(f"Failed to purge queue {queue_name}: {e}")
            return False
        finally:
            if channel and getattr(channel, "is_open", False):
                with contextlib.suppress(Exception):
                    channel.close()

    def _purge_all_queues(self, thread_id: str, include_cancel_queue: bool = True) -> None:
        """清空指定 thread_id 的所有队列（内部方法）

        每个 purge 操作使用独立 channel，避免某个队列不存在时 channel 被关闭
        导致后续 purge 静默失败。

        Args:
            thread_id: 线程ID
            include_cancel_queue: 是否同时清空取消请求队列
        """
        try:
            with self._with_connection() as connection:
                # 每个 purge 操作使用独立 channel，避免 404 channel error 影响后续操作
                self._safe_purge_queue(connection, self._get_queue_name(thread_id))
                # 清空取消请求队列（如果需要，先检查是否存在）
                if include_cancel_queue:
                    self._safe_purge_queue(connection, self._get_cancel_queue_name(thread_id), passive_check=True)
        except Exception as e:
            logger.error(f"Error purging queues for thread_id={thread_id}: {e}")

    def _delete_all_resources(self, thread_id: str) -> None:
        """
        删除指定 thread_id 的所有 RabbitMQ 队列资源。
        在消费完成后调用，主动释放资源，避免空队列空占 1 小时。
        """
        try:
            with self._with_channel() as channel:
                # 收集所有需要删除的队列名
                queue_names = [
                    self._get_queue_name(thread_id),
                    self._get_cancel_queue_name(thread_id),
                    self._get_active_consumer_queue_name(thread_id),
                ]
                # 追加 MultiProcessMixin 管理的信号队列
                queue_names.extend(self._get_signal_queue_names(thread_id))

                logger.info(f"Deleting all RabbitMQ resources for thread_id={thread_id}: {queue_names}")
                # 批量删除所有队列（queue_delete 对不存在的队列是幂等的）
                for queue_name in queue_names:
                    try:
                        channel.queue_delete(queue=queue_name)
                    except Exception as e:
                        logger.exception(f"Queue {queue_name} delete failed: {e}")

                logger.info(f"Deleted all RabbitMQ resources for thread_id={thread_id}")
        except Exception as e:
            logger.error(f"Error deleting resources for thread_id={thread_id}: {e}")

    def mark_completed(self, thread_id: str) -> None:
        """标记流已完成并清理队列

        消费者在读取到结束标记时调用此方法：
        1. 先清理本地缓冲区（防止守护线程 flush 时重建已删除的队列）
        2. 清空所有队列中的消息（purge）
        3. 主动删除所有队列（delete）

        Args:
            thread_id: 线程ID
        """
        # 先清理本地缓冲区，防止守护线程在队列删除后仍尝试 flush 残留消息
        with self._buffer_lock:
            if thread_id in self._message_buffer:
                self._message_buffer.pop(thread_id, None)

        self._purge_all_queues(thread_id, include_cancel_queue=True)
        self._delete_all_resources(thread_id)

        # 清理 flush_peek_lock（session 已结束，不再需要）
        with self._flush_peek_locks_guard:
            self._flush_peek_locks.pop(thread_id, None)

    def request_cancel(self, thread_id: str) -> None:
        """请求取消该 thread_id 的流。幂等：向取消队列投递一条消息，生产者轮询时消费到即退出。"""
        try:
            with self._with_channel() as channel:
                cancel_queue_name = self._get_cancel_queue_name(thread_id)
                channel.queue_declare(
                    queue=cancel_queue_name,
                    durable=True,
                    arguments={"x-expires": self.QUEUE_TTL_MS},
                )
                channel.basic_publish(
                    exchange="",
                    routing_key=cancel_queue_name,
                    body=b"1",
                    properties=pika.BasicProperties(delivery_mode=1),
                )
                logger.debug(f"Requested cancel for thread_id={thread_id}")
        except Exception as e:
            logger.warning(f"Failed to request cancel for thread_id={thread_id}: {e}")

    def is_cancel_requested(self, thread_id: str) -> bool:
        """检查是否已请求取消该 thread_id 的流；若存在取消消息则消费一条并返回 True。"""
        try:
            with self._with_channel() as channel:
                cancel_queue_name = self._get_cancel_queue_name(thread_id)
                try:
                    channel.queue_declare(queue=cancel_queue_name, durable=True, passive=True)
                except Exception:
                    return False
                method_frame, _, _ = channel.basic_get(queue=cancel_queue_name, auto_ack=False)
                if method_frame:
                    channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                    return True
                return False
        except Exception as e:
            logger.debug(f"Error checking cancel for thread_id={thread_id}: {e}")
            return False

    def clear(self, thread_id: str) -> None:
        """清空指定 thread_id 的主队列和控制队列。"""
        # 清空缓冲区中的消息
        with self._buffer_lock:
            if thread_id in self._message_buffer:
                self._message_buffer[thread_id] = []

        # 检查并迁移不兼容的旧队列
        self._migrate_queue_if_needed(thread_id)

        # 清空所有队列
        self._purge_all_queues(thread_id, include_cancel_queue=True)

    def get_cached_count(self, thread_id: str) -> int:
        """获取主队列中的消息数量"""
        try:
            with self._with_channel() as channel:
                queue_name = self._get_queue_name(thread_id)
                try:
                    queue_info = channel.queue_declare(queue=queue_name, durable=True, passive=True)
                    return queue_info.method.message_count
                except Exception:
                    return 0
        except Exception as e:
            logger.error(f"Error getting cached count: {e}")
            return 0

    def get_total_count(self, thread_id: str) -> int:
        """获取主队列消息数量。"""
        return self.get_cached_count(thread_id)

    # is_empty() 和 size() 使用基类的通用实现

    def __del__(self):
        """析构函数：停止守护线程并关闭连接池"""
        with contextlib.suppress(Exception):
            with self._producer_lock_guard:
                lock_connections = list(self._producer_lock_connections.values())
                self._producer_lock_connections.clear()
            for connection in lock_connections:
                if getattr(connection, "is_open", False):
                    with contextlib.suppress(Exception):
                        connection.close()
        with contextlib.suppress(Exception):
            self._stop_daemon()
        with contextlib.suppress(Exception):
            if hasattr(self, "_connection_pool"):
                self._connection_pool.close()

    def list_thread_ids(self) -> list[str]:
        """列出所有 thread_id

        注意：此方法仅返回当前缓冲区中的 thread_id。
        如果需要列出所有 RabbitMQ 中的队列，需要使用管理 API。
        """
        with self._buffer_lock:
            return list(self._message_buffer.keys())

    def get_dlq_messages(self, thread_id: str) -> list[Any]:
        """RabbitMQ replay 不使用死信队列。"""
        return []
