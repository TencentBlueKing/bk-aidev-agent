import queue
import threading
import time
from logging import getLogger
from typing import Any, ClassVar, Optional

from .base import BaseMessageQueueHandler
from .single_process_mixin import SingleProcessMixin

logger = getLogger(__name__)


class InMemoryQueueMessageHandler(SingleProcessMixin, BaseMessageQueueHandler):
    """基于内存的消息处理器（单进程版本）

    使用 Python 内置的 queue.Queue 作为存储，支持与 RabbitMQ 版本相同的消息流转机制。
    每个 thread_id 对应一个主队列和一个死信队列。

    消息流转机制（模拟 RabbitMQ 的死信队列）：
    - 主队列：存放待消费的消息
    - 死信队列：存放已消费但未确认完成的消息

    工作流程：
    1. 生产者将消息放入主队列
    2. 消费者从主队列获取消息，消息自动进入死信队列
    3. 消费者断开重连时，将死信队列的消息移回主队列，从头消费
    4. 流完成时（mark_completed），清空主队列和死信队列

    特点：
    - 避免每次都全量读取消息（只读取主队列中的新消息）
    - 支持断点续传（从死信队列恢复消息）
    - 线程安全
    - 适用于单进程测试场景
    """

    _instance: Optional["InMemoryQueueMessageHandler"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __new__(cls) -> "InMemoryQueueMessageHandler":
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_queues()
        return cls._instance

    def _init_queues(self):
        """初始化队列存储"""
        SingleProcessMixin.__init__(self)
        # 主队列：thread_id -> queue.Queue
        self._main_queues: dict[str, queue.Queue] = {}
        # 死信队列：thread_id -> list[Any]
        self._dead_letter_queues: dict[str, list[Any]] = {}
        # 队列锁：thread_id -> threading.Lock
        self._queue_locks: dict[str, threading.Lock] = {}
        # 全局锁：用于创建新队列时的同步
        self._global_lock = threading.Lock()

    def _get_or_create_queues(self, thread_id: str) -> tuple[queue.Queue, list[Any], threading.Lock]:
        """获取或创建指定 thread_id 的队列和锁

        Returns:
            (主队列, 死信队列, 队列锁)
        """
        if thread_id not in self._main_queues:
            with self._global_lock:
                if thread_id not in self._main_queues:
                    self._main_queues[thread_id] = queue.Queue()
                    self._dead_letter_queues[thread_id] = []
                    self._queue_locks[thread_id] = threading.Lock()

        return (
            self._main_queues[thread_id],
            self._dead_letter_queues[thread_id],
            self._queue_locks[thread_id],
        )

    # ================== BaseMessageQueueHandler 接口实现 ==================

    def put(self, thread_id: str, message: Any) -> None:
        """向指定 thread_id 的队列中添加消息

        消息会立即添加到主队列中。

        Args:
            thread_id: 线程ID
            message: 要添加的消息
        """
        main_queue, _, _ = self._get_or_create_queues(thread_id)
        main_queue.put(message)
        logger.debug(f"Put message to queue for thread_id={thread_id}")

    def flush(self, thread_id: str) -> None:
        """立即推送缓冲区中的消息（内存版本无需实现）

        内存版本的消息是立即写入的，无需额外的 flush 操作。

        Args:
            thread_id: 线程ID（忽略）
        """

    def get(self, thread_id: str, timeout: Optional[float] = None) -> list[Any]:
        """从指定 thread_id 的队列中获取消息

        增量获取：只获取主队列中的新消息，已读取的消息会移动到死信队列。

        Args:
            thread_id: 线程ID
            timeout: 超时时间（秒）。None 表示无限等待

        Returns:
            消息列表，如果队列为空但已有部分消息则返回已获取的消息

        Raises:
            TimeoutError: 队列为空且超时时抛出
        """
        main_queue, dlq, queue_lock = self._get_or_create_queues(thread_id)
        start_time = time.time()
        messages = []

        def _move_to_dlq(message: Any) -> None:
            """将消息移动到死信队列"""
            with queue_lock:
                dlq.append(message)

        def _get_all_available() -> bool:
            """获取主队列中所有可用的消息

            Returns:
                True 表示获取到至少一条消息
            """
            try:
                # 获取第一条消息
                message = main_queue.get(timeout=remaining_timeout)
                messages.append(message)
                _move_to_dlq(message)
            except queue.Empty:
                return False

            # 继续获取队列中的其他消息（非阻塞）
            while True:
                try:
                    message = main_queue.get_nowait()
                    messages.append(message)
                    _move_to_dlq(message)
                except queue.Empty:
                    break

            return True

        while True:
            # 计算剩余超时时间
            if timeout is not None:
                elapsed = time.time() - start_time
                remaining_timeout = timeout - elapsed
                if remaining_timeout <= 0:
                    if not messages:
                        raise TimeoutError("No message available within timeout")
                    break
            else:
                remaining_timeout = 0.1  # 无超时时使用短超时轮询

            # 尝试获取消息
            if _get_all_available():
                logger.debug(f"Got {len(messages)} messages from queue for thread_id={thread_id}")
                return messages

            # 队列为空，检查是否超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise TimeoutError("No message available within timeout")

        return messages

    def has_pending_messages(self, thread_id: str) -> bool:
        """检查是否有未消费的消息（用于判断是否需要创建生产者）

        检查主队列和死信队列是否有消息。

        Args:
            thread_id: 线程ID

        Returns:
            True 表示有未消费的消息，不需要创建新的生产者
            False 表示没有消息，需要创建生产者
        """
        if thread_id not in self._main_queues:
            return False

        main_queue, dlq, queue_lock = self._get_or_create_queues(thread_id)

        # 检查主队列
        if not main_queue.empty():
            return True

        # 检查死信队列
        with queue_lock:
            if dlq:
                return True

        return False

    def restore_messages(self, thread_id: str) -> int:
        """将死信队列中的消息恢复到主队列（断点续传）

        消费者重连时调用此方法，将之前消费过的消息恢复到主队列，从头开始消费。

        Args:
            thread_id: 线程ID

        Returns:
            恢复的消息数量
        """
        if thread_id not in self._main_queues:
            return 0

        main_queue, dlq, queue_lock = self._get_or_create_queues(thread_id)

        with queue_lock:
            if not dlq:
                return 0

            # 先取出主队列中的所有消息
            main_queue_messages = []
            while not main_queue.empty():
                try:
                    main_queue_messages.append(main_queue.get_nowait())
                except queue.Empty:
                    break

            # 按正确顺序重新放入：先放死信队列的消息，再放主队列的消息
            restored_count = len(dlq)
            for message in dlq:
                main_queue.put(message)
            for message in main_queue_messages:
                main_queue.put(message)

            # 清空死信队列
            dlq.clear()

            logger.info(f"Restored {restored_count} messages from DLQ for thread_id={thread_id}")
            return restored_count

    def mark_completed(self, thread_id: str) -> None:
        """标记流已完成并清理队列

        消费者在读取到结束标记时调用此方法，清空主队列和死信队列中的所有消息。

        Args:
            thread_id: 线程ID
        """
        if thread_id not in self._main_queues:
            return

        main_queue, dlq, queue_lock = self._get_or_create_queues(thread_id)

        # 清空主队列
        while not main_queue.empty():
            try:
                main_queue.get_nowait()
            except queue.Empty:
                break

        # 清空死信队列
        with queue_lock:
            dlq.clear()

        logger.debug(f"Marked completed and cleared queues for thread_id={thread_id}")

    def clear(self, thread_id: str) -> None:
        """清空指定 thread_id 的所有队列（主队列和死信队列）

        Args:
            thread_id: 线程ID
        """
        if thread_id not in self._main_queues:
            return

        main_queue, dlq, queue_lock = self._get_or_create_queues(thread_id)

        # 清空主队列
        while not main_queue.empty():
            try:
                main_queue.get_nowait()
            except queue.Empty:
                break

        # 清空死信队列
        with queue_lock:
            dlq.clear()

        logger.debug(f"Cleared all queues for thread_id={thread_id}")

    def get_cached_count(self, thread_id: str) -> int:
        """获取主队列中的消息数量

        Args:
            thread_id: 线程ID

        Returns:
            主队列中的消息数量
        """
        if thread_id not in self._main_queues:
            return 0

        main_queue, _, _ = self._get_or_create_queues(thread_id)
        return main_queue.qsize()

    def get_total_count(self, thread_id: str) -> int:
        """获取主队列和死信队列的总消息数量

        Args:
            thread_id: 线程ID

        Returns:
            总消息数量
        """
        if thread_id not in self._main_queues:
            return 0

        main_queue, dlq, queue_lock = self._get_or_create_queues(thread_id)

        main_count = main_queue.qsize()
        with queue_lock:
            dlq_count = len(dlq)

        return main_count + dlq_count

    def is_empty(self, thread_id: str) -> bool:
        """检查指定 thread_id 的队列是否为空（包括主队列和死信队列）

        Args:
            thread_id: 线程ID

        Returns:
            True 表示队列为空，False 表示队列不为空
        """
        return self.get_total_count(thread_id) == 0

    def size(self, thread_id: str) -> int:
        """获取主队列中的消息数量

        Args:
            thread_id: 线程ID

        Returns:
            主队列中的消息数量
        """
        return self.get_cached_count(thread_id)

    def list_thread_ids(self) -> list[str]:
        """列出所有 thread_id

        Returns:
            所有 thread_id 的列表
        """
        with self._global_lock:
            return list(self._main_queues.keys())

    def get_dlq_messages(self, thread_id: str) -> list[Any]:
        """获取死信队列中的所有消息（不移除）

        用于在流被取消时，获取已发送给前端但未回写数据库的完整消息内容。

        Args:
            thread_id: 线程ID

        Returns:
            死信队列中的消息列表（已发送给前端的消息）
        """
        if thread_id not in self._main_queues:
            return []

        _, dlq, queue_lock = self._get_or_create_queues(thread_id)

        with queue_lock:
            # 返回副本，避免外部修改
            return list(dlq)
