from aidev_agent.packages.opentelemetry.config import OTelConfig
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
