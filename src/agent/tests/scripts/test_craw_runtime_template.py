import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SCRIPT = (
    Path(__file__).parents[4]
    / "template"
    / "builtin"
    / "{{cookiecutter.project_name}}"
    / "deploy"
    / "apply-agent-config.py"
)

@pytest.fixture
def module(monkeypatch):
    django = ModuleType("django")
    django_conf = ModuleType("django.conf")
    django_conf.settings = SimpleNamespace(configured=True)
    monkeypatch.setitem(sys.modules, "django", django)
    monkeypatch.setitem(sys.modules, "django.conf", django_conf)

    spec = spec_from_file_location("apply_agent_config", SCRIPT)
    loaded = module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_main_rejects_missing_injected_runtime_settings(module, monkeypatch):
    monkeypatch.setenv("BKAI_AGENT", "demo-agent")
    monkeypatch.delenv("AIDEV_GATEWAY_NAME", raising=False)
    monkeypatch.delenv("BK_APIGW_STAGE", raising=False)

    assert module.main() == 4


def test_optional_skill_failure_does_not_abort(module, monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise ValueError("bad archive")

    monkeypatch.setattr(module, "_install_skill", fail)
    status_path = tmp_path / "status.json"

    assert module.materialize_skills(object(), [{"id": "1", "skill_code": "demo"}], tmp_path, status_path) == []
    status = json.loads(status_path.read_text())
    assert status["skills_root"] == str(tmp_path)
    assert status["related_count"] == 1
    assert status["installed"] == []
    assert status["failures"] == [{"skill": "demo", "error": "ValueError"}]


def test_openclaw_2026_8_migration_preserves_supported_ui_settings(module):
    config = {"ui": {"assistant": {"name": "legacy"}, "prefs": {"theme": "claw"}}}

    module._migrate_openclaw_2026_8(config)

    assert config == {"ui": {"prefs": {"theme": "claw"}}}


def test_openclaw_2026_8_migration_removes_empty_ui(module):
    config = {"ui": {"assistant": {"name": "legacy"}}}

    module._migrate_openclaw_2026_8(config)

    assert "ui" not in config
