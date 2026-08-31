"""Small durable publisher/consumer boundary, using Django ORM (including MySQL 5.7).

It deliberately does not implement LocalEventBus.subscribe(callback). Subscribers
are durable identities; channel processes own handlers. No scheduler or network
operations run in the publisher. Delivery is at-least-once, not exactly-once.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import timedelta

from ag_ui.core import BaseEvent, CustomEvent
from aidev_agent.events import event_key
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from aidev_bkplugin.models import EventDelivery, EventSubscription
from aidev_bkplugin.services.event_tracing import event_span

logger = logging.getLogger(__name__)


class DatabaseEventBus:
    LEASE_SECONDS = 120
    MAX_ATTEMPTS = 8

    def __init__(self, app_code: str):
        if not app_code:
            raise ValueError("Event publisher requires an application scope")
        self.app_code = app_code

    def subscribe(self, subscriber: str, name: str, session_code: str, *, property: dict) -> EventSubscription:
        if not subscriber or not name or not session_code:
            raise ValueError("Incomplete event subscription scope")
        key = hashlib.sha256(json.dumps([self.app_code, subscriber, name, session_code]).encode()).hexdigest()
        subscription, _ = EventSubscription.objects.get_or_create(
            key=key,
            defaults={
                "scope_key": self._scope_key(session_code),
                "subscriber": subscriber,
                "event_name": name,
                "app_code": self.app_code,
                "session_code": session_code,
                "property": property,
            },
        )
        if subscription.property != property or not subscription.enabled:
            raise ValueError("Existing subscription binding cannot be silently replaced")
        return subscription

    def _scope_key(self, session_code: str) -> str:
        return hashlib.sha256(json.dumps([self.app_code, session_code]).encode()).hexdigest()

    def publish(self, event: BaseEvent) -> None:
        if not isinstance(event, CustomEvent) or not isinstance(event.value, dict):
            raise ValueError("Database events require a scoped CUSTOM envelope")
        value = event.value
        if value.get("appCode") != self.app_code or not value.get("sessionCode") or not value.get("eventId"):
            raise ValueError("Invalid event scope or identity")
        event_id = hashlib.sha256(str(value["eventId"]).encode()).hexdigest()
        envelope = event.model_dump(mode="json", by_alias=True)
        with event_span("database_event.publish", envelope, producer=True), transaction.atomic():
            subscriptions = EventSubscription.objects.filter(
                scope_key=self._scope_key(value["sessionCode"]),
                app_code=self.app_code,
                session_code=value["sessionCode"],
                event_name=event_key(event),
                enabled=True,
            )
            for subscription in subscriptions:
                delivery, created = EventDelivery.objects.get_or_create(
                    subscription=subscription,
                    event_id=event_id,
                    defaults={"envelope": envelope, "route": subscription.property, "available_at": timezone.now()},
                )
                if not created and delivery.envelope != envelope:
                    raise ValueError("An event identity cannot be reused for different content")

    def claim(self, subscriber: str) -> EventDelivery | None:
        lookup_started = time.perf_counter()
        now = timezone.now()
        eligible = Q(status="pending", available_at__lte=now) | Q(status="processing", lease_until__lte=now)
        earlier = EventDelivery.objects.filter(
            subscription__scope_key=OuterRef("subscription__scope_key"),
            subscription__subscriber=subscriber,
            subscription__enabled=True,
            id__lt=OuterRef("id"),
            status__in=["pending", "processing"],
        )
        candidates = (
            EventDelivery.objects.filter(
                eligible,
                subscription__app_code=self.app_code,
                subscription__subscriber=subscriber,
                subscription__enabled=True,
            )
            .filter(~Exists(earlier))
            .order_by("id")[:50]
        )
        for candidate in candidates:
            attributes = {
                "messaging.receive.lookup.duration_ms": (time.perf_counter() - lookup_started) * 1000,
                "messaging.message.age_ms": max(0, (now - candidate.created_at).total_seconds() * 1000),
                "messaging.delivery.attempt": candidate.attempts + 1,
            }
            # The parent becomes known only after selecting the candidate. Record
            # lookup time as an attribute, and trace the actual lease acquisition.
            with event_span("database_event.claim", candidate.envelope, attributes=attributes):
                claimed = self._claim_candidate(candidate, eligible, now)
            if claimed is not None:
                return claimed
        return None

    def _claim_candidate(self, candidate: EventDelivery, eligible: Q, now) -> EventDelivery | None:
        # Order all event kinds per session/subscriber; no MySQL-8-only SKIP LOCKED.
        token = uuid.uuid4().hex
        count = EventDelivery.objects.filter(eligible, pk=candidate.pk).update(
            status="processing",
            lease_token=token,
            lease_until=now + timedelta(seconds=self.LEASE_SECONDS),
            attempts=F("attempts") + 1,
            updated_at=now,
        )
        if count:
            return EventDelivery.objects.get(pk=candidate.pk, lease_token=token)
        return None

    def _owned(self, delivery: EventDelivery):
        return EventDelivery.objects.filter(
            pk=delivery.pk,
            subscription__app_code=self.app_code,
            status="processing",
            subscription__enabled=True,
            lease_token=delivery.lease_token,
            lease_until__gt=timezone.now(),
        )

    def checkpoint(self, delivery: EventDelivery, progress: int) -> None:
        if not self._owned(delivery).update(
            progress=progress,
            lease_until=timezone.now() + timedelta(seconds=self.LEASE_SECONDS),
            updated_at=timezone.now(),
        ):
            raise RuntimeError("Event delivery lease lost")
        delivery.progress = progress

    def acknowledge(self, delivery: EventDelivery) -> None:
        if not self._owned(delivery).update(status="delivered", lease_until=None, updated_at=timezone.now()):
            raise RuntimeError("Event delivery lease lost")

    def retry(self, delivery: EventDelivery, error: Exception) -> None:
        status = "failed" if delivery.attempts >= self.MAX_ATTEMPTS else "pending"
        self._owned(delivery).update(
            status=status,
            lease_until=None,
            lease_token="",
            error_type=type(error).__name__[:128],
            available_at=timezone.now() + timedelta(seconds=min(300, 2**delivery.attempts)),
            updated_at=timezone.now(),
        )
        logger.warning("event=database_event_delivery_retry status=%s error_type=%s", status, type(error).__name__)
