from dataclasses import dataclass, field
from typing import Any, Optional

from environs import Env

from aidev_agent.enums import MessageHandlerType

from .constants import EnvVarNames

env = Env()


@dataclass(frozen=True)
class RabbitMQStreamConfig:
    connection_kwargs: dict[str, Any] = field(repr=False)
    operation_timeout: float
    shared_group: str
    shards: int
    redis_url: str = field(repr=False)


class MessageHandlerConfig:
    """消息处理器配置"""

    @classmethod
    def get_explicit_type(cls) -> Optional[MessageHandlerType]:
        """获取显式指定的处理器类型"""
        type_str = env.str(EnvVarNames.HANDLER_TYPE, "").strip().lower()
        if not type_str or type_str == MessageHandlerType.AUTO.value:
            return None
        try:
            return MessageHandlerType(type_str)
        except ValueError as exc:
            supported = ", ".join(handler_type.value for handler_type in MessageHandlerType)
            raise RuntimeError(
                f"Invalid {EnvVarNames.HANDLER_TYPE}={type_str!r}; expected one of: {supported}"
            ) from exc

    @classmethod
    def has_rabbitmq_config(cls) -> bool:
        """检查是否配置了 RabbitMQ 主机。"""
        return bool(env.str(EnvVarNames.RABBITMQ_HOST, "").strip())

    @classmethod
    def has_rabbitmq_stream_config(cls) -> bool:
        """检查是否启用 RabbitMQ Stream 数据面。"""
        return bool(env.str(EnvVarNames.RABBITMQ_STREAM_PORT, "").strip())

    @classmethod
    def get_rabbitmq_stream_config(cls) -> RabbitMQStreamConfig:
        group = env.str(EnvVarNames.RABBITMQ_STREAM_SHARED_GROUP, "").strip()
        shards = env.int(EnvVarNames.RABBITMQ_STREAM_SHARED_SHARDS, 1) if group else 1
        if shards < 1:
            raise ValueError(f"{EnvVarNames.RABBITMQ_STREAM_SHARED_SHARDS} must be positive")
        redis_url = env.str(EnvVarNames.REDIS_URL, "").strip() if group else ""
        if group and not redis_url:
            raise ValueError(f"Shared streams require {EnvVarNames.REDIS_URL}")
        connection_kwargs = {
            "host": env.str(EnvVarNames.RABBITMQ_HOST, "localhost"),
            "port": env.int(EnvVarNames.RABBITMQ_STREAM_PORT),
            "username": env.str("RABBITMQ_USER", "guest"),
            "password": env.str("RABBITMQ_PASSWORD", "guest"),
            "vhost": env.str("RABBITMQ_VHOST", "/"),
            "heartbeat": env.int("RABBITMQ_STREAM_HEARTBEAT", 60),
            "max_retries": env.int("RABBITMQ_STREAM_MAX_RETRIES", 3),
            "load_balancer_mode": env.bool("RABBITMQ_STREAM_LB_MODE", True),
        }
        return RabbitMQStreamConfig(
            connection_kwargs=connection_kwargs,
            operation_timeout=env.float("RABBITMQ_STREAM_OPERATION_TIMEOUT", 10.0),
            shared_group=group,
            shards=shards,
            redis_url=redis_url,
        )

    @classmethod
    def has_redis_config(cls) -> bool:
        """检查是否配置了 Redis MessageHandler 专用连接地址。"""
        return bool(env.str(EnvVarNames.REDIS_URL, "").strip())

    @classmethod
    def resolve_handler_type(cls) -> MessageHandlerType:
        """解析最终使用的处理器类型

        优先级：
        1. 显式配置 MESSAGE_HANDLER_TYPE
        2. 有 Redis 专用配置 → Redis
        3. 有 RabbitMQ 主机或 Stream 端口配置 → RabbitMQ
        4. 默认 → InMemory
        """
        # 1. 显式配置优先
        explicit = cls.get_explicit_type()
        if explicit:
            return explicit

        # 2. Redis 使用专用配置，可安全自动选择
        if cls.has_redis_config():
            return MessageHandlerType.REDIS

        # 3. 只要有 RabbitMQ 配置就使用 RabbitMQ
        if cls.has_rabbitmq_config() or cls.has_rabbitmq_stream_config():
            return MessageHandlerType.RABBITMQ

        # 4. 默认使用内存队列
        return MessageHandlerType.INMEMORY
