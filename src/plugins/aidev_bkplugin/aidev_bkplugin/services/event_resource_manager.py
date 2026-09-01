"""Per-agent publishing adapter; never replaces the global resource registry."""

from ag_ui.core import BaseEvent
from aidev_agent.config import settings as agent_settings
from django.db import close_old_connections


class EventResourceManager:
    def __init__(self, resource_manager, publisher):
        self._resource_manager = resource_manager
        self._publisher = publisher

    def __getattr__(self, name):
        return getattr(self._resource_manager, name)

    def event_publishing_enabled(self) -> bool:
        return True

    def publish_event(self, event: BaseEvent) -> None:
        # The Agent producer runs outside Django's request thread/lifecycle.
        try:
            close_old_connections()
            self._publisher.publish(event)
        finally:
            close_old_connections()


def with_database_events(resource_manager, app_code: str):
    if agent_settings.BKAI_DATABASE_EVENTS_ENABLED is not True:
        return resource_manager
    if isinstance(resource_manager, EventResourceManager):
        return resource_manager
    from aidev_agent.packages.resource_manager import resource_manager as factory

    from aidev_bkplugin.services.database_event_bus import DatabaseEventBus

    return EventResourceManager(resource_manager or factory(), DatabaseEventBus(app_code))
