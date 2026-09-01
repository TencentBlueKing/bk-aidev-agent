from types import SimpleNamespace

import aidev_agent.packages as aidev_agent_packages
import pytest
from aidev_agent.packages.opentelemetry.utils import ExporterType
from aidev_bkplugin import apps


def test_init_otel_disabled_skips_remote_initialization(mocker):
    otel_config = SimpleNamespace(enabled=False)
    mocker.patch.object(apps, "OTelConfig", return_value=otel_config)
    get_json_endpoints = mocker.patch.object(apps, "get_otel_endpoint_by_json_str")
    get_env_endpoints = mocker.patch.object(apps, "get_otel_endpoint_by_env")
    instrumentor = mocker.patch.object(apps, "BkAidevAgentInstrumentor")
    set_metric_service = mocker.patch.object(apps, "set_metric_service")

    apps.init_bk_aidev_agent_otel()

    get_json_endpoints.assert_not_called()
    get_env_endpoints.assert_not_called()
    instrumentor.assert_not_called()
    set_metric_service.assert_called_once_with(None)


def test_init_otel_logging_export_skips_remote_configuration(mocker):
    otel_config = SimpleNamespace(
        enabled=True,
        trace_exporter="logging",
        enable_metrics=True,
        enable_logs=True,
    )
    mocker.patch.object(apps, "OTelConfig", return_value=otel_config)
    get_json_endpoints = mocker.patch.object(apps, "get_otel_endpoint_by_json_str")
    get_env_endpoints = mocker.patch.object(apps, "get_otel_endpoint_by_env")
    instrumentor = mocker.patch.object(apps, "BkAidevAgentInstrumentor").return_value
    set_metric_service = mocker.patch.object(apps, "set_metric_service")

    apps.init_bk_aidev_agent_otel()

    get_json_endpoints.assert_not_called()
    get_env_endpoints.assert_not_called()
    set_metric_service.assert_called_once_with(None)
    assert otel_config.enable_metrics is False
    assert otel_config.enable_logs is False
    instrumentor.instrument.assert_called_once_with()


def _mock_otel_inputs(mocker, agent_info, metric_settings):
    mocker.patch.object(apps, "get_otel_endpoint_by_json_str", return_value=[])
    mocker.patch.object(apps, "get_otel_endpoint_by_agent_info", return_value=[])
    mocker.patch.object(apps, "get_otel_endpoint_by_env", return_value=[])
    get_agent_info = mocker.patch(
        "aidev_bkplugin.services.agent_config.AgentConfigFetcher.get_info",
        return_value=agent_info,
    )
    otel_config = SimpleNamespace(
        enabled=True,
        enable_metrics=True,
        service_name="agent-service",
        metric_provider_managed_externally=False,
    )
    mocker.patch.object(apps, "OTelConfig", return_value=otel_config)
    metric_export_settings = mocker.patch.object(apps, "MetricExportSettings")
    metric_export_settings.from_agent_info.return_value = metric_settings
    instrumentor = mocker.patch.object(apps, "BkAidevAgentInstrumentor").return_value
    return otel_config, instrumentor, get_agent_info


def test_deduplicate_otel_endpoints_keeps_first_effective_destination():
    preferred = {"url": "https://collector.example/api", "token": "token", "exporter_type": ExporterType.GRPC}
    duplicate = {"url": "https://collector.example/api/", "token": "token", "exporter_type": ExporterType.GRPC}
    different_token = {"url": preferred["url"], "token": "other-token", "exporter_type": ExporterType.GRPC}
    different_protocol = {"url": preferred["url"], "token": "token", "exporter_type": ExporterType.HTTP}

    assert apps._deduplicate_otel_endpoints([preferred, duplicate, different_token, different_protocol]) == [
        preferred,
        different_token,
        different_protocol,
    ]


def test_init_otel_deduplicates_endpoint_sources_before_instrumenting(mocker):
    endpoint = {"url": "https://collector.example/api", "token": "token", "exporter_type": ExporterType.GRPC}
    metric_settings = SimpleNamespace(
        enabled=False,
        export_via_celery=False,
        export_interval_millis=1500,
        export_timeout_millis=7000,
    )
    otel_config, instrumentor, _ = _mock_otel_inputs(mocker, {}, metric_settings)
    apps.get_otel_endpoint_by_json_str.return_value = [endpoint]
    apps.get_otel_endpoint_by_agent_info.return_value = [{**endpoint}]
    apps.get_otel_endpoint_by_env.return_value = [{**endpoint}]
    mocker.patch.object(apps, "configure_metric_identity")
    mocker.patch.object(apps, "set_metric_service")

    apps.init_bk_aidev_agent_otel()

    assert otel_config.otel_endpoints == [endpoint]
    instrumentor.instrument.assert_called_once_with()


