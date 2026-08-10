"""Optional metric hooks shared by message handler implementations."""

from __future__ import annotations

import logging
import time

try:
    from aidev_agent.packages.opentelemetry.metrics import get_enabled_agent_metrics
except ImportError:  # pragma: no cover - OpenTelemetry is an optional SDK extra
    get_enabled_agent_metrics = None

logger = logging.getLogger(__name__)


def record_message_publish_metrics(
    *,
    handler_type: str,
    messaging_system: str,
    event_count: int,
    message_sizes: list[int],
    started_at: float,
    error: BaseException | None = None,
) -> None:
    """Record one logical handler batch without affecting the publish path."""
    if get_enabled_agent_metrics is None:
        return
    metric_recorder = get_enabled_agent_metrics()
    if metric_recorder is None:
        return
    try:
        metric_recorder.record_message_publish(
            handler_type=handler_type,
            messaging_system=messaging_system,
            event_count=event_count,
            message_sizes=message_sizes,
            duration=time.monotonic() - started_at,
            error=error,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to record %s publish metrics", handler_type, exc_info=True)
