"""Polling Chat admission and execution. Only the session carries the reply."""

import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import timedelta

from aidev_agent.enums import ChatContentStatus, PromptRole, SessionsStatus
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from aidev_bkplugin.enums import PluginPollTaskState
from aidev_bkplugin.models import SessionPollTurn


class PollSessionBusy(ValueError):
    """Another task owns this session."""


class PollSubmissionFailed(RuntimeError):
    """The polling admission path already recorded the failure."""


def _session_key(manager, session_code):
    identity = [manager.agent_code, getattr(manager.resource_manager, "tenant_id", ""), session_code]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def expire_poll_turn(manager, session_code):
    with transaction.atomic():
        expired = (
            SessionPollTurn.objects.select_for_update()
            .filter(session_key=_session_key(manager, session_code), expires_at__lte=timezone.now())
            .first()
        )
        if expired:
            if manager.retrieve_session(session_code).get("status") == SessionsStatus.PENDING.value:
                manager.save_stream_failure(session_code, "后台轮询任务超时", turn_id=expired.turn_id)
            expired.delete()


def poll_turn_result(manager, session_code, turn_id):
    expire_poll_turn(manager, session_code)
    session = manager.retrieve_session(session_code)
    if not session:
        raise NotFound("会话不存在")
    status = session.get("status")
    if (
        status == SessionsStatus.PENDING.value
        and SessionPollTurn.objects.filter(session_key=_session_key(manager, session_code), turn_id=turn_id).exists()
    ):
        return PluginPollTaskState.RUNNING, ""
    contents = manager.list_session_contents(session_code)
    for item in reversed(contents):
        if item.get("role") not in (PromptRole.AI.value, PromptRole.ASSISTANT.value):
            continue
        if (item.get("property") or {}).get("turn_id") != turn_id:
            continue
        text = item.get("content") or ""
        if item.get("status") == ChatContentStatus.ERROR.value:
            return PluginPollTaskState.FAILED, text
        if item.get("status") in (ChatContentStatus.SUCCESS.value, ChatContentStatus.COMPLETE.value):
            return PluginPollTaskState.SUCCESS, text
    if status in (SessionsStatus.CANCELLED.value, SessionsStatus.FAILED.value):
        return PluginPollTaskState.FAILED, status
    if status == SessionsStatus.FINISHED.value:
        return PluginPollTaskState.FAILED, "该轮次没有最终回复"
    return PluginPollTaskState.RUNNING, ""


@contextmanager
def reserve_poll_turn(manager, session_code, turn_id, invoke_timeout):
    expire_poll_turn(manager, session_code)
    key = _session_key(manager, session_code)
    timeout = invoke_timeout or getattr(settings, "BKAI_CHAT_WAIT_TIMEOUT", 1800)
    deadline = timezone.now() + timedelta(seconds=timeout + getattr(settings, "BKAI_CHAT_QUEUE_TIMEOUT", 300))

    ticket = uuid.uuid4()
    with transaction.atomic():
        slot, created = SessionPollTurn.objects.select_for_update().get_or_create(
            session_key=key, defaults={"ticket": ticket, "turn_id": turn_id, "expires_at": deadline}
        )
        session = manager.retrieve_session(session_code)
        if not session:
            raise ValueError("Chat session not found")
        status = session.get("status")
        if status == SessionsStatus.RUNNING.value or (not created and status == SessionsStatus.PENDING.value):
            raise PollSessionBusy("会话已有任务执行中")
        if not created:
            slot.ticket = ticket
            slot.turn_id = turn_id
            slot.expires_at = deadline
            slot.started = False
            slot.save(update_fields=["ticket", "started", "turn_id", "expires_at"])
        # The frontend only attaches SSE to running sessions. Pollers treat pending as in progress.
        manager.update_session_status(session_code, SessionsStatus.PENDING.value)
    try:
        yield str(ticket)
    except Exception as exc:
        with transaction.atomic():
            if SessionPollTurn.objects.select_for_update().filter(ticket=ticket).first():
                manager.save_stream_failure(session_code, str(exc), turn_id=turn_id)
                SessionPollTurn.objects.filter(ticket=ticket).delete()
        raise PollSubmissionFailed(str(exc)) from exc


def execute_poll_turn(manager, session_code, turn_id, ticket, invoke):
    """Deduplicate deliveries and fence a cancelled/superseded worker before persisting."""
    slot = SessionPollTurn.objects.filter(
        session_key=_session_key(manager, session_code), turn_id=turn_id, ticket=ticket
    )
    if not slot.filter(started=False).update(started=True):
        return
    try:
        if manager.retrieve_session(session_code).get("status") != SessionsStatus.PENDING.value:
            slot.delete()
            return
        result = invoke()
        with transaction.atomic():
            if (
                slot.select_for_update().first()
                and manager.retrieve_session(session_code).get("status") == SessionsStatus.PENDING.value
            ):
                manager.save_ai_response(session_code, result, turn_id=turn_id, persist_empty=True)
                manager.update_session_status(session_code, SessionsStatus.FINISHED.value)
            slot.delete()
    except Exception as exc:
        with transaction.atomic():
            if (
                slot.select_for_update().first()
                and manager.retrieve_session(session_code).get("status") == SessionsStatus.PENDING.value
            ):
                manager.save_stream_failure(session_code, str(exc), turn_id=turn_id)
            slot.delete()
        raise
