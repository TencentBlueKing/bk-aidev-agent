# -*- coding: utf-8 -*-
"""Agent metric instruments.

This module deliberately depends on the OpenTelemetry API only.  The SDK,
readers and exporters are owned by the runtime integration (bkplugin), so the
agent framework is responsible for instrumentation but not transport.
"""

from __future__ import annotations

from typing import Any

from langchain_core.outputs import LLMResult
from opentelemetry import metrics

METER_NAME = "aidev_agent"
AGENT_TYPE = "LLMGW"


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _coerce_usage_dict(usage: Any) -> dict[str, Any] | None:
    for method_name in ("to_dict_recursive", "model_dump", "dict"):
        if hasattr(usage, method_name):
            usage = getattr(usage, method_name)()
            break
    return usage if isinstance(usage, dict) else None


def extract_token_usage(response: LLMResult) -> dict[str, int] | None:
    """Extract provider token details without putting them in metric labels.

    ``input_tokens`` is normalized to non-cache input.  Cache creation/read are
    retained separately for trace attributes, while the metric input value is
    the sum of all three input categories.
    """

    llm_output = response.llm_output or {}
    raw_usage: Any = next((llm_output[key] for key in ("token_usage", "usage") if llm_output.get(key)), None)
    if raw_usage is None:
        for generation_group in reversed(response.generations or []):
            for generation in reversed(generation_group):
                message = getattr(generation, "message", None)
                raw_usage = getattr(message, "usage_metadata", None)
                if raw_usage is not None:
                    break
            if raw_usage is not None:
                break

    usage = _coerce_usage_dict(raw_usage)
    if usage is None:
        return None

    input_details = usage.get("input_token_details") or usage.get("prompt_tokens_details") or {}
    if not isinstance(input_details, dict):
        input_details = {}

    cache_creation = _as_int(
        usage.get("cache_creation_input_tokens")
        or input_details.get("cache_creation")
        or input_details.get("cache_creation_input_tokens")
    )
    cache_read = _as_int(
        usage.get("cache_read_input_tokens") or input_details.get("cache_read") or input_details.get("cached_tokens")
    )

    # Anthropic-style input_tokens is already non-cache input. OpenAI-style
    # prompt_tokens includes cached tokens, so subtract the explicit cache
    # detail before reporting the non-cache component.
    has_provider_cache_fields = any(key in usage for key in ("cache_creation_input_tokens", "cache_read_input_tokens"))
    if usage.get("input_tokens") is not None:
        input_tokens = _as_int(usage.get("input_tokens"))
        # LangChain UsageMetadata expresses input_tokens as the inclusive total
        # and puts cache detail in input_token_details. Provider-native
        # Anthropic usage instead exposes cache_* beside non-cache input_tokens.
        if input_details and not has_provider_cache_fields:
            input_tokens = max(0, input_tokens - cache_creation - cache_read)
    else:
        input_tokens = max(0, _as_int(usage.get("prompt_tokens")) - cache_creation - cache_read)

    output_tokens = _as_int(usage.get("output_tokens") or usage.get("completion_tokens"))
    total_tokens = _as_int(usage.get("total_tokens")) or (input_tokens + cache_creation + cache_read + output_tokens)
    return {
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


class AgentMetrics:
    """Low-cardinality OpenTelemetry metrics emitted by the agent SDK."""

    def __init__(self, meter=None):
        meter = meter or metrics.get_meter(METER_NAME)
        self.agent_duration = meter.create_histogram(
            "gen_ai.invoke_agent.duration", unit="s", description="Agent invocation duration"
        )
        self.agent_inference_calls = meter.create_counter(
            "gen_ai.invoke_agent.inference_calls", unit="{call}", description="LLM calls per agent invocation"
        )
        self.agent_tool_calls = meter.create_counter(
            "gen_ai.invoke_agent.tool_calls", unit="{call}", description="Tool calls per agent invocation"
        )
        self.llm_duration = meter.create_histogram(
            "gen_ai.client.operation.duration", unit="s", description="LLM operation duration"
        )
        self.llm_time_to_first_chunk = meter.create_histogram(
            "gen_ai.client.operation.time_to_first_chunk", unit="s", description="LLM time to first stream chunk"
        )
        self.token_usage = meter.create_histogram(
            "gen_ai.client.token.usage", unit="{token}", description="LLM input and output token usage"
        )
        self.tool_duration = meter.create_histogram(
            "gen_ai.execute_tool.duration", unit="s", description="Tool execution duration"
        )
        self.sse_event_count = meter.create_counter(
            "aidev.sse.event.count", unit="{event}", description="Produced SSE event count"
        )
        self.sse_event_bytes = meter.create_counter(
            "aidev.sse.event.bytes", unit="By", description="Produced SSE event bytes"
        )
        self.sse_response_size = meter.create_histogram(
            "aidev.sse.response.size", unit="By", description="Total SSE response bytes"
        )
        self.sse_time_to_first_event = meter.create_histogram(
            "aidev.sse.time_to_first_event", unit="s", description="Time to first produced SSE event"
        )

    @staticmethod
    def agent_attributes(agent_code: str | None, agent_name: str | None) -> dict[str, str]:
        return {
            "agent.info.code": agent_code or "unknown",
            "agent.info.name": agent_name or "unknown",
            "agent.info.type": AGENT_TYPE,
        }

    def record_agent(
        self,
        duration: float,
        inference_calls: int,
        tool_calls: int,
        attributes: dict[str, str],
        error: BaseException | None = None,
    ) -> None:
        attrs = dict(attributes)
        if error is not None:
            attrs["error.type"] = type(error).__name__
        self.agent_duration.record(duration, attrs)
        self.agent_inference_calls.add(inference_calls, attributes)
        self.agent_tool_calls.add(tool_calls, attributes)

    def record_llm(
        self,
        duration: float,
        attributes: dict[str, str],
        usage: dict[str, int] | None = None,
        error: BaseException | None = None,
    ) -> None:
        attrs = dict(attributes)
        if error is not None:
            attrs["error.type"] = type(error).__name__
        self.llm_duration.record(duration, attrs)
        if usage:
            input_tokens = (
                usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
            )
            self.token_usage.record(input_tokens, {**attributes, "gen_ai.token.type": "input"})
            self.token_usage.record(usage["output_tokens"], {**attributes, "gen_ai.token.type": "output"})

    def record_first_llm_chunk(self, duration: float, attributes: dict[str, str]) -> None:
        self.llm_time_to_first_chunk.record(duration, attributes)

    def record_tool(
        self,
        duration: float,
        attributes: dict[str, str],
        error: BaseException | None = None,
    ) -> None:
        attrs = dict(attributes)
        if error is not None:
            attrs["error.type"] = type(error).__name__
        self.tool_duration.record(duration, attrs)

    def record_sse_event(self, size: int, event_type: str) -> None:
        attrs = {**_metric_identity, "aidev.sse.event.type": event_type or "unknown"}
        self.sse_event_count.add(1, attrs)
        self.sse_event_bytes.add(size, attrs)

    def record_sse_first_event(self, duration: float) -> None:
        self.sse_time_to_first_event.record(duration, _metric_identity)

    def record_sse_response(self, size: int) -> None:
        self.sse_response_size.record(size, _metric_identity)


_agent_metrics: AgentMetrics | None = None
_metrics_enabled = False
_metric_identity: dict[str, str] = {}


def get_agent_metrics() -> AgentMetrics:
    global _agent_metrics
    if _agent_metrics is None:
        _agent_metrics = AgentMetrics()
    return _agent_metrics


def configure_metrics(enabled: bool) -> None:
    """Set the process-level instrumentation gate from the runtime config."""
    global _metrics_enabled
    _metrics_enabled = enabled


def configure_metric_identity(agent_code: str | None, agent_name: str | None) -> None:
    """Configure the low-cardinality identity used by process-level SSE hooks."""
    global _metric_identity
    _metric_identity = AgentMetrics.agent_attributes(agent_code, agent_name)


def get_enabled_agent_metrics() -> AgentMetrics | None:
    return get_agent_metrics() if _metrics_enabled else None
