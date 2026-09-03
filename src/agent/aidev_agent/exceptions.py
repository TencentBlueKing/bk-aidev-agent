# -*- coding: utf-8 -*-
import ast
import json
import re
from logging import getLogger
from typing import Any

from mcp.shared.exceptions import McpError

from aidev_agent.enums import StreamEventType

_logger = getLogger(__name__)

_MAX_UNWRAP_DEPTH = 8
_ERROR_CODE_PREFIX = re.compile(r"^Error code:\s*\d+\s*-\s*", re.IGNORECASE)
_MULTIMODAL_MODEL = re.compile(r"(?P<model>.+?) is not a multimodal model", re.IGNORECASE)
_RAW_PAYLOAD_MARKERS = ("Error code:", "{'error'", '{"error"', "'type':", '"type":', "'trace_id'", '"trace_id"')


class AIDevException(Exception):
    ERROR_CODE = "500"
    MESSAGE = "APP异常"

    def __init__(self, *args, message: str | None = None):
        self.message = message or self.MESSAGE
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message})"


class AgentException(AIDevException):
    MESSAGE = "Agent异常"


class AgentDeadlineExceededError(TimeoutError):
    """The configured total Agent/session runtime limit was exhausted."""


def find_mcp_errors(exc):
    if isinstance(exc, McpError):
        _logger.exception(f"MCP error: {exc}")
        yield exc
    elif hasattr(exc, "exceptions"):  # Check if exc has exceptions attribute first
        for sub_exc in exc.exceptions:
            yield from find_mcp_errors(sub_exc)


def _parse_mapping(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    payload = text[start : end + 1]
    for loader in (ast.literal_eval, json.loads):
        try:
            data = loader(payload)
        except (ValueError, SyntaxError, json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _nested_message(data: dict[str, Any]) -> Any:
    error = data.get("error")
    if isinstance(error, dict) and error.get("message") not in (None, ""):
        return error["message"]
    if data.get("message") not in (None, ""):
        return data["message"]
    return None


def _looks_like_raw_payload(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if _ERROR_CODE_PREFIX.search(stripped):
        return True
    return any(marker in stripped for marker in _RAW_PAYLOAD_MARKERS)


def unwrap_error_message(error_string: str, *, depth: int = 0) -> str:
    if not error_string or depth >= _MAX_UNWRAP_DEPTH:
        return (error_string or "").strip()
    data = _parse_mapping(error_string)
    if data is None:
        return error_string.strip()
    nested = _nested_message(data)
    if nested is None:
        return error_string.strip()
    return unwrap_error_message(str(nested), depth=depth + 1)


def extract_error_message(error_string):
    if not error_string or _parse_mapping(error_string) is None:
        return None
    return unwrap_error_message(error_string)


def _friendly_known_error(message: str) -> str | None:
    match = _MULTIMODAL_MODEL.search(message)
    if not match:
        return None
    model = match.group("model").strip().strip("'\"")
    return f"当前模型 {model} 不支持图片或文档输入。请更换支持多模态的模型，或移除附件后再试。"


def streaming_chunk_exception_handling(exception: Exception) -> str:
    message = extract_model_error_message(exception)
    ret = {
        "event": StreamEventType.ERROR.value,
        "code": exception.code if hasattr(exception, "code") else 400,
        "message": message,
    }
    return f"data: {json.dumps(ret)}\n\n"


def extract_model_error_message(exception: Exception) -> str:
    err_msg = exception.message if hasattr(exception, "message") else str(exception)
    if list(find_mcp_errors(exception)):
        return "模型调用异常: MCP调用工具异常"
    unwrapped = unwrap_error_message(str(err_msg or ""))
    if friendly := _friendly_known_error(unwrapped):
        return friendly
    if _looks_like_raw_payload(unwrapped):
        return "模型调用失败"
    return f"模型调用异常: {unwrapped}"
