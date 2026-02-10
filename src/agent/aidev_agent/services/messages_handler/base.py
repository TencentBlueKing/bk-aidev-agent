from abc import ABC, abstractmethod
from typing import Any, Optional

# 流结束标记
EOD_CHUNK = "<END_OF_STREAM>"
# 主动取消标记（生产者被 request_cancel 停止时发送，消费者与 EOD 同样清理队列）
CANCELLED_CHUNK = "<CANCELLED>"
# 心跳标记
HEARTBEAT_CHUNK = "<HEARTBEAT>"
# 心跳发送间隔（秒）
HEARTBEAT_INTERVAL = 5.0
# 心跳超时时间（秒），允许 3 个心跳周期
HEARTBEAT_TIMEOUT = HEARTBEAT_INTERVAL * 3


class ConsumerPreemptedError(Exception):
    """当前消费者已被新消费者抢占"""


class StreamCancelledError(Exception):
    """流被用户主动取消（停止会话）"""


class BaseMessageQueueHandler(ABC):
    """消息队列处理器抽象基类

    纯接口定义，不包含任何具体实现。
    使用 thread_id 作为 key 来管理不同的消息队列。

    消息队列接口：
    - put(): 向主队列添加消息
    - get(): 从主队列获取消息（消费后消息进入死信队列）
    - has_pending_messages(): 检查主队列+死信队列是否有消息
    - restore_messages(): 将死信队列的消息恢复到主队列（断点续传）
    - mark_completed(): 标记流完成并清理所有队列
    - clear(): 清空所有队列
    - flush(): 立即推送缓冲区消息

    消费者管理接口（由 ConsumerManagementMixin 提供默认实现）：
    - acquire_consumer(): 注册新消费者，返回消费者 ID
    - wait_for_previous_consumer(): 等待旧消费者退出
    - check_consumer(): 检查当前消费者是否仍是活跃消费者
    - release_consumer(): 释放消费者

    消息流转：
    1. 生产者 put() -> 主队列
    2. 消费者 get() -> 消息从主队列移动到死信队列
    3. 断点续传 restore_messages() -> 死信队列消息恢复到主队列
    4. 流完成 mark_completed() -> 清空主队列和死信队列
    """

    @abstractmethod
    def put(self, thread_id: str, message: Any) -> None:
        """向指定 thread_id 的队列中添加消息

        Args:
            thread_id: 线程ID
            message: 要添加的消息
        """

    @abstractmethod
    def get(self, thread_id: str, timeout: Optional[float] = None) -> list[Any]:
        """从指定 thread_id 的队列中获取消息

        消息被读取后会移动到死信队列，支持增量读取。

        Args:
            thread_id: 线程ID
            timeout: 超时时间（秒）

        Returns:
            消息列表

        Raises:
            TimeoutError: 超时时抛出
        """

    @abstractmethod
    def has_pending_messages(self, thread_id: str) -> bool:
        """检查是否有未消费的消息（用于判断是否需要创建生产者）

        检查主队列和死信队列是否有消息。

        Args:
            thread_id: 线程ID

        Returns:
            True 表示有未消费的消息，不需要创建新的生产者
            False 表示没有消息，需要创建生产者
        """

    @abstractmethod
    def restore_messages(self, thread_id: str) -> int:
        """将死信队列中的消息恢复到主队列（断点续传）

        消费者重连时调用此方法，将之前消费过的消息恢复到主队列。

        Args:
            thread_id: 线程ID

        Returns:
            恢复的消息数量
        """

    @abstractmethod
    def mark_completed(self, thread_id: str) -> None:
        """标记流已完成并清理所有队列

        消费者在读取到结束标记时调用此方法，清空主队列和死信队列。

        Args:
            thread_id: 线程ID
        """

    @abstractmethod
    def clear(self, thread_id: str) -> None:
        """清空指定 thread_id 的所有队列

        Args:
            thread_id: 线程ID
        """

    @abstractmethod
    def request_cancel(self, thread_id: str) -> None:
        """请求取消指定 thread_id 的流（生产者会在下次轮询时退出并发送结束标记）。

        幂等：多次调用等价于一次。
        """

    def is_cancel_requested(self, thread_id: str) -> bool:
        """检查是否已请求取消该 thread_id 的流。"""
        return False

    @abstractmethod
    def flush(self, thread_id: str) -> None:
        """立即将缓冲区中的消息推送到队列

        对于不使用缓冲区的实现，可以实现为空操作。

        Args:
            thread_id: 线程ID
        """

    @abstractmethod
    def acquire_consumer(self, thread_id: str) -> str:
        """注册新消费者，返回消费者 ID

        同一 thread_id 同一时间只允许一个活跃消费者。

        Args:
            thread_id: 线程ID

        Returns:
            新消费者的唯一 ID
        """

    @abstractmethod
    def wait_for_previous_consumer(self, thread_id: str, timeout: float = 3.0) -> bool:
        """等待旧消费者完全退出

        Args:
            thread_id: 线程ID
            timeout: 最大等待时间（秒）

        Returns:
            True 表示旧消费者已退出，False 表示超时
        """

    @abstractmethod
    def check_consumer(self, thread_id: str, consumer_id: str) -> None:
        """检查当前消费者是否仍是活跃消费者

        Args:
            thread_id: 线程ID
            consumer_id: 消费者 ID

        Raises:
            ConsumerPreemptedError: 当前消费者已被新消费者抢占
        """

    @abstractmethod
    def release_consumer(self, thread_id: str, consumer_id: str) -> None:
        """释放消费者

        Args:
            thread_id: 线程ID
            consumer_id: 消费者 ID
        """

    @abstractmethod
    def get_dlq_messages(self, thread_id: str) -> list[Any]:
        """获取死信队列中的所有消息（不移除）

        用于在流被取消时，获取已发送给前端但未回写数据库的完整消息内容。

        Args:
            thread_id: 线程ID

        Returns:
            死信队列中的消息列表（已发送给前端的消息）
        """
