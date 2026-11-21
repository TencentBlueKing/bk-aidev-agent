import os
import subprocess
import sys
import tempfile
import time

import pytest
from aidev_bkplugin.services import local_producer


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", raising=False)
    assert not local_producer.try_start_local_producer({})


@pytest.mark.skipif(local_producer.fcntl is None, reason="requires flock")
def test_slot_survives_dispatcher_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("BKAI_CHAT_LOCAL_PRODUCER_LIMIT", "1")
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
        "from aidev_bkplugin.services.local_producer import try_start_local_producer\n"
        f"assert try_start_local_producer({payload!r})"
    )
    monkeypatch.chdir(tmp_path)
    subprocess.run([sys.executable, "-c", launch], check=True, timeout=10)
    try:
        assert not local_producer.try_start_local_producer(payload)
    finally:
        (tmp_path / "release").touch()
    deadline = time.monotonic() + 5
    while not (tmp_path / "finished").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert (tmp_path / "finished").exists()
    assert (tmp_path / "ready").read_text() == "task"
