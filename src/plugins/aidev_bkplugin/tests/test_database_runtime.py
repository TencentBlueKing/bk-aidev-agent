from concurrent.futures import ThreadPoolExecutor

import pytest
from aidev_bkplugin.database_runtime import install_database_connection_guard
from django.db import OperationalError, connection
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.sqlite3.base import DatabaseWrapper

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def connection_guard(monkeypatch):
    monkeypatch.setattr(BaseDatabaseWrapper, "_cursor", BaseDatabaseWrapper._cursor)
    install_database_connection_guard()
    installed = BaseDatabaseWrapper._cursor
    install_database_connection_guard()
    assert BaseDatabaseWrapper._cursor is installed


@pytest.mark.parametrize("alias", ["default", "other"])
def test_stale_connection_recovers_in_orm_thread(connection_guard, mocker, alias, tmp_path):
    settings = {**connection.settings_dict, "NAME": str(tmp_path / "guard.sqlite3")}

    def read_in_worker():
        database = DatabaseWrapper(settings, alias)
        database.ensure_connection()
        stale = mocker.MagicMock(wraps=database.connection)
        stale.cursor.side_effect = database.Database.OperationalError("connection closed during idle")
        database.connection = stale
        try:
            with database.cursor() as cursor:
                cursor.execute("SELECT 42")
                assert cursor.fetchone() == (42,)
            stale.close.assert_called_once_with()
        finally:
            database.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(read_in_worker).result()


def test_transaction_does_not_probe_or_replace_connection(connection_guard, mocker):
    database = DatabaseWrapper({**connection.settings_dict, "NAME": ":memory:"}, "transaction")
    database.ensure_connection()
    database.in_atomic_block = True
    raw_cursor = mocker.patch.object(database, "create_cursor", wraps=database.create_cursor)
    close = mocker.patch.object(database, "close", wraps=database.close)
    try:
        with database.cursor() as cursor:
            cursor.execute("SELECT 42")
        raw_cursor.assert_called_once_with(None)
        close.assert_not_called()
    finally:
        database.in_atomic_block = False
        database.close()


def test_business_sql_failure_is_not_replayed(connection_guard, mocker):
    database = DatabaseWrapper({**connection.settings_dict, "NAME": ":memory:"}, "write")
    create_cursor = mocker.patch.object(database, "create_cursor", wraps=database.create_cursor)
    try:
        with pytest.raises(OperationalError), database.cursor() as cursor:
            cursor.execute("INSERT INTO missing_table VALUES (1)")
        create_cursor.assert_called_once_with(None)
    finally:
        database.close()
