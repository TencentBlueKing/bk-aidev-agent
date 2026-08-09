import json
import threading
import time
import uuid
from logging import getLogger
from typing import Any, Callable, Generator

from ag_ui.core import EventType, RawEvent, RunErrorEvent, RunFinishedEvent
from ag_ui.encoder import EventEncoder

from aidev_agent.core.ag_ui.types import RunFinishedSuccessOutcome, serialize_run_finished_outcome
from aidev_agent.utils.event import RunId, emit_run_finished_event

from .base import (
    BaseMessageQueueHandler,
    ConsumerPreemptedError,
    RetryableHeartbeatTimeoutError,
    StreamAttachUnavailableError,
)
from .constants import (
    CANCELLED_CHUNK,
    EOD_CHUNK,
    HEARTBEAT_CHUNK,
    HEARTBEAT_INTERVAL,
    TimeoutConfig,
)
from .factory import message_handler_factory

logger = getLogger(__name__)

_SSE_HEARTBEAT_EVENT = EventEncoder().encode(
    RawEvent(type=EventType.RAW, event={"type": "heartbeat"}),
)

# 断点续传时需要过滤的事件类型
# flow_agent_start 事件在续聊时不应该重复发送，避免前端重新渲染
_RESUME_FILTER_EVENT_TYPES: frozenset[str] = frozenset({"flow_agent_start"})


