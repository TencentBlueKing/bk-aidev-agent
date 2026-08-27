from __future__ import annotations

from dataclasses import dataclass, field

from aidev_agent.packages.opentelemetry.metrics import (
    AgentMetrics,
    configure_metric_identity,
    configure_metrics,
    extract_token_usage,
    get_enabled_agent_metrics,
)
from langchain_core.outputs import LLMResult


@dataclass
class FakeInstrument:
    calls: list[tuple[float, dict | None]] = field(default_factory=list)

    def record(self, value, attributes=None):
        self.calls.append((value, attributes))

    def add(self, value, attributes=None):
        self.calls.append((value, attributes))


class FakeMeter:
    def __init__(self):
        self.instruments = {}

    def create_histogram(self, name, **kwargs):
        return self.instruments.setdefault(name, FakeInstrument())

    def create_counter(self, name, **kwargs):
        return self.instruments.setdefault(name, FakeInstrument())

    def create_up_down_counter(self, name, **kwargs):
        return self.instruments.setdefault(name, FakeInstrument())


def test_agent_metrics_only_create_instruments_used_by_the_dashboard():
    meter = FakeMeter()

    AgentMetrics(meter)

    assert set(meter.instruments) == {
        "aidev.agent.active",
        "aidev.agent.phase.active",
        "aidev.agent.phase.duration",
        "aidev.message.publish.count",
        "aidev.message.publish.duration",
        "aidev.message.publish.event_count",
        "aidev.message.publish.size",
        "aidev.sse.event.count",
        "gen_ai.client.operation.active",
        "gen_ai.client.operation.duration",
        "gen_ai.client.operation.time_to_first_chunk",
        "gen_ai.execute_tool.active",
        "gen_ai.execute_tool.duration",
        "gen_ai.invoke_agent.duration",
        "gen_ai.invoke_agent.iteration_count",
        "gen_ai.invoke_agent.started",
        "gen_ai.invoke_agent.time_to_first_token",
    }


def test_extract_token_usage_preserves_cache_breakdown_and_normalizes_prompt_tokens():
    response = LLMResult(
        generations=[],
        llm_output={
            "token_usage": {
                "prompt_tokens": 120,
                "completion_tokens": 48,
                "total_tokens": 168,
                "prompt_tokens_details": {"cached_tokens": 16, "cache_creation": 8},
            }
        },
    )

    assert extract_token_usage(response) == {
        "cache_creation_input_tokens": 8,
        "cache_read_input_tokens": 16,
        "input_tokens": 96,
        "output_tokens": 48,
        "total_tokens": 168,
    }


def test_extract_standard_usage_metadata_subtracts_nested_cache_from_input():
    response = LLMResult(
        generations=[],
        llm_output={
            "usage": {
                "input_tokens": 120,
                "output_tokens": 48,
                "total_tokens": 168,
                "input_token_details": {"cache_read": 16, "cache_creation": 8},
            }
        },
    )

    usage = extract_token_usage(response)
    assert usage is not None
    assert usage["input_tokens"] == 96


def test_error_type_is_added_only_to_duration_metric():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    attrs = recorder.agent_attributes("ai-demo", "演示智能体")

    recorder.record_agent(1.2, 2, attrs, error=RuntimeError("boom"))

    duration_attrs = meter.instruments["gen_ai.invoke_agent.duration"].calls[0][1]
    assert duration_attrs["error.type"] == "RuntimeError"
    assert meter.instruments["gen_ai.invoke_agent.iteration_count"].calls == [(2, attrs)]
    assert "agent.session.session_code" not in duration_attrs


def test_active_agent_metric_is_symmetric_and_low_cardinality():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    attrs = recorder.agent_attributes("ai-demo", "演示智能体")

    recorder.record_active_agent(1, attrs)
    recorder.record_active_agent(-1, attrs)

    assert meter.instruments["aidev.agent.active"].calls == [(1, attrs), (-1, attrs)]
    assert "agent.session.session_code" not in attrs
    assert "agent.info.type" not in attrs


