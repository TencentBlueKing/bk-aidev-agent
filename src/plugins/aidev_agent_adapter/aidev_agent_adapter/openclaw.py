"""Run inside one user's sandbox. Read the prompt from stdin, emit AG-UI envelopes."""

import argparse
import asyncio
import json
import logging
import os
import secrets
import shutil
import sys
import tempfile
import uuid
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from dataclasses import replace
from pathlib import Path

import httpx
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .adapter import Adapter
from .cli import load_settings
from .config_sync import ConfigSynchronizer, Snapshot, private_directory, write_private
from .models import Settings
from .platform import PlatformClient
from .runner import serve_runner

logger = logging.getLogger(__name__)
OTEL_PLUGIN_DIR = Path("/app/otel/node_modules/@openclaw/diagnostics-otel")
GATEWAY_PORT = 18789
GATEWAY_READY_TIMEOUT = 100


def install_user_config(settings: Settings, snapshot: Snapshot, user_root: Path) -> Snapshot:
    # Persist configuration separately from SQLite. Credentials are resolved per sandbox start.
    user_root = private_directory(user_root)
    config = json.loads((snapshot.path / "openclaw.json").read_text(encoding="utf-8"))
    for index, server in enumerate(config.get("mcp", {}).get("servers", {}).values()):
        for position, (key, value) in enumerate(server.get("headers", {}).items()):
            variable = f"AIDEV_MCP_{index}_HEADER_{position}"
            settings.engine_env[variable] = value
            server["headers"][key] = "${" + variable + "}"
    target = user_root / "openclaw.json"
    stage = Path(tempfile.mkstemp(dir=user_root, prefix=".openclaw-")[1])
    try:
        os.chmod(stage, 0o600)
        with stage.open("w", encoding="utf-8") as tmp:
            json.dump(config, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(stage, target)
    finally:
        stage.unlink(missing_ok=True)
    return replace(snapshot, engine_config=target)


async def wait_for_gateway(gateway: asyncio.subprocess.Process) -> None:
    # Leave time for Runner registration within Channel's 150-second startup window.
    last_status = "not probed"
    async with httpx.AsyncClient(trust_env=False, timeout=2) as client:
        try:
            async with asyncio.timeout(GATEWAY_READY_TIMEOUT):
                while gateway.returncode is None:
                    try:
                        response = await client.get(f"http://127.0.0.1:{GATEWAY_PORT}/readyz")
                        if response.status_code == 200:
                            return
                        last_status = f"HTTP {response.status_code}"
                    except httpx.RequestError as exc:
                        last_status = type(exc).__name__
                    await asyncio.sleep(1)
                raise RuntimeError(f"OpenClaw Gateway exited with status {gateway.returncode}")
        except TimeoutError as exc:
            raise RuntimeError(f"OpenClaw Gateway readiness timed out; last probe: {last_status}") from exc


async def run_runner_with_gateway(gateway: asyncio.subprocess.Process, runner_coro) -> None:
    """联动监控 Gateway 与 Runner；Gateway 异常退出时立即中止 Runner，避免僵尸心跳。"""
    runner_task = asyncio.create_task(runner_coro)
    gateway_task = asyncio.create_task(gateway.wait())
    try:
        done, pending = await asyncio.wait({runner_task, gateway_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if gateway_task in done and runner_task not in done:
            raise RuntimeError(f"OpenClaw Gateway exited unexpectedly with status {gateway_task.result()}")
        runner_task.result()
    finally:
        for task in (runner_task, gateway_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(runner_task, gateway_task, return_exceptions=True)


def configure_otel(settings: Settings, endpoint: str) -> tuple[TracerProvider, MeterProvider]:
    resource = Resource.create({"service.name": "aidev-agent-adapter"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=5000)],
    )
    metrics.set_meter_provider(meter_provider)
    if not OTEL_PLUGIN_DIR.is_dir():
        logger.warning(
            "OpenClaw diagnostics-otel plugin directory not found (%s); skipping engine OTLP plugin",
            OTEL_PLUGIN_DIR,
        )
        return provider, meter_provider
    plugins = settings.native_config.setdefault("plugins", {})
    allowed = plugins.setdefault("allow", ["openai"])
    if "diagnostics-otel" not in allowed:
        allowed.append("diagnostics-otel")
    plugins.setdefault("entries", {})["diagnostics-otel"] = {"enabled": True}
    load_paths = plugins.setdefault("load", {}).setdefault("paths", [])
    plugin_str = str(OTEL_PLUGIN_DIR)
    if plugin_str not in load_paths:
        load_paths.append(plugin_str)
    settings.native_config["diagnostics"] = {
        "enabled": True,
        "otel": {
            "enabled": True,
            "traces": True,
            "metrics": True,
            "logs": False,
            "captureContent": False,
            "serviceName": "openclaw-gateway",
        },
    }
    settings.engine_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
    return provider, meter_provider


@contextmanager
def _open_private_log(path: Path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        yield stream


@asynccontextmanager
async def _managed_gateway(binary: str, env: dict[str, str], stderr_stream):
    gateway = await asyncio.create_subprocess_exec(
        binary,
        "gateway",
        "run",
        "--bind",
        "loopback",
        "--port",
        str(GATEWAY_PORT),
        "--auth",
        "token",
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=stderr_stream,
    )
    try:
        yield gateway
    finally:
        if gateway.returncode is None:
            gateway.terminate()
            try:
                await asyncio.wait_for(gateway.wait(), 10)
            except TimeoutError:
                gateway.kill()
                await gateway.wait()


async def run(config: Path, prompt: str | None) -> None:
    if sys.platform != "linux" or Path.cwd().resolve() not in {Path("/opt/adapter"), Path("/app/workspace")}:
        raise RuntimeError("use the OpenClaw sandbox image entrypoint")
    settings = load_settings(config)
    if settings.engine != "openclaw" or (prompt is not None and not prompt.strip()):
        raise ValueError("expected an OpenClaw profile and a nonempty prompt")
    binary = shutil.which("openclaw")
    if not binary:
        raise RuntimeError("install openclaw in the sandbox first")
    settings.native_config["gateway"] = {"mode": "local", "bind": "loopback", "port": GATEWAY_PORT}

    otel_providers = None
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        otel_providers = configure_otel(settings, endpoint)

    client = PlatformClient(settings)
    if prompt is None and "AIDEV_PREVIEW_CONFIG" in os.environ:
        client.preview_config = json.loads(os.environ.pop("AIDEV_PREVIEW_CONFIG"))
    try:
        snapshot = await ConfigSynchronizer(settings, client).sync()
    finally:
        await client.close()
    if prompt is None:
        os.environ.pop("AIDEV_ACCESS_TOKEN", None)

    if settings.mounted_storage:
        snapshot = install_user_config(settings, snapshot, Path("/app/.storage/user"))

    # Both processes share the same user-private state, token and immutable config.
    settings.engine_env.update(
        {
            "PATH": os.environ["PATH"],
            "HOME": str(private_directory(settings.root / "engine-home")),
            "OPENCLAW_STATE_DIR": str(
                private_directory(
                    Path("/app/.storage/user/state") if settings.mounted_storage else settings.root / "openclaw-state"
                )
            ),
            "OPENCLAW_GATEWAY_TOKEN": secrets.token_urlsafe(32),
        }
    )
    for name in (
        "OPENCLAW_MODEL_KEY",
        "OPENCLAW_APP_AUTH",
        "NODE_EXTRA_CA_CERTS",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
    ):
        if name in os.environ:
            settings.engine_env[name] = os.environ[name]
    env = {**settings.engine_env, **snapshot.environment}
    settings.command = [binary, "acp"]

    async with AsyncExitStack() as stack:
        if otel_providers is not None:
            tracer_provider, meter_provider = otel_providers
            stack.callback(tracer_provider.shutdown)
            stack.callback(meter_provider.shutdown)
        adapter = await stack.enter_async_context(Adapter(settings, snapshot))
        gateway_log = stack.enter_context(
            _open_private_log(private_directory(settings.root / "logs") / "gateway.stderr.log")
        )
        gateway = await stack.enter_async_context(_managed_gateway(binary, env, gateway_log))
        await wait_for_gateway(gateway)
        if prompt is None:
            await run_runner_with_gateway(
                gateway,
                serve_runner(
                    adapter,
                    os.environ["CHANNEL_RUNNER_URL"],
                    Path(os.environ["CHANNEL_RUNNER_TICKET_FILE"]),
                    os.environ["SANDBOX_ID"],
                ),
            )
            return
        run_id = uuid.uuid4().hex
        await adapter.submit(run_id, uuid.uuid4().hex, prompt)
        async for item in adapter.events(run_id):
            print(json.dumps(item["event"], ensure_ascii=False), flush=True)
            if item["event"]["type"] == "RUN_ERROR":
                raise RuntimeError("OpenClaw run failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--runner", action="store_true")
    args = parser.parse_args()
    try:
        if args.config:
            asyncio.run(run(args.config, None if args.runner else sys.stdin.read()))
        elif args.runner:
            # PaaS supplies bootstrap data as environment variables. Keep credentials off the user PV.
            with tempfile.TemporaryDirectory(prefix="aidev-bootstrap-") as directory:
                profile = Path(directory) / "profile.json"
                write_private(profile, os.environ.pop("AIDEV_ADAPTER_CONFIG"))
                ticket = Path(directory) / "runner.ticket"
                write_private(ticket, os.environ.pop("CHANNEL_RUNNER_TICKET"))
                os.environ["CHANNEL_RUNNER_TICKET_FILE"] = str(ticket)
                asyncio.run(run(profile, None))
        else:
            parser.error("--config is required for a single prompt")
    except Exception as exc:
        logger.error("OpenClaw adapter exited with error: %s", type(exc).__name__)
        raise SystemExit(1) from None
