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
import threading
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


class CrawChatStream:
    """一次流式 chat 的可关闭句柄。

    - 迭代产出已解析的 OpenAI 兼容 chunk dict（严格 SSE：畸形 ``data:`` 行、
      未见 ``[DONE]`` 即 EOF 均抛 ``CrawStreamProtocolError``，不静默当成功）；
    - ``close()`` 线程安全且幂等：``stop()`` 取消链路从其他线程调用它可立即
      中断阻塞中的上游读取（HTTP 客户端等数据期间也能打断），关闭后迭代
      静默结束，由调用方走取消收尾而非报错。
    """

    def __init__(self, backend_name: str, client: httpx.Client, response: httpx.Response) -> None:
        self.backend_name = backend_name
        self._client = client
        self._response = response
        self._lock = threading.Lock()
        self._closed = False
        self._finished = False

    @property
    def interrupted(self) -> bool:
        """是否在自然结束（``[DONE]``）前被主动 ``close()``（取消语义）。"""
        return self._closed and not self._finished

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            self._response.close()
        finally:
            self._client.close()

    def __enter__(self) -> "CrawChatStream":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def __iter__(self) -> Iterator[dict]:
        try:
            for chunk in BaseCrawBackend.iter_sse_chunks(self._response.iter_lines(), backend=self.backend_name):
                if self._closed:  # 已取消：残余缓冲数据不再下发
                    return
                yield chunk
            self._finished = True
        except CrawStreamProtocolError:
            if self._closed:  # 被 stop() 主动关闭：EOF/读错误是预期结果，不算协议违例
                return
            raise
        except Exception as exc:
            if self._closed:
                return
            raise CrawStreamProtocolError(self.backend_name, f"读取上游流失败: {exc}") from exc
        finally:
            self.close()


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
        """非流式转发。仅 2xx 视为成功——3xx（如未预期的重定向）同样拒绝，
        绝不把非正常响应解析成"成功回复"。

        :raises CrawUpstreamError: 上游返回非 2xx。
        """
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.api_url}{self.chat_path}",
                headers=self.build_headers(identity=identity, session_code=session_code),
                json=self.chat_payload(messages, stream=False),
            )
            if not (200 <= resp.status_code < 300):
                raise CrawUpstreamError(self.name, resp.status_code, resp.text[:500])
            return resp.json()

    def open_chat_stream(
        self,
        messages: list[dict],
        identity: Optional[CrawIdentity] = None,
        session_code: Optional[str] = None,
    ) -> CrawChatStream:
        """打开流式 chat，返回可关闭句柄（供 ``stop()`` 跨线程中断阻塞读取）。

        :raises CrawUpstreamError: 上游返回非 2xx（3xx 亦拒绝）。
        """
        client = httpx.Client(timeout=self.timeout)
        try:
            request = client.build_request(
                "POST",
                f"{self.api_url}{self.chat_path}",
                headers=self.build_headers(identity=identity, session_code=session_code),
                json=self.chat_payload(messages, stream=True),
            )
            response = client.send(request, stream=True)
        except Exception:
            client.close()
            raise
        if not (200 <= response.status_code < 300):
            try:
                detail = response.read().decode("utf-8", "ignore")[:500]
            finally:
                response.close()
                client.close()
            raise CrawUpstreamError(self.name, response.status_code, detail)
        return CrawChatStream(self.name, client, response)

    def chat_completions_stream(
        self,
        messages: list[dict],
        identity: Optional[CrawIdentity] = None,
        session_code: Optional[str] = None,
    ) -> Iterator[dict]:
        """流式转发（``open_chat_stream`` 的迭代包装，句柄随迭代结束关闭）。"""
        with self.open_chat_stream(messages, identity=identity, session_code=session_code) as stream:
            yield from stream

    @staticmethod
    def iter_sse_chunks(lines: Iterator[str], backend: str = "") -> Iterator[dict]:
        """解析 OpenAI 兼容 SSE 行流（严格模式）。

        产出 ``data:`` JSON chunk，遇 ``[DONE]`` 正常结束。两类违例即抛
        ``CrawStreamProtocolError``，不静默吞掉当成功：

        - ``data:`` 行不是合法 JSON（解析错误不再跳过）；
        - EOF 时未见 ``[DONE]`` 终止标志（空流 / 截断流）。
        """
        done_seen = False
        for raw in lines:
            if not raw:
                continue
            line = raw.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                done_seen = True
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError as exc:
                raise CrawStreamProtocolError(backend, f"SSE data 行不是合法 JSON: {data[:120]!r}") from exc
            yield chunk
        if not done_seen:
            raise CrawStreamProtocolError(backend, "上游流在 [DONE] 终止标志前结束（空流或截断）")

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
    """craw 上游返回非 2xx（携带截断后的响应详情，不含凭证）。

    ``detail`` 是上游响应体片段，只应进服务端日志；发给客户端的错误消息
    用 ``client_message``（仅 backend + 状态码），避免泄露内部错误页内容。
    """

    def __init__(self, backend: str, status_code: int, detail: str) -> None:
        self.backend = backend
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"craw backend {backend} upstream {status_code}: {detail}")

    @property
    def client_message(self) -> str:
        return f"craw backend {self.backend} upstream {self.status_code}"


class CrawStreamProtocolError(RuntimeError):
    """craw 上游 SSE 流违反协议（畸形 data 行 / 未见 ``[DONE]`` 即 EOF）。

    ``reason`` 可能含上游数据片段，只应进服务端日志；客户端错误消息用
    ``client_message``。
    """

    def __init__(self, backend: str, reason: str) -> None:
        self.backend = backend
        self.reason = reason
        super().__init__(f"craw backend {backend} stream protocol error: {reason}")

    @property
    def client_message(self) -> str:
        return f"craw backend {self.backend} 流式响应违例（详情见服务端日志）"
