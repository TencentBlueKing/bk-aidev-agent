# -*- coding: utf-8 -*-
"""OpenClaw 后端：转发 OpenClaw gateway 的 OpenAI 兼容 HTTP API。

- 默认端口 18789（gateway ``chatCompletions`` 端点需在 craw 侧打开，
  ``bkai-openclaw-agent`` 镜像 paas 模式默认已打开）；
- ``model`` 字段选择的是 OpenClaw **agent**（默认 ``openclaw``），不是 LLM 名；
- 会话粘滞经 ``x-openclaw-session-key``（gateway 的 per-request 会话路由，
  与 Hermes 后端的 ``X-Hermes-Session-Id`` 对称）；
- 健康检查 ``GET /healthz``；
- legacy env 兼容既有插件实现（``BKAI_OPENCLAW_GATEWAY_URL`` 等）。
"""

from __future__ import annotations

import os
from typing import ClassVar, Optional

from aidev_agent.packages.craw.base import BaseCrawBackend, CrawIdentity

# gateway 会话路由头：同 key 复用同一内核会话，不发则每请求新建。
# 内核侧状态（工作区文件 / exec 审批 pending 等）只在同一内核会话内保留，
# 缺此头会导致多轮对话每轮丢失内核状态（文本上下文靠宿主整段重放不受影响）。
SESSION_KEY_HEADER = "x-openclaw-session-key"


class OpenClawBackend(BaseCrawBackend):
    name: ClassVar[str] = "openclaw"
    default_model: ClassVar[str] = "openclaw"
    default_api_url: ClassVar[str] = "http://127.0.0.1:18789"
    health_path: ClassVar[str] = "/healthz"

    legacy_url_envs: ClassVar[tuple[str, ...]] = ("BKAI_OPENCLAW_GATEWAY_URL",)
    legacy_key_envs: ClassVar[tuple[str, ...]] = ("OPENCLAW_GATEWAY_TOKEN",)
    legacy_model_envs: ClassVar[tuple[str, ...]] = ("BKAI_OPENCLAW_MODEL",)
    legacy_timeout_envs: ClassVar[tuple[str, ...]] = ("BKAI_OPENCLAW_TIMEOUT",)

    def __init__(self, *args, transport: Optional[str] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.transport = (transport or os.getenv("BKAI_OPENCLAW_TRANSPORT") or "http").strip().lower()
        if self.transport not in {"http", "ws"}:
            self.transport = "http"

    def extra_headers(
        self, identity: Optional[CrawIdentity] = None, session_code: Optional[str] = None
    ) -> dict[str, str]:
        if not session_code:
            return {}
        return {SESSION_KEY_HEADER: session_code}
