"""取消成功后在原会话续流，写回 Web，并可注入企微消息消费者。"""

import threading
from contextvars import copy_context
from logging import getLogger

from aidev_agent.enums import ChannelType
from aidev_agent.services.agent.approval import ApprovalStateHandler
from aidev_agent.utils.tracing import get_current_trace_id
from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_execution import AgentExecutor, build_execute_kwargs
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_bkplugin.services.execution import get_agent_executor
from django.db import close_old_connections

from .approval_cards import ApprovalCancelAction
from .resume_context import original_interrupt_turn
from .tracing import record_failure, wxbot_span

logger = getLogger(__name__)
_pending: set[ApprovalCancelAction] = set()
_pending_lock = threading.Lock()


def submit_cancelled_approval_resume(
    action: ApprovalCancelAction, username: str, envelope: dict, delivery=None
) -> bool:
    """仅接受本次撤销成功的原会话指令；不信任回调携带的 URL 或执行参数。"""
    if not _can_resume(action, envelope):
        return False
    with _pending_lock:
        if action in _pending:
            if delivery is not None:
                delivery.finish()
            return True
        _pending.add(action)
    submitted = False
    try:
        submitted = get_agent_executor().submit(copy_context().run, _resume_worker, action, username, delivery)
        logger.info("event=wxbot_approval_resume_submitted accepted=%s trace_id=%s", submitted, get_current_trace_id())
        return submitted
    finally:
        if not submitted:
            with _pending_lock:
                _pending.discard(action)


def _can_resume(action: ApprovalCancelAction, envelope: dict) -> bool:
    if not isinstance(envelope, dict) or envelope.get("ok") is not True:
        return False
    result = envelope.get("result")
    next_action = envelope.get("next")
    if not isinstance(result, dict) or not isinstance(next_action, dict):
        return False
    payload = next_action.get("payload")
    return (
        result.get("approve_result") == "cancelled"
        and not result.get("already_finalized")
        and next_action.get("endpoint") == "chat_completion"
        and isinstance(payload, dict)
        and payload.get("session_code") == action.session_code
    )


def _resume_worker(action: ApprovalCancelAction, username: str, delivery=None) -> None:
    with wxbot_span("wxbot.approval.resume") as span:
        try:
            close_old_connections()
            _resume_cancelled_approval(action, username, delivery)
        except Exception as error:
            if delivery is not None:
                delivery.failed()
            record_failure(span, error)
            logger.error(
                "event=wxbot_approval_resume_failed error_type=%s trace_id=%s",
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


def _contains_interrupt(interrupts, interrupt_id: str) -> bool:
    return isinstance(interrupts, list) and any(
        isinstance(item, dict)
        and (item.get("id") or item.get("interruptId")) == interrupt_id
        and item.get("reason") == "aidev:tool_approval"
        for item in interrupts
    )


def _resume_cancelled_approval(action: ApprovalCancelAction, username: str, delivery=None) -> None:
    handler = ApprovalStateHandler(username=username)
    pending = handler.get_pending_interrupt_context(action.session_code)
    info = handler.fetch_approve_result(action.session_code)
    # 排队期间可能已由 Web 恢复或进入下一轮审批，不对旧卡片重放 Agent。
    if (
        not pending.get("graph_thread_id")
        or not _contains_interrupt(pending.get("interrupts"), action.interrupt_id)
        or not info
        or info.get("approve_result") != "cancelled"
        or not _contains_interrupt(info.get("interrupts"), action.interrupt_id)
    ):
        logger.info("event=wxbot_approval_resume_skipped reason=interrupt_changed trace_id=%s", get_current_trace_id())
        return
    resume = [{"interruptId": action.interrupt_id}]
    handler.hydrate_resume_payload(resume, "cancelled")
    execute_kwargs = build_execute_kwargs(
        {
            "stream": True,
            "session_code": action.session_code,
            "thread_id": pending["graph_thread_id"],
            "resume": resume,
        },
        username,
    )
    builder = AgentBuilder(username=username)
    agent = builder.by_session_code(action.session_code, channel_type=ChannelType.RTX.value)
    manager = SessionManager(username=username, resource_manager=builder.resource_manager)
    if delivery is None:
        AgentExecutor.run_agent_to_completion(agent, execute_kwargs, action.session_code, manager)
    else:
        turn_id = original_interrupt_turn(manager, action.session_code, action.interrupt_id)
        execute_kwargs.turn_id = turn_id
        AgentExecutor.run_agent_to_completion(
            agent,
            execute_kwargs,
            action.session_code,
            manager,
            turn_id=turn_id,
            consume_stream=lambda output: delivery.consume(
                output, action.session_code, action.interrupt_id, turn_id, thread_id=pending["graph_thread_id"]
            ),
        )
    logger.info("event=wxbot_approval_resume_finished trace_id=%s", get_current_trace_id())
