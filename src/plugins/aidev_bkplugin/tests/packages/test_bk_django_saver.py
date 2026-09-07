# -*- coding: utf-8 -*-

import threading

import pytest
from aidev_bkplugin.packages.checkpoint.bk_django_saver import BKDjangoSaver, bulk_upsert
from django.db import OperationalError, connection, models
from langgraph.checkpoint.base import WRITES_IDX_MAP


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


class WriteWithTaskPathForTest(models.Model):
    """模拟新版业务方 writes_model：带 task_path 列（NOT NULL 无 SQL default）。

    复现 langgraph 上游给 put_writes 加 task_path 参数后，业务方按新示例
    在 model 里加了 task_path 字段时，MySQL 严格模式下 1364 的场景。
    """

    thread_id = models.CharField(max_length=255)
    checkpoint_ns = models.CharField(max_length=255, default="")
    checkpoint_id = models.CharField(max_length=255)
    task_id = models.CharField(max_length=255)
    task_path = models.TextField()
    idx = models.IntegerField()
    channel = models.TextField()
    type = models.TextField(null=True, blank=True)
    value = models.BinaryField()

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


# ---------- put_writes task_path 兼容性测试（修复 MySQL 1364） ----------


def _make_put_writes_saver(mocker, writes_model, has_task_path):
    """构造一个绕过 __init__ 校验的 saver 实例，用于测 put_writes 分支。"""
    saver = object.__new__(BKDjangoSaver)
    saver.lock = threading.Lock()
    saver.writes_model = writes_model
    saver._writes_has_task_path = has_task_path
    saver.serde = mocker.Mock()
    saver.serde.dumps_typed.return_value = ("json", b"v")
    return saver


def _put_writes_config():
    return {
        "configurable": {
            "thread_id": "t",
            "checkpoint_ns": "",
            "checkpoint_id": "c",
        }
    }


def test_writes_has_task_path_detection_true():
    """__init__ 探测逻辑：writes_model 声明 task_path 时应识别为 True。"""
    has = any(f.name == "task_path" for f in WriteWithTaskPathForTest._meta.get_fields())
    assert has is True


def test_writes_has_task_path_detection_false():
    """__init__ 探测逻辑：老版 model 未声明 task_path 时应识别为 False，走兼容路径。"""
    has = any(f.name == "task_path" for f in WriteForTest._meta.get_fields())
    assert has is False


def test_put_writes_new_model_appends_task_path_to_update_fields_and_write_obj(mocker):
    """新版 model（含 task_path）走 upsert 分支时：

    1. bulk_upsert 的 update_fields 应追加 "task_path"（否则原生 SQL INSERT
       缺列，MySQL 严格模式抛 1364）
    2. 构造的 write_obj 上应实际写入 task_path 值
    """
    saver = _make_put_writes_saver(mocker, WriteWithTaskPathForTest, has_task_path=True)
    bulk_upsert_mock = mocker.patch(
        "aidev_bkplugin.packages.checkpoint.bk_django_saver.bulk_upsert"
    )

    # 用 WRITES_IDX_MAP 里任一 key 作为 channel，确保命中 upsert 分支
    channel_key = next(iter(WRITES_IDX_MAP.keys()))
    saver.put_writes(
        _put_writes_config(),
        [(channel_key, "v")],
        "task-id",
        task_path="('__pregel_pull','agent')",
    )

    call = bulk_upsert_mock.call_args
    # bulk_upsert(model, objs, update_fields=..., unique_fields=...) —— 关键字调用
    update_fields = call.kwargs["update_fields"]
    unique_fields = call.kwargs["unique_fields"]
    writes_objects = call.args[1]

    assert "task_path" in update_fields, f"update_fields 缺 task_path: {update_fields}"
    # 保底断言：unique_fields 没被误改
    assert unique_fields == ["thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"]
    # write_obj 上实际写入了 task_path
    assert writes_objects[0].task_path == "('__pregel_pull','agent')"


def test_put_writes_old_model_skips_task_path(mocker):
    """老版 model（无 task_path）走 upsert 分支时：

    1. update_fields 不应包含 "task_path"
    2. 构造 write_obj 时不应传 task_path kwarg（否则 model(**kwargs) 抛
       TypeError: unexpected keyword）
    3. 即使 langgraph 上游传了 task_path，也不能挂
    """
    saver = _make_put_writes_saver(mocker, WriteForTest, has_task_path=False)
    bulk_upsert_mock = mocker.patch(
        "aidev_bkplugin.packages.checkpoint.bk_django_saver.bulk_upsert"
    )

    channel_key = next(iter(WRITES_IDX_MAP.keys()))
    # 老 model，但上游依然会传 task_path —— 必须能兼容
    saver.put_writes(
        _put_writes_config(),
        [(channel_key, "v")],
        "task-id",
        task_path="whatever",
    )

    call = bulk_upsert_mock.call_args
    update_fields = call.kwargs["update_fields"]
    writes_objects = call.args[1]

    assert "task_path" not in update_fields
    # 老 model 没这个字段，实例上也不该出现属性
    assert not hasattr(writes_objects[0], "task_path")


def test_put_writes_new_model_falsy_task_path_falls_back_to_empty_string(mocker):
    """langgraph 上游可能传 None / 空串（异常场景），saver 应兜底为空串。

    避免把 None 塞给 NOT NULL 字段 —— 虽然 Django ORM 层会转成 SQL NULL 而不
    是 1364，但语义上 task_path 应该始终是字符串。
    """
    saver = _make_put_writes_saver(mocker, WriteWithTaskPathForTest, has_task_path=True)
    bulk_upsert_mock = mocker.patch(
        "aidev_bkplugin.packages.checkpoint.bk_django_saver.bulk_upsert"
    )

    channel_key = next(iter(WRITES_IDX_MAP.keys()))
    # 场景 1: task_path=None
    saver.put_writes(_put_writes_config(), [(channel_key, "v")], "task-id", task_path=None)
    # 场景 2: 走默认值（未传参 → 默认 ""）
    saver.put_writes(_put_writes_config(), [(channel_key, "v")], "task-id")

    # 两次调用的 write_obj 的 task_path 都应是空串
    assert bulk_upsert_mock.call_count == 2
    for call in bulk_upsert_mock.call_args_list:
        writes_objects = call.args[1]
        assert writes_objects[0].task_path == ""
