from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

# (relative_path, pattern, component_key for version)
VERSION_RULES: list[tuple[str, str, str]] = [
    ("src/agent/pyproject.toml", r'^version = "[^"]*"$', "agent"),
    ("src/plugins/aidev_bkplugin/pyproject.toml", r'^version = "[^"]*"$', "bkplugin"),
    (
        "src/plugins/aidev_bkplugin/pyproject.toml",
        r'"aidev-agent>=[^"]*"',
        "agent",
    ),
    ("src/plugins/aidev_wxbot/pyproject.toml", r'^version = "[^"]*"$', "wxbot"),
    (
        "src/plugins/aidev_wxbot/pyproject.toml",
        r'"aidev-bkplugin>=[^"]*"',
        "bkplugin",
    ),
    ("src/plugins/aidev_wxbot/aidev_wxbot/__init__.py", r'^__version__ = "[^"]*"$', "wxbot"),
    ("src/plugins/aidev_ai_blueking/pyproject.toml", r'^version = "[^"]*"$', "ai_blueking"),
    (
        "src/plugins/aidev_ai_blueking/pyproject.toml",
        r'"aidev-agent>=[^"]*"',
        "agent",
    ),
    ("template/{{cookiecutter.project_name}}/pyproject.toml", r'^version = "[^"]*"$', "template"),
    (
        "template/{{cookiecutter.project_name}}/pyproject.toml",
        r'"aidev-agent==[^"]*"',
        "agent",
    ),
    (
        "template/{{cookiecutter.project_name}}/pyproject.toml",
        r'"aidev-bkplugin==[^"]*"',
        "bkplugin",
    ),
    (
        "template/{{cookiecutter.project_name}}/pyproject.toml",
        r'"aidev-wxbot==[^"]*"',
        "wxbot",
    ),
    (
        "template/{{cookiecutter.project_name}}/pyproject.toml",
        r'"aidev-ai-blueking==[^"]*"',
        "ai_blueking",
    ),
    (
        "template/{{cookiecutter.project_name}}/requirements.txt",
        r'^"?aidev-agent==.*"?$',
        "agent",
    ),
    (
        "template/{{cookiecutter.project_name}}/requirements.txt",
        r'^"?aidev-ai-blueking==.*"?$',
        "ai_blueking",
    ),
    (
        "template/{{cookiecutter.project_name}}/requirements.txt",
        r'^"?aidev-bkplugin==.*"?$',
        "bkplugin",
    ),
    (
        "template/{{cookiecutter.project_name}}/requirements.txt",
        r'^"?aidev-wxbot==.*"?$',
        "wxbot",
    ),
    (
        "template/{{cookiecutter.project_name}}/VERSION",
        r"^.+$",
        "template",
    ),
]

SOURCE_PACKAGE_VERSION_FILES: dict[str, str] = {
    "agent": "src/agent/pyproject.toml",
    "bkplugin": "src/plugins/aidev_bkplugin/pyproject.toml",
    "wxbot": "src/plugins/aidev_wxbot/pyproject.toml",
    "ai_blueking": "src/plugins/aidev_ai_blueking/pyproject.toml",
}

TEMPLATE_VERSION_TARGETS = {
    Path("template/{{cookiecutter.project_name}}/pyproject.toml"),
    Path("template/{{cookiecutter.project_name}}/requirements.txt"),
}

# `make release_versions VERSION=...` 统一版本时不会触达的组件；
# 这些组件需通过 per-component 参数（如 `aidev_ai_blueking_version=...`）单独发布。
EXCLUDED_FROM_BULK_UPDATE: set[str] = {"ai_blueking"}


def replacement_for(pattern: str, version: str) -> str:
    if pattern == r"^.+$":
        return version
    if "version =" in pattern or "__version__" in pattern:
        return f'version = "{version}"' if "version =" in pattern else f'__version__ = "{version}"'
    if "aidev-agent>=" in pattern:
        return f'"aidev-agent>={version}"'
    if "aidev-bkplugin>=" in pattern:
        return f'"aidev-bkplugin>={version}"'
    if pattern.startswith(("^aidev-agent==", '^"?aidev-agent==')):
        return f"aidev-agent=={version}"
    if pattern.startswith(("^aidev-ai-blueking==", '^"?aidev-ai-blueking==')):
        return f"aidev-ai-blueking=={version}"
    if pattern.startswith(("^aidev-bkplugin==", '^"?aidev-bkplugin==')):
        return f"aidev-bkplugin=={version}"
    if pattern.startswith(("^aidev-wxbot==", '^"?aidev-wxbot==')):
        return f"aidev-wxbot=={version}"
    if "aidev-agent==" in pattern:
        return f'"aidev-agent=={version}"'
    if "aidev-bkplugin==" in pattern:
        return f'"aidev-bkplugin=={version}"'
    if "aidev-wxbot==" in pattern:
        return f'"aidev-wxbot=={version}"'
    if "aidev-ai-blueking==" in pattern:
        return f'"aidev-ai-blueking=={version}"'
    raise ValueError(f"Cannot build replacement for pattern {pattern!r}")


