from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from dev.otel.mock_agent_metrics import (
    DEFAULT_MODELS,
    HANDLER_SYSTEMS,
    MOCK_ERROR_CASES,
    SANITIZED_LOGS,
    SANITIZED_PROMPT,
    TOOL_STEPS,
    assigned_models,
    build_sanitized_sse_events,
    build_scenario_stages,
    build_scenario_timings,
    coalesce_content_events,
    mock_error_case,
    sample_handler_runs,
    selected_handlers,
    selected_models,
)

OTEL_ROOT = Path(__file__).resolve().parents[1]
PROMETHEUS_DASHBOARD = OTEL_ROOT / "grafana/dashboards/aidev-agent-metrics.json"
BKMONITOR_DASHBOARD = OTEL_ROOT / "grafana/components/aidev-agent-metrics-bkmonitor.json"


def test_local_dashboard_covers_required_filters_and_metric_groups():
    dashboard = json.loads(PROMETHEUS_DASHBOARD.read_text())
    compose = (OTEL_ROOT / "docker-compose.yml").read_text()
    variables = {item["name"] for item in dashboard["templating"]["list"]}
    panels_by_id = {panel["id"]: panel for panel in dashboard["panels"]}
    panel_queries = "\n".join(
        target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", []) if target.get("expr")
    )

    assert "grafana/grafana:10.4.19" in compose
    assert dashboard["schemaVersion"] == 39
    assert dashboard["graphTooltip"] == 1
    assert len(dashboard["panels"]) == 37

    for panel in dashboard["panels"]:
        if panel.get("type") == "row":
            continue
        assert panel.get("description", "").startswith("含义：")
        assert "计算：" in panel["description"]

    assert variables == {
        "agent_code",
        "agent_version",
        "request_model",
        "response_model",
        "tool_name",
        "handler_type",
    }
    for metric in (
        "aidev_agent_phase_active",
        "aidev_agent_phase_duration",
        "gen_ai_invoke_agent_time_to_first_token",
        "gen_ai_invoke_agent_iteration_count",
        "gen_ai_client_operation_active",
        "gen_ai_execute_tool_active",
        "aidev_sse_event_count",
        "aidev_message_publish_count",
        "aidev_message_publish_size",
    ):
        assert metric in panel_queries

    assert 8 not in panels_by_id
    assert panels_by_id[1]["title"] == "活跃 Agent Run"
    assert "sum(aidev_agent_active" in panels_by_id[1]["targets"][0]["expr"]
    assert "or vector(0)" in panels_by_id[1]["targets"][0]["expr"]
    assert panels_by_id[30]["title"] == "活跃智能体数量"
    assert panels_by_id[2]["title"] == "LLM 阶段 Agent Run"
    assert 'aidev_agent_phase="llm"' in panels_by_id[2]["targets"][0]["expr"]
    assert "gen_ai_client_operation_active" not in panels_by_id[2]["targets"][0]["expr"]
    assert panels_by_id[3]["title"] == "Tool 阶段 Agent Run"
    assert 'aidev_agent_phase="tool"' in panels_by_id[3]["targets"][0]["expr"]
    assert "gen_ai_execute_tool_active" not in panels_by_id[3]["targets"][0]["expr"]
    assert "or vector(0)" in panels_by_id[2]["targets"][0]["expr"]
    assert "or vector(0)" in panels_by_id[3]["targets"][0]["expr"]
    assert panels_by_id[30]["gridPos"]["x"] == 0
    assert panels_by_id[1]["gridPos"]["x"] == 4
    assert "sum by (agent_info_code)" in panels_by_id[30]["targets"][0]["expr"]
    assert "or vector(0)" in panels_by_id[30]["targets"][0]["expr"]
    assert panels_by_id[7]["type"] == "timeseries"
    assert panels_by_id[7]["title"] == "Agent 阶段并发（当前与趋势）"
    assert panels_by_id[11]["title"] == "Agent 阶段耗时 P95（已结束阶段）"
    assert len(panels_by_id[11]["targets"]) == 1
    assert panels_by_id[10]["title"] == "Agent 墙钟耗时 P95"
    assert len(panels_by_id[10]["targets"]) == 1
    assert panels_by_id[32]["title"] == "Agent 首 Token P95（流式调用，按 Agent Code）"
    assert panels_by_id[32]["type"] == "timeseries"
    assert "sum by (le, agent_info_code)" in panels_by_id[32]["targets"][0]["expr"]
    assert "gen_ai_invoke_agent_time_to_first_token_seconds_bucket" in panels_by_id[32]["targets"][0]["expr"]
    assert panels_by_id[32]["gridPos"] == {"h": 8, "w": 12, "x": 12, "y": 23}
    assert panels_by_id[6]["title"] == "Agent 迭代次数 P95"
    assert panels_by_id[6]["targets"][0]["instant"] is True
    assert "histogram_quantile(0.95" in panels_by_id[6]["targets"][0]["expr"]
    assert "gen_ai_invoke_agent_iteration_count_bucket" in panels_by_id[6]["targets"][0]["expr"]
    assert panels_by_id[33]["title"] == "当前运行智能体及会话数"
    assert panels_by_id[33]["type"] == "bargauge"
    assert panels_by_id[33]["targets"][0]["instant"] is True
    assert "sum by (agent_info_code, agent_info_name, agent_info_sdk_version)" in panels_by_id[33]["targets"][0]["expr"]
    assert panels_by_id[33]["gridPos"] == {"h": 8, "w": 12, "x": 0, "y": 14}
    assert panels_by_id[9]["gridPos"] == {"h": 8, "w": 12, "x": 12, "y": 14}
    assert panels_by_id[12]["gridPos"] == {"h": 8, "w": 24, "x": 0, "y": 31}
    assert panels_by_id[16]["title"].startswith("LLM 并发")
    assert "gen_ai_client_operation_active" in panels_by_id[16]["targets"][0]["expr"]
    for panel_id in (2, 14, 16):
        assert all("gen_ai_response_model" not in target["expr"] for target in panels_by_id[panel_id]["targets"])
    for panel_id in (13, 15):
        assert any("gen_ai_response_model" in target["expr"] for target in panels_by_id[panel_id]["targets"])
    assert panels_by_id[29]["title"].startswith("工具并发")
    assert "gen_ai_execute_tool_active" in panels_by_id[29]["targets"][0]["expr"]
    assert panels_by_id[29]["gridPos"]["w"] == 24
    assert 19 not in panels_by_id
    assert 17 not in panels_by_id
    assert len(panels_by_id[18]["targets"]) == 1
    for panel in dashboard["panels"]:
        if panel.get("type") != "timeseries":
            continue
        for target in panel.get("targets", []):
            if "histogram_quantile" not in target["expr"]:
                continue
            assert "P95" in panel["title"]
            assert "histogram_quantile(0.95" in target["expr"]
            assert "P95" in target["legendFormat"]
    assert panels_by_id[20]["options"]["legend"]["sortBy"] == "Name"
    assert panels_by_id[20]["options"]["tooltip"]["sort"] == "none"
    assert all("aidev_message_publish_event_count.*_total" in target["expr"] for target in panels_by_id[20]["targets"])
    assert all(
        "aidev_message_publish_event_count.*_sum" not in target["expr"] for target in panels_by_id[20]["targets"]
    )
    assert [target["refId"] for target in panels_by_id[20]["targets"]] == ["A", "B", "C", "D", "E"]
    assert panels_by_id[21]["title"] == "Handler 分布（所选时段）"
    assert panels_by_id[21]["type"] == "bargauge"
    assert panels_by_id[21]["fieldConfig"]["defaults"]["unit"] == "percentunit"
    assert [target["refId"] for target in panels_by_id[21]["targets"]] == ["A", "B", "C", "D", "E"]
    assert all(target["instant"] is True for target in panels_by_id[21]["targets"])
    assert all("aidev_message_publish_count" in target["expr"] for target in panels_by_id[21]["targets"])
    assert all(
        "sum by (aidev_message_handler_type, agent_info_code)" in target["expr"]
        for target in panels_by_id[21]["targets"]
    )
    assert all("count by (aidev_message_handler_type)" in target["expr"] for target in panels_by_id[21]["targets"])
    assert all("aidev_message_publish_event_count" not in target["expr"] for target in panels_by_id[21]["targets"])
    assert panels_by_id[104]["title"] == "SSE 输出与物理消息"
    assert panels_by_id[106]["title"] == "Broker 发布侧"
    assert 27 not in panels_by_id
    assert panels_by_id[105]["gridPos"]["y"] == 99
    assert panels_by_id[28]["gridPos"]["y"] == 100
    assert panels_by_id[34]["title"] == "错误计数（所选时段）"
    assert panels_by_id[34]["type"] == "stat"
    assert panels_by_id[34]["targets"][0]["instant"] is True
    assert "increase(gen_ai_invoke_agent_duration_seconds_count" in panels_by_id[34]["targets"][0]["expr"]
    assert panels_by_id[35]["title"] == "错误智能体分布（所选时段）"
    assert panels_by_id[35]["type"] == "bargauge"
    assert "sum by (agent_info_code)" in panels_by_id[35]["targets"][0]["expr"]
    assert panels_by_id[34]["gridPos"] == {"h": 8, "w": 4, "x": 0, "y": 100}
    assert panels_by_id[35]["gridPos"] == {"h": 8, "w": 8, "x": 4, "y": 100}
    assert panels_by_id[28]["gridPos"] == {"h": 8, "w": 12, "x": 12, "y": 100}
    assert [target["legendFormat"] for target in panels_by_id[28]["targets"]] == [
        "Agent · {{error_type}}",
        "LLM · {{error_type}}",
        "Tool · {{error_type}}",
        "Handler · {{error_type}}",
    ]
    assert all('error_type!=""' in target["expr"] for target in panels_by_id[28]["targets"])
    assert 26 not in panels_by_id
    assert panels_by_id[25]["title"] == "SSE 事件与物理消息数量"
    assert panels_by_id[25]["gridPos"]["y"] == panels_by_id[31]["gridPos"]["y"] == 74
    assert [target["refId"] for target in panels_by_id[25]["targets"]] == ["A", "B", "C", "D", "E"]
    assert panels_by_id[25]["type"] == "timeseries"
    assert all(target["range"] is True for target in panels_by_id[25]["targets"])
    assert all("aidev_sse_event_type" not in target["expr"] for target in panels_by_id[25]["targets"])
    assert [
        next(
            handler
            for handler in ("inmemory", "rabbitmq", "rabbitmq_stream", "redis")
            if f'="{handler}"' in target["expr"]
        )
        for target in panels_by_id[25]["targets"][:4]
    ] == ["inmemory", "rabbitmq", "rabbitmq_stream", "redis"]
    assert panels_by_id[25]["options"]["legend"]["sortBy"] == "Name"
    assert panels_by_id[25]["options"]["legend"]["sortDesc"] is False
    assert panels_by_id[31]["title"] == "SSE/物理消息压缩比"
    assert panels_by_id[31]["type"] == "timeseries"
    assert [target["refId"] for target in panels_by_id[31]["targets"]] == ["A", "B", "C", "D", "E"]
    assert all(target["range"] is True for target in panels_by_id[31]["targets"])
    assert panels_by_id[31]["options"]["legend"]["sortBy"] == "Name"
    assert "aidev_sse_event_count" in panels_by_id[31]["targets"][0]["expr"]
    assert "aidev_message_publish_count" in panels_by_id[31]["targets"][0]["expr"]
    assert panels_by_id[20]["gridPos"]["y"] == panels_by_id[21]["gridPos"]["y"] == 83
    panel_order = [panel["id"] for panel in dashboard["panels"]]
    assert panel_order.index(104) < panel_order.index(25) < panel_order.index(106) < panel_order.index(20)


