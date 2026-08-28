from types import SimpleNamespace

import aidev_agent.packages as aidev_agent_packages
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
    mocker.patch(
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
    return otel_config, instrumentor


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
    otel_config, instrumentor = _mock_otel_inputs(
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
    otel_config, instrumentor = _mock_otel_inputs(
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
    instrumentor.instrument.assert_called_once_with()
