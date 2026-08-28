from __future__ import annotations

import importlib
import json
import sys
from types import ModuleType

import pytest
import requests

pytest.importorskip("opentelemetry.sdk.metrics")

from aidev_agent.packages.opentelemetry.metrics import (
    AGENT_ITERATION_HISTOGRAM_BOUNDARIES,
    DURATION_HISTOGRAM_BOUNDARIES,
    MESSAGE_SIZE_HISTOGRAM_BOUNDARIES,
)
from aidev_bkplugin.services.metric_runtime import RetryableMetricPushError
from aidev_bkplugin.services.otel_metrics import (
    BkPluginMetricService,
    CeleryMetricExporter,
    MetricExportSettings,
    _bkm_endpoint_key,
    _bkm_metric_name,
    _bkm_records,
    _normalize_bkm_push_url,
)
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    Histogram,
    HistogramDataPoint,
    Metric,
    MetricExportResult,
    MetricsData,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
    Sum,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.util.instrumentation import InstrumentationScope


def _import_tasks_with_celery_stub(mocker):
    """Load task functions without requiring the template-only Celery dependency."""
    celery = ModuleType("celery")

    def shared_task(**options):
        def decorate(function):
            function.shared_task_options = options
            return function

        return decorate

    celery.shared_task = shared_task
    mocker.patch.dict(sys.modules, {"celery": celery})
    sys.modules.pop("aidev_bkplugin.tasks", None)
    return importlib.import_module("aidev_bkplugin.tasks")


def _sample_metrics_data() -> MetricsData:
    timestamp = 1_786_300_118_338_000_000
    counter = Metric(
        name="aidev.sse.event.count",
        description="SSE events",
        unit="{event}",
        data=Sum(
            data_points=[NumberDataPoint({"handler.type": "redis"}, timestamp - 1, timestamp, 3)],
            aggregation_temporality=AggregationTemporality.CUMULATIVE,
            is_monotonic=True,
        ),
    )
    duration = Metric(
        name="gen_ai.invoke_agent.duration",
        description="Agent duration",
        unit="s",
        data=Histogram(
            data_points=[
                HistogramDataPoint(
                    {"error.type": "TimeoutError"},
                    timestamp - 1,
                    timestamp,
                    count=4,
                    sum=2.5,
                    bucket_counts=[1, 2, 1],
                    explicit_bounds=[0.1, 1.0],
                    min=0.05,
                    max=1.2,
                )
            ],
            aggregation_temporality=AggregationTemporality.CUMULATIVE,
        ),
    )
    resource = Resource.create(
        {
            "service.name": "ai-demo",
            "service.instance.id": "host:123",
            "agent.info.code": "ai-demo",
            "agent.info.name": "演示智能体",
            "agent.info.sdk_version": "2.2.3",
        }
    )
    scope_metrics = ScopeMetrics(InstrumentationScope("test"), [counter, duration], "")
    return MetricsData([ResourceMetrics(resource, [scope_metrics], "")])


def _bkm_settings(**overrides) -> MetricExportSettings:
    values = {
        "enabled": True,
        "bkm_data_id": 1001,
        "bkm_access_token": "secret",
        "bkm_push_url": "http://proxy:10205/v2/push/",
        "bkm_target": "127.0.0.1",
    }
    values.update(overrides)
    return MetricExportSettings(**values)


def test_metric_settings_parse_nested_otel_info():
    settings = MetricExportSettings.from_agent_info(
        {
            "otel_info": {
                "metrics": {
                    "enabled": True,
                    "export_interval_millis": 1500,
                    "export_timeout_millis": 7000,
                    "agent_data_id": "1001",
                    "agent_access_token": "metric-secret",
                    "agent_push_url": "http://proxy:10205/v2/push/",
                    "agent_target": "127.0.0.1",
                }
            }
        },
        default_enabled=False,
    )

    assert settings.enabled is True
    assert settings.export_interval_millis == 1500
    assert settings.export_timeout_millis == 7000
    assert settings.export_via_celery is True
    assert settings.bkm_data_id == 1001
    assert settings.bkm_access_token == "metric-secret"
    assert settings.bkm_push_url == "http://proxy:10205/v2/push/"
    assert settings.bkm_target == "127.0.0.1"


