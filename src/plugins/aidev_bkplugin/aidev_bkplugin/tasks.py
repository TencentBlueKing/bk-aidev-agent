# -*- coding: utf-8 -*-
"""标准运维插件 Celery 任务。"""

from __future__ import annotations

import logging
import time
from typing import Any

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentType
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


@shared_task(
    name="aidev_bkplugin.run_background_agent",
    ignore_result=True,
    queue=agent_settings.BKAI_AGENT_TASK,
)
def run_bkplugin_background_agent_task(
    session_code: str,
    execute_payload: dict,
    username: str | None,
    agent_type_value: str,
    chat_context: list[dict] | None = None,
) -> None:
    from .services.agent_bkplugin import build_bkplugin_runner

    runner = build_bkplugin_runner(
        execute_kwargs=execute_payload,
        username=username,
        agent_type=AgentType(agent_type_value),
    )
    runner.run_worker(session_code, execute_payload, chat_context=chat_context or [])
