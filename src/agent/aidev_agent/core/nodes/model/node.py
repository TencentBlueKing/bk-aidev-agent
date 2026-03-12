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

import logging
from typing import Annotated, Any, Dict, List

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AnyMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph._internal._runnable import RunnableCallable
from langgraph.graph.message import add_messages
from langgraph.store.base import BaseStore
from typing_extensions import Required, TypedDict

from aidev_agent.packages.langchain_core.output_parsers import StructuredOutputToToolMessageParser

from .basic_middleware import (
    BaseVariablesMiddleware,
    DeepSeekR1VariablesMiddleware,
    SpecialVariablesMiddleware,
)
from .context_assembly import ContextAssembly
from .prompt_middleware import (
    BeijingTimeMiddleware,
    DecisionSystemMiddleware,
    HistorySystemPromptMiddleware,
    NoSystemInThinkingMiddleware,
    RoleDefinitionMiddleware,
    StructuredChatFormatMiddleware,
)
from .pydantic_models import ModelNodeSettings, ProcessorContext
from .token_compression import (
    ChatHistoryCompressionMiddleware,
    KnowledgeCompressionMiddleware,
    KnowledgeCompressor,
    ToolOutputCompressor,
    ToolOutputLengthCompressionMiddleware,
    ToolOutputTokenCompressionMiddleware,
)

logger = logging.getLogger(__name__)


class ModelState(TypedDict, total=False):
    """模型节点的类型安全状态定义。

    使用 TypedDict 提供类型安全的状态访问，与 LangChain AgentState 模式保持一致。

    Attributes:
        messages: 消息列表，使用 add_messages 注解确保消息正确合并
    """

    messages: Required[Annotated[list[AnyMessage], add_messages]]


def _extract_query_text_and_images(query: Any) -> tuple[Any, list[dict[str, Any]]]:
    """从 query 中提取文本和图片（OpenAI-style content list）。"""

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


def _prepare_model_chain(
    *,
    llm: BaseChatModel,
    context_assembly: ContextAssembly,
    use_structured_response: bool,
    enable_parallel_tool_calls: bool,
    state: ModelState,
    config: RunnableConfig,
    store: BaseStore,
) -> tuple[Runnable, list[BaseMessage]]:
    """
    准备模型推理所需的 LLM chain 和渲染后的 messages。

    抽取 model_node 和 amodel_node 的公共逻辑，包括：
    - 获取工具列表
    - 获取 prompt 模板
    - 准备上下文变量
    - 渲染 prompt -> messages
    - 构建 LLM chain（不含 prompt）

    Args:
        llm: 语言模型
        context_assembly: 上下文组件实例
        use_structured_response: 是否使用结构化输出模式
        enable_parallel_tool_calls: 是否启用并行工具调用
        state: 状态字典
        config: Runnable 配置
        store: LangGraph Store

    Returns:
        tuple: (llm_chain, messages)
            - llm_chain: LLM chain（可能包含 parser 或已绑定工具）
            - messages: 渲染后的消息列表（可观测点）
    """
    # 创建共享的 ProcessorContext（整个 node 执行过程中复用）
    ctx = ProcessorContext(
        state=state,
        config=config,
        store=store,
        llm=llm,
    )

    # 使用 ContextAssembly 获取工具
    tools = context_assembly.get_choice_tools(ctx)
    # 使用 ContextAssembly 选择 prompt 模板（会设置 ctx.chat_prompt_template）
    chat_prompt_template = context_assembly.get_chat_prompt_template(ctx)
    # 使用 ContextAssembly 准备上下文变量
    context_variables = context_assembly.get_chat_prompt_variables(ctx)
    image_contents: list[dict[str, Any]] = []
    query, image_contents = _extract_query_text_and_images(context_variables.get("query"))
    if image_contents:
        context_variables = {**context_variables, "query": query}

    # 渲染 prompt -> messages（可观测点）
    prompt_value = chat_prompt_template.invoke(context_variables, config=config)
    messages: list[BaseMessage] = prompt_value.to_messages()
    _attach_images_to_last_human_message(messages, image_contents)

    # 根据模式构建不同的 llm_chain（不含 prompt）
    if use_structured_response:
        # 创建结构化输出解析器（用于 use_structured_response 模式）
        # 传递 llm 以支持 DeepSeek R1 等模型的特殊处理
        # 注意：不传递 tools，工具存在性校验由 ToolNode 负责
        tool_message_parser = StructuredOutputToToolMessageParser(
            llm=llm,
            enable_parallel_tool_calls=enable_parallel_tool_calls,
        )
        # 结构化输出模式：llm 输出经过 parser 转换为带 tool_calls 的 AIMessage
        llm_chain: Runnable = llm | tool_message_parser
        # 添加工具描述到上下文变量
    else:
        # 原生工具调用模式：使用 bind_tools 绑定工具
        llm_chain = llm.bind_tools(tools) if tools else llm

    return llm_chain, messages


