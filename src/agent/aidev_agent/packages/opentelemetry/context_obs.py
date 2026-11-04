# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

上下文装配与压缩的可观测性埋点。

本模块只承载观测逻辑：装配链路与压缩链路各调用一次入口，不感知 span 细节。

- ``observe_assembly``：装配 span（``context.assembly``）的生命周期与属性聚合；
- ``observe_compression_call``：每次压缩 LLM 调用的 span（``context.compression.generate``）；

全部埋点 fail-open：仅隔离观测故障，业务异常原样传播。
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.utils import function_calling

try:
    from opentelemetry import context as otel_context
    from opentelemetry.trace import SpanKind

    from .callback_handler import BkAidevAgentCallbackHandler
except ImportError:  # OpenTelemetry 是可选 SDK extra。
    SpanKind = None
    BkAidevAgentCallbackHandler = None

logger = logging.getLogger(__name__)

ASSEMBLY_SPAN_NAME = "context.assembly"
COMPRESSION_SPAN_NAME = "context.compression.generate"

# 工具 schema 序列化长度的观测缓存键（写入 ctx.assembly_cache，不写业务字段）
_TOOL_SCHEMA_CACHE_KEY = "context_obs_tool_schema_chars"

_HANDLER_CONTEXT_KEY = "aidev_context_compression_handler"


# ============================================================================
# 字符度量
# ============================================================================
@dataclass
class ContextChars:
    """一次装配的字符度量（Unicode 码点数）。图片字符单列，不计入 total。"""

    total: int = 0
    system_prompt: int = 0
    conversation_history: int = 0
    agent_scratchpad: int = 0
    knowledge: int = 0
    user_query: int = 0
    tool_definitions: int = 0
    image_chars: int = 0


def _text_len(value: Any) -> int:
    if value is None:
        return 0
    return len(value) if isinstance(value, str) else len(str(value))


def _content_len(content: Any) -> int:
    """文本 content 的长度：str 取码点数，列表只累加 text 块（图片/附件块不计）。"""
    if not isinstance(content, list):
        return _text_len(content)
    total = 0
    for block in content:
        if isinstance(block, str):
            total += len(block)
        elif isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            total += len(block["text"])
    return total


def _block_payload_text(block: dict) -> str:
    """取图片块承载的字符串（URL 或 base64 原文），无 payload 时返回空字符串。"""
    for key in ("image_url", "url", "data", "base64", "source"):
        value = block.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for inner_key in ("url", "data", "base64"):
                inner = value.get(inner_key)
                if isinstance(inner, str):
                    return inner
    return ""


def _tool_calls_len(message: Any) -> int:
    """assistant 消息 tool_calls 参数 JSON 的字符数。"""
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        additional_kwargs = getattr(message, "additional_kwargs", None) or {}
        if isinstance(additional_kwargs, dict):
            tool_calls = additional_kwargs.get("tool_calls") or []
    total = 0
    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        args = call.get("args")
        if args is None:
            function = call.get("function")
            if isinstance(function, dict):
                args = function.get("arguments")
        if isinstance(args, str):
            total += len(args)
            continue
        try:
            total += len(json.dumps(args, ensure_ascii=False, default=str))
        except Exception:  # noqa: BLE001
            total += len(str(args))
    return total


def _message_text_chars(message: Any) -> int:
    """单条消息的文本字符数：content 文本块 + tool_calls 参数 JSON。"""
    return _content_len(getattr(message, "content", None)) + _tool_calls_len(message)


def _message_chars(message: Any) -> tuple[int, int]:
    """单条消息的 (文本字符数, 图片字符数)。"""
    content = getattr(message, "content", None)
    image_chars = 0
    if isinstance(content, list):
        image_chars = sum(
            len(_block_payload_text(block))
            for block in content
            if isinstance(block, dict) and block.get("type") in ("image_url", "image", "input_image")
        )
    return _message_text_chars(message), image_chars


def _messages_text_chars(messages: Any) -> int:
    """消息列表的文本字符合计（不含图片/附件）。"""
    if not isinstance(messages, list):
        return 0
    return sum(len(message) if isinstance(message, str) else _message_text_chars(message) for message in messages)


def _scratchpad_chars(scratchpad: Any) -> int:
    """scratchpad（工具消息）字符数：消息列表按消息口径累加，其余取文本长度。"""
    if isinstance(scratchpad, list):
        return _messages_text_chars(scratchpad)
    return _text_len(scratchpad)


