"""Adapter 及 OpenClaw Gateway 的 OpenTelemetry Trace / Metrics 初始化。"""

import logging
from pathlib import Path

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ..protocols.models import Settings

logger = logging.getLogger(__name__)
OTEL_PLUGIN_DIR = Path("/app/otel/node_modules/@openclaw/diagnostics-otel")


def configure_otel(settings: Settings, endpoint: str) -> tuple[TracerProvider, MeterProvider]:
    resource = Resource.create({"service.name": "aidev-agent-adapter"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=5000)],
    )
    metrics.set_meter_provider(meter_provider)
    if not OTEL_PLUGIN_DIR.is_dir():
        logger.warning(
            "OpenClaw diagnostics-otel plugin directory not found (%s); skipping engine OTLP plugin",
            OTEL_PLUGIN_DIR,
        )
        return provider, meter_provider
    plugins = settings.native_config.setdefault("plugins", {})
    allowed = plugins.setdefault("allow", ["openai"])
    if "diagnostics-otel" not in allowed:
        allowed.append("diagnostics-otel")
    plugins.setdefault("entries", {})["diagnostics-otel"] = {"enabled": True}
    load_paths = plugins.setdefault("load", {}).setdefault("paths", [])
    plugin_str = str(OTEL_PLUGIN_DIR)
    if plugin_str not in load_paths:
        load_paths.append(plugin_str)
    settings.native_config["diagnostics"] = {
        "enabled": True,
        "otel": {
            "enabled": True,
            "traces": True,
            "metrics": True,
            "logs": False,
            "captureContent": False,
            "serviceName": "openclaw-gateway",
        },
    }
    settings.engine_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
    return provider, meter_provider
