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


def test_publishing_uses_injected_backend():
    backend = Mock()
    wrapped = EventResourceManager(object(), backend)
    event = object()
    wrapped.publish_event(event)
    backend.publish.assert_called_once_with(event)
    assert wrapped.event_publishing_enabled() is True
