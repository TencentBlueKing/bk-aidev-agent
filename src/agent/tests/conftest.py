import logging
import os
import sys
from pathlib import Path


def pytest_ignore_collect(collection_path: Path, path, config):
    """如果 opentelemetry 未安装，忽略 tests/packages/opentelemetry 目录。

    conftest 中的 allow_module_level=True skip 会向父目录传播导致整个 session 被跳过，
    因此改为在此处用 pytest_ignore_collect 控制。
    """
    if collection_path.name == "opentelemetry":
        try:
            import opentelemetry  # noqa: F401
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter  # noqa: F401
            from opentelemetry.sdk._logs import LogRecord  # noqa: F401
        except ImportError:
            return True
    return None


def pytest_configure(config):
    """在测试收集前强制使用 InMemory 消息处理器，避免连接 RabbitMQ"""
    os.environ["MESSAGE_HANDLER_TYPE"] = "inmemory"


try:
    from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel  # type: ignore
except ModuleNotFoundError:
    ChatModel = None
try:
    from loguru import logger  # type: ignore
except ModuleNotFoundError:
    logger = None


class InterceptHandler(logging.Handler):
    """Intercept standard logging messages toward loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # If loguru isn't installed, do nothing (stdlib logging will handle it)
        if logger is None:
            return

        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Configure loguru to show DEBUG logs in pytest (if available)
if logger is not None:
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        colorize=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}",
    )
    logger.add("test.log", rotation="100 MB", retention=3)

    # Intercept standard logging and route to loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
