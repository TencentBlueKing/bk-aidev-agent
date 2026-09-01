import asyncio
from datetime import timedelta

import pytest
from aidev_bkplugin.models import EventDelivery
from django.utils import timezone


def test_send_failure_retries_from_last_successful_message(wx_delivery_case):
    case = wx_delivery_case
    case.event.value["events"][2]["delta"] = "A" * 8001
    case.bus.publish(case.event)
    case.send.side_effect = [None, RuntimeError("private failure"), None, None]
    asyncio.run(case.consumer.consume_once())
    delivery = EventDelivery.objects.get()
    assert delivery.status == "pending" and delivery.progress == 1
    EventDelivery.objects.update(available_at=timezone.now() - timedelta(seconds=1))
    asyncio.run(case.consumer.consume_once())
    delivery.refresh_from_db()
    assert delivery.status == "delivered" and delivery.progress == 3
    assert case.send.call_count == 4
    assert all(call.args[0] == "original-group" for call in case.send.call_args_list)


def test_rendering_again_yields_question_card_for_the_original_session(wx_delivery_case):
    from aidev_wxbot.wxaibot.question_cards import decode_question_key

    from .process_helpers import runtime_events

    case = wx_delivery_case
    case.event.value["events"] = runtime_events(question=True)
    case.bus.publish(case.event)
    asyncio.run(case.consumer.consume_once())
    assert case.send.call_count == 2
    card = case.send.call_args.args[1]["template_card"]
    assert card["card_type"] == "vote_interaction"
    assert decode_question_key(card["submit_button"]["key"]).session_code == "session-original"
    assert EventDelivery.objects.get().status == "delivered"


def test_mismatched_route_is_never_sent(wx_delivery_case):
    case = wx_delivery_case
    case.bus.publish(case.event)
    EventDelivery.objects.update(route={"target": "other", "username": "author", "sessionCode": "other-session"})
    asyncio.run(case.consumer.consume_once())
    case.send.assert_not_called()
    assert EventDelivery.objects.get().status == "pending"


def test_restart_after_success_does_not_send_again(wx_delivery_case):
    from aidev_wxbot.wxaibot.database_delivery import DatabaseResumeConsumer

    case = wx_delivery_case
    case.bus.publish(case.event)
    asyncio.run(case.consumer.consume_once())
    new_consumer = DatabaseResumeConsumer("app", "bot-original", case.send)
    assert not asyncio.run(new_consumer.consume_once())
    assert case.send.call_count == 1


def test_cancelled_sender_is_not_acknowledged(wx_delivery_case):
    case = wx_delivery_case
    case.bus.publish(case.event)
    case.send.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(case.consumer.consume_once())
    assert EventDelivery.objects.get().status == "processing"
    assert EventDelivery.objects.get().progress == 0
