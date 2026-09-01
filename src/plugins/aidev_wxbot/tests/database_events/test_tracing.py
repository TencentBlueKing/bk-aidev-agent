import asyncio

from aidev_agent.utils import tracing
from aidev_bkplugin.models import EventDelivery


def test_publish_claim_consume_share_entry_trace(wx_delivery_case, wxbot_spans):
    case = wx_delivery_case
    with tracing.recording_span("web.entry") as entry:
        case.event.value["traceContext"] = tracing.trace_headers()
    original = dict(case.event.value["traceContext"])
    with tracing.recording_span("unrelated-worker"):
        case.bus.publish(case.event)
        case.bus.publish(case.event)
        asyncio.run(case.consumer.consume_once())
    recorded = [
        span
        for span in wxbot_spans.get_finished_spans()
        if span.name in ("database_event.publish", "database_event.claim", "wxbot.event.consume")
    ]
    assert len(recorded) == 4
    assert all(span.context.trace_id == entry.get_span_context().trace_id for span in recorded)
    claim = next(span for span in recorded if span.name == "database_event.claim")
    assert claim.attributes["messaging.message.age_ms"] >= 0
    assert claim.attributes["messaging.receive.lookup.duration_ms"] >= 0
    assert claim.attributes["messaging.delivery.attempt"] == 1
    delivery = EventDelivery.objects.get()
    assert delivery.status == "delivered" and delivery.envelope["value"]["traceContext"] == original
