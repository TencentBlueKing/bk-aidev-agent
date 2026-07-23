# -*- coding: utf-8 -*-
"""Craw 后端通用基座。

收敛所有内核共用的传输逻辑：
- 连接参数装配（统一 env ``BKAI_CRAW_*`` > 各内核 legacy env > 默认值）；
- ``POST /v1/chat/completions`` 流式（SSE 解析）/ 非流式转发；
- 健康探测；
- 用户身份隔离（``CrawIdentity``）：对齐 bkai-cli 池模式反代契约——
  用户 access_token 经 ``X-Bkai-Access-Token`` 头透传，craw 侧（或其前置
  反代）据此做每用户内核 / MCP 凭证隔离；本层只做路由键哈希与头注入，
  **绝不记录 / 持久化原始 token**。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from logging import getLogger
from typing import ClassVar, Iterator, Optional

import httpx
from pydantic import BaseModel

_logger = getLogger(__name__)

# 用户身份透传头：与 bkai-cli `hermes proxy expose --pool` 的池路由契约一致
IDENTITY_HEADER = "X-Bkai-Access-Token"


class CrawIdentity(BaseModel):
    """一次调用的用户身份（token 隔离的最小载体）。

    :param username: 平台用户名（可空）。
    :param access_token: 用户 AIDEV access_token（可空；不入日志、不落盘）。
    """

    username: str = ""
    access_token: str = ""

    @property
    def identity_id(self) -> str:
        """身份路由键：``sha256(access_token or username)[:16]``，可安全入日志。"""
        seed = self.access_token or self.username
        if not seed:
            return ""
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    def __repr__(self) -> str:  # 防止意外把 token 打进日志 / 异常栈
        return f"CrawIdentity(username={self.username!r}, identity_id={self.identity_id!r})"

    __str__ = __repr__


def _env_first(*names: str) -> str:
    """按序取第一个非空 env 值。"""
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


class BaseCrawBackend:
    """Craw 后端通用实现（``CrawBackendProtocol`` 的基座）。

    子类需给出类属性：``name`` / ``default_model`` / ``default_api_url``，
    以及 legacy env 名（``legacy_url_envs`` / ``legacy_key_envs`` /
    ``legacy_model_envs`` / ``legacy_timeout_envs``）；差异化请求头覆写
    ``extra_headers()``。
    """

    name: ClassVar[str] = ""
    default_model: ClassVar[str] = ""
    default_api_url: ClassVar[str] = ""
    health_path: ClassVar[str] = "/healthz"
    chat_path: ClassVar[str] = "/v1/chat/completions"

    legacy_url_envs: ClassVar[tuple[str, ...]] = ()
    legacy_key_envs: ClassVar[tuple[str, ...]] = ()
    legacy_model_envs: ClassVar[tuple[str, ...]] = ()
    legacy_timeout_envs: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.api_url = (
            api_url or _env_first("BKAI_CRAW_API_URL", *self.legacy_url_envs) or self.default_api_url
        ).rstrip("/")
        self.api_key = api_key or _env_first("BKAI_CRAW_API_KEY", *self.legacy_key_envs)
        self.model = model or _env_first("BKAI_CRAW_MODEL", *self.legacy_model_envs) or self.default_model
        if timeout is None:
            raw = _env_first("BKAI_CRAW_TIMEOUT", *self.legacy_timeout_envs)
            try:
                timeout = float(raw) if raw else 300.0
            except (TypeError, ValueError):
                timeout = 300.0
        self.timeout = timeout

    # ---------- 请求装配 ----------

    def build_headers(
        self, identity: Optional[CrawIdentity] = None, session_code: Optional[str] = None
    ) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if identity and identity.access_token:
            headers[IDENTITY_HEADER] = identity.access_token
        headers.update(self.extra_headers(identity=identity, session_code=session_code))
        return headers

    def extra_headers(
        self, identity: Optional[CrawIdentity] = None, session_code: Optional[str] = None
    ) -> dict[str, str]:
        """内核差异化请求头（会话粘滞 / 记忆作用域等），子类按需覆写。"""
        return {}

    def chat_payload(self, messages: list[dict], stream: bool) -> dict:
        return {"messages": messages, "model": self.model, "stream": stream}

    # ---------- chat 转发 ----------

    def chat_completions(
        self,
        messages: list[dict],
        identity: Optional[CrawIdentity] = None,
        session_code: Optional[str] = None,
    ) -> dict:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.api_url}{self.chat_path}",
                headers=self.build_headers(identity=identity, session_code=session_code),
                json=self.chat_payload(messages, stream=False),
            )
            resp.raise_for_status()
            return resp.json()

    def chat_completions_stream(
        self,
        messages: list[dict],
        identity: Optional[CrawIdentity] = None,
        session_code: Optional[str] = None,
    ) -> Iterator[dict]:
        with (
            httpx.Client(timeout=self.timeout) as client,
            client.stream(
                "POST",
                f"{self.api_url}{self.chat_path}",
                headers=self.build_headers(identity=identity, session_code=session_code),
                json=self.chat_payload(messages, stream=True),
            ) as resp,
        ):
            if resp.status_code >= 400:
                detail = resp.read().decode("utf-8", "ignore")[:500]
                raise CrawUpstreamError(self.name, resp.status_code, detail)
            yield from self.iter_sse_chunks(resp.iter_lines())

    @staticmethod
    def iter_sse_chunks(lines: Iterator[str]) -> Iterator[dict]:
        """解析 OpenAI 兼容 SSE 行流：产出 ``data:`` JSON chunk，遇 ``[DONE]`` 结束。"""
        for raw in lines:
            if not raw:
                continue
            line = raw.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                return
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                continue

    @staticmethod
    def delta_text(chunk: dict) -> str:
        """从流式 chunk 取 ``choices[0].delta.content``（无则空串）。"""
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        piece = (choices[0].get("delta") or {}).get("content")
        return piece if isinstance(piece, str) else ""

    @staticmethod
    def message_text(body: dict) -> str:
        """从非流式响应取 ``choices[0].message.content``（兼容 delta 形态）。"""
        choice = (body.get("choices") or [{}])[0]
        return (choice.get("message") or {}).get("content") or (choice.get("delta") or {}).get("content") or ""

    # ---------- 健康探测 ----------

    def health(self) -> dict:
        started = time.monotonic()
        try:
            with httpx.Client(timeout=min(self.timeout, 10.0)) as client:
                resp = client.get(f"{self.api_url}{self.health_path}")
            return {
                "ok": resp.status_code < 400,
                "status_code": resp.status_code,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "backend": self.name,
                "api_url": self.api_url,
            }
        except Exception as exc:
            _logger.warning("[CRAW] %s health check failed: %s", self.name, exc)
            return {
                "ok": False,
                "status_code": None,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "backend": self.name,
                "api_url": self.api_url,
                "error": str(exc),
            }


class CrawIdentityError(RuntimeError):
    """用户身份装配失败（fail-closed）：拒绝降级为无身份请求。

    有 username 但 access_token 获取失败 / 为空时抛出——无身份的请求会
    落入 craw 侧默认路由，破坏用户级内核 / MCP 隔离，宁可本次调用失败。
    """


class CrawUpstreamError(RuntimeError):
    """craw 上游返回 4xx/5xx（携带截断后的响应详情，不含凭证）。"""

    def __init__(self, backend: str, status_code: int, detail: str) -> None:
        self.backend = backend
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"craw backend {backend} upstream {status_code}: {detail}")