def _tool_definitions_chars(ctx: Any, tools: List[Any]) -> int:
    """工具 schema 的 JSON 序列化字符数之和，按工具名元组缓存在 assembly_cache。"""
    if not tools:
        return 0

    cache = getattr(ctx, "assembly_cache", None)
    cache_map: Optional[dict] = None
    cache_key: Optional[tuple] = None
    if isinstance(cache, dict):
        stored = cache.get(_TOOL_SCHEMA_CACHE_KEY)
        if isinstance(stored, dict):
            cache_map = stored
        else:
            cache_map = {}
            cache[_TOOL_SCHEMA_CACHE_KEY] = cache_map
        cache_key = tuple(str(getattr(tool, "name", "")) for tool in tools)

    if cache_map is not None and cache_key is not None and cache_key in cache_map:
        return int(cache_map[cache_key])

    total = 0
    for tool in tools:
        try:
            schema = function_calling.convert_to_openai_tool(tool)
            total += len(json.dumps(schema, ensure_ascii=False, default=str))
        except Exception:  # noqa: BLE001
            logger.debug("工具 schema 序列化失败，跳过该工具的字符统计", exc_info=True)
    if cache_map is not None and cache_key is not None:
        cache_map[cache_key] = total
    return total


def measure_context(ctx: Any, *, query_text: Any = None) -> Optional[ContextChars]:
    """统计一次装配的字符度量，失败返回 None（fail-open）。

    - ``total``：最终提交请求的文本块 + assistant tool_calls 参数 JSON + 工具 schema JSON；
    - ``conversation_history`` / ``agent_scratchpad`` / ``knowledge`` / ``user_query`` / ``tool_definitions``
      按变量来源归因：conversation_history 来自 chat_history，agent_scratchpad 来自 agent_scratchpad；
    - ``system_prompt`` 为残差。残差为负时依次从 knowledge / conversation_history / agent_scratchpad /
      user_query / tool_definitions 扣减，保证六项之和恒等于 total 且均非负。
    """
    if SpanKind is None:
        return None
    return _observe(_measure_context, ctx, query_text)


def _measure_context(ctx: Any, query_text: Any) -> ContextChars:
    messages = getattr(ctx, "messages", None) or []
    total_text = 0
    image_chars = 0
    for message in messages:
        chars, image_len = _message_chars(message)
        total_text += chars
        image_chars += image_len

    tool_definitions = _tool_definitions_chars(ctx, list(getattr(ctx, "tools", None) or []))
    total = total_text + tool_definitions

    variables = getattr(ctx, "variables", None) or {}
    attributed = {
        "conversation_history": _messages_text_chars(variables.get("chat_history")),
        "agent_scratchpad": _scratchpad_chars(variables.get("agent_scratchpad")),
        "knowledge": _text_len(variables.get("context")) if variables.get("context") else 0,
        "user_query": _text_len(query_text),
        "tool_definitions": tool_definitions,
    }
    deficit = max(0, sum(attributed.values()) - total)
    for key in ("knowledge", "conversation_history", "agent_scratchpad", "user_query", "tool_definitions"):
        deduct = min(attributed[key], deficit)
        attributed[key] -= deduct
        deficit -= deduct
    system_prompt = total - sum(attributed.values())

    return ContextChars(
        total=total,
        system_prompt=system_prompt,
        image_chars=image_chars,
        **attributed,
    )


# ============================================================================
# Span 写入辅助
# ============================================================================
def _resolve_handler(ctx: Any) -> Optional[BkAidevAgentCallbackHandler]:
    """从 ctx.config.callbacks 中找出本仓的 callback handler；未开启 tracing 时返回 None。"""
    if BkAidevAgentCallbackHandler is None:
        return None
    config = getattr(ctx, "config", None)
    if not isinstance(config, dict):
        return None
    callbacks = config.get("callbacks")
    if callbacks is None:
        return None
    if isinstance(callbacks, (list, tuple)):
        handlers = callbacks
    elif hasattr(callbacks, "handlers"):
        handlers = callbacks.handlers
    else:
        handlers = [callbacks]
    for handler in handlers or []:
        if isinstance(handler, BkAidevAgentCallbackHandler):
            if not getattr(handler, "enabled", True) or not getattr(handler, "enable_traces", True):
                return None
            return handler
    return None


def resolve_model_name(llm: Any) -> Optional[str]:
    """取模型名用于 ``gen_ai.request.model``，取不到返回 None（属性缺省）。"""
    for source in (llm, getattr(llm, "runnable", None)):
        for attr in ("model_name", "model", "model_id"):
            value = getattr(source, attr, None)
            if isinstance(value, str) and value:
                return value
    return None


def _response_usage(response: Any) -> Optional[Dict[str, int]]:
    """从模型响应中提取 usage（可得时）。"""
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    if not isinstance(usage, dict):
        return None
    return {key: int(usage[key]) for key in ("input_tokens", "output_tokens") if usage.get(key) is not None} or None


