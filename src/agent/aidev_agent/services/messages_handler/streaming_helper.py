import threading
import time
import uuid
from logging import getLogger
from typing import Any, Callable, Generator

from .base import (
    CANCELLED_CHUNK,
    EOD_CHUNK,
    HEARTBEAT_CHUNK,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    BaseMessageQueueHandler,
    ConsumerPreemptedError,
    StreamCancelledError,
)
from .factory import message_handler_factory

logger = getLogger(__name__)


class GeneratorStreamingHelper:
    """生成器流式处理辅助类

    使用死信队列机制支持断点续传的流式处理：
    - 通过 has_pending_messages() 判断是否需要创建新的生产者
    - 消费者读取消息后，消息从主队列移动到死信队列
    - 消费者断开后重连时，先调用 restore_messages() 恢复消息，再继续消费
    - 读到 EOD_CHUNK 时调用 mark_completed() 清理所有队列

    心跳机制：
    - 生产者在数据产生间隔较长时，定期发送心跳消息
    - 消费者检测心跳超时，如果超过 HEARTBEAT_TIMEOUT 未收到任何消息，则认为生产者异常

    取消机制（支持多进程）：
    - 进程内取消：使用 threading.Event，同进程内的生产者/消费者可立即感知
    - 跨进程取消：使用 RabbitMQ 队列存储取消信号，任意进程都可设置/检测

    工作流程：
    1. 客户端首次请求时，队列为空，启动生产者线程生产数据
    2. 消费者从主队列获取消息，消息被移动到死信队列
    3. 如果客户端断开连接，生产者继续运行直到完成
    4. 客户端重连时，检查队列中是否有数据：
       - 如果有数据，先调用 restore_messages() 恢复消息，再消费
       - 如果没有数据，启动新的生产者
    5. 读到 EOD_CHUNK 时，调用 mark_completed() 清理队列
    """

    # 进程内取消标志：thread_id -> threading.Event
    # 用于同进程内的快速通知（如生产者线程和消费者循环在同一进程）
    _cancel_events: dict[str, "threading.Event"] = {}
    _cancel_lock = threading.Lock()

    def __init__(self, message_handler: BaseMessageQueueHandler | None = None, thread_id: str | None = None) -> None:
        self.message_handler = message_handler if message_handler else message_handler_factory.get()
        self.thread_id = thread_id or uuid.uuid4().hex

    @classmethod
    def cancel(cls, thread_id: str, message_handler: BaseMessageQueueHandler | None = None) -> bool:
        """取消指定 thread_id 的流式生产（支持多进程）

        同时设置：
        1. 进程内取消事件（同进程内的生产者/消费者立即感知）
        2. 跨进程取消信号（通过 RabbitMQ，任意进程的生产者/消费者都能检测到）

        Args:
            thread_id: 要取消的线程 ID / session_code
            message_handler: 消息处理器，用于设置跨进程取消信号。如果为 None，
                           则仅设置进程内取消事件（向后兼容）

        Returns:
            True 如果成功设置取消信号（进程内或跨进程任一成功即返回 True）
        """
        result = False

        # 1. 设置进程内取消事件（快速路径，同进程内立即生效）
        with cls._cancel_lock:
            event = cls._cancel_events.get(thread_id)
            if event:
                event.set()
                result = True

        # 2. 设置跨进程取消信号（通过 RabbitMQ，支持多进程部署）
        if message_handler is None:
            message_handler = message_handler_factory.get()

        # 检查 message_handler 是否支持跨进程取消（MultiProcessMixin）
        if hasattr(message_handler, "set_cancel_signal"):
            try:
                cross_process_result = message_handler.set_cancel_signal(thread_id)
                if cross_process_result:
                    result = True
            except Exception as e:
                logger.exception(f"Error setting cross-process cancel signal: {e}")

        return result

    @classmethod
    def has_output(cls, thread_id: str, message_handler: BaseMessageQueueHandler | None = None) -> bool:
        """检查指定 thread_id 的流是否已有输出

        通过检查消息队列中是否有消息来判断：
        - 主队列有消息：说明生产者已产生输出
        - 死信队列有消息：说明消费者已读取过输出

        Args:
            thread_id: 线程 ID / session_code
            message_handler: 消息处理器。如果为 None，使用默认的消息处理器

        Returns:
            True 表示流已有输出，False 表示流还没有任何输出
        """
        if message_handler is None:
            message_handler = message_handler_factory.get()

        try:
            return message_handler.has_pending_messages(thread_id)
        except Exception as e:
            logger.warning(f"Error checking has_output for thread_id={thread_id}: {e}")
            # 出错时保守返回 True，避免误补消息
            return True

    def _register_cancel_event(self) -> "threading.Event":
        """注册取消事件"""
        event = threading.Event()
        with self._cancel_lock:
            self._cancel_events[self.thread_id] = event
        return event

    def _unregister_cancel_event(self) -> None:
        """取消注册取消事件"""
        with self._cancel_lock:
            self._cancel_events.pop(self.thread_id, None)

    def _is_cancelled(self, cancel_event: threading.Event) -> bool:
        """检查是否被取消（同时检查进程内事件和跨进程信号）

        Args:
            cancel_event: 进程内取消事件

        Returns:
            True 表示被取消，应该停止
        """
        # 1. 快速路径：检查进程内取消事件
        if cancel_event.is_set():
            return True

        # 2. 慢速路径：检查跨进程取消信号（通过 RabbitMQ）
        if hasattr(self.message_handler, "check_cancel_signal"):
            try:
                if self.message_handler.check_cancel_signal(self.thread_id):
                    # 跨进程取消信号存在，同时设置进程内事件（让后续检查更快）
                    cancel_event.set()
                    return True
            except Exception as e:
                logger.warning(f"Error checking cross-process cancel signal: {e}")

        return False

    def stream(
        self,
        generator: Generator[Any, None, None],
        on_complete: Callable[[], None] | None = None,
    ) -> Generator[Any, None, None]:
        """使用队列处理器缓存流式请求

        支持消费者抢占：当新消费者（如断点续传的新窗口）到来时，
        旧消费者会被优雅地抢占并退出，新消费者接管队列。

        Args:
            generator: 数据生成器
            on_complete: 流完成时的回调函数（在 mark_completed 之前调用），
                        用于及时更新 session status 等外部状态

        Yields:
            生成器产生的数据

        Raises:
            RuntimeError: 当心跳超时时抛出，表示生产者可能已异常结束
        """
        # 注册取消事件（让 cancel() 可以通知生产者和消费者停止）
        cancel_event = self._register_cancel_event()

        # 清理上一次可能残留的跨进程取消信号
        # 场景：前端先调用 stop（设置取消信号），然后立刻发起重新生成
        # 如果不清理，新的流会立刻检测到旧的取消信号而被误取消
        if hasattr(self.message_handler, "clear_cancel_signal"):
            try:
                self.message_handler.clear_cancel_signal(self.thread_id)
            except Exception as e:
                logger.warning(f"Error clearing old cancel signal: {e}")

        # 注册为当前活跃消费者
        consumer_id = self.message_handler.acquire_consumer(self.thread_id)

        # 检查队列中是否有未消费的数据
        has_pending = self.message_handler.has_pending_messages(self.thread_id)

        producer_thread = None
        # 记录最后一次收到消息的时间（用于心跳超时检测）
        last_message_time = time.time()
        # 是否启用心跳检测（仅在启动新生产者时启用）
        enable_heartbeat_check = False

        if not has_pending:
            # 队列看起来为空，但可能旧消费者正在被抢占过程中（消息在 processing 中还未进入 DLQ）
            # 先等待旧消费者退出（如果有的话），旧消费者退出时会 restore DLQ 消息到主队列
            prev_exited = self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=3.0)

            # 再次检查是否有未消费的数据（旧消费者退出后可能 restore 了 DLQ 消息）
            has_pending = self.message_handler.has_pending_messages(self.thread_id)
            if has_pending:
                logger.info(
                    f"Messages appeared after waiting for previous consumer "
                    f"(prev_exited={prev_exited}), thread_id={self.thread_id}, "
                    f"will consume existing messages instead of starting new producer"
                )

        if not has_pending:
            # 确认队列确实为空（不存在旧消费者 restore 的消息），需要启动新的生产者
            # 先清空队列确保干净状态
            self.message_handler.clear(self.thread_id)

            # 启动生产者线程（传入 cancel_event 以支持取消）
            producer_thread = threading.Thread(target=self._producer, args=(generator, cancel_event), daemon=True)
            producer_thread.start()
            logger.info(f"Started producer for thread_id={self.thread_id}")
            enable_heartbeat_check = True
        else:
            # 队列中有数据（可能是初次检查就有，也可能是等旧消费者退出后出现的），不启动新的生产者
            # 等待旧消费者完全退出并恢复 DLQ
            self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=3.0)
            # 将死信队列的消息恢复到主队列，从头消费
            restored = self.message_handler.restore_messages(self.thread_id)
            logger.info(
                f"Pending messages exist for thread_id={self.thread_id}, "
                f"restored {restored} messages from DLQ, consuming from start"
            )

        # 消费者：从队列中获取消息
        try:
            while True:
                try:
                    # 检查是否被取消（同时检查进程内事件和跨进程信号）
                    if self._is_cancelled(cancel_event):
                        logger.info(f"Stream cancelled for thread_id={self.thread_id}")
                        # 不立即清理 DLQ，而是通知 stop_session 可以读取了
                        # stop_session 读取完后会自己调用 mark_completed() 清理
                        if hasattr(self.message_handler, "notify_consumer_cancelled"):
                            self.message_handler.notify_consumer_cancelled(self.thread_id)
                        raise StreamCancelledError(f"Stream cancelled for thread_id={self.thread_id}")

                    # 检查是否被新消费者抢占
                    self.message_handler.check_consumer(self.thread_id, consumer_id)

                    # 从主队列获取消息（消息会被移动到死信队列）
                    messages = self.message_handler.get(self.thread_id, timeout=0.5)

                    # 收到消息，更新最后消息时间
                    if messages:
                        last_message_time = time.time()

                    # 处理获取到的消息
                    for item in messages:
                        if item == HEARTBEAT_CHUNK:
                            # 跳过心跳消息，不向消费者返回
                            logger.debug(f"Received heartbeat for thread_id={self.thread_id}")
                            continue
                        if item == EOD_CHUNK:
                            # 流完成回调（在清理队列之前更新外部状态，如 session status）
                            if on_complete:
                                try:
                                    on_complete()
                                except Exception as e:
                                    logger.exception(f"on_complete callback error: {e}")
                            # 读到结束标记，调用 mark_completed 清理所有队列
                            self.message_handler.mark_completed(self.thread_id)
                            logger.info(f"Stream completed for thread_id={self.thread_id}")
                            return
                        if item == CANCELLED_CHUNK:
                            # 主动取消，同样清理队列并结束
                            self.message_handler.mark_completed(self.thread_id)
                            logger.info(f"Stream cancelled for thread_id={self.thread_id}")
                            return
                        yield item
                except ConsumerPreemptedError:
                    # 被新消费者（如断点续传的新窗口）抢占
                    # 不清理队列，让新消费者接管
                    logger.info(
                        f"Consumer {consumer_id[:8]} preempted for thread_id={self.thread_id}, yielding to new consumer"
                    )
                    # 向上层抛出，让调用方知道不应该更新 session status
                    raise
                except TimeoutError:
                    # 超时，检查心跳是否超时
                    if enable_heartbeat_check and (time.time() - last_message_time > HEARTBEAT_TIMEOUT):
                        logger.error(f"心跳超时 thread_id={self.thread_id}，超过 {HEARTBEAT_TIMEOUT}s 未收到任何消息")
                        raise RuntimeError(
                            f"生产者心跳超时：超过 {HEARTBEAT_TIMEOUT}s 未收到任何消息，生产者可能已崩溃"
                        )
                    continue
        except GeneratorExit:
            # 客户端断开连接，不清理队列，消息已在死信队列中保留
            logger.info(f"Consumer disconnected for thread_id={self.thread_id}, messages preserved in DLQ")
            raise
        finally:
            self._unregister_cancel_event()
            # 清理跨进程取消信号（避免残留影响下次请求）
            if hasattr(self.message_handler, "clear_cancel_signal"):
                try:
                    self.message_handler.clear_cancel_signal(self.thread_id)
                except Exception as e:
                    logger.warning(f"Error clearing cancel signal: {e}")
            # 释放消费者（仅当自己仍是活跃消费者时）
            self.message_handler.release_consumer(self.thread_id, consumer_id)
            # 等待生产者线程结束（如果是本次启动的）
            if producer_thread is not None:
                try:
                    producer_thread.join(timeout=2.0)
                except Exception as e:
                    logger.exception(f"Error joining producer thread for thread_id={self.thread_id}: {e}")

    def _producer(self, generator: Generator[Any, None, None], cancel_event: threading.Event | None = None) -> None:
        """生产者线程：将生成器产生的消息推送到队列

        即使消费者断开连接，生产者也会继续运行直到完成。
        会定期发送心跳消息，让消费者知道生产者仍然存活。
        如果 cancel_event 被设置（进程内或跨进程），生产者会尽快退出。
        """
        last_heartbeat_time = time.time()
        # 跨进程取消检查计数器（每 N 个 chunk 检查一次，避免频繁访问 RabbitMQ）
        chunk_count = 0
        CROSS_PROCESS_CHECK_INTERVAL = 10  # 每处理 10 个 chunk 检查一次跨进程取消

        try:
            for chunk in generator:
                chunk_count += 1

                # 检查是否被取消（进程内快速检查）
                if cancel_event and cancel_event.is_set():
                    logger.info(f"Producer cancelled (in-process) for thread_id={self.thread_id}")
                    break

                # 定期检查跨进程取消信号（每 N 个 chunk 或心跳时检查）
                current_time = time.time()
                should_check_cross_process = (
                    chunk_count % CROSS_PROCESS_CHECK_INTERVAL == 0
                    or current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL
                )
                if should_check_cross_process and hasattr(self.message_handler, "check_cancel_signal"):
                    try:
                        if self.message_handler.check_cancel_signal(self.thread_id):
                            logger.info(f"Producer cancelled (cross-process) for thread_id={self.thread_id}")
                            if cancel_event:
                                cancel_event.set()  # 同步设置进程内标志
                            break
                    except Exception as e:
                        logger.warning(f"Error checking cross-process cancel signal in producer: {e}")

                self.message_handler.put(self.thread_id, chunk)
                logger.debug(f"Produced chunk for thread_id={self.thread_id}")

                # 检查是否需要发送心跳
                if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL:
                    self.message_handler.put(self.thread_id, HEARTBEAT_CHUNK)
                    last_heartbeat_time = current_time
                    logger.debug(f"Sent heartbeat for thread_id={self.thread_id}")
        except GeneratorExit:
            logger.info(f"Generator closed for thread_id={self.thread_id}")
        except Exception as e:
            logger.debug(f"Sent error chunk for thread_id={self.thread_id}: {e}")
        finally:
            cancelled = cancel_event.is_set() if cancel_event else False
            if cancelled:
                # 被取消时，消费者已经调用了 mark_completed() 清理队列
                # 不再推送 EOD_CHUNK，避免残留消息导致重新生成时误走断点续传
                logger.info(f"Producer cancelled, skip EOD_CHUNK for thread_id={self.thread_id}")
            else:
                # 正常结束，推送结束标记
                self.message_handler.put(self.thread_id, EOD_CHUNK)
                # 立即刷新缓冲区，确保 EOD_CHUNK 被及时发送到队列
                self.message_handler.flush(self.thread_id)
                logger.debug(f"Producer finished, sent EOD_CHUNK for thread_id={self.thread_id}")
