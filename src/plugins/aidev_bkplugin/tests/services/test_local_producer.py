import io
import json
import os
import subprocess
import sys
import tempfile
import time
from unittest.mock import Mock

import pytest
from aidev_agent.utils.tracing import trace_headers
from aidev_bkplugin.management.commands import run_chat_local_producer as command
from aidev_bkplugin.services.producer import local as local_producer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def test_zero_disables_local_producer(monkeypatch):
    monkeypatch.setenv("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", "0")
    assert not local_producer.try_start_local_producer({})


@pytest.mark.skipif(local_producer.fcntl is None, reason="requires flock")
def test_default_five_slots_survive_dispatcher_exit(tmp_path, monkeypatch):
    monkeypatch.delenv("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", raising=False)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(sys.path))
    (tmp_path / "django.py").write_text(
        "import json, pathlib, sys, time\n"
        "pathlib.Path('ready').write_text(json.load(sys.stdin)['task_id'])\n"
        "for attempt in range(200):\n"
        "    if pathlib.Path('release').exists(): break\n"
        "    time.sleep(0.05)\n"
        "pathlib.Path('finished').touch()\n"
    )
    payload = {"task_id": "task", "spec": {"app_code": "app"}}
    launch = (
        "from aidev_bkplugin.services.producer.local import try_start_local_producer\n"
        f"assert try_start_local_producer({payload!r})"
    )
    monkeypatch.chdir(tmp_path)
    try:
        for _ in range(5):
            subprocess.run([sys.executable, "-c", launch], check=True, timeout=10)
        assert not local_producer.try_start_local_producer(payload)
    finally:
        (tmp_path / "release").touch()
    deadline = time.monotonic() + 5
    while not (tmp_path / "finished").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert (tmp_path / "finished").exists()
    assert (tmp_path / "ready").read_text() == "task"


def test_local_command_records_launch_before_worker(monkeypatch):
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(command.trace, "get_tracer", provider.get_tracer)
    with provider.get_tracer("test").start_as_current_span("dispatch") as dispatch:
        payload = {"task_id": "task", "spec": {}, "expires_at": 10, "launch_context": trace_headers()}
    monkeypatch.setattr(command.sys, "stdin", io.StringIO(json.dumps(payload)))
    run = Mock()
    monkeypatch.setattr(command, "run_chat", run)
    launched = time.time_ns() - 1_000_000_000
    command.Command().handle(launch_time_ns=launched)
    run.assert_called_once_with(task_id="task", spec={}, expires_at=10, backend="local")
    _, startup = exporter.get_finished_spans()
    assert startup.name == "bkplugin.chat.local.startup"
    assert startup.parent.span_id == dispatch.get_span_context().span_id
    assert startup.start_time == launched < startup.end_time
    assert startup.attributes["process.pid"] == os.getpid()
    provider.shutdown()
