import pytest
from ag_ui.core import CustomEvent, RunStartedEvent
from aidev_agent.events import LocalEventBus


@pytest.mark.parametrize(
    "event,name",
    [(CustomEvent(name="demo", value={}), "demo"), (RunStartedEvent(thread_id="t", run_id="r"), "RUN_STARTED")],
)
def test_dispatch_and_idempotent_unsubscribe(event, name):
    bus, seen = LocalEventBus(), []
    unsubscribe = bus.subscribe(name, seen.append)
    bus.publish(event)
    unsubscribe()
    unsubscribe()
    bus.publish(event)
    assert seen == [event]
    assert seen[0] is not event


def test_failure_does_not_skip_other_listeners_or_mutate_payload():
    bus, seen = LocalEventBus(), []
    event = CustomEvent(name="demo", value={"ok": True})

    def failing(value):
        value.value.clear()
        raise ValueError("listener failed")

    bus.subscribe("demo", failing)
    bus.subscribe("demo", seen.append)
    with pytest.raises(ExceptionGroup):
        bus.publish(event)
    assert seen[0].value == event.value == {"ok": True}


def test_listener_can_unsubscribe_during_dispatch():
    bus, seen = LocalEventBus(), []
    unsubscribe = bus.subscribe("demo", lambda _: unsubscribe())
    bus.subscribe("demo", seen.append)
    bus.publish(CustomEvent(name="demo", value={}))
    bus.publish(CustomEvent(name="demo", value={}))
    assert len(seen) == 2
