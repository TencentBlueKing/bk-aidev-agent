#!/usr/bin/env python3
"""Bootstrap OpenClaw from AIDEV with the current PaaS application's identity."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import httpx

# bkapi-client-core probes django.conf.settings when Django is installed, even in a
# standalone process. Configure only the option it reads; no Django app setup is needed.
from django.conf import settings as django_settings

if not django_settings.configured:
    django_settings.configure(BK_API_CLIENT_ENABLE_SSL_VERIFY=True)

from aidev_agent.packages.craw.sync import render_soul
from aidev_agent.packages.resource_manager.agent import AgentResourceManager

_MAX_SKILL_ARCHIVE_BYTES = 100 * 1024 * 1024
_MANAGED_META = ".bkai-meta.json"


def _skill_slug(skill: dict) -> str:
    raw = str(skill.get("skill_code") or skill.get("skill_name") or skill.get("id") or "skill")
    return re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-.") or "skill"


def _extract_skill_archive(archive: Path, destination: Path) -> Path:
    total_size = 0
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            relative = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("skill archive contains unsafe path")
            if stat.S_ISLNK(mode):
                raise ValueError("skill archive contains symlink")
            total_size += info.file_size
            if total_size > _MAX_SKILL_ARCHIVE_BYTES:
                raise ValueError("skill archive is too large")
        bundle.extractall(destination)

    entries = [path for path in destination.iterdir() if path.name != "__MACOSX"]
    source = entries[0] if len(entries) == 1 and entries[0].is_dir() else destination
    skill_files = list(source.rglob("SKILL.md"))
    if len(skill_files) != 1:
        raise ValueError("skill archive must contain exactly one SKILL.md")
    return skill_files[0].parent


def _install_skill(manager: AgentResourceManager, skill: dict, skills_root: Path) -> str:
    skill_id = skill.get("id")
    if not skill_id:
        raise ValueError("related skill has no id")
    version = skill.get("version") or None
    callee_agent_code = skill.get("callee_agent_code") or None
    slug = _skill_slug(skill)
    print(f"[craw] syncing skill {slug}: resolve application download", file=sys.stderr)
    download = manager.retrieve_skill_download(
        str(skill_id),
        version=version,
        callee_agent_code=callee_agent_code,
    )
    download_url = download.get("url")
    if not download_url:
        raise ValueError("skill download URL is empty")
    print(f"[craw] syncing skill {slug}: download from {urlsplit(download_url).hostname or 'unknown'}", file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="craw-skill-") as temp_dir:
        temp = Path(temp_dir)
        archive = temp / "skill.zip"
        extracted = temp / "extracted"
        extracted.mkdir()
        with httpx.stream("GET", download_url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            size = 0
            with archive.open("wb") as output:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > _MAX_SKILL_ARCHIVE_BYTES:
                        raise ValueError("skill download is too large")
                    output.write(chunk)
        print(f"[craw] syncing skill {slug}: validate archive", file=sys.stderr)
        source = _extract_skill_archive(archive, extracted)

        staging = skills_root / f".{slug}.staging.{uuid.uuid4().hex}"
        target = skills_root / slug
        backup = skills_root / f".{slug}.backup.{uuid.uuid4().hex}"
        shutil.copytree(source, staging)
        (staging / _MANAGED_META).write_text(
            json.dumps(
                {
                    "provider": "aidev-app-identity",
                    "skill_code": skill.get("skill_code") or slug,
                    "version": version or "latest",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            if target.exists():
                target.replace(backup)
            staging.replace(target)
            shutil.rmtree(backup, ignore_errors=True)
        except Exception:
            if not target.exists() and backup.exists():
                backup.replace(target)
            shutil.rmtree(staging, ignore_errors=True)
            raise
    print(f"[craw] syncing skill {slug}: installed", file=sys.stderr)
    return slug


def _error_code(exc: Exception) -> str:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return f"{type(exc).__name__}:{status}" if status else type(exc).__name__


def _write_skill_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def materialize_skills(
    manager: AgentResourceManager,
    related_skills: list,
    skills_root: Path,
    status_path: Path | None = None,
) -> list[str]:
    skills_root.mkdir(parents=True, exist_ok=True)
    installed = []
    failures = []
    expected = set()
    for skill in related_skills:
        if not isinstance(skill, dict):
            continue
        slug = _skill_slug(skill)
        expected.add(slug)
        try:
            installed.append(_install_skill(manager, skill, skills_root))
        except Exception as exc:
            error = _error_code(exc)
            failures.append({"skill": slug, "error": error})
            print(f"[craw] WARN: skipped skill {slug}: {error}", file=sys.stderr)

    for child in skills_root.iterdir():
        metadata_path = child / _MANAGED_META
        if not child.is_dir() or child.name in expected or not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if metadata.get("provider") == "aidev-app-identity":
            shutil.rmtree(child)
    if status_path:
        _write_skill_status(
            status_path,
            {
                "gateway": os.getenv("AIDEV_GATEWAY_NAME", ""),
                "stage": os.getenv("BK_APIGW_STAGE", ""),
                "skills_root": str(skills_root),
                "related_count": len(related_skills),
                "installed": installed,
                "failures": failures,
            },
        )
    return installed


def _migrate_openclaw_2026_8(config: dict) -> None:
    """Remove the ui.assistant key retired by OpenClaw v2026.8.1 without touching valid UI prefs."""
    ui = config.get("ui")
    if not isinstance(ui, dict):
        return
    ui.pop("assistant", None)
    if not ui:
        config.pop("ui", None)


def main() -> int:
    agent_code = os.getenv("BKAI_AGENT") or os.getenv("BKPAAS_APP_ID") or os.getenv("BK_APP_CODE")
    if not agent_code:
        print("missing current application code", file=sys.stderr)
        return 2
    missing = [name for name in ("AIDEV_GATEWAY_NAME", "BK_APIGW_STAGE") if not os.getenv(name)]
    if missing:
        print(f"missing injected runtime settings: {', '.join(missing)}", file=sys.stderr)
        return 4

    manager = AgentResourceManager()
    config = manager.get_agent_config(agent_code)
    model = (config.chat_model or "").strip()
    if not model:
        print(f"agent {agent_code} has no chat model", file=sys.stderr)
        return 3

    state_dir = Path(os.getenv("OPENCLAW_STATE_DIR", Path.home() / ".openclaw"))
    if os.getenv("BKAI_CRAW_SKILLS_ONLY") == "1":
        installed = materialize_skills(
            manager,
            config.related_skills or [],
            state_dir / "skills",
            Path(os.getenv("BKAI_CRAW_SKILL_STATUS_PATH", "/data/craw/skill-sync-status.json")),
        )
        print(f"[craw] application identity synced skills={installed}", file=sys.stderr)
        return 0

    workspace = Path(os.getenv("OPENCLAW_WORKSPACE_DIR", state_dir / "workspace"))
    workspace.mkdir(parents=True, exist_ok=True)
    soul_path = workspace / "SOUL.md"
    soul_path.write_text(render_soul(config), encoding="utf-8")
    soul_path.chmod(0o600)

    config_path = Path(os.getenv("OPENCLAW_CONFIG_PATH", state_dir / "openclaw.json"))
    try:
        openclaw = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        openclaw = {}
    _migrate_openclaw_2026_8(openclaw)

    providers = openclaw.setdefault("models", {}).setdefault("providers", {})
    providers["bkaidev"] = {
        "baseUrl": (
            f"http://127.0.0.1:{os.getenv('BKAI_APP_IDENTITY_EGRESS_PORT', '18790')}/openapi/aidev/gateway/llm/v1"
        ),
        "apiKey": "loopback-application-identity",
        "headers": {"X-Model-Name": model},
        "models": [{"id": model, "name": model}],
    }
    defaults = openclaw.setdefault("agents", {}).setdefault("defaults", {})
    defaults["model"] = f"bkaidev/{model}"
    defaults["skipBootstrap"] = True
    mcp_servers = openclaw.setdefault("mcp", {}).setdefault("servers", {})
    for mcp_code, mcp_config in (config.mcp_server_config or {}).items():
        if isinstance(mcp_config, dict):
            normalized = dict(mcp_config)
            transport = normalized.get("transport")
            if transport in {"streamable_http", "streamableHttp", "streamablehttp"}:
                normalized["transport"] = "streamable-http"
            mcp_servers[mcp_code] = normalized
    gateway = openclaw.setdefault("gateway", {})
    gateway.setdefault("port", int(os.getenv("OPENCLAW_GATEWAY_PORT", "18789")))
    gateway.setdefault("mode", "local")
    gateway.setdefault("bind", "auto")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(openclaw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(config_path)

    print(f"[craw] application identity loaded agent config: {agent_code}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
