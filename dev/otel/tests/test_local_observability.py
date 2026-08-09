from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from dev.otel.mock_agent_metrics import (
    DEFAULT_MODELS,
    HANDLER_SYSTEMS,
    SANITIZED_LOGS,
    SANITIZED_PROMPT,
    TOOL_STEPS,
    assigned_models,
    build_sanitized_sse_events,
    build_scenario_stages,
    build_scenario_timings,
    coalesce_content_events,
    sample_handler_runs,
    selected_handlers,
    selected_models,
)

OTEL_ROOT = Path(__file__).resolve().parents[1]


def test_local_dashboard_covers_required_filters_and_metric_groups():
    dashboard = json.loads((OTEL_ROOT / "grafana/dashboards/aidev-agent-metrics.json").read_text())
    variables = {item["name"] for item in dashboard["templating"]["list"]}
    panels_by_id = {panel["id"]: panel for panel in dashboard["panels"]}
    panel_queries = "\n".join(target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", []))

    assert variables == {
        "agent_code",
        "agent_version",
        "request_model",
        "response_model",
        "tool_name",
        "handler_type",
        "sse_event_type",
    }
    for metric in (
        "aidev_agent_phase_active",
        "aidev_agent_phase_duration",
        "gen_ai_invoke_agent_time_to_first_token",
        "gen_ai_client_operation_active",
        "gen_ai_execute_tool_active",
        "aidev_sse_event_size",
        "aidev_message_publish_count",
        "aidev_message_publish_size",
    ):
        assert metric in panel_queries

    assert 8 not in panels_by_id
    assert panels_by_id[1]["title"] == "活跃 Agent Run"
    assert "sum(aidev_agent_active" in panels_by_id[1]["targets"][0]["expr"]
    assert panels_by_id[30]["title"] == "活跃智能体数量"
    assert "sum by (agent_info_code)" in panels_by_id[30]["targets"][0]["expr"]
    assert "or vector(0)" in panels_by_id[30]["targets"][0]["expr"]
    assert panels_by_id[7]["type"] == "timeseries"
    assert panels_by_id[7]["title"] == "Agent 阶段并发（当前与趋势）"
    assert panels_by_id[11]["title"] == "Agent 阶段耗时分布（已结束阶段）"
    assert len(panels_by_id[11]["targets"]) == 1
    assert "histogram_quantile(0.99" in panels_by_id[11]["targets"][0]["expr"]
    assert panels_by_id[16]["title"].startswith("LLM 并发")
    for panel_id in (2, 14, 16):
        assert all("gen_ai_response_model" not in target["expr"] for target in panels_by_id[panel_id]["targets"])
    for panel_id in (13, 15):
        assert any("gen_ai_response_model" in target["expr"] for target in panels_by_id[panel_id]["targets"])
    assert panels_by_id[29]["title"].startswith("工具并发")
    assert 17 not in panels_by_id
    assert len(panels_by_id[18]["targets"]) == 1
    assert "histogram_quantile(0.99" in panels_by_id[18]["targets"][0]["expr"]
    assert panels_by_id[21]["title"] == "事件合并比（所选时段）"
    assert panels_by_id[21]["targets"][0]["instant"] is True


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


def test_log_query_mock_randomizes_stage_durations_within_agent_total():
    rng = random.Random(20260810)
    samples = [build_scenario_timings(rng) for _ in range(50)]

    assert all(30 <= sample.agent_duration <= 120 for sample in samples)
    assert all(len(sample.llm_durations) == 6 and len(sample.tool_durations) == 4 for sample in samples)
    assert all(
        sum(sample.llm_durations) + sum(sample.tool_durations) + sample.processing_duration
        == pytest.approx(sample.agent_duration)
        for sample in samples
    )
    assert all(
        0 < first_chunk_duration <= llm_duration
        for sample in samples
        for first_chunk_duration, llm_duration in zip(
            sample.llm_first_chunk_durations,
            sample.llm_durations,
            strict=True,
        )
    )
    assert len({round(sample.agent_duration, 3) for sample in samples}) == len(samples)


def test_log_query_mock_builds_exclusive_real_time_agent_phases():
    timings = build_scenario_timings(random.Random(20260810))
    stages = build_scenario_stages(timings)

    assert sum(stage.duration for stage in stages) == pytest.approx(timings.agent_duration)
    assert stages[-1].phase == "finalizing"
    assert {stage.phase for stage in stages} == {"processing", "llm", "tool", "finalizing"}
