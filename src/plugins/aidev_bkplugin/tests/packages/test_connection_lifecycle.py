import pytest
from aidev_bkplugin.packages.checkpoint.bk_django_saver import run_db_in_thread
from django.db import connections

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.anyio
async def test_orm_worker_returns_connection_even_with_long_max_age():
    def worker():
        database = connections["default"]
        original_max_age = database.settings_dict["CONN_MAX_AGE"]
        database.settings_dict["CONN_MAX_AGE"] = 600
        database.ensure_connection()
        database.settings_dict["CONN_MAX_AGE"] = original_max_age
        return database

    database = await run_db_in_thread(worker)
    assert database.connection is None


@pytest.fixture
def anyio_backend():
    return "asyncio"
