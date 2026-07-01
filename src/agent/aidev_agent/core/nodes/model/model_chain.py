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
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool
from openai import RateLimitError
from tenacity import RetryError

from aidev_agent.config import settings
from aidev_agent.packages.langchain_core.output_parsers import StructuredOutputToToolMessageParser

from .pydantic_models import (
    RETRYABLE_EXCEPTIONS,
    ProcessorContext,
    RetryableRateLimitError,
)
from .quality_gate import QualityGate
from .utils import promote_plain_text_tool_call_message

logger = logging.getLogger(__name__)


def _promote_message(message: AnyMessage, allowed_tool_names: set[str]) -> AnyMessage:
    """尝试将消息中的纯文本工具调用提升为原生 tool_calls。"""
    if not isinstance(message, AIMessage):
        return message
    return promote_plain_text_tool_call_message(message, allowed_tool_names)


def _extract_query_text_and_images(query: Any) -> tuple[Any, list[dict[str, Any]]]:
    """从 query 中提取文本和图片（OpenAI 风格内容列表）。"""

    if not isinstance(query, list):
        return query, []

    text_parts: list[str] = []
    image_contents: list[dict[str, Any]] = []
    for item in query:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        elif item_type == "image_url":
            image_contents.append(item)

    return "\n".join(text_parts), image_contents


def _attach_images_to_last_human_message(messages: list[BaseMessage], image_contents: list[dict[str, Any]]) -> None:
    """将图片内容挂载到最后一条 HumanMessage，避免丢失多模态输入。"""

    if not image_contents:
        return

    for idx in range(len(messages) - 1, -1, -1):
        if not isinstance(messages[idx], HumanMessage):
            continue

        human_message = messages[idx]
        rendered_text = human_message.content if isinstance(human_message.content, str) else ""
        multimodal_content: list[dict[str, Any]] = []
        if rendered_text:
            multimodal_content.append({"type": "text", "text": rendered_text})
        multimodal_content.extend(image_contents)
        messages[idx] = human_message.model_copy(update={"content": multimodal_content})
        return


def _build_effective_chain(
    *,
    llm: BaseChatModel,
    tools: list[BaseTool],
    use_structured_response: bool,
    enable_parallel_tool_calls: bool,
    use_tool_call_promotion: bool,
    max_tokens_override: int | None = None,
) -> Runnable:
    """从原始 LLM 构建可执行的 chain。

    根据模式标志绑定工具、结构化响应解析器、promotion 等，返回
    可直接调用的 Runnable。

    构建顺序：
    1. max_tokens 前置（消除两分支重复 bind）
    2. 无工具时直接返回 llm——StructuredOutputToToolMessageParser 的唯一
       作用是将 JSON 输出解析为 tool_calls，无工具时无意义
    3. structured / 非 structured 分支构建 chain
    4. promotion 统一加在末尾（两个分支一致）
    """
    # 1. max_tokens 前置
    if max_tokens_override:
        llm = llm.bind(max_tokens=max_tokens_override)

    # 2. 无工具 → 直接返回 llm
    #    StructuredOutputToToolMessageParser 的作用是把 JSON 输出解析为
    #    tool_calls；没有工具时 parser 无意义，无论 use_structured_response
    #    取值如何都应直接返回 llm。
    if not tools:
        return llm

    # 3. 构建 chain（tools 非空）
    if use_structured_response:
        chain = llm | StructuredOutputToToolMessageParser(
            llm=llm,
            enable_parallel_tool_calls=enable_parallel_tool_calls,
        )
    else:
        chain = llm.bind_tools(tools)

    # 4. promotion（两个分支统一加；无工具时已在上方提前返回）
    if use_tool_call_promotion:
        allowed_tool_names = {t.name for t in tools}
        chain = chain | RunnableLambda(lambda msg, _names=allowed_tool_names: _promote_message(msg, _names))
    return chain


def _exhaustion_fallback(ctx: ProcessorContext) -> ProcessorContext:
    """当所有重试耗尽时返回最后响应。"""
    return ctx


