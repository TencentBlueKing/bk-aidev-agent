from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from .trace import API_TRACE


@dataclass
class HttpResult:
    status: int
    headers: dict[str, str]
    body: Any
    duration_ms: int


def stream_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    timeout: float = 30,
    stop_after: Callable[[str], bool] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> HttpResult:
    """Read an SSE response line-by-line, optionally simulating a client disconnect."""

    payload = None if json_body is None else json.dumps(json_body, ensure_ascii=False).encode()
    request_headers = {"Accept": "text/event-stream", **(headers or {})}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method.upper())
    started = time.monotonic()
    trace_call = API_TRACE.start_call(
        source="test-runner",
        method=method,
        url=url,
        request_headers=request_headers,
        request_body=json_body,
    )
    response = None
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
        response_headers = dict(response.headers.items())
        lines: list[str] = []
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace")
            lines.append(line)
            if on_line is not None:
                on_line(line)
            if stop_after is not None and stop_after(line):
                response.close()
                break
        body = "".join(lines)
        elapsed = round((time.monotonic() - started) * 1000)
        API_TRACE.finish_call(
            trace_call,
            status=response.status,
            response_headers=response_headers,
            response_body=body,
            duration_ms=elapsed,
        )
        return HttpResult(response.status, response_headers, body, elapsed)
    except urllib.error.HTTPError as error:
        raw = error.read()
        body = raw.decode("utf-8", errors="replace")
        elapsed = round((time.monotonic() - started) * 1000)
        response_headers = dict(error.headers.items())
        API_TRACE.finish_call(
            trace_call,
            status=error.status,
            response_headers=response_headers,
            response_body=body,
            duration_ms=elapsed,
        )
        return HttpResult(error.status, response_headers, body, elapsed)
    except Exception as error:
        elapsed = round((time.monotonic() - started) * 1000)
        API_TRACE.finish_call(trace_call, duration_ms=elapsed, error=str(error))
        raise
    finally:
        if response is not None:
            response.close()


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    timeout: float = 15,
) -> HttpResult:
    payload = None if json_body is None else json.dumps(json_body, ensure_ascii=False).encode()
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method.upper())
    started = time.monotonic()
    trace_call = API_TRACE.start_call(
        source="test-runner",
        method=method,
        url=url,
        request_headers=request_headers,
        request_body=json_body,
    )
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    except Exception as error:
        elapsed = round((time.monotonic() - started) * 1000)
        API_TRACE.finish_call(trace_call, duration_ms=elapsed, error=str(error))
        raise
    try:
        raw = response.read()
        elapsed = round((time.monotonic() - started) * 1000)
        status = response.status
        response_headers = dict(response.headers.items())
        text = raw.decode("utf-8", errors="replace")
        content_type = response.headers.get("Content-Type", "")
        try:
            body = json.loads(text) if "json" in content_type or text[:1] in "[{" else text
        except json.JSONDecodeError:
            body = text
        API_TRACE.finish_call(
            trace_call,
            status=status,
            response_headers=response_headers,
            response_body=body,
            duration_ms=elapsed,
        )
        return HttpResult(status, response_headers, body, elapsed)
    finally:
        response.close()


def with_query(url: str, **params: Any) -> str:
    values = {key: value for key, value in params.items() if value is not None}
    return f"{url}?{urllib.parse.urlencode(values)}" if values else url
