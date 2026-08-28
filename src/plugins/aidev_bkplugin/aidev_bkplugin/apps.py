# -*- coding: utf-8 -*-

import logging

from aidev_agent.utils.module_loading import import_string
from django.apps import AppConfig
from django.conf import settings

from aidev_bkplugin.services.metric_runtime import set_metric_service

try:
    import bkoauth
except ImportError:
    bkoauth = None

# OpenTelemetry 是可选 extras，未安装时降级为 no-op。
# 安装方式：pip install aidev-bkplugin[opentelemetry]
try:
    from aidev_agent.packages.opentelemetry import BkAidevAgentInstrumentor
    from aidev_agent.packages.opentelemetry.config import OTelConfig
    from aidev_agent.packages.opentelemetry.utils import (
        get_otel_endpoint_by_agent_info,
        get_otel_endpoint_by_env,
        get_otel_endpoint_by_json_str,
    )
except ImportError:
    BkAidevAgentInstrumentor = None
    OTelConfig = None
    get_otel_endpoint_by_agent_info = None
    get_otel_endpoint_by_env = None
    get_otel_endpoint_by_json_str = None

try:
    from aidev_agent.packages.opentelemetry.metrics import configure_metric_identity

    from aidev_bkplugin.services.otel_metrics import (
        BkPluginMetricService,
        MetricExportSettings,
    )
except ImportError:
    configure_metric_identity = None
    BkPluginMetricService = None
    MetricExportSettings = None

try:
    from aidev_bkplugin.tasks import push_bkm_metrics_task
except ImportError:
    push_bkm_metrics_task = None

try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
except ImportError:
    HTTPXClientInstrumentor = None

try:
    from opentelemetry.instrumentation.threading import ThreadingInstrumentor
except ImportError:
    ThreadingInstrumentor = None

logger = logging.getLogger(__name__)


