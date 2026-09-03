"""企微协议层埋点：不采集消息、身份、链接或原始异常内容。"""

from __future__ import annotations

import asyncio
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from aidev_agent.utils.tracing import recording_span

try:
    from opentelemetry import context, trace
    from opentelemetry.trace import SpanKind, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    context = trace = SpanKind = StatusCode = TraceContextTextMapPropagator = None


message_trace_active: ContextVar[bool] = ContextVar("wxbot_message_trace_active", default=False)
CLIENT = SpanKind.CLIENT if SpanKind else None
CONSUMER = SpanKind.CONSUMER if SpanKind else None


class _NoOpSpan:
    def set_attribute(self, *_args) -> None:
        pass

    def add_event(self, *_args, **_kwargs) -> None:
        pass

    def set_status(self, *_args) -> None:
        pass


def current_span() -> Any:
    return trace.get_current_span() if trace else _NoOpSpan()


def trace_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if TraceContextTextMapPropagator:
        TraceContextTextMapPropagator().inject(headers)
    return headers


def error_attributes(error: BaseException) -> dict[str, str | int]:
    attributes: dict[str, str | int] = {"error.type": type(error).__name__}
    # SDK 将 ACK 错误码放在异常文案中；只提取数字，绝不采集 errmsg。
    if match := re.search(r"\berrcode=(-?\d{1,10})\b", str(error)):
        attributes["wecom.ack.errcode"] = int(match[1])
    return attributes


def record_failure(span: Any, error: BaseException) -> None:
    for key, value in error_attributes(error).items():
        span.set_attribute(key, value)
    span.set_attribute("wxbot.outcome", "cancelled" if isinstance(error, asyncio.CancelledError) else "error")
    if StatusCode:
        span.set_status(StatusCode.ERROR)


def record_ack(span: Any, response: Any) -> None:
    if isinstance(response, dict) and isinstance(response.get("errcode"), int):
        span.set_attribute("wecom.ack.errcode", response["errcode"])
        if response["errcode"] != 0:
            raise RuntimeError(f"WeCom acknowledgment error: errcode={response['errcode']}")
        span.set_attribute("wecom.ack.received", True)
    span.set_attribute("wxbot.outcome", "success")


@contextmanager
def wxbot_span(name: str, *, root: bool = False, kind=None, attributes: dict | None = None) -> Iterator[Any]:
    """使用应用全局 tracer，使 service.name 与 MCP tool 一样为 appcode + module。"""
    if trace is None:
        yield _NoOpSpan()
        return
    with recording_span(
        name,
        attributes={"aidev.channel": "rtx", **(attributes or {})},
        kind=kind,
        root=root,
        record_exception=False,
        use_global_tracer=True,
    ) as span:
        try:
            yield span
        except BaseException as error:
            record_failure(span, error)
            raise


@contextmanager
def resumed_event_context(carrier: dict) -> Iterator[None]:
    """Continue the producer trace across a durable event; never carry baggage."""
    if not context or not TraceContextTextMapPropagator:
        yield
        return
    safe = {key: carrier[key] for key in ("traceparent", "tracestate") if isinstance(carrier.get(key), str)}
    token = context.attach(TraceContextTextMapPropagator().extract(safe))
    try:
        yield
    finally:
        context.detach(token)


@contextmanager
def received_message_span(frame: dict) -> Iterator[None]:
    payload = frame.get("body") or {}
    msgtype = payload.get("msgtype") if isinstance(payload, dict) else None
    chattype = payload.get("chattype") if isinstance(payload, dict) else None
    attributes = {
        "aidev.transport": "websocket",
        "wecom.message.type": msgtype if msgtype in ("text", "stream", "event", "image", "voice", "mixed") else "other",
        "wecom.chat.type": chattype if chattype in ("single", "group") else "other",
    }
    with wxbot_span("wxbot.message.receive", root=True, kind=CONSUMER, attributes=attributes):
        token = message_trace_active.set(True)
        try:
            yield
        finally:
            message_trace_active.reset(token)
