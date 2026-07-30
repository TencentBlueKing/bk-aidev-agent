import threading
import time
import uuid
from logging import getLogger
from typing import Any, Callable, Generator

from ag_ui.core import EventType, RunErrorEvent
from ag_ui.encoder import EventEncoder

from aidev_agent.utils.event import RunId, emit_run_finished_event

from .base import BaseMessageQueueHandler, ConsumerPreemptedError
from .constants import (
    CANCELLED_CHUNK,
    EOD_CHUNK,
    HEARTBEAT_CHUNK,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    TimeoutConfig,
)
from .factory import message_handler_factory

logger = getLogger(__name__)

# 断点续传时需要过滤的事件类型
# flow_agent_start 事件在续聊时不应该重复发送，避免前端重新渲染
_RESUME_FILTER_EVENT_TYPES: frozenset[str] = frozenset({"flow_agent_start"})


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

    # 取消后等待 generator 产出 RUN_FINISHED 的宽限时间（秒）
    CANCEL_DRAIN_TIMEOUT = TimeoutConfig.CANCEL_DRAIN_TIMEOUT

    # 生产者结束后延迟清理会话资源的等待时间（秒）
    # 需足够长以允许活跃消费者处理 EOD_CHUNK，又不至于长时间占用资源
    _PRODUCER_CLEANUP_DELAY = 30.0
    # 业务流已发出 [DONE] 且当前无活跃消费者时，保留队列等待前端接管续流的窗口（秒）。
    # 注意：后台 drain（background_only）完成后不会立即清理队列，需保留足够窗口让前端重连后
    # 通过 restore_messages 接管已生产的完整内容；窗口内若有消费者接管则跳过清理。
    _DONE_ORPHAN_CLEANUP_GRACE = 30.0
    _ORPHAN_CLEANUP_POLL_INTERVAL = 0.1

    @staticmethod
    def _should_filter_on_resume(item: Any) -> bool:
        """判断断点续传时是否应该过滤该消息

        在断点续传（续聊）场景下，某些事件不应该重复发送给前端：
        - flow_agent_start: 前端收到此事件会重新初始化/渲染，续聊时不需要

        Args:
            item: 队列中的消息（SSE 编码字符串或其他格式）

        Returns:
            True 表示应该过滤（不发送给前端），False 表示正常发送
        """
        if not isinstance(item, str):
            return False

        # 检查是否是需要过滤的事件类型
        # SSE 格式: data: {"type":"CUSTOM","name":"flow_agent_start",...}
        for event_type in _RESUME_FILTER_EVENT_TYPES:
            if f'"name":"{event_type}"' in item:
                logger.info(f"Filtering event on resume: {event_type}")
                return True
        return False

    def __init__(
        self,
        message_handler: BaseMessageQueueHandler | None = None,
        thread_id: str | None = None,
        defer_cleanup_on_complete: bool = False,
    ) -> None:
        self.message_handler = message_handler if message_handler else message_handler_factory.get()
        self.thread_id = thread_id or uuid.uuid4().hex
        # 后台 drain（无 SSE 下游）场景：读到 EOD 时不立即 mark_completed 清队列，
        # 保留 DLQ 历史供前端在清理窗口内接管续流；清理交由 producer 的延迟清理线程兜底。
        self.defer_cleanup_on_complete = defer_cleanup_on_complete

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

    @staticmethod
    def _is_done_event_chunk(chunk: Any) -> bool:
        """判断 chunk 是否为 SSE 的业务完成标记。"""
        return isinstance(chunk, str) and chunk.strip() == "data: [DONE]"

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

    def _supports_replay_from_start(self) -> bool:
        """当前 handler 是否支持多消费者从会话日志独立 replay。"""
        try:
            return self.message_handler.supports_replay_from_start()
        except Exception:
            return False

    def _get_consumer_messages(
        self,
        *,
        timeout: float,
        replay_offset: int,
    ) -> tuple[list[Any], int]:
        """读取当前消费者可见的消息。

        replay-from-start handler 使用连接内 offset 做非破坏性读取；
        旧 handler 继续使用 get() 的竞争消费语义。
        """
        if self._supports_replay_from_start():
            return self.message_handler.get_messages_since(self.thread_id, replay_offset, timeout=timeout)

        return self.message_handler.get(self.thread_id, timeout=timeout), replay_offset

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
        replay_offset = 0
        supports_replay_from_start = self._supports_replay_from_start()

        while True:
            try:
                if not supports_replay_from_start:
                    self.message_handler.check_consumer(self.thread_id, consumer_id)
                messages, replay_offset = self._get_consumer_messages(timeout=0.3, replay_offset=replay_offset)

                if not messages:
                    empty_rounds += 1
                    if empty_rounds >= max_empty_rounds:
                        # 发送 RUN_FINISHED 事件，确保前端收到标准的结束信号
                        yield emit_run_finished_event(thread_id=self.thread_id, run_id=RunId.STOPPED)
                        # 旧竞争消费模型展示完即可清理；replay 模式由完成清理或 TTL 兜底回收。
                        if not supports_replay_from_start:
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
                    # 发送 RUN_FINISHED 事件，确保前端收到标准的结束信号
                    yield emit_run_finished_event(thread_id=self.thread_id, run_id=RunId.STOPPED)
                    if not supports_replay_from_start:
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

    def _should_notify_consumer_cancelled_on_complete(self, cancel_event: threading.Event) -> bool:
        """正常结束时，仅在确实存在 stop/cancel 场景下才发送完成通知。"""
        if cancel_event.is_set():
            return True

        try:
            if self.message_handler.check_cancel_signal(self.thread_id):
                return True
        except Exception as e:
            logger.exception(f"Error checking cancel signal before completion for thread_id={self.thread_id}: {e}")

        try:
            return self.message_handler.is_stopped(self.thread_id)
        except Exception as e:
            logger.exception(f"Error checking stopped state before completion for thread_id={self.thread_id}: {e}")
            return False

    def _resolve_stopped_or_pending_state(self) -> tuple[bool, bool]:
        """解析当前会话状态，返回 (是否消费已停止会话, 是否有待消费消息)。"""
        is_stopped = self.message_handler.is_stopped(self.thread_id)
        has_pending = self.message_handler.has_pending_messages(self.thread_id)

        if not is_stopped:
            return False, has_pending

        if self._supports_replay_from_start():
            if not has_pending:
                self.message_handler.clear_stopped(self.thread_id)
                return False, False
            return True, True

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
        on_complete: Callable[[], None] | None = None,
    ) -> tuple[threading.Thread | None, bool, bool, threading.Event | None]:
        """根据队列状态决定启动生产者还是恢复旧消息。"""
        producer_thread: threading.Thread | None = None
        producer_succeeded_event: threading.Event | None = None
        is_resuming = False
        enable_heartbeat_check = False
        supports_replay_from_start = self._supports_replay_from_start()

        if not has_pending:
            if not self.message_handler.acquire_producer(self.thread_id):
                logger.info(
                    "Producer already active for thread_id=%s, consuming existing replay stream",
                    self.thread_id,
                )
                return producer_thread, True, True, producer_succeeded_event

            try:
                self.message_handler.clear(self.thread_id)
                self.message_handler.clear_stopped(self.thread_id)
            except Exception:
                self.message_handler.release_producer(self.thread_id)
                raise

            producer_succeeded_event = threading.Event()
            producer_thread = threading.Thread(
                target=self._producer,
                args=(generator, cancel_event, on_complete, True, producer_succeeded_event),
                daemon=True,
            )
            producer_thread.start()
            logger.info(f"Started producer for thread_id={self.thread_id}")
            enable_heartbeat_check = True
            return producer_thread, is_resuming, enable_heartbeat_check, producer_succeeded_event

        if supports_replay_from_start:
            is_resuming = True
            logger.info(
                "Pending messages exist for thread_id=%s, replaying cached stream from start",
                self.thread_id,
            )
            return producer_thread, is_resuming, enable_heartbeat_check, producer_succeeded_event

        self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=3.0)
        restored = self.message_handler.restore_messages(self.thread_id)
        is_resuming = True
        logger.info(
            f"Pending messages exist for thread_id={self.thread_id}, "
            f"restored {restored} messages from DLQ, consuming from start"
        )
        return producer_thread, is_resuming, enable_heartbeat_check, producer_succeeded_event

    # ---- L1 观测：consumer 循环内联耗时 WARNING 阈值（秒），仅日志用途 ----
    _CHECK_CONSUMER_SLOW_SEC = 2.0
    _GET_SLOW_SEC = 5.0
    _YIELD_SLOW_SEC = 10.0
    # consumer progress 心跳：每 N 条 yield 或每 M 秒（取先到者）
    _CONSUMER_PROGRESS_EVERY_N = 50
    _CONSUMER_PROGRESS_EVERY_SECONDS = 10.0

    def _consume_stream_messages(
        self,
        consumer_id: str,
        cancel_event: threading.Event,
        is_resuming: bool,
        enable_heartbeat_check: bool,
        on_complete: Callable[[], None] | None = None,
        producer_thread: threading.Thread | None = None,
        producer_succeeded_event: threading.Event | None = None,
    ) -> Generator[Any, None, str]:
        """消费者循环：读取队列、处理控制消息并向上游产出业务消息。

        纯观测日志（零行为改动）：
        - 入口 / 出口 INFO，`finally` 带 reason / consumed / iter；
        - `check_consumer` / `get` / `yield` 内联耗时度量，超阈值打 WARNING；
        - 每 N 条 yield 或 10s 打 1 条 progress INFO；
        - 最外层 unexpected 异常打 ERROR 后 `raise`。
        """
        consumer_draining = False
        consumer_drain_start = 0.0
        last_message_time = time.time()

        consumer_id_short = consumer_id[:8] if consumer_id else "?"
        loop_iter = 0
        yielded_total = 0
        exit_reason = "unknown"
        last_progress_ts = time.time()
        replay_offset = 0
        supports_replay_from_start = self._supports_replay_from_start()

        logger.info(
            "[RabbitMQ] consumer loop enter thread_id=%s consumer_id=%s is_resuming=%s heartbeat_check=%s",
            self.thread_id,
            consumer_id_short,
            is_resuming,
            enable_heartbeat_check,
        )

        def _maybe_log_progress() -> None:
            nonlocal last_progress_ts
            now = time.time()
            if yielded_total and (
                yielded_total % self._CONSUMER_PROGRESS_EVERY_N == 0
                or now - last_progress_ts >= self._CONSUMER_PROGRESS_EVERY_SECONDS
            ):
                logger.info(
                    "[RabbitMQ] consumer progress thread_id=%s consumer_id=%s consumed_total=%d iter=%d",
                    self.thread_id,
                    consumer_id_short,
                    yielded_total,
                    loop_iter,
                )
                last_progress_ts = now

        try:
            while True:
                loop_iter += 1
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
                        self._notify_consumer_cancelled_safely()
                        yield emit_run_finished_event(thread_id=self.thread_id, run_id=RunId.CANCELLED)
                        yielded_total += 1
                        exit_reason = "drain_timeout"
                        return exit_reason

                    if not supports_replay_from_start:
                        t_check = time.time()
                        self.message_handler.check_consumer(self.thread_id, consumer_id)
                        check_elapsed = time.time() - t_check
                        if check_elapsed > self._CHECK_CONSUMER_SLOW_SEC:
                            logger.warning(
                                "[RabbitMQ] check_consumer slow thread_id=%s consumer_id=%s elapsed=%.2fs",
                                self.thread_id,
                                consumer_id_short,
                                check_elapsed,
                            )

                    t_get = time.time()
                    messages, replay_offset = self._get_consumer_messages(timeout=0.5, replay_offset=replay_offset)
                    get_elapsed = time.time() - t_get
                    if get_elapsed > self._GET_SLOW_SEC:
                        logger.warning(
                            "[RabbitMQ] get slow thread_id=%s consumer_id=%s elapsed=%.2fs got=%d",
                            self.thread_id,
                            consumer_id_short,
                            get_elapsed,
                            len(messages),
                        )

                    if messages:
                        last_message_time = time.time()

                    for item in messages:
                        if item == HEARTBEAT_CHUNK:
                            logger.debug(f"Received heartbeat for thread_id={self.thread_id}")
                            continue
                        if item == EOD_CHUNK:
                            logger.info(f"[EOD] Consumer received EOD_CHUNK for thread_id={self.thread_id}")
                            should_notify_cancelled = self._should_notify_consumer_cancelled_on_complete(cancel_event)
                            if on_complete and not supports_replay_from_start:
                                try:
                                    on_complete()
                                except Exception as e:
                                    logger.exception(f"on_complete callback error: {e}")
                            if not supports_replay_from_start and not self.defer_cleanup_on_complete:
                                self.message_handler.mark_completed(self.thread_id)
                                logger.info(f"Stream completed for thread_id={self.thread_id}")
                            elif self.defer_cleanup_on_complete:
                                # 后台 drain（无 SSE 下游）：不立即清理队列，保留 DLQ 历史供前端接管续流。
                                # 实际清理由 producer 的 _schedule_session_cleanup 在窗口内兜底，
                                # 若窗口内有前端接管消费则跳过清理。
                                logger.info(
                                    f"Stream completed for thread_id={self.thread_id} "
                                    f"(background drain, defer cleanup for frontend takeover)"
                                )
                            else:
                                # supports_replay_from_start 场景：由上层在合适时机统一 mark_completed
                                logger.info(f"Stream completed for thread_id={self.thread_id}")
                            if should_notify_cancelled:
                                # cancel 可能已发出但 Agent 恰好也完成了，此时仍需通知 stop 接口。
                                self._notify_consumer_cancelled_safely()
                            exit_reason = "completed"
                            return exit_reason
                        if item == CANCELLED_CHUNK:
                            if hasattr(self.message_handler, "mark_stopped"):
                                self.message_handler.mark_stopped(self.thread_id)
                            logger.info(f"Stream cancelled for thread_id={self.thread_id}, DLQ content preserved")
                            self._notify_consumer_cancelled_safely()
                            yield emit_run_finished_event(thread_id=self.thread_id, run_id=RunId.CANCELLED)
                            yielded_total += 1
                            exit_reason = "cancelled"
                            return exit_reason
                        if is_resuming and self._should_filter_on_resume(item):
                            logger.debug(f"Filtered thinking event in resume mode for thread_id={self.thread_id}")
                            continue
                        t_yield = time.time()
                        yield item
                        yield_elapsed = time.time() - t_yield
                        yielded_total += 1
                        if yield_elapsed > self._YIELD_SLOW_SEC:
                            # H1 直接证据：下游消费慢 / SSE 发送缓冲满 / 网关 buffering
                            logger.warning(
                                "[RabbitMQ] yield slow thread_id=%s consumer_id=%s elapsed=%.2fs yielded_total=%d",
                                self.thread_id,
                                consumer_id_short,
                                yield_elapsed,
                                yielded_total,
                            )
                        _maybe_log_progress()
                except ConsumerPreemptedError:
                    logger.info(
                        f"Consumer {consumer_id[:8]} preempted for thread_id={self.thread_id}, yielding to new consumer"
                    )
                    exit_reason = "preempted"
                    raise
                except TimeoutError:
                    time_since_last = time.time() - last_message_time
                    if enable_heartbeat_check and time_since_last > HEARTBEAT_TIMEOUT:
                        # 兜底：nack(requeue=True) 在大队列上反复 peek 会静默丢消息（含 EOD），
                        # consumer 收不到 EOD 而误判 starved。仅当 producer 线程已结束且
                        # 明确记录 EOD flush 成功时，才按正常完成处理，避免掩盖 producer
                        # 异常或消息投递失败。
                        producer_finished = producer_thread is not None and not producer_thread.is_alive()
                        producer_succeeded = producer_succeeded_event is not None and producer_succeeded_event.is_set()
                        if producer_finished and producer_succeeded:
                            logger.info(
                                "[EOD] starved 兜底：producer 已结束，按正常完成处理 thread_id=%s",
                                self.thread_id,
                            )
                            should_notify_cancelled = self._should_notify_consumer_cancelled_on_complete(cancel_event)
                            if on_complete and not supports_replay_from_start:
                                try:
                                    on_complete()
                                except Exception as e:
                                    logger.exception(f"on_complete callback error (starved fallback): {e}")
                            if not supports_replay_from_start and not self.defer_cleanup_on_complete:
                                self.message_handler.mark_completed(self.thread_id)
                                logger.info(f"Stream completed (starved fallback) for thread_id={self.thread_id}")
                            elif self.defer_cleanup_on_complete:
                                logger.info(
                                    f"Stream completed (starved fallback, background drain) "
                                    f"for thread_id={self.thread_id}"
                                )
                            else:
                                logger.info(f"Stream completed (starved fallback) for thread_id={self.thread_id}")
                            if should_notify_cancelled:
                                self._notify_consumer_cancelled_safely()
                            exit_reason = "completed"
                            return exit_reason
                        logger.error(
                            f"心跳超时 thread_id={self.thread_id}，距上次消息 {time_since_last:.1f}s "
                            f"(last_message_time={last_message_time:.1f}, now={time.time():.1f}) "
                            f"replay_offset={replay_offset} producer_finished={producer_finished} "
                            f"producer_succeeded={producer_succeeded}"
                        )
                        exit_reason = "starved"
                        raise RuntimeError(
                            f"生产者心跳超时：超过 {HEARTBEAT_TIMEOUT}s 未收到任何消息，生产者可能已崩溃"
                        )
                    continue
                except Exception as exc:
                    # L-5：避免 unexpected 异常被上层 _wrap_streaming_with_status 吞成沉默
                    logger.error(
                        "[RabbitMQ] consumer loop unexpected exception thread_id=%s consumer_id=%s "
                        "loop_iter=%d yielded_total=%d exc=%r",
                        self.thread_id,
                        consumer_id_short,
                        loop_iter,
                        yielded_total,
                        exc,
                    )
                    exit_reason = "error"
                    raise
        except GeneratorExit:
            exit_reason = "generator_exit"
            raise
        finally:
            logger.info(
                "[RabbitMQ] consumer loop exit thread_id=%s consumer_id=%s reason=%s consumed=%d iter=%d",
                self.thread_id,
                consumer_id_short,
                exit_reason,
                yielded_total,
                loop_iter,
            )

    def _cleanup_replay_session_if_idle(self) -> None:
        """replay 模式下，最后一个正常完成的消费者负责清理会话日志。"""
        if not self._supports_replay_from_start():
            return

        try:
            has_pending = self.message_handler.has_pending_messages(self.thread_id)
            has_active_consumer = self.message_handler.has_active_consumer(self.thread_id)
            if has_pending and not has_active_consumer:
                self.message_handler.mark_completed(self.thread_id)
                logger.info("[RabbitMQ] replay session completed and cleaned thread_id=%s", self.thread_id)
        except Exception:
            logger.exception("Error cleaning completed replay session for thread_id=%s", self.thread_id)

    def stream(
        self,
        generator: Generator[Any, None, None],
        on_complete: Callable[[], None] | None = None,
    ) -> Generator[Any, None, None]:
        """使用队列处理器缓存流式请求

        replay-from-start handler 支持多个消费者各自从会话日志开头 replay；
        旧 handler 仍使用竞争消费语义，新消费者会抢占旧消费者。

        Args:
            generator: 数据生成器
            on_complete: 流完成时的回调函数，用于及时更新 session status 等外部状态。
                replay-from-start handler 在 producer 完成时调用；旧 handler 在消费到 EOD 后调用。

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
        producer_succeeded_event: threading.Event | None = None
        consumer_exit_reason: str | None = None

        should_consume_stopped, has_pending = self._resolve_stopped_or_pending_state()

        try:
            if should_consume_stopped:
                yield from self._consume_stopped_session(consumer_id)
                return

            has_pending = self._recheck_pending_after_waiting_consumer(has_pending)
            producer_thread, is_resuming, enable_heartbeat_check, producer_succeeded_event = (
                self._start_or_resume_stream(
                    generator=generator,
                    cancel_event=cancel_event,
                    has_pending=has_pending,
                    on_complete=on_complete,
                )
            )
            consumer_exit_reason = yield from self._consume_stream_messages(
                consumer_id=consumer_id,
                cancel_event=cancel_event,
                is_resuming=is_resuming,
                enable_heartbeat_check=enable_heartbeat_check,
                on_complete=on_complete,
                producer_thread=producer_thread,
                producer_succeeded_event=producer_succeeded_event,
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
            if consumer_exit_reason == "completed":
                self._cleanup_replay_session_if_idle()

    def _schedule_session_cleanup(self, done_event_seen: bool = False) -> None:
        """生产者完成后延迟清理孤立的会话资源。

        用户断开连接后，如果未在延迟窗口内重连消费数据，队列数据会一直保留到 TTL 过期。
        此方法启动一个守护线程，在延迟后检查队列中是否仍有未消费的数据，
        若有则调用 mark_completed 主动释放资源。
        """
        thread_id = self.thread_id
        handler = self.message_handler
        delay = self._PRODUCER_CLEANUP_DELAY
        grace = self._DONE_ORPHAN_CLEANUP_GRACE
        poll_interval = self._ORPHAN_CLEANUP_POLL_INTERVAL

        def _do_cleanup() -> None:
            try:
                start_time = time.time()
                fast_cleanup_at = start_time + grace if done_event_seen else None
                deadline = start_time + delay
                # L-6 观测：区分 A1「消费者从未来过」/ A2「消费者到过又走了」
                consumer_ever_seen = False

                while True:
                    if not handler.has_pending_messages(thread_id):
                        logger.debug(f"Session already consumed for thread_id={thread_id}, skipping cleanup")
                        return

                    has_active_consumer = handler.has_active_consumer(thread_id)
                    if has_active_consumer:
                        consumer_ever_seen = True
                    now = time.time()
                    should_cleanup_now = False
                    trigger_reason = ""

                    fast_grace_hit = (
                        done_event_seen
                        and not has_active_consumer
                        and fast_cleanup_at is not None
                        and now >= fast_cleanup_at
                    )
                    deadline_hit = now >= deadline
                    if fast_grace_hit or deadline_hit:
                        should_cleanup_now = True
                        trigger_reason = "fast_grace" if fast_grace_hit and not deadline_hit else "deadline"

                    if should_cleanup_now:
                        logger.info(
                            "[RabbitMQ] orphan cleanup triggered thread_id=%s elapsed=%.1fs "
                            "reason=%s done_event_seen=%s had_active_consumer=%s consumer_ever_seen=%s",
                            thread_id,
                            now - start_time,
                            trigger_reason,
                            done_event_seen,
                            has_active_consumer,
                            consumer_ever_seen,
                        )
                        handler.mark_completed(thread_id)
                        logger.info(f"Cleaned up orphaned session data for thread_id={thread_id}")
                        return

                    time.sleep(min(poll_interval, max(deadline - now, 0.0)))
            except Exception:
                logger.exception(f"Error in delayed session cleanup for thread_id={thread_id}")

        threading.Thread(
            target=_do_cleanup,
            daemon=True,
            name=f"session-cleanup-{thread_id[:8]}",
        ).start()

    def _producer(
        self,
        generator: Generator[Any, None, None],
        cancel_event: threading.Event | None = None,
        on_complete: Callable[[], None] | None = None,
        release_producer: bool = False,
        producer_succeeded_event: threading.Event | None = None,
    ) -> None:
        """生产者线程：将生成器产生的消息推送到队列

        即使消费者断开连接，生产者也会继续运行直到完成。
        会定期发送心跳消息，让消费者知道生产者仍然存活。
        如果 cancel_event 被设置（进程内或跨进程），生产者不会直接退出，
        而是继续 drain generator 一段时间，等待 Agent 内部的 cancel_checker 触发
        并 yield RUN_FINISHED 事件，确保前端能收到完整的结束信号。
        """
        _producer_start = time.monotonic()
        logger.info(f"[PRODUCER] start thread_id={self.thread_id} thread={threading.current_thread().name}")
        heartbeat_stop_event = threading.Event()
        heartbeat_thread: threading.Thread | None = None
        # 跨进程取消检查计数器（每 N 个 chunk 检查一次，避免频繁访问 RabbitMQ）
        chunk_count = 0
        CROSS_PROCESS_CHECK_INTERVAL = 10  # 每处理 10 个 chunk 检查一次跨进程取消
        last_cross_process_check_time = time.time()
        # 标记是否进入取消 drain 模式（检测到取消后继续读取 generator，等待 RUN_FINISHED）
        draining = False
        drain_start_time = 0.0
        done_event_seen = False
        producer_error = False

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
                if self._is_done_event_chunk(chunk):
                    done_event_seen = True

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
            producer_error = True
            logger.exception(f"Producer error for thread_id={self.thread_id}: {e}")
            # 将错误信息作为 SSE error event 推送到队列，让消费者能感知并传播给前端
            try:
                encoder = EventEncoder()
                error_event = RunErrorEvent(type=EventType.RUN_ERROR, message=f"Producer error: {e}")
                self.message_handler.put(self.thread_id, encoder.encode(error_event))
            except Exception as encode_err:
                logger.exception(f"Failed to encode/send error event for thread_id={self.thread_id}: {encode_err}")
        finally:
            logger.info(
                f"[PRODUCER] finally enter thread_id={self.thread_id} "
                f"producer_error={producer_error} done_event_seen={done_event_seen} "
                f"draining={draining} "
                f"elapsed={time.monotonic() - _producer_start:.1f}s"
            )
            heartbeat_stop_event.set()
            if heartbeat_thread is not None:
                try:
                    heartbeat_thread.join(timeout=HEARTBEAT_INTERVAL + 0.2)
                except Exception as e:
                    logger.exception(f"Error joining heartbeat thread for thread_id={self.thread_id}: {e}")

            if on_complete and self._supports_replay_from_start() and not producer_error:
                try:
                    on_complete()
                except Exception as e:
                    logger.exception(f"on_complete callback error in producer: {e}")

            # 无论是正常结束还是取消，都推送 EOD_CHUNK 让消费者知道流已结束
            logger.info(
                f"[EOD] Producer sending EOD_CHUNK for thread_id={self.thread_id} (producer_error={producer_error})"
            )
            self.message_handler.put(self.thread_id, EOD_CHUNK)
            self.message_handler.flush(self.thread_id)
            if not producer_error and producer_succeeded_event is not None:
                producer_succeeded_event.set()
            logger.info(f"[EOD] Producer EOD_CHUNK sent successfully for thread_id={self.thread_id}")

            # 延迟清理：如果消费者已断开且未重连，主动释放队列资源
            # 不能立即清理，否则会与正在读取 EOD_CHUNK 的活跃消费者竞争
            self._schedule_session_cleanup(done_event_seen=done_event_seen)
            if release_producer:
                logger.info(
                    f"[PRODUCER] releasing producer lock thread_id={self.thread_id} "
                    f"elapsed={time.monotonic() - _producer_start:.1f}s"
                )
                # 兜底：release_producer 内部已对连接断开做容错，这里再加一层
                # try 防止任何遗漏的异常冒泡导致 _producer 线程异常退出
                try:
                    self.message_handler.release_producer(self.thread_id)
                except Exception as e:
                    logger.exception(f"Error releasing producer for thread_id={self.thread_id}: {e}")
