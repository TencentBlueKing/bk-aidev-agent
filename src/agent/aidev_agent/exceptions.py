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


_HTTP_STATUS_MIN = 100
_HTTP_STATUS_MAX = 599


class AIDevException(Exception):
    ERROR_CODE = "500"
    MESSAGE = "APP异常"

    def __init__(
        self,
        *args,
        message: str | None = None,
        status_code: int | None = None,
        code: Any = None,
        code_name: str | None = None,
    ):
        self.message = message or self.MESSAGE
        self.status_code = status_code
        self.code = code
        self.code_name = code_name
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(message={self.message!r}, "
            f"status_code={self.status_code!r}, code={self.code!r}, code_name={self.code_name!r})"
        )


class AgentException(AIDevException):
    MESSAGE = "Agent异常"

    @classmethod
    def from_exception(cls, exc: BaseException, *, message: str | None = None) -> "AgentException":
        status_code, code, code_name = extract_exception_status_fields(exc)
        return cls(
            message=message or (str(exc) or cls.MESSAGE),
            status_code=status_code,
            code=code,
            code_name=code_name,
        )


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


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _http_status(value: Any) -> int | None:
    number = _as_int(value)
    if number is None or not (_HTTP_STATUS_MIN <= number <= _HTTP_STATUS_MAX):
        return None
    return number


def _as_code_name(value: Any) -> str | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _is_business_code(value: Any) -> bool:
    number = _as_int(value)
    return number is not None and _http_status(number) is None


def _prefer_code(current: Any, incoming: Any) -> Any:
    if incoming in (None, ""):
        return current
    if current in (None, ""):
        return incoming
    if _is_business_code(incoming) and not _is_business_code(current):
        return incoming
    return current


def _mapping_candidates(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    error = data.get("error")
    return [error, data] if isinstance(error, dict) else [data]


def _merge_status_fields(
    data: Any,
    status_code: int | None,
    code: Any,
    code_name: str | None,
) -> tuple[int | None, Any, str | None]:
    for src in _mapping_candidates(data):
        status_code = status_code or _http_status(
            src["status_code"] if src.get("status_code") is not None else src.get("status")
        )
        code = _prefer_code(code, src.get("code"))
        code_name = code_name or _as_code_name(src.get("code_name"))
    return status_code, code, code_name


def _response_mapping(response: Any) -> dict[str, Any] | None:
    if response is None:
        return None
    json_loader = getattr(response, "json", None)
    if callable(json_loader):
        try:
            data = json_loader()
        except Exception:
            data = None
        if isinstance(data, dict):
            return data
    text = getattr(response, "text", None)
    if text is None:
        content = getattr(response, "content", None)
        text = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else content
    return _parse_mapping(text) if isinstance(text, str) else None


def extract_exception_status_fields(exc: Any) -> tuple[int | None, Any, str | None]:
    """从异常链提取 HTTP status_code 与 body 中的 code / code_name。"""
    status_code: int | None = None
    code: Any = None
    code_name: str | None = None
    seen: set[int] = set()
    stack: list[Any] = [exc] if exc is not None else []
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        status_code = status_code or _http_status(getattr(current, "status_code", None))
        code = _prefer_code(code, getattr(current, "code", None))
        code_name = code_name or _as_code_name(getattr(current, "code_name", None))
        response = getattr(current, "response", None)
        if response is not None:
            status_code = status_code or _http_status(getattr(response, "status_code", None))
            status_code, code, code_name = _merge_status_fields(
                _response_mapping(response), status_code, code, code_name
            )
        status_code, code, code_name = _merge_status_fields(
            getattr(current, "body", None), status_code, code, code_name
        )
        status_code, code, code_name = _merge_status_fields(
            _parse_mapping(str(getattr(current, "message", current))), status_code, code, code_name
        )
        if getattr(current, "__cause__", None) is not None:
            stack.append(current.__cause__)
        elif getattr(current, "__context__", None) is not None:
            stack.append(current.__context__)
        nested_errors = getattr(current, "exceptions", None)
        if isinstance(nested_errors, (list, tuple)):
            stack.extend(item for item in nested_errors if item is not None)
    return status_code, code, code_name


def _friendly_known_error(message: str) -> str | None:
    match = _MULTIMODAL_MODEL.search(message)
    if not match:
        return None
    model = match.group("model").strip().strip("'\"")
    return f"当前模型 {model} 不支持图片或文档输入。请更换支持多模态的模型，或移除附件后再试。"


def streaming_chunk_exception_handling(exception: Exception) -> str:
    message = extract_model_error_message(exception)
    status_code, code, _code_name = extract_exception_status_fields(exception)
    ret = {
        "event": StreamEventType.ERROR.value,
        "code": code if code not in (None, "") else (status_code or 400),
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
