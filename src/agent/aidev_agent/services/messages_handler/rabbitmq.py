import contextlib
import pickle
import queue
import threading
import time
from contextlib import contextmanager
from logging import getLogger
from typing import TYPE_CHECKING, Any, ClassVar, Optional

if TYPE_CHECKING:
    import pika.channel
from urllib.parse import quote

import pika
from environs import Env

from .base import BaseMessageQueueHandler, QueueTTLConfig
from .constants import QueueNamePrefixes
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
    每个 thread_id 对应一个主队列和一个死信队列。

    消息流转机制（使用死信队列优化性能）：
    - 主队列：存放待消费的消息
    - 死信队列：存放已消费但未确认完成的消息

    工作流程：
    1. 生产者将消息放入主队列
    2. 消费者从主队列获取消息，ack 后消息自动进入死信队列
    3. 消费者断开重连时，将死信队列的消息移回主队列，从头消费
    4. 流完成时（mark_completed），清空主队列和死信队列

    特点：
    - 避免每次都全量读取消息（只读取主队列中的新消息）
    - 支持断点续传（从死信队列恢复消息）
    - 后台守护线程每隔 0.5 秒批量推送消息，减少连接开销
    """

    # 使用统一的队列名称前缀和 TTL 配置
    QUEUE_PREFIX: ClassVar[str] = QueueNamePrefixes.MESSAGE_QUEUE
    DLX_EXCHANGE_PREFIX: ClassVar[str] = "aidev_agent.dlx."  # 死信交换机前缀（无需抽取）
    DLQ_PREFIX: ClassVar[str] = QueueNamePrefixes.DEAD_LETTER_QUEUE
    CANCEL_QUEUE_PREFIX: ClassVar[str] = QueueNamePrefixes.CANCEL_REQUEST
    QUEUE_TTL_MS: ClassVar[int] = QueueTTLConfig.QUEUE_EXPIRE_MS

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

    def _get_dlx_exchange_name(self, thread_id: str) -> str:
        """获取 thread_id 对应的死信交换机名"""
        return f"{self.DLX_EXCHANGE_PREFIX}{thread_id}"

    def _get_dlq_name(self, thread_id: str) -> str:
        """获取 thread_id 对应的死信队列名"""
        return f"{self.DLQ_PREFIX}{thread_id}"

    def _get_cancel_queue_name(self, thread_id: str) -> str:
        """获取 thread_id 对应的取消请求队列名"""
        return f"{self.CANCEL_QUEUE_PREFIX}{thread_id}"

    def _ensure_queue_with_dlx(self, channel: Any, thread_id: str) -> tuple[str, str]:
        """确保主队列和死信队列都存在，返回 (主队列名, 死信队列名)

        死信队列机制：
        - 当消息被 ack 时，不会进入死信队列（这是正常消费）
        - 当消息被 reject/nack 且 requeue=False 时，进入死信队列
        - 我们使用 reject(requeue=False) 将已读取的消息移到死信队列
        """
        main_queue_name = self._get_queue_name(thread_id)
        dlx_exchange_name = self._get_dlx_exchange_name(thread_id)
        dlq_name = self._get_dlq_name(thread_id)

        # 1. 声明死信交换机（direct 类型）
        channel.exchange_declare(
            exchange=dlx_exchange_name,
            exchange_type="direct",
            durable=True,
        )

        # 2. 声明死信队列
        channel.queue_declare(
            queue=dlq_name,
            durable=True,
            arguments={"x-expires": self.QUEUE_TTL_MS},
        )

        # 3. 绑定死信队列到死信交换机
        channel.queue_bind(
            queue=dlq_name,
            exchange=dlx_exchange_name,
            routing_key=dlq_name,  # 使用队列名作为 routing key
        )

        # 4. 声明主队列，配置死信交换机
        main_queue_args = {
            "x-expires": self.QUEUE_TTL_MS,
            "x-dead-letter-exchange": dlx_exchange_name,
            "x-dead-letter-routing-key": dlq_name,
        }
        channel.queue_declare(
            queue=main_queue_name,
            durable=True,
            arguments=main_queue_args,
        )

        return main_queue_name, dlq_name

    def _migrate_queue_if_needed(self, thread_id: str) -> bool:
        """检查并迁移不兼容的旧队列

        如果队列存在但参数不兼容（例如没有死信配置），则删除旧队列。
        这个方法应该在首次使用队列时调用一次。

        Args:
            thread_id: 线程ID

        Returns:
            True 表示进行了迁移，False 表示无需迁移
        """
        main_queue_name = self._get_queue_name(thread_id)

        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                # 尝试被动声明来检查队列是否存在
                try:
                    channel.queue_declare(queue=main_queue_name, durable=True, passive=True)
                except Exception:
                    # 队列不存在，无需迁移
                    return False

                # 队列存在，尝试用新参数声明
                dlx_exchange_name = self._get_dlx_exchange_name(thread_id)
                dlq_name = self._get_dlq_name(thread_id)

                # 先声明死信交换机和队列
                channel.exchange_declare(exchange=dlx_exchange_name, exchange_type="direct", durable=True)
                channel.queue_declare(queue=dlq_name, durable=True, arguments={"x-expires": self.QUEUE_TTL_MS})
                channel.queue_bind(queue=dlq_name, exchange=dlx_exchange_name, routing_key=dlq_name)

                # 尝试声明主队列（会检查参数是否匹配）
                try:
                    channel.queue_declare(
                        queue=main_queue_name,
                        durable=True,
                        arguments={
                            "x-expires": self.QUEUE_TTL_MS,
                            "x-dead-letter-exchange": dlx_exchange_name,
                            "x-dead-letter-routing-key": dlq_name,
                        },
                    )
                    # 声明成功，参数匹配，无需迁移
                    return False
                except Exception as e:
                    if "PRECONDITION_FAILED" not in str(e):
                        raise
                    # 参数不匹配，需要删除旧队列
                    logger.warning(f"Queue {main_queue_name} has incompatible arguments, will be deleted")

            # 使用新连接删除旧队列（因为上面的 channel 可能已关闭）
            with self._with_connection() as connection:
                channel = connection.channel()
                channel.queue_delete(queue=main_queue_name)
                logger.info(f"Deleted incompatible queue {main_queue_name}")
                return True

        except Exception as e:
            logger.error(f"Error during queue migration check: {e}")
            return False

    def _ensure_queue(self, channel: Any, thread_id: str) -> str:
        """确保队列存在，返回主队列名（兼容旧接口）"""
        main_queue_name, _ = self._ensure_queue_with_dlx(channel, thread_id)
        return main_queue_name

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
                # 等待 0.5 秒或直到停止事件触发
                if self._daemon_stop_event.wait(timeout=0.5):
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

    def _flush_messages(self) -> None:
        """批量推送缓冲区中的所有消息到 RabbitMQ"""
        # 获取所有待推送的消息
        messages_to_flush: dict[str, list[Any]] = {}
        with self._buffer_lock:
            if not self._message_buffer:
                return

            # 复制并清空缓冲区
            messages_to_flush = self._message_buffer.copy()
            self._message_buffer.clear()

        if not messages_to_flush:
            return

        # 批量推送到 RabbitMQ
        try:
            with self._with_connection() as connection:
                channel = connection.channel()

                for thread_id, messages in messages_to_flush.items():
                    if not messages:
                        continue

                    queue_name = self._ensure_queue(channel, thread_id)

                    # 批量发布消息
                    for message in messages:
                        body = pickle.dumps(message)
                        channel.basic_publish(
                            exchange="",
                            routing_key=queue_name,
                            body=body,
                            properties=pika.BasicProperties(delivery_mode=2),  # 持久化消息
                        )

                    logger.debug(f"Flushed {len(messages)} messages to queue {queue_name}")
        except Exception as e:
            logger.error(f"Error flushing messages to RabbitMQ: {e}")
            # 如果推送失败，将消息放回缓冲区
            with self._buffer_lock:
                for thread_id, messages in messages_to_flush.items():
                    if thread_id not in self._message_buffer:
                        self._message_buffer[thread_id] = []
                    self._message_buffer[thread_id].extend(messages)

    # ================== 死信队列操作 ==================

    def _restore_from_dlq(self, thread_id: str) -> int:
        """将死信队列中的消息恢复到主队列（用于断点续传）

        断点续传时，DLQ 中的消息（已被旧消费者读取过）需要与主队列中的消息（未被读取）
        合并，且 DLQ 消息应该排在前面，保证消息的正确顺序：
        [DLQ历史消息] + [主队列新消息] = 完整的消息序列

        Args:
            thread_id: 线程ID

        Returns:
            恢复的消息数量
        """
        with self._with_connection() as connection:
            channel = connection.channel()
            main_queue_name, dlq_name = self._ensure_queue_with_dlx(channel, thread_id)

            # 检查死信队列中的消息数量
            try:
                dlq_info = channel.queue_declare(queue=dlq_name, durable=True, passive=True)
                dlq_count = dlq_info.method.message_count
            except Exception:
                # 死信队列不存在
                return 0

            if dlq_count == 0:
                return 0

            # 检查主队列中的消息数量
            try:
                main_queue_info = channel.queue_declare(queue=main_queue_name, durable=True, passive=True)
                main_queue_count = main_queue_info.method.message_count
            except Exception:
                main_queue_count = 0

            logger.info(f"Restoring messages for thread_id={thread_id}: DLQ={dlq_count}, main_queue={main_queue_count}")

            # 1. 先把主队列中的消息暂存（如果有的话）
            main_queue_messages = []
            if main_queue_count > 0:
                for _ in range(main_queue_count):
                    method_frame, properties, body = channel.basic_get(queue=main_queue_name, auto_ack=True)
                    if not method_frame:
                        break
                    main_queue_messages.append(body)

            # 2. 从 DLQ 获取所有消息
            dlq_messages = []
            for _ in range(dlq_count):
                method_frame, properties, body = channel.basic_get(queue=dlq_name, auto_ack=False)
                if not method_frame:
                    break
                dlq_messages.append((method_frame.delivery_tag, body))

            # 3. 按正确顺序重新发布到主队列：先 DLQ（历史），后主队列（新消息）
            for _, body in dlq_messages:
                channel.basic_publish(
                    exchange="",
                    routing_key=main_queue_name,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )

            for body in main_queue_messages:
                channel.basic_publish(
                    exchange="",
                    routing_key=main_queue_name,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )

            # 4. 确认 DLQ 中的消息（删除）
            for delivery_tag, _ in dlq_messages:
                channel.basic_ack(delivery_tag=delivery_tag)

            restored_count = len(dlq_messages)
            logger.info(
                f"Restored {restored_count} messages from DLQ for thread_id={thread_id}, "
                f"merged with {len(main_queue_messages)} main queue messages"
            )
            return restored_count

    def _get_dlq_count(self, thread_id: str) -> int:
        """获取死信队列中的消息数量"""
        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                dlq_name = self._get_dlq_name(thread_id)
                try:
                    dlq_info = channel.queue_declare(queue=dlq_name, durable=True, passive=True)
                    return dlq_info.method.message_count
                except Exception:
                    return 0
        except Exception as e:
            logger.error(f"Error getting DLQ count: {e}")
            return 0

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

    def flush(self, thread_id: Optional[str] = None) -> None:
        """立即推送缓冲区中的消息到 RabbitMQ

        Args:
            thread_id: 如果指定，只推送该 thread_id 的消息；否则推送所有消息
        """
        if thread_id:
            # 只推送指定 thread_id 的消息
            messages_to_flush = []
            with self._buffer_lock:
                if thread_id in self._message_buffer:
                    messages_to_flush = self._message_buffer[thread_id]
                    self._message_buffer[thread_id] = []

            if not messages_to_flush:
                return

            logger.debug("[Streaming] rabbitmq flush thread_id=%s, count=%d", thread_id, len(messages_to_flush))

            try:
                with self._with_connection() as connection:
                    channel = connection.channel()
                    queue_name = self._ensure_queue(channel, thread_id)

                    for message in messages_to_flush:
                        body = pickle.dumps(message)
                        channel.basic_publish(
                            exchange="",
                            routing_key=queue_name,
                            body=body,
                            properties=pika.BasicProperties(delivery_mode=2),
                        )
            except Exception as e:
                logger.error(f"Error flushing messages for {thread_id}: {e}")
                # 推送失败，放回缓冲区
                with self._buffer_lock:
                    if thread_id not in self._message_buffer:
                        self._message_buffer[thread_id] = []
                    self._message_buffer[thread_id].extend(messages_to_flush)
                raise
        else:
            # 推送所有消息
            self._flush_messages()

    def _get_available_messages(self, thread_id: str, max_messages: int = 0) -> list[Any]:
        """从主队列获取可用消息

        消息被读取后，通过 reject(requeue=False) 移动到死信队列。
        这样实现增量读取，而不是每次全量读取。

        Args:
            thread_id: 线程ID
            max_messages: 最大获取消息数量，0 表示获取所有可用消息

        Returns:
            消息列表
        """
        with self._with_connection() as connection:
            channel = connection.channel()
            main_queue_name = self._ensure_queue(channel, thread_id)

            # 查询主队列中有多少消息
            queue_info = channel.queue_declare(queue=main_queue_name, durable=True, passive=True)
            available_count = queue_info.method.message_count

            if available_count == 0:
                return []

            # 确定要获取的消息数量
            fetch_count = available_count if max_messages == 0 else min(available_count, max_messages)

            # 获取消息
            messages = []
            for _ in range(fetch_count):
                method_frame, properties, body = channel.basic_get(queue=main_queue_name, auto_ack=False)
                if not method_frame:
                    break

                message = pickle.loads(body)
                messages.append(message)

                # 拒绝消息（不重新入队），消息会进入死信队列
                channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=False)

            if messages:
                logger.debug(f"Fetched {len(messages)} messages from queue {main_queue_name}, moved to DLQ")

            return messages

    def _get_block(self, thread_id: str, timeout: Optional[float] = None) -> list[Any]:
        """阻塞方式获取消息

        Args:
            thread_id: 线程ID
            timeout: 超时时间（秒）

        Returns:
            消息列表

        Raises:
            TimeoutError: 超时时抛出
        """
        start_time = time.time()

        while True:
            try:
                messages = self._get_available_messages(thread_id)
                if messages:
                    return messages
            except Exception as e:
                logger.exception(f"Error in _get_block: {e}")

            # 检查超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.debug("[Streaming] rabbitmq get timeout thread_id=%s, elapsed=%.3fs", thread_id, elapsed)
                    raise TimeoutError("No message available within timeout")

            # 等待一小段时间后重试（轮询方式）
            time.sleep(0.1)

    def get(self, thread_id: str, timeout: Optional[float] = None) -> list[Any]:
        """从指定 thread_id 的队列中获取消息

        增量获取：只获取主队列中的新消息，已读取的消息会移动到死信队列。

        Args:
            thread_id: 线程ID
            timeout: 超时时间（秒）

        Returns:
            消息列表

        Raises:
            TimeoutError: 队列为空且超时时抛出
        """
        return self._get_block(thread_id, timeout=timeout)

    def has_pending_messages(self, thread_id: str) -> bool:
        """检查是否有未消费的消息（用于判断是否需要创建生产者）

        检查主队列、死信队列以及本地缓冲区是否有消息。
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

        # 检查 RabbitMQ 主队列和死信队列
        # 每次 passive declare 使用独立 channel，避免主队列不存在时
        # channel 被 404 error 关闭导致 DLQ 检查静默失败
        try:
            with self._with_connection() as connection:
                main_queue_name = self._get_queue_name(thread_id)
                dlq_name = self._get_dlq_name(thread_id)

                # 检查主队列（独立 channel）
                try:
                    channel = connection.channel()
                    queue_info = channel.queue_declare(queue=main_queue_name, durable=True, passive=True)
                    if queue_info.method.message_count > 0:
                        return True
                except Exception:
                    pass

                # 检查死信队列（独立 channel）
                try:
                    channel = connection.channel()
                    dlq_info = channel.queue_declare(queue=dlq_name, durable=True, passive=True)
                    if dlq_info.method.message_count > 0:
                        return True
                except Exception:
                    pass

                return False
        except Exception as e:
            logger.error(f"Error checking pending messages for thread_id={thread_id}: {e}")
            return False

    def restore_messages(self, thread_id: str) -> int:
        """将死信队列中的消息恢复到主队列（断点续传）

        消费者重连时调用此方法，将之前消费过的消息恢复到主队列，从头开始消费。

        Args:
            thread_id: 线程ID

        Returns:
            恢复的消息数量
        """
        return self._restore_from_dlq(thread_id)

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
                self._safe_purge_queue(connection, self._get_dlq_name(thread_id))

                # 清空取消请求队列（如果需要，先检查是否存在）
                if include_cancel_queue:
                    self._safe_purge_queue(connection, self._get_cancel_queue_name(thread_id), passive_check=True)
        except Exception as e:
            logger.error(f"Error purging queues for thread_id={thread_id}: {e}")

    def _delete_all_resources(self, thread_id: str) -> None:
        """
        删除指定 thread_id 的所有 RabbitMQ 资源（队列 + 交换机）
        在消费完成后调用，主动释放资源，避免空队列空占 1 小时以及死信交换机永久残留。
        """
        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                # 收集所有需要删除的队列名
                queue_names = [
                    self._get_queue_name(thread_id),
                    self._get_dlq_name(thread_id),
                    self._get_cancel_queue_name(thread_id),
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

                # 删除死信交换机（exchange_delete 对不存在的交换机也是幂等的）
                try:
                    channel.exchange_delete(exchange=self._get_dlx_exchange_name(thread_id))
                    logger.debug(f"Deleted exchange {self._get_dlx_exchange_name(thread_id)}")
                except Exception as e:
                    logger.debug(f"Exchange {self._get_dlx_exchange_name(thread_id)} delete failed: {e}")

                logger.info(f"Deleted all RabbitMQ resources for thread_id={thread_id}")
        except Exception as e:
            logger.error(f"Error deleting resources for thread_id={thread_id}: {e}")

    def mark_completed(self, thread_id: str) -> None:
        """标记流已完成并清理队列

        消费者在读取到结束标记时调用此方法：
        1. 先清理本地缓冲区（防止守护线程 flush 时重建已删除的队列）
        2. 清空所有队列中的消息（purge）
        3. 主动删除所有队列和交换机（delete）

        Args:
            thread_id: 线程ID
        """
        # 先清理本地缓冲区，防止守护线程在队列删除后仍尝试 flush 残留消息
        with self._buffer_lock:
            if thread_id in self._message_buffer:
                self._message_buffer.pop(thread_id, None)

        self._purge_all_queues(thread_id, include_cancel_queue=True)
        self._delete_all_resources(thread_id)

    def request_cancel(self, thread_id: str) -> None:
        """请求取消该 thread_id 的流。幂等：向取消队列投递一条消息，生产者轮询时消费到即退出。"""
        try:
            with self._with_connection() as connection:
                channel = connection.channel()
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
            with self._with_connection() as connection:
                channel = connection.channel()
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
        """清空指定 thread_id 的所有队列（主队列和死信队列）"""
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
            with self._with_connection() as connection:
                channel = connection.channel()
                queue_name = self._get_queue_name(thread_id)
                queue_info = channel.queue_declare(queue=queue_name, durable=True, passive=True)
                return queue_info.method.message_count
        except Exception as e:
            logger.error(f"Error getting cached count: {e}")
            return 0

    def get_total_count(self, thread_id: str) -> int:
        """获取主队列和死信队列的总消息数量"""
        main_count = self.get_cached_count(thread_id)
        dlq_count = self._get_dlq_count(thread_id)
        return main_count + dlq_count

    # is_empty() 和 size() 使用基类的通用实现

    def __del__(self):
        """析构函数：停止守护线程并关闭连接池"""
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
        """获取死信队列中的所有消息（不移除）

        用于在流被取消时，获取已发送给前端但未回写数据库的完整消息内容。
        使用 basic_get + basic_nack(requeue=True) 实现"偷看"效果。

        Args:
            thread_id: 线程ID

        Returns:
            死信队列中的消息列表（已发送给前端的消息）
        """
        messages = []
        delivery_tags = []

        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                dlq_name = self._get_dlq_name(thread_id)

                # 先获取 DLQ 中的消息数量
                try:
                    dlq_info = channel.queue_declare(queue=dlq_name, durable=True, passive=True)
                    dlq_count = dlq_info.method.message_count
                except Exception:
                    return []

                if dlq_count == 0:
                    return []

                # 获取所有消息（不自动确认）
                for _ in range(dlq_count):
                    method_frame, properties, body = channel.basic_get(queue=dlq_name, auto_ack=False)
                    if not method_frame:
                        break

                    message = pickle.loads(body)
                    messages.append(message)
                    delivery_tags.append(method_frame.delivery_tag)

                # 将消息放回队列（不消费，只是"偷看"）
                for tag in delivery_tags:
                    channel.basic_nack(delivery_tag=tag, requeue=True)

                logger.debug(f"Peeked {len(messages)} messages from DLQ for thread_id={thread_id}")

        except Exception as e:
            logger.error(f"Error getting DLQ messages for thread_id={thread_id}: {e}")

        return messages
