# -*- coding: utf-8 -*-
"""Celery 自动发现入口；保留原有任务导出路径。"""

from .metric_tasks import enqueue_bkm_metrics_task as enqueue_bkm_metrics_task
from .metric_tasks import push_bkm_metrics_task as push_bkm_metrics_task
from .services.agent_bkplugin import run_bkplugin_background_agent_task as run_bkplugin_background_agent_task