def _build_model_chain(
    *,
    llm,
    context_assembly,
    model_chain_config,
    quality_gate: QualityGate,
    use_structured_response: bool,
    enable_parallel_tool_calls: bool,
    use_tool_call_promotion: bool,
) -> Runnable:
    """构建共享的 LCEL 模型链。

    将原 _run_recovery_loop / _arun_recovery_loop 的 while 循环逻辑
    替换为 LCEL 管道：RunnableLambda 步骤 → RunnableRetry → RunnableWithFallbacks。

    Args:
        llm: 语言模型
        context_assembly: 上下文装配器
        model_chain_config: 模型链配置（max_empty_retries 等）
        quality_gate: 质量门禁实例（评估响应并决定恢复路由）
        use_structured_response: 是否使用结构化响应模式
        enable_parallel_tool_calls: 是否启用并行工具调用
        use_tool_call_promotion: 是否启用工具调用提升

    Returns:
        Runnable，支持 .invoke() 和 .ainvoke()
    """

    # ------------------------------------------------------------------
    # 内部函数：消息渲染（链头，D-07/D-08/D-09）
    # ------------------------------------------------------------------
    def _render_messages(ctx: ProcessorContext) -> ProcessorContext:
        """渲染 prompt 模板为消息列表，填入 ctx.messages (D-07/D-08)。

        复用入口 ctx（不构造临时 ProcessorContext——D-08）。原地变更
        ctx.messages 并返回同一对象，使重试边界重新执行时消息保留。
        """
        chat_prompt_template = context_assembly.get_chat_prompt_template(ctx)
        context_variables = context_assembly.get_chat_prompt_variables(ctx)
        image_contents: list[dict[str, Any]] = []
        query, image_contents = _extract_query_text_and_images(context_variables.get("query"))
        if image_contents:
            context_variables = {**context_variables, "query": query}
        prompt_value = chat_prompt_template.invoke(context_variables, config=ctx.config)
        messages: list[BaseMessage] = prompt_value.to_messages()
        _attach_images_to_last_human_message(messages, image_contents)
        ctx.messages = messages  # 原地变更 ctx，返回同一对象
        return ctx

    # ------------------------------------------------------------------
    # 内部函数：LLM 调用步骤
    # ------------------------------------------------------------------
    def _call_llm(ctx: ProcessorContext) -> ProcessorContext:
        """从原始 LLM 构建 chain 并调用，处理 RateLimitError。"""
        tools = context_assembly.get_choice_tools(ctx)
        effective_llm = _build_effective_chain(
            llm=llm,
            tools=tools,
            use_structured_response=use_structured_response,
            enable_parallel_tool_calls=enable_parallel_tool_calls,
            use_tool_call_promotion=use_tool_call_promotion,
            max_tokens_override=ctx.model_chain_state.max_tokens_override,
        )
        try:
            response = effective_llm.invoke(ctx.messages, config=ctx.config)
        except RateLimitError:
            if settings.LLM_RETRY_STRATEGY != "sdk":
                raise
            ctx.model_chain_state.empty_content_retries += 1
            logger.warning(
                "Rate limit error, waiting 60s before retry (%d/%d)",
                ctx.model_chain_state.empty_content_retries,
                ctx.model_chain_state.max_empty_retries,
            )
            if ctx.model_chain_state.empty_content_retries > ctx.model_chain_state.max_empty_retries:
                raise
            time.sleep(60)
            raise RetryableRateLimitError(ctx.response or AIMessage(content=""))
        ctx.response = response
        return ctx

    async def _acall_llm(ctx: ProcessorContext) -> ProcessorContext:
        """从原始 LLM 异步构建 chain 并调用，处理 RateLimitError。"""
        tools = context_assembly.get_choice_tools(ctx)
        effective_llm = _build_effective_chain(
            llm=llm,
            tools=tools,
            use_structured_response=use_structured_response,
            enable_parallel_tool_calls=enable_parallel_tool_calls,
            use_tool_call_promotion=use_tool_call_promotion,
            max_tokens_override=ctx.model_chain_state.max_tokens_override,
        )
        try:
            response = await effective_llm.ainvoke(ctx.messages, config=ctx.config)
        except RateLimitError:
            if settings.LLM_RETRY_STRATEGY != "sdk":
                raise
            ctx.model_chain_state.empty_content_retries += 1
            logger.warning(
                "Rate limit error, waiting 60s before retry (%d/%d)",
                ctx.model_chain_state.empty_content_retries,
                ctx.model_chain_state.max_empty_retries,
            )
            if ctx.model_chain_state.empty_content_retries > ctx.model_chain_state.max_empty_retries:
                raise
            await asyncio.sleep(60)
            raise RetryableRateLimitError(ctx.response or AIMessage(content=""))
        ctx.response = response
        return ctx

    # ------------------------------------------------------------------
    # 链组合：_render_messages（仅一次）| model_chain（含重试 + 回退）
    # ------------------------------------------------------------------
    # _render_messages 不参与重试——消息渲染是幂等的、只应跑一次，
    # 重试时只需重建 model_chain（llm | capture | quality）。
    # with_fallbacks 也只包裹 model_chain——耗尽时返回最后响应。
    model_chain = RunnableLambda(_call_llm, _acall_llm) | RunnableLambda(quality_gate)
    # 用重试包装 — 捕获所有 RETRYABLE_EXCEPTIONS
    retryable_model_chain = model_chain.with_retry(
        retry_if_exception_type=RETRYABLE_EXCEPTIONS,
        stop_after_attempt=model_chain_config.max_empty_retries + 1,
        wait_exponential_jitter=True,
        exponential_jitter_params={"initial": 0.001},  # 最小化 — 实际等待在 Lambda 中
    )

    # _exhaustion_fallback 是模块级函数（无闭包依赖）

    model_chain = RunnableLambda(_render_messages) | retryable_model_chain.with_fallbacks(
        [RunnableLambda(_exhaustion_fallback)],
        exceptions_to_handle=(RetryError,),
    )

    return model_chain
