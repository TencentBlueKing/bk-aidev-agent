"""Flow 节点重试/跳过后在原会话续跑，结果用企微主动消息投递。"""

from __future__ import annotations

import threading
from contextvars import copy_context
from logging import getLogger

from aidev_agent.utils.tracing import get_current_trace_id
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_bkplugin.services.execution import get_agent_executor
from django.db import close_old_connections

from .direct_stream import iter_direct_stream_frames
from .flow_cards import FlowNodeAction
from .strategies import FlowAgentStrategy
from .tracing import record_failure, wxbot_span

logger = getLogger(__name__)
_pending: set[FlowNodeAction] = set()
_pending_lock = threading.Lock()


def submit_flow_node_resume(action: FlowNodeAction, username: str, delivery=None) -> bool:
    """只接受本次卡片对应的原会话续跑；不信任回调里的 URL 或执行参数。"""
    with _pending_lock:
        if action in _pending:
            if delivery is not None:
                delivery.finish()
            return True
        _pending.add(action)
    submitted = False
    try:
        submitted = get_agent_executor().submit(copy_context().run, _resume_worker, action, username, delivery)
        logger.info("event=wxbot_flow_resume_submitted accepted=%s trace_id=%s", submitted, get_current_trace_id())
        return submitted
    finally:
        if not submitted:
            with _pending_lock:
                _pending.discard(action)


def _resume_worker(action: FlowNodeAction, username: str, delivery=None) -> None:
    with wxbot_span("wxbot.flow.resume") as span:
        try:
            close_old_connections()
            _resume_flow_node(action, username, delivery)
        except Exception as error:
            if delivery is not None:
                delivery.failed()
            record_failure(span, error)
            logger.error(
                "event=wxbot_flow_resume_failed error_type=%s trace_id=%s",
                type(error).__name__,
                get_current_trace_id(),
            )
        finally:
            try:
                close_old_connections()
            finally:
                with _pending_lock:
                    _pending.discard(action)
                if delivery is not None:
                    delivery.finish()


def _resume_flow_node(action: FlowNodeAction, username: str, delivery=None) -> None:
    manager = SessionManager(username=username)
    session = manager.retrieve_session(action.session_code)
    flow_info = (session.get("session_property") or {}).get("flow_info") or {}
    if not session or str(flow_info.get("task_id") or "") != str(action.task_id):
        logger.info(
            "event=wxbot_flow_resume_skipped reason=session_or_task_mismatch trace_id=%s",
            get_current_trace_id(),
        )
        if delivery is not None:
            delivery.failed()
        return

    content = f"{'重试' if action.operation == 'retry' else '跳过'}节点：{action.node_name or action.node_id}"
    agent_stream = FlowAgentStrategy().open_stream(
        content=content,
        username=username,
        thread_id="",
        group_id="",
        task_id=action.task_id,
        resume_from_node=action.operation,
        session_code=action.session_code,
    )
    if delivery is None:
        for _ in iter_direct_stream_frames(agent_stream, action.node_id):
            pass
        logger.info("event=wxbot_flow_resume_finished delivery=none trace_id=%s", get_current_trace_id())
        return

    delivery.consume(
        agent_stream.generator,
        agent_stream.session_code,
        action.node_id,
        kind="flow",
    )
    logger.info("event=wxbot_flow_resume_finished trace_id=%s", get_current_trace_id())
