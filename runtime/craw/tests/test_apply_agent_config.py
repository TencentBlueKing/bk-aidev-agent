import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

sys.modules.setdefault("httpx", ModuleType("httpx"))
django = ModuleType("django")
django_conf = ModuleType("django.conf")
django_conf.settings = SimpleNamespace(configured=True)
sys.modules.setdefault("django", django)
sys.modules.setdefault("django.conf", django_conf)
sync = ModuleType("aidev_agent.packages.craw.sync")
sync.render_soul = lambda config: ""
manager = ModuleType("aidev_agent.packages.resource_manager.agent")
manager.AgentResourceManager = object
sys.modules.setdefault("aidev_agent", ModuleType("aidev_agent"))
sys.modules.setdefault("aidev_agent.packages", ModuleType("aidev_agent.packages"))
sys.modules.setdefault("aidev_agent.packages.craw", ModuleType("aidev_agent.packages.craw"))
sys.modules.setdefault("aidev_agent.packages.craw.sync", sync)
sys.modules.setdefault("aidev_agent.packages.resource_manager", ModuleType("aidev_agent.packages.resource_manager"))
sys.modules.setdefault("aidev_agent.packages.resource_manager.agent", manager)

SCRIPT = Path(__file__).parents[1] / "deploy" / "apply-agent-config.py"
spec = spec_from_file_location("apply_agent_config", SCRIPT)
module = module_from_spec(spec)
spec.loader.exec_module(module)


def test_main_rejects_missing_injected_runtime_settings(monkeypatch):
    monkeypatch.setenv("BKAI_AGENT", "demo-agent")
    monkeypatch.delenv("AIDEV_GATEWAY_NAME", raising=False)
    monkeypatch.delenv("BK_APIGW_STAGE", raising=False)

    assert module.main() == 4


def test_optional_skill_failure_does_not_abort(monkeypatch, tmp_path):
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


def test_openclaw_2026_8_migration_preserves_supported_ui_settings():
    config = {"ui": {"assistant": {"name": "legacy"}, "prefs": {"theme": "claw"}}}

    module._migrate_openclaw_2026_8(config)

    assert config == {"ui": {"prefs": {"theme": "claw"}}}


def test_openclaw_2026_8_migration_removes_empty_ui():
    config = {"ui": {"assistant": {"name": "legacy"}}}

    module._migrate_openclaw_2026_8(config)

    assert "ui" not in config
