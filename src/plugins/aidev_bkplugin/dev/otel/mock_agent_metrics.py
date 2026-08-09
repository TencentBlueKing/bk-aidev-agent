"""Emit a sanitized log-query scenario through the real bkplugin exporter."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from aidev_agent.packages.opentelemetry.metrics import AgentMetrics, configure_metric_identity
from aidev_agent.packages.opentelemetry.utils import ExporterType
from aidev_bkplugin.services.otel_metrics import BkPluginMetricService, MetricExportSettings

SANITIZED_PROMPT = "查一下业务 <BK_BIZ_ID> 的索引集 <INDEX_SET_ID> 近 1 天前 10 条日志，按合适维度输出总结"
SANITIZED_LOGS = (
    {
        "timestamp": "2026-01-01T00:01:00Z",
        "level": "INFO",
        "service": "api",
        "node": "node-a",
        "message": "request completed",
    },
    {
        "timestamp": "2026-01-01T00:02:00Z",
        "level": "WARN",
        "service": "worker",
        "node": "node-b",
        "message": "retry scheduled",
    },
    {
        "timestamp": "2026-01-01T00:03:00Z",
        "level": "ERROR",
        "service": "api",
        "node": "node-a",
        "message": "upstream timeout",
    },
    {
        "timestamp": "2026-01-01T00:04:00Z",
        "level": "INFO",
        "service": "scheduler",
        "node": "node-c",
        "message": "job dispatched",
    },
    {
        "timestamp": "2026-01-01T00:05:00Z",
        "level": "WARN",
        "service": "api",
        "node": "node-b",
        "message": "response latency elevated",
    },
    {
        "timestamp": "2026-01-01T00:06:00Z",
        "level": "INFO",
        "service": "worker",
        "node": "node-b",
        "message": "task completed",
    },
    {
        "timestamp": "2026-01-01T00:07:00Z",
        "level": "ERROR",
        "service": "scheduler",
        "node": "node-c",
        "message": "dependency unavailable",
    },
    {
        "timestamp": "2026-01-01T00:08:00Z",
        "level": "INFO",
        "service": "api",
        "node": "node-a",
        "message": "health check passed",
    },
    {
        "timestamp": "2026-01-01T00:09:00Z",
        "level": "WARN",
        "service": "worker",
        "node": "node-c",
        "message": "queue depth elevated",
    },
    {
        "timestamp": "2026-01-01T00:10:00Z",
        "level": "INFO",
        "service": "scheduler",
        "node": "node-a",
        "message": "job completed",
    },
)


@dataclass(frozen=True)
class ModelStep:
    output: str
    duration: float
    time_to_first_chunk: float
    usage: dict[str, int]


@dataclass(frozen=True)
class ToolStep:
    name: str
    arguments: dict[str, Any]
    output: Any
    duration: float


@dataclass(frozen=True)
class MockSseEvent:
    event_type: str
    size: int


def _usage(input_tokens: int, output_tokens: int, cache_creation: int = 0, cache_read: int = 0) -> dict[str, int]:
    return {
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens + cache_creation + cache_read,
    }


MODEL_STEPS = (
    ModelStep(
        "我会先激活日志分析能力，再根据时间范围和数量限制执行查询。", 4.0, 0.8, _usage(220, 52, cache_creation=64)
    ),
    ModelStep(
        "日志分析能力已就绪，先确认可用字段，避免使用不存在的聚合维度。", 4.5, 0.9, _usage(110, 45, cache_read=64)
    ),
    ModelStep(
        "字段中包含时间、级别、服务和节点，现在查询最近一天的 10 条样本。", 3.8, 0.7, _usage(160, 58, cache_read=64)
    ),
    ModelStep(
        "已取得 10 条脱敏日志，继续按 level 和 service 聚合，检查异常集中度。",
        5.2,
        1.0,
        _usage(180, 62, cache_read=128),
    ),
    ModelStep(
        "聚合结果显示 ERROR 2 条、WARN 3 条、INFO 5 条；api 服务的日志数最多。",
        4.8,
        0.9,
        _usage(450, 85, cache_read=256),
    ),
    ModelStep(
        "总结：10 条样本中 ERROR 2 条、WARN 3 条、INFO 5 条。异常主要集中在 api 超时和 scheduler 依赖不可用；"
        "worker 出现重试与队列深度升高。建议优先核对上游依赖可用性，并按 service、level 和 node 继续扩大时间窗口观察。",
        7.0,
        1.2,
        _usage(620, 210, cache_read=256),
    ),
)

TOOL_STEPS = (
    ToolStep(
        "activate_skill",
        {"skill_name": "log-analysis"},
        {"status": "activated", "capabilities": ["search_logs", "aggregate_logs"]},
        0.2,
    ),
    ToolStep(
        "inspect_log_fields",
        {"index_set_id": "<INDEX_SET_ID>"},
        {"fields": ["timestamp", "level", "service", "node", "message"]},
        0.3,
    ),
    ToolStep(
        "search_logs",
        {"bk_biz_id": "<BK_BIZ_ID>", "index_set_id": "<INDEX_SET_ID>", "time_range": "24h", "size": 10},
        {"total": 10, "records": SANITIZED_LOGS},
        12.0,
    ),
    ToolStep(
        "aggregate_logs",
        {"dimensions": ["level", "service"]},
        {"level": {"ERROR": 2, "WARN": 3, "INFO": 5}, "service": {"api": 4, "worker": 3, "scheduler": 3}},
        0.8,
    ),
)


def _serialized_size(event_type: str, payload: Any) -> int:
    return len(json.dumps({"type": event_type, "payload": payload}, ensure_ascii=False, separators=(",", ":")).encode())


def _append_text_events(events: list[MockSseEvent], prefix: str, text: str, chunk_size: int = 12) -> None:
    events.append(MockSseEvent(f"{prefix}_START", _serialized_size(f"{prefix}_START", {})))
    for offset in range(0, len(text), chunk_size):
        chunk = text[offset : offset + chunk_size]
        events.append(MockSseEvent(f"{prefix}_CONTENT", _serialized_size(f"{prefix}_CONTENT", {"delta": chunk})))
    events.append(MockSseEvent(f"{prefix}_END", _serialized_size(f"{prefix}_END", {})))


def build_sanitized_sse_events() -> list[MockSseEvent]:
    """Build a realistic AG-UI event mix without retaining source conversation data."""
    events = [MockSseEvent("RUN_STARTED", _serialized_size("RUN_STARTED", {}))]
    for index, model_step in enumerate(MODEL_STEPS):
        prefix = "TEXT_MESSAGE" if index == len(MODEL_STEPS) - 1 else "THINKING_TEXT_MESSAGE"
        _append_text_events(events, prefix, model_step.output)
        if index < len(TOOL_STEPS):
            tool = TOOL_STEPS[index]
            for event_type, payload in (
                ("TOOL_CALL_START", {"tool": tool.name}),
                ("TOOL_CALL_ARGS", tool.arguments),
                ("TOOL_CALL_END", {"tool": tool.name}),
                ("TOOL_CALL_RESULT", tool.output),
            ):
                events.append(MockSseEvent(event_type, _serialized_size(event_type, payload)))
    events.append(MockSseEvent("RUN_FINISHED", _serialized_size("RUN_FINISHED", {"status": "completed"})))
    return events


def coalesce_content_events(events: list[MockSseEvent]) -> list[int]:
    """Approximate the handler's consecutive text-content coalescing."""
    physical_sizes: list[int] = []
    buffered_size = 0
    for event in events:
        if event.event_type in {"TEXT_MESSAGE_CONTENT", "THINKING_TEXT_MESSAGE_CONTENT"}:
            buffered_size += event.size
            continue
        if buffered_size:
            physical_sizes.append(buffered_size)
            buffered_size = 0
        physical_sizes.append(event.size)
    if buffered_size:
        physical_sizes.append(buffered_size)
    return physical_sizes


