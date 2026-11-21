"""AIDev 当前 OpenAPI 的独立 HTTP 客户端，不加载 Django/Agent 执行图。"""

import hashlib
import json
from urllib.parse import quote, urlsplit

import httpx

from .models import Bundle, Settings


class PlatformError(RuntimeError):
    """面向调用者的脱敏错误。"""


def origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PlatformError("HTTPS URL without embedded credentials required")
    if parsed.fragment:
        raise PlatformError("URL fragments are not supported")
    return f"https://{parsed.hostname}:{parsed.port or 443}"


class PlatformClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        origin(settings.endpoint)
        if urlsplit(settings.endpoint).query:
            raise PlatformError("platform endpoint must not contain a query")
        auth = {"bk_app_code": settings.agent_app_code, "access_token": settings.access_token.get_secret_value()}
        if settings.app_secret.get_secret_value():
            auth["bk_app_secret"] = settings.app_secret.get_secret_value()
        self.client = httpx.AsyncClient(
            transport=transport,
            timeout=30,
            follow_redirects=False,
            trust_env=False,
            headers={"X-Bkapi-Authorization": json.dumps(auth), "X-Bk-Tenant-Id": settings.tenant_id},
        )
        # 下载使用无认证独立客户端，绝不泄露平台凭据给制品域名。
        self.download_client = httpx.AsyncClient(
            transport=transport,
            timeout=60,
            follow_redirects=False,
            trust_env=False,
        )
        self.allowed_origins = {origin(settings.endpoint), *(origin(url) for url in settings.download_origins)}

    async def close(self) -> None:
        await self.client.aclose()
        await self.download_client.aclose()

    async def get(self, path: str, params: dict) -> dict:
        url = self.settings.endpoint.rstrip("/") + "/openapi/aidev/resource/v1/" + path
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise PlatformError("AIDev API returned invalid envelope")
            if payload.get("result") is False or payload.get("code", 0) not in (0, "0"):
                raise PlatformError("AIDev API rejected the request")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise PlatformError("AIDev API returned invalid data")
            return data
        except (httpx.HTTPError, ValueError):
            raise PlatformError("AIDev request failed") from None

    async def fetch(self) -> Bundle:
        settings = self.settings
        data = await self.get(f"agent/{quote(settings.agent_app_code, safe='')}/", {"version": settings.version})
        if data.get("allowed_access") is not True:
            raise PlatformError("agent access is not authorized")
        if data.get("agent_code") != settings.agent_app_code:
            raise PlatformError("agent identity mismatch")
        prompt = None
        if settings.include_prompt:
            content = (data.get("prompt_setting") or {}).get("content")
            if isinstance(content, str):
                prompt = content
            elif isinstance(content, list) and all(
                isinstance(item, dict)
                and item.get("role") in {"system", "developer"}
                and isinstance(item.get("content"), str)
                for item in content
            ):
                prompt = "\n\n".join(item["content"] for item in content)
            else:
                raise PlatformError("prompt must contain system/developer instructions only")
        servers = (data.get("mcp_server_config") or {}).get("mcpServers", {})
        if not isinstance(servers, dict):
            raise PlatformError("invalid MCP configuration")
        names = list(servers) if settings.mcp_names is None else settings.mcp_names
        if not set(names) <= servers.keys():
            raise PlatformError("selected MCP is not bound to this agent")
        related = data.get("related_skills") or []
        if isinstance(related, dict):
            related = related.get("skills", [])
        bound = {int(item["id"]): item for item in related}
        ids = list(bound) if settings.skill_ids is None else settings.skill_ids
        if not set(ids) <= bound.keys():
            raise PlatformError("selected Skill is not bound to this agent")
        if not settings.skill_versions.keys() <= set(ids):
            raise PlatformError("Skill version pins must refer to selected bound Skills")
        skills = []
        for skill_id in ids:
            expected = settings.skill_versions.get(skill_id, bound[skill_id].get("version"))
            if not expected:
                raise PlatformError("Skill version must be explicit")
            skill = await self.get(
                f"agents/skill/{skill_id}/",
                {"version": expected, "agent_version": settings.version},
            )
            if skill.get("id") != skill_id or skill.get("version") != expected:
                raise PlatformError("Skill identity/version mismatch")
            skills.append(skill)
        return Bundle(
            agent_code=settings.agent_code,
            version=settings.version,
            prompt=prompt if settings.include_prompt else None,
            mcp_servers={name: self.prepare_mcp(servers[name]) for name in names},
            skills=skills,
        )

    def prepare_mcp(self, server: dict) -> dict:
        server = dict(server)
        headers = dict(server.get("headers") or {})
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in headers.items()):
            raise PlatformError("invalid MCP headers")
        needs_auth = (
            server.get("credential_type") == "blueapps"
            or any(key.lower() == "x-bkapi-authorization" for key in headers)
            or any("{{access_token}}" in value for value in headers.values())
        )
        if needs_auth:
            allowed = {origin(self.settings.endpoint), *(origin(url) for url in self.settings.mcp_auth_origins)}
            if origin(server.get("url", "")) not in allowed:
                raise PlatformError("MCP credential destination is not explicitly allowed")
            headers = {
                key: value
                for key, value in headers.items()
                if key.lower() not in {"x-bkapi-authorization", "x-bk-tenant-id"}
            }
            headers["X-Bk-Tenant-Id"] = self.settings.tenant_id
            headers["X-Bkapi-Authorization"] = json.dumps(
                {"access_token": self.settings.access_token.get_secret_value()}
            )
        if any("{{" in value or "bk_app_secret" in value for value in headers.values()):
            raise PlatformError("unresolved or privileged MCP credentials are not allowed")
        server["headers"] = headers
        return server

    async def download(self, skill: dict) -> bytes:
        url = skill.get("url", "")
        if origin(url) not in self.allowed_origins:
            raise PlatformError("Skill download origin is not allowed")
        chunks = bytearray()
        try:
            async with self.download_client.stream("GET", url) as response:
                response.raise_for_status()  # redirects are rejected, never followed
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > self.settings.max_download_bytes:
                        raise PlatformError("Skill download exceeds size limit")
        except httpx.HTTPError:
            raise PlatformError("Skill download failed") from None
        digest = skill.get("file_md5")
        if not digest or hashlib.md5(chunks, usedforsecurity=False).hexdigest() != digest.lower():
            raise PlatformError("Skill checksum missing or mismatched")
        return bytes(chunks)
