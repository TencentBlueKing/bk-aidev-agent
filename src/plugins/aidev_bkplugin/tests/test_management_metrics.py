import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PLUGIN_ROOT.parents[1] / "agent"

# Exercise the actual plugin initializer and SDK shutdown without a database,
# collector or broker. A regression delays exit during the final metric export.
EXIT_PROBE = dedent("""
    import sys
    import threading
    from types import SimpleNamespace
    from unittest.mock import patch

    import django
    django.setup()
    from aidev_bkplugin import apps
    from aidev_bkplugin.services.otel_metrics import BkPluginMetricService
    from aidev_agent.packages.opentelemetry.otel_service import BkAgentOTelService
    from aidev_agent.packages.opentelemetry.utils import ExporterType
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult

    class SlowExporter(MetricExporter):
        def export(self, metrics_data, timeout_millis=10000, **kwargs):
            threading.Event().wait(20)
            return MetricExportResult.SUCCESS

        def force_flush(self, timeout_millis=10000):
            return True

        def shutdown(self, timeout_millis=30000, **kwargs):
            pass

    def instrumentor(config):
        # Keep the real SDK provider lifecycle; avoid unrelated agent wrappers.
        return SimpleNamespace(instrument=BkAgentOTelService(config).start)

    via_celery = sys.argv[1] == "celery"
    sys.argv = ["bin/manage.py", sys.argv[2]]
    agent_info = {"otel_info": {"metrics": {
        "enabled": True, "export_via_celery": via_celery,
        "agent_data_id": 1, "agent_access_token": "test-token",
        "agent_push_url": "http://collector.example.com/v2/push/",
    }}}
    endpoint = {"url": "http://collector.example.com", "token": "", "exporter_type": ExporterType.HTTP}
    with (
        patch.object(apps, "get_otel_endpoint_by_json_str", return_value=[endpoint]),
        patch.object(apps, "get_otel_endpoint_by_agent_info", return_value=[]),
        patch.object(apps, "get_otel_endpoint_by_env", return_value=[]),
        patch("aidev_bkplugin.services.agent_config.AgentConfigFetcher.get_info", return_value=agent_info),
        patch.object(apps, "BkAidevAgentInstrumentor", side_effect=instrumentor),
        patch.object(apps, "push_bkm_metrics_task", SimpleNamespace(delay=lambda *args: None)),
        patch.object(BkAgentOTelService, "_create_metric_exporter", side_effect=lambda *args: SlowExporter()),
        patch.object(BkPluginMetricService, "_create_celery_exporter", side_effect=lambda: SlowExporter()),
    ):
        apps.init_bk_aidev_agent_otel()
        metrics.get_meter("exit-probe").create_counter("probe.count").add(1)
        print("command returned", flush=True)
""")


@pytest.mark.parametrize("transport", ["direct", "celery"])
@pytest.mark.parametrize("command", ["migrate", "upgrade_sessions"])
def test_management_initialization_exits_without_final_metric_export(transport, command):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "tests.settings",
        "PYTHONPATH": os.pathsep.join([str(PLUGIN_ROOT), str(AGENT_ROOT)]),
        "BKAI_AGENT_OTEL_ENABLED": "true",
        "BKAI_AGENT_ENABLE_METRICS": "true",
        "BKAI_AGENT_ENABLE_TRACES": "false",
        "BKAI_AGENT_ENABLE_LOGS": "false",
        "BKAI_AGENT_TRACE_EXPORTER": "otlp",
    }
    result = subprocess.run(
        [sys.executable, "-c", EXIT_PROBE, transport, command],
        cwd=PLUGIN_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert "command returned" in result.stdout