def test_metric_settings_use_local_environment_fallback(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_METRICS_DATA_ID", "1002")
    monkeypatch.setenv("BKAI_AGENT_METRICS_TOKEN", "local-secret")
    monkeypatch.setenv("BKAI_AGENT_METRICS_HOST", "local-proxy")
    monkeypatch.setenv("BKAI_AGENT_METRICS_TARGET", "local-target")

    settings = MetricExportSettings.from_agent_info({}, default_enabled=False)

    assert settings.enabled is True
    assert settings.bkm_data_id == 1002
    assert settings.bkm_access_token == "local-secret"
    assert settings.bkm_push_url == "http://local-proxy:10205/v2/push/"
    assert settings.bkm_target == "local-target"
    assert settings.export_via_celery is True
    assert settings.export_interval_millis == 10_000


def test_metric_settings_keep_direct_otlp_transport_without_bkm_config(monkeypatch):
    for name in ("BKAI_AGENT_METRICS_DATA_ID", "BKAI_AGENT_METRICS_TOKEN", "BKAI_AGENT_METRICS_HOST", "PROXY_IP"):
        monkeypatch.delenv(name, raising=False)

    settings = MetricExportSettings.from_agent_info({}, default_enabled=True)

    assert settings.enabled is True
    assert settings.export_via_celery is False


def test_metric_settings_do_not_reuse_trace_credentials(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_OTEL_TOKEN", "trace-secret")

    settings = MetricExportSettings.from_agent_info({}, default_enabled=False)

    assert settings.enabled is False
    assert settings.bkm_data_id is None
    assert settings.bkm_access_token == ""
    assert settings.bkm_push_url == ""


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("bk-report.example.com", "http://bk-report.example.com:10205/v2/push/"),
        ("http://proxy:10205", "http://proxy:10205/v2/push/"),
        ("http://proxy:10205/v2/push/", "http://proxy:10205/v2/push/"),
    ],
)
def test_normalize_bkm_push_url(configured, expected):
    assert _normalize_bkm_push_url(configured) == expected


