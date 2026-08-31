from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_bkplugin.services.event_resource_manager import EventResourceManager, with_database_events


@pytest.mark.parametrize("enabled", [False, True])
def test_injection_is_opt_in_and_preserves_original_resource_manager(settings, enabled):
    settings.AIDEV_DATABASE_EVENTS_ENABLED = enabled
    original = SimpleNamespace(username="author", get_agent_config=lambda: "custom-config")
    wrapped = with_database_events(original, "app")
    assert wrapped.get_agent_config() == "custom-config" and wrapped.username == "author"
    assert isinstance(wrapped, EventResourceManager) == enabled
    assert with_database_events(wrapped, "app") is wrapped


@pytest.mark.parametrize("failing", [False, True])
def test_publishing_cleans_producer_connections_even_on_error(monkeypatch, failing):
    calls = []
    monkeypatch.setattr(
        "aidev_bkplugin.services.event_resource_manager.close_old_connections",
        lambda: calls.append("cleanup"),
    )

    def publish(_event):
        calls.append("publish")
        if failing:
            raise RuntimeError("database unavailable")

    backend = Mock(publish=publish)
    wrapped = EventResourceManager(object(), backend)
    if failing:
        with pytest.raises(RuntimeError):
            wrapped.publish_event(object())
    else:
        wrapped.publish_event(object())
    assert calls == ["cleanup", "publish", "cleanup"]
    assert wrapped.event_publishing_enabled() is True
