from __future__ import annotations

import importlib.util
from pathlib import Path


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


def test_template_celery_worker_listens_to_plugin_agent_and_metric_queues():
    repo_root = Path(__file__).resolve().parents[4]
    app_desc = repo_root / "template" / "builtin" / "{{cookiecutter.project_name}}" / "app_desc.yml"

    assert "-Q plugin_schedule,bkai_agent_task,bkai_agent_metric" in app_desc.read_text(encoding="utf-8")


def test_builtin_template_can_render_craw_dockerfile_package():
    repo_root = Path(__file__).resolve().parents[4]
    project = repo_root / "template" / "builtin" / "{{cookiecutter.project_name}}"
    dockerfile = (project / "Dockerfile").read_text(encoding="utf-8")
    app_desc = (project / "app_desc.yml").read_text(encoding="utf-8")

    assert "ARG CRAW_BASE_IMAGE\nFROM ${CRAW_BASE_IMAGE}" in dockerfile
    assert (project / "deploy" / "craw-supervisor.sh").is_file()
    assert 'cookiecutter.agent_runtime == "craw"' in app_desc
    assert "craw-supervisor.sh" in app_desc
