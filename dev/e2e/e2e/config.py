from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

TRUTHY = {"1", "true", "yes", "on", "y"}
SUPPORTED_MODULES = ("api", "ai-blueking", "message", "metrics", "wxbot")


def load_env_file(path: Path) -> None:
    """Load a small dotenv subset without overwriting explicit process env."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[:1] == value[-1:] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in TRUTHY


@dataclass(frozen=True)
class Identity:
    username: str
    mode: str
    access_token: str = ""

    @property
    def headers(self) -> dict[str, str]:
        return {"X-BKAIDEV-USER": self.username}


@dataclass(frozen=True)
class Config:
    root: Path
    modules: tuple[str, ...]
    database: str
    app_url: str
    mock_url: str
    report_dir: Path
    headless: bool
    observability: bool
    env_file: Path

    @classmethod
    def from_env(cls, modules: str = "") -> "Config":
        root = Path(__file__).resolve().parents[3]
        env_file = Path(os.getenv("E2E_ENV_FILE", root / "dev/e2e/.env")).expanduser()
        load_env_file(env_file)
        selected = tuple(item.strip() for item in (modules or os.getenv("E2E_MODULES", "")).split(",") if item.strip())
        if not selected or "all" in selected:
            selected = SUPPORTED_MODULES
        unknown = sorted(set(selected) - set(SUPPORTED_MODULES))
        if unknown:
            raise ValueError(f"unsupported E2E modules: {', '.join(unknown)}")
        database = os.getenv("E2E_DB", "sqlite").strip().lower()
        if database not in {"sqlite", "mysql"}:
            raise ValueError("E2E_DB must be sqlite or mysql")
        report_dir = Path(os.getenv("E2E_REPORT_DIR", root / "dev/e2e/reports")).expanduser()
        if not report_dir.is_absolute():
            report_dir = root / report_dir
        config = cls(
            root=root,
            modules=selected,
            database=database,
            app_url=os.getenv("E2E_APP_URL", "http://127.0.0.1:18000").rstrip("/"),
            mock_url=os.getenv("E2E_MOCK_URL", "http://127.0.0.1:18080").rstrip("/"),
            report_dir=report_dir,
            headless=env_bool("E2E_HEADLESS", True),
            observability=env_bool("E2E_OBSERVABILITY", True),
            env_file=env_file,
        )
        for label, value in (("E2E_APP_URL", config.app_url), ("E2E_MOCK_URL", config.mock_url)):
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError(f"{label} must be an HTTP URL")
        return config


def configured_identity() -> Identity:
    """Resolve local login with the documented access-token-first priority."""
    access_token = os.getenv("E2E_ACCESS_TOKEN", "").strip() or os.getenv("ACCESS_TOKEN", "").strip()
    if access_token:
        username = os.getenv("E2E_TOKEN_USERNAME", "").strip() or os.getenv("E2E_USERNAME", "").strip()
        return Identity(username=username or "e2e-token-user", mode="access_token", access_token=access_token)
    username = os.getenv("E2E_USERNAME", "").strip()
    if username:
        return Identity(username=username, mode="username")
    raise ValueError("configure E2E_ACCESS_TOKEN or E2E_USERNAME in the E2E env file")
