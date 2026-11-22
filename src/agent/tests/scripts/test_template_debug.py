from __future__ import annotations

import base64
import importlib.util
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


def load_template_debug_module():
    repo_root = Path(__file__).resolve().parents[4]
    script_path = repo_root / "scripts" / "template_debug.py"
    spec = importlib.util.spec_from_file_location("template_debug", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load script module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builtin_template_is_cookiecutter_root():
    repo_root = Path(__file__).resolve().parents[4]
    template_root = repo_root / "template" / "builtin"

    assert (template_root / "cookiecutter.json").is_file()
    assert (template_root / "hooks" / "post_gen_project.py").is_file()
    assert (template_root / "{{cookiecutter.project_name}}").is_dir()


def test_template_debug_targets_builtin_project():
    module = load_template_debug_module()

    assert module.TEMPLATE_PROJECT == (
        module.REPOSITORY_ROOT / "template" / "builtin" / "{{cookiecutter.project_name}}"
    )


@pytest.mark.parametrize("concurrency, expected", [(None, "16"), ("8", "8")])
def test_template_celery_worker_listens_to_plugin_agent_and_metric_queues(tmp_path, concurrency, expected):
    repo_root = Path(__file__).resolve().parents[4]
    project = repo_root / "template" / "builtin" / "{{cookiecutter.project_name}}"
    assert "procCommand: /bin/bash bin/start_celery.sh" in (project / "app_desc.yml").read_text()
    celery = tmp_path / "celery"
    celery.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
    celery.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}")
    env.pop("BKAI_CELERY_CONCURRENCY", None)
    if concurrency is not None:
        env["BKAI_CELERY_CONCURRENCY"] = concurrency
    args = subprocess.check_output(["bash", str(project / "bin/start_celery.sh")], env=env, text=True).splitlines()
    assert args[args.index("-Q") + 1] == "plugin_schedule,bkai_agent_task,bkai_agent_metric"
    assert args[args.index("-c") + 1] == expected


@pytest.fixture
def load_plugin_settings(monkeypatch):
    project = Path(__file__).resolve().parents[4] / "template/builtin/{{cookiecutter.project_name}}"
    monkeypatch.setenv("BKPAAS_ENVIRONMENT", "dev")
    monkeypatch.setitem(sys.modules, "pymysql", Mock())
    module = "bk_plugin_runtime.config.dev"
    monkeypatch.setitem(sys.modules, module, ModuleType(module))
    return lambda: runpy.run_path(str(project / "bk_plugin/patch/plugin.py"))


@pytest.mark.parametrize("scheme", ["redis", "rediss", "unix"])
@pytest.mark.parametrize("encoded", [True, False])
def test_session_queue_url(load_plugin_settings, monkeypatch, scheme, encoded):
    url = f"{scheme}:///tmp/测试" if scheme == "unix" else f"{scheme}://queue.example.invalid:6379/1"
    value = base64.b64encode(url.encode()).decode() if encoded else url
    monkeypatch.setenv("MESSAGE_REDIS_URL", value)
    monkeypatch.setenv("MESSAGE_HANDLER_TYPE", "auto")
    load_plugin_settings()
    assert os.environ["MESSAGE_REDIS_URL"] == url


@pytest.mark.parametrize("value", ["not_base64!", "/w==", base64.b64encode(b"https://example.invalid").decode()])
def test_invalid_session_queue_url(load_plugin_settings, monkeypatch, value):
    monkeypatch.setenv("MESSAGE_REDIS_URL", value)
    monkeypatch.setenv("MESSAGE_HANDLER_TYPE", "redis")
    with pytest.raises(ValueError, match="MESSAGE_REDIS_URL") as exc:
        load_plugin_settings()
    assert value not in str(exc.value)
    monkeypatch.setenv("MESSAGE_HANDLER_TYPE", "rabbitmq")
    load_plugin_settings()
    assert os.environ["MESSAGE_REDIS_URL"] == value
