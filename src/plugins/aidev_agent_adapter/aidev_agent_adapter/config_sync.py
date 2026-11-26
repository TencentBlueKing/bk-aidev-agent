"""配置先完整构建，再发布版本快照。消费端固定快照路径，更新不扰动运行。"""

import asyncio
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from .models import Bundle, Settings
from .platform import PlatformClient, PlatformError, origin

NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


@contextmanager
def directory_fd(path: Path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def private_directory(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlinked state path is not allowed")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise ValueError("state directory must belong to the adapter user")
    path.chmod(0o700)
    return path


def write_private(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(data.encode() if isinstance(data, str) else data)
        stream.flush()
        os.fsync(stream.fileno())


def unpack_skill(data: bytes, destination: Path, limit: int) -> None:
    """只支持平台 ZIP 包；拒绝链接、路径穿越、重复项与展开炸弹。"""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        if len(files) > 4096 or sum(item.file_size for item in files) > limit:
            raise ValueError("Skill archive exceeds extraction limits")
        paths = [PurePosixPath(item.filename) for item in files]
        for item, path in zip(files, paths, strict=True):
            mode = item.external_attr >> 16
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in item.filename
                or ":" in item.filename
                or not path.parts
                or stat.S_ISLNK(mode)
                or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
            ):
                raise ValueError("unsafe Skill archive entry")
        prefix = None
        if PurePosixPath("SKILL.md") not in paths:
            roots = {path.parts[0] for path in paths}
            if len(roots) != 1 or PurePosixPath(next(iter(roots)), "SKILL.md") not in paths:
                raise ValueError("Skill archive must contain a single SKILL.md root")
            prefix = next(iter(roots))
        seen = set()
        for item, path in zip(files, paths, strict=True):
            relative = path.relative_to(prefix) if prefix else path
            key = str(relative).casefold()
            if key in seen:
                raise ValueError("duplicate Skill archive entry")
            seen.add(key)
            target = destination / relative
            write_private(target, archive.read(item))
            if (item.external_attr >> 16) & 0o100:
                target.chmod(0o700)  # retain owner execute only, never group/world/setuid bits
        if not (destination / "SKILL.md").read_text().strip():
            raise ValueError("empty SKILL.md")


def render_mcp(servers: dict[str, dict], engine: str) -> dict:
    result = {}
    for name, server in servers.items():
        if not NAME.fullmatch(name):
            raise ValueError("invalid MCP name")
        if server.get("command"):
            raise ValueError("platform-provided stdio MCP requires a separately approved launcher")
        url = server.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("remote MCP must use HTTPS")
        origin(url)
        transport = server.get("transport", "streamable_http").replace("_", "-")
        if transport not in {"sse", "streamable-http", "http"}:
            raise ValueError("unsupported MCP transport")
        headers = server.get("headers") or {}
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()):
            raise ValueError("invalid MCP headers")
        # Native config belongs to a dedicated engine profile, not the user's global config.
        entry = {"url": url, "headers": headers}
        if engine == "openclaw":
            entry["transport"] = "streamable-http" if transport == "http" else transport
        elif transport == "sse":
            entry["transport"] = "sse"
        selected = server.get("selected_tools")
        if selected is not None:
            if not isinstance(selected, list) or any(
                not isinstance(tool, str) or not tool or any(c in tool for c in "*?[") for tool in selected
            ):
                raise ValueError("MCP selected_tools must contain literal tool names")
            if not selected:
                entry["enabled"] = False
            else:
                entry["toolFilter" if engine == "openclaw" else "tools"] = {"include": selected}
        result[name] = entry
    return result


@dataclass(frozen=True)
class Snapshot:
    path: Path
    revision: str
    engine: str

    @property
    def workspace(self) -> Path:
        return self.path / "workspace"

    @property
    def environment(self) -> dict[str, str]:
        if self.engine == "openclaw":
            return {"OPENCLAW_CONFIG_PATH": str(self.path / "openclaw.json")}
        return {"HERMES_HOME": str(self.path)}


class ConfigSynchronizer:
    def __init__(self, settings: Settings, platform: PlatformClient):
        self.settings = settings
        self.platform = platform
        self.root = private_directory(settings.root)
        self._lock = asyncio.Lock()

    async def sync(self) -> Snapshot:
        async with self._lock:
            # flock serializes publishers across processes, acquired without blocking the event loop.
            with (self.root / ".sync.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise RuntimeError("configuration sync already in progress") from None
                owner = self.root / "owner.json"
                if owner.is_symlink():
                    raise ValueError("invalid configuration owner file")
                if owner.exists():
                    if json.loads(owner.read_text()).get("identity") != self.settings.identity:
                        raise ValueError("configuration identity mismatch; use a separate instance directory")
                else:
                    write_private(owner, json.dumps({"identity": self.settings.identity}))
                bundle = await self.platform.fetch()
                packages = [(skill, await self.platform.download(skill)) for skill in bundle.skills]
                return self._publish(bundle, packages)

    def _publish(self, bundle: Bundle, packages: list[tuple[dict, bytes]]) -> Snapshot:
        stage = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.root))
        try:
            # Avoid storing signed artifact URLs in metadata or fingerprint; archive digest suffices.
            identity = {
                "renderer_version": 2,
                "agent_code": bundle.agent_code,
                "version": bundle.version,
                "tenant": self.settings.tenant_id,
                "engine": self.settings.engine,
                "prompt": bundle.prompt,
                "mcp": bundle.mcp_servers,
                "native": self.settings.native_config,
                "skills": [
                    (s["id"], s["version"], s.get("skill_code"), hashlib.sha256(b).hexdigest()) for s, b in packages
                ],
            }
            revision = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            final = self.root / revision
            self._render(stage, final, bundle, packages)
            write_private(
                stage / "manifest.json",
                json.dumps(
                    {
                        "revision": revision,
                        "version": bundle.version,
                        "agent_code": bundle.agent_code,
                        "engine": self.settings.engine,
                    }
                ),
            )
            if final.exists():
                if final.is_symlink():
                    raise ValueError("invalid snapshot path")
                self._verify_managed_files(stage, final)
            else:
                stage.rename(final)
            temporary_link = self.root / ".next"
            if temporary_link.exists() or temporary_link.is_symlink():
                temporary_link.unlink()
            temporary_link.symlink_to(final.name, target_is_directory=True)
            os.replace(temporary_link, self.root / "current")
            with directory_fd(self.root) as descriptor:
                os.fsync(descriptor)
            return Snapshot(final, revision, self.settings.engine)
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def _verify_managed_files(self, stage: Path, final: Path) -> None:
        managed = (
            ["openclaw.json", "workspace/SOUL.md", "workspace/skills"]
            if self.settings.engine == "openclaw"
            else ["config.yaml", "SOUL.md", "skills"]
        )
        managed.append("manifest.json")
        for name in managed:
            expected, actual = stage / name, final / name
            if any(part.is_symlink() for part in (actual, *actual.parents)):
                raise ValueError("managed snapshot was modified: symlink")
            if expected.exists() != actual.exists():
                raise ValueError("managed snapshot was modified")
            if not expected.exists():
                continue
            expected_paths = {Path("."): expected, **{p.relative_to(expected): p for p in expected.rglob("*")}}
            actual_paths = {Path("."): actual, **{p.relative_to(actual): p for p in actual.rglob("*")}}
            if expected_paths.keys() != actual_paths.keys():
                raise ValueError("managed snapshot was modified")
            for relative, source in expected_paths.items():
                target = actual_paths[relative]
                if target.is_symlink() or source.is_dir() != target.is_dir() or source.is_file() != target.is_file():
                    raise ValueError("managed snapshot was modified")
                if source.is_file() and (
                    source.read_bytes() != target.read_bytes()
                    or stat.S_IMODE(source.stat().st_mode) != stat.S_IMODE(target.stat().st_mode)
                ):
                    raise ValueError("managed snapshot was modified")

    def _render(self, stage: Path, final: Path, bundle: Bundle, packages: list[tuple[dict, bytes]]) -> None:
        (stage / "workspace").mkdir(mode=0o700)
        prompt_dir = stage / "workspace" if self.settings.engine == "openclaw" else stage
        if bundle.prompt is not None:
            write_private(prompt_dir / "SOUL.md", bundle.prompt)
        skills_dir = stage / "workspace" / "skills" if self.settings.engine == "openclaw" else stage / "skills"
        for skill, data in packages:
            name = skill.get("skill_code", "")
            if not NAME.fullmatch(name) or (skills_dir / name).exists():
                raise PlatformError("invalid or duplicate Skill code")
            unpack_skill(data, skills_dir / name, self.settings.max_download_bytes)
        config = json.loads(json.dumps(self.settings.native_config))
        servers = render_mcp(bundle.mcp_servers, self.settings.engine)
        if self.settings.engine == "openclaw":
            config.setdefault("agents", {}).setdefault("defaults", {})["workspace"] = str(final / "workspace")
            config.setdefault("mcp", {})["servers"] = servers
            write_private(stage / "openclaw.json", json.dumps(config, ensure_ascii=False, indent=2))
        else:
            config["mcp_servers"] = servers
            write_private(stage / "config.yaml", yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
