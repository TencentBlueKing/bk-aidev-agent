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
        type_str = env.str(EnvVarNames.HANDLER_TYPE, "").lower()
        if type_str == MessageHandlerType.RABBITMQ.value:
            return MessageHandlerType.RABBITMQ
        if type_str == MessageHandlerType.INMEMORY.value:
            return MessageHandlerType.INMEMORY
        return None

    @classmethod
    def has_rabbitmq_config(cls) -> bool:
        """检查是否配置了 RabbitMQ"""
        return bool(env.str(EnvVarNames.RABBITMQ_HOST, ""))

    @classmethod
    def resolve_handler_type(cls) -> MessageHandlerType:
        """解析最终使用的处理器类型

        优先级：
        1. 显式配置 MESSAGE_HANDLER_TYPE
        2. 有 RabbitMQ 配置（RABBITMQ_HOST 非空）→ RabbitMQ
        3. 默认 → InMemory
        """
        # 1. 显式配置优先
        explicit = cls.get_explicit_type()
        if explicit:
            return explicit

        # 2. 只要有 RabbitMQ 配置就使用 RabbitMQ
        if cls.has_rabbitmq_config():
            return MessageHandlerType.RABBITMQ

        # 3. 默认使用内存队列
        return MessageHandlerType.INMEMORY
