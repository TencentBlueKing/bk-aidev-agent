# -*- coding: utf-8 -*-
"""bkoauth 取 access_token 时的数据库连接失效处理。

回归点：数据库错误曾被 ``_get_access_token_by_user`` 吞成 None，``build_executor_info`` 随之静默降级为空凭证，
下游只能返回难以定位的鉴权失败。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from aidev_agent.packages.resource_manager import base as resource_base
from aidev_agent.packages.resource_manager.base import BaseResourceManager


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
    bkoauth_lookup.side_effect = [
        fake_db_connection.OperationalError(2013, "Lost connection to MySQL server during query"),
        SimpleNamespace(access_token="alice-token"),
    ]

    assert resource_base._get_access_token_by_user("alice") == "alice-token"
    assert bkoauth_lookup.call_count == 2
    fake_db_connection.connection.close.assert_called_once_with()


def test_database_error_is_raised_instead_of_returning_none(bkoauth_lookup, fake_db_connection):
    error = fake_db_connection.OperationalError(2013, "Lost connection to MySQL server during query")
    bkoauth_lookup.side_effect = [error, error]

    with pytest.raises(fake_db_connection.OperationalError):
        resource_base._get_access_token_by_user("alice")

    assert bkoauth_lookup.call_count == 2


def test_resolve_access_token_propagates_database_error(bkoauth_lookup, fake_db_connection):
    error = fake_db_connection.OperationalError(2013, "Lost connection to MySQL server during query")
    bkoauth_lookup.side_effect = [error, error]
    manager = _StubResourceManager(username="alice")

    with pytest.raises(fake_db_connection.OperationalError):
        manager.resolve_access_token()


def test_resolve_access_token_keeps_empty_string_when_user_has_no_token(bkoauth_lookup, fake_db_connection):
    bkoauth_lookup.return_value = None
    manager = _StubResourceManager(username="alice")

    assert manager.resolve_access_token() == ""


def test_non_database_error_still_degrades_to_none(bkoauth_lookup, fake_db_connection):
    bkoauth_lookup.side_effect = ConnectionError("bkoauth timeout")

    assert resource_base._get_access_token_by_user("alice") is None
    assert bkoauth_lookup.call_count == 1
    fake_db_connection.connection.close.assert_not_called()
