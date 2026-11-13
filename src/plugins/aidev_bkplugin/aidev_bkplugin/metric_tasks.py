# -*- coding: utf-8 -*-
"""轻量指标任务：管理命令初始化时不加载 Agent 执行链路。"""

from __future__ import annotations

import logging
import time
from typing import Any

from aidev_agent.config import settings as agent_settings
from celery import shared_task

from .services.metric_runtime import RetryableMetricPushError, get_metric_service

logger = logging.getLogger(__name__)


@shared_task(
    name="aidev_bkplugin.push_bkm_metrics",
    ignore_result=True,
    queue=agent_settings.BKAI_AGENT_QUEUE_METRIC,
    autoretry_for=(RetryableMetricPushError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def push_bkm_metrics_task(
    endpoint_key: str,
    payload: str,
    created_at_millis: int,
    ttl_seconds: int,
) -> None:
    """Push one periodic BKM metric snapshot from the Celery worker."""
    age_millis = max(0, time.time_ns() // 1_000_000 - created_at_millis)
    if age_millis > ttl_seconds * 1000:
        logger.warning(
            "[aidev_bkplugin] stale metric snapshot discarded: endpoint=%s age_seconds=%.3f ttl_seconds=%d",
            endpoint_key,
            age_millis / 1000,
            ttl_seconds,
        )
        return
    metric_service = get_metric_service()
    if metric_service is None:
        raise RuntimeError("Metric service is unavailable in the Celery worker")
    metric_service.push_bkm(endpoint_key, payload)


def enqueue_bkm_metrics_task(
    endpoint_key: str,
    payload: str,
    created_at_millis: int,
    ttl_seconds: int,
) -> Any:
    """Enqueue a metric snapshot with the same expiry enforced by the worker."""
    return push_bkm_metrics_task.apply_async(
        args=(endpoint_key, payload, created_at_millis, ttl_seconds),
        expires=ttl_seconds,
    )