def _handler_config() -> tuple[str, str]:
    handler_type = os.getenv("AIDEV_MOCK_MESSAGE_HANDLER", "rabbitmq")
    systems = {"inmemory": "in_memory", "rabbitmq": "rabbitmq", "rabbitmq_stream": "rabbitmq", "redis": "redis"}
    if handler_type not in systems:
        raise ValueError(f"Unsupported AIDEV_MOCK_MESSAGE_HANDLER: {handler_type}")
    return handler_type, systems[handler_type]


def _record_scenario(recorder: AgentMetrics, agent_attrs: dict[str, str], index: int) -> None:
    handler_type, messaging_system = _handler_config()
    llm_attrs = {
        **agent_attrs,
        "gen_ai.request.model": "mock-log-analysis-model",
        "gen_ai.response.model": "mock-log-analysis-model-routed",
    }
    duration_offset = index * 0.05
    for step in MODEL_STEPS:
        recorder.record_llm(step.duration + duration_offset, llm_attrs, step.usage)
        recorder.record_first_llm_chunk(step.time_to_first_chunk + duration_offset, llm_attrs)
    for step in TOOL_STEPS:
        recorder.record_tool(
            step.duration + duration_offset,
            {**agent_attrs, "gen_ai.tool.name": step.name, "gen_ai.tool.type": "function"},
        )

    llm_duration = sum(step.duration + duration_offset for step in MODEL_STEPS)
    tool_duration = sum(step.duration + duration_offset for step in TOOL_STEPS)
    processing_duration = 4.5 + index * 0.2
    recorder.record_agent(
        llm_duration + tool_duration + processing_duration,
        len(MODEL_STEPS),
        len(TOOL_STEPS),
        agent_attrs,
        child_duration=llm_duration + tool_duration,
    )

    message_attrs = {"aidev.message.handler.type": handler_type, "messaging.system": messaging_system}
    events = build_sanitized_sse_events()
    recorder.record_sse_first_event(MODEL_STEPS[0].time_to_first_chunk + duration_offset, message_attrs)
    for event in events:
        recorder.record_sse_event(event.size, event.event_type, message_attrs)
    recorder.record_sse_response(sum(event.size for event in events), message_attrs)
    physical_sizes = coalesce_content_events(events)
    recorder.record_message_publish(
        handler_type=handler_type,
        messaging_system=messaging_system,
        event_count=len(events),
        message_sizes=physical_sizes,
        duration=0.01 + len(physical_sizes) * 0.0002 + index * 0.002,
    )


