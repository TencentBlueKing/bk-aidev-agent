from types import SimpleNamespace

import pytest
from ag_ui.core import CustomEvent
from aidev_agent.events import AIDEV_CHAT_RESUME_FINISHED
from aidev_bkplugin.services.database_event_bus import DatabaseEventBus


@pytest.fixture(scope="session")
def django_db_modify_db_settings(tmp_path_factory):
    from django.conf import settings

    settings.DATABASES["default"]["TEST"]["NAME"] = str(tmp_path_factory.mktemp("event-db") / "events.sqlite3")


@pytest.fixture
def event_case(db):
    bus = DatabaseEventBus("app")
    subscription = bus.subscribe("wxbot:test", AIDEV_CHAT_RESUME_FINISHED, "session", property={"target": "user"})
    event = CustomEvent(
        name=AIDEV_CHAT_RESUME_FINISHED,
        value={
            "eventId": "event-1",
            "appCode": "app",
            "sessionCode": "session",
            "events": [],
        },
    )
    return SimpleNamespace(bus=bus, subscription=subscription, event=event)
