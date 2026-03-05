import json
import os
import time
import uuid
from logging import getLogger
from typing import Any

from .base import ConsumerPreemptedError

logger = getLogger(__name__)


class MultiProcessMixin:
    """多进程消费者抢占管理 Mixin

    利用 RabbitMQ 自身的队列来存储消费者状态，替代内存中的 threading.Lock + dict，
    使消费者管理在多进程（gunicorn -w N）部署下也能正确工作。

    适用于：多进程部署（如 gunicorn -w 4）

    核心设计：
    - 控制队列（x-max-length: 1）：存储当前活跃消费者的注册信息
    - 退出通知队列（x-message-ttl）：旧消费者退出后发送通知
    - 取消信号队列（x-max-length: 1）：存储取消信号，支持跨进程取消

    前提条件：
    - 宿主类必须提供 _with_connection() 上下文管理器来获取 RabbitMQ 连接
    - 宿主类必须提供 restore_messages(thread_id) 方法

    使用方式：
        class MyHandler(MultiProcessMixin, BaseMessageQueueHandler):
            ...

    队列命名约定：
    - 控制队列：aidev_agent.consumer.{thread_id}
    - 退出通知队列：aidev_agent.consumer_exit.{thread_id}
    - 取消信号队列：aidev_agent.cancel.{thread_id}
    """

    CONSUMER_QUEUE_PREFIX = "aidev_agent.consumer."
    CONSUMER_EXIT_QUEUE_PREFIX = "aidev_agent.consumer_exit."
    CANCEL_QUEUE_PREFIX = "aidev_agent.cancel."
    # 控制队列和退出通知队列的 TTL（毫秒），1小时后自动删除
    CONSUMER_QUEUE_TTL_MS = 3600 * 1000
    # 退出通知消息的 TTL（毫秒），5秒后自动过期
    CONSUMER_EXIT_MSG_TTL_MS = 5000
    # 取消信号的 TTL（毫秒），30秒后自动过期（防止残留）
    CANCEL_SIGNAL_TTL_MS = 30000
    # wait_for_previous_consumer 的轮询间隔（秒）
    WAIT_POLL_INTERVAL = 0.2

    def _get_consumer_queue_name(self, thread_id: str) -> str:
        """获取控制队列名"""
        return f"{self.CONSUMER_QUEUE_PREFIX}{thread_id}"

    def _get_consumer_exit_queue_name(self, thread_id: str) -> str:
        """获取退出通知队列名"""
        return f"{self.CONSUMER_EXIT_QUEUE_PREFIX}{thread_id}"

    def _get_cancel_queue_name(self, thread_id: str) -> str:
        """获取取消信号队列名"""
        return f"{self.CANCEL_QUEUE_PREFIX}{thread_id}"

    def _ensure_consumer_queues(self, channel: Any, thread_id: str) -> tuple[str, str]:
        """确保控制队列和退出通知队列存在

        Args:
            channel: RabbitMQ channel
            thread_id: 线程ID

        Returns:
            (控制队列名, 退出通知队列名)
        """
        consumer_queue = self._get_consumer_queue_name(thread_id)
        exit_queue = self._get_consumer_exit_queue_name(thread_id)

        # 控制队列：x-max-length=1 确保只保留最新的消费者注册信息
        # x-overflow=drop-head：当队列满时丢弃最旧的消息，保留最新的
        channel.queue_declare(
            queue=consumer_queue,
            durable=True,
            arguments={
                "x-max-length": 1,
                "x-overflow": "drop-head",
                "x-expires": self.CONSUMER_QUEUE_TTL_MS,
            },
        )

        # 退出通知队列：消息 5 秒后自动过期，最多保留 1 条
        channel.queue_declare(
            queue=exit_queue,
            durable=True,
            arguments={
                "x-message-ttl": self.CONSUMER_EXIT_MSG_TTL_MS,
                "x-max-length": 1,
                "x-expires": self.CONSUMER_QUEUE_TTL_MS,
            },
        )

        return consumer_queue, exit_queue

    def acquire_consumer(self, thread_id: str) -> str:
        """注册新消费者，返回消费者 ID

        通过 purge + publish 到控制队列来实现"最后写入者胜出"的语义。
        无论哪个进程执行，最后写入的 consumer_id 就是最新的活跃消费者。

        Args:
            thread_id: 线程ID

        Returns:
            新消费者的唯一 ID
        """
        consumer_id = uuid.uuid4().hex

        import pika

        with self._with_connection() as connection:
            channel = connection.channel()
            consumer_queue, exit_queue = self._ensure_consumer_queues(channel, thread_id)

            # 先读取旧消费者信息（用于日志）
            old_consumer_id = None
            method_frame, _, body = channel.basic_get(queue=consumer_queue, auto_ack=True)
            if method_frame:
                try:
                    old_data = json.loads(body)
                    old_consumer_id = old_data.get("consumer_id")
                except (json.JSONDecodeError, KeyError):
                    pass

            # 清空退出通知队列（为新的等待周期做准备）
            channel.queue_purge(queue=exit_queue)

            # 写入新消费者注册信息
            payload = json.dumps(
                {
                    "consumer_id": consumer_id,
                    "ts": time.time(),
                }
            )
            channel.basic_publish(
                exchange="",
                routing_key=consumer_queue,
                body=payload.encode(),
                properties=pika.BasicProperties(delivery_mode=2),
            )

            if old_consumer_id:
                logger.info(
                    f"Consumer preempted for thread_id={thread_id}: old={old_consumer_id[:8]}, new={consumer_id[:8]}"
                )

        return consumer_id

    def wait_for_previous_consumer(self, thread_id: str, timeout: float = 3.0) -> bool:
        """等待旧消费者完全退出（包括 DLQ restore）

        通过轮询退出通知队列来等待旧消费者发送退出信号。

        Args:
            thread_id: 线程ID
            timeout: 最大等待时间（秒）

        Returns:
            True 表示旧消费者已退出，False 表示超时
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for previous consumer to exit, thread_id={thread_id}")
                return False

            try:
                with self._with_connection() as connection:
                    channel = connection.channel()
                    exit_queue = self._get_consumer_exit_queue_name(thread_id)

                    # 尝试先被动声明检查队列是否存在
                    try:
                        channel.queue_declare(queue=exit_queue, passive=True)
                    except Exception:
                        # 队列不存在，说明没有旧消费者需要等待
                        return True

                    method_frame, _, body = channel.basic_get(queue=exit_queue, auto_ack=True)
                    if method_frame:
                        # 收到退出信号
                        logger.info(f"Previous consumer exited for thread_id={thread_id}")
                        return True
            except Exception as e:
                logger.warning(f"Error polling exit queue for thread_id={thread_id}: {e}")

            # 短暂等待后重试
            time.sleep(self.WAIT_POLL_INTERVAL)

    def check_consumer(self, thread_id: str, consumer_id: str) -> None:
        """检查当前消费者是否仍是活跃消费者

        通过 peek 控制队列（basic_get + reject requeue）来检查。

        Args:
            thread_id: 线程ID
            consumer_id: 消费者 ID

        Raises:
            ConsumerPreemptedError: 当前消费者已被新消费者抢占
        """
        with self._with_connection() as connection:
            channel = connection.channel()
            consumer_queue = self._get_consumer_queue_name(thread_id)

            # 尝试先被动声明检查队列是否存在
            try:
                channel.queue_declare(queue=consumer_queue, passive=True)
            except Exception:
                # 队列不存在，无法判断，认为通过
                return

            # peek：取出后放回
            method_frame, _, body = channel.basic_get(queue=consumer_queue, auto_ack=False)
            if not method_frame:
                # 控制队列为空，无法判断，认为通过
                return

            try:
                data = json.loads(body)
                active_consumer_id = data.get("consumer_id")
            except (json.JSONDecodeError, KeyError):
                # 数据损坏，放回并通过
                channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
                return

            # 放回消息
            channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)

            if active_consumer_id and active_consumer_id != consumer_id:
                raise ConsumerPreemptedError(
                    f"Consumer {consumer_id[:8]} preempted by {active_consumer_id[:8]} for thread_id={thread_id}"
                )

    def release_consumer(self, thread_id: str, consumer_id: str) -> None:
        """释放消费者

        如果自己仍是当前活跃消费者（正常结束），清空控制队列。
        如果自己已被抢占，恢复 DLQ 消息并向退出通知队列发送信号。

        Args:
            thread_id: 线程ID
            consumer_id: 消费者 ID
        """

        is_preempted = False
        active_consumer_id = None

        with self._with_connection() as connection:
            channel = connection.channel()
            consumer_queue, exit_queue = self._ensure_consumer_queues(channel, thread_id)

            # peek 控制队列
            method_frame, _, body = channel.basic_get(queue=consumer_queue, auto_ack=False)
            if method_frame:
                try:
                    data = json.loads(body)
                    active_consumer_id = data.get("consumer_id")
                except (json.JSONDecodeError, KeyError):
                    active_consumer_id = None

                if active_consumer_id == consumer_id:
                    # 正常结束：消费掉控制队列中的注册信息（ack 删除）
                    channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                    logger.debug(f"Consumer {consumer_id[:8]} released normally for thread_id={thread_id}")
                else:
                    # 被抢占：放回控制队列中的消息
                    channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
                    is_preempted = True

        if is_preempted:
            # 被抢占：将 DLQ 中自己消费过的消息恢复到主队列，然后发送退出信号
            try:
                restored = self.restore_messages(thread_id)
                logger.info(
                    f"Preempted consumer {consumer_id[:8]} restored {restored} DLQ messages for thread_id={thread_id}"
                )
            except Exception as e:
                logger.error(f"Failed to restore DLQ messages for consumer {consumer_id[:8]}: {e}")
            finally:
                # 无论恢复消息是否成功，都要向退出通知队列发送信号，避免新消费者无限等待
                self._send_exit_signal(thread_id, consumer_id)

    def _send_exit_signal(self, thread_id: str, consumer_id: str) -> None:
        """向退出通知队列发送信号"""
        import pika

        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                exit_queue = self._get_consumer_exit_queue_name(thread_id)

                payload = json.dumps(
                    {
                        "old_consumer_id": consumer_id,
                        "ts": time.time(),
                    }
                )
                channel.basic_publish(
                    exchange="",
                    routing_key=exit_queue,
                    body=payload.encode(),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                logger.info(f"Sent exit signal for preempted consumer {consumer_id[:8]}, thread_id={thread_id}")
        except Exception as e:
            logger.error(f"Failed to send exit signal for consumer {consumer_id[:8]}: {e}")

    # ==================== 跨进程取消信号管理 ====================

    def set_cancel_signal(self, thread_id: str) -> bool:
        """设置跨进程取消信号（通过 RabbitMQ 队列）

        可以从任意进程调用，生产者/消费者会通过 check_cancel_signal() 检测到取消。

        Args:
            thread_id: 线程ID / session_code

        Returns:
            True 表示成功设置取消信号
        """
        import pika

        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                cancel_queue = self._get_cancel_queue_name(thread_id)

                # 声明取消信号队列（x-max-length=1 只保留最新信号）
                channel.queue_declare(
                    queue=cancel_queue,
                    durable=True,
                    arguments={
                        "x-max-length": 1,
                        "x-overflow": "drop-head",
                        "x-message-ttl": self.CANCEL_SIGNAL_TTL_MS,
                        "x-expires": self.CONSUMER_QUEUE_TTL_MS,
                    },
                )

                # 发送取消信号
                payload = json.dumps(
                    {
                        "cancelled": True,
                        "ts": time.time(),
                    }
                )
                channel.basic_publish(
                    exchange="",
                    routing_key=cancel_queue,
                    body=payload.encode(),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                logger.info(f"Cancel signal set for thread_id={thread_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to set cancel signal for thread_id={thread_id}: {e}")
            return False

    def check_cancel_signal(self, thread_id: str) -> bool:
        """检查是否存在取消信号（peek 模式，不消费消息）

        用于生产者/消费者定期检查是否需要停止。

        Args:
            thread_id: 线程ID / session_code

        Returns:
            True 表示存在取消信号，应该停止
        """
        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                cancel_queue = self._get_cancel_queue_name(thread_id)

                # 先被动声明检查队列是否存在
                try:
                    channel.queue_declare(queue=cancel_queue, passive=True)
                except Exception:
                    # 队列不存在，没有取消信号
                    return False

                # peek：取出后放回
                method_frame, _, body = channel.basic_get(queue=cancel_queue, auto_ack=False)
                if not method_frame:
                    return False

                # 放回消息（让后续检查也能看到）
                channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)

                try:
                    data = json.loads(body)
                    cancelled = data.get("cancelled", False)
                    return cancelled
                except (json.JSONDecodeError, KeyError):
                    return False
        except Exception as e:
            logger.warning(f"Error checking cancel signal for thread_id={thread_id}: {e}")
            return False

    def clear_cancel_signal(self, thread_id: str) -> None:
        """清除取消信号（在流结束后调用）

        Args:
            thread_id: 线程ID / session_code
        """
        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                cancel_queue = self._get_cancel_queue_name(thread_id)

                # 尝试清空取消信号队列
                try:
                    channel.queue_declare(queue=cancel_queue, passive=True)
                    channel.queue_purge(queue=cancel_queue)
                except Exception:
                    # 队列不存在，忽略
                    pass
        except Exception as e:
            logger.warning(f"Error clearing cancel signal for thread_id={thread_id}: {e}")

    CANCELLED_QUEUE_PREFIX = "aidev_agent.cancelled."
    # 取消完成信号的 TTL（毫秒），30秒后自动过期
    CANCELLED_SIGNAL_TTL_MS = 30000

    def _get_cancelled_queue_name(self, thread_id: str) -> str:
        """获取"消费者已因取消退出"通知队列名"""
        return f"{self.CANCELLED_QUEUE_PREFIX}{thread_id}"

    def notify_consumer_cancelled(self, thread_id: str) -> bool:
        """通知 stop_session 消费者已因取消信号退出（DLQ 可以读取了）

        消费者在检测到取消信号并退出时调用此方法。
        stop_session 通过 wait_for_consumer_cancelled() 等待这个信号后再读取 DLQ。

        Args:
            thread_id: 线程ID / session_code

        Returns:
            True 表示成功发送通知
        """
        import pika

        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                cancelled_queue = self._get_cancelled_queue_name(thread_id)

                # 声明通知队列
                channel.queue_declare(
                    queue=cancelled_queue,
                    durable=True,
                    arguments={
                        "x-max-length": 1,
                        "x-overflow": "drop-head",
                        "x-message-ttl": self.CANCELLED_SIGNAL_TTL_MS,
                        "x-expires": self.CONSUMER_QUEUE_TTL_MS,
                    },
                )

                # 发送通知
                payload = json.dumps(
                    {
                        "cancelled": True,
                        "ts": time.time(),
                        "pid": os.getpid(),
                    }
                )
                channel.basic_publish(
                    exchange="",
                    routing_key=cancelled_queue,
                    body=payload.encode(),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                logger.info(f"Consumer cancelled notification sent for thread_id={thread_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to send cancelled notification for thread_id={thread_id}: {e}")
            return False

    def wait_for_consumer_cancelled(self, thread_id: str, timeout: float = 3.0) -> bool:
        """等待消费者因取消信号退出

        stop_session 调用此方法等待消费者退出后，再从 DLQ 读取消息。

        Args:
            thread_id: 线程ID / session_code
            timeout: 最大等待时间（秒）

        Returns:
            True 表示消费者已退出，False 表示超时
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for consumer to exit after cancel, thread_id={thread_id}")
                return False

            try:
                with self._with_connection() as connection:
                    channel = connection.channel()
                    cancelled_queue = self._get_cancelled_queue_name(thread_id)

                    # 先被动声明检查队列是否存在
                    try:
                        channel.queue_declare(queue=cancelled_queue, passive=True)
                    except Exception:
                        # 队列不存在，等待
                        time.sleep(self.WAIT_POLL_INTERVAL)
                        continue

                    # 尝试获取通知（消费掉，因为只需要等待一次）
                    method_frame, _, body = channel.basic_get(queue=cancelled_queue, auto_ack=True)
                    if method_frame:
                        logger.info(f"Consumer cancelled confirmed for thread_id={thread_id}")
                        return True
            except Exception as e:
                logger.warning(f"Error polling cancelled queue for thread_id={thread_id}: {e}")

            time.sleep(self.WAIT_POLL_INTERVAL)

    def clear_cancelled_signal(self, thread_id: str) -> None:
        """清除消费者取消完成通知（在获取 DLQ 后调用）

        Args:
            thread_id: 线程ID / session_code
        """
        try:
            with self._with_connection() as connection:
                channel = connection.channel()
                cancelled_queue = self._get_cancelled_queue_name(thread_id)

                try:
                    channel.queue_declare(queue=cancelled_queue, passive=True)
                    channel.queue_purge(queue=cancelled_queue)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error clearing cancelled signal for thread_id={thread_id}: {e}")
