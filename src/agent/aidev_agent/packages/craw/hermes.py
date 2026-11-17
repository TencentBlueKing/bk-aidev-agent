# -*- coding: utf-8 -*-
"""Hermes 后端：转发 Hermes gateway api_server 平台（OpenAI 兼容）。

会话 / 记忆语义（与既有插件实现一致）：
- ``X-Hermes-Session-Id``  ← 平台 ``session_code``：Hermes 侧复用同一会话与
  沙箱目录；
- ``X-Hermes-Session-Key`` ← 平台 ``username``：长期记忆按用户作用域隔离。
  上游强制要求启用 Bearer 认证才接受该头（未配 token 时发送会被 4xx 拒绝，
  故仅在配了 api_key 时携带）。

api_server 端口为部署级配置（bkai-cli 池模式默认 8642），legacy env 兼容
``BKAI_HERMES_API_URL`` / ``BKAI_HERMES_API_KEY``（对应 Hermes 侧
``API_SERVER_KEY``）。
"""

from __future__ import annotations

from typing import ClassVar, Optional

from aidev_agent.packages.craw.base import BaseCrawBackend, CrawIdentity


class HermesBackend(BaseCrawBackend):
    name: ClassVar[str] = "hermes"
    default_model: ClassVar[str] = "hermes-agent"
    default_api_url: ClassVar[str] = "http://127.0.0.1:8642"
    health_path: ClassVar[str] = "/health"

    legacy_url_envs: ClassVar[tuple[str, ...]] = ("BKAI_HERMES_API_URL",)
    legacy_key_envs: ClassVar[tuple[str, ...]] = ("BKAI_HERMES_API_KEY",)
    legacy_model_envs: ClassVar[tuple[str, ...]] = ("BKAI_HERMES_MODEL",)
    legacy_timeout_envs: ClassVar[tuple[str, ...]] = ("BKAI_HERMES_TIMEOUT",)

    def extra_headers(
        self, identity: Optional[CrawIdentity] = None, session_code: Optional[str] = None
    ) -> dict[str, str]:
        headers: dict[str, str] = {}
        if session_code:
            headers["X-Hermes-Session-Id"] = str(session_code)
        if self.api_key and identity and identity.username:
            headers["X-Hermes-Session-Key"] = str(identity.username)
        return headers
