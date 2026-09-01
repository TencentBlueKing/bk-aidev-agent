# -*- coding: utf-8 -*-
"""bkplugin-owned OpenTelemetry metric provider with BKM worker export."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

import requests
from aidev_agent.config import settings as agent_settings
from aidev_agent.packages.opentelemetry.metrics import (
    AGENT_ITERATION_HISTOGRAM_BOUNDARIES,
    DURATION_HISTOGRAM_BOUNDARIES,
    MESSAGE_SIZE_HISTOGRAM_BOUNDARIES,
)
from aidev_agent.packages.opentelemetry.utils import ExporterType
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GRPCMetricExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HTTPMetricExporter
from opentelemetry.sdk.metrics import Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import (
    Gauge,
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
    Sum,
)
from opentelemetry.sdk.metrics.export import (
    Histogram as HistogramData,
)
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

from .metric_runtime import RetryableMetricPushError

logger = logging.getLogger(__name__)

DEFAULT_METRIC_EXPORT_INTERVAL_MILLIS = 10_000
BKM_PUSH_MODE_CELERY = "celery"
BKM_PUSH_MODE_DIRECT = "direct"
BKM_PUSH_MODES = frozenset({BKM_PUSH_MODE_CELERY, BKM_PUSH_MODE_DIRECT})


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_bkm_push_url(value: Any) -> str:
    """Expand a proxy host or base URL to the BKM v2 push endpoint."""
    raw_url = str(value or "").strip()
    if not raw_url:
        return ""
    if "://" not in raw_url:
        raw_url = f"http://{raw_url}"
    parsed = urlparse(raw_url)
    netloc = parsed.netloc
    if parsed.port is None:
        netloc = f"{netloc}:10205"
    path = parsed.path if parsed.path not in ("", "/") else "/v2/push/"
    return urlunparse((parsed.scheme, netloc, path, "", parsed.query, ""))


@dataclass(frozen=True)
class MetricExportSettings:
    """Metric-specific settings parsed from decoded ``agent_info.otel_info``."""

    enabled: bool
    export_interval_millis: int = DEFAULT_METRIC_EXPORT_INTERVAL_MILLIS
    export_timeout_millis: int = 30000
    export_via_celery: bool = True
    bkm_push_mode: str = BKM_PUSH_MODE_CELERY
    bkm_data_id: int | None = None
    bkm_access_token: str = ""
    bkm_push_url: str = ""
    bkm_target: str = ""
    task_ttl_seconds: int = agent_settings.BKAI_AGENT_METRICS_TASK_TTL_SECONDS

    @classmethod
    def from_agent_info(cls, agent_info: dict[str, Any] | None, *, default_enabled: bool) -> "MetricExportSettings":
        otel_info = (agent_info or {}).get("otel_info") or {}
        metrics_info = otel_info.get("metrics") or {}
        interval = agent_settings.BKAI_AGENT_METRICS_EXPORT_INTERVAL_MILLIS
        if interval is None:
            interval = metrics_info.get(
                "export_interval_millis",
                otel_info.get("metric_export_interval_millis", DEFAULT_METRIC_EXPORT_INTERVAL_MILLIS),
            )
        timeout = metrics_info.get(
            "export_timeout_millis",
            otel_info.get("metric_export_timeout_millis", 30000),
        )
        task_ttl_seconds = metrics_info.get(
            "task_ttl_seconds",
            agent_settings.BKAI_AGENT_METRICS_TASK_TTL_SECONDS,
        )
        export_via_celery = metrics_info.get(
            "export_via_celery",
            otel_info.get("metric_export_via_celery"),
        )
        bkm_push_mode = (
            str(
                metrics_info.get(
                    "push_mode",
                    otel_info.get("metric_push_mode", agent_settings.BKAI_AGENT_METRICS_PUSH_MODE),
                )
            )
            .strip()
            .lower()
        )
        if bkm_push_mode not in BKM_PUSH_MODES:
            raise ValueError(
                f"Unsupported metric push mode: {bkm_push_mode!r}; expected one of {sorted(BKM_PUSH_MODES)}"
            )
        data_id = metrics_info.get("agent_data_id", agent_settings.BKAI_AGENT_METRICS_DATA_ID)
        access_token = metrics_info.get("agent_access_token", agent_settings.BKAI_AGENT_METRICS_TOKEN)
        push_url = metrics_info.get("agent_push_url", agent_settings.BKAI_AGENT_METRICS_HOST)
        push_url = _normalize_bkm_push_url(push_url)
        target = metrics_info.get("agent_target", agent_settings.BKAI_AGENT_METRICS_TARGET)
        has_bkm_config = data_id not in (None, "") and bool(access_token and push_url)
        if export_via_celery is None:
            export_via_celery = has_bkm_config
        environment_enabled = agent_settings.BKAI_AGENT_ENABLE_METRICS
        enabled = (
            environment_enabled
            if environment_enabled is not None
            else metrics_info.get("enabled", otel_info.get("enable_metrics", default_enabled or has_bkm_config))
        )
        return cls(
            enabled=_as_bool(enabled),
            export_interval_millis=max(10_000, int(interval)),
            export_timeout_millis=max(1000, int(timeout)),
            task_ttl_seconds=max(1, int(task_ttl_seconds)),
            export_via_celery=_as_bool(export_via_celery),
            bkm_push_mode=bkm_push_mode,
            bkm_data_id=int(data_id) if data_id not in (None, "") else None,
            bkm_access_token=str(access_token or ""),
            bkm_push_url=str(push_url or ""),
            bkm_target=str(target or ""),
        )


def _bkm_endpoint_key(settings: MetricExportSettings) -> str:
    """Return a stable BKM endpoint identity without exposing its access token."""
    identity = f"{settings.bkm_data_id}\0{settings.bkm_push_url}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _bkm_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", value)


def _bkm_metric_name(name: str, unit: str) -> str:
    """Match the Prometheus exporter's stable unit suffixes for BKM metrics."""
    metric_name = _bkm_name(name)
    unit_suffix = {"s": "seconds", "By": "bytes"}.get(unit)
    if unit_suffix and not metric_name.endswith(f"_{unit_suffix}"):
        return f"{metric_name}_{unit_suffix}"
    return metric_name


