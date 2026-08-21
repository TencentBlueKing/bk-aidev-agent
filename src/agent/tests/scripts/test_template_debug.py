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
