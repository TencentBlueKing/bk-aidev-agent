# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging
import platform
import socket
from typing import Optional, Type

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter as GRPCLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GRPCMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCSpanExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter as HTTPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HTTPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import Histogram, MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import ProcessResourceDetector, Resource, ResourceDetector, get_aggregated_resources
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from typing_extensions import assert_never

try:
    from opentelemetry.sdk.resources import OsResourceDetector
except ImportError:
    OsResourceDetector: Optional[Type[ResourceDetector]] = None


from .config import  OTelConfig
from .utils import ExporterType
logger = logging.getLogger(__name__)


class BkAgentOTelService:
    """
    Agent 专用的 OTel 服务

    负责初始化 OpenTelemetry SDK,配置 Resource 和 Tracer Provider
    """

    def __init__(self, config: OTelConfig):
        """
        初始化 OTel 服务

        Args:
            config: OTel 配置对象
        """
        self.config = config
        self.tracer_provider: Optional[TracerProvider] = None
        self.meter_provider: Optional[MeterProvider] = None
        self.logger_provider: Optional[LoggerProvider] = None

    def start(self):
        """启动 OTel 服务"""
        if not self.config.enabled:
            logger.info("OTel service is disabled")
            return
        logger.info("Starting OTel service...")
        # 创建 Resource
        resource = self._create_resource()
        # 设置 Traces
        if self.config.enable_traces:
            self._setup_traces(resource)
        if self.config.enable_metrics:
            self._setup_metrics(resource)
        if self.config.enable_logs:
            self._setup_logs(resource)
        logger.info("OTel service started successfully")

    def stop(self):
        """停止 OTel 服务"""
        if not self.config.enabled:
            return
        logger.info("Stopping OTel service...")
        if self.tracer_provider:
            self.tracer_provider.shutdown()
        if self.meter_provider:
            self.meter_provider.shutdown()
        if self.logger_provider:
            self.logger_provider.shutdown()
        logger.info("OTel service stopped successfully")

    def _create_resource(self) -> Resource:
        detectors = [ProcessResourceDetector()]
        if OsResourceDetector is not None:
            detectors.append(OsResourceDetector())
        # create 提供了部分 SDK 默认属性
        initial_resource = Resource.create(
            {
                # ❗❗【非常重要】应用服务唯一标识
                ResourceAttributes.SERVICE_NAME: self.config.service_name,
                ResourceAttributes.OS_TYPE: platform.system().lower(),
                ResourceAttributes.HOST_NAME: socket.gethostname(),
            }
        )
        return get_aggregated_resources(detectors, initial_resource)

    def _setup_traces(self, resource: Resource):
        """
        设置 Traces - 支持多个上报地址

        Args:
            resource: Resource 实例
        """
        # 创建 TracerProvider
        self.tracer_provider = TracerProvider(resource=resource)

        # 为每个端点创建独立的 SpanProcessor
        for idx, endpoint_config in enumerate(self.config.otel_endpoints):
            try:
                # 创建该端点的 Exporter
                exporter = self._create_trace_exporter(endpoint_config)
                # 获取该端点的批处理配置
                batch_config = {
                    "max_queue_size": endpoint_config.get("batch_max_queue_size"),
                    "schedule_delay_millis": endpoint_config.get("batch_schedule_delay_millis"),
                    "export_timeout_millis": endpoint_config.get("batch_export_timeout_millis"),
                    "max_export_batch_size": endpoint_config.get("batch_max_export_batch_size"),
                }
                # 创建 BatchSpanProcessor
                span_processor = BatchSpanProcessor(exporter, **batch_config)
                # 添加到 TracerProvider
                self.tracer_provider.add_span_processor(span_processor)
                logger.info(
                    f"Trace processor {idx + 1}/{len(self.config.otel_endpoints)} added: "
                    f"url={endpoint_config['url']}, type={endpoint_config['exporter_type'].value}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to setup trace processor for endpoint {endpoint_config['url']}: {e}", exc_info=True
                )
                # 某个端点失败不影响其他端点,继续处理

    def _create_trace_exporter(self, endpoint_config: dict):
        """
        创建 Trace Exporter (支持独立配置)

        Args:
            endpoint_config: 端点配置字典,包含 url, token, exporter_type 等

        Returns:
            OTLPSpanExporter 实例
        """
        url = endpoint_config["url"]
        token = endpoint_config["token"]
        exporter_type = endpoint_config["exporter_type"]

        headers = {"x-bk-token": token} if token else {}

        if exporter_type == ExporterType.GRPC:
            return GRPCSpanExporter(
                endpoint=url,
                # insecure=True,  # 生产环境建议使用 TLS
                headers=headers,
            )
        elif exporter_type == ExporterType.HTTP:
            # HTTP 协议需要在 endpoint 后添加 /v1/traces
            if not url.endswith("/v1/traces"):
                url = f"{url.rstrip('/')}/v1/traces"
            return HTTPSpanExporter(endpoint=url, headers=headers)
        else:
            assert_never(exporter_type)

    def _setup_metrics(self, resource: Resource):
        """
        设置 Metrics - 支持多个上报地址

        Args:
            resource: Resource 实例
        """
        # 为每个端点创建独立的 Reader
        readers = []
        for idx, endpoint_config in enumerate(self.config.otel_endpoints):
            try:
                # 创建该端点的 Metric Exporter
                exporter = self._create_metric_exporter(endpoint_config)

                # 创建 PeriodicExportingMetricReader
                reader = PeriodicExportingMetricReader(exporter)
                readers.append(reader)

                logger.info(
                    f"Metric reader {idx + 1}/{len(self.config.otel_endpoints)} added: "
                    f"url={endpoint_config['url']}, type={endpoint_config['exporter_type'].value}"
                )

            except Exception as e:
                logger.error(f"Failed to setup metric reader for endpoint {endpoint_config['url']}: {e}", exc_info=True)
                # 某个端点失败不影响其他端点,继续处理

        # 配置 Histogram 视图
        histogram_view = View(
            instrument_type=Histogram,
            instrument_unit="s",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=[0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0]
            ),
        )

        # 创建 MeterProvider
        self.meter_provider = MeterProvider(resource=resource, metric_readers=readers, views=[histogram_view])
        metrics.set_meter_provider(self.meter_provider)

    def _create_metric_exporter(self, endpoint_config: dict):
        """
        创建 Metric Exporter (支持独立配置)

        Args:
            endpoint_config: 端点配置字典

        Returns:
            OTLPMetricExporter 实例
        """
        url = endpoint_config["url"]
        token = endpoint_config["token"]
        exporter_type = endpoint_config["exporter_type"]

        headers = {"x-bk-token": token} if token else {}

        if exporter_type == ExporterType.GRPC:
            return GRPCMetricExporter(endpoint=url, insecure=True, headers=headers)
        elif exporter_type == ExporterType.HTTP:
            if not url.endswith("/v1/metrics"):
                url = f"{url.rstrip('/')}/v1/metrics"
            return HTTPMetricExporter(endpoint=url, headers=headers)
        else:
            assert_never(exporter_type)

    def _setup_logs(self, resource: Resource):
        """
        设置 Logs - 支持多个上报地址

        Args:
            resource: Resource 实例
        """
        # 创建 LoggerProvider
        self.logger_provider = LoggerProvider(resource=resource)

        # 为每个端点创建独立的 LogRecordProcessor
        for idx, endpoint_config in enumerate(self.config.otel_endpoints):
            try:
                # 创建该端点的 Log Exporter
                exporter = self._create_log_exporter(endpoint_config)

                # 创建 BatchLogRecordProcessor
                processor = BatchLogRecordProcessor(exporter)

                # 添加到 LoggerProvider
                self.logger_provider.add_log_record_processor(processor)

                logger.info(
                    f"Log processor {idx + 1}/{len(self.config.otel_endpoints)} added: "
                    f"url={endpoint_config['url']}, type={endpoint_config['exporter_type'].value}"
                )

            except Exception as e:
                logger.error(f"Failed to setup log processor for endpoint {endpoint_config['url']}: {e}", exc_info=True)
                # 某个端点失败不影响其他端点,继续处理

        # 配置 LoggingHandler
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=self.logger_provider)
        logging.getLogger("otel").addHandler(handler)

    def _create_log_exporter(self, endpoint_config: dict):
        """
        创建 Log Exporter (支持独立配置)

        Args:
            endpoint_config: 端点配置字典

        Returns:
            OTLPLogExporter 实例
        """
        url = endpoint_config["url"]
        token = endpoint_config["token"]
        exporter_type = endpoint_config["exporter_type"]

        headers = {"x-bk-token": token} if token else {}

        if exporter_type == ExporterType.GRPC:
            return GRPCLogExporter(endpoint=url, insecure=True, headers=headers)
        elif exporter_type == ExporterType.HTTP:
            if not url.endswith("/v1/logs"):
                url = f"{url.rstrip('/')}/v1/logs"
            return HTTPLogExporter(endpoint=url, headers=headers)
        else:
            assert_never(exporter_type)

    def get_tracer(self, name: str):
        """
        获取 Tracer 实例

        Args:
            name: Tracer 名称,通常使用 __name__

        Returns:
            Tracer 实例
        """
        # 如果未启用 trace 或未正确初始化 tracer_provider，则回退到全局 Tracer
        if not self.config.enabled or not self.config.enable_traces or self.tracer_provider is None:
            return trace.get_tracer(name)

        # 使用 Agent 专用的 TracerProvider，避免影响全局 Tracer 配置
        return self.tracer_provider.get_tracer(name)

    def __str__(self):
        return f"AgentOTLPService(service_name={self.config.service_name})"