def _bkm_dimension_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def _bkm_record(
    *,
    metric_name: str,
    value: int | float,
    dimensions: dict[str, str],
    target: str,
    timestamp: int,
) -> dict[str, Any]:
    return {
        "metrics": {metric_name: value},
        "target": target,
        "dimension": dimensions,
        "timestamp": timestamp,
    }


def _bkm_records(metrics_data: MetricsData, target: str) -> list[dict[str, Any]]:
    """Convert an OTel cumulative snapshot into BKM custom metric records."""
    records: list[dict[str, Any]] = []
    resource_dimension_names = {
        "service.name",
        "service.instance.id",
        "agent.info.code",
        "agent.info.name",
        "agent.info.sdk_version",
    }
    for resource_metrics in metrics_data.resource_metrics:
        resource_dimensions = {
            _bkm_name(key): _bkm_dimension_value(value)
            for key, value in resource_metrics.resource.attributes.items()
            if key in resource_dimension_names
        }
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                metric_name = _bkm_metric_name(metric.name, metric.unit)
                for point in metric.data.data_points:
                    dimensions = dict(resource_dimensions)
                    dimensions.update(
                        {_bkm_name(key): _bkm_dimension_value(value) for key, value in (point.attributes or {}).items()}
                    )
                    timestamp = point.time_unix_nano // 1_000_000
                    if isinstance(metric.data, Sum):
                        sum_name = (
                            f"{metric_name}_total"
                            if metric.data.is_monotonic and not metric_name.endswith("_total")
                            else metric_name
                        )
                        records.append(
                            _bkm_record(
                                metric_name=sum_name,
                                value=point.value,
                                dimensions=dimensions,
                                target=target,
                                timestamp=timestamp,
                            )
                        )
                    elif isinstance(metric.data, Gauge):
                        records.append(
                            _bkm_record(
                                metric_name=metric_name,
                                value=point.value,
                                dimensions=dimensions,
                                target=target,
                                timestamp=timestamp,
                            )
                        )
                    elif isinstance(metric.data, HistogramData):
                        cumulative_count = 0
                        for bound, bucket_count in zip(
                            [*point.explicit_bounds, "+Inf"],
                            point.bucket_counts,
                            strict=True,
                        ):
                            cumulative_count += bucket_count
                            bucket_dimensions = {**dimensions, "le": str(bound)}
                            records.append(
                                _bkm_record(
                                    metric_name=f"{metric_name}_bucket",
                                    value=cumulative_count,
                                    dimensions=bucket_dimensions,
                                    target=target,
                                    timestamp=timestamp,
                                )
                            )
                        records.extend(
                            [
                                _bkm_record(
                                    metric_name=f"{metric_name}_sum",
                                    value=point.sum,
                                    dimensions=dimensions,
                                    target=target,
                                    timestamp=timestamp,
                                ),
                                _bkm_record(
                                    metric_name=f"{metric_name}_count",
                                    value=point.count,
                                    dimensions=dimensions,
                                    target=target,
                                    timestamp=timestamp,
                                ),
                            ]
                        )
    return records


