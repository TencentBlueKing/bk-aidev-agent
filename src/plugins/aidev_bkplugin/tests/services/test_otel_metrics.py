from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.metrics")

from aidev_bkplugin.services.otel_metrics import BkPluginMetricService, MetricExportSettings
from dev.otel.mock_agent_metrics import (
    DEFAULT_MODELS,
    HANDLER_SYSTEMS,
    SANITIZED_LOGS,
    SANITIZED_PROMPT,
    TOOL_STEPS,
    assigned_models,
    build_sanitized_sse_events,
    coalesce_content_events,
    sample_handler_runs,
    selected_handlers,
    selected_models,
)


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


def test_log_query_mock_is_sanitized_and_models_broker_coalescing():
    assert SANITIZED_PROMPT.count("<BK_BIZ_ID>") == 1
    assert SANITIZED_PROMPT.count("<INDEX_SET_ID>") == 1
    assert len(SANITIZED_LOGS) == 10
    assert [step.name for step in TOOL_STEPS] == [
        "activate_skill",
        "inspect_log_fields",
        "search_logs",
        "aggregate_logs",
    ]

    events = build_sanitized_sse_events()
    physical_sizes = coalesce_content_events(events)

    assert any(event.event_type == "TOOL_CALL_RESULT" for event in events)
    assert len(physical_sizes) < len(events)
    assert sum(physical_sizes) == sum(event.size for event in events)


@pytest.mark.parametrize(
    ("handler_type", "expected"),
    [
        ("all", tuple(HANDLER_SYSTEMS)),
        ("redis", ("redis",)),
    ],
)
def test_log_query_mock_selects_handlers(handler_type, expected):
    assert selected_handlers(handler_type) == expected


def test_log_query_mock_varies_active_runs_between_one_and_maximum_per_handler():
    handlers = selected_handlers("all")
    rng = random.Random(20260809)
    samples = [sample_handler_runs(handlers, 3, rng) for _ in range(20)]

    assert all(set(sample) == set(handlers) for sample in samples)
    assert all(1 <= count <= 3 for sample in samples for count in sample.values())
    assert all(4 <= sum(sample.values()) <= 12 for sample in samples)
    assert len({sum(sample.values()) for sample in samples}) > 1


def test_log_query_mock_distributes_active_runs_across_three_default_models():
    assignments = assigned_models(DEFAULT_MODELS, 12)

    assert len(assignments) == 12
    assert {model: assignments.count(model) for model in DEFAULT_MODELS} == {
        "mock-log-analysis-a": 4,
        "mock-log-analysis-b": 4,
        "mock-log-analysis-c": 4,
    }


def test_log_query_mock_accepts_custom_models_and_removes_duplicates():
    assert selected_models("mock-a, mock-b,mock-a") == ("mock-a", "mock-b")
