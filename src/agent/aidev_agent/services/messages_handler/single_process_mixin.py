import threading
import uuid
from logging import getLogger

from .base import ConsumerPreemptedError

logger = getLogger(__name__)


class SingleProcessMixin:
    """单进程消费者抢占管理 Mixin

    提供基于 threading 的单进程消费者抢占管理能力。
    同一 thread_id 同一时间只允许一个活跃消费者，新消费者注册时旧消费者被抢占。

    适用于：单进程部署（如 python manage.py runserver）

    使用方式：
        class MyHandler(SingleProcessMixin, BaseMessageQueueHandler):
            def __init__(self):
                SingleProcessMixin.__init__(self)
                ...
    """

    def __init__(self):
        # 消费者管理：thread_id -> 当前活跃消费者 ID
        self._active_consumers: dict[str, str] = {}
        self._consumer_lock = threading.Lock()
        # 消费者退出事件：thread_id -> Event，新消费者等待旧消费者完全退出
        self._consumer_exit_events: dict[str, threading.Event] = {}

    def acquire_consumer(self, thread_id: str) -> str:
        """注册新消费者，返回消费者 ID

        同一 thread_id 同一时间只允许一个活跃消费者。
        新消费者注册后，旧消费者在下次 check_consumer() 时会检测到被抢占。

        如果已有活跃消费者，会创建一个 Event 等待旧消费者退出。
        调用方应该在 acquire 后调用 wait_for_previous_consumer() 等待旧消费者完全退出。

        Args:
            thread_id: 线程ID

        Returns:
            新消费者的唯一 ID
        """
        consumer_id = uuid.uuid4().hex
        with self._consumer_lock:
            old_consumer = self._active_consumers.get(thread_id)
            self._active_consumers[thread_id] = consumer_id
            if old_consumer:
                # 创建退出事件，让新消费者可以等待旧消费者退出
                self._consumer_exit_events[thread_id] = threading.Event()
                logger.info(
                    f"Consumer preempted for thread_id={thread_id}: old={old_consumer[:8]}, new={consumer_id[:8]}"
                )
        return consumer_id

    def wait_for_previous_consumer(self, thread_id: str, timeout: float = 3.0) -> bool:
        """等待旧消费者完全退出（包括 DLQ restore）

        Args:
            thread_id: 线程ID
            timeout: 最大等待时间（秒）

        Returns:
            True 表示旧消费者已退出，False 表示超时
        """
        with self._consumer_lock:
            event = self._consumer_exit_events.get(thread_id)
        if event is None:
            return True
        result = event.wait(timeout=timeout)
        if not result:
            logger.warning(f"Timeout waiting for previous consumer to exit, thread_id={thread_id}")
        return result

    def check_consumer(self, thread_id: str, consumer_id: str) -> None:
        """检查当前消费者是否仍是活跃消费者

        Args:
            thread_id: 线程ID
            consumer_id: 消费者 ID

        Raises:
            ConsumerPreemptedError: 当前消费者已被新消费者抢占
        """
        with self._consumer_lock:
            active = self._active_consumers.get(thread_id)
            if active and active != consumer_id:
                raise ConsumerPreemptedError(
                    f"Consumer {consumer_id[:8]} preempted by {active[:8]} for thread_id={thread_id}"
                )

    def release_consumer(self, thread_id: str, consumer_id: str) -> None:
        """释放消费者

        如果自己不是当前活跃消费者（被抢占了），将 DLQ 中的消息恢复到主队列，
        然后通知新消费者可以开始消费。

        如果自己仍是当前活跃消费者（正常结束），直接释放。

        Args:
            thread_id: 线程ID
            consumer_id: 消费者 ID
        """
        is_preempted = False
        with self._consumer_lock:
            active = self._active_consumers.get(thread_id)
            if active == consumer_id:
                # 正常结束，释放
                del self._active_consumers[thread_id]
            elif active and active != consumer_id:
                # 被抢占
                is_preempted = True

        if is_preempted:
            # 先获取事件，确保无论如何都会通知新消费者
            with self._consumer_lock:
                event = self._consumer_exit_events.pop(thread_id, None)

            try:
                # 被抢占：将 DLQ 中自己消费过的消息恢复到主队列
                restored = self.restore_messages(thread_id)
                logger.info(
                    f"Preempted consumer {consumer_id[:8]} restored {restored} DLQ messages for thread_id={thread_id}"
                )
            except Exception as e:
                logger.error(f"Failed to restore DLQ messages for consumer {consumer_id[:8]}: {e}")
            finally:
                # 无论恢复消息是否成功，都要通知新消费者可以开始消费
                if event:
                    event.set()
