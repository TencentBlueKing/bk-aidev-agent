# -*- coding: utf-8 -*-
"""凭证读取只恢复连接，禁止重放已成功的外部续期。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from aidev_agent.packages.resource_manager import base as resource_base


def test_recovers_connection_before_token_lookup(monkeypatch, fake_db_connection):
    fake_db_connection.connection.ensure_connection.side_effect = [
        fake_db_connection.OperationalError(2013, "lost"),
        None,
    ]
    lookup = MagicMock(return_value=SimpleNamespace(access_token="alice-token"))
    monkeypatch.setattr(resource_base, "bkoauth", SimpleNamespace(get_access_token_by_user=lookup))

    assert resource_base._get_access_token_by_user("alice") == "alice-token"
    lookup.assert_called_once_with("alice")
    fake_db_connection.connection.close.assert_called_once_with()


def test_refresh_is_not_replayed_when_token_save_disconnects(monkeypatch, fake_db_connection):
    refresh = MagicMock(return_value="new-token")
    save = MagicMock(side_effect=fake_db_connection.OperationalError(2013, "save failed"))

    def lookup(username):
        save(refresh())

    monkeypatch.setattr(resource_base, "bkoauth", SimpleNamespace(get_access_token_by_user=lookup))

    assert resource_base._get_access_token_by_user("alice") is None
    refresh.assert_called_once_with()
    save.assert_called_once_with("new-token")
    fake_db_connection.connection.close.assert_called_once_with()
