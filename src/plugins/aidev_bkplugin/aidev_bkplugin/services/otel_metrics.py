# -*- coding: utf-8 -*-
"""bkplugin-owned OpenTelemetry metric provider and OTLP exporters."""

from __future__ import annotations

import logging
import os
import socket
from dataclasses import dataclass
from typing import Any

from aidev_agent.packages.opentelemetry.utils import ExporterType
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GRPCMetricExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HTTPMetricExporter
from opentelemetry.sdk.metrics import Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

logger = logging.getLogger(__name__)


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(frozen=True)
class MetricExportSettings:
    """Metric-specific settings parsed from decoded ``agent_info.otel_info``."""

    enabled: bool
    export_interval_millis: int = 5000
    export_timeout_millis: int = 30000

    @classmethod
    def from_agent_info(cls, agent_info: dict[str, Any] | None, *, default_enabled: bool) -> "MetricExportSettings":
        otel_info = (agent_info or {}).get("otel_info") or {}
        metrics_info = otel_info.get("metrics") or {}
        enabled = metrics_info.get("enabled", otel_info.get("enable_metrics", default_enabled))
        interval = metrics_info.get(
            "export_interval_millis",
            otel_info.get("metric_export_interval_millis", 5000),
        )
        timeout = metrics_info.get(
            "export_timeout_millis",
            otel_info.get("metric_export_timeout_millis", 30000),
        )
        return cls(
            enabled=_as_bool(enabled),
            export_interval_millis=max(1000, int(interval)),
            export_timeout_millis=max(1000, int(timeout)),
        )


class BkPluginMetricService:
    """Own the metric SDK lifecycle; the Agent SDK only calls metric APIs."""

    def __init__(
        self,
        *,
        service_name: str,
        endpoints: list[dict[str, Any]],
        agent_info: dict[str, Any] | None,
        settings: MetricExportSettings,
    ) -> None:
        self.service_name = service_name
        self.endpoints = endpoints
        self.agent_info = agent_info or {}
        self.settings = settings
        self.provider: MeterProvider | None = None

    def start(self) -> None:
        if not self.settings.enabled:
            logger.info("[aidev_bkplugin] metric export disabled")
            return
        if not self.endpoints:
            logger.warning("[aidev_bkplugin] metric export enabled but no OTLP endpoint configured")
            return

        readers = []
        for endpoint in self.endpoints:
            exporter = self._create_exporter(endpoint)
            readers.append(
                PeriodicExportingMetricReader(
                    exporter,
                    export_interval_millis=self.settings.export_interval_millis,
                    export_timeout_millis=self.settings.export_timeout_millis,
                )
            )

        self.provider = MeterProvider(resource=self._create_resource(), metric_readers=readers, views=self._views())
        metrics.set_meter_provider(self.provider)
        logger.info("[aidev_bkplugin] metric export started with %d OTLP endpoint(s)", len(readers))

    def _create_resource(self) -> Resource:
        return Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: self.service_name,
                "service.instance.id": f"{socket.gethostname()}:{os.getpid()}",
                "agent.info.code": self.agent_info.get("agent_code")
                or self.agent_info.get("code")
                or self.service_name,
                "agent.info.name": self.agent_info.get("agent_name") or self.agent_info.get("name") or "unknown",
                "agent.info.sdk_version": self.agent_info.get("agent_sdk_version") or "unknown",
            }
        )

    def stop(self) -> None:
        if self.provider is not None:
            self.provider.shutdown()

    @staticmethod
    def _views() -> list[View]:
        return [
            View(
                instrument_type=Histogram,
                instrument_unit="s",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300]
                ),
            ),
            View(
                instrument_name="gen_ai.client.token.usage",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=[1, 8, 32, 128, 512, 1024, 2048, 4096, 8192, 16384, 32768]
                ),
            ),
            View(
                instrument_name="aidev.sse.response.size",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=[64, 256, 1024, 4096, 16384, 65536, 262144, 1048576]
                ),
            ),
        ]

    @staticmethod
    def _create_exporter(endpoint: dict[str, Any]):
        url = endpoint["url"]
        headers = {"x-bk-token": endpoint.get("token", "")} if endpoint.get("token") else {}
        exporter_type = endpoint["exporter_type"]
        if exporter_type == ExporterType.GRPC:
            return GRPCMetricExporter(endpoint=url, insecure=True, headers=headers)
        if exporter_type == ExporterType.HTTP:
            if not url.endswith("/v1/metrics"):
                url = f"{url.rstrip('/')}/v1/metrics"
            return HTTPMetricExporter(endpoint=url, headers=headers)
        raise ValueError(f"Unsupported OTLP exporter type: {exporter_type}")
