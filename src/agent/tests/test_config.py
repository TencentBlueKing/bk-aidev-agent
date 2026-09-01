import runpy

import pytest
from aidev_agent import config
from aidev_agent.config import BKAI_AGENT_QUEUE_METRIC, BKAI_EVENT_DATABASE_ENABLED, settings


def test_database_events_setting_is_registered_in_agent_config():
    assert settings.BKAI_EVENT_DATABASE_ENABLED is BKAI_EVENT_DATABASE_ENABLED


def test_metric_queue_name_is_registered_in_agent_config():
    assert BKAI_AGENT_QUEUE_METRIC == "BKAI_AGENT_QUEUE_METRIC"
    assert settings.BKAI_AGENT_QUEUE_METRIC is BKAI_AGENT_QUEUE_METRIC


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
    [(None, None), (" Direct ", "direct")],
)
def test_metrics_push_mode_environment_override(monkeypatch, value, expected):
    name = "BKAI_AGENT_METRICS_PUSH_MODE"
    monkeypatch.delenv(name, raising=False)
    if value is not None:
        monkeypatch.setenv(name, value)

    module = runpy.run_path(config.__file__)
    assert module[name] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("1800", 1800), ("0", 1)],
)
def test_metrics_task_ttl_environment_override_and_minimum(monkeypatch, value, expected):
    name = "BKAI_AGENT_METRICS_TASK_TTL_SECONDS"
    monkeypatch.delenv(name, raising=False)
    if value is not None:
        monkeypatch.setenv(name, value)

    module = runpy.run_path(config.__file__)
    assert module[name] == expected
