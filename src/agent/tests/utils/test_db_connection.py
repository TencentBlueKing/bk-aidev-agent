from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_agent.utils import db_connection


def test_release_only_current_thread_autocommit_connections(monkeypatch):
    def database(atomic=False, autocommit=True, connected=True):
        return SimpleNamespace(
            connection=object() if connected else None,
            in_atomic_block=atomic,
            get_autocommit=lambda: autocommit,
            close=MagicMock(),
            alias="test",
        )

    databases = [database(), database(atomic=True), database(autocommit=False), database(connected=False)]
    connections = SimpleNamespace(all=MagicMock(return_value=databases))
    monkeypatch.setattr(db_connection, "connections", connections)
    monkeypatch.setattr(db_connection, "settings", SimpleNamespace(configured=True))

    db_connection.release_idle_connections()

    databases[0].close.assert_called_once_with()
    for retained in databases[1:]:
        retained.close.assert_not_called()
    connections.all.assert_called_once_with(initialized_only=True)


@pytest.mark.asyncio
async def test_async_thread_does_not_touch_orm_connections(monkeypatch):
    connections = MagicMock()
    monkeypatch.setattr(db_connection, "connections", connections)
    monkeypatch.setattr(db_connection, "settings", SimpleNamespace(configured=True))

    db_connection.release_idle_connections()

    connections.all.assert_not_called()