@pytest.mark.parametrize(
    "argv",
    [
        ["bin/manage.py", "migrate", "--noinput"],
        ["manage.py", "collectstatic"],
        ["manage.py", "shell", "-c", "pass"],
        ["manage.py", "upgrade_sessions"],
        ["manage.py", "new_management_command"],
        ["manage.py", "--help"],
        ["/usr/bin/django-admin", "check"],
        ["django-admin.py", "migrate"],
    ],
)
@pytest.mark.parametrize("trace_exporter", ["otlp", "logging"])
def test_management_commands_disable_metrics_and_traces_before_remote_config(mocker, monkeypatch, argv, trace_exporter):
    monkeypatch.setattr(apps.sys, "argv", argv)
    config, instrumentor, get_agent_info = _mock_otel_inputs(mocker, {"otel_info": {"enable_metrics": True}}, None)
    config.enable_traces = True
    config.trace_exporter = trace_exporter
    metric_service = mocker.patch.object(apps, "BkPluginMetricService")
    set_metric_service = mocker.patch.object(apps, "set_metric_service")

    apps.init_bk_aidev_agent_otel()

    assert config.enable_metrics is False
    assert config.enable_traces is False
    get_agent_info.assert_not_called()
    apps.get_otel_endpoint_by_json_str.assert_not_called()
    apps.get_otel_endpoint_by_env.assert_not_called()
    apps.MetricExportSettings.from_agent_info.assert_not_called()
    metric_service.assert_not_called()
    set_metric_service.assert_called_once_with(None)
    instrumentor.instrument.assert_called_once_with()


@pytest.mark.parametrize(
    "argv",
    [
        ["bin/manage.py", "runserver", "--noreload"],
        ["manage.py", "celery", "worker", "-B"],
        ["manage.py", "celery", "beat", "-l", "info"],
        ["manage.py", "celery", "-A", "test_app", "worker"],
        ["manage.py", "run_wxaibot_ws"],
        ["gunicorn", "wsgi:application"],
        ["celery", "-A", "test_app", "worker"],
    ],
)
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("via_celery", [False, True])
def test_service_entries_preserve_metric_configuration(mocker, monkeypatch, argv, enabled, via_celery):
    monkeypatch.setattr(apps.sys, "argv", argv)
    metric_settings = SimpleNamespace(
        enabled=enabled, export_via_celery=via_celery, export_interval_millis=1500, export_timeout_millis=7000
    )
    config, instrumentor, _ = _mock_otel_inputs(mocker, {}, metric_settings)
    config.enable_traces = not enabled
    metric_service = mocker.patch.object(apps, "BkPluginMetricService")
    metric_service.return_value.start.return_value = enabled
    mocker.patch.object(apps, "configure_metric_identity")
    mocker.patch.object(apps, "set_metric_service")

    apps.init_bk_aidev_agent_otel()

    assert config.enable_metrics is enabled
    assert config.enable_traces is (not enabled)
    assert config.metric_provider_managed_externally is (enabled and via_celery)
    assert metric_service.called is via_celery
    apps.MetricExportSettings.from_agent_info.assert_called_once()
    instrumentor.instrument.assert_called_once_with()


def test_init_otel_keeps_direct_metric_export_in_agent_sdk(mocker, monkeypatch):
    # Some installations expose the optional OTel modules only through their
    # fully qualified imports, not as an attribute on ``aidev_agent.packages``.
    monkeypatch.delattr(aidev_agent_packages, "opentelemetry", raising=False)
    settings = SimpleNamespace(
        enabled=True,
        export_via_celery=False,
        export_interval_millis=1500,
        export_timeout_millis=7000,
    )
    otel_config, instrumentor, _ = _mock_otel_inputs(
        mocker,
        {"code": "legacy-code", "name": "legacy-name"},
        settings,
    )
    metric_service = mocker.patch.object(apps, "BkPluginMetricService")
    set_metric_service = mocker.patch.object(apps, "set_metric_service")
    configure_identity = mocker.patch.object(apps, "configure_metric_identity")

    apps.init_bk_aidev_agent_otel()

    metric_service.assert_not_called()
    set_metric_service.assert_called_once_with(None)
    configure_identity.assert_called_once_with("agent-service", None, None)
    assert otel_config.enable_metrics is True
    assert otel_config.metric_provider_managed_externally is False
    assert otel_config.metric_export_interval_millis == 1500
    assert otel_config.metric_export_timeout_millis == 7000
    instrumentor.instrument.assert_called_once_with()


def test_init_otel_uses_bkplugin_metric_provider_for_celery_export(mocker):
    settings = SimpleNamespace(
        enabled=True,
        export_via_celery=True,
        export_interval_millis=1500,
        export_timeout_millis=7000,
    )
    otel_config, instrumentor, _ = _mock_otel_inputs(
        mocker,
        {
            "agent_code": "ai-demo",
            "agent_name": "Demo Agent",
            "agent_sdk_version": "2.2.3",
        },
        settings,
    )
    metric_service = mocker.patch.object(apps, "BkPluginMetricService").return_value
    metric_service.start.return_value = True
    set_metric_service = mocker.patch.object(apps, "set_metric_service")
    configure_identity = mocker.patch.object(apps, "configure_metric_identity")

    apps.init_bk_aidev_agent_otel()

    set_metric_service.assert_called_once_with(metric_service)
    configure_identity.assert_called_once_with("ai-demo", "Demo Agent", "2.2.3")
    assert otel_config.enable_metrics is True
    assert otel_config.metric_provider_managed_externally is True
    assert apps.BkPluginMetricService.call_args.kwargs["enqueue_bkm_metrics"] is apps.enqueue_bkm_metrics_task
    instrumentor.instrument.assert_called_once_with()
