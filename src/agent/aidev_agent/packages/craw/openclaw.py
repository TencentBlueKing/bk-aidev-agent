# -*- coding: utf-8 -*-
"""OpenClaw 后端：转发 OpenClaw gateway 的 OpenAI 兼容 HTTP API。

- 默认端口 18789（gateway ``chatCompletions`` 端点需在 craw 侧打开，
  ``bkai-openclaw-agent`` 镜像 paas 模式默认已打开）；
- ``model`` 字段选择的是 OpenClaw **agent**（默认 ``openclaw``），不是 LLM 名；
- 健康检查 ``GET /healthz``；
- legacy env 兼容既有插件实现（``BKAI_OPENCLAW_GATEWAY_URL`` 等）。
"""

from __future__ import annotations

from typing import ClassVar

from aidev_agent.packages.craw.base import BaseCrawBackend


class OpenClawBackend(BaseCrawBackend):
    name: ClassVar[str] = "openclaw"
    default_model: ClassVar[str] = "openclaw"
    default_api_url: ClassVar[str] = "http://127.0.0.1:18789"
    health_path: ClassVar[str] = "/healthz"

    legacy_url_envs: ClassVar[tuple[str, ...]] = ("BKAI_OPENCLAW_GATEWAY_URL",)
    legacy_key_envs: ClassVar[tuple[str, ...]] = ("OPENCLAW_GATEWAY_TOKEN",)
    legacy_model_envs: ClassVar[tuple[str, ...]] = ("BKAI_OPENCLAW_MODEL",)
    legacy_timeout_envs: ClassVar[tuple[str, ...]] = ("BKAI_OPENCLAW_TIMEOUT",)
