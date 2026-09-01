# -*- coding: utf-8 -*-

import threading

import pytest
from aidev_bkplugin.packages.checkpoint.bk_django_saver import BKDjangoSaver, _database_write_lock, bulk_upsert
from django.db import OperationalError, connection, models


class WriteForTest(models.Model):
    thread_id = models.CharField(max_length=255)
    checkpoint_ns = models.CharField(max_length=255, default="")
    checkpoint_id = models.CharField(max_length=255)
    task_id = models.CharField(max_length=255)
    idx = models.IntegerField()
    channel = models.TextField()
    type = models.TextField(null=True, blank=True)
    value = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        app_label = "tests"


@pytest.fixture
def saver(mocker):
    instance = object.__new__(BKDjangoSaver)
    instance.lock = threading.Lock()
    instance.checkpoint_model = mocker.Mock()
    instance.serde = mocker.Mock()
    instance.serde.dumps_typed.return_value = ("json", b"checkpoint")
    return instance


@pytest.fixture
def checkpoint_args():
    return (
        {"configurable": {"thread_id": "thread-id"}},
        {"id": "checkpoint-id"},
        {},
        {},
    )


@pytest.mark.parametrize("error_code", [1205, 1213])
def test_put_retries_transient_database_lock_error(mocker, saver, checkpoint_args, error_code):
    saver.checkpoint_model.objects.update_or_create.side_effect = [
        OperationalError(error_code, "retryable"),
        (mocker.Mock(), True),
    ]
    close_old_connections = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.close_old_connections")
    sleep = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.time.sleep")

    saver.put(*checkpoint_args)

    assert saver.checkpoint_model.objects.update_or_create.call_count == 2
    close_old_connections.assert_called_once_with()
    sleep.assert_called_once_with(0.05)


def test_put_does_not_retry_other_database_error(mocker, saver, checkpoint_args):
    error = OperationalError(2006, "server has gone away")
    saver.checkpoint_model.objects.update_or_create.side_effect = error
    sleep = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.time.sleep")

    with pytest.raises(OperationalError) as exc_info:
        saver.put(*checkpoint_args)

    assert exc_info.value is error
    assert saver.checkpoint_model.objects.update_or_create.call_count == 1
    sleep.assert_not_called()


def test_put_raises_after_database_lock_retries_exhausted(mocker, saver, checkpoint_args):
    error = OperationalError(1213, "deadlock")
    saver.checkpoint_model.objects.update_or_create.side_effect = error
    mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.close_old_connections")
    sleep = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.time.sleep")

    with pytest.raises(OperationalError) as exc_info:
        saver.put(*checkpoint_args)

    assert exc_info.value is error
    assert saver.checkpoint_model.objects.update_or_create.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [0.05, 0.1]


def test_put_retries_sqlite_database_locked_error(mocker, saver, checkpoint_args):
    saver.checkpoint_model.objects.update_or_create.side_effect = [
        OperationalError("database is locked"),
        (mocker.Mock(), True),
    ]
    mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.router.db_for_write", return_value="default")
    connections = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.connections")
    connections.__getitem__.return_value.vendor = "sqlite"
    sleep = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.time.sleep")

    saver.put(*checkpoint_args)

    assert saver.checkpoint_model.objects.update_or_create.call_count == 2
    sleep.assert_called_once_with(0.05)


def test_database_write_lock_serializes_sqlite_saver_instances(mocker):
    model = mocker.Mock()
    mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.router.db_for_write", return_value="default")
    connections = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.connections")
    connections.__getitem__.return_value.vendor = "sqlite"
    first_entered = threading.Event()
    second_entered = threading.Event()
    release = threading.Event()

    def hold_lock(entered):
        with _database_write_lock(model):
            entered.set()
            release.wait(timeout=1)

    first = threading.Thread(target=hold_lock, args=(first_entered,))
    second = threading.Thread(target=hold_lock, args=(second_entered,))
    first.start()
    assert first_entered.wait(timeout=1)
    second.start()
    assert not second_entered.wait(timeout=0.1)
    release.set()
    first.join(timeout=1)
    second.join(timeout=1)
    assert second_entered.is_set()


def test_database_write_lock_keeps_mysql_writes_parallel(mocker):
    model = mocker.Mock()
    mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.router.db_for_write", return_value="default")
    connections = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.connections")
    connections.__getitem__.return_value.vendor = "mysql"
    entered = threading.Event()

    def take_lock():
        with _database_write_lock(model):
            entered.set()

    with _database_write_lock(model):
        contender = threading.Thread(target=take_lock)
        contender.start()
        assert entered.wait(timeout=1)
    contender.join(timeout=1)


@pytest.fixture
def write_obj():
    return WriteForTest(
        thread_id="thread-id",
        checkpoint_ns="",
        checkpoint_id="checkpoint-id",
        task_id="task-id",
        idx=0,
        channel="channel",
        type="json",
        value=b"1",
    )


@pytest.fixture
def write_model(transactional_db, django_db_blocker):
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.create_model(WriteForTest)
    yield WriteForTest
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.delete_model(WriteForTest)


def test_bulk_upsert_non_mysql_without_unique_constraint_creates_record(write_model, write_obj):
    fields = ["thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"]

    bulk_upsert(write_model, [write_obj], ["channel", "type", "value"], fields)

    saved = write_model.objects.get()
    assert (saved.channel, saved.type, saved.value) == ("channel", "json", b"1")


@pytest.mark.parametrize("vendor", ["sqlite", "postgresql"])
def test_bulk_upsert_non_mysql_updates_latest_duplicate_record(mocker, write_model, write_obj, vendor):
    connections = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.connections")
    connections.__getitem__.return_value.vendor = vendor
    lookup = {
        "thread_id": write_obj.thread_id,
        "checkpoint_ns": write_obj.checkpoint_ns,
        "checkpoint_id": write_obj.checkpoint_id,
        "task_id": write_obj.task_id,
        "idx": write_obj.idx,
    }
    older = write_model.objects.create(**lookup, channel="older", type="json", value=b"older")
    latest = write_model.objects.create(**lookup, channel="latest", type="json", value=b"latest")
    write_obj.channel = "updated"
    write_obj.value = b"updated"

    bulk_upsert(
        write_model,
        [write_obj],
        ["channel", "type", "value"],
        ["thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"],
    )

    older.refresh_from_db()
    latest.refresh_from_db()
    assert (older.channel, older.value) == ("older", b"older")
    assert (latest.channel, latest.value) == ("updated", b"updated")


def test_bulk_upsert_preserves_mysql_native_upsert(mocker, write_obj):
    connection = mocker.MagicMock(vendor="mysql")
    cursor = connection.cursor.return_value.__enter__.return_value
    connections = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.connections")
    connections.__getitem__.return_value = connection
    mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.router.db_for_write", return_value="default")
    mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.transaction.atomic")

    bulk_upsert(
        WriteForTest,
        [write_obj],
        ["channel", "type", "value"],
        ["thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"],
    )

    sql, params = cursor.executemany.call_args.args
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert params == [["thread-id", "", "checkpoint-id", "task-id", 0, "channel", "json", b"1"]]
