# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

import pytest

from aidev_agent.utils import db_connection
from aidev_agent.utils.db_connection import call_with_reconnect


def test_success_runs_once_without_touching_connection(fake_db_connection):
    operation = MagicMock(return_value="ok")

    assert call_with_reconnect(operation, "读取") == "ok"

    assert operation.call_count == 1
    fake_db_connection.connection.close.assert_not_called()
    assert fake_db_connection.clock.sleeps == []


@pytest.mark.parametrize(
    "error_factory",
    [
        lambda db: db.OperationalError(2013, "Lost connection to MySQL server during query"),
        lambda db: db.OperationalError(2006, "MySQL server has gone away"),
        lambda db: db.InterfaceError(0, ""),
        lambda db: db.OperationalError(2002, "Can't connect to local MySQL server through socket"),
        lambda db: db.OperationalError(2003, "Can't connect to MySQL server on 'db'"),
    ],
)
def test_reconnectable_error_is_retried_until_success(fake_db_connection, error_factory):
    operation = MagicMock(side_effect=[error_factory(fake_db_connection), "ok"])

    assert call_with_reconnect(operation, "读取") == "ok"

    assert operation.call_count == 2
    fake_db_connection.connection.close.assert_called_once_with()
    # 首次重试立即发起，不做退避等待
    assert fake_db_connection.clock.sleeps == []


def test_retries_with_backoff_within_window_until_success(fake_db_connection):
    lost = fake_db_connection.OperationalError(2013, "lost")
    operation = MagicMock(side_effect=[lost, lost, lost, "ok"])

    assert call_with_reconnect(operation, "读取") == "ok"

    assert operation.call_count == 4
    assert fake_db_connection.connection.close.call_count == 3
    assert fake_db_connection.clock.sleeps == [0.5, 1.0]


def test_gives_up_after_max_attempts_and_raises_last_error(fake_db_connection):
    errors = [
        fake_db_connection.OperationalError(2013, f"lost {index}")
        for index in range(db_connection.RECONNECT_MAX_ATTEMPTS)
    ]
    operation = MagicMock(side_effect=errors)

    with pytest.raises(fake_db_connection.OperationalError) as exc_info:
        call_with_reconnect(operation, "读取")

    assert exc_info.value is errors[-1]
    assert operation.call_count == db_connection.RECONNECT_MAX_ATTEMPTS
    # 每次准备重试前丢弃连接；最后一次失败后已无重试，不再丢弃
    assert fake_db_connection.connection.close.call_count == db_connection.RECONNECT_MAX_ATTEMPTS - 1
    assert fake_db_connection.clock.sleeps == [0.5, 1.0, 2.0]


def test_stops_when_next_wait_would_exceed_the_window(fake_db_connection, monkeypatch):
    monkeypatch.setattr(db_connection, "RECONNECT_BUDGET_SECONDS", 1.0)
    lost = fake_db_connection.OperationalError(2013, "lost")
    operation = MagicMock(side_effect=[lost, lost, lost, lost])

    with pytest.raises(fake_db_connection.OperationalError):
        call_with_reconnect(operation, "读取")

    # 第 3 次失败后再等 1.0 秒，总耗时将达到 1.5 秒，超出 1.0 秒窗口，因此只尝试 3 次
    assert operation.call_count == 3
    assert fake_db_connection.clock.sleeps == [0.5]


def test_other_database_error_is_not_retried(fake_db_connection):
    error = fake_db_connection.OperationalError(1146, "table doesn't exist")
    operation = MagicMock(side_effect=error)

    with pytest.raises(fake_db_connection.OperationalError) as exc_info:
        call_with_reconnect(operation, "读取")

    assert exc_info.value is error
    assert operation.call_count == 1
    fake_db_connection.connection.close.assert_not_called()


def test_non_database_error_is_not_retried(fake_db_connection):
    operation = MagicMock(side_effect=ValueError("boom"))

    with pytest.raises(ValueError):
        call_with_reconnect(operation, "读取")

    assert operation.call_count == 1
    fake_db_connection.connection.close.assert_not_called()


def test_close_failure_does_not_block_the_retry(fake_db_connection):
    fake_db_connection.connection.close.side_effect = RuntimeError("close failed")
    operation = MagicMock(side_effect=[fake_db_connection.OperationalError(2013, "lost"), "ok"])

    assert call_with_reconnect(operation, "读取") == "ok"
    assert operation.call_count == 2


def test_without_django_the_operation_runs_once_and_errors_propagate(monkeypatch):
    """宿主未安装 Django 时没有可重建的连接，判断全部退化，调用原样执行。"""
    monkeypatch.setattr(db_connection, "OperationalError", None)
    monkeypatch.setattr(db_connection, "InterfaceError", None)
    monkeypatch.setattr(db_connection, "connection", None)
    error = Exception(2013, "lost")
    operation = MagicMock(side_effect=error)

    with pytest.raises(Exception) as exc_info:
        call_with_reconnect(operation, "读取")

    assert exc_info.value is error
    assert operation.call_count == 1
