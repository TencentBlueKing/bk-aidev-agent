from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.metrics")

from aidev_bkplugin.services.otel_metrics import BkPluginMetricService, MetricExportSettings


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


def test_metric_resource_uses_agent_sdk_version_without_agent_type():
    service = BkPluginMetricService(
        service_name="ai-demo",
        endpoints=[],
        agent_info={"agent_code": "ai-demo", "agent_name": "演示智能体", "agent_sdk_version": "2.2.3"},
        settings=MetricExportSettings(enabled=True),
    )

    attributes = service._create_resource().attributes

    assert attributes["agent.info.sdk_version"] == "2.2.3"
    assert attributes["service.instance.id"]
    assert "agent.info.type" not in attributes


def test_local_dashboard_covers_required_filters_and_metric_groups():
    dashboard_path = Path(__file__).resolve().parents[2] / "dev/otel/grafana/dashboards/aidev-agent-metrics.json"
    dashboard = json.loads(dashboard_path.read_text())
    variables = {item["name"] for item in dashboard["templating"]["list"]}
    panel_queries = "\n".join(target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", []))

    assert variables == {
        "agent_code",
        "agent_version",
        "request_model",
        "handler_type",
        "token_type",
        "sse_event_type",
    }
    for metric in (
        "aidev_agent_processing_duration",
        "gen_ai_client_operation_active",
        "gen_ai_client_token_usage",
        "aidev_sse_event_size",
        "aidev_message_publish_count",
        "aidev_message_publish_size",
    ):
        assert metric in panel_queries