def main() -> None:
    endpoint = os.getenv("AIDEV_LOCAL_OTLP_ENDPOINT", "http://localhost:4318")
    concurrency = max(1, int(os.getenv("AIDEV_MOCK_CONCURRENCY", "3")))
    iterations = max(1, int(os.getenv("AIDEV_MOCK_ITERATIONS", "10")))
    interval = max(0.1, float(os.getenv("AIDEV_MOCK_INTERVAL_SECONDS", "1.5")))
    service = BkPluginMetricService(
        service_name="aidev-agent-local",
        endpoints=[{"url": endpoint, "token": "", "exporter_type": ExporterType.HTTP}],
        agent_info={
            "agent_code": "ai-agent-local-demo",
            "agent_name": "本地指标验证智能体",
            "agent_sdk_version": "2.2.3",
        },
        settings=MetricExportSettings(enabled=True, export_interval_millis=1000, export_timeout_millis=5000),
    )
    service.start()

    configure_metric_identity("ai-agent-local-demo", "本地指标验证智能体")
    recorder = AgentMetrics()
    agent_attrs = recorder.agent_attributes("ai-agent-local-demo", "本地指标验证智能体")
    llm_attrs = {
        **agent_attrs,
        "gen_ai.request.model": "mock-log-analysis-model",
        "gen_ai.response.model": "mock-log-analysis-model-routed",
    }
    recorder.record_active_session(concurrency, agent_attrs)
    recorder.record_active_llm(concurrency, llm_attrs)
    print(f"Sanitized scenario: {SANITIZED_PROMPT}")
    print("Mock tools: " + ", ".join(step.name for step in TOOL_STEPS))
    try:
        for iteration in range(iterations):
            for worker in range(concurrency):
                _record_scenario(recorder, agent_attrs, (iteration + worker) % 3)
            if service.provider is not None:
                service.provider.force_flush(timeout_millis=5000)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        recorder.record_active_session(-concurrency, agent_attrs)
        recorder.record_active_llm(-concurrency, llm_attrs)
        if service.provider is not None:
            service.provider.force_flush(timeout_millis=5000)
        service.stop()
    print("Mock metrics exported. Open http://localhost:3000/d/aidev-agent-metrics")


if __name__ == "__main__":
    main()
