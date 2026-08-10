# -*- coding: utf-8 -*-
"""Process-local metric service registry shared by Django and Celery."""

from __future__ import annotations

from typing import Protocol


class BkmMetricPusher(Protocol):
    """Minimal worker-side interface required by the BKM Celery task."""

    def push_bkm(self, endpoint_key: str, payload: str) -> None: ...


_metric_service: BkmMetricPusher | None = None


def get_metric_service() -> BkmMetricPusher | None:
    """Return the metric service initialized in the current process."""
    return _metric_service


def set_metric_service(metric_service: BkmMetricPusher | None) -> None:
    """Replace the metric service used by worker tasks in this process."""
    global _metric_service
    _metric_service = metric_service
