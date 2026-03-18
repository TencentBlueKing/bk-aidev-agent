import threading
import time
import uuid
from logging import getLogger
from typing import Any, Callable, Generator

from .base import BaseMessageQueueHandler, ConsumerPreemptedError
from .constants import (
    CANCELLED_CHUNK,
    EOD_CHUNK,
    HEARTBEAT_CHUNK,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    STOPPED_CHUNK,
    TimeoutConfig,
)
from .factory import message_handler_factory

logger = getLogger(__name__)

# 断点续传时需要过滤的事件类型
_RESUME_FILTER_EVENT_TYPES: frozenset[str] = frozenset()


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

    @staticmethod
    def _should_filter_on_resume(item: Any) -> bool:  # noqa: ARG004
        """判断断点续传时是否应该过滤该消息

        注意：目前不过滤任何事件，包括 THINKING_* 事件，
        因为前端需要通过 SSE 流恢复思考内容。

        Args:
            item: 队列中的消息（SSE 编码字符串或其他格式）

        Returns:
            始终返回 False，表示不过滤任何消息
        """
        # 目前不过滤任何事件类型
        return False

    def __init__(self, message_handler: BaseMessageQueueHandler | None = None, thread_id: str | None = None) -> None:
        self.message_handler = message_handler if message_handler else message_handler_factory.get()
        self.thread_id = thread_id or uuid.uuid4().hex

    @classmethod
    def _check_cancel_status(
        cls,
        thread_id: str,
        message_handler: BaseMessageQueueHandler | None = None,
        set_event_on_cross_process: bool = False,
        cancel_event: "threading.Event | None" = None,
    ) -> bool:
        """检查取消状态的公共逻辑（内部使用）

        同时检查：
        1. 进程内取消事件（快速路径）
        2. 跨进程取消信号（通过 RabbitMQ）

        Args:
            thread_id: 线程 ID / session_code
            message_handler: 消息处理器，用于检查跨进程取消信号
            set_event_on_cross_process: 如果检测到跨进程取消信号，是否同时设置进程内事件
            cancel_event: 进程内取消事件（当 set_event_on_cross_process=True 时使用）

        Returns:
            True 表示已被取消，应该停止
        """
        # 1. 快速路径：检查进程内取消事件
        with cls._cancel_lock:
            event = cls._cancel_events.get(thread_id)
            if event and event.is_set():
                return True

        # 2. 慢速路径：检查跨进程取消信号
        if message_handler is None:
            message_handler = message_handler_factory.get()

        try:
            cross_cancelled = message_handler.check_cancel_signal(thread_id)
            if cross_cancelled:
                # 跨进程取消信号存在，同时设置进程内事件（让后续检查更快）
                if set_event_on_cross_process and cancel_event:
                    cancel_event.set()
                return True
        except Exception as e:
            logger.exception(f"Error checking cancel signal for thread_id={thread_id}: {e}")

        return False

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

        try:
            cross_process_result = message_handler.set_cancel_signal(thread_id)
            if cross_process_result:
                result = True
        except Exception as e:
            logger.exception(f"Error setting cross-process cancel signal: {e}")

        return result

    @classmethod
    def is_cancelled(cls, thread_id: str, message_handler: BaseMessageQueueHandler | None = None) -> bool:
        """检查指定 thread_id 是否已被取消（供 Agent 内部使用）

        Args:
            thread_id: 线程 ID / session_code
            message_handler: 消息处理器，用于检查跨进程取消信号。如果为 None，
                           使用默认的消息处理器

        Returns:
            True 表示已被取消，应该停止
        """
        return cls._check_cancel_status(thread_id, message_handler)

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
            logger.exception(f"Error checking has_output for thread_id={thread_id}: {e}")
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
        # 直接使用公共方法检查，并在检测到跨进程取消时同步设置进程内事件
        return self._check_cancel_status(
            self.thread_id,
            self.message_handler,
            set_event_on_cross_process=True,
            cancel_event=cancel_event,
        )

    def _consume_stopped_session(
        self,
        consumer_id: str,
    ) -> Generator[Any, None, None]:
        """消费已停止会话的消息（内部方法）

        用于用户点击 Stop 后再次进入会话的场景，只展示已有内容，不启动新生产者。

        Args:
            consumer_id: 消费者 ID

        Yields:
            队列中的消息（跳过控制消息）
        """
        max_empty_rounds = 3  # 最多空轮询3次就结束
        empty_rounds = 0

        while True:
            try:
                self.message_handler.check_consumer(self.thread_id, consumer_id)
                messages = self.message_handler.get(self.thread_id, timeout=0.3)

                if not messages:
                    empty_rounds += 1
                    if empty_rounds >= max_empty_rounds:
                        # 没有更多消息了，发送 STOPPED_CHUNK 并结束
                        yield STOPPED_CHUNK
                        # 清理队列（因为已经展示完了）
                        self.message_handler.mark_completed(self.thread_id)
                        # 清除停止标记
                        self.message_handler.clear_stopped(self.thread_id)
                        return
                    continue

                empty_rounds = 0  # 重置空轮询计数
                for item in messages:
                    if item in (HEARTBEAT_CHUNK, EOD_CHUNK, CANCELLED_CHUNK):
                        continue  # 跳过控制消息
                    # 已停止会话也是恢复模式，过滤 thinking 事件避免重复显示
                    if self._should_filter_on_resume(item):
                        logger.debug(f"Filtered thinking event in stopped session for thread_id={self.thread_id}")
                        continue
                    yield item
            except ConsumerPreemptedError:
                logger.info(f"Consumer preempted in stopped session for thread_id={self.thread_id}")
                raise
            except TimeoutError:
                empty_rounds += 1
                if empty_rounds >= max_empty_rounds:
                    yield STOPPED_CHUNK
                    self.message_handler.mark_completed(self.thread_id)
                    self.message_handler.clear_stopped(self.thread_id)
                    return
                continue

    def _clear_cancel_signal_safely(self, error_prefix: str) -> None:
        """安全清理跨进程取消信号，避免异常打断主流程。"""
        try:
            self.message_handler.clear_cancel_signal(self.thread_id)
        except Exception as e:
            logger.exception(f"{error_prefix}: {e}")

    def _notify_consumer_cancelled_safely(self) -> None:
        """安全发送消费者取消完成通知，避免异常打断主流程。

        在消费者因取消信号退出时调用，通知 stop 接口流已结束。
        """
        try:
            if hasattr(self.message_handler, "notify_consumer_cancelled"):
                self.message_handler.notify_consumer_cancelled(self.thread_id)
        except Exception as e:
            logger.exception(f"Error sending consumer cancelled notification for thread_id={self.thread_id}: {e}")

    def _resolve_stopped_or_pending_state(self) -> tuple[bool, bool]:
        """解析当前会话状态，返回 (是否消费已停止会话, 是否有待消费消息)。"""
        is_stopped = self.message_handler.is_stopped(self.thread_id)
        has_pending = self.message_handler.has_pending_messages(self.thread_id)

        if not is_stopped:
            return False, has_pending

        # Stop 后再次进入：优先展示已有内容
        self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=1.0)
        restored = self.message_handler.restore_messages(self.thread_id)
        main_count = self.message_handler.get_cached_count(self.thread_id)

        if restored == 0 and main_count == 0:
            # 没有可展示内容，按“重新生成”处理
            self.message_handler.clear_stopped(self.thread_id)
            return False, False

        return True, True

    def _recheck_pending_after_waiting_consumer(self, has_pending: bool) -> bool:
        """队列初判为空时，等待旧消费者退出后再次确认是否有消息。"""
        if has_pending:
            return True

        prev_exited = self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=3.0)
        has_pending = self.message_handler.has_pending_messages(self.thread_id)
        if has_pending:
            logger.info(
                f"Messages appeared after waiting for previous consumer "
                f"(prev_exited={prev_exited}), thread_id={self.thread_id}, "
                f"will consume existing messages instead of starting new producer"
            )
        return has_pending

    def _start_or_resume_stream(
        self,
        generator: Generator[Any, None, None],
        cancel_event: threading.Event,
        has_pending: bool,
    ) -> tuple[threading.Thread | None, bool, bool]:
        """根据队列状态决定启动生产者还是恢复旧消息。"""
        producer_thread: threading.Thread | None = None
        is_resuming = False
        enable_heartbeat_check = False

        if not has_pending:
            self.message_handler.clear(self.thread_id)
            self.message_handler.clear_stopped(self.thread_id)

            producer_thread = threading.Thread(target=self._producer, args=(generator, cancel_event), daemon=True)
            producer_thread.start()
            logger.info(f"Started producer for thread_id={self.thread_id}")
            enable_heartbeat_check = True
            return producer_thread, is_resuming, enable_heartbeat_check

        self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=3.0)
        restored = self.message_handler.restore_messages(self.thread_id)
        is_resuming = True
        logger.info(
            f"Pending messages exist for thread_id={self.thread_id}, "
            f"restored {restored} messages from DLQ, consuming from start"
        )
        return producer_thread, is_resuming, enable_heartbeat_check

    def _consume_stream_messages(
        self,
        consumer_id: str,
        cancel_event: threading.Event,
        is_resuming: bool,
        enable_heartbeat_check: bool,
        on_complete: Callable[[], None] | None = None,
    ) -> Generator[Any, None, None]:
        """消费者循环：读取队列、处理控制消息并向上游产出业务消息。"""
        consumer_draining = False
        consumer_drain_start = 0.0
        last_message_time = time.time()

        while True:
            try:
                if not consumer_draining and self._is_cancelled(cancel_event):
                    logger.info(
                        f"Stream cancel detected for thread_id={self.thread_id}, "
                        f"entering drain mode to wait for RUN_FINISHED"
                    )
                    consumer_draining = True
                    consumer_drain_start = time.time()

                if consumer_draining and (time.time() - consumer_drain_start > self.CANCEL_DRAIN_TIMEOUT):
                    logger.exception(
                        f"Consumer drain timeout ({self.CANCEL_DRAIN_TIMEOUT}s) "
                        f"for thread_id={self.thread_id}, force exit"
                    )
                    if hasattr(self.message_handler, "mark_stopped"):
                        self.message_handler.mark_stopped(self.thread_id)
                    # 通知 stop 接口：流已结束，可以继续后续操作
                    self._notify_consumer_cancelled_safely()
                    yield STOPPED_CHUNK
                    return

                self.message_handler.check_consumer(self.thread_id, consumer_id)
                messages = self.message_handler.get(self.thread_id, timeout=0.5)

                if messages:
                    last_message_time = time.time()

                for item in messages:
                    if item == HEARTBEAT_CHUNK:
                        logger.debug(f"Received heartbeat for thread_id={self.thread_id}")
                        continue
                    if item == EOD_CHUNK:
                        if on_complete:
                            try:
                                on_complete()
                            except Exception as e:
                                logger.exception(f"on_complete callback error: {e}")
                        self.message_handler.mark_completed(self.thread_id)
                        logger.info(f"Stream completed for thread_id={self.thread_id}")
                        # 通知 stop 接口：流已结束（正常结束也需要通知，
                        # 因为 cancel 可能已发出但 Agent 恰好也完成了）
                        self._notify_consumer_cancelled_safely()
                        return
                    if item == CANCELLED_CHUNK:
                        if hasattr(self.message_handler, "mark_stopped"):
                            self.message_handler.mark_stopped(self.thread_id)
                        logger.info(f"Stream cancelled for thread_id={self.thread_id}, DLQ content preserved")
                        # 通知 stop 接口：流已结束，可以继续后续操作
                        self._notify_consumer_cancelled_safely()
                        yield STOPPED_CHUNK
                        return
                    if is_resuming and self._should_filter_on_resume(item):
                        logger.debug(f"Filtered thinking event in resume mode for thread_id={self.thread_id}")
                        continue
                    yield item
            except ConsumerPreemptedError:
                logger.info(
                    f"Consumer {consumer_id[:8]} preempted for thread_id={self.thread_id}, yielding to new consumer"
                )
                raise
            except TimeoutError:
                if enable_heartbeat_check and (time.time() - last_message_time > HEARTBEAT_TIMEOUT):
                    logger.error(f"心跳超时 thread_id={self.thread_id}，超过 {HEARTBEAT_TIMEOUT}s 未收到任何消息")
                    raise RuntimeError(f"生产者心跳超时：超过 {HEARTBEAT_TIMEOUT}s 未收到任何消息，生产者可能已崩溃")
                continue

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
        self._clear_cancel_signal_safely("Error clearing old cancel signal")

        # 注册为当前活跃消费者
        consumer_id = self.message_handler.acquire_consumer(self.thread_id)
        producer_thread: threading.Thread | None = None

        should_consume_stopped, has_pending = self._resolve_stopped_or_pending_state()

        try:
            if should_consume_stopped:
                yield from self._consume_stopped_session(consumer_id)
                return

            has_pending = self._recheck_pending_after_waiting_consumer(has_pending)
            producer_thread, is_resuming, enable_heartbeat_check = self._start_or_resume_stream(
                generator=generator,
                cancel_event=cancel_event,
                has_pending=has_pending,
            )
            yield from self._consume_stream_messages(
                consumer_id=consumer_id,
                cancel_event=cancel_event,
                is_resuming=is_resuming,
                enable_heartbeat_check=enable_heartbeat_check,
                on_complete=on_complete,
            )
        except GeneratorExit:
            # 客户端断开连接，不清理队列，消息已在死信队列中保留
            logger.info(f"Consumer disconnected for thread_id={self.thread_id}, messages preserved in DLQ")
            raise
        finally:
            self._unregister_cancel_event()
            # 清理跨进程取消信号（避免残留影响下次请求）
            self._clear_cancel_signal_safely("Error clearing cancel signal")
            # 释放消费者（仅当自己仍是活跃消费者时）
            self.message_handler.release_consumer(self.thread_id, consumer_id)
            # 等待生产者线程结束（如果是本次启动的）
            if producer_thread is not None:
                try:
                    producer_thread.join(timeout=self.CANCEL_DRAIN_TIMEOUT + 2.0)
                except Exception as e:
                    logger.exception(f"Error joining producer thread for thread_id={self.thread_id}: {e}")

    # 取消后等待 generator 产出 RUN_FINISHED 的宽限时间（秒）
    CANCEL_DRAIN_TIMEOUT = TimeoutConfig.CANCEL_DRAIN_TIMEOUT

    def _producer(self, generator: Generator[Any, None, None], cancel_event: threading.Event | None = None) -> None:
        """生产者线程：将生成器产生的消息推送到队列

        即使消费者断开连接，生产者也会继续运行直到完成。
        会定期发送心跳消息，让消费者知道生产者仍然存活。
        如果 cancel_event 被设置（进程内或跨进程），生产者不会直接退出，
        而是继续 drain generator 一段时间，等待 Agent 内部的 cancel_checker 触发
        并 yield RUN_FINISHED 事件，确保前端能收到完整的结束信号。
        """
        heartbeat_stop_event = threading.Event()
        heartbeat_thread: threading.Thread | None = None
        # 跨进程取消检查计数器（每 N 个 chunk 检查一次，避免频繁访问 RabbitMQ）
        chunk_count = 0
        CROSS_PROCESS_CHECK_INTERVAL = 10  # 每处理 10 个 chunk 检查一次跨进程取消
        last_cross_process_check_time = time.time()
        # 标记是否进入取消 drain 模式（检测到取消后继续读取 generator，等待 RUN_FINISHED）
        draining = False
        drain_start_time = 0.0

        def _heartbeat_worker() -> None:
            """独立心跳线程：即使 generator 阻塞也保持心跳。"""
            while not heartbeat_stop_event.wait(HEARTBEAT_INTERVAL):
                try:
                    self.message_handler.put(self.thread_id, HEARTBEAT_CHUNK)
                    logger.debug(f"Sent heartbeat for thread_id={self.thread_id}")
                except Exception as e:
                    logger.exception(f"Error sending heartbeat for thread_id={self.thread_id}: {e}")

        try:
            heartbeat_thread = threading.Thread(
                target=_heartbeat_worker,
                daemon=True,
                name=f"stream-heartbeat-{self.thread_id[:8]}",
            )
            heartbeat_thread.start()

            for chunk in generator:
                chunk_count += 1

                if not draining:
                    # 检查是否被取消（进程内快速检查）
                    if cancel_event and cancel_event.is_set():
                        logger.info(f"Producer entering drain mode (in-process cancel) for thread_id={self.thread_id}")
                        draining = True
                        drain_start_time = time.time()
                        heartbeat_stop_event.set()
                        # 不 break，继续 drain generator 等待 RUN_FINISHED

                    # 定期检查跨进程取消信号（每 N 个 chunk 或固定时间间隔）
                    current_time = time.time()
                    should_check_cross_process = (
                        chunk_count % CROSS_PROCESS_CHECK_INTERVAL == 0
                        or current_time - last_cross_process_check_time >= HEARTBEAT_INTERVAL
                    )
                    if should_check_cross_process:
                        last_cross_process_check_time = current_time
                        try:
                            cross_cancelled = self.message_handler.check_cancel_signal(self.thread_id)
                            if cross_cancelled:
                                logger.info(
                                    f"Producer entering drain mode (cross-process cancel) "
                                    f"for thread_id={self.thread_id}"
                                )
                                if cancel_event:
                                    cancel_event.set()  # 同步设置进程内标志
                                draining = True
                                drain_start_time = time.time()
                                heartbeat_stop_event.set()
                        except Exception as e:
                            logger.exception(f"Error checking cross-process cancel signal in producer: {e}")
                else:
                    # drain 模式：检查是否超时
                    if time.time() - drain_start_time > self.CANCEL_DRAIN_TIMEOUT:
                        logger.exception(
                            f"Producer drain timeout ({self.CANCEL_DRAIN_TIMEOUT}s) "
                            f"for thread_id={self.thread_id}, force exit"
                        )
                        break

                self.message_handler.put(self.thread_id, chunk)
                logger.debug(f"Produced chunk for thread_id={self.thread_id}")
        except GeneratorExit:
            logger.info(f"Generator closed for thread_id={self.thread_id}")
        except Exception as e:
            logger.debug(f"Sent error chunk for thread_id={self.thread_id}: {e}")
        finally:
            heartbeat_stop_event.set()
            if heartbeat_thread is not None:
                try:
                    heartbeat_thread.join(timeout=HEARTBEAT_INTERVAL + 0.2)
                except Exception as e:
                    logger.exception(f"Error joining heartbeat thread for thread_id={self.thread_id}: {e}")

            # 无论是正常结束还是取消，都推送 EOD_CHUNK 让消费者知道流已结束
            self.message_handler.put(self.thread_id, EOD_CHUNK)
            self.message_handler.flush(self.thread_id)
            logger.debug(f"Producer finished, sent EOD_CHUNK for thread_id={self.thread_id}")
