"""消息队列处理器工厂

根据运行环境自动选择合适的消息处理器：
- 单进程模式：使用 InMemoryQueueMessageHandler（内存队列，简单高效）
- 多进程模式：使用 RabbitMQ 或 Redis Streams（支持跨进程通信、独立回放）
"""

import logging

from aidev_agent.enums import MessageHandlerType
from aidev_agent.utils.factory import SingletonFactory

from .base import BaseMessageQueueHandler
from .config import MessageHandlerConfig
from .constants import EnvVarNames
from .in_memory import InMemoryQueueMessageHandler
from .rabbitmq import RabbitMQMessageHandler
from .rabbitmq_stream import RabbitMQStreamMessageHandler
from .redis import RedisMessageHandler

logger = logging.getLogger(__name__)


def _create_handler(handler_type: MessageHandlerType) -> BaseMessageQueueHandler:
    """根据类型创建消息处理器"""
    if handler_type == MessageHandlerType.RABBITMQ:
        if MessageHandlerConfig.has_rabbitmq_stream_config():
            if not MessageHandlerConfig.has_rabbitmq_config():
                raise RuntimeError(
                    f"RabbitMQ Stream handler requires {EnvVarNames.RABBITMQ_HOST} and "
                    f"{EnvVarNames.RABBITMQ_STREAM_PORT}"
                )
            return RabbitMQStreamMessageHandler()
        if not MessageHandlerConfig.has_rabbitmq_config():
            logger.warning("RabbitMQ handler requested but RABBITMQ_HOST not configured, falling back to InMemory")
            return InMemoryQueueMessageHandler()
        return RabbitMQMessageHandler()

    if handler_type == MessageHandlerType.REDIS:
        if not MessageHandlerConfig.has_redis_config():
            raise RuntimeError(f"Redis handler requires {EnvVarNames.REDIS_URL}")
        return RedisMessageHandler()

    return InMemoryQueueMessageHandler()


def _init_factory() -> SingletonFactory[str, BaseMessageQueueHandler]:
    """初始化消息处理器工厂"""
    # 解析使用哪种处理器
    handler_type = MessageHandlerConfig.resolve_handler_type()
    default_handler = _create_handler(handler_type)

    logger.info(
        "Message handler initialized: type=%s, rabbitmq_configured=%s, redis_configured=%s",
        handler_type.value,
        MessageHandlerConfig.has_rabbitmq_config(),
        MessageHandlerConfig.has_redis_config(),
    )

    # 创建工厂
    factory: SingletonFactory[str, BaseMessageQueueHandler] = SingletonFactory(
        "message_handler", defaults=default_handler
    )

    # 只初始化选中的外部 backend，避免未使用的连接配置把进程启动与另一套中间件耦合。
    in_memory_handler = (
        default_handler if handler_type == MessageHandlerType.INMEMORY else InMemoryQueueMessageHandler()
    )
    factory.register(MessageHandlerType.INMEMORY.value, in_memory_handler)
    if handler_type != MessageHandlerType.INMEMORY:
        factory.register(handler_type.value, default_handler)

    return factory


# 导出的工厂实例
message_handler_factory = _init_factory()
