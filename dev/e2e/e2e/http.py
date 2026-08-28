from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class HttpResult:
    status: int
    headers: dict[str, str]
    body: Any
    duration_ms: int


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
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    elapsed = round((time.monotonic() - started) * 1000)
    text = raw.decode("utf-8", errors="replace")
    content_type = response.headers.get("Content-Type", "")
    try:
        body = json.loads(text) if "json" in content_type or text[:1] in "[{" else text
    except json.JSONDecodeError:
        body = text
    return HttpResult(response.status, dict(response.headers.items()), body, elapsed)


def with_query(url: str, **params: Any) -> str:
    values = {key: value for key, value in params.items() if value is not None}
    return f"{url}?{urllib.parse.urlencode(values)}" if values else url
