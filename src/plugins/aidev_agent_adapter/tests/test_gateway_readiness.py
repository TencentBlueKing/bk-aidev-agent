import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from aidev_agent_adapter.services.openclaw import run_runner_with_gateway, wait_for_gateway
from aidev_agent_adapter.telemetry import otel
from aidev_agent_adapter.telemetry.otel import configure_otel


async def test_register_only_after_gateway_is_ready(monkeypatch):
    responses = iter([503, 200])
    probes = []

    async def get(client, url):
        probes.append(url)
        return httpx.Response(next(responses))

    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    await wait_for_gateway(SimpleNamespace(returncode=None))
    assert probes == ["http://127.0.0.1:18789/readyz"] * 2


async def test_gateway_exit_is_reported_before_registration():
    with pytest.raises(RuntimeError, match="status 7"):
        await wait_for_gateway(SimpleNamespace(returncode=7))


async def test_run_runner_with_gateway_aborts_when_gateway_exits():
    cancelled = False

    async def fake_runner():
        nonlocal cancelled
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled = True
            raise

    class _DyingGateway:
        async def wait(self):
            await asyncio.sleep(0.02)
            return 137

    with pytest.raises(RuntimeError, match="status 137"):
        await run_runner_with_gateway(_DyingGateway(), fake_runner())
    assert cancelled is True


def test_configure_otel_skips_missing_plugin_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(otel, "OTEL_PLUGIN_DIR", Path(tmp_path / "missing-plugin"))
    monkeypatch.setattr(otel.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(otel.metrics, "set_meter_provider", lambda provider: None)
    settings = SimpleNamespace(native_config={}, engine_env={})
    tracer_provider, meter_provider = configure_otel(settings, "http://127.0.0.1:4318")
    tracer_provider.shutdown()
    meter_provider.shutdown()
    assert "diagnostics" not in settings.native_config
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in settings.engine_env