def test_metric_settings_prefer_agent_info_over_local_environment(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_METRICS_DATA_ID", "1002")
    monkeypatch.setenv("BKAI_AGENT_METRICS_TOKEN", "local-secret")
    monkeypatch.setenv("BKAI_AGENT_METRICS_HOST", "local-proxy")

    settings = MetricExportSettings.from_agent_info(
        {
            "otel_info": {
                "metrics": {
                    "agent_data_id": 1003,
                    "agent_access_token": "platform-secret",
                    "agent_push_url": "http://platform-proxy:10205/v2/push/",
                }
            }
        },
        default_enabled=False,
    )

    assert settings.bkm_data_id == 1003
    assert settings.bkm_access_token == "platform-secret"
    assert settings.bkm_push_url == "http://platform-proxy:10205/v2/push/"


def test_metric_settings_parse_false_string_safely():
    settings = MetricExportSettings.from_agent_info(
        {"otel_info": {"metrics": {"enabled": "false"}}},
        default_enabled=True,
    )
    assert settings.enabled is False


def test_metric_settings_explicit_environment_disable_overrides_agent_info(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT_ENABLE_METRICS", "false")

    settings = MetricExportSettings.from_agent_info(
        {
            "otel_info": {
                "metrics": {
                    "enabled": True,
                    "agent_data_id": 1001,
                    "agent_access_token": "platform-secret",
                    "agent_push_url": "http://platform-proxy:10205/v2/push/",
                }
            }
        },
        default_enabled=True,
    )

    assert settings.enabled is False


def test_metric_resource_uses_agent_sdk_version_without_agent_type():
    service = BkPluginMetricService(
        service_name="ai-demo",
        endpoints=[],
        agent_info={"agent_code": "ai-demo", "agent_name": "演示智能体", "agent_sdk_version": "2.2.3"},
        settings=_bkm_settings(),
    )

    attributes = service._create_resource().attributes

    assert attributes["agent.info.sdk_version"] == "2.2.3"
    assert attributes["service.instance.id"]
    assert "agent.info.type" not in attributes


def test_metric_resource_does_not_use_noncanonical_agent_identity():
    service = BkPluginMetricService(
        service_name="agent-service",
        endpoints=[],
        agent_info={"code": "fallback-code", "name": "fallback-name"},
        settings=_bkm_settings(),
    )

    attributes = service._create_resource().attributes

    assert attributes["agent.info.code"] == "agent-service"
    assert attributes["agent.info.name"] == "unknown"


def test_metric_service_uses_agent_sdk_histogram_boundaries():
    views = BkPluginMetricService._views()

    assert tuple(views[0]._aggregation._boundaries) == DURATION_HISTOGRAM_BOUNDARIES
    assert tuple(views[1]._aggregation._boundaries) == MESSAGE_SIZE_HISTOGRAM_BOUNDARIES
    assert tuple(views[2]._aggregation._boundaries) == AGENT_ITERATION_HISTOGRAM_BOUNDARIES


def test_bkm_records_preserve_counter_and_histogram_semantics():
    records = _bkm_records(_sample_metrics_data(), "127.0.0.1")
    by_metric = {next(iter(record["metrics"])): record for record in records if "le" not in record["dimension"]}
    buckets = [record for record in records if "le" in record["dimension"]]

    counter = by_metric["aidev_sse_event_count_total"]
    assert counter["metrics"] == {"aidev_sse_event_count_total": 3}
    assert counter["dimension"]["handler_type"] == "redis"
    assert counter["dimension"]["agent_info_code"] == "ai-demo"
    assert counter["timestamp"] == 1_786_300_118_338
    assert counter["target"] == "127.0.0.1"
    assert [record["metrics"]["gen_ai_invoke_agent_duration_seconds_bucket"] for record in buckets] == [1, 3, 4]
    assert [record["dimension"]["le"] for record in buckets] == ["0.1", "1.0", "+Inf"]
    assert by_metric["gen_ai_invoke_agent_duration_seconds_sum"]["metrics"] == {
        "gen_ai_invoke_agent_duration_seconds_sum": 2.5
    }
    assert by_metric["gen_ai_invoke_agent_duration_seconds_count"]["metrics"] == {
        "gen_ai_invoke_agent_duration_seconds_count": 4
    }


@pytest.mark.parametrize(
    ("name", "unit", "expected"),
    [
        ("aidev.message.publish.duration", "s", "aidev_message_publish_duration_seconds"),
        ("aidev.message.publish.size", "By", "aidev_message_publish_size_bytes"),
        ("aidev.sse.event.count", "{event}", "aidev_sse_event_count"),
        ("custom.duration_seconds", "s", "custom_duration_seconds"),
    ],
)
def test_bkm_metric_name_matches_prometheus_unit_suffixes(name, unit, expected):
    assert _bkm_metric_name(name, unit) == expected


def test_celery_exporter_enqueues_bkm_records_without_credentials(mocker):
    delay = mocker.Mock()

    result = CeleryMetricExporter(
        endpoint_key="endpoint-fingerprint",
        target="127.0.0.1",
        enqueue=delay,
    ).export(_sample_metrics_data())

    assert result is MetricExportResult.SUCCESS
    endpoint_key, payload = delay.call_args.args
    assert endpoint_key == "endpoint-fingerprint"
    assert "secret" not in payload
    assert json.loads(payload)[0]["target"] == "127.0.0.1"


def test_metric_service_uses_credential_free_bkm_endpoint_key():
    settings = _bkm_settings()
    service = BkPluginMetricService(
        service_name="ai-demo",
        endpoints=[],
        agent_info={},
        settings=settings,
        enqueue_bkm_metrics=lambda *_args: None,
    )

    exporter = service._create_celery_exporter()

    assert isinstance(exporter, CeleryMetricExporter)
    assert exporter.endpoint_key == _bkm_endpoint_key(settings)
    assert settings.bkm_access_token not in exporter.endpoint_key


def test_metric_service_does_not_enable_incomplete_bkm_export():
    service = BkPluginMetricService(
        service_name="ai-demo",
        endpoints=[],
        agent_info={},
        settings=MetricExportSettings(enabled=True, bkm_data_id=1001),
    )

    assert service.start() is False
    assert service.provider is None


def test_metric_service_does_not_enable_when_global_provider_is_already_configured(mocker):
    existing_provider = mocker.Mock()
    new_provider = mocker.Mock()
    mocker.patch("aidev_bkplugin.services.otel_metrics.MeterProvider", return_value=new_provider)
    mocker.patch("aidev_bkplugin.services.otel_metrics.metrics.get_meter_provider", return_value=existing_provider)
    set_meter_provider = mocker.patch("aidev_bkplugin.services.otel_metrics.metrics.set_meter_provider")
    service = BkPluginMetricService(
        service_name="ai-demo",
        endpoints=[],
        agent_info={},
        settings=_bkm_settings(),
        enqueue_bkm_metrics=lambda *_args: None,
    )

    assert service.start() is False
    set_meter_provider.assert_called_once_with(new_provider)
    new_provider.shutdown.assert_called_once_with()
    assert service.provider is None


def test_worker_posts_bkm_report_with_process_local_credentials(mocker):
    post = mocker.patch("aidev_bkplugin.services.otel_metrics.requests.post")
    post.return_value.status_code = 200
    settings = _bkm_settings(export_timeout_millis=7000)
    service = BkPluginMetricService(service_name="ai-demo", endpoints=[], agent_info={}, settings=settings)
    records = [{"metrics": {"aidev_agent_active": 3}, "target": "127.0.0.1", "dimension": {}, "timestamp": 1}]

    service.push_bkm(_bkm_endpoint_key(settings), json.dumps(records))

    post.assert_called_once_with(
        "http://proxy:10205/v2/push/",
        json={"data_id": 1001, "access_token": "secret", "data": records},
        timeout=7.0,
    )
    post.return_value.raise_for_status.assert_called_once_with()


@pytest.mark.parametrize("status_code", [408, 425, 429, 500, 503])
def test_worker_marks_transient_bkm_status_as_retryable(mocker, status_code):
    post = mocker.patch("aidev_bkplugin.services.otel_metrics.requests.post")
    post.return_value.status_code = status_code
    service = BkPluginMetricService(service_name="ai-demo", endpoints=[], agent_info={}, settings=_bkm_settings())

    with pytest.raises(RetryableMetricPushError, match=str(status_code)):
        service.push_bkm(_bkm_endpoint_key(service.settings), "[]")


def test_worker_marks_bkm_network_failure_as_retryable(mocker):
    mocker.patch("aidev_bkplugin.services.otel_metrics.requests.post", side_effect=requests.Timeout)
    service = BkPluginMetricService(service_name="ai-demo", endpoints=[], agent_info={}, settings=_bkm_settings())

    with pytest.raises(RetryableMetricPushError, match="transient network error"):
        service.push_bkm(_bkm_endpoint_key(service.settings), "[]")


def test_worker_keeps_non_retryable_bkm_client_error(mocker):
    post = mocker.patch("aidev_bkplugin.services.otel_metrics.requests.post")
    post.return_value.status_code = 400
    post.return_value.raise_for_status.side_effect = requests.HTTPError("bad request")
    service = BkPluginMetricService(service_name="ai-demo", endpoints=[], agent_info={}, settings=_bkm_settings())

    with pytest.raises(requests.HTTPError, match="bad request"):
        service.push_bkm(_bkm_endpoint_key(service.settings), "[]")


def test_metric_service_rejects_unknown_worker_endpoint():
    service = BkPluginMetricService(service_name="ai-demo", endpoints=[], agent_info={}, settings=_bkm_settings())

    with pytest.raises(ValueError, match="Unknown metric endpoint key"):
        service.push_bkm("unknown", "[]")


def test_celery_task_exports_through_process_local_metric_service(mocker):
    tasks = _import_tasks_with_celery_stub(mocker)
    service = mocker.Mock()
    mocker.patch.object(tasks, "get_metric_service", return_value=service)

    tasks.push_bkm_metrics_task("endpoint-fingerprint", "payload")

    service.push_bkm.assert_called_once_with("endpoint-fingerprint", "payload")
    assert tasks.push_bkm_metrics_task.shared_task_options["autoretry_for"] == (RetryableMetricPushError,)
    assert tasks.push_bkm_metrics_task.shared_task_options["max_retries"] == 3
