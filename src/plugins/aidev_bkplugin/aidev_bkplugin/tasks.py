# -*- coding: utf-8 -*-
"""标准运维插件 Celery 任务；保留指标任务的原有导出路径。"""

from __future__ import annotations

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentType
from celery import shared_task

from .metric_tasks import enqueue_bkm_metrics_task as enqueue_bkm_metrics_task
from .metric_tasks import push_bkm_metrics_task as push_bkm_metrics_task
from .services.agent_bkplugin import build_bkplugin_runner
from .services.background_dispatch import attach_trace_context, detach_trace_context


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
    trace_context: dict[str, str] | None = None,
) -> None:
    token = attach_trace_context(trace_context)
    try:
        runner = build_bkplugin_runner(
            execute_kwargs=execute_payload,
            username=username,
            agent_type=AgentType(agent_type_value),
        )
        runner.run_worker(session_code, execute_payload, chat_context=chat_context or [])
    finally:
        detach_trace_context(token)