# ============================================================================
# 装配观测器
# ============================================================================
@dataclass
class AssemblyObservation:
    """一次装配的字符与预算观测；属性在装配结束时写入 span。"""

    token_limit: Optional[int] = None
    token_margin: Optional[int] = None
    span: Any = None
    chars: Optional[ContextChars] = None

    def record_chars(self, chars: Optional[ContextChars]) -> None:
        if chars is not None:
            self.chars = chars

    def build_attributes(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        chars = self.chars
        if chars is not None:
            attrs.update(
                {
                    "context.chars.total": int(chars.total),
                    "context.chars.system_prompt": int(chars.system_prompt),
                    "context.chars.conversation_history": int(chars.conversation_history),
                    "context.chars.agent_scratchpad": int(chars.agent_scratchpad),
                    "context.chars.knowledge": int(chars.knowledge),
                    "context.chars.user_query": int(chars.user_query),
                    "context.chars.tool_definitions": int(chars.tool_definitions),
                    "context.chars.image": int(chars.image_chars),
                }
            )
        # 预算按 token 原值上报；未配置时不写（区别于预算为 0）
        if self.token_limit is not None:
            attrs["context.budget.token_limit"] = int(self.token_limit)
        if self.token_margin is not None:
            attrs["context.budget.token_margin"] = int(self.token_margin)

        return attrs


def _observe(operation, *args, **kwargs):
    """只在观测操作边界隔离故障，不包裹业务调用。"""
    try:
        return operation(*args, **kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("上下文观测失败，埋点降级", exc_info=True)
        return None


def _write_attributes(span: Any, attributes) -> None:
    for key, value in attributes().items():
        if value is not None:
            span.set_attribute(key, value)


@contextmanager
def _custom_span(handler: Any, name: str, *, attributes, **kwargs):
    """创建 span 并在结束前写入属性；fail-open 由 create_custom_span 保证。

    ``attributes`` 是回调而非 dict，不走 create_custom_span 的同名参数：该参数只在创建 span 时
    写入一次，而字符度量、压缩产出和 usage 要等业务代码执行后才可得。回调在 finally 中求值，
    业务抛异常时已记录的属性同样会上报。
    """
    with handler.create_custom_span(name, **kwargs) as span:
        try:
            yield span
        finally:
            if span is not None:
                _observe(_write_attributes, span, attributes)


@contextmanager
def observe_assembly(
    ctx: Any,
    *,
    token_limit: Optional[int] = None,
    token_margin: Optional[int] = None,
) -> Iterator[Optional[AssemblyObservation]]:
    """装配观测；tracing 关闭或创建失败时 yield None。"""
    if SpanKind is None:
        yield None
        return
    handler = _resolve_handler(ctx)
    # handler 为 None 也写入 context，遮蔽外层装配的 handler
    context_token = otel_context.attach(otel_context.set_value(_HANDLER_CONTEXT_KEY, handler))
    try:
        if handler is None:
            yield None
            return
        observation = AssemblyObservation(token_limit=token_limit, token_margin=token_margin)
        with _custom_span(
            handler, ASSEMBLY_SPAN_NAME, attributes=observation.build_attributes, kind=SpanKind.INTERNAL
        ) as span:
            observation.span = span
            yield observation if span is not None else None
    finally:
        otel_context.detach(context_token)


# ============================================================================
# 压缩调用观测
# ============================================================================
@dataclass
class CompressionCall:
    """单次压缩 LLM 调用的观测句柄。"""

    module: str
    model: Optional[str] = None
    input_chars: int = 0
    output_chars: Optional[int] = field(default=None, init=False)
    usage: Optional[Dict[str, int]] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.input_chars = max(0, int(self.input_chars or 0))

    def set_output(self, chars: int, response: Any = None) -> None:
        """记录压缩产出字符数；有模型响应时可一并带上 usage。"""
        try:
            self.output_chars = max(0, int(chars))
        except (TypeError, ValueError):
            self.output_chars = None
        self.usage = _observe(_response_usage, response)

    def build_attributes(self) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {
            "context.compression.module": self.module,
            "context.compression.input_chars": self.input_chars,
        }
        if self.model:
            attrs["gen_ai.request.model"] = self.model
        if self.output_chars is not None:
            attrs["context.compression.output_chars"] = self.output_chars
        if self.usage:
            for key, value in self.usage.items():
                attrs[f"gen_ai.usage.{key}"] = value
        return attrs


@contextmanager
def observe_compression_call(
    *,
    module: str,
    model: Optional[str] = None,
    input_chars: int = 0,
) -> Iterator[CompressionCall]:
    """每次调用复用 custom span，默认以当前 OTel context 为父。"""
    call = CompressionCall(module=module, model=model, input_chars=input_chars)
    handler = otel_context.get_value(_HANDLER_CONTEXT_KEY) if SpanKind is not None else None
    if handler is None:
        yield call
        return

    with _custom_span(
        handler,
        COMPRESSION_SPAN_NAME,
        attributes=call.build_attributes,
        kind=SpanKind.CLIENT,
    ):
        yield call
