"""Emit a small metric sample through the real bkplugin OTLP exporter."""

from __future__ import annotations

import os
import time

from aidev_agent.packages.opentelemetry.metrics import AgentMetrics, configure_metric_identity
from aidev_agent.packages.opentelemetry.utils import ExporterType
from aidev_bkplugin.services.otel_metrics import BkPluginMetricService, MetricExportSettings


def main() -> None:
    endpoint = os.getenv("AIDEV_LOCAL_OTLP_ENDPOINT", "http://localhost:4318")
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
        "gen_ai.request.model": "mock-model",
        "gen_ai.response.model": "mock-model-routed",
    }
    message_attrs = {"aidev.message.handler.type": "rabbitmq", "messaging.system": "rabbitmq"}
    for index in range(3):
        recorder.record_active_session(1, agent_attrs)
        recorder.record_active_llm(1, llm_attrs)
        if service.provider is not None:
            service.provider.force_flush(timeout_millis=5000)
        time.sleep(1.5)
        recorder.record_agent(1.2 + index * 0.2, 2, 1, agent_attrs, child_duration=0.95 + index * 0.1)
        recorder.record_active_session(-1, agent_attrs)
        recorder.record_active_llm(-1, llm_attrs)
        recorder.record_llm(
            0.8 + index * 0.1,
            llm_attrs,
            {
                "cache_creation_input_tokens": 8,
                "cache_read_input_tokens": 16,
                "input_tokens": 96,
                "output_tokens": 48,
                "total_tokens": 168,
            },
        )
        recorder.record_first_llm_chunk(0.18 + index * 0.02, llm_attrs)
        recorder.record_tool(
            0.15 + index * 0.02,
            {**agent_attrs, "gen_ai.tool.name": "mock_search", "gen_ai.tool.type": "function"},
        )
        recorder.record_sse_first_event(0.2 + index * 0.02, message_attrs)
        for event_type, size in (("TEXT_MESSAGE_START", 96), ("TEXT_MESSAGE_CONTENT", 512), ("RUN_FINISHED", 128)):
            recorder.record_sse_event(size, event_type, message_attrs)
        recorder.record_sse_response(736, message_attrs)
        recorder.record_message_publish(
            handler_type="rabbitmq",
            messaging_system="rabbitmq",
            event_count=3,
            message_sizes=[608, 128],
            duration=0.012 + index * 0.002,
        )
        if service.provider is not None:
            service.provider.force_flush(timeout_millis=5000)
        # Keep the process alive across Prometheus scrapes so rate() panels
        # have multiple cumulative samples to calculate from.
        time.sleep(2.5)

    service.stop()
    print("Mock metrics exported. Open http://localhost:3000/d/aidev-agent-metrics")


if __name__ == "__main__":
    main()
