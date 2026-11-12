"""Celery 调度边界：仅传可序列化参数，不依赖任务实现以避免循环导入。"""

from typing import Any

from aidev_agent.config import settings as agent_settings
from celery import current_app

try:
    from opentelemetry import context, propagate
except ImportError:  # OTel is optional.
    context = propagate = None


def enqueue_background_agent(**payload: Any) -> Any:
    carrier: dict[str, str] = {}
    if propagate is not None:
        propagate.inject(carrier)
    return current_app.signature("aidev_bkplugin.run_background_agent", queue=agent_settings.BKAI_AGENT_TASK).delay(
        **payload, trace_context=carrier
    )


def attach_trace_context(carrier: dict[str, str] | None) -> Any:
    if not carrier or context is None or propagate is None:
        return None
    return context.attach(propagate.extract(carrier))


def detach_trace_context(token: Any) -> None:
    if context is not None and token is not None:
        context.detach(token)