def test_bkmonitor_dashboard_is_a_separate_importable_component():
    local = json.loads(PROMETHEUS_DASHBOARD.read_text())
    dashboard = json.loads(BKMONITOR_DASHBOARD.read_text())
    datasource = {"type": "bkmonitor-timeseries-datasource", "uid": "cfjy28njb6ghsd"}
    panels = [panel for panel in dashboard["panels"] if panel.get("type") != "row"]
    targets = [target for panel in panels for target in panel["targets"]]
    variables = {item["name"]: item for item in dashboard["templating"]["list"]}

    assert local["uid"] == "aidev-agent-metrics"
    assert dashboard["uid"] == "aidev-agent-metrics-bkmonitor"
    assert dashboard["title"] == "AIDev Agent Metrics (BK Monitor)"
    assert dashboard["schemaVersion"] == 39
    assert len(dashboard["panels"]) == len(local["panels"]) == 37
    assert "__inputs" not in dashboard
    assert dashboard["__requires"][0]["id"] == "bkmonitor-timeseries-datasource"
    rows = [panel for panel in dashboard["panels"] if panel["type"] == "row"]
    assert all("datasource" not in panel and "targets" not in panel for panel in rows)
    assert all(panel["datasource"] == datasource for panel in panels)
    assert all(target["datasource"] == datasource and target["type"] == "range" for target in targets)
    assert all("source" in target and "expr" not in target for target in targets)
    assert all(
        "${" not in target["source"]
        and "$__rate_interval" not in target["source"]
        and "$__range" not in target["source"]
        for target in targets
    )
    assert any("$window" in target["source"] for target in targets)
    assert set(variables) == {
        "agent_code",
        "agent_version",
        "request_model",
        "response_model",
        "tool_name",
        "handler_type",
        "window",
    }
    assert variables["window"]["query"] == "1m,5m,1h"
    assert all(variable["datasource"] == datasource for name, variable in variables.items() if name != "window")


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


def test_log_query_mock_cycles_success_and_distinct_error_sources():
    cases = {
        mock_error_case(handler_index, slot_index, run_index)
        for handler_index in range(4)
        for slot_index in range(3)
        for run_index in range(5)
    }

    assert cases == set(MOCK_ERROR_CASES)
    assert MOCK_ERROR_CASES == ("success", "agent", "llm", "tool", "handler")


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
