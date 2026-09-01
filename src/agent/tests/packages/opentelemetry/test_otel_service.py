import logging
from types import SimpleNamespace

import pytest
from aidev_agent.packages.opentelemetry.config import (
    DEFAULT_MAX_ATTRIBUTE_LENGTH,
    DEFAULT_MAX_INPUT_ATTRIBUTE_LENGTH,
    DEFAULT_MAX_OUTPUT_ATTRIBUTE_LENGTH,
    OTelConfig,
)
from aidev_agent.packages.opentelemetry.metrics import (
    AGENT_ITERATION_HISTOGRAM_BOUNDARIES,
    DURATION_HISTOGRAM_BOUNDARIES,
    MESSAGE_SIZE_HISTOGRAM_BOUNDARIES,
)
from aidev_agent.packages.opentelemetry.otel_service import BkAgentOTelService
from opentelemetry.sdk.resources import Resource


def test_otel_config_uses_central_metric_toggle(monkeypatch):
    monkeypatch.setattr("aidev_agent.packages.opentelemetry.config.agent_settings.BKAI_AGENT_ENABLE_METRICS", True)

    assert OTelConfig(otel_endpoints=[]).enable_metrics is True


def test_otel_config_uses_central_attribute_limits_by_default():
    config = OTelConfig(otel_endpoints=[])

    assert DEFAULT_MAX_ATTRIBUTE_LENGTH == config.max_attribute_length == 10000
    assert DEFAULT_MAX_INPUT_ATTRIBUTE_LENGTH == config.max_input_attribute_length == 80 * 1024
    assert DEFAULT_MAX_OUTPUT_ATTRIBUTE_LENGTH == config.max_output_attribute_length == 20 * 1024
    assert config.span_attribute_length_limit == DEFAULT_MAX_INPUT_ATTRIBUTE_LENGTH


def test_otel_config_uses_independent_central_attribute_limits(monkeypatch):
    monkeypatch.setattr("aidev_agent.packages.opentelemetry.config.agent_settings.BKAI_AGENT_MAX_ATTRIBUTE_LENGTH", 123)
    monkeypatch.setattr(
        "aidev_agent.packages.opentelemetry.config.agent_settings.BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH", 456
    )
    monkeypatch.setattr(
        "aidev_agent.packages.opentelemetry.config.agent_settings.BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH", 234
    )

    config = OTelConfig(otel_endpoints=[])

    assert config.max_attribute_length == 123
    assert config.max_input_attribute_length == 456
    assert config.max_output_attribute_length == 234
    assert config.span_attribute_length_limit == 456


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


def test_logging_trace_exporter_writes_span_without_remote_export(mocker, caplog):
    config = OTelConfig(otel_endpoints=[])
    config.trace_exporter = "logging"
    service = BkAgentOTelService(config)
    create_remote_exporter = mocker.patch.object(service, "_create_trace_exporter")

    with caplog.at_level(logging.INFO, logger="aidev_agent.packages.opentelemetry.otel_service"):
        service._setup_traces(Resource.create({}))
        tracer = service.get_tracer(__name__)
        with tracer.start_as_current_span("local-evaluation"):
            pass

    create_remote_exporter.assert_not_called()
    assert "event=aidev_otel_span" in caplog.text
    assert "name=local-evaluation" in caplog.text
    service.tracer_provider.shutdown()


@pytest.mark.parametrize(
    "attribute_name",
    [
        "agent.session.input",
        "gen_ai.request.tools",
        "llm.input",
        "llm.output",
        "tool.input",
        "tool.output",
    ],
)
def test_trace_provider_bounds_all_span_and_event_attributes(attribute_name):
    config = OTelConfig(otel_endpoints=[])
    config.max_attribute_length = 16
    config.max_input_attribute_length = 16
    config.max_output_attribute_length = 16
    service = BkAgentOTelService(config)

    service._setup_traces(Resource.create({}))
    span = service.get_tracer(__name__).start_span("bounded-attributes")
    span.set_attribute(attribute_name, "x" * 100)
    span.add_event("failure", {"exception.stacktrace": "y" * 100})
    span.end()

    assert span.attributes[attribute_name] == "x" * 16
    assert span.events[0].attributes["exception.stacktrace"] == "y" * 16
    service.tracer_provider.shutdown()
