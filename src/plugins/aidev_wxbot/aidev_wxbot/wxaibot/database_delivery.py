"""Consume producer-owned events; never call chat/Agent to deliver a result."""

import asyncio
import hashlib
import json
import logging

from aidev_agent.events import AIDEV_CHAT_RESUME_FAILED, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_READY
from aidev_bkplugin.models import EventDelivery
from aidev_bkplugin.services.database_event_bus import DatabaseEventBus
from django.db import transaction
from django.utils import timezone

from .approval_notifications import approval_result_messages
from .database import database_connection_scope, run_with_database_connections
from .direct_stream import AgentStream, iter_direct_stream_frames
from .resume_delivery import markdown_parts
from .tracing import CONSUMER, resumed_event_context, wxbot_span

logger = logging.getLogger(__name__)
RESUME_EVENTS = (AIDEV_CHAT_RESUME_READY, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_FAILED)


def subscriber_name(bot_id: str) -> str:
    if not bot_id:
        raise ValueError("Missing WeCom bot identity")
    return "wxbot:" + hashlib.sha256(bot_id.encode()).hexdigest()


@database_connection_scope()
def bind_resume_subscription(app_code: str, bot_id: str, session_code: str, username: str, target: str) -> None:
    if not username or not target:
        raise ValueError("Missing trusted original WeCom recipient")
    with transaction.atomic():
        for name in RESUME_EVENTS:
            DatabaseEventBus(app_code).subscribe(
                subscriber_name(bot_id),
                name,
                session_code,
                property={"username": username, "target": target, "sessionCode": session_code},
            )


def result_messages(envelope: dict) -> list[dict]:
    """Reuse the same AG-UI renderer/card protocol as ordinary long-connection replies."""
    name, value = envelope["name"], envelope["value"]
    if name == AIDEV_CHAT_RESUME_READY:
        return []  # Approval notices need a separate authoritative history read.
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


class DatabaseResumeConsumer:
    def __init__(self, app_code: str, bot_id: str, send):
        self.bus = DatabaseEventBus(app_code)
        self.subscriber = subscriber_name(bot_id)
        self.send = send

    @database_connection_scope()
    def _prepare_messages(self, delivery) -> list[dict]:
        if delivery.envelope["name"] != AIDEV_CHAT_RESUME_READY:
            return result_messages(delivery.envelope)
        if "approvalMessages" in delivery.route:
            return delivery.route["approvalMessages"]
        value = delivery.envelope["value"]
        messages = approval_result_messages(
            value["sessionCode"], value.get("interruptIds") or [], delivery.route["username"]
        )
        # Freeze the rendered notice before the first send. Retrying (or another
        # process) must not change message indexes if history/config later changes.
        route = {**delivery.route, "approvalMessages": messages}
        updated = EventDelivery.objects.filter(
            pk=delivery.pk,
            status="processing",
            lease_token=delivery.lease_token,
            lease_until__gt=timezone.now(),
            subscription__enabled=True,
            subscription__app_code=self.bus.app_code,
        ).update(route=route)
        if not updated:
            raise RuntimeError("Event delivery lease lost")
        delivery.route = route
        return messages

    async def consume_once(self) -> bool:
        delivery = await asyncio.to_thread(run_with_database_connections, self.bus.claim, self.subscriber)
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
                messages = await asyncio.to_thread(self._prepare_messages, delivery)
                for index in range(delivery.progress, len(messages)):
                    await asyncio.to_thread(run_with_database_connections, self.bus.checkpoint, delivery, index)
                    await asyncio.wait_for(self.send(delivery.route["target"], messages[index]), timeout=45)
                    await asyncio.to_thread(run_with_database_connections, self.bus.checkpoint, delivery, index + 1)
                await asyncio.to_thread(run_with_database_connections, self.bus.acknowledge, delivery)
                logger.info("event=wxbot_event_delivered event_name=%s", delivery.envelope["name"])
        except Exception as error:
            await asyncio.to_thread(run_with_database_connections, self.bus.retry, delivery, error)
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