def init_bk_aidev_agent_otel() -> None:
    """
    初始化 BK AIDEV Agent OpenTelemetry。

    按优先级收集所有 OTEL Endpoint 配置：
    1. BKAI_AGENT_OTEL_ENDPOINTS 环境变量（支持多地址）
    2. agent_info 中的 otel_url / otel_token（单地址）
    3. OTEL_GRPC_URL + OTEL_BK_DATA_TOKEN 环境变量（单地址）

    如果未安装 opentelemetry extras，跳过初始化。
    """
    if BkAidevAgentInstrumentor is None:
        logger.info(
            "[aidev_bkplugin] OpenTelemetry extras 未安装，跳过自动 instrument；"
            "如需启用请安装 aidev-bkplugin[opentelemetry]。"
        )
        return

    # 先解析全局开关，避免本地评测或显式关闭 OTel 的进程仍为 endpoint/identity
    # 发起 Agent 配置远程请求。默认值保持开启，不改变线上既有初始化行为。
    otel_config = OTelConfig(otel_endpoints=[])
    if not getattr(otel_config, "enabled", True):
        logger.info("[aidev_bkplugin] OpenTelemetry disabled; remote initialization skipped")
        set_metric_service(None)
        return

    if getattr(otel_config, "trace_exporter", "otlp") == "logging":
        # 本地评测只需要 trace/span，禁用远程 endpoint 探测和指标上报，
        # 由 Agent SDK 的 LoggingSpanExporter 写入应用日志。
        otel_config.enable_metrics = False
        otel_config.enable_logs = False
        set_metric_service(None)
        BkAidevAgentInstrumentor(config=otel_config).instrument()
        logger.info("[aidev_bkplugin] OpenTelemetry local logging export enabled")
        return

    from aidev_bkplugin.services.agent_config import AgentConfigFetcher

    endpoints = []
    # 1. 从 BKAI_AGENT_OTEL_ENDPOINTS 解析多地址
    try:
        endpoints.extend(get_otel_endpoint_by_json_str())
    except ValueError as e:
        logger.warning(
            "[aidev_bkplugin] 解析 BKAI_AGENT_OTEL_ENDPOINTS 失败：%s，跳过该配置来源。",
            e,
        )
    # 2. 从 agent_info 获取单地址
    agent_info = AgentConfigFetcher.get_info()
    endpoints.extend(get_otel_endpoint_by_agent_info(agent_info=agent_info))
    # 3. 从 OTEL_GRPC_URL 和 OTEL_BK_DATA_TOKEN 获取单地址
    endpoints.extend(get_otel_endpoint_by_env())

    otel_config.otel_endpoints = endpoints
    if configure_metric_identity is None or BkPluginMetricService is None or MetricExportSettings is None:
        logger.info("[aidev_bkplugin] metric OpenTelemetry extras unavailable; metric export skipped")
        otel_config.enable_metrics = False
        BkAidevAgentInstrumentor(config=otel_config).instrument()
        return
    try:
        metric_settings = MetricExportSettings.from_agent_info(
            agent_info,
            default_enabled=otel_config.enable_metrics,
        )
        otel_config.enable_metrics = metric_settings.enabled
        otel_config.metric_export_interval_millis = metric_settings.export_interval_millis
        otel_config.metric_export_timeout_millis = metric_settings.export_timeout_millis
        configure_metric_identity(
            agent_info.get("agent_code") or otel_config.service_name,
            agent_info.get("agent_name"),
            agent_info.get("agent_sdk_version"),
        )
        if metric_settings.export_via_celery:
            metric_service = BkPluginMetricService(
                service_name=otel_config.service_name,
                endpoints=endpoints,
                agent_info=agent_info,
                settings=metric_settings,
                enqueue_bkm_metrics=push_bkm_metrics_task.delay if push_bkm_metrics_task is not None else None,
            )
            set_metric_service(metric_service)
            otel_config.enable_metrics = metric_service.start()
            otel_config.metric_provider_managed_externally = otel_config.enable_metrics
            if not otel_config.enable_metrics:
                set_metric_service(None)
        else:
            # 直连 OTLP 继续复用 Agent SDK 原有的 MetricProvider / MetricExporter；
            # bkplugin 只负责根据 agent_info 选择该路径并传入配置。
            set_metric_service(None)
            otel_config.metric_provider_managed_externally = False
    except Exception:  # noqa: BLE001
        logger.exception("[aidev_bkplugin] metric export initialization failed; continuing without metrics")
        set_metric_service(None)
        otel_config.enable_metrics = False
    BkAidevAgentInstrumentor(config=otel_config).instrument()


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_bkplugin"

    def ready(self) -> None:
        from aidev_agent.packages.resource_manager import resource_manager
        from aidev_agent.services.common_agent import (
            CommonQAAgent,
            common_agent_factory,
        )

        if bkoauth:
            bkoauth._init_function()

        # 仅当 AIDEV_AGENT 解析出的类与 SDK 默认 CommonQAAgent 不一致时，实例化后注入；
        # 缺省值即继续使用 SDK 默认实例（来自 common_agent_factory 的 default）。
        custom_agent_cls = import_string(settings.AIDEV_AGENT)
        if custom_agent_cls is not CommonQAAgent:
            common_agent_factory.replace_defaults(custom_agent_cls())

        custom_resource_manager = getattr(settings, "AIDEV_RESOURCE_MANAGER", "")
        if custom_resource_manager:
            resource_manager.replace_defaults(import_string(custom_resource_manager)())

        # 初始化 OpenTelemetry
        init_bk_aidev_agent_otel()

        # 注入 httpx (LLM 网关底层 HTTP 客户端) 的 trace 传播
        # 使 LLM 调用自动携带 traceparent header，网关可加入分布式追踪
        try:
            HTTPXClientInstrumentor().instrument()
        except Exception:  # noqa: BLE001
            logger.debug("opentelemetry-instrumentation-httpx not available, skipping httpx instrumentation")
        # 注入跨线程的 trace 传递，因为知识库中 LLM 提交是异步的
        try:
            ThreadingInstrumentor().instrument()
        except Exception:  # noqa: BLE001
            logger.debug("opentelemetry-instrumentation-threading not available, skipping httpx instrumentation")

        return super().ready()