def build_model_node(
    *,
    llm: BaseChatModel,
    non_thinking_llm: BaseChatModel = None,
    tools: List[BaseTool],
    node_options: ModelNodeSettings | None = None,
) -> RunnableCallable:
    """创建标准 QA 场景的模型节点。

    Args:
        llm: 语言模型
        non_thinking_llm: 辅助模型
        tools: 工具列表（全量工具，内部会根据 state 决策筛选）
        node_options: 模型节点选项（可选，不传则使用默认值）

    Returns:
        RunnableCallable，包含同步和异步两个节点函数
    """

    if node_options is None:
        node_options = ModelNodeSettings()

    use_structured_response = node_options.use_structured_response
    enable_parallel_tool_calls = node_options.enable_parallel_tool_calls

    # NOTE: `chat_prompt_templates` is kept for backwards compatibility but is no longer used.

    # 在内部构建 ContextAssembly，并手动加载所有必需的中间件
    context_assembly = ContextAssembly(tools=tools)
    # 加载和构造 prompt-template 相关的中间件
    context_assembly.add_middleware(
        "template",
        StructuredChatFormatMiddleware(use_structured_response=use_structured_response),
    )
    context_assembly.add_middleware("template", RoleDefinitionMiddleware())
    context_assembly.add_middleware(
        "template",
        DecisionSystemMiddleware(enable_query_clarification=node_options.enable_query_clarification),
    )
    context_assembly.add_middleware("template", BeijingTimeMiddleware())
    context_assembly.add_middleware("template", NoSystemInThinkingMiddleware())
    context_assembly.add_middleware("template", HistorySystemPromptMiddleware())
    # 加载和构造 prompt-variables 相关的中间件
    context_assembly.add_middleware("variable", BaseVariablesMiddleware())
    context_assembly.add_middleware(
        "variable",
        SpecialVariablesMiddleware(
            use_structured_response=use_structured_response,
            use_general_knowledge_on_miss=node_options.use_general_knowledge_on_miss,
            rejection_message=node_options.rejection_message,
            role_prompt=node_options.role_prompt,
            enable_parallel_tool_calls=enable_parallel_tool_calls,
        ),
    )
    # 知识库的压缩器
    context_assembly.add_middleware(
        "variable",
        KnowledgeCompressionMiddleware(
            knowledge_compressor_func=KnowledgeCompressor(non_thinking_llm),
            token_limit=node_options.token_limit,
            token_margin=node_options.token_margin,
        ),
    )
    # 基于字符长度阈值的工具输出压缩
    tool_output_compressor = ToolOutputCompressor(
        non_thinking_llm, compressor_type=node_options.tool_output_compressor_type
    )
    context_assembly.add_middleware(
        "variable",
        ToolOutputLengthCompressionMiddleware(
            tool_output_compress_thrd=node_options.tool_output_compress_thrd,
            tool_output_compressor_func=tool_output_compressor,
        ),
    )
    # 基于 Token 超限的工具输出压缩
    context_assembly.add_middleware(
        "variable",
        ToolOutputTokenCompressionMiddleware(
            tool_output_compressor_func=tool_output_compressor,
            token_limit=node_options.token_limit,
            token_margin=node_options.token_margin,
        ),
    )
    context_assembly.add_middleware(
        "variable",
        DeepSeekR1VariablesMiddleware(use_deepseek_r1_models_process=node_options.use_deepseek_r1_models_process),
    )

    context_assembly.add_middleware(
        "variable",
        ChatHistoryCompressionMiddleware(
            token_limit=node_options.token_limit,
            token_margin=node_options.token_margin,
        ),
    )

    def model_node(
        state: ModelState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> Dict[str, Any]:
        """
        同步模型推理节点。

        - 根据 state 中的 decision 选择合适的 ReAct Prompt
        - 支持两种模式：
          - use_structured_response=True: 使用结构化输出 + tool_message_parser
          - use_structured_response=False: 使用原生 function calling (bind_tools)

        Args:
            state: 类型安全的状态字典
            config: Runnable 配置
            store: LangGraph Store

        Returns:
            包含 messages 的字典
        """
        llm_chain, messages = _prepare_model_chain(
            llm=llm,
            context_assembly=context_assembly,
            use_structured_response=use_structured_response,
            enable_parallel_tool_calls=enable_parallel_tool_calls,
            state=state,
            config=config,
            store=store,
        )

        # 调用 LLM chain
        response = llm_chain.invoke(messages, config=config)
        return {"messages": [response]}

    async def amodel_node(
        state: ModelState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> Dict[str, Any]:
        """
        异步模型推理节点。

        - 根据 state 中的 decision 选择合适的 ReAct Prompt
        - 支持两种模式：
          - use_structured_response=True: 使用结构化输出 + tool_message_parser
          - use_structured_response=False: 使用原生 function calling (bind_tools)

        Args:
            state: 类型安全的状态字典
            config: Runnable 配置
            store: LangGraph Store

        Returns:
            包含 messages 的字典
        """
        llm_chain, messages = _prepare_model_chain(
            llm=llm,
            context_assembly=context_assembly,
            use_structured_response=use_structured_response,
            enable_parallel_tool_calls=enable_parallel_tool_calls,
            state=state,
            config=config,
            store=store,
        )

        # 异步调用 LLM chain
        response = await llm_chain.ainvoke(messages, config=config)
        return {"messages": [response]}

    return RunnableCallable(model_node, amodel_node, trace=True)
