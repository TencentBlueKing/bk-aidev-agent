# -*- coding: utf-8 -*-
"""Celery worker 与 broker 断连后的退出策略。

默认 Celery 会无限重连。重连失败或 consumers 未恢复时进程仍活着，
队列 ``consumers=0``，任务堆积，表现为服务假死。
连上之后禁止重连，让 worker 以非 0 退出，由 PaaS 拉起新进程。
启动阶段仍允许重试，避免 broker 尚未就绪时直接起不来。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Django settings / Celery 5 namespace 两套名字都写，兼容 blueapps 是否带 CELERY_ 前缀。
BROKER_LOSS_EXIT_SETTINGS = {
    "BROKER_CONNECTION_RETRY": False,
    "BROKER_CONNECTION_RETRY_ON_STARTUP": True,
    "WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS": True,
    "CELERY_BROKER_CONNECTION_RETRY": False,
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP": True,
    "CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS": True,
}


def is_celery_worker(argv: list[str] | None = None) -> bool:
    """判断当前进程是否为 Celery worker（不含 beat）。"""
    args = list(argv if argv is not None else sys.argv)
    if not args:
        return False
    program = Path(args[0]).name.lower()
    rest = args[1:]
    if program in {"celery", "celery.exe"}:
        return "worker" in rest
    if rest and rest[0] == "celery":
        return "worker" in rest[1:]
    return False


def apply_celery_exit_on_broker_loss(app: Any) -> None:
    """Disable post-connect broker reconnect so a lost consumer shuts the worker down."""
    conf = app.conf
    conf.broker_connection_retry = False
    conf.broker_connection_retry_on_startup = True
    conf.worker_cancel_long_running_tasks_on_connection_loss = True


def install_celery_exit_on_broker_loss(argv: list[str] | None = None) -> bool:
    """Worker 进程里关掉连上之后的 broker 重连。非 worker 或未安装 Celery 时跳过。"""
    if not is_celery_worker(argv):
        return False
    try:
        from celery import current_app
    except ImportError:
        logger.warning("[aidev_bkplugin] celery is not installed; skip broker-loss exit hook")
        return False

    apps = [current_app]
    try:
        from blueapps.core.celery import app as blueapps_app
    except ImportError:
        blueapps_app = None
    if blueapps_app is not None and blueapps_app is not current_app:
        apps.append(blueapps_app)

    for app in apps:
        apply_celery_exit_on_broker_loss(app)
    logger.warning(
        "[aidev_bkplugin] Celery broker reconnect after connect is disabled; "
        "worker will exit on connection loss so the platform can restart it"
    )
    return True
