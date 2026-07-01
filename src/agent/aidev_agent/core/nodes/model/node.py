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
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph._internal._runnable import RunnableCallable
from langgraph.graph.message import add_messages
from langgraph.store.base import BaseStore
from typing_extensions import Required, TypedDict

from .basic_middleware import (
    BaseVariablesMiddleware,
    DeepSeekR1VariablesMiddleware,
    SpecialVariablesMiddleware,
    SpecialVariablesPostMiddleware,
)
from .context_assembly import ContextAssembly
from .model_chain import _build_model_chain
from .prompt_middleware import (
    BeijingTimeMiddleware,
    DecisionSystemMiddleware,
    HistorySystemPromptMiddleware,
    ImageRenderingMiddleware,
    NoSystemInThinkingMiddleware,
    RoleDefinitionMiddleware,
    StructuredChatFormatMiddleware,
)
from .pydantic_models import ModelChainState, ModelNodeSettings, ProcessorContext
from .quality_gate import QualityGate
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


# ---------------------------------------------------------------------------
# build_model_node
# ---------------------------------------------------------------------------


def build_model_node(
    *,
    llm: BaseChatModel,
    non_thinking_llm: BaseChatModel = None,
    judge_llm: BaseChatModel | None = None,
    tools: List[BaseTool],
    node_options: ModelNodeSettings | None = None,
) -> RunnableCallable:
    """创建标准 QA 场景的模型节点。

    模型节点内部包含 recovery 循环，处理模型响应异常（空内容、纯思考、截断等），
    无需在 graph 层添加额外的 recovery 节点。

    Args:
        llm: 语言模型
        non_thinking_llm: 辅助模型
        judge_llm: 判断用 LLM（用于 quality_gate 评估任务完成度）；None 时 fail-open
        tools: 工具列表（全量工具，内部会根据 state 决策筛选）
        node_options: 模型节点选项（可选，不传则使用默认值）

    Returns:
        RunnableCallable，包含同步和异步两个节点函数
    """

    if node_options is None:
        node_options = ModelNodeSettings()

    use_structured_response = node_options.use_structured_response
    enable_parallel_tool_calls = node_options.enable_parallel_tool_calls
    model_chain_config = node_options.model_chain_config
    quality_gate = QualityGate(
        judge_llm=judge_llm,
        enable_judgment_llm=model_chain_config.enable_judgment_llm,
    )

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
    context_assembly.add_middleware("template", ImageRenderingMiddleware())
    context_assembly.add_middleware("template", NoSystemInThinkingMiddleware())
    context_assembly.add_middleware("template", HistorySystemPromptMiddleware())
    # 加载由 graph 层注入的额外模板中间件（例如 SkillsPromptMiddleware）
    for middleware in node_options.extra_template_middlewares:
        context_assembly.add_middleware("template", middleware)
    # 加载和构造 prompt-variables 相关的中间件
    context_assembly.add_middleware("variable", BaseVariablesMiddleware())
    context_assembly.add_middleware(
        "variable",
        SpecialVariablesMiddleware(
            use_structured_response=use_structured_response,
            use_general_knowledge_on_miss=node_options.use_general_knowledge_on_miss,
            rejection_message=node_options.rejection_message,
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
    # 基于 Token 超限的工具输出压缩
    context_assembly.add_middleware(
        "variable",
        ToolOutputLengthCompressionMiddleware(
            tool_output_compress_thrd=node_options.tool_output_compress_thrd,
            tool_output_compressor_func=tool_output_compressor,
        ),
    )
    # 工具压缩后重新渲染agent_scratchpad
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
        SpecialVariablesPostMiddleware(use_structured_response=use_structured_response),
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
    for m in getattr(node_options, "extra_tool_middlewares", []) or []:
        context_assembly.add_middleware("tool", m)

    # 在闭包作用域中一次性构建共享的 LCEL 模型链。
    model_chain = _build_model_chain(
        llm=llm,
        context_assembly=context_assembly,
        model_chain_config=model_chain_config,
        quality_gate=quality_gate,
        use_structured_response=use_structured_response,
        enable_parallel_tool_calls=enable_parallel_tool_calls,
        use_tool_call_promotion=node_options.use_tool_call_promotion,
    )

    def model_node(
        state: ModelState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> Dict[str, Any]:
        """同步模型推理节点（含内部恢复循环）。"""
        ctx = ProcessorContext(
            state=state,
            config=config,
            store=store,
            llm=llm,
            model_chain_state=ModelChainState(
                max_empty_retries=model_chain_config.max_empty_retries,
                max_thinking_prefill_retries=model_chain_config.max_thinking_prefill_retries,
                max_truncation_retries=model_chain_config.max_truncation_retries,
                max_truncated_tool_call_retries=model_chain_config.max_truncated_tool_call_retries,
            ),
            messages=[],
            response=None,
        )
        # 断言链运行时必填字段（中间件路径不校验）
        assert ctx.config is not None and ctx.state is not None
        final_ctx = model_chain.invoke(ctx)
        return {"messages": [final_ctx.response]}

    async def amodel_node(
        state: ModelState,
        config: RunnableConfig,
        *,
        store: BaseStore,
    ) -> Dict[str, Any]:
        """异步模型推理节点（含内部恢复循环）。"""
        ctx = ProcessorContext(
            state=state,
            config=config,
            store=store,
            llm=llm,
            model_chain_state=ModelChainState(
                max_empty_retries=model_chain_config.max_empty_retries,
                max_thinking_prefill_retries=model_chain_config.max_thinking_prefill_retries,
                max_truncation_retries=model_chain_config.max_truncation_retries,
                max_truncated_tool_call_retries=model_chain_config.max_truncated_tool_call_retries,
            ),
            messages=[],
            response=None,
        )
        # 断言链运行时必填字段（中间件路径不校验）
        assert ctx.config is not None and ctx.state is not None
        final_ctx = await model_chain.ainvoke(ctx)
        return {"messages": [final_ctx.response]}

    return RunnableCallable(model_node, amodel_node, trace=True)
