from abc import ABC, abstractmethod
from typing import Any, ClassVar, Optional, Protocol, runtime_checkable

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
    "StreamAttachUnavailableError",
    "ConsumerManagementProtocol",
    "BaseMessageQueueHandler",
]


class ConsumerPreemptedError(Exception):
    """当前消费者已被新消费者抢占"""


class StreamCancelledError(Exception):
    """流被用户主动取消（停止会话）"""


class RetryableHeartbeatTimeoutError(RuntimeError):
    """消费者心跳超时，可通过重新消费恢复且不应更新会话终态。"""


class StreamAttachUnavailableError(RuntimeError):
    """attach 请求找不到可回放消息或活跃生产者，不允许隐式创建新生产者。"""


@runtime_checkable
class ConsumerManagementProtocol(Protocol):
    """消费者管理协议

    定义消费者登记的最小结构接口；竞争消费可以实现抢占语义，replay backend
    可以实现多消费者并存。使用 Protocol 避免强制具体 Mixin 继承关系。
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

    核心契约只约束生产、生命周期和消费者登记；读取按能力分为两种模式：

    - 旧竞争消费：``get()`` + ``restore_messages()``，目前仅 InMemory 使用；
    - 非破坏性回放：``get_messages_since()`` + offset，RabbitMQ / Redis 使用。

    后端通过 ``supports_replay_from_start()`` 声明读取能力。旧模式方法保留默认
    实现用于兼容，但不再强迫 replay backend 提供无意义的占位实现。
    """

    CONSUMER_HEARTBEAT_TIMEOUT: ClassVar[float] = HEARTBEAT_TIMEOUT

    @abstractmethod
    def put(self, thread_id: str, message: Any) -> None:
        """向指定 thread_id 的队列中添加消息

        Args:
            thread_id: 线程ID
            message: 要添加的消息
        """

    def get(self, thread_id: str, timeout: Optional[float] = None) -> list[Any]:
        """竞争消费模式下读取消息；replay backend 应使用 get_messages_since。"""

        raise NotImplementedError("get is only available for competing-consumer handlers")

    @abstractmethod
    def has_pending_messages(self, thread_id: str) -> bool:
        """检查是否已有可消费或可回放的消息（用于判断是否需要创建生产者）

        Args:
            thread_id: 线程ID

        Returns:
            True 表示有未消费的消息，不需要创建新的生产者
            False 表示没有消息，需要创建生产者
        """

    def restore_messages(self, thread_id: str) -> int:
        """恢复竞争消费模式已读取的消息；replay backend 默认无需处理。"""
        return 0

    @abstractmethod
    def mark_completed(self, thread_id: str) -> None:
        """标记流已完成，并按 backend 的 replay 窗口策略清理或设置过期时间。

        Args:
            thread_id: 线程ID
        """

    @abstractmethod
    def clear(self, thread_id: str) -> None:
        """清空指定 thread_id 的所有队列

        Args:
            thread_id: 线程ID
        """

    def request_cancel(self, thread_id: str) -> None:
        """兼容旧调用：设置 session 级取消信号。

        幂等：多次调用等价于一次。
        """
        self.set_cancel_signal(thread_id)

    def is_cancel_requested(self, thread_id: str) -> bool:
        """兼容旧调用：非破坏性检查 session 级取消信号。"""
        return self.check_cancel_signal(thread_id)

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

        竞争消费 backend 可抢占旧消费者；replay backend 允许多个消费者并存。

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

    def get_dlq_messages(self, thread_id: str) -> list[Any]:
        """返回竞争消费模式的已读缓存；replay backend 不使用 DLQ。"""
        return []

    # ================== 可选功能接口 ==================
    # 以下方法提供默认实现，子类可以选择性地覆盖以支持额外功能

    def get_total_count(self, thread_id: str) -> int:
        """获取该会话当前缓存的逻辑消息总数。

        默认与 ``get_cached_count()`` 一致；包含额外已读缓存的竞争消费实现可覆盖。

        Args:
            thread_id: 线程ID

        Returns:
            总消息数量
        """
        return self.get_cached_count(thread_id)

    def is_empty(self, thread_id: str) -> bool:
        """检查指定 thread_id 是否没有缓存消息。

        Args:
            thread_id: 线程ID

        Returns:
            True 表示队列为空，False 表示队列不为空
        """
        return self.get_total_count(thread_id) == 0

    def supports_replay_from_start(self) -> bool:
        """是否支持多个消费者从同一会话日志独立 replay。

        默认沿用旧竞争消费模型。
        """
        return False

    def bind_replay_run(self, thread_id: str, run_id: str) -> None:
        """将当前回放日志绑定到 run；非 replay handler 默认无需处理。"""

    def replay_belongs_to_run(self, thread_id: str, run_id: str) -> bool:
        """判断当前回放日志是否属于指定 run；默认保持旧 handler 的 session 级语义。"""
        return True

    def arm_completed_replay_expiry(self, thread_id: str) -> bool:
        """为已完成的回放日志启用 backend 托管过期。

        返回 ``True`` 表示 backend 已负责后续回收，调用方无需启动轮询清理线程。
        默认返回 ``False``，保留不具备原生 TTL 能力的 handler 现有行为。
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

    def has_active_producer(self, thread_id: str) -> bool:
        """是否存在仍持有写入权的生产者。默认不提供跨进程判断。"""
        return False

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
        - 只展示缓存中已有的内容
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
    # 以下方法用于支持跨线程或跨进程取消信号传递。
    # 默认实现返回 False/空操作，具体 backend 按需覆盖。

    def set_cancel_signal(self, thread_id: str, run_id: str | None = None) -> bool:
        """设置跨进程取消信号

        可以从任意进程调用，生产者/消费者会通过 check_cancel_signal() 检测到取消。

        默认实现返回 False（不支持共享取消信号）。

        Args:
            thread_id: 线程ID / session_code
            run_id: 本轮运行 ID；为空时保留旧版 session 级取消语义

        Returns:
            True 表示成功设置取消信号，False 表示不支持或设置失败
        """
        return False

    def check_cancel_signal(self, thread_id: str, run_id: str | None = None) -> bool:
        """检查是否存在取消信号

        用于生产者/消费者定期检查是否需要停止。

        默认实现返回 False（不支持共享取消信号）。

        Args:
            thread_id: 线程ID / session_code
            run_id: 本轮运行 ID；非空时只匹配同一轮取消信号

        Returns:
            True 表示存在取消信号，应该停止
        """
        return False

    def clear_cancel_signal(self, thread_id: str, run_id: str | None = None) -> None:
        """清除取消信号（在流结束后调用）

        默认实现为空操作。

        Args:
            thread_id: 线程ID / session_code
            run_id: 本轮运行 ID；非空时只清理同一轮取消信号
        """

    def notify_consumer_cancelled(self, thread_id: str, run_id: str | None = None) -> bool:
        """通知 stop 调用方消费者已经退出；不支持共享通知的实现返回 False。"""
        return False

    def wait_for_consumer_cancelled(
        self,
        thread_id: str,
        timeout: float = 3.0,
        run_id: str | None = None,
    ) -> bool:
        """等待消费者退出通知；不支持共享通知的实现返回 False。"""
        return False

    def clear_cancelled_signal(self, thread_id: str, run_id: str | None = None) -> None:
        """清除消费者退出通知；默认无操作。"""
