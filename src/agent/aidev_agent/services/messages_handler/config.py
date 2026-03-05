from typing import Optional

from environs import Env

from aidev_agent.enums import MessageHandlerType

env = Env()


class MessageHandlerConfig:
    """消息处理器配置"""

    # 环境变量名称
    ENV_HANDLER_TYPE = "MESSAGE_HANDLER_TYPE"
    ENV_GUNICORN_WORKERS = "GUNICORN_WORKERS"
    ENV_WEB_CONCURRENCY = "WEB_CONCURRENCY"
    ENV_MULTI_PROCESS_MODE = "MULTI_PROCESS_MODE"
    ENV_RABBITMQ_HOST = "RABBITMQ_HOST"

    @classmethod
    def get_explicit_type(cls) -> Optional[MessageHandlerType]:
        """获取显式指定的处理器类型"""
        type_str = env.str(cls.ENV_HANDLER_TYPE, "").lower()
        if type_str == MessageHandlerType.RABBITMQ.value:
            return MessageHandlerType.RABBITMQ
        if type_str == MessageHandlerType.INMEMORY.value:
            return MessageHandlerType.INMEMORY
        return None

    @classmethod
    def has_rabbitmq_config(cls) -> bool:
        """检查是否配置了 RabbitMQ"""
        return bool(env.str(cls.ENV_RABBITMQ_HOST, ""))

    @classmethod
    def is_multiprocess_mode(cls) -> bool:
        """检测是否运行在多进程模式

        检测方式（按优先级）：
        1. GUNICORN_WORKERS > 1
        2. WEB_CONCURRENCY > 1
        3. MULTI_PROCESS_MODE = true/1/yes
        4. uWSGI numproc > 1
        """
        # Gunicorn workers
        gunicorn_workers = env.int(cls.ENV_GUNICORN_WORKERS, 1)
        if gunicorn_workers > 1:
            return True

        # WEB_CONCURRENCY（通用 worker 数量配置）
        web_concurrency = env.int(cls.ENV_WEB_CONCURRENCY, 1)
        if web_concurrency > 1:
            return True

        # 显式多进程标志
        try:
            if env.bool(cls.ENV_MULTI_PROCESS_MODE, False):
                return True
        except (ValueError, TypeError):
            return False

        # uWSGI 检测
        try:
            import uwsgi

            if uwsgi.numproc > 1:
                return True
        except ImportError:
            pass

        return False

    @classmethod
    def resolve_handler_type(cls) -> MessageHandlerType:
        """解析最终使用的处理器类型

        优先级：
        1. 显式配置 MESSAGE_HANDLER_TYPE
        2. 多进程模式 + 有 RabbitMQ 配置 → RabbitMQ
        3. 默认 → InMemory
        """
        # 1. 显式配置优先
        explicit = cls.get_explicit_type()
        if explicit:
            return explicit

        # 2. 自动检测：多进程 + RabbitMQ 配置
        if cls.is_multiprocess_mode() and cls.has_rabbitmq_config():
            return MessageHandlerType.RABBITMQ

        # 3. 默认使用内存队列
        return MessageHandlerType.INMEMORY
