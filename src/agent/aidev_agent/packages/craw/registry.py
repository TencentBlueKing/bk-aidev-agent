# -*- coding: utf-8 -*-
"""Craw 后端协议与注册中心。

Craw = CLI 形态 Agent 内核（OpenClaw / Hermes / …）在本机（localhost /
同容器 / 同 Pod）暴露的 OpenAI 兼容 API 服务。本注册中心以内核名为 key
管理后端实现类：

- 注册：``craw_backend_registry.register("openclaw", OpenClawBackend)``
- 取实现类：``craw_backend_registry.must_get(name)``；
- 取已装配实例（env 装配连接参数）：``get_backend(name)``。

默认后端（openclaw / hermes）的注册在包 ``__init__.py`` 完成 wiring，
避免本模块反向依赖具体实现。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Iterator, Optional, Protocol, Type, runtime_checkable

from aidev_agent.utils.factory import SimpleFactory

if TYPE_CHECKING:
    from aidev_agent.packages.craw.base import CrawChatStream, CrawIdentity


@runtime_checkable
class CrawBackendProtocol(Protocol):
    """Craw 后端协议。

    声明包内实际消费的**全部**成员（``agent.py`` / ``takeover.py`` /
    ``sync.py`` 会访问的属性与方法）；由 ``BaseCrawBackend`` 提供通用实现，
    各内核子类只覆写差异点。自定义后端缺任一成员即不满足协议，接管入口
    在改动 registry 前完成校验。
    """

    name: str
    default_model: str
    # 装配后连接参数（takeover 日志 / agent 非流式回包引用）
    api_url: str
    api_key: str
    model: str
    timeout: float
    transport: str

    def build_headers(
        self, identity: Optional["CrawIdentity"] = None, session_code: Optional[str] = None
    ) -> dict[str, str]:
        """构造请求头（含 Bearer 认证与用户身份隔离头，原始 token 不入日志）。"""
        ...

    def chat_completions(
        self,
        messages: list[dict],
        identity: Optional["CrawIdentity"] = None,
        session_code: Optional[str] = None,
    ) -> dict:
        """非流式转发 ``POST /v1/chat/completions``，返回 OpenAI 兼容响应 dict。"""
        ...

    def chat_completions_stream(
        self,
        messages: list[dict],
        identity: Optional["CrawIdentity"] = None,
        session_code: Optional[str] = None,
    ) -> Iterator[dict]:
        """流式转发，逐个产出 OpenAI 兼容 SSE chunk dict（已解析 ``data:`` 行）。"""
        ...

    def open_chat_stream(
        self,
        messages: list[dict],
        identity: Optional["CrawIdentity"] = None,
        session_code: Optional[str] = None,
    ) -> "CrawChatStream":
        """打开流式 chat，返回可关闭句柄（``stop()`` 跨线程中断阻塞读取用）。"""
        ...

    def delta_text(self, chunk: dict) -> str:
        """从流式 chunk 提取文本增量（无则空串）。"""
        ...

    def message_text(self, body: dict) -> str:
        """从非流式响应提取文本内容（无则空串）。"""
        ...

    def health(self) -> dict:
        """健康探测，返回 ``{"ok": bool, "status_code": int | None, "latency_ms": float, ...}``。"""
        ...


craw_backend_registry: SimpleFactory[str, Type[CrawBackendProtocol]] = SimpleFactory("craw_backend")

# 后端选择 env：值为已注册的内核名（openclaw / hermes / …）
BACKEND_ENV = "BKAI_CRAW_BACKEND"


def get_backend(name: Optional[str] = None, **kwargs) -> CrawBackendProtocol:
    """按名取已装配的后端实例。

    :param name: 内核名；缺省读 env ``BKAI_CRAW_BACKEND``。
    :param kwargs: 透传给后端构造函数（api_url / api_key / model / timeout），
        缺省项由后端自身的 env 回落链装配。
    :raises RuntimeError: 未注册的内核名（``must_get`` 语义）。
    """
    final_name = (name or os.getenv(BACKEND_ENV) or "").strip().lower()
    backend_cls = craw_backend_registry.must_get(final_name)
    return backend_cls(**kwargs)
