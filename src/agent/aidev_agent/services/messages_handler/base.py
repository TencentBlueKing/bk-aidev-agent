from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol, runtime_checkable

# 从 constants 模块导入所有常量（统一管理）
from .constants import (
    CANCELLED_CHUNK,
    EOD_CHUNK,
    HEARTBEAT_CHUNK,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    STOPPED_CHUNK,
    QueueTTLConfig,
)

# 重新导出常量，保持向后兼容
__all__ = [
    "EOD_CHUNK",
    "CANCELLED_CHUNK",
    "STOPPED_CHUNK",
    "HEARTBEAT_CHUNK",
    "HEARTBEAT_INTERVAL",
    "HEARTBEAT_TIMEOUT",
    "QueueTTLConfig",
    "ConsumerPreemptedError",
    "StreamCancelledError",
    "RetryableHeartbeatTimeoutError",
    "ConsumerManagementProtocol",
    "BaseMessageQueueHandler",
]


class ConsumerPreemptedError(Exception):
    """当前消费者已被新消费者抢占"""


class StreamCancelledError(Exception):
    """流被用户主动取消（停止会话）"""


class RetryableHeartbeatTimeoutError(RuntimeError):
    """消费者心跳超时，可通过重新消费恢复且不应更新会话终态。"""


@runtime_checkable
class ConsumerManagementProtocol(Protocol):
    """消费者管理协议

    定义消费者抢占管理的统一接口，SingleProcessMixin 和 MultiProcessMixin 都实现此协议。
    使用 Protocol 而非 ABC 是因为 Mixin 类不应强制继承关系。
    """

    def acquire_consumer(self, thread_id: str) -> str:
        """注册新消费者，返回消费者 ID"""
        ...

    def wait_for_previous_consumer(self, thread_id: str, timeout: float = 3.0) -> bool:
        """等待旧消费者完全退出"""
        ...

    def check_consumer(self, thread_id: str, consumer_id: str) -> None:
        """检查当前消费者是否仍是活跃消费者"""
        ...

    def release_consumer(self, thread_id: str, consumer_id: str) -> None:
        """释放消费者"""
        ...


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

    def has_active_consumer(self, thread_id: str) -> bool:
        """检查指定 thread_id 当前是否仍有活跃消费者。

        默认返回 False，具体消息处理器可按其消费者管理机制覆盖。
        """
        return False

    @abstractmethod
    def get_dlq_messages(self, thread_id: str) -> list[Any]:
        """获取死信队列中的所有消息（不移除）

        用于在流被取消时，获取已发送给前端但未回写数据库的完整消息内容。

        Args:
            thread_id: 线程ID

        Returns:
            死信队列中的消息列表（已发送给前端的消息）
        """

    # ================== 可选功能接口 ==================
    # 以下方法提供默认实现，子类可以选择性地覆盖以支持额外功能

    def get_total_count(self, thread_id: str) -> int:
        """获取主队列和死信队列的总消息数量

        默认实现：子类应覆盖此方法。

        Args:
            thread_id: 线程ID

        Returns:
            总消息数量
        """
        return 0

    def is_empty(self, thread_id: str) -> bool:
        """检查指定 thread_id 的队列是否为空（包括主队列和死信队列）

        Args:
            thread_id: 线程ID

        Returns:
            True 表示队列为空，False 表示队列不为空
        """
        return self.get_total_count(thread_id) == 0

    def supports_replay_from_start(self) -> bool:
        """是否支持多个消费者从同一会话日志独立 replay。

        默认沿用旧的主队列 + DLQ 竞争消费模型。
        """
        return False

    def get_messages_since(self, thread_id: str, offset: int, timeout: Optional[float] = None) -> tuple[list[Any], int]:
        """从指定 offset 开始读取消息，且不破坏底层缓存。

        仅支持 replay-from-start 的 handler 需要覆盖该方法。
        """
        raise NotImplementedError("get_messages_since is only available for replay-from-start handlers")

    def acquire_producer(self, thread_id: str) -> bool:
        """尝试获取会话级生产者写入权。

        默认返回 True，保持旧 handler 行为不变。
        """
        return True

    def release_producer(self, thread_id: str) -> None:
        """释放会话级生产者写入权。默认无操作。"""

    def size(self, thread_id: str) -> int:
        """获取主队列中的消息数量（get_cached_count 的别名）

        Args:
            thread_id: 线程ID

        Returns:
            主队列中的消息数量
        """
        return self.get_cached_count(thread_id)

    def get_cached_count(self, thread_id: str) -> int:
        """获取主队列中缓存的消息数量

        默认实现返回 0，子类可覆盖。

        Args:
            thread_id: 线程ID

        Returns:
            缓存的消息数量
        """
        return 0

    # ================== 停止状态管理接口 ==================
    # 以下方法用于支持 "用户点击 Stop 后保留已输出内容" 的功能
    # 子类可以选择性地覆盖以支持此功能

    def mark_stopped(self, thread_id: str) -> None:
        """标记 session 已被用户主动停止

        用户点击 Stop 时调用。标记后，下次进入该 session 时：
        - 只展示 DLQ 中已有的内容
        - 不启动新的生产者

        默认实现为空，子类可覆盖。

        Args:
            thread_id: 线程ID
        """

    def is_stopped(self, thread_id: str) -> bool:
        """检查 session 是否已被用户主动停止

        默认实现返回 False，子类可覆盖。

        Args:
            thread_id: 线程ID

        Returns:
            True 表示已停止，只应展示已有内容，不应启动新生产者
        """
        return False

    def clear_stopped(self, thread_id: str) -> None:
        """清除停止标记

        当用户发起新的输入（重新生成）时调用，清除停止状态。
        默认实现为空，子类可覆盖。

        Args:
            thread_id: 线程ID
        """

    # ================== 跨进程取消信号接口 ==================
    # 以下方法用于支持多进程环境下的取消信号传递（如 RabbitMQ）
    # 默认实现返回 False/空操作，MultiProcessMixin 会覆盖这些方法

    def set_cancel_signal(self, thread_id: str) -> bool:
        """设置跨进程取消信号

        可以从任意进程调用，生产者/消费者会通过 check_cancel_signal() 检测到取消。

        默认实现返回 False（不支持跨进程取消），MultiProcessMixin 会覆盖此方法。

        Args:
            thread_id: 线程ID / session_code

        Returns:
            True 表示成功设置取消信号，False 表示不支持或设置失败
        """
        return False

    def check_cancel_signal(self, thread_id: str) -> bool:
        """检查是否存在取消信号

        用于生产者/消费者定期检查是否需要停止。

        默认实现返回 False（不支持跨进程取消），MultiProcessMixin 会覆盖此方法。

        Args:
            thread_id: 线程ID / session_code

        Returns:
            True 表示存在取消信号，应该停止
        """
        return False

    def clear_cancel_signal(self, thread_id: str) -> None:
        """清除取消信号（在流结束后调用）

        默认实现为空操作，MultiProcessMixin 会覆盖此方法。

        Args:
            thread_id: 线程ID / session_code
        """
