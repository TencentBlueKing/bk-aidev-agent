import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

TEMPLATE_DEPLOY = Path(__file__).parents[4] / "template" / "builtin" / "{{cookiecutter.project_name}}" / "deploy"
SCRIPT = TEMPLATE_DEPLOY / "apply-agent-config.py"
SUPERVISOR = TEMPLATE_DEPLOY / "craw-supervisor.sh"


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


def test_supervisor_uses_one_config_path_and_fails_closed_on_rewrite():
    script = SUPERVISOR.read_text(encoding="utf-8")

    assert 'OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.openclaw}"' in script
    assert 'OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-${OPENCLAW_STATE_DIR}/openclaw.json}"' in script
    assert '--port "${BKAI_MCP_EGRESS_PORT}" --config "" &' in script
    assert 'if [ ! -f "${OPENCLAW_CONFIG_PATH}" ]; then' in script
    assert "FATAL: MCP egress rewrite failed" in script
    assert "WARN: MCP egress rewrite failed" not in script


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
