import asyncio
from datetime import timedelta

import pytest
from aidev_bkplugin.models import EventDelivery
from django.utils import timezone

from .process_helpers import approval_record


@pytest.mark.parametrize("status,label", [("approved", "审批已通过"), ("rejected", "审批已拒绝")])
def test_ready_reads_authoritative_decision_before_notifying(approval_delivery_case, status, label):
    case = approval_delivery_case
    case.history.return_value = [approval_record(status)]
    case.bus.publish(case.event)
    asyncio.run(case.consumer.consume_once())
    target, body = case.send.call_args.args
    assert target == "original-group"
    assert body["template_card"]["jump_list"] == [{"type": 0, "title": label}]
    assert EventDelivery.objects.get().status == "delivered"
    assert EventDelivery.objects.get().progress == 1


def test_retry_uses_frozen_notice_without_requerying_platform(approval_delivery_case):
    from aidev_wxbot.wxaibot.database_delivery import DatabaseResumeConsumer

    case = approval_delivery_case
    case.bus.publish(case.event)
    case.send.side_effect = [RuntimeError("send failed"), None]
    asyncio.run(case.consumer.consume_once())
    delivery = EventDelivery.objects.get()
    assert delivery.status == "pending" and delivery.progress == 0
    assert len(delivery.route["approvalMessages"]) == 1
    case.history.side_effect = RuntimeError("platform unavailable after restart")
    EventDelivery.objects.update(available_at=timezone.now() - timedelta(seconds=1))
    restarted = DatabaseResumeConsumer("app", "bot-original", case.send)
    asyncio.run(restarted.consume_once())
    assert case.send.call_args_list[0] == case.send.call_args_list[1]
    case.history.assert_called_once_with("session-original")
    assert EventDelivery.objects.get().status == "delivered"
    assert not asyncio.run(restarted.consume_once())


def test_unpersisted_decision_retries_without_claiming_approval(approval_delivery_case):
    case = approval_delivery_case
    case.history.return_value = [approval_record("pending")]
    case.bus.publish(case.event)
    asyncio.run(case.consumer.consume_once())
    case.send.assert_not_called()
    assert EventDelivery.objects.get().status == "pending"
    assert "approvalMessages" not in EventDelivery.objects.get().route
    case.history.return_value = [approval_record()]
    EventDelivery.objects.update(available_at=timezone.now() - timedelta(seconds=1))
    asyncio.run(case.consumer.consume_once())
    assert case.send.call_count == 1
    assert EventDelivery.objects.get().status == "delivered"


@pytest.mark.parametrize("status", ["cancelled", "question"])
def test_no_extra_approval_notice_for_cancel_or_ask_user(approval_delivery_case, status):
    case = approval_delivery_case
    record = approval_record("cancelled")
    if status == "question":
        record["content"]["outcome"]["interrupts"][0]["reason"] = "aidev:user_question"
    case.history.return_value = [record]
    case.bus.publish(case.event)
    asyncio.run(case.consumer.consume_once())
    case.send.assert_not_called()
    assert EventDelivery.objects.get().status == "delivered"


def test_expired_lease_cannot_freeze_or_send_notice(approval_delivery_case):
    case = approval_delivery_case
    case.bus.publish(case.event)

    def expire_lease(_session):
        EventDelivery.objects.update(lease_until=timezone.now() - timedelta(seconds=1))
        return [approval_record()]

    case.history.side_effect = expire_lease
    asyncio.run(case.consumer.consume_once())
    case.send.assert_not_called()
    assert "approvalMessages" not in EventDelivery.objects.get().route
    assert EventDelivery.objects.get().status != "delivered"
