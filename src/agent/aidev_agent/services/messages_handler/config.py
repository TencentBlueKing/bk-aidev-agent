from typing import Optional

from environs import Env

from aidev_agent.enums import MessageHandlerType

from .constants import EnvVarNames

env = Env()


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
