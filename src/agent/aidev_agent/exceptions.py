# -*- coding: utf-8 -*-
import json

from mcp.shared.exceptions import McpError

from aidev_agent.enums import StreamEventType


class AIDevException(Exception):
    ERROR_CODE = "500"
    MESSAGE = "APP异常"

    def __init__(self, *args, message: str | None = None):
        self.message = message or self.MESSAGE

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message})"


class AgentException(AIDevException):
    MESSAGE = "Agent异常"


def find_mcp_errors(exc):
    if isinstance(exc, McpError):
        yield exc
    elif hasattr(exc, "exceptions"):  # Check if exc has exceptions attribute first
        for sub_exc in exc.exceptions:
            yield from find_mcp_errors(sub_exc)


def streaming_chunk_exception_handling(exception: Exception) -> str:
    err_msg = exception.message if hasattr(exception, "message") else str(exception)
    mcp_errors = list(find_mcp_errors(exception))
    if mcp_errors:
        err_msg = "MCP调用工具异常"
    ret = {
        "event": StreamEventType.ERROR.value,
        "code": exception.code if hasattr(exception, "code") else 400,
        "message": f"模型调用异常: {err_msg}",
    }
    return f"data: {json.dumps(ret)}\n\n"
