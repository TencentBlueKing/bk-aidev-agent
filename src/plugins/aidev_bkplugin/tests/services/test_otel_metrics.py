from __future__ import annotations

import pytest

pytest.importorskip("opentelemetry.sdk.metrics")

from aidev_bkplugin.services.otel_metrics import MetricExportSettings


def test_metric_settings_parse_nested_otel_info():
    settings = MetricExportSettings.from_agent_info(
        {
            "otel_info": {
                "metrics": {
                    "enabled": True,
                    "export_interval_millis": 1500,
                    "export_timeout_millis": 7000,
                }
            }
        },
        default_enabled=False,
    )

    assert settings.enabled is True
    assert settings.export_interval_millis == 1500
    assert settings.export_timeout_millis == 7000


def test_metric_settings_support_legacy_flat_keys_and_enforce_minimums():
    settings = MetricExportSettings.from_agent_info(
        {
            "otel_info": {
                "enable_metrics": True,
                "metric_export_interval_millis": 100,
                "metric_export_timeout_millis": 200,
            }
        },
        default_enabled=False,
    )

    assert settings.enabled is True
    assert settings.export_interval_millis == 1000
    assert settings.export_timeout_millis == 1000


def test_metric_settings_fall_back_to_environment_derived_default():
    settings = MetricExportSettings.from_agent_info({}, default_enabled=True)
    assert settings.enabled is True


def test_metric_settings_parse_false_string_safely():
    settings = MetricExportSettings.from_agent_info(
        {"otel_info": {"metrics": {"enabled": "false"}}},
        default_enabled=True,
    )
    assert settings.enabled is False
