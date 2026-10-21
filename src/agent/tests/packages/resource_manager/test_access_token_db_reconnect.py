# -*- coding: utf-8 -*-
"""bkoauth 取 access_token 时的数据库连接失效处理。

回归点：会话线程在长时间 LLM 调用后复用已被服务端关闭的连接，bkoauth 读取报 2013；
失效连接必须被丢弃并重试，否则同一线程后续所有 ORM 访问都会复用这条坏连接。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_agent.packages.resource_manager import base as resource_base
from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.utils import db_connection


class _StubResourceManager(BaseResourceManager):
    def get_client(self, **kwargs):
        raise NotImplementedError


@pytest.fixture
def bkoauth_lookup(monkeypatch):
    lookup = MagicMock()
    monkeypatch.setattr(resource_base, "bkoauth", SimpleNamespace(get_access_token_by_user=lookup))
    return lookup


def test_returns_access_token_on_success(bkoauth_lookup, fake_db_connection):
    bkoauth_lookup.return_value = SimpleNamespace(access_token="alice-token")

    assert resource_base._get_access_token_by_user("alice") == "alice-token"
    assert bkoauth_lookup.call_count == 1


def test_connection_lost_is_retried_once_before_returning_token(bkoauth_lookup, fake_db_connection):
    fake_db_connection.connection.ensure_connection.side_effect = [
        fake_db_connection.OperationalError(2013, "Lost connection to MySQL server during query"),
        None,
    ]
    bkoauth_lookup.return_value = SimpleNamespace(access_token="alice-token")

    assert resource_base._get_access_token_by_user("alice") == "alice-token"
    assert bkoauth_lookup.call_count == 1
    fake_db_connection.connection.close.assert_called_once_with()


def test_database_error_degrades_to_none_without_replaying_refresh(bkoauth_lookup, fake_db_connection):
    error = fake_db_connection.OperationalError(2013, "Lost connection to MySQL server during query")
    bkoauth_lookup.side_effect = [error] * db_connection.RECONNECT_MAX_ATTEMPTS

    assert resource_base._get_access_token_by_user("alice") is None
    assert bkoauth_lookup.call_count == 1
    fake_db_connection.connection.close.assert_called_once_with()


def test_resolve_access_token_degrades_to_empty_string_after_retries_exhausted(bkoauth_lookup, fake_db_connection):
    error = fake_db_connection.OperationalError(2013, "Lost connection to MySQL server during query")
    bkoauth_lookup.side_effect = [error] * db_connection.RECONNECT_MAX_ATTEMPTS
    manager = _StubResourceManager(username="alice")

    assert manager.resolve_access_token() == ""


def test_resolve_access_token_keeps_empty_string_when_user_has_no_token(bkoauth_lookup, fake_db_connection):
    bkoauth_lookup.return_value = None
    manager = _StubResourceManager(username="alice")

    assert manager.resolve_access_token() == ""


def test_non_database_error_still_degrades_to_none(bkoauth_lookup, fake_db_connection):
    bkoauth_lookup.side_effect = ConnectionError("bkoauth timeout")

    assert resource_base._get_access_token_by_user("alice") is None
    assert bkoauth_lookup.call_count == 1
    fake_db_connection.connection.close.assert_not_called()


def test_refresh_is_not_replayed_when_token_save_disconnects(monkeypatch, fake_db_connection):
    refresh = MagicMock(return_value="new-token")
    save = MagicMock(side_effect=fake_db_connection.OperationalError(2013, "save failed"))

    def lookup(username):
        token = refresh()
        save(token)

    monkeypatch.setattr(resource_base, "bkoauth", SimpleNamespace(get_access_token_by_user=lookup))

    assert resource_base._get_access_token_by_user("alice") is None

    refresh.assert_called_once_with()
    save.assert_called_once_with("new-token")
    fake_db_connection.connection.close.assert_called_once_with()