class BkmMetricExporter(MetricExporter):
    """Convert one periodic OTel snapshot and publish it through a selected transport."""

    def __init__(self, endpoint_key: str, target: str) -> None:
        super().__init__()
        self.endpoint_key = endpoint_key
        self.target = target

    def export(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10000,
        **kwargs: Any,
    ) -> MetricExportResult:
        try:
            records = _bkm_records(metrics_data, self.target)
            if not records:
                return MetricExportResult.SUCCESS
            payload = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
            self._publish(payload)
        except Exception:  # noqa: BLE001
            logger.exception(
                "[aidev_bkplugin] failed to publish metric snapshot for endpoint %s",
                self.endpoint_key,
            )
            return MetricExportResult.FAILURE
        return MetricExportResult.SUCCESS

    def _publish(self, payload: str) -> None:
        raise NotImplementedError

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        return True

    def shutdown(self, timeout_millis: float = 30000, **kwargs: Any) -> None:
        return None


class CeleryMetricExporter(BkmMetricExporter):
    """Delegate one periodic BKM snapshot to Celery."""

    def __init__(
        self,
        endpoint_key: str,
        target: str,
        enqueue: Callable[[str, str, int, int], Any],
        task_ttl_seconds: int = agent_settings.BKAI_AGENT_METRICS_TASK_TTL_SECONDS,
    ) -> None:
        super().__init__(endpoint_key, target)
        self.task_ttl_seconds = task_ttl_seconds
        self.enqueue = enqueue

    def _publish(self, payload: str) -> None:
        created_at_millis = time.time_ns() // 1_000_000
        self.enqueue(self.endpoint_key, payload, created_at_millis, self.task_ttl_seconds)


class DirectBkmMetricExporter(BkmMetricExporter):
    """Push one periodic BKM snapshot directly from the metric reader thread."""

    def __init__(self, endpoint_key: str, target: str, push: Callable[[str, str], Any]) -> None:
        super().__init__(endpoint_key, target)
        self.push = push

    def _publish(self, payload: str) -> None:
        self.push(self.endpoint_key, payload)


