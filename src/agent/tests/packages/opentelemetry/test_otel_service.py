from types import SimpleNamespace

from aidev_agent.packages.opentelemetry.config import OTelConfig
from aidev_agent.packages.opentelemetry.metrics import (
    AGENT_ITERATION_HISTOGRAM_BOUNDARIES,
    DURATION_HISTOGRAM_BOUNDARIES,
    MESSAGE_SIZE_HISTOGRAM_BOUNDARIES,
)
from aidev_agent.packages.opentelemetry.otel_service import BkAgentOTelService


def test_metric_toggle_does_not_change_trace_service_setup(mocker):
    config = OTelConfig(otel_endpoints=[])
    config.enabled = True
    config.enable_traces = True
    config.enable_metrics = True
    config.enable_logs = False
    service = BkAgentOTelService(config)
    setup_traces = mocker.patch.object(service, "_setup_traces")
    setup_metrics = mocker.patch.object(service, "_setup_metrics")

    service.start()

    setup_traces.assert_called_once()
    setup_metrics.assert_called_once()


def test_externally_managed_metric_provider_does_not_duplicate_setup(mocker):
    config = OTelConfig(otel_endpoints=[])
    config.enabled = True
    config.enable_traces = True
    config.enable_metrics = True
    config.enable_logs = False
    config.metric_provider_managed_externally = True
    service = BkAgentOTelService(config)
    setup_traces = mocker.patch.object(service, "_setup_traces")
    setup_metrics = mocker.patch.object(service, "_setup_metrics")

    service.start()

    setup_traces.assert_called_once()
    setup_metrics.assert_not_called()


def test_direct_metric_provider_uses_configured_reader_and_shared_histogram_views(mocker):
    config = OTelConfig(otel_endpoints=[{"url": "http://collector", "exporter_type": SimpleNamespace(value="http")}])
    config.metric_export_interval_millis = 1500
    config.metric_export_timeout_millis = 7000
    service = BkAgentOTelService(config)
    exporter = mocker.Mock()
    mocker.patch.object(service, "_create_metric_exporter", return_value=exporter)
    reader = mocker.patch("aidev_agent.packages.opentelemetry.otel_service.PeriodicExportingMetricReader")
    provider = mocker.patch("aidev_agent.packages.opentelemetry.otel_service.MeterProvider")
    mocker.patch("aidev_agent.packages.opentelemetry.otel_service.metrics.set_meter_provider")

    service._setup_metrics(mocker.Mock())

    reader.assert_called_once_with(exporter, export_interval_millis=1500, export_timeout_millis=7000)
    views = provider.call_args.kwargs["views"]
    assert tuple(views[0]._aggregation._boundaries) == DURATION_HISTOGRAM_BOUNDARIES
    assert tuple(views[1]._aggregation._boundaries) == MESSAGE_SIZE_HISTOGRAM_BOUNDARIES
    assert tuple(views[2]._aggregation._boundaries) == AGENT_ITERATION_HISTOGRAM_BOUNDARIES
