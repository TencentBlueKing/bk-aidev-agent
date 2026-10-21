# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

import pytest
from aidev_agent.utils import db_connection
from aidev_agent.utils.db_connection import call_with_healthy_connection, call_with_reconnect


@pytest.mark.parametrize(
    "error_type, code", [("OperationalError", 2013), ("OperationalError", 2003), ("InterfaceError", 0)]
)
def test_reconnects_before_retry(fake_db_connection, error_type, code):
    error = getattr(fake_db_connection, error_type)(code, "lost")
    operation = MagicMock(side_effect=[error, "ok"])

    assert call_with_reconnect(operation, "读取") == "ok"
    assert operation.call_count == 2
    fake_db_connection.connection.close.assert_called_once_with()
    assert fake_db_connection.clock.sleeps == []


@pytest.mark.parametrize("budget, attempts, sleeps", [(5.0, 5, [0.5, 1.0, 2.0]), (1.0, 3, [0.5])])
def test_retry_limits_release_last_connection(fake_db_connection, monkeypatch, budget, attempts, sleeps):
    monkeypatch.setattr(db_connection, "RECONNECT_BUDGET_SECONDS", budget)
    errors = [fake_db_connection.OperationalError(2013, f"lost {i}") for i in range(5)]
    operation = MagicMock(side_effect=errors)

    with pytest.raises(fake_db_connection.OperationalError) as exc_info:
        call_with_reconnect(operation, "读取")

    assert exc_info.value is errors[attempts - 1]
    assert operation.call_count == fake_db_connection.connection.close.call_count == attempts
    assert fake_db_connection.clock.sleeps == sleeps


@pytest.mark.parametrize("database_error", [True, False])
def test_unrelated_errors_are_not_retried(fake_db_connection, database_error):
    error = fake_db_connection.OperationalError(1146, "missing table") if database_error else ValueError("boom")
    operation = MagicMock(side_effect=error)

    with pytest.raises(type(error)) as exc_info:
        call_with_reconnect(operation, "读取")

    assert exc_info.value is error
    operation.assert_called_once_with()
    fake_db_connection.connection.close.assert_not_called()


def test_health_check_recovers_before_operation(fake_db_connection):
    fake_db_connection.connection.is_usable.side_effect = [False, True]
    operation = MagicMock(return_value="ok")

    assert call_with_healthy_connection(operation, "凭证") == "ok"
    operation.assert_called_once_with()
    fake_db_connection.connection.close.assert_called_once_with()


def test_failed_preflight_does_not_call_operation(fake_db_connection):
    fake_db_connection.connection.ensure_connection.side_effect = fake_db_connection.OperationalError(
        2003, "unavailable"
    )
    operation = MagicMock()

    with pytest.raises(fake_db_connection.OperationalError):
        call_with_healthy_connection(operation, "凭证")

    operation.assert_not_called()
    assert fake_db_connection.connection.close.call_count == db_connection.RECONNECT_MAX_ATTEMPTS


@pytest.mark.parametrize("without_django", [False, True])
def test_operation_runs_once_without_preflight(fake_db_connection, monkeypatch, without_django):
    if without_django:
        monkeypatch.setattr(db_connection, "connection", None)
    else:
        fake_db_connection.connection.in_atomic_block = True
    operation = MagicMock(return_value="ok")

    assert call_with_healthy_connection(operation, "凭证") == "ok"
    operation.assert_called_once_with()
    fake_db_connection.connection.ensure_connection.assert_not_called()
    fake_db_connection.connection.is_usable.assert_not_called()