def replace_required(text: str, pattern: str, replacement: str, path: Path) -> str:
    updated_text, replacements = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if replacements == 0:
        raise ValueError(f"No matches found for pattern {pattern!r} in {path}")
    return updated_text


def normalize_versions(versions: str | dict[str, str]) -> dict[str, str]:
    if isinstance(versions, str):
        components = {component for _, _, component in VERSION_RULES}
        return {component: versions for component in components if component not in EXCLUDED_FROM_BULK_UPDATE}
    return {component: version for component, version in versions.items() if version}


def build_file_rules(
    repo_root: Path,
    versions: str | dict[str, str],
    allowed_paths: set[Path] | None = None,
) -> dict[Path, list[tuple[str, str]]]:
    resolved_versions = normalize_versions(versions)
    file_rules: dict[Path, list[tuple[str, str]]] = {}
    for relative_path, pattern, component in VERSION_RULES:
        if component not in resolved_versions:
            continue
        resolved_path = repo_root / relative_path
        if allowed_paths is not None and resolved_path not in allowed_paths:
            continue
        version = resolved_versions[component]
        replacement = replacement_for(pattern, version)
        file_rules.setdefault(resolved_path, []).append((pattern, replacement))
    return file_rules


def apply_file_rules(repo_root: Path, file_rules: dict[Path, list[tuple[str, str]]]) -> list[Path]:
    updated_files: list[Path] = []
    for path, rules in file_rules.items():
        text = path.read_text(encoding="utf-8")
        for pattern, replacement in rules:
            text = replace_required(text, pattern, replacement, path.relative_to(repo_root))
        path.write_text(text, encoding="utf-8")
        updated_files.append(path.relative_to(repo_root))
    return updated_files


def update_repo_versions(repo_root: Path, versions: str | dict[str, str]) -> list[Path]:
    file_rules = build_file_rules(repo_root, versions)
    return apply_file_rules(repo_root, file_rules)


def read_project_version(pyproject_path: Path) -> str:
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = pyproject.get("project", {}).get("version")
    if not version:
        raise ValueError(f"No [project].version found in {pyproject_path}")
    return version


def get_repo_sdk_versions(repo_root: Path) -> dict[str, str]:
    return {
        component: read_project_version(repo_root / relative_path)
        for component, relative_path in SOURCE_PACKAGE_VERSION_FILES.items()
    }


def sync_template_sdk_versions(repo_root: Path) -> tuple[dict[str, str], list[Path]]:
    versions = get_repo_sdk_versions(repo_root)
    file_rules = build_file_rules(
        repo_root, versions, allowed_paths={repo_root / path for path in TEMPLATE_VERSION_TARGETS}
    )
    updated_files = apply_file_rules(repo_root, file_rules)
    return versions, updated_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update repository package versions. Pass a single VERSION to set all components, or pass per-component versions."
    )
    parser.add_argument(
        "version",
        nargs="?",
        default=None,
        help="Single version for all components (e.g. 2.0.0b1). Omit when using per-component options.",
    )
    parser.add_argument("--aidev-agent-version", dest="aidev_agent_version", help="aidev-agent version")
    parser.add_argument("--aidev-bkplugin-version", dest="aidev_bkplugin_version", help="aidev-bkplugin version")
    parser.add_argument("--aidev-wxbot-version", dest="aidev_wxbot_version", help="aidev-wxbot version")
    parser.add_argument(
        "--aidev-ai-blueking-version",
        dest="aidev_ai_blueking_version",
        default=None,
        help="aidev-ai-blueking version (defaults to aidev-agent version if not set)",
    )
    parser.add_argument("--aidev-template-version", dest="aidev_template_version", help="Template project version")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root path",
    )
    parser.add_argument(
        "--sync-template-sdk-versions",
        action="store_true",
        help="Sync template SDK dependency versions from the current source package versions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sync_template_sdk_versions:
        resolved_versions, updated_files = sync_template_sdk_versions(args.repo_root)
    elif args.version:
        versions: str | dict[str, str] = args.version
        resolved_versions = normalize_versions(versions)
        updated_files = update_repo_versions(args.repo_root, versions)
    else:
        partial_versions = {
            "agent": args.aidev_agent_version,
            "bkplugin": args.aidev_bkplugin_version,
            "wxbot": args.aidev_wxbot_version,
            "ai_blueking": args.aidev_ai_blueking_version,
            "template": args.aidev_template_version,
        }
        versions = {component: version for component, version in partial_versions.items() if version}
        if not versions:
            print("Error: set VERSION=2.0.0b1 or pass at least one per-component version")
            print(
                "Example: make release_versions aidev_ai_blueking_version=2.0.0rc1 "
                "or make release_versions aidev_agent_version=2.0.0b1 aidev_bkplugin_version=2.0.0b2"
            )
            return 1

        resolved_versions = normalize_versions(versions)
        updated_files = update_repo_versions(args.repo_root, versions)
    print("Updated versions:")
    for k, v in resolved_versions.items():
        print(f"  {k}: {v}")
    print(f"Updated {len(updated_files)} files:")
    for path in updated_files:
        print(f"  {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
