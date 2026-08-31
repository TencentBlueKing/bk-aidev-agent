from datetime import timedelta

import pytest
from aidev_bkplugin.models import EventDelivery
from aidev_bkplugin.services.database_event_bus import DatabaseEventBus
from django.db import transaction
from django.utils import timezone


def test_publish_is_durable_idempotent_and_not_a_delivery_ack(event_case):
    case = event_case
    case.bus.publish(case.event)
    DatabaseEventBus("app").publish(case.event.model_copy(deep=True))
    delivery = EventDelivery.objects.get()
    assert delivery.status == "pending" and delivery.attempts == 0
    assert delivery.route == {"target": "user"}
    assert delivery.envelope["value"]["sessionCode"] == "session"


def test_subscribers_receive_independent_deliveries(event_case):
    case = event_case
    case.bus.subscribe("audit", case.event.name, "session", property={})
    case.bus.publish(case.event)
    first = case.bus.claim("wxbot:test")
    case.bus.acknowledge(first)
    assert case.bus.claim("wxbot:test") is None
    other = case.bus.claim("audit")
    assert other and other.pk != first.pk and other.envelope == first.envelope


@pytest.mark.parametrize("key,value", [("appCode", "other"), ("sessionCode", ""), ("eventId", "")])
def test_invalid_scope_cannot_publish(event_case, key, value):
    event_case.event.value[key] = value
    with pytest.raises(ValueError):
        event_case.bus.publish(event_case.event)
    assert not EventDelivery.objects.exists()


def test_unsubscribed_session_is_not_broadcast_and_app_isolation(event_case):
    case = event_case
    case.event.value["sessionCode"] = "unrelated"
    case.bus.publish(case.event)
    assert not EventDelivery.objects.exists()
    case.event.value["sessionCode"] = "session"
    case.bus.publish(case.event)
    assert DatabaseEventBus("other-app").claim("wxbot:test") is None


def test_rollback_does_not_leak_event(event_case):
    with pytest.raises(RuntimeError), transaction.atomic():
        event_case.bus.publish(event_case.event)
        raise RuntimeError("roll back")
    assert not EventDelivery.objects.exists()


def test_existing_route_cannot_be_rebound_on_new_conversation(event_case):
    case = event_case
    with pytest.raises(ValueError, match="binding"):
        case.bus.subscribe("wxbot:test", case.event.name, "session", property={"target": "other"})
    assert case.subscription.property == {"target": "user"}


def test_expired_lease_can_be_reclaimed_but_old_owner_cannot_ack(event_case):
    case = event_case
    case.bus.publish(case.event)
    old = case.bus.claim("wxbot:test")
    assert case.bus.claim("wxbot:test") is None
    EventDelivery.objects.filter(pk=old.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
    new = DatabaseEventBus("app").claim("wxbot:test")
    assert new.pk == old.pk and new.lease_token != old.lease_token
    with pytest.raises(RuntimeError, match="lease lost"):
        case.bus.acknowledge(old)
    case.bus.acknowledge(new)


def test_retry_preserves_progress_and_stores_no_exception_body(event_case):
    case = event_case
    case.bus.publish(case.event)
    delivery = case.bus.claim("wxbot:test")
    case.bus.checkpoint(delivery, 1)
    case.bus.retry(delivery, RuntimeError("private response"))
    delivery.refresh_from_db()
    assert delivery.status == "pending" and delivery.progress == 1
    assert delivery.error_type == "RuntimeError"
    assert case.bus.claim("wxbot:test") is None


def test_same_subscriber_does_not_overtake_retrying_event(event_case):
    case = event_case
    case.bus.publish(case.event)
    first = case.bus.claim("wxbot:test")
    next_event = case.event.model_copy(deep=True)
    next_event.value["eventId"] = "event-2"
    case.bus.publish(next_event)
    case.bus.retry(first, RuntimeError())
    assert case.bus.claim("wxbot:test") is None


def test_exhausted_retry_is_visible_and_not_automatically_reexecuted(event_case):
    case = event_case
    case.bus.publish(case.event)
    EventDelivery.objects.update(attempts=case.bus.MAX_ATTEMPTS - 1)
    delivery = case.bus.claim("wxbot:test")
    case.bus.retry(delivery, RuntimeError())
    delivery.refresh_from_db()
    assert delivery.status == "failed" and case.bus.claim("wxbot:test") is None


def test_event_kinds_share_session_order_without_starving_other_sessions(event_case):
    case = event_case
    case.bus.publish(case.event)
    first = case.bus.claim("wxbot:test")
    case.bus.retry(first, RuntimeError())
    case.bus.subscribe("wxbot:test", "OTHER_EVENT", "session", property={"target": "user"})
    for number in range(55):
        event = case.event.model_copy(deep=True)
        event.name = "OTHER_EVENT"
        event.value["eventId"] = f"later-{number}"
        case.bus.publish(event)
    case.bus.subscribe("wxbot:test", case.event.name, "another-session", property={"target": "user"})
    event = case.event.model_copy(deep=True)
    event.value.update(sessionCode="another-session", eventId="other-session-event")
    case.bus.publish(event)
    assert case.bus.claim("wxbot:test").envelope["value"]["sessionCode"] == "another-session"


def test_disabled_subscription_cannot_send_or_ack_claimed_event(event_case):
    case = event_case
    case.bus.publish(case.event)
    delivery = case.bus.claim("wxbot:test")
    case.subscription.enabled = False
    case.subscription.save(update_fields=["enabled"])
    with pytest.raises(RuntimeError, match="lease lost"):
        case.bus.checkpoint(delivery, 0)
    with pytest.raises(RuntimeError, match="lease lost"):
        case.bus.acknowledge(delivery)
    assert case.bus.claim("wxbot:test") is None


def test_event_migration_matches_models(db):
    from django.core.management import call_command

    call_command("makemigrations", "aidev_bkplugin", check=True, dry_run=True, verbosity=0)
