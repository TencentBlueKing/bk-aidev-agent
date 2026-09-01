"""Validate an Ask-user submission and resume the existing session once."""

from contextvars import copy_context
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as datetime_timezone
from logging import getLogger

from aidev_agent.core.ag_ui.ask_user_question import ASK_USER_QUESTION_REASON
from aidev_agent.enums import ChannelType
from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_execution import AgentExecutor, build_execute_kwargs
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_bkplugin.services.execution import get_agent_executor
from django.core.cache import cache
from django.db import close_old_connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .question_cards import (
    MAX_AGE,
    QuestionAction,
    decode_answers,
    question_task_id,
    questions_digest,
)
from .resume_context import original_interrupt_record, original_interrupt_turn
from .tracing import wxbot_span

logger = getLogger(__name__)


@dataclass(frozen=True)
class QuestionSubmission:
    action: QuestionAction
    username: str
    answers: list
    interrupt: dict
    graph_thread_id: str
    turn_id: str


def _read_pending(action: QuestionAction, username: str) -> tuple[SessionManager, dict, dict]:
    manager = SessionManager(username=username)
    # User-scoped platform read enforces session access; group visibility is not authorization.
    session = manager.retrieve_session(action.session_code)
    pending = (session.get("session_property") or {}).get("pending_interrupt") or {}
    if not pending:
        # Older platforms omit this session property. Recover only the latest
        # matching, still-pending persisted question after the scoped read above.
        record = original_interrupt_record(manager, action.session_code, action.interrupt_id)
        outcome = record["content"].get("outcome") or {}
        if outcome.get("type") != "interrupt":
            raise ValueError("Question is already finalized")
        builtin = (record.get("property") or {}).get("builtin_property")
        builtin = builtin if isinstance(builtin, dict) else record
        pending = {
            "graph_thread_id": builtin.get("graph_thread_id") or record.get("graph_thread_id"),
            "interrupts": outcome.get("interrupts"),
        }
    interrupts = pending.get("interrupts") or []
    interrupt = interrupts[-1] if isinstance(interrupts, list) and interrupts else {}
    metadata = interrupt.get("metadata") or {}
    if (
        interrupt.get("id") != action.interrupt_id
        or interrupt.get("reason") != ASK_USER_QUESTION_REASON
        or metadata.get("status", "pending") != "pending"
        or not pending.get("graph_thread_id")
        or questions_digest(metadata.get("questions") or []) != action.digest
    ):
        raise ValueError("Question is no longer pending")
    if interrupt.get("expiresAt"):
        expires = parse_datetime(interrupt["expiresAt"])
        if expires is None or timezone.is_naive(expires) or expires <= datetime.now(datetime_timezone.utc):
            raise ValueError("Question has expired")
    return manager, pending, interrupt


def prepare_question_submission(action: QuestionAction, username: str, selected: dict) -> QuestionSubmission:
    try:
        close_old_connections()
        manager, pending, interrupt = _read_pending(action, username)
        questions = interrupt["metadata"]["questions"]
        answers = decode_answers(questions, selected)
        turn_id = original_interrupt_turn(manager, action.session_code, action.interrupt_id)
        return QuestionSubmission(action, username, answers, interrupt, pending["graph_thread_id"], turn_id)
    finally:
        close_old_connections()


def submit_question_resume(submission: QuestionSubmission, delivery) -> str:
    try:
        close_old_connections()
        return _claim_and_submit(submission, delivery)
    finally:
        close_old_connections()


def _claim_and_submit(submission: QuestionSubmission, delivery) -> str:
    key = f"wxbot:question-submit:{question_task_id(submission.action)}"
    # Use the configured shared cache. Keep the claim after failure: uncertain
    # submissions must be inspected in Web, never replayed automatically.
    if not cache.add(key, "accepted", timeout=MAX_AGE):
        return "duplicate"
    submitted = False
    try:
        submitted = get_agent_executor().submit(copy_context().run, _question_worker, submission, delivery, key)
        return "accepted" if submitted else "busy"
    finally:
        if not submitted:
            cache.delete(key)


def _question_worker(submission: QuestionSubmission, delivery, key: str) -> None:
    with wxbot_span("wxbot.question.resume"):
        try:
            close_old_connections()
            manager, pending, _ = _read_pending(submission.action, submission.username)
            if pending["graph_thread_id"] != submission.graph_thread_id:
                raise ValueError("Runtime thread has changed")
            if (
                original_interrupt_turn(manager, submission.action.session_code, submission.action.interrupt_id)
                != submission.turn_id
            ):
                raise ValueError("Original turn has changed")
            builder = AgentBuilder(username=submission.username, turn_id=submission.turn_id)
            agent = builder.by_session_code(submission.action.session_code, channel_type=ChannelType.RTX.value)
            kwargs = build_execute_kwargs(
                {
                    "stream": True,
                    "session_code": submission.action.session_code,
                    "thread_id": submission.graph_thread_id,
                    "turn_id": submission.turn_id,
                    "resume": [
                        {
                            "interruptId": submission.action.interrupt_id,
                            "status": "resolved",
                            "payload": {"answers": submission.answers},
                        }
                    ],
                },
                submission.username,
            )
            AgentExecutor.run_agent_to_completion(
                agent,
                kwargs,
                submission.action.session_code,
                builder.session_manager,
                turn_id=submission.turn_id,
                consume_stream=(
                    lambda output: delivery.consume(
                        output,
                        submission.action.session_code,
                        submission.action.interrupt_id,
                        submission.turn_id,
                        thread_id=submission.graph_thread_id,
                    )
                )
                if delivery is not None
                else None,
            )
            cache.set(key, "completed", timeout=MAX_AGE)
            logger.info("event=wxbot_question_resume_finished")
        except Exception as error:
            logger.error("event=wxbot_question_resume_failed error_type=%s", type(error).__name__)
            if delivery is not None:
                delivery.failed()
        finally:
            close_old_connections()
            if delivery is not None:
                delivery.finish()
