"""独立插件的启动配置和平台资源契约。"""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str
    agent_code: str
    # 当前平台 agent/{agent_code} 路径实际按 app_code 查询，不能隐式等同业务 code。
    agent_app_code: str
    tenant_id: str
    access_token: SecretStr
    app_secret: SecretStr = SecretStr("")
    subject_id: str = ""
    version: str = Field(min_length=1)
    engine: Literal["openclaw", "hermes"]
    mounted_storage: bool = False
    root: Path
    mcp_names: list[str] | None = None
    skill_ids: list[int] | None = None
    skill_versions: dict[int, str] = Field(default_factory=dict)
    include_prompt: bool = True
    download_origins: list[str] = Field(default_factory=list)
    mcp_auth_origins: list[str] = Field(default_factory=list)
    max_download_bytes: int = Field(default=32 * 1024 * 1024, gt=0)
    max_pending_runs: int = Field(default=32, ge=1)
    poll_seconds: float = Field(default=60, ge=1)
    prompt_timeout: float = Field(default=300, gt=0)
    command: list[str] | None = Field(default=None, min_length=1)
    # 子进程仅继承明确的引擎环境；不继承 Adapter 的平台身份。
    engine_env: dict[str, str] = Field(default_factory=dict, repr=False)
    # Enable platform model selection for a deployment-owned OpenClaw provider.
    openclaw_model_provider: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]+$")
    native_config: dict[str, Any] = Field(default_factory=dict, repr=False)

    @property
    def identity(self) -> str:
        """持久化存储身份：仅绑定不可变业务坐标，不耦合易轮换的 access_token。"""
        parts = [
            self.endpoint.rstrip("/"),
            self.tenant_id,
            self.agent_code,
            self.agent_app_code,
            self.engine,
        ]
        if self.subject_id:
            parts.append(self.subject_id)
        return hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()

    @field_validator("agent_code", "agent_app_code", "tenant_id", "version")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip() or any(c in value for c in "\r\n\x00"):
            raise ValueError("identity/version must be nonempty and single-line")
        return value


class Bundle(BaseModel):
    agent_code: str
    version: str
    model_code: str | None = None
    prompt: str | None = None
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict, repr=False)
    skills: list[dict[str, Any]] = Field(default_factory=list, repr=False)
