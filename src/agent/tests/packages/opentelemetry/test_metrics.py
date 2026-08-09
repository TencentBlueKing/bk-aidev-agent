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


def test_token_metric_uses_only_input_output_type_and_sums_cached_input():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    attrs = {
        **recorder.agent_attributes("ai-demo", "演示智能体"),
        "gen_ai.request.model": "model-a",
        "gen_ai.response.model": "model-b",
    }

    recorder.record_llm(
        0.8,
        attrs,
        {
            "cache_creation_input_tokens": 8,
            "cache_read_input_tokens": 16,
            "input_tokens": 96,
            "output_tokens": 48,
            "total_tokens": 168,
        },
    )

    calls = meter.instruments["gen_ai.client.token.usage"].calls
    assert calls[0][0] == 120
    assert calls[0][1]["gen_ai.token.type"] == "input"
    assert calls[1][0] == 48
    assert calls[1][1]["gen_ai.token.type"] == "output"
    assert all("aidev.token.cache.type" not in call_attrs for _, call_attrs in calls)


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

    recorder.record_agent(1.2, 2, 1, attrs, error=RuntimeError("boom"))

    duration_attrs = meter.instruments["gen_ai.invoke_agent.duration"].calls[0][1]
    assert duration_attrs["error.type"] == "RuntimeError"
    assert "error.type" not in meter.instruments["gen_ai.invoke_agent.inference_calls"].calls[0][1]
    assert "agent.session.session_code" not in duration_attrs


def test_active_session_metric_is_symmetric_and_low_cardinality():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    attrs = recorder.agent_attributes("ai-demo", "演示智能体")

    recorder.record_active_session(1, attrs)
    recorder.record_active_session(-1, attrs)

    assert meter.instruments["aidev.session.active"].calls == [(1, attrs), (-1, attrs)]
    assert "agent.session.session_code" not in attrs


def test_process_metric_gate_disables_sse_instrumentation():
    configure_metrics(False)
    assert get_enabled_agent_metrics() is None
    configure_metrics(True)
    assert get_enabled_agent_metrics() is not None
    configure_metrics(False)


def test_sse_metrics_include_configured_agent_code_dimension():
    meter = FakeMeter()
    recorder = AgentMetrics(meter)
    configure_metric_identity("ai-demo", "演示智能体")

    recorder.record_sse_event(128, "TEXT_MESSAGE_CONTENT")
    recorder.record_sse_response(128)

    event_attrs = meter.instruments["aidev.sse.event.count"].calls[0][1]
    response_attrs = meter.instruments["aidev.sse.response.size"].calls[0][1]
    assert event_attrs["agent.info.code"] == "ai-demo"
    assert response_attrs["agent.info.code"] == "ai-demo"
