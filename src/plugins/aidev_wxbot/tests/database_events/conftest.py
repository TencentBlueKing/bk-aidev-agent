import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from ag_ui.core import CustomEvent
from aidev_agent.events import AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_READY
from aidev_bkplugin.services.database_event_bus import DatabaseEventBus

from .process_helpers import approval_record, runtime_events


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


@pytest.fixture
def wx_delivery_case(transactional_db, settings, monkeypatch):
    from aidev_wxbot.wxaibot.database_delivery import DatabaseResumeConsumer

    settings.BK_APIGW_MANAGER_URL_TMPL = "https://{api_name}.example.invalid"
    settings.AIDEV_GATEWAY_NAME, settings.BK_APIGW_STAGE = "test", "test"
    settings.BKPAAS_APP_CODE, settings.BKPAAS_APP_SECRET = "app", "test-only"
    monkeypatch.setattr(
        "aidev_bkplugin.services.agent_helpers.AgentHelper.build_session_detail_url",
        lambda session: f"https://agent.example.com/?session={session}",
    )
    bus = DatabaseEventBus("app")
    subscriber = "wxbot:" + hashlib.sha256(b"bot-original").hexdigest()
    bus.subscribe(
        subscriber,
        AIDEV_CHAT_RESUME_FINISHED,
        "session-original",
        property={"target": "original-group", "username": "author", "sessionCode": "session-original"},
    )
    event = CustomEvent(
        name=AIDEV_CHAT_RESUME_FINISHED,
        value={
            "schemaVersion": 1,
            "eventId": "delivery-1",
            "appCode": "app",
            "sessionCode": "session-original",
            "runId": "run-original",
            "turnId": "turn-original",
            "interruptIds": ["approval-original"],
            "events": runtime_events(),
            "persisted": True,
        },
    )
    send = AsyncMock()
    return SimpleNamespace(
        bus=bus, event=event, send=send, consumer=DatabaseResumeConsumer("app", "bot-original", send)
    )


@pytest.fixture
def approval_delivery_case(wx_delivery_case, monkeypatch):
    case = wx_delivery_case
    case.event.name = AIDEV_CHAT_RESUME_READY
    case.event.value.pop("events")
    case.event.value.pop("persisted")
    case.bus.subscribe(
        case.consumer.subscriber,
        AIDEV_CHAT_RESUME_READY,
        "session-original",
        property={"target": "original-group", "username": "author", "sessionCode": "session-original"},
    )
    case.history = MagicMock(return_value=[approval_record()])
    monkeypatch.setattr("aidev_wxbot.wxaibot.approval_notifications.SessionManager.list_session_contents", case.history)
    return case
