# -*- coding: utf-8 -*-

import threading

import pytest
from aidev_bkplugin.packages.checkpoint.bk_django_saver import BKDjangoSaver
from django.db import OperationalError


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
    sleep = mocker.patch("aidev_bkplugin.packages.checkpoint.bk_django_saver.time.sleep")

    with pytest.raises(OperationalError) as exc_info:
        saver.put(*checkpoint_args)

    assert exc_info.value is error
    assert saver.checkpoint_model.objects.update_or_create.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [0.05, 0.1]
