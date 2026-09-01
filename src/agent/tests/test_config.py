import runpy

import pytest
from aidev_agent import config
from aidev_agent.config import BKAI_EVENT_DATABASE_ENABLED, settings


def test_database_events_setting_is_registered_in_agent_config():
    assert settings.BKAI_EVENT_DATABASE_ENABLED is BKAI_EVENT_DATABASE_ENABLED


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, True),
        ("1", True),
        ("0", False),
        ("true", True),
        ("false", False),
    ],
)
def test_database_events_environment_default_and_override(monkeypatch, value, expected):
    name = "BKAI_EVENT_DATABASE_ENABLED"
    monkeypatch.delenv(name, raising=False)
    if value is not None:
        monkeypatch.setenv(name, value)

    module = runpy.run_path(config.__file__)
    assert module[name] is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("25000", 25000), ("999", 10_000)],
)
def test_metrics_export_interval_environment_override_and_minimum(monkeypatch, value, expected):
    name = "BKAI_AGENT_METRICS_EXPORT_INTERVAL_MILLIS"
    monkeypatch.delenv(name, raising=False)
    if value is not None:
        monkeypatch.setenv(name, value)

    module = runpy.run_path(config.__file__)
    assert module[name] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "celery"), (" Direct ", "direct")],
)
def test_metrics_push_mode_environment_default_and_override(monkeypatch, value, expected):
    name = "BKAI_AGENT_METRICS_PUSH_MODE"
    monkeypatch.delenv(name, raising=False)
    if value is not None:
        monkeypatch.setenv(name, value)

    module = runpy.run_path(config.__file__)
    assert module[name] == expected
