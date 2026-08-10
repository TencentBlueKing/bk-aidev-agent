# -*- coding: utf-8 -*-
"""标准运维插件 Celery 任务。"""

from __future__ import annotations

from aidev_agent.enums import AgentType
from celery import shared_task

# 与模板 app_desc.yml 中 celery worker 的 -Q 保持一致，否则任务会进默认 celery 队列而无人消费
BKPLUGIN_CELERY_QUEUE = "plugin_schedule"


@shared_task(
    name="aidev_bkplugin.push_bkm_metrics",
    ignore_result=True,
    queue=BKPLUGIN_CELERY_QUEUE,
)
def push_bkm_metrics_task(endpoint_key: str, payload: str) -> None:
    """Push one periodic BKM metric snapshot from the Celery worker."""
    from .apps import get_metric_service

    metric_service = get_metric_service()
    if metric_service is None:
        raise RuntimeError("Metric service is unavailable in the Celery worker")
    metric_service.push_bkm(endpoint_key, payload)


@shared_task(
    name="aidev_bkplugin.run_background_agent",
    ignore_result=True,
    queue=BKPLUGIN_CELERY_QUEUE,
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
