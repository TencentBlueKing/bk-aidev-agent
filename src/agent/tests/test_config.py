import pytest
from aidev_agent.config import BKAI_DATABASE_EVENTS_ENABLED, _read_bool_env, settings


def test_database_events_setting_is_registered_in_agent_config():
    assert settings.BKAI_DATABASE_EVENTS_ENABLED is BKAI_DATABASE_EVENTS_ENABLED


@pytest.mark.parametrize(
    "canonical, legacy, expected",
    [
        (None, None, True),
        ("1", None, True),
        ("0", None, False),
        ("true", None, True),
        (None, "1", True),
        (None, "0", False),
        (None, "true", False),
        (None, "", False),
        ("1", "0", True),
        ("0", "1", False),
    ],
)
def test_read_bool_env_prefers_canonical_name(monkeypatch, canonical, legacy, expected):
    canonical_name = "BKAI_DATABASE_EVENTS_ENABLED"
    legacy_name = "BKAPP_AIDEV_DATABASE_EVENTS_ENABLED"
    monkeypatch.delenv(canonical_name, raising=False)
    monkeypatch.delenv(legacy_name, raising=False)
    if canonical is not None:
        monkeypatch.setenv(canonical_name, canonical)
    if legacy is not None:
        monkeypatch.setenv(legacy_name, legacy)

    assert _read_bool_env(canonical_name, legacy_name, True) is expected
