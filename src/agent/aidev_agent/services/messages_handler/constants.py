"""消息处理器常量定义模块

统一管理 messages_handler 模块中所有的常量，包括：
- 流控制标记（Stream Control Markers）
- 心跳配置（Heartbeat Configuration）
- 队列 TTL 配置（Queue TTL Configuration）
- 队列名称前缀（Queue Name Prefixes）
- 超时配置（Timeout Configuration）
"""

import os

# 用于标识流的各种状态变化


class StreamMarkers:
    """流控制标记常量"""

    # 流结束标记（正常完成）
    EOD = "<END_OF_STREAM>"
    # 主动取消标记（生产者被 request_cancel 停止时发送）
    CANCELLED = "<CANCELLED>"
    # 已停止标记（用户点击停止后，标记 session 已停止）
    STOPPED = "<STOPPED>"
    # 心跳标记
    HEARTBEAT = "<HEARTBEAT>"


# 向后兼容的常量别名
EOD_CHUNK = StreamMarkers.EOD
CANCELLED_CHUNK = StreamMarkers.CANCELLED
STOPPED_CHUNK = StreamMarkers.STOPPED
HEARTBEAT_CHUNK = StreamMarkers.HEARTBEAT


class HeartbeatConfig:
    """心跳机制配置"""

    # 心跳发送间隔（秒）
    INTERVAL = 5.0
    # 心跳超时时间（秒），允许 3 个心跳周期
    TIMEOUT = INTERVAL * 3


# 向后兼容的常量别名
HEARTBEAT_INTERVAL = HeartbeatConfig.INTERVAL
HEARTBEAT_TIMEOUT = HeartbeatConfig.TIMEOUT


class QueueTTLConfig:
    """队列 TTL 配置常量

    统一管理所有消息队列相关的 TTL（生存时间）配置，
    避免在多个文件中重复定义，便于统一调整。
    """

    # 队列生命周期（毫秒），默认 1 小时后自动删除，可通过环境变量 QUEUE_EXPIRE_SECONDS 配置（单位：秒）
    QUEUE_EXPIRE_MS = int(os.environ.get("QUEUE_EXPIRE_SECONDS", 3600)) * 1000

    # 取消信号的 TTL（毫秒）：30 秒后自动过期
    CANCEL_SIGNAL_TTL_MS = 30000

    # 消费者取消完成通知的 TTL（毫秒）：30 秒后自动过期
    CANCELLED_SIGNAL_TTL_MS = 30000

    # RabbitMQ 消费者退出通知 5 秒后自动过期
    CONSUMER_EXIT_MSG_TTL_MS = 5000

    # 停止状态信号的 TTL（毫秒）：10 分钟后自动过期
    STOPPED_SIGNAL_TTL_MS = 600000

    # 等待旧消费者退出的轮询间隔（秒）
    WAIT_POLL_INTERVAL = 0.2


class QueueNamePrefixes:
    """RabbitMQ 队列名称前缀

    统一管理所有队列的命名约定，便于识别和管理。
    """

    # 消息队列前缀
    MESSAGE_QUEUE = "aidev_agent.thread."
    # 死信队列前缀
    DEAD_LETTER_QUEUE = "aidev_agent.dlq."
    # 取消请求队列前缀
    CANCEL_REQUEST = "aidev_agent.cancel."
    # 消费者控制队列前缀
    CONSUMER_CONTROL = "aidev_agent.consumer."
    # 消费者退出通知队列前缀
    CONSUMER_EXIT = "aidev_agent.consumer_exit."
    # 取消信号队列前缀
    CANCEL_SIGNAL = "aidev_agent.cancel."
    # 停止状态队列前缀（标记 session 已被用户 stop）
    STOPPED_SIGNAL = "aidev_agent.stopped."


class TimeoutConfig:
    """超时配置常量"""

    # 取消后等待 generator 产出 RUN_FINISHED 的宽限时间（秒）
    CANCEL_DRAIN_TIMEOUT = 3.0

    # 获取 RabbitMQ 连接的超时时间（秒）
    CONNECTION_TIMEOUT = 10.0

    # stop 接口等待 SSE 流真正结束的超时时间（秒）
    # 正常情况下只需几百毫秒，超时则降级为当前行为
    STOP_WAIT_STREAM_FINISH_TIMEOUT = 8.0


class ConnectionPoolConfig:
    """RabbitMQ 连接池配置"""

    # 默认连接池大小
    DEFAULT_POOL_SIZE = 5

    # 心跳间隔（秒）
    HEARTBEAT_INTERVAL = 60

    # 阻塞超时（秒）
    BLOCKED_CONNECTION_TIMEOUT = 300


class EnvVarNames:
    """环境变量名称常量
    统一管理消息处理器相关的环境变量名称，
    便于文档化和避免拼写错误。
    """

    # 消息处理器类型（inmemory / rabbitmq / redis）
    HANDLER_TYPE = "MESSAGE_HANDLER_TYPE"
    # RabbitMQ 主机地址
    RABBITMQ_HOST = "RABBITMQ_HOST"
    # RabbitMQ Stream 协议端口；配置后 RabbitMQ handler 切换到 Stream 数据面
    RABBITMQ_STREAM_PORT = "RABBITMQ_STREAM_PORT"
    # Redis MessageHandler 专用配置，避免误用业务缓存 REDIS_* 环境变量
    REDIS_URL = "MESSAGE_REDIS_URL"
    REDIS_SOCKET_TIMEOUT = "MESSAGE_REDIS_SOCKET_TIMEOUT"
    REDIS_CONNECT_TIMEOUT = "MESSAGE_REDIS_CONNECT_TIMEOUT"
    REDIS_PRODUCER_LOCK_TTL_SECONDS = "MESSAGE_REDIS_PRODUCER_LOCK_TTL_SECONDS"
    REDIS_PRODUCER_LOCK_RENEW_INTERVAL = "MESSAGE_REDIS_PRODUCER_LOCK_RENEW_INTERVAL"
    REDIS_CONSUMER_STALE_SECONDS = "MESSAGE_REDIS_CONSUMER_STALE_SECONDS"
    REDIS_COMPLETED_STREAM_TTL_SECONDS = "MESSAGE_REDIS_COMPLETED_STREAM_TTL_SECONDS"
    # 队列过期时间（秒），默认 3600（1 小时）
    QUEUE_EXPIRE_SECONDS = "QUEUE_EXPIRE_SECONDS"