class GeneratorStreamingHelper:
    """生成器流式处理辅助类

    根据 handler 能力选择断点续传策略：
    - replay-from-start handler 按 offset 非破坏性读取同一份持久化日志
    - 旧 handler 保留竞争消费与 restore_messages() 兼容语义
    - 通过 has_pending_messages() 判断是否需要创建新的生产者
    - 读到 EOD_CHUNK 时调用 mark_completed() 清理所有队列

    心跳机制：
    - 生产者在数据产生间隔较长时，定期发送心跳消息
    - 消费者按 message handler 的策略检测心跳超时，连续无消息则认为生产者异常

    取消机制（支持多进程）：
    - 进程内取消：使用 threading.Event，同进程内的生产者/消费者可立即感知
    - 跨进程取消：使用 RabbitMQ 队列存储取消信号，任意进程都可设置/检测

    工作流程：
    1. 客户端首次请求时，队列为空，启动生产者线程生产数据
    2. 消费者读取缓存消息；replay 模式下消息始终保留在主队列
    3. 如果客户端断开连接，生产者继续运行直到完成
    4. 客户端重连时，检查队列中是否有数据：
       - replay 模式从当前连接的 offset 继续读取
       - 旧模式先调用 restore_messages() 恢复消息再消费
       - 如果没有数据，启动新的生产者
    5. 读到 EOD_CHUNK 时，调用 mark_completed() 清理队列
    """

    # 进程内取消标志：(thread_id, run_id) -> threading.Event 集合。
    # 同一 Run 允许多个 SSE Consumer，各自退出不会移除其他 Consumer/Producer 的事件。
    _cancel_events: dict[tuple[str, str], set["threading.Event"]] = {}
    _cancel_lock = threading.Lock()

    # 取消后等待 generator 产出 RUN_FINISHED 的宽限时间（秒）
    CANCEL_DRAIN_TIMEOUT = TimeoutConfig.CANCEL_DRAIN_TIMEOUT

    # 生产者结束后延迟清理会话资源的等待时间（秒）。
    # 覆盖最长 60 秒消费者心跳窗口，并为前端重连预留约 30 秒。
    _PRODUCER_CLEANUP_DELAY = 90.0
    # 业务流已发出 [DONE] 且当前无活跃消费者时，保留队列等待前端接管续流的窗口（秒）。
    # 注意：后台 drain（background_only）完成后不会立即清理队列，需保留足够窗口让前端重连后
    # replay 已生产的完整内容；窗口内若有消费者接管则跳过清理。
    _DONE_ORPHAN_CLEANUP_GRACE = 30.0
    _ORPHAN_CLEANUP_POLL_INTERVAL = 0.1
    _HEARTBEAT_TIMEOUT_GRACE = 5.0
    # 后台 schedule 没有前端可接管重连；心跳超时后保留最多 60 秒恢复窗口。
    # 窗口耗尽仅退出异常消费者，producer 后续仍可在 EOD 提交后收敛会话终态。
    _BACKGROUND_HEARTBEAT_RECOVERY_TIMEOUT = 60.0
    _EOD_COMMIT_RECOVERY_TIMEOUT = 15.0
    _HEARTBEAT_TIMEOUT_MESSAGE = "Agent 执行中断：生产者心跳超时，请稍后重试"

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
        # 保留缓存历史供前端在清理窗口内接管续流；清理交由 producer 的延迟清理线程兜底。
        self.defer_cleanup_on_complete = defer_cleanup_on_complete
        self._producer_completion_error: Exception | None = None
        self.run_id: str = ""
        self._cancel_event: threading.Event | None = None
        self._replace_replay_run = False

    @classmethod
    def _check_cancel_status(
        cls,
        thread_id: str,
        message_handler: BaseMessageQueueHandler | None = None,
        run_id: str | None = None,
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
        run_key = run_id or ""
        with cls._cancel_lock:
            events = [
                event
                for (registered_thread_id, registered_run_id), registered_events in cls._cancel_events.items()
                if registered_thread_id == thread_id and (not run_id or registered_run_id == run_key)
                for event in registered_events
            ]
            if any(event.is_set() for event in events):
                return True

        # 2. 慢速路径：检查跨进程取消信号
        if message_handler is None:
            message_handler = message_handler_factory.get()

        try:
            cross_cancelled = (
                message_handler.check_cancel_signal(thread_id, run_id=run_id)
                if run_id
                else message_handler.check_cancel_signal(thread_id)
            )
            if cross_cancelled:
                # 跨进程取消信号存在，同时设置进程内事件（让后续检查更快）
                if set_event_on_cross_process and cancel_event:
                    cancel_event.set()
                return True
        except Exception as e:
            logger.exception(f"Error checking cancel signal for thread_id={thread_id}: {e}")

        return False

    @classmethod
    def is_registered(
        cls,
        thread_id: str,
        message_handler: BaseMessageQueueHandler | None = None,
        run_id: str | None = None,
    ) -> bool:
        """判断流式侧是否已注册，此时调用 cancel 可投递到活跃流。

        - 进程内：``stream()`` 开头已写入 ``_cancel_events``
        - 跨进程：存在活跃消费者（``stream()`` 在注册 cancel 后 ``acquire_consumer``）
        """
        with cls._cancel_lock:
            if any(
                registered_thread_id == thread_id and (not run_id or registered_run_id == run_id)
                for registered_thread_id, registered_run_id in cls._cancel_events
            ):
                return True
        if message_handler is None:
            message_handler = message_handler_factory.get()
        try:
            return bool(message_handler.has_active_consumer(thread_id))
        except Exception:
            logger.exception("Error checking stream registration for thread_id=%s", thread_id)
            return False

    @classmethod
    def cancel(
        cls,
        thread_id: str,
        message_handler: BaseMessageQueueHandler | None = None,
        run_id: str | None = None,
    ) -> bool:
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
            events = [
                event
                for (registered_thread_id, registered_run_id), registered_events in cls._cancel_events.items()
                if registered_thread_id == thread_id and (not run_id or registered_run_id == run_id)
                for event in registered_events
            ]
            for event in events:
                event.set()
            if events:
                result = True

        # 2. 设置跨进程取消信号（通过 RabbitMQ，支持多进程部署）
        if message_handler is None:
            message_handler = message_handler_factory.get()

        try:
            cross_process_result = (
                message_handler.set_cancel_signal(thread_id, run_id=run_id)
                if run_id
                else message_handler.set_cancel_signal(thread_id)
            )
            if cross_process_result:
                result = True
        except Exception as e:
            logger.exception(f"Error setting cross-process cancel signal: {e}")

        return result

    @classmethod
    def is_cancelled(
        cls,
        thread_id: str,
        message_handler: BaseMessageQueueHandler | None = None,
        run_id: str | None = None,
    ) -> bool:
        """检查指定 thread_id 是否已被取消（供 Agent 内部使用）

        Args:
            thread_id: 线程 ID / session_code
            message_handler: 消息处理器，用于检查跨进程取消信号。如果为 None，
                           使用默认的消息处理器

        Returns:
            True 表示已被取消，应该停止
        """
        return cls._check_cancel_status(thread_id, message_handler, run_id=run_id)

    @classmethod
    def has_output(cls, thread_id: str, message_handler: BaseMessageQueueHandler | None = None) -> bool:
        """检查指定 thread_id 的流是否已有输出

        通过 handler 的缓存状态判断生产者是否已经产生输出。

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

    def prepare_run(self, run_id: str) -> "threading.Event":
        """在输出 RUN_STARTED 前建立本轮取消作用域。"""
        self.run_id = run_id
        return self._register_cancel_event(run_id)

    def _register_cancel_event(self, run_id: str | None = None) -> "threading.Event":
        """注册取消事件"""
        if self._cancel_event is not None:
            return self._cancel_event

        if run_id:
            self.run_id = run_id
        event = threading.Event()
        key = (self.thread_id, self.run_id)
        with self._cancel_lock:
            self._cancel_events.setdefault(key, set()).add(event)
        self._cancel_event = event
        return event

    def _unregister_cancel_event(self, event: threading.Event) -> None:
        """取消注册取消事件"""
        key = (self.thread_id, self.run_id)
        with self._cancel_lock:
            registered_events = self._cancel_events.get(key)
            if registered_events is not None:
                registered_events.discard(event)
                if not registered_events:
                    self._cancel_events.pop(key, None)
        if self._cancel_event is event:
            self._cancel_event = None

    def discard_prepared_run(self, event: threading.Event) -> None:
        """在队列消费尚未接管前回收预注册的取消事件。"""
        self._unregister_cancel_event(event)

    @staticmethod
    def _is_done_event_chunk(chunk: Any) -> bool:
        """判断 chunk 是否为 SSE 的业务完成标记。"""
        return isinstance(chunk, str) and chunk.strip() == "data: [DONE]"

    @staticmethod
    def _is_run_finished_event_chunk(chunk: Any) -> bool:
        """判断 chunk 是否为 AG-UI RUN_FINISHED 事件。"""
        if not isinstance(chunk, str) or not chunk.startswith("data:"):
            return False
        try:
            payload = json.loads(chunk.removeprefix("data:").strip())
        except (TypeError, json.JSONDecodeError):
            return False
        return isinstance(payload, dict) and payload.get("type") == EventType.RUN_FINISHED.value

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
            run_id=self.run_id or None,
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
        last_consumer_check = 0.0

        while True:
            try:
                now = time.monotonic()
                if (
                    not supports_replay_from_start
                    or now - last_consumer_check >= self._REPLAY_CONSUMER_HEARTBEAT_INTERVAL
                ):
                    self.message_handler.check_consumer(self.thread_id, consumer_id)
                    last_consumer_check = now
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

    def _clear_cancel_signal_safely(self, error_prefix: str, run_id: str | None = None) -> None:
        """安全清理跨进程取消信号，避免异常打断主流程。"""
        try:
            if run_id:
                self.message_handler.clear_cancel_signal(self.thread_id, run_id=run_id)
            else:
                self.message_handler.clear_cancel_signal(self.thread_id)
        except Exception as e:
            logger.exception(f"{error_prefix}: {e}")

    def _notify_consumer_cancelled_safely(self) -> None:
        """安全发送消费者取消完成通知，避免异常打断主流程。

        在消费者因取消信号退出时调用，通知 stop 接口流已结束。
        """
        try:
            if self.run_id:
                self.message_handler.notify_consumer_cancelled(self.thread_id, run_id=self.run_id)
            else:
                self.message_handler.notify_consumer_cancelled(self.thread_id)
        except Exception as e:
            logger.exception(f"Error sending consumer cancelled notification for thread_id={self.thread_id}: {e}")

    def _should_notify_consumer_cancelled_on_complete(self, cancel_event: threading.Event) -> bool:
        """正常结束时，仅在确实存在 stop/cancel 场景下才发送完成通知。"""
        if cancel_event.is_set():
            return True

        try:
            if (
                self.message_handler.check_cancel_signal(self.thread_id, run_id=self.run_id)
                if self.run_id
                else self.message_handler.check_cancel_signal(self.thread_id)
            ):
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

        if self._is_pending_replay_from_other_run(has_pending):
            # 新输入使用新的 run_id，不应回放上一轮缓存。旧数据要等本轮取得
            # producer 锁后再清理，避免与仍在 flush EOD 的上一轮生产者并发写。
            self._replace_replay_run = True
            return False, False

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

    def _is_pending_replay_from_other_run(self, has_pending: bool) -> bool:
        return bool(
            has_pending
            and self._supports_replay_from_start()
            and self.run_id
            and not self.message_handler.has_active_producer(self.thread_id)
            and not self.message_handler.replay_belongs_to_run(self.thread_id, self.run_id)
        )

    def _recheck_pending_after_waiting_consumer(self, has_pending: bool, attach_only: bool = False) -> bool:
        """队列初判为空时，等待旧消费者退出后再次确认是否有消息。"""
        if has_pending:
            return True

        prev_exited = self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=3.0)
        has_pending = self.message_handler.has_pending_messages(self.thread_id)
        if not attach_only and self._is_pending_replay_from_other_run(has_pending):
            # 等待旧 consumer 期间，上一 run 的 EOD 可能刚写入并留下 replay
            # 日志；新 run 必须创建 producer，不能把这批旧日志当成待恢复数据。
            self._replace_replay_run = True
            return False
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
        event_handler: Callable[[Any], None] | None = None,
        expected_run_id: str | None = None,
        attach_only: bool = False,
    ) -> tuple[threading.Thread | None, bool, bool]:
        """根据队列状态决定启动生产者还是恢复旧消息。"""
        producer_thread: threading.Thread | None = None
        is_resuming = False
        enable_heartbeat_check = False
        supports_replay_from_start = self._supports_replay_from_start()

        if attach_only:
            active_producer = self.message_handler.has_active_producer(self.thread_id)
            if not has_pending and not active_producer:
                raise StreamAttachUnavailableError(f"No active or replayable stream for thread_id={self.thread_id}")
            logger.info(
                "Attach existing stream for thread_id=%s has_pending=%s active_producer=%s",
                self.thread_id,
                has_pending,
                active_producer,
            )
            # attach 永远不获取 producer lock、不迭代业务 generator。即使生产者已退出但
            # 尚有缓存，也开启心跳检查，避免缺少 EOD 的孤儿回放无限等待。
            return producer_thread, True, True

        if not has_pending:
            producer_acquired = self.message_handler.acquire_producer(self.thread_id)
            if not producer_acquired and self._replace_replay_run:
                deadline = time.monotonic() + self.CANCEL_DRAIN_TIMEOUT + 2.0
                while time.monotonic() < deadline and not producer_acquired:
                    time.sleep(0.05)
                    producer_acquired = self.message_handler.acquire_producer(self.thread_id)

            if not producer_acquired:
                if self._replace_replay_run:
                    raise RuntimeError(
                        f"Previous replay run did not release producer lock for thread_id={self.thread_id}"
                    )
                logger.info(
                    "Producer already active for thread_id=%s, consuming existing replay stream",
                    self.thread_id,
                )
                return producer_thread, True, True

            try:
                # clear() 会清理部分 handler 的信号资源。先把已到达的 stop 意图
                # 固化到本次 run 的进程内 Event，避免“先 stop、后 producer 注册”竞态。
                self._is_cancelled(cancel_event)
                self.message_handler.clear(self.thread_id)
                self.message_handler.clear_stopped(self.thread_id)
                if expected_run_id:
                    self.message_handler.bind_replay_run(self.thread_id, expected_run_id)
            except Exception:
                self.message_handler.release_producer(self.thread_id)
                raise

            producer_thread = threading.Thread(
                target=self._run_producer,
                kwargs={
                    "generator": generator,
                    "cancel_event": cancel_event,
                    "on_complete": on_complete,
                    "event_handler": event_handler,
                    "expected_run_id": expected_run_id,
                    "release_producer": True,
                },
                daemon=True,
            )
            producer_thread.start()
            logger.info(f"Started producer for thread_id={self.thread_id}")
            enable_heartbeat_check = True
            return producer_thread, is_resuming, enable_heartbeat_check

        if supports_replay_from_start:
            is_resuming = True
            logger.info(
                "Pending messages exist for thread_id=%s, replaying cached stream from start",
                self.thread_id,
            )
            return producer_thread, is_resuming, enable_heartbeat_check

        self.message_handler.wait_for_previous_consumer(self.thread_id, timeout=3.0)
        restored = self.message_handler.restore_messages(self.thread_id)
        is_resuming = True
        logger.info(
            f"Pending messages exist for thread_id={self.thread_id}, "
            f"restored {restored} cached messages, consuming from start"
        )
        return producer_thread, is_resuming, enable_heartbeat_check

    # ---- L1 观测：consumer 循环内联耗时 WARNING 阈值（秒），仅日志用途 ----
    _CHECK_CONSUMER_SLOW_SEC = 2.0
    _GET_SLOW_SEC = 5.0
    _YIELD_SLOW_SEC = 10.0
    # consumer progress 心跳：每 N 条 yield 或每 M 秒（取先到者）
    _CONSUMER_PROGRESS_EVERY_N = 50
    _CONSUMER_PROGRESS_EVERY_SECONDS = 10.0
    # replay handler 不使用抢占式消费，但仍需低频刷新活跃消费者，避免长会话被清理线程误判为空闲。
    _REPLAY_CONSUMER_HEARTBEAT_INTERVAL = 10.0

    def _emit_terminal_error_events(
        self,
        message: str,
        event_handler: Callable[[Any], None] | None = None,
    ) -> Generator[str, None, None]:
        """输出 AG-UI 错误与结束事件，并同步通知会话事件处理器。"""
        error_event = RunErrorEvent(type=EventType.RUN_ERROR, message=message)
        if event_handler is not None:
            try:
                event_handler(error_event)
            except Exception:
                logger.exception("Error dispatching RUN_ERROR for thread_id=%s", self.thread_id)
        yield EventEncoder().encode(error_event)
        yield emit_run_finished_event(
            thread_id=self.thread_id,
            run_id="error",
            event_handler=event_handler,
        )

    def _build_terminal_cancel_events(self) -> tuple[tuple[Any, str], tuple[Any, str]]:
        """构造标准取消事件；写入队列成功后再派发给会话写入器。"""
        encoder = EventEncoder()
        error_event = RunErrorEvent(type=EventType.RUN_ERROR, message=RunId.CANCELLED_MESSAGE)
        finished_event = RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id=self.thread_id,
            run_id=RunId.CANCELLED,
            outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
        )
        return (error_event, encoder.encode(error_event)), (finished_event, encoder.encode(finished_event))

    def _emit_retryable_heartbeat_timeout(
        self,
        event_handler: Callable[[Any], None] | None = None,
    ) -> Generator[str, None, None]:
        """先输出 RAW 提示，再中断 SSE 让前端按 network error 重连。"""
        retry_event = RawEvent(
            type=EventType.RAW,
            event={
                "type": "error",
                "message": self._HEARTBEAT_TIMEOUT_MESSAGE,
            },
        )
        if event_handler is not None:
            try:
                event_handler(retry_event)
            except Exception:
                logger.exception("Error dispatching retryable RAW event for thread_id=%s", self.thread_id)
        yield EventEncoder().encode(retry_event)

        # 后续增加独立重试事件后，前端无需再依赖 transport/network error。
        raise RetryableHeartbeatTimeoutError(self._HEARTBEAT_TIMEOUT_MESSAGE)

    def _consume_stream_messages(
        self,
        consumer_id: str,
        cancel_event: threading.Event,
        is_resuming: bool,
        enable_heartbeat_check: bool,
        on_complete: Callable[[], None] | None = None,
        producer_thread: threading.Thread | None = None,
        event_handler: Callable[[Any], None] | None = None,
    ) -> Generator[Any, None, str]:
        """消费者循环：读取队列、处理控制消息并向上游产出业务消息。

        纯观测日志（零行为改动）：
        - 入口 / 出口 INFO，`finally` 带 reason / consumed / iter；
        - `check_consumer` / `get` / `yield` 内联耗时度量，超阈值打 WARNING；
        - 每 N 条 yield 或 10s 打 1 条 progress INFO；
        - 最外层 unexpected 异常打 ERROR 后 `raise`。
        """
        consumer_draining = False
        last_message_time = time.time()
        last_message_monotonic = time.monotonic()

        consumer_id_short = consumer_id[:8] if consumer_id else "?"
        loop_iter = 0
        yielded_total = 0
        exit_reason = "unknown"
        last_progress_ts = time.time()
        replay_offset = 0
        supports_replay_from_start = self._supports_replay_from_start()
        heartbeat_timeout = self.message_handler.CONSUMER_HEARTBEAT_TIMEOUT
        heartbeat_grace_deadline: float | None = None
        background_recovery_deadline: float | None = None
        last_consumer_check = 0.0

        logger.info(
            "[MessageHandler] consumer loop enter thread_id=%s consumer_id=%s is_resuming=%s heartbeat_check=%s",
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
                    "[MessageHandler] consumer progress thread_id=%s consumer_id=%s consumed_total=%d iter=%d",
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

                    now = time.monotonic()
                    if (
                        not supports_replay_from_start
                        or now - last_consumer_check >= self._REPLAY_CONSUMER_HEARTBEAT_INTERVAL
                    ):
                        t_check = time.time()
                        self.message_handler.check_consumer(self.thread_id, consumer_id)
                        last_consumer_check = now
                        check_elapsed = time.time() - t_check
                        if check_elapsed > self._CHECK_CONSUMER_SLOW_SEC:
                            logger.warning(
                                "[MessageHandler] check_consumer slow thread_id=%s consumer_id=%s elapsed=%.2fs",
                                self.thread_id,
                                consumer_id_short,
                                check_elapsed,
                            )

                    t_get = time.time()
                    messages, replay_offset = self._get_consumer_messages(timeout=0.5, replay_offset=replay_offset)
                    get_elapsed = time.time() - t_get
                    if get_elapsed > self._GET_SLOW_SEC:
                        logger.warning(
                            "[MessageHandler] get slow thread_id=%s consumer_id=%s elapsed=%.2fs got=%d",
                            self.thread_id,
                            consumer_id_short,
                            get_elapsed,
                            len(messages),
                        )

                    if messages:
                        last_message_time = time.time()
                        last_message_monotonic = time.monotonic()
                        heartbeat_grace_deadline = None
                        background_recovery_deadline = None

                    for item in messages:
                        if item == HEARTBEAT_CHUNK:
                            logger.debug(f"Received heartbeat for thread_id={self.thread_id}")
                            yield _SSE_HEARTBEAT_EVENT
                            yielded_total += 1
                            continue
                        if item == EOD_CHUNK:
                            logger.info(f"[EOD] Consumer received EOD_CHUNK for thread_id={self.thread_id}")
                            completion_error: Exception | None = None
                            if on_complete and not supports_replay_from_start:
                                try:
                                    on_complete()
                                except Exception as exc:
                                    completion_error = exc
                                    logger.exception("on_complete callback error for thread_id=%s", self.thread_id)
                            if not supports_replay_from_start and not self.defer_cleanup_on_complete:
                                self.message_handler.mark_completed(self.thread_id)
                                logger.info(f"Stream completed for thread_id={self.thread_id}")
                            elif self.defer_cleanup_on_complete:
                                # 后台 drain（无 SSE 下游）：不立即清理队列，保留缓存历史供前端接管续流。
                                # 实际清理由 producer 的 _schedule_session_cleanup 在窗口内兜底，
                                # 若窗口内有前端接管消费则跳过清理。
                                logger.info(
                                    f"Stream completed for thread_id={self.thread_id} "
                                    f"(background drain, defer cleanup for frontend takeover)"
                                )
                            else:
                                # supports_replay_from_start 场景：由上层在合适时机统一 mark_completed
                                logger.info(f"Stream completed for thread_id={self.thread_id}")
                            if completion_error is not None:
                                raise completion_error
                            exit_reason = "completed"
                            return exit_reason
                        if item == CANCELLED_CHUNK:
                            self.message_handler.mark_stopped(self.thread_id)
                            logger.info(f"Stream cancelled for thread_id={self.thread_id}, cached content preserved")
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
                                "[MessageHandler] yield slow thread_id=%s consumer_id=%s elapsed=%.2fs yielded_total=%d",
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
                    if (
                        producer_thread is not None
                        and not producer_thread.is_alive()
                        and self._producer_completion_error is not None
                    ):
                        raise self._producer_completion_error
                    time_since_last = time.monotonic() - last_message_monotonic
                    if enable_heartbeat_check and time_since_last > heartbeat_timeout:
                        producer_finished = producer_thread is not None and not producer_thread.is_alive()

                        # producer 仍可能存活时仅给予一次短暂宽限，不重新启动 Agent，
                        # 也不刷新业务执行超时。producer 已结束却未收到 EOD 时按链路异常处理。
                        if not producer_finished and heartbeat_grace_deadline is None:
                            heartbeat_grace_deadline = time.monotonic() + self._HEARTBEAT_TIMEOUT_GRACE
                            logger.warning(
                                "[MessageHandler] producer heartbeat grace started thread_id=%s grace=%.1fs replay_offset=%d",
                                self.thread_id,
                                self._HEARTBEAT_TIMEOUT_GRACE,
                                replay_offset,
                            )
                            continue
                        if heartbeat_grace_deadline is not None and time.monotonic() < heartbeat_grace_deadline:
                            continue

                        if self.defer_cleanup_on_complete:
                            if background_recovery_deadline is None:
                                background_recovery_deadline = (
                                    time.monotonic() + self._BACKGROUND_HEARTBEAT_RECOVERY_TIMEOUT
                                )
                                logger.warning(
                                    "[MessageHandler] background consumer keeps waiting after heartbeat timeout "
                                    "thread_id=%s recovery_timeout=%.1fs replay_offset=%d producer_finished=%s",
                                    self.thread_id,
                                    self._BACKGROUND_HEARTBEAT_RECOVERY_TIMEOUT,
                                    replay_offset,
                                    producer_finished,
                                )
                            if time.monotonic() < background_recovery_deadline:
                                continue

                        logger.error(
                            f"心跳超时 thread_id={self.thread_id}，距上次消息 {time_since_last:.1f}s "
                            f"(last_message_time={last_message_time:.1f}, now={time.time():.1f}) "
                            f"replay_offset={replay_offset} producer_finished={producer_finished}"
                        )
                        yielded_total += 1
                        exit_reason = "heartbeat_timeout"
                        yield from self._emit_retryable_heartbeat_timeout(event_handler=event_handler)
                    continue
                except Exception as exc:
                    # L-5：避免 unexpected 异常被上层 _wrap_streaming_with_status 吞成沉默
                    logger.error(
                        "[MessageHandler] consumer loop unexpected exception thread_id=%s consumer_id=%s "
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
                "[MessageHandler] consumer loop exit thread_id=%s consumer_id=%s reason=%s consumed=%d iter=%d",
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
                logger.info("[MessageHandler] replay session completed and cleaned thread_id=%s", self.thread_id)
        except Exception:
            logger.exception("Error cleaning completed replay session for thread_id=%s", self.thread_id)

    def stream(
        self,
        generator: Generator[Any, None, None],
        on_complete: Callable[[], None] | None = None,
        event_handler: Callable[[Any], None] | None = None,
        expected_run_id: str | None = None,
        cancel_event: threading.Event | None = None,
        attach_only: bool = False,
    ) -> Generator[Any, None, None]:
        """使用队列处理器缓存流式请求

        replay-from-start handler 支持多个消费者各自从会话日志开头 replay；
        旧 handler 仍使用竞争消费语义，新消费者会抢占旧消费者。

        Args:
            generator: 数据生成器
            on_complete: 流完成时的回调函数，用于及时更新 session status 等外部状态。
                producer 将 RUN_FINISHED 入队后立即调用；缺少 RUN_FINISHED 时在 EOD 路径兜底调用。
            event_handler: AG-UI 事件处理器，用于同步记录受控错误和结束状态。
            expected_run_id: 正常 AG-UI 流的 run_id；提供时保证 EOD 前至少输出一次 RUN_FINISHED。
            attach_only: 仅接管/回放已有流，不允许创建新的生产者。

        Yields:
            生成器产生的数据

        """
        if expected_run_id:
            self.run_id = expected_run_id
        self._replace_replay_run = False
        # 注册取消事件（让 cancel() 可以通知生产者和消费者停止）
        cancel_event = cancel_event or self._register_cancel_event(expected_run_id)

        # 注册为当前活跃消费者
        consumer_id: str | None = None
        producer_thread: threading.Thread | None = None
        consumer_exit_reason: str | None = None
        self._producer_completion_error = None

        completion_lock = threading.Lock()
        completion_called = False

        def _on_complete_once() -> None:
            nonlocal completion_called
            with completion_lock:
                if completion_called:
                    return
                completion_called = True
            if on_complete is not None:
                on_complete()

        completion_callback = _on_complete_once if on_complete is not None else None

        try:
            consumer_id = self.message_handler.acquire_consumer(self.thread_id)
            should_consume_stopped, has_pending = self._resolve_stopped_or_pending_state()
            if should_consume_stopped:
                yield from self._consume_stopped_session(consumer_id)
                return

            has_pending = self._recheck_pending_after_waiting_consumer(has_pending, attach_only=attach_only)
            producer_thread, is_resuming, enable_heartbeat_check = self._start_or_resume_stream(
                generator=generator,
                cancel_event=cancel_event,
                has_pending=has_pending,
                on_complete=completion_callback,
                event_handler=event_handler,
                expected_run_id=expected_run_id,
                attach_only=attach_only,
            )
            consumer_exit_reason = yield from self._consume_stream_messages(
                consumer_id=consumer_id,
                cancel_event=cancel_event,
                is_resuming=is_resuming,
                enable_heartbeat_check=enable_heartbeat_check,
                on_complete=completion_callback,
                producer_thread=producer_thread,
                event_handler=event_handler,
            )
        except GeneratorExit:
            # 客户端断开连接时仅释放消费者，缓存消息继续保留供重连 replay。
            logger.info(f"Consumer disconnected for thread_id={self.thread_id}, cached messages preserved")
            raise
        finally:
            self._unregister_cancel_event(cancel_event)
            # 释放消费者（仅当自己仍是活跃消费者时）
            if consumer_id is not None:
                self.message_handler.release_consumer(self.thread_id, consumer_id)
            # 等待生产者线程结束（如果是本次启动的）
            if producer_thread is not None:
                try:
                    producer_thread.join(timeout=self.CANCEL_DRAIN_TIMEOUT + 2.0)
                except Exception as e:
                    logger.exception(f"Error joining producer thread for thread_id={self.thread_id}: {e}")
            if consumer_exit_reason == "completed":
                self._cleanup_replay_session_if_idle()
                # replay cleanup 会删除信号队列；必须在清理之后发送完成通知，
                # 否则 stop 轮询可能错过通知并额外等待到超时。
                if self._should_notify_consumer_cancelled_on_complete(cancel_event):
                    self._notify_consumer_cancelled_safely()
                if self._producer_completion_error is not None:
                    raise self._producer_completion_error

    def _schedule_session_cleanup(self, done_event_seen: bool = False) -> None:
        """生产者完成后延迟清理孤立的会话资源。

        用户断开连接后，如果未在延迟窗口内重连消费数据，队列数据会一直保留到 TTL 过期。
        此方法启动一个守护线程，在延迟后检查队列中是否仍有未消费的数据，
        若有则调用 mark_completed 主动释放资源。
        """
        thread_id = self.thread_id
        handler = self.message_handler
        try:
            if handler.arm_completed_replay_expiry(thread_id):
                logger.info(
                    "[MessageHandler] backend-managed replay expiry armed thread_id=%s done_event_seen=%s",
                    thread_id,
                    done_event_seen,
                )
                return
        except Exception:
            logger.exception(
                "[MessageHandler] failed to arm backend-managed replay expiry; falling back to polling thread_id=%s",
                thread_id,
            )

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
                        and not consumer_ever_seen
                        and fast_cleanup_at is not None
                        and now >= fast_cleanup_at
                    )
                    # 活跃消费者可能仍在回放较大的历史队列，不能在固定 deadline 到达后删除其队列。
                    deadline_hit = now >= deadline and not has_active_consumer
                    if fast_grace_hit or deadline_hit:
                        should_cleanup_now = True
                        trigger_reason = "fast_grace" if fast_grace_hit and not deadline_hit else "deadline"

                    if should_cleanup_now:
                        logger.info(
                            "[MessageHandler] orphan cleanup triggered thread_id=%s elapsed=%.1fs "
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

                    sleep_for = min(poll_interval, deadline - now) if now < deadline else poll_interval
                    time.sleep(sleep_for)
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
        event_handler: Callable[[Any], None] | None = None,
        release_producer: bool = False,
        expected_run_id: str | None = None,
    ) -> None:
        """生产者线程：将生成器产生的消息推送到队列

        即使消费者断开连接，生产者也会继续运行直到完成。
        会定期发送心跳消息，让消费者知道生产者仍然存活。
        cancel_event 被设置后，生产者会输出标准取消终态并关闭底层 generator。
        无法中断的工具调用会先执行到下一次 yield，再由生产者统一结束。
        """
        _producer_start = time.monotonic()
        logger.info(f"[PRODUCER] start thread_id={self.thread_id} thread={threading.current_thread().name}")
        heartbeat_stop_event = threading.Event()
        heartbeat_thread: threading.Thread | None = None
        # 跨进程取消检查计数器（每 N 个 chunk 检查一次，避免频繁访问 RabbitMQ）
        chunk_count = 0
        CROSS_PROCESS_CHECK_INTERVAL = 10  # 每处理 10 个 chunk 检查一次跨进程取消
        last_cross_process_check_time = time.time()
        # 标记是否进入取消终止流程
        draining = False
        done_event_seen = False
        producer_error = False
        run_finished_seen = False
        cancel_error_emitted = False
        cancel_finished_emitted = False

        def _heartbeat_worker() -> None:
            """独立心跳线程：即使 generator 阻塞也保持心跳。"""
            while not heartbeat_stop_event.wait(HEARTBEAT_INTERVAL):
                try:
                    self.message_handler.put(self.thread_id, HEARTBEAT_CHUNK)
                    logger.debug(f"Sent heartbeat for thread_id={self.thread_id}")
                except Exception as e:
                    logger.exception(f"Error sending heartbeat for thread_id={self.thread_id}: {e}")

        def _complete_session() -> None:
            if on_complete is None:
                return
            try:
                on_complete()
            except Exception as completion_error:
                self._producer_completion_error = completion_error
                logger.exception("on_complete callback error in producer for thread_id=%s", self.thread_id)

        def _is_cancel_requested(*, check_cross_process: bool = False) -> bool:
            if cancel_event and cancel_event.is_set():
                return True
            if not check_cross_process:
                return False
            try:
                active_run_id = expected_run_id or self.run_id
                if (
                    self.message_handler.check_cancel_signal(self.thread_id, run_id=active_run_id)
                    if active_run_id
                    else self.message_handler.check_cancel_signal(self.thread_id)
                ):
                    if cancel_event:
                        cancel_event.set()
                    return True
            except Exception as e:
                logger.exception(f"Error checking cross-process cancel signal in producer: {e}")
            return False

        def _emit_cancel_and_complete() -> None:
            nonlocal cancel_error_emitted, cancel_finished_emitted, draining, run_finished_seen
            if cancel_error_emitted and cancel_finished_emitted:
                return
            draining = True
            heartbeat_stop_event.set()
            logger.info("Producer finalizing cancelled stream for thread_id=%s", self.thread_id)
            for event, encoded_event in self._build_terminal_cancel_events():
                is_run_finished = event.type == EventType.RUN_FINISHED
                if (is_run_finished and cancel_finished_emitted) or (not is_run_finished and cancel_error_emitted):
                    continue
                self.message_handler.put(self.thread_id, encoded_event)
                if event_handler is not None:
                    try:
                        event_handler(event)
                    except Exception:
                        logger.exception(
                            "Error dispatching cancel terminal event type=%s thread_id=%s",
                            event.type,
                            self.thread_id,
                        )
                if is_run_finished:
                    cancel_finished_emitted = True
                    run_finished_seen = True
                    _complete_session()
                else:
                    cancel_error_emitted = True

        try:
            heartbeat_thread = threading.Thread(
                target=_heartbeat_worker,
                daemon=True,
                name=f"stream-heartbeat-{self.thread_id[:8]}",
            )
            heartbeat_thread.start()

            # stop 可能早于 producer/consumer 注册；启动时必须保留并消费该取消意图。
            if _is_cancel_requested(check_cross_process=True):
                _emit_cancel_and_complete()
                return

            for chunk in generator:
                chunk_count += 1

                current_time = time.time()
                should_check_cross_process = (
                    chunk_count % CROSS_PROCESS_CHECK_INTERVAL == 0
                    or current_time - last_cross_process_check_time >= HEARTBEAT_INTERVAL
                )
                if should_check_cross_process:
                    last_cross_process_check_time = current_time

                # 在当前 chunk 入队前终止，避免停止后继续向前端发送工具/模型结果。
                if _is_cancel_requested(check_cross_process=should_check_cross_process):
                    _emit_cancel_and_complete()
                    break

                if self._is_done_event_chunk(chunk):
                    done_event_seen = True
                is_run_finished = self._is_run_finished_event_chunk(chunk)
                if is_run_finished:
                    run_finished_seen = True

                self.message_handler.put(self.thread_id, chunk)
                if isinstance(chunk, str) and '"type":"RUN_STARTED"' in chunk:
                    # 初始化帧也由后台 producer 写入。RUN_STARTED 到达后立即提交，
                    # 避免等待批量写入周期，同时保持 MESSAGES_SNAPSHOT 在其之前。
                    self.message_handler.flush(self.thread_id)
                logger.debug(f"Produced chunk for thread_id={self.thread_id}")
                if is_run_finished:
                    _complete_session()
                    logger.info(
                        "[RUN_FINISHED] terminal event queued and session finalized; stopping producer thread_id=%s",
                        self.thread_id,
                    )
                    break
        except GeneratorExit:
            logger.info(f"Generator closed for thread_id={self.thread_id}")
        except Exception as e:
            if _is_cancel_requested(check_cross_process=True):
                logger.info("Producer generator stopped after cancellation for thread_id=%s", self.thread_id)
                _emit_cancel_and_complete()
            else:
                producer_error = True
                logger.exception(f"Producer error for thread_id={self.thread_id}: {e}")
                try:
                    for event in self._emit_terminal_error_events(
                        "Agent 执行异常，请稍后重试",
                        event_handler=event_handler,
                    ):
                        is_run_finished = self._is_run_finished_event_chunk(event)
                        if is_run_finished:
                            run_finished_seen = True
                        self.message_handler.put(self.thread_id, event)
                        if is_run_finished:
                            _complete_session()
                except Exception as encode_err:
                    logger.exception(
                        f"Failed to send terminal error events for thread_id={self.thread_id}: {encode_err}"
                    )
        finally:
            logger.info(
                f"[PRODUCER] finally enter thread_id={self.thread_id} "
                f"producer_error={producer_error} done_event_seen={done_event_seen} "
                f"draining={draining} "
                f"elapsed={time.monotonic() - _producer_start:.1f}s"
            )
            heartbeat_stop_event.set()
            close_generator = getattr(generator, "close", None)
            if callable(close_generator):
                try:
                    close_generator()
                except Exception:
                    logger.exception("Error closing producer generator thread_id=%s", self.thread_id)
            if heartbeat_thread is not None:
                try:
                    heartbeat_thread.join(timeout=HEARTBEAT_INTERVAL + 0.2)
                except Exception as e:
                    logger.exception(f"Error joining heartbeat thread for thread_id={self.thread_id}: {e}")

            try:
                if not producer_error and not run_finished_seen and _is_cancel_requested(check_cross_process=True):
                    # generator 可能在内部检测取消后直接 StopIteration，生产者循环没有机会看到新 chunk。
                    _emit_cancel_and_complete()
                elif expected_run_id and not producer_error and not run_finished_seen:
                    logger.warning(
                        "[RUN_FINISHED] missing from normal producer stream; emitting fallback thread_id=%s run_id=%s",
                        self.thread_id,
                        expected_run_id,
                    )
                    self.message_handler.put(
                        self.thread_id,
                        emit_run_finished_event(
                            thread_id=self.thread_id,
                            run_id=expected_run_id,
                            event_handler=event_handler,
                        ),
                    )
                    _complete_session()

                # 无论是正常结束还是取消，都推送 EOD_CHUNK 让消费者知道流已结束。
                logger.info(
                    f"[EOD] Producer sending EOD_CHUNK for thread_id={self.thread_id} (producer_error={producer_error})"
                )
                eod_commit_event = threading.Event()
                register_eod_commit = getattr(self.message_handler, "register_eod_commit_event", None)
                unregister_eod_commit = getattr(self.message_handler, "unregister_eod_commit_event", None)
                eod_commit_registered = callable(register_eod_commit) and callable(unregister_eod_commit)
                if eod_commit_registered:
                    register_eod_commit(self.thread_id, eod_commit_event)

                try:
                    self.message_handler.put(self.thread_id, EOD_CHUNK)
                    try:
                        self.message_handler.flush(self.thread_id)
                    except Exception as flush_error:
                        if not eod_commit_registered:
                            self._producer_completion_error = flush_error
                            raise
                        logger.warning(
                            "[EOD] synchronous flush failed; waiting for background recovery "
                            "thread_id=%s timeout=%.1fs",
                            self.thread_id,
                            self._EOD_COMMIT_RECOVERY_TIMEOUT,
                            exc_info=True,
                        )
                        if not eod_commit_event.wait(timeout=self._EOD_COMMIT_RECOVERY_TIMEOUT):
                            completion_error = RuntimeError(
                                f"EOD commit did not recover within {self._EOD_COMMIT_RECOVERY_TIMEOUT:.1f}s"
                            )
                            self._producer_completion_error = completion_error
                            raise completion_error from flush_error
                        logger.info("[EOD] background flush recovered thread_id=%s", self.thread_id)
                finally:
                    if eod_commit_registered:
                        unregister_eod_commit(self.thread_id, eod_commit_event)
                logger.info(f"[EOD] Producer EOD_CHUNK sent successfully for thread_id={self.thread_id}")

                # 只有 Producer 确认 EOD 已提交后，才清理自己所属 Run 的取消信号。
                self._clear_cancel_signal_safely(
                    "Error clearing committed cancel signal",
                    run_id=expected_run_id or self.run_id or None,
                )

                # EOD 仅负责消费者结束与队列资源回收；会话终态已在 RUN_FINISHED 入队后回写。
                self._schedule_session_cleanup(done_event_seen=done_event_seen)

                if on_complete and self._supports_replay_from_start():
                    _complete_session()
                if self._producer_completion_error is not None:
                    raise self._producer_completion_error
            finally:
                if release_producer:
                    logger.info(
                        f"[PRODUCER] releasing producer lock thread_id={self.thread_id} "
                        f"elapsed={time.monotonic() - _producer_start:.1f}s"
                    )
                    try:
                        self.message_handler.release_producer(self.thread_id)
                    except Exception as e:
                        logger.exception(f"Error releasing producer for thread_id={self.thread_id}: {e}")

    def _run_producer(self, **kwargs: Any) -> None:
        """线程入口：记录 producer 终结异常，由消费线程统一向调用方传播。"""
        try:
            self._producer(**kwargs)
        except Exception as exc:
            if self._producer_completion_error is None:
                self._producer_completion_error = exc
            logger.exception("Producer finalization failed for thread_id=%s", self.thread_id)
