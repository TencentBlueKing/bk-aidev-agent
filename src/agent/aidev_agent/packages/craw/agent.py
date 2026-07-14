# -*- coding: utf-8 -*-
"""``CrawCompletionAgent``：把 AIDEV 的执行转发给本机 craw API 服务。

泛化自业务插件中既有的 OpenClaw / Hermes 转发 Agent 实现：连接细节
（URL / 认证 / 会话头）全部下沉到 ``CrawBackendProtocol``，本类只负责：

- 实现 SDK ``AgentProtocol``（``build`` / ``execute`` / ``stop``）；
- AIDEV 会话上下文 → OpenAI messages 装配；
- craw 的 OpenAI 兼容 SSE → AG-UI 事件翻译（经 ``event_handler`` 落库）；
- 用户身份装配（``CrawIdentity``：username + access_token 透传，做
  craw 侧每用户隔离的入口）。

注册接管见 ``takeover.enable_chat_takeover()``（env 门控，默认零影响）。
"""

from __future__ import annotations

import uuid
from logging import getLogger
from typing import Any, Callable, ClassVar, Generator, Optional

from ag_ui.core import (
    BaseEvent,
    EventType,
    RunErrorEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from ag_ui.encoder import EventEncoder
from pydantic import BaseModel, Field

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw.base import CrawIdentity, CrawUpstreamError
from aidev_agent.packages.craw.registry import CrawBackendProtocol, get_backend
from aidev_agent.services.agent.registry import AgentBuildContext
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.utils.event import RunId, emit_run_finished_event

logger = getLogger(__name__)

# AIDEV 会话角色 → OpenAI 角色（system 已在工厂层被滤除，activity/tool 不入消息）
_ROLE_MAP = {"user": "user", "assistant": "assistant", "ai": "assistant", "system": "system"}


def build_openai_messages(session_context_data: list[dict]) -> list[dict]:
    """AIDEV 会话上下文 → OpenAI messages（多段视觉内容仅取 text 段）。"""
    messages: list[dict] = []
    for item in session_context_data:
        role = _ROLE_MAP.get((item.get("role") or "").strip())
        if not role:
            continue
        content = item.get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
            )
        elif not isinstance(content, str):
            content = "" if content is None else str(content)
        if not content and role != "user":
            continue
        messages.append({"role": role, "content": content})
    return messages