class BkPluginMetricService:
    """Own the metric SDK lifecycle; the Agent SDK only calls metric APIs."""

    def __init__(
        self,
        *,
        service_name: str,
        endpoints: list[dict[str, Any]],
        agent_info: dict[str, Any] | None,
        settings: MetricExportSettings,
        enqueue_bkm_metrics: Callable[[str, str, int, int], Any] | None = None,
    ) -> None:
        self.service_name = service_name
        self.endpoints = endpoints
        self.agent_info = agent_info or {}
        self.settings = settings
        self.enqueue_bkm_metrics = enqueue_bkm_metrics
        self.provider: MeterProvider | None = None

    def start(self) -> bool:
        if not self.settings.enabled:
            logger.info("[aidev_bkplugin] metric export disabled")
            return False
        readers = []
        if self.settings.export_via_celery:
            if self.settings.bkm_push_mode == BKM_PUSH_MODE_CELERY and self.enqueue_bkm_metrics is None:
                logger.warning("[aidev_bkplugin] BKM metric export enabled but Celery enqueue is unavailable")
                return False
            if not self.settings.bkm_data_id or not self.settings.bkm_access_token or not self.settings.bkm_push_url:
                logger.warning("[aidev_bkplugin] BKM metric export enabled but push configuration is incomplete")
                return False
            readers.append(
                PeriodicExportingMetricReader(
                    self._create_bkm_exporter(),
                    export_interval_millis=self.settings.export_interval_millis,
                    export_timeout_millis=self.settings.export_timeout_millis,
                )
            )
        else:
            if not self.endpoints:
                logger.warning("[aidev_bkplugin] direct metric export enabled but no OTLP endpoint configured")
                return False
            for endpoint in self.endpoints:
                readers.append(
                    PeriodicExportingMetricReader(
                        self._create_exporter(endpoint),
                        export_interval_millis=self.settings.export_interval_millis,
                        export_timeout_millis=self.settings.export_timeout_millis,
                    )
                )

        self.provider = MeterProvider(resource=self._create_resource(), metric_readers=readers, views=self._views())
        metrics.set_meter_provider(self.provider)
        if metrics.get_meter_provider() is not self.provider:
            logger.warning(
                "[aidev_bkplugin] metric export disabled because the global MeterProvider is already configured"
            )
            self.provider.shutdown()
            self.provider = None
            return False
        transport = f"bkm_{self.settings.bkm_push_mode}" if self.settings.export_via_celery else "otlp_direct"
        logger.info(
            "[aidev_bkplugin] metric export started with %d reader(s), transport=%s",
            len(readers),
            transport,
        )
        return True

    def _create_bkm_exporter(self) -> BkmMetricExporter:
        target = self.settings.bkm_target or socket.gethostname()
        endpoint_key = _bkm_endpoint_key(self.settings)
        if self.settings.bkm_push_mode == BKM_PUSH_MODE_DIRECT:
            return DirectBkmMetricExporter(endpoint_key, target, self.push_bkm)
        if self.enqueue_bkm_metrics is None:
            raise RuntimeError("Celery metric enqueue is unavailable")
        return CeleryMetricExporter(
            endpoint_key=endpoint_key,
            target=target,
            enqueue=self.enqueue_bkm_metrics,
            task_ttl_seconds=self.settings.task_ttl_seconds,
        )

    def push_bkm(self, endpoint_key: str, payload: str) -> None:
        if endpoint_key != _bkm_endpoint_key(self.settings):
            raise ValueError(f"Unknown metric endpoint key: {endpoint_key}")
        records = json.loads(payload)
        if not isinstance(records, list):
            raise ValueError("BKM metric payload must be a list")
        report_data = {
            "data_id": self.settings.bkm_data_id,
            "access_token": self.settings.bkm_access_token,
            "data": records,
        }
        try:
            response = requests.post(
                self.settings.bkm_push_url,
                json=report_data,
                timeout=max(1.0, self.settings.export_timeout_millis / 1000),
            )
        except (requests.ConnectionError, requests.Timeout) as error:
            raise RetryableMetricPushError("BKM metric push failed due to a transient network error") from error
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise RetryableMetricPushError(f"BKM metric push returned retryable HTTP {response.status_code}")
        response.raise_for_status()

    def _create_resource(self) -> Resource:
        return Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: self.service_name,
                "service.instance.id": f"{socket.gethostname()}:{os.getpid()}",
                "agent.info.code": self.agent_info.get("agent_code") or self.service_name,
                "agent.info.name": self.agent_info.get("agent_name") or "unknown",
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
                aggregation=ExplicitBucketHistogramAggregation(boundaries=DURATION_HISTOGRAM_BOUNDARIES),
            ),
            View(
                instrument_name="aidev.message.publish.size",
                aggregation=ExplicitBucketHistogramAggregation(boundaries=MESSAGE_SIZE_HISTOGRAM_BOUNDARIES),
            ),
            View(
                instrument_name="gen_ai.invoke_agent.iteration_count",
                aggregation=ExplicitBucketHistogramAggregation(boundaries=AGENT_ITERATION_HISTOGRAM_BOUNDARIES),
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
