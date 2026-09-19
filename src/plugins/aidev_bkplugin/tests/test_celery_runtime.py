# -*- coding: utf-8 -*-

from types import ModuleType, SimpleNamespace

import pytest
from aidev_bkplugin import settings as plugin_settings
from aidev_bkplugin.celery_runtime import (
    BROKER_LOSS_EXIT_SETTINGS,
    apply_celery_exit_on_broker_loss,
    install_celery_exit_on_broker_loss,
    is_celery_worker,
)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["celery", "-A", "blueapps.core.celery", "worker", "-P", "threads"], True),
        (["/usr/local/bin/celery", "-A", "test_app", "worker"], True),
        (["manage.py", "celery", "worker", "-B"], True),
        (["bin/manage.py", "celery", "-A", "test_app", "worker"], True),
        (["celery", "-A", "blueapps.core.celery", "beat"], False),
        (["manage.py", "celery", "beat", "-l", "info"], False),
        (["gunicorn", "wsgi:application"], False),
        (["manage.py", "runserver"], False),
        ([], False),
    ],
)
def test_is_celery_worker_detects_worker_only(argv, expected):
    assert is_celery_worker(argv) is expected


def test_apply_celery_exit_on_broker_loss_disables_reconnect_after_connect():
    app = SimpleNamespace(conf=SimpleNamespace())

    apply_celery_exit_on_broker_loss(app)

    assert app.conf.broker_connection_retry is False
    assert app.conf.broker_connection_retry_on_startup is True
    assert app.conf.worker_cancel_long_running_tasks_on_connection_loss is True


def test_install_applies_when_celery_is_available(mocker):
    app = SimpleNamespace(conf=SimpleNamespace())
    celery_mod = ModuleType("celery")
    celery_mod.current_app = app
    mocker.patch.dict("sys.modules", {"celery": celery_mod})

    assert install_celery_exit_on_broker_loss(["celery", "-A", "app", "worker"]) is True
    assert app.conf.broker_connection_retry is False
    assert app.conf.broker_connection_retry_on_startup is True


def test_plugin_settings_disable_broker_reconnect_after_connect():
    for name, value in BROKER_LOSS_EXIT_SETTINGS.items():
        assert getattr(plugin_settings, name) is value


def test_install_skips_non_worker_process():
    assert install_celery_exit_on_broker_loss(["gunicorn", "wsgi:application"]) is False