class CrawCompletionAgent(BaseModel):
    """把执行委托给 craw 后端的 Chat Agent（注册时覆盖 ``AgentType.CHAT``）。"""

    agent_type: ClassVar[AgentType] = AgentType.CHAT

    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_code: Optional[str] = None
    username: Optional[str] = None
    session_context_data: list[dict] = Field(default_factory=list)
    event_handler: Optional[Callable[[BaseEvent], None]] = None

    backend: Optional[Any] = None  # CrawBackendProtocol（runtime_checkable Protocol，不做 pydantic 校验）
    identity: Optional[CrawIdentity] = None

    class Config:
        arbitrary_types_allowed = True

    # ---------------- 构建期（种子模式：cls() 空种子 → build(ctx) 原地装配） ----------------

    def build(self, ctx: AgentBuildContext) -> "CrawCompletionAgent":
        self.session_code = ctx.session_code
        self.username = ctx.username
        self.session_context_data = list(ctx.session_context_data or [])
        if ctx.event_handler is not None:
            self.event_handler = ctx.event_handler
        if self.backend is None:
            self.backend = get_backend()
        self.identity = self._resolve_identity(ctx)
        return self

    def _resolve_identity(self, ctx: AgentBuildContext) -> CrawIdentity:
        """装配用户身份：access_token 经 resource_manager 尽力取回（失败不阻塞对话）。"""
        access_token = ""
        try:
            if ctx.resource_manager is not None and ctx.username:
                access_token = ctx.resource_manager.resolve_access_token(ctx.username) or ""
        except Exception as exc:
            logger.warning("[CRAW] resolve_access_token failed (degrade to no identity token): %s", exc)
        return CrawIdentity(username=ctx.username or "", access_token=access_token)

    # ---------------- 运行时 ----------------

    def execute(self, execute_kwargs=None) -> Any:
        """流式返回 SSE 字符串生成器；非流式返回 ChatCompletionAgent 同构 dict。"""
        if bool(getattr(execute_kwargs, "stream", False)):
            thread = self.session_code or self.thread_id
            return GeneratorStreamingHelper(thread_id=thread).stream(self._run_stream())
        return self._run_sync()

    def stop(self) -> None:
        GeneratorStreamingHelper.cancel(self.session_code or self.thread_id)

    # ---------------- 事件分发 ----------------

    def _dispatch(self, event: BaseEvent) -> None:
        if self.event_handler:
            try:
                self.event_handler(event)
            except Exception as exc:  # 事件处理器异常不应中断流式响应
                logger.exception("[CRAW] event handler error: %s", exc)

    def _emit_finish(self, run_id: str) -> Generator[str, None, None]:
        yield emit_run_finished_event(thread_id=self.thread_id, run_id=run_id, event_handler=self._dispatch)

    def _emit_error_and_finish(self, encoder: EventEncoder, run_id: str, message: str) -> Generator[str, None, None]:
        error_event = RunErrorEvent(type=EventType.RUN_ERROR, message=message)
        self._dispatch(error_event)
        yield encoder.encode(error_event)
        yield from self._emit_finish(run_id)

    def _emit_text_end(self, encoder: EventEncoder, message_id: str) -> Generator[str, None, None]:
        end_event = TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=message_id)
        self._dispatch(end_event)
        yield encoder.encode(end_event)

    # ---------------- 流式：转发 craw + 翻译成 AG-UI 文本事件 ----------------

    def _run_stream(self) -> Generator[str, None, None]:
        encoder = EventEncoder()
        run_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        thread = self.session_code or self.thread_id
        backend: CrawBackendProtocol = self.backend

        started = RunStartedEvent(type=EventType.RUN_STARTED, thread_id=self.thread_id, run_id=run_id)
        self._dispatch(started)
        yield encoder.encode(started)

        if backend is None:
            yield from self._emit_error_and_finish(encoder, run_id, "craw backend 未装配（检查 BKAI_CRAW_BACKEND）")
            return

        text_open = False
        try:
            chunks = backend.chat_completions_stream(
                build_openai_messages(self.session_context_data),
                identity=self.identity,
                session_code=self.session_code,
            )
            for chunk in chunks:
                if GeneratorStreamingHelper.is_cancelled(thread):
                    if text_open:
                        yield from self._emit_text_end(encoder, message_id)
                    yield emit_run_finished_event(
                        thread_id=self.thread_id, run_id=RunId.CANCELLED, event_handler=self._dispatch
                    )
                    return
                piece = backend.delta_text(chunk)
                if not piece:
                    continue
                if not text_open:
                    start_event = TextMessageStartEvent(
                        type=EventType.TEXT_MESSAGE_START, message_id=message_id, role="assistant"
                    )
                    self._dispatch(start_event)
                    yield encoder.encode(start_event)
                    text_open = True
                content_event = TextMessageContentEvent(
                    type=EventType.TEXT_MESSAGE_CONTENT, message_id=message_id, delta=piece
                )
                self._dispatch(content_event)
                yield encoder.encode(content_event)
            if text_open:
                yield from self._emit_text_end(encoder, message_id)
            yield from self._emit_finish(run_id)
        except CrawUpstreamError as exc:
            logger.warning("[CRAW] upstream error: %s", exc)
            if text_open:
                yield from self._emit_text_end(encoder, message_id)
            yield from self._emit_error_and_finish(encoder, run_id, str(exc))
        except Exception as exc:
            logger.exception("[CRAW] stream forward error: %s", exc)
            if text_open:
                yield from self._emit_text_end(encoder, message_id)
            yield from self._emit_error_and_finish(encoder, run_id, f"转发 craw({backend.name}) 失败: {exc}")

    # ---------------- 非流式：转发 craw + 适配回 ChatCompletionAgent 形状 ----------------

    def _run_sync(self) -> dict:
        backend: CrawBackendProtocol = self.backend
        if backend is None:
            raise RuntimeError("craw backend 未装配（检查 BKAI_CRAW_BACKEND）")
        body = backend.chat_completions(
            build_openai_messages(self.session_context_data),
            identity=self.identity,
            session_code=self.session_code,
        )
        content = backend.message_text(body)
        # 与 ChatCompletionAgent._execute 非流式返回同构 → save_ai_response 可直接取 choices[0].delta.content
        return {
            "choices": [{"delta": {"role": "assistant", "content": content}}],
            "model": body.get("model", backend.model),
            "id": body.get("id", str(uuid.uuid4())),
            "reference_doc": [],
        }
