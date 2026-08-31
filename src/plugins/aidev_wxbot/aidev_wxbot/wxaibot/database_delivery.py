"""Consume producer-owned events; never call chat/Agent to deliver a result."""

import asyncio
import hashlib
import json
import logging

from aidev_agent.events import AIDEV_CHAT_RESUME_FAILED, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_READY
from aidev_bkplugin.services.database_event_bus import DatabaseEventBus
from django.db import close_old_connections, transaction

from .direct_stream import AgentStream, iter_direct_stream_frames
from .resume_delivery import markdown_parts
from .tracing import CONSUMER, resumed_event_context, wxbot_span

logger = logging.getLogger(__name__)
RESUME_EVENTS = (AIDEV_CHAT_RESUME_READY, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_FAILED)


def subscriber_name(bot_id: str) -> str:
    if not bot_id:
        raise ValueError("Missing WeCom bot identity")
    return "wxbot:" + hashlib.sha256(bot_id.encode()).hexdigest()


def bind_resume_subscription(app_code: str, bot_id: str, session_code: str, username: str, target: str) -> None:
    if not username or not target:
        raise ValueError("Missing trusted original WeCom recipient")
    try:
        close_old_connections()
        with transaction.atomic():
            for name in RESUME_EVENTS:
                DatabaseEventBus(app_code).subscribe(
                    subscriber_name(bot_id),
                    name,
                    session_code,
                    property={"username": username, "target": target, "sessionCode": session_code},
                )
    finally:
        close_old_connections()


def result_messages(envelope: dict) -> list[dict]:
    """Reuse the same AG-UI renderer/card protocol as ordinary long-connection replies."""
    name, value = envelope["name"], envelope["value"]
    if name == AIDEV_CHAT_RESUME_READY:
        return []  # Notification/audit only; never equate READY with approval granted.
    if name not in RESUME_EVENTS:
        raise ValueError("Unsupported wxbot event")
    if not value.get("persisted"):
        return [{"msgtype": "markdown", "markdown": {"content": "会话恢复未完成，请返回原会话查看。"}}]
    events = value.get("events") or []
    if not any(e.get("type") == "RUN_FINISHED" for e in events):
        raise ValueError("Resume result has no terminal event")
    chunks = ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n" for event in events)
    interrupt_id = next(iter(value.get("interruptIds") or []), "")
    stream = AgentStream("chat", chunks, value["sessionCode"], resume_interrupt_id=interrupt_id)
    final = None
    for frame in iter_direct_stream_frames(stream, value["eventId"]):
        if frame.finish:
            final = frame
    if final is None:
        raise ValueError("Resume result did not render a final frame")
    messages = [{"msgtype": "markdown", "markdown": {"content": part}} for part in markdown_parts(final.content)]
    if final.template_card:
        messages.append({"msgtype": "template_card", "template_card": final.template_card})
    return messages


def _database_call(func, *args):
    try:
        close_old_connections()
        return func(*args)
    finally:
        close_old_connections()


class DatabaseResumeConsumer:
    def __init__(self, app_code: str, bot_id: str, send):
        self.bus = DatabaseEventBus(app_code)
        self.subscriber = subscriber_name(bot_id)
        self.send = send

    async def consume_once(self) -> bool:
        delivery = await asyncio.to_thread(_database_call, self.bus.claim, self.subscriber)
        if delivery is None:
            return False
        try:
            with (
                resumed_event_context(delivery.envelope["value"].get("traceContext") or {}),
                wxbot_span(
                    "wxbot.event.consume",
                    kind=CONSUMER,
                    attributes={"event.name": delivery.envelope["name"]},
                ),
            ):
                value = delivery.envelope["value"]
                if (
                    value.get("schemaVersion") != 1
                    or value.get("appCode") != self.bus.app_code
                    or value.get("sessionCode") != delivery.route.get("sessionCode")
                    or not delivery.route.get("target")
                    or not delivery.route.get("username")
                ):
                    raise ValueError("Invalid event recipient binding")
                messages = await asyncio.to_thread(result_messages, delivery.envelope)
                for index in range(delivery.progress, len(messages)):
                    await asyncio.to_thread(_database_call, self.bus.checkpoint, delivery, index)
                    await asyncio.wait_for(self.send(delivery.route["target"], messages[index]), timeout=45)
                    await asyncio.to_thread(_database_call, self.bus.checkpoint, delivery, index + 1)
                await asyncio.to_thread(_database_call, self.bus.acknowledge, delivery)
                logger.info("event=wxbot_event_delivered event_name=%s", delivery.envelope["name"])
        except Exception as error:
            await asyncio.to_thread(_database_call, self.bus.retry, delivery, error)
        # CancelledError leaves the lease unacknowledged for another process after expiry.
        return True

    async def run(self, available, stopping) -> None:
        while not stopping():
            try:
                if available() and await self.consume_once():
                    continue
            except Exception as error:
                logger.warning("event=wxbot_event_poll_failed error_type=%s", type(error).__name__)
            await asyncio.sleep(1)
