import contextlib
import json
import os
import pickle
import queue
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from logging import getLogger
from typing import Any, ClassVar, Optional
from urllib.parse import quote

import pika
from environs import Env

from .base import BaseMessageQueueHandler, ConsumerPreemptedError, QueueTTLConfig
from .constants import EOD_CHUNK, QueueNamePrefixes
from .replay_buffer_mixin import ReplayBufferMixin

logger = getLogger(__name__)

env = Env()


class _RabbitMQConsumerMixin:
    """RabbitMQ 多进程消费者控制实现。

    利用 RabbitMQ 自身的队列来存储消费者状态，替代内存中的 threading.Lock + dict，
    使消费者管理在多进程（gunicorn -w N）部署下也能正确工作。

    核心设计：
    - 控制队列（x-max-length: 1）：存储当前活跃消费者的注册信息
    - 退出通知队列（x-message-ttl）：旧消费者退出后发送通知
    - 取消信号队列（x-max-length: 1）：存储取消信号，支持跨进程取消

    前提条件：
    - 宿主类必须提供 _with_connection() 上下文管理器来获取 RabbitMQ 连接

    队列命名约定：
    - 控制队列：aidev_agent.consumer.{thread_id}
    - 退出通知队列：aidev_agent.consumer_exit.{thread_id}
    - 取消信号队列：aidev_agent.cancel.{thread_id}
    """

    # 使用统一的队列前缀和 TTL 配置
    CONSUMER_QUEUE_PREFIX = QueueNamePrefixes.CONSUMER_CONTROL
    CONSUMER_EXIT_QUEUE_PREFIX = QueueNamePrefixes.CONSUMER_EXIT
    CANCEL_QUEUE_PREFIX = QueueNamePrefixes.CANCEL_SIGNAL
    STOPPED_QUEUE_PREFIX = QueueNamePrefixes.STOPPED_SIGNAL
    CONSUMER_QUEUE_TTL_MS = QueueTTLConfig.QUEUE_EXPIRE_MS
    CONSUMER_EXIT_MSG_TTL_MS = QueueTTLConfig.CONSUMER_EXIT_MSG_TTL_MS
    CANCEL_SIGNAL_TTL_MS = QueueTTLConfig.CANCEL_SIGNAL_TTL_MS
    STOPPED_SIGNAL_TTL_MS = QueueTTLConfig.STOPPED_SIGNAL_TTL_MS
    WAIT_POLL_INTERVAL = QueueTTLConfig.WAIT_POLL_INTERVAL

    @contextlib.contextmanager
    def _with_channel(self):
        """获取临时 RabbitMQ channel，并确保用完后关闭。"""
        with self._with_connection() as connection:
            channel = connection.channel()
            try:
                yield channel
            finally:
                if getattr(channel, "is_open", False):
                    with contextlib.suppress(Exception):
                        channel.close()

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

        with self._with_channel() as channel:
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

        logger.info(
            "[RabbitMQ] consumer acquired thread_id=%s consumer_id=%s preempted_old=%s",
            thread_id,
            consumer_id[:8],
            old_consumer_id[:8] if old_consumer_id else None,
        )
        return consumer_id

    def wait_for_previous_consumer(self, thread_id: str, timeout: float = 3.0) -> bool:
        """等待旧消费者完全退出（包括兼容模式的消息恢复）

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
                with self._with_channel() as channel:
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
        with self._with_channel() as channel:
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
        如果自己已被抢占，保留 replay 缓存并向退出通知队列发送信号。

        Args:
            thread_id: 线程ID
            consumer_id: 消费者 ID
        """

        is_preempted = False
        active_consumer_id = None
        release_outcome = "empty_control_queue"

        with self._with_channel() as channel:
            consumer_queue = self._get_consumer_queue_name(thread_id)

            try:
                channel.queue_declare(queue=consumer_queue, passive=True)
            except Exception:
                logger.info(
                    "[RabbitMQ] consumer released thread_id=%s consumer_id=%s reason=missing_queue",
                    thread_id,
                    consumer_id[:8],
                )
                return

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
                    release_outcome = "normal"
                else:
                    # 被抢占：放回控制队列中的消息
                    channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
                    is_preempted = True
                    release_outcome = "preempted"

        if is_preempted:
            logger.info(
                "Preempted replay consumer %s preserved cached messages for thread_id=%s",
                consumer_id[:8],
                thread_id,
            )
            self._send_exit_signal(thread_id, consumer_id)

        logger.info(
            "[RabbitMQ] consumer released thread_id=%s consumer_id=%s reason=%s",
            thread_id,
            consumer_id[:8],
            release_outcome,
        )

    def has_active_consumer(self, thread_id: str) -> bool:
        """检查指定 thread_id 是否仍有活跃消费者。"""
        try:
            with self._with_channel() as channel:
                consumer_queue = self._get_consumer_queue_name(thread_id)

                try:
                    channel.queue_declare(queue=consumer_queue, passive=True)
                except Exception:
                    return False

                method_frame, _, body = channel.basic_get(queue=consumer_queue, auto_ack=False)
                if not method_frame:
                    return False

                channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)

                try:
                    data = json.loads(body)
                except (json.JSONDecodeError, KeyError):
                    return False

                return bool(data.get("consumer_id"))
        except Exception as e:
            logger.warning(f"Error checking active consumer for thread_id={thread_id}: {e}")
            return False

    def _send_exit_signal(self, thread_id: str, consumer_id: str) -> None:
        """向退出通知队列发送信号"""
        try:
            with self._with_channel() as channel:
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

    def _declare_signal_queue(
        self,
        channel: Any,
        queue_name: str,
        message_ttl_ms: int,
    ) -> None:
        """声明信号队列（内部方法）

        用于取消信号、消费者退出通知等场景，统一队列声明逻辑。

        Args:
            channel: RabbitMQ channel
            queue_name: 队列名
            message_ttl_ms: 消息 TTL（毫秒）
        """
        channel.queue_declare(
            queue=queue_name,
            durable=True,
            arguments={
                "x-max-length": 1,
                "x-overflow": "drop-head",
                "x-message-ttl": message_ttl_ms,
                "x-expires": self.CONSUMER_QUEUE_TTL_MS,
            },
        )

    def _publish_signal(
        self,
        channel: Any,
        queue_name: str,
        payload: dict,
    ) -> None:
        """发布信号消息（内部方法）

        Args:
            channel: RabbitMQ channel
            queue_name: 队列名
            payload: 消息内容（会被 JSON 序列化）
        """
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=json.dumps(payload).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def set_cancel_signal(self, thread_id: str, run_id: str | None = None) -> bool:
        """设置跨进程取消信号（通过 RabbitMQ 队列）

        可以从任意进程调用，生产者/消费者会通过 check_cancel_signal() 检测到取消。

        Args:
            thread_id: 线程ID / session_code
            run_id: 本轮运行 ID；为空时兼容旧版 session 级取消

        Returns:
            True 表示成功设置取消信号
        """
        cancel_queue = self._get_cancel_queue_name(thread_id)
        payload = {"cancelled": True, "run_id": run_id, "ts": time.time()}
        try:
            try:
                # 滚动发布期间可能仍有旧 worker 创建的同名队列；先复用，避免参数不一致关闭 channel。
                with self._with_channel() as channel:
                    channel.queue_declare(queue=cancel_queue, passive=True)
                    self._publish_signal(channel, cancel_queue, payload)
            except pika.exceptions.ChannelClosedByBroker as exc:
                if exc.reply_code != 404:
                    raise
                with self._with_channel() as channel:
                    self._declare_signal_queue(channel, cancel_queue, self.CANCEL_SIGNAL_TTL_MS)
                    self._publish_signal(channel, cancel_queue, payload)
            logger.info("Cancel signal set for thread_id=%s run_id=%s", thread_id, run_id)
            return True
        except Exception as e:
            logger.error(f"Failed to set cancel signal for thread_id={thread_id}: {e}")
            return False

    def check_cancel_signal(self, thread_id: str, run_id: str | None = None) -> bool:
        """检查是否存在取消信号（peek 模式，不消费消息）

        用于生产者/消费者定期检查是否需要停止。

        Args:
            thread_id: 线程ID / session_code
            run_id: 本轮运行 ID；非空时只匹配同一轮或旧版无作用域信号

        Returns:
            True 表示存在取消信号，应该停止
        """
        try:
            with self._with_channel() as channel:
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
                    # 兼容滚动发布中旧 request_cancel() 写入的 session 级信号。
                    if body == b"1":
                        return True
                    data = json.loads(body)
                    if not isinstance(data, dict):
                        return False
                    signal_run_id = data.get("run_id")
                    if run_id and signal_run_id and signal_run_id != run_id:
                        return False
                    return bool(data.get("cancelled", False))
                except (json.JSONDecodeError, KeyError):
                    return False
        except Exception as e:
            logger.warning(f"Error checking cancel signal for thread_id={thread_id}: {e}")
            return False

    def clear_cancel_signal(self, thread_id: str, run_id: str | None = None) -> None:
        """清除取消信号（在流结束后调用）

        Args:
            thread_id: 线程ID / session_code
            run_id: 本轮运行 ID；非空时只清理同一轮或旧版无作用域信号
        """
        try:
            with self._with_channel() as channel:
                cancel_queue = self._get_cancel_queue_name(thread_id)

                # 尝试清空取消信号队列
                try:
                    channel.queue_declare(queue=cancel_queue, passive=True)
                    if run_id is None:
                        channel.queue_purge(queue=cancel_queue)
                        return

                    method_frame, _, body = channel.basic_get(queue=cancel_queue, auto_ack=False)
                    if not method_frame:
                        return
                    try:
                        signal_run_id = json.loads(body).get("run_id")
                    except (json.JSONDecodeError, AttributeError):
                        signal_run_id = None
                    if signal_run_id in (None, run_id):
                        channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                    else:
                        channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
                except Exception:
                    # 队列不存在，忽略
                    pass
        except Exception as e:
            logger.warning(f"Error clearing cancel signal for thread_id={thread_id}: {e}")

    # 消费者取消完成通知队列前缀（与上面的类常量保持一致的风格）
    CANCELLED_QUEUE_PREFIX = "aidev_agent.cancelled."
    CANCELLED_SIGNAL_TTL_MS = QueueTTLConfig.CANCELLED_SIGNAL_TTL_MS

    def _get_cancelled_queue_name(self, thread_id: str) -> str:
        """获取"消费者已因取消退出"通知队列名"""
        return f"{self.CANCELLED_QUEUE_PREFIX}{thread_id}"

    def notify_consumer_cancelled(self, thread_id: str, run_id: str | None = None) -> bool:
        """通知 stop_session 消费者已因取消信号退出（缓存内容可以读取了）

        消费者在检测到取消信号并退出时调用此方法。
        stop_session 通过 wait_for_consumer_cancelled() 等待这个信号后再读取缓存内容。

        Args:
            thread_id: 线程ID / session_code
            run_id: 已完成取消的运行 ID

        Returns:
            True 表示成功发送通知
        """
        try:
            with self._with_channel() as channel:
                cancelled_queue = self._get_cancelled_queue_name(thread_id)

                # 声明通知队列
                self._declare_signal_queue(channel, cancelled_queue, self.CANCELLED_SIGNAL_TTL_MS)

                # 发送通知
                self._publish_signal(
                    channel,
                    cancelled_queue,
                    {"cancelled": True, "run_id": run_id, "ts": time.time(), "pid": os.getpid()},
                )
                logger.info("Consumer cancelled notification sent for thread_id=%s run_id=%s", thread_id, run_id)
                return True
        except Exception as e:
            logger.error(f"Failed to send cancelled notification for thread_id={thread_id}: {e}")
            return False

    def wait_for_consumer_cancelled(
        self,
        thread_id: str,
        timeout: float = 3.0,
        run_id: str | None = None,
    ) -> bool:
        """等待消费者因取消信号退出

        stop_session 调用此方法等待消费者退出后，再读取缓存消息。

        Args:
            thread_id: 线程ID / session_code
            timeout: 最大等待时间（秒）
            run_id: 本轮运行 ID；非空时忽略其他轮次的完成通知

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
                with self._with_channel() as channel:
                    cancelled_queue = self._get_cancelled_queue_name(thread_id)

                    # 先被动声明检查队列是否存在
                    try:
                        channel.queue_declare(queue=cancelled_queue, passive=True)
                    except Exception:
                        # 队列不存在，等待
                        time.sleep(self.WAIT_POLL_INTERVAL)
                        continue

                    # 匹配本轮通知后确认；其他 Run 的通知放回，避免并发 Stop 互相吞消息。
                    method_frame, _, body = channel.basic_get(queue=cancelled_queue, auto_ack=False)
                    if method_frame:
                        try:
                            signal_run_id = json.loads(body).get("run_id")
                        except (json.JSONDecodeError, AttributeError):
                            signal_run_id = None
                        if not run_id or signal_run_id in (None, run_id):
                            channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                            logger.info(
                                "Consumer cancelled confirmed for thread_id=%s run_id=%s",
                                thread_id,
                                run_id,
                            )
                            return True
                        channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
                        logger.info(
                            "Ignored stale consumer cancelled notification thread_id=%s expected_run_id=%s "
                            "actual_run_id=%s",
                            thread_id,
                            run_id,
                            signal_run_id,
                        )
            except Exception as e:
                logger.warning(f"Error polling cancelled queue for thread_id={thread_id}: {e}")

            time.sleep(self.WAIT_POLL_INTERVAL)

    def clear_cancelled_signal(self, thread_id: str, run_id: str | None = None) -> None:
        """清除消费者取消完成通知（在获取缓存内容后调用）

        Args:
            thread_id: 线程ID / session_code
            run_id: 本轮运行 ID；非空时只清理同一轮或旧版无作用域通知
        """
        try:
            with self._with_channel() as channel:
                cancelled_queue = self._get_cancelled_queue_name(thread_id)

                try:
                    channel.queue_declare(queue=cancelled_queue, passive=True)
                    if run_id is None:
                        channel.queue_purge(queue=cancelled_queue)
                        return

                    method_frame, _, body = channel.basic_get(queue=cancelled_queue, auto_ack=False)
                    if not method_frame:
                        return
                    try:
                        signal_run_id = json.loads(body).get("run_id")
                    except (json.JSONDecodeError, AttributeError):
                        signal_run_id = None
                    if signal_run_id in (None, run_id):
                        channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                    else:
                        channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error clearing cancelled signal for thread_id={thread_id}: {e}")

    # ==================== 跨进程停止状态管理 ====================

    def _get_stopped_queue_name(self, thread_id: str) -> str:
        """获取停止状态队列名"""
        return f"{self.STOPPED_QUEUE_PREFIX}{thread_id}"

    def mark_stopped(self, thread_id: str) -> None:
        """标记 session 已被用户主动停止（跨进程实现）

        通过 RabbitMQ 队列存储停止状态，任意进程都能读取。

        Args:
            thread_id: 线程ID / session_code
        """
        try:
            with self._with_channel() as channel:
                stopped_queue = self._get_stopped_queue_name(thread_id)

                # 声明停止状态队列
                self._declare_signal_queue(channel, stopped_queue, self.STOPPED_SIGNAL_TTL_MS)

                # 发送停止信号
                self._publish_signal(channel, stopped_queue, {"stopped": True, "ts": time.time()})
                logger.info(f"Stopped signal set for thread_id={thread_id}")
        except Exception as e:
            logger.error(f"Failed to set stopped signal for thread_id={thread_id}: {e}")

    def is_stopped(self, thread_id: str) -> bool:
        """检查 session 是否已被用户主动停止（跨进程实现）

        通过 peek RabbitMQ 队列检查停止状态（不消费消息）。

        Args:
            thread_id: 线程ID / session_code

        Returns:
            True 表示已停止
        """
        try:
            with self._with_channel() as channel:
                stopped_queue = self._get_stopped_queue_name(thread_id)

                # 先被动声明检查队列是否存在
                try:
                    channel.queue_declare(queue=stopped_queue, passive=True)
                except Exception as e:
                    logger.warning(f"Error declaring stopped queue for thread_id={thread_id}: {e}")
                    return False

                # peek：取出后放回
                method_frame, _, body = channel.basic_get(queue=stopped_queue, auto_ack=False)
                if not method_frame:
                    return False

                # 放回消息
                channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)

                try:
                    data = json.loads(body)
                    return data.get("stopped", False)
                except (json.JSONDecodeError, KeyError):
                    return False
        except Exception as e:
            logger.warning(f"Error checking stopped signal for thread_id={thread_id}: {e}")
            return False

    def clear_stopped(self, thread_id: str) -> None:
        """清除停止标记（跨进程实现）

        Args:
            thread_id: 线程ID / session_code
        """
        try:
            with self._with_channel() as channel:
                stopped_queue = self._get_stopped_queue_name(thread_id)

                try:
                    channel.queue_declare(queue=stopped_queue, passive=True)
                    channel.queue_purge(queue=stopped_queue)
                    logger.debug(f"Cleared stopped signal for thread_id={thread_id}")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Error clearing stopped signal for thread_id={thread_id}: {e}")

    def _get_signal_queue_names(self, thread_id: str) -> list[str]:
        """获取 _RabbitMQConsumerMixin 管理的所有信号队列名列表"""
        return [
            self._get_consumer_queue_name(thread_id),
            self._get_consumer_exit_queue_name(thread_id),
            self._get_cancelled_queue_name(thread_id),
            self._get_stopped_queue_name(thread_id),
        ]

    def _delete_signal_queues(self, connection: Any, thread_id: str) -> None:
        """
        删除 _RabbitMQConsumerMixin 管理的所有信号队列
        使用单个 channel 批量删除所有信号队列。
        AMQP 0-9-1 规范中 queue.delete 对不存在的队列不会抛出 channel error，
        因此无需为每个队列创建独立的 channel，也无需先 passive declare 检查。
        """
        channel = connection.channel()
        try:
            for queue_name in self._get_signal_queue_names(thread_id):
                try:
                    channel.queue_delete(queue=queue_name)
                    logger.debug(f"Deleted signal queue {queue_name}")
                except Exception as e:
                    # 队列不存在或删除失败，忽略
                    logger.exception(f"Failed to delete signal queue {queue_name}: {e}")
        finally:
            if channel and channel.is_open:
                with contextlib.suppress(Exception):
                    channel.close()


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
        max_retries = 2  # 最多重试 2 次（共 3 次尝试）
        conn = None
        for attempt in range(max_retries + 1):
            try:
                conn = self.get_connection()
            except (
                pika.exceptions.StreamLostError,
                pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError,
                ConnectionResetError,
                BrokenPipeError,
                OSError,
            ) as e:
                if attempt >= max_retries:
                    logger.error(f"RabbitMQ connection error after {max_retries + 1} attempts: {e}")
                    raise
                logger.warning(f"RabbitMQ connection error (attempt {attempt + 1}/{max_retries + 1}): {e}, retrying...")
                continue
            break

        try:
            yield conn
        except Exception:
            # contextmanager 在 yield 后不能重新进入重试循环，否则会二次 yield 并触发
            # RuntimeError("generator didn't stop after throw()")。连接内操作由调用方整体重试。
            self._close_connection(conn)
            with self._created_lock:
                self._created_count = max(0, self._created_count - 1)
            conn = None
            raise
        finally:
            if conn is not None:
                self.release_connection(conn)

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


class RabbitMQMessageHandler(_RabbitMQConsumerMixin, ReplayBufferMixin, BaseMessageQueueHandler):
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

    # Classic Queue 有新增消息时需要扫描并 requeue 已提交历史，长队列单次 replay
    # 可能超过通用 15 秒窗口，因此仅该 handler 放宽到 60 秒。
    CONSUMER_HEARTBEAT_TIMEOUT: ClassVar[float] = 60.0

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

    def has_active_producer(self, thread_id: str) -> bool:
        """通过被动声明 producer lock queue 判断跨进程生产者是否仍存活。"""
        lock_queue = self._get_producer_lock_queue_name(thread_id)
        with self._producer_lock_guard:
            local_connection = self._producer_lock_connections.get(thread_id)
            if local_connection is not None and getattr(local_connection, "is_open", False):
                return True

        try:
            with self._with_channel() as channel:
                channel.queue_declare(queue=lock_queue, passive=True)
            return True
        except pika.exceptions.ChannelClosedByBroker as e:
            if e.reply_code == 404:
                return False
            # producer lock queue 为 exclusive；其他连接 passive declare 时 broker
            # 以 RESOURCE_LOCKED 响应，这恰好说明生产者仍持有该队列。
            if e.reply_code == 405:
                return True
            raise

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
                # 追加 RabbitMQ 消费者控制使用的信号队列
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