def test_active_llm_metric_is_symmetric():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    attrs = {**recorder.agent_attributes("ai-demo", "演示智能体"), "gen_ai.request.model": "model-a"}

    recorder.record_active_llm(1, attrs)
    recorder.record_active_llm(-1, attrs)

    assert meter.instruments["gen_ai.client.operation.active"].calls == [(1, attrs), (-1, attrs)]


def test_agent_lifecycle_metrics_use_only_low_cardinality_phase_attributes():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    attrs = recorder.agent_attributes("ai-demo", "演示智能体")

    recorder.record_agent_started(attrs)
    recorder.record_agent_first_token(0.8, attrs)
    recorder.record_agent_phase_active(1, "llm", attrs)
    recorder.record_agent_phase_duration(0.6, "llm", attrs)
    recorder.record_agent_phase_active(-1, "llm", attrs)

    assert meter.instruments["gen_ai.invoke_agent.started"].calls == [(1, attrs)]
    assert meter.instruments["gen_ai.invoke_agent.time_to_first_token"].calls == [(0.8, attrs)]
    phase_calls = meter.instruments["aidev.agent.phase.active"].calls
    assert [value for value, _ in phase_calls] == [1, -1]
    assert {call_attrs["aidev.agent.phase"] for _, call_attrs in phase_calls} == {"llm"}
    assert "agent.session.session_code" not in phase_calls[0][1]


def test_active_tool_metric_preserves_tool_name():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    attrs = {**recorder.agent_attributes("ai-demo", "演示智能体"), "gen_ai.tool.name": "search_logs"}

    recorder.record_active_tool(1, attrs)
    recorder.record_active_tool(-1, attrs)

    assert meter.instruments["gen_ai.execute_tool.active"].calls == [(1, attrs), (-1, attrs)]


def test_process_metric_gate_disables_sse_instrumentation():
    configure_metrics(False)
    assert get_enabled_agent_metrics() is None
    configure_metrics(True)
    assert get_enabled_agent_metrics() is not None
    configure_metrics(False)


def test_sse_metrics_include_configured_agent_code_dimension():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    configure_metric_identity("ai-demo", "演示智能体", "2.2.3")

    recorder.record_sse_event()

    event_attrs = meter.instruments["aidev.sse.event.count"].calls[0][1]
    assert event_attrs["agent.info.code"] == "ai-demo"
    assert event_attrs["agent.info.sdk_version"] == "2.2.3"


def test_message_publish_metrics_include_actual_handler_without_session_labels():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    configure_metric_identity("ai-demo", "演示智能体")

    recorder.record_message_publish(
        handler_type="rabbitmq",
        messaging_system="rabbitmq",
        event_count=6,
        message_sizes=[128, 256],
        duration=0.02,
    )

    count_value, attrs = meter.instruments["aidev.message.publish.count"].calls[0]
    assert count_value == 2
    assert attrs["aidev.message.handler.type"] == "rabbitmq"
    assert attrs["messaging.system"] == "rabbitmq"
    assert "agent.session.session_code" not in attrs
    assert meter.instruments["aidev.message.publish.event_count"].calls[0][0] == 6
    assert [value for value, _ in meter.instruments["aidev.message.publish.size"].calls] == [128, 256]


def test_failed_message_publish_is_not_counted_as_successful_broker_writes():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)

    recorder.record_message_publish(
        handler_type="redis",
        messaging_system="redis",
        event_count=3,
        message_sizes=[128, 256],
        duration=0.02,
        error=TimeoutError(),
    )

    assert meter.instruments["aidev.message.publish.count"].calls == []
    assert meter.instruments["aidev.message.publish.event_count"].calls == []
    assert meter.instruments["aidev.message.publish.size"].calls == []
    assert meter.instruments["aidev.message.publish.duration"].calls[0][1]["error.type"] == "TimeoutError"
