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
from typing import TYPE_CHECKING, Annotated, Dict, List, Optional, Sequence, Tuple

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import ByteStore
from langchain_core.tools import BaseTool
from langgraph.cache.base import BaseCache
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import add_messages
from langgraph.graph.state import StateGraph
from langgraph.store.memory import InMemoryStore
from typing_extensions import Literal, TypedDict, TypeVar

from aidev_agent.core.nodes.knowledge import make_knowledge_node
from aidev_agent.core.nodes.model import ModelNodeSettings
from aidev_agent.core.nodes.model import build_model_node as std_make_model_node
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.tools.add_image_to_chat_context import add_image_to_chat_context
from aidev_agent.enums import Decision
from aidev_agent.packages.langchain_core.models.utils import is_model_without_function_calling
from aidev_agent.packages.langgraph.streaming.streaming_protocol import AgentStreamAdapter
from aidev_agent.services.pydantic_models import AgentExecutorKwargs, AgentOptions

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable
    from langgraph.store.base import BaseStore
ResponseT = TypeVar("ResponseT")

logger = logging.getLogger(__name__)


class DefaultState(TypedDict):
    # 消息历史（包含人类消息、AI消息和工具执行结果）
    messages: Annotated[List[BaseMessage], add_messages]
    # 知识库相关数据
    decision: Decision
    knowledge_resources_highly_relevant: list
    knowledge_resources_moderately_relevant: list
    knowledge_resources_lowly_relevant: list
    reference_doc: list
    knowledge_content: list
    knowledge_qa_content: list
    with_qa_response: list


class KnowledgeInputState(TypedDict):
    input: str
    query: str


class ReActAgentBuilder:
    """LangGraph V1 QA Agent 构建器。

    支持工具调用的完整 ReAct 循环：
    - model 节点：调用 LLM 进行推理
    - tool 节点：执行工具调用
    - 条件路由：model → tool / END，tool → model
    """

    def __init__(self) -> None:
        # Core model & tools
        self._llm: BaseChatModel | None = None
        self._knowledge_llm: BaseChatModel | None = None
        self._non_thinking_llm: BaseChatModel | str | None = None
        self._extra_tools: list[BaseTool] = []

        # Prompt / chat context
        self._prefix: str | None = None
        self._role_prompt: str | None = None
        self._suffix: str | None = None
        self._format_instructions: str | None = None
        self._chat_history: list[BaseMessage] | None = None

        # Knowledge & options
        self._knowledge_items: list[Dict] | None = None
        self._knowledge_bases: list[Dict] | None = None
        self._agent_options: AgentOptions | None = None
        self._intent_recognition_kwargs: Dict | None = None

        # Runtime config
        self._callbacks: list | None = None
        self._file_store: ByteStore | None = None
        self._support_vision: bool = False
        self._llm_token_limit: int = 28000
        self._state_schema: type[AgentState[ResponseT]] | None = None
        self._checkpointer: BaseCheckpointSaver | None = None
        self._store: "BaseStore | None" = None
        self._interrupt_before: list[str] | None = None
        self._interrupt_after: list[str] | None = None
        self._debug: bool = False
        self._name: str | None = None
        self._cache: BaseCache | None = None
        self._enable_query_clarification: Optional[bool] = None
        self._langchain_middleware: Sequence[AgentMiddleware] = ()
        self._tool_node_options: ToolNodeSettings | None = None

        # Keep extra kwargs for forward compatibility (BkAi platform options / user extensions)
        self._extra_kwargs: dict = {}

    def set_llm(self, llm: BaseChatModel) -> "ReActAgentBuilder":
        self._llm = llm
        return self

    def set_knowledge_llm(self, knowledge_llm: BaseChatModel | None) -> "ReActAgentBuilder":
        self._knowledge_llm = knowledge_llm
        return self

    def set_non_thinking_llm(self, non_thinking_llm: BaseChatModel | str | None) -> "ReActAgentBuilder":
        self._non_thinking_llm = non_thinking_llm
        return self

    def set_tools(self, tools: Sequence[BaseTool] | None) -> "ReActAgentBuilder":
        self._extra_tools = list(tools or [])
        return self

    def add_tools(self, tools: Sequence[BaseTool]) -> "ReActAgentBuilder":
        self._extra_tools.extend(list(tools or []))
        return self

    def set_role_prompt(self, role_prompt: str | None) -> "ReActAgentBuilder":
        self._role_prompt = role_prompt
        return self

    def set_agent_options(self, agent_options: AgentOptions | None) -> "ReActAgentBuilder":
        self._agent_options = agent_options
        return self

    def set_callbacks(self, callbacks: list | None) -> "ReActAgentBuilder":
        self._callbacks = callbacks
        return self

    def set_file_store(self, file_store: ByteStore | None) -> "ReActAgentBuilder":
        self._file_store = file_store
        return self

    def set_support_vision(self, support_vision: bool) -> "ReActAgentBuilder":
        self._support_vision = support_vision
        return self

    def set_checkpointer(self, checkpointer: BaseCheckpointSaver | None) -> "ReActAgentBuilder":
        self._checkpointer = checkpointer
        return self

    def set_store(self, store: "BaseStore | None") -> "ReActAgentBuilder":
        self._store = store
        return self

    def set_langchain_middleware(self, middleware: Sequence[AgentMiddleware]) -> "ReActAgentBuilder":
        self._langchain_middleware = middleware or ()
        return self

    def set_tool_node_options(self, tool_node_options: ToolNodeSettings | None) -> "ReActAgentBuilder":
        self._tool_node_options = tool_node_options
        return self

    def set_bkai_options(self, options: AgentExecutorKwargs) -> "ReActAgentBuilder":
        """将 BkAi 平台通用配置（AgentExecutorKwargs）映射到 builder 内部状态。"""
        if options.llm is not None:
            self._llm = options.llm
        if options.knowledge_llm is not None:
            self._knowledge_llm = options.knowledge_llm
        if options.non_thinking_llm is not None:
            self._non_thinking_llm = options.non_thinking_llm
        if options.extra_tools is not None:
            self._extra_tools = list(options.extra_tools)
        if options.chat_history is not None:
            self._chat_history = list(options.chat_history)
        if options.role_prompt is not None:
            self._role_prompt = options.role_prompt
        if options.support_vision is not None:
            self._support_vision = bool(options.support_vision)
        if options.file_store is not None:
            self._file_store = options.file_store
        if options.callbacks is not None:
            self._callbacks = list(options.callbacks)
        if options.agent_options is not None:
            self._agent_options = options.agent_options
        if options.checkpointer is not None:
            self._checkpointer = options.checkpointer

        # 未被 builder 消费的字段（包含 extra='allow'）全部存入 _extra_kwargs，供后续扩展
        consumed = {
            "llm",
            "knowledge_llm",
            "non_thinking_llm",
            "extra_tools",
            "chat_history",
            "role_prompt",
            "support_vision",
            "file_store",
            "callbacks",
            "agent_options",
            "checkpointer",
        }
        dumped = options.model_dump(exclude_none=True)
        for k, v in dumped.items():
            if k not in consumed:
                self._extra_kwargs[k] = v
        return self

    def set_prefix(self, prefix: str | None) -> "ReActAgentBuilder":
        self._prefix = prefix
        return self

    def set_suffix(self, suffix: str | None) -> "ReActAgentBuilder":
        self._suffix = suffix
        return self

    def set_format_instructions(self, format_instructions: str | None) -> "ReActAgentBuilder":
        self._format_instructions = format_instructions
        return self

    def set_chat_history(self, chat_history: list[BaseMessage] | None) -> "ReActAgentBuilder":
        self._chat_history = chat_history
        return self

    def set_knowledge_items(self, knowledge_items: list[Dict] | None) -> "ReActAgentBuilder":
        self._knowledge_items = knowledge_items
        return self

    def set_knowledge_bases(self, knowledge_bases: list[Dict] | None) -> "ReActAgentBuilder":
        self._knowledge_bases = knowledge_bases
        return self

    def set_intent_recognition_kwargs(self, intent_recognition_kwargs: Dict | None) -> "ReActAgentBuilder":
        self._intent_recognition_kwargs = intent_recognition_kwargs
        return self

    def set_enable_query_clarification(self, enable_query_clarification: bool | None) -> "ReActAgentBuilder":
        self._enable_query_clarification = enable_query_clarification
        return self

    def set_llm_token_limit(self, llm_token_limit: int) -> "ReActAgentBuilder":
        self._llm_token_limit = llm_token_limit
        return self

    def set_state_schema(self, state_schema: type[AgentState[ResponseT]] | None) -> "ReActAgentBuilder":
        self._state_schema = state_schema
        return self

    def set_interrupt_before(self, interrupt_before: list[str] | None) -> "ReActAgentBuilder":
        self._interrupt_before = interrupt_before
        return self

    def set_interrupt_after(self, interrupt_after: list[str] | None) -> "ReActAgentBuilder":
        self._interrupt_after = interrupt_after
        return self

    def set_debug(self, debug: bool) -> "ReActAgentBuilder":
        self._debug = debug
        return self

    def set_name(self, name: str | None) -> "ReActAgentBuilder":
        self._name = name
        return self

    def set_cache(self, cache: BaseCache | None) -> "ReActAgentBuilder":
        self._cache = cache
        return self

    def _prepare_agent_options(
        self,
        agent_options: Optional[AgentOptions],
        *,
        knowledge_items: Optional[List[Dict]] = None,
        knowledge_bases: Optional[List[Dict]] = None,
        role_prompt: Optional[str] = None,
        intent_recognition_kwargs: Optional[Dict] = None,
    ) -> AgentOptions:
        options = agent_options or AgentOptions()

        ir_options = options.intent_recognition_options
        kq_options = options.knowledge_query_options
        if intent_recognition_kwargs:
            if "tool_output_compress_thrd" in intent_recognition_kwargs:
                # aidev_agent/services/pydantic_models.py 中，默认配置为 5000
                ir_options.tool_output_compress_thrd = intent_recognition_kwargs["tool_output_compress_thrd"]
            if "token_limit_margin" in intent_recognition_kwargs:
                # aidev_agent/services/pydantic_models.py 中，默认配置为 100
                kq_options.token_limit_margin = intent_recognition_kwargs["token_limit_margin"]
            if "max_tool_output_len" in intent_recognition_kwargs:
                # aidev_agent/services/pydantic_models.py 中，默认配置为 500
                ir_options.max_tool_output_len = intent_recognition_kwargs["max_tool_output_len"]
        if knowledge_bases:
            kq_options.knowledge_bases = knowledge_bases
        if knowledge_items:
            kq_options.knowledge_items = knowledge_items
        if role_prompt:
            kq_options.role_prompt = role_prompt

        return options

    def _prepare_agent_knowledge_node(self, *, knowledge_llm, agent_options):
        knowledge_query_options = agent_options.knowledge_query_options
        has_knowledge = knowledge_query_options.knowledge_bases or knowledge_query_options.knowledge_items
        if has_knowledge:
            return make_knowledge_node(
                llm=knowledge_llm,
                agent_options=agent_options,
            )
        return None

    def _prepare_agent_model_node(
        self,
        *,
        llm: BaseChatModel,
        non_thinking_llm: BaseChatModel,
        tools: List[BaseTool],
        use_structured_response: bool,
        enable_query_clarification: bool,
        agent_options: AgentOptions,
    ):
        """创建模型节点。

        构建 ModelNodeSettings 并创建 model_node，用于 LLM 推理。

        Args:
            llm: 语言模型
            tools: 工具列表
            use_structured_response: 是否使用结构化输出模式
            enable_query_clarification: 是否启用查询澄清
            agent_options: Agent 配置选项

        Returns:
            model_node: 模型节点
        """
        # 处理 enable_query_clarification 的默认值
        if enable_query_clarification is None:
            model_name = getattr(llm, "model_name", "")
            enable_query_clarification = model_name == "gpt-4o" or "deepseek" in model_name or "qwq" in model_name
        # 从 agent_options 获取配置
        knowledge_query_options = agent_options.knowledge_query_options
        default_node_options = ModelNodeSettings()
        rejection_message = (
            knowledge_query_options.rejection_message
            if knowledge_query_options.rejection_message is not None
            else default_node_options.rejection_message
        )
        role_prompt = (
            knowledge_query_options.role_prompt
            if knowledge_query_options.role_prompt is not None
            else default_node_options.role_prompt
        )
        use_general_knowledge_on_miss = knowledge_query_options.is_response_when_no_knowledgebase_match

        node_options = ModelNodeSettings(
            use_structured_response=use_structured_response,
            enable_query_clarification=enable_query_clarification,
            rejection_message=rejection_message,
            role_prompt=role_prompt,
            use_general_knowledge_on_miss=use_general_knowledge_on_miss,
            tool_output_compress_thrd=agent_options.intent_recognition_options.tool_output_compress_thrd,
        )

        # 创建模型节点
        model_node = std_make_model_node(
            llm=llm,
            non_thinking_llm=non_thinking_llm,
            tools=tools,
            node_options=node_options,
        )

        return model_node

    def _prepare_agent_tools(
        self,
        *,
        extra_tools: List[BaseTool] = None,
        support_vision: bool = False,
        ignore_errors: bool = False,
        langchain_middleware: Sequence[AgentMiddleware],
    ) -> List[BaseTool]:
        tools: List[BaseTool] = []
        # 加载所有传入的工具
        if extra_tools:
            tools.extend(extra_tools or [])
        # 加载图片工具
        if support_vision:
            tools.append(add_image_to_chat_context)
        # 加载由中间间导入的工具
        middleware_tools = [t for m in langchain_middleware for t in getattr(m, "tools", [])]
        tools.extend(middleware_tools)
        # 为所有工具添加忽略错误表示
        if ignore_errors:
            # NOTE: 在 StructuredChatAgent 中修改 tools 中的参数
            # 使得如果 LLM 调用工具时如果出现以下类型的错误，可以重新尝试，继续进行而不阻碍过程
            for i in range(len(tools)):
                tools[i].handle_validation_error = True
                tools[i].handle_tool_error = True
        return tools

    def _prepare_agent_tool_node(
        self,
        tools: List[BaseTool],
        *,
        name: str = "tools",
        tags: List[str] | None = None,
        langchain_middleware: Sequence[AgentMiddleware],
        node_options: ToolNodeSettings = None,
    ):
        # 处理执行时的包装器
        middleware_w_wrap_tool_call = [
            m
            for m in langchain_middleware
            if m.__class__.wrap_tool_call is not AgentMiddleware.wrap_tool_call
            or m.__class__.awrap_tool_call is not AgentMiddleware.awrap_tool_call
        ]
        middleware_w_awrap_tool_call = [
            m
            for m in langchain_middleware
            if m.__class__.awrap_tool_call is not AgentMiddleware.awrap_tool_call
            or m.__class__.wrap_tool_call is not AgentMiddleware.wrap_tool_call
        ]
        if tools:
            return build_tool_node(
                tools=tools,
                name=name,
                tags=tags,
                wrappers=middleware_w_wrap_tool_call,
                async_wrappers=middleware_w_awrap_tool_call,
                node_options=node_options,
            )
        return None

    def _prepare_checkpointer(self, *, checkpointer: BaseCheckpointSaver | None = None):
        if isinstance(checkpointer, BaseCheckpointSaver):
            return checkpointer
        return MemorySaver()

    def _prepare_store(
        self,
        *,
        store: "BaseStore | None",
        file_store: Optional[ByteStore],
    ) -> "BaseStore":
        """使用 LangGraph Store 模拟 request_local.current_user_store。

        - 默认使用 InMemoryStore
        - 预先写入 file_store / image / knowledge_bases / knowledge_items / reference_doc
        """
        if store is None:
            store = InMemoryStore()
        return store

    @staticmethod
    def _should_continue(state: dict) -> Literal["tools", "end"]:
        """条件路由函数：决定 model 节点后的下一步。

        检查模型输出是否包含 tool_calls：
        - 如果有 tool_calls，路由到 tools 节点执行工具
        - 否则路由到 end 结束对话

        Args:
            state: 当前状态字典

        Returns:
            "tools" 或 "end"
        """
        messages = state.get("messages", [])
        if not messages:
            return "end"

        last_message = messages[-1]

        # 检查最后一条消息是否是 AIMessage 并且包含 tool_calls
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"

        return "end"

    def _build_graph(
        self,
        *,
        agent_options: AgentOptions,
        state_schema,
        callbacks: List,
        debug: bool,
        checkpointer,
        store,
        interrupt_before,
        interrupt_after,
        name,
        cache,
        knowledge_node,
        model_node,
        tool_node,
    ) -> Tuple["Runnable", RunnableConfig]:
        """构建 LangGraph 图。

        图结构：
        - 无知识库配置: START → model → tools/END
        - 有知识库配置: START → knowledge → model → tools/END
        - 如果有工具: model → (条件) → tools / END, tools → model

        Args:
            agent_options: Agent 配置选项
            state_schema: 状态模式
            callbacks: 回调列表
            debug: 是否开启调试模式
            checkpointer: 检查点
            store: 存储
            interrupt_before: 中断前节点列表
            interrupt_after: 中断后节点列表
            name: 图名称
            cache: 缓存
            knowledge_node: 知识库节点
            model_node: 模型节点
            tool_node: 工具节点

        Returns:
            (CompiledGraph, RunnableConfig) 元组
        """
        graph = StateGraph(state_schema=state_schema)

        # 如果配置了知识库,添加 knowledge 节点
        if knowledge_node:
            graph.add_node("knowledge", knowledge_node)
            graph.add_edge(START, "knowledge")

        # 添加模型节点
        graph.add_node("model", model_node)

        # 根据是否有知识库节点,连接不同的边
        if knowledge_node:
            # 有知识库: knowledge → model
            graph.add_edge("knowledge", "model")
        else:
            # 无知识库: START → model
            graph.add_edge(START, "model")

        # 如果有工具，添加工具节点和条件路由
        if tool_node:
            graph.add_node("tools", tool_node)
            # model → (should_continue) → tools / end
            graph.add_conditional_edges(
                "model",
                self._should_continue,
                {
                    "tools": "tools",
                    "end": END,
                },
            )
            # tools → model (形成 ReAct 循环)
            graph.add_edge("tools", "model")
        else:
            # 无工具时直接结束
            graph.add_edge("model", END)

        compile_graph = graph.compile(
            checkpointer=checkpointer,
            cache=cache,
            store=store,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
            debug=debug,
            name=name,
        )

        cfg = RunnableConfig()
        cfg["configurable"] = {
            "agent_options": agent_options,
            "debug": debug,
        }
        if callbacks:
            cfg["callbacks"] = callbacks
            compile_graph = compile_graph.with_config({"callbacks": callbacks})
            logger.info(f"react graph callbacks: {callbacks}")
        return compile_graph, cfg

    def build(self) -> Tuple["Runnable", RunnableConfig]:
        """构建并返回 compiled graph 与 runnable config。"""
        if self._llm is None:
            raise ValueError("ReActAgentBuilder 构建失败：缺少 llm，请先调用 set_llm(...) 或 set_bkai_options(...)")

        callbacks = list(self._callbacks or [])
        non_thinking_llm = self._non_thinking_llm or self._llm
        use_structured_response = bool(is_model_without_function_calling(self._llm) and self._extra_tools)

        # 统一处理 agent_options
        prepared_agent_options = self._prepare_agent_options(
            self._agent_options,
            knowledge_items=self._knowledge_items,
            knowledge_bases=self._knowledge_bases,
            role_prompt=self._role_prompt,
            intent_recognition_kwargs=self._intent_recognition_kwargs,
        )

        # 若配置了知识库/知识项，则需要 knowledge_llm
        has_knowledge = bool(
            prepared_agent_options.knowledge_query_options.knowledge_bases
            or prepared_agent_options.knowledge_query_options.knowledge_items
        )
        if has_knowledge and self._knowledge_llm is None:
            raise ValueError("ReActAgentBuilder 构建失败：检测到知识库配置，但 knowledge_llm 为空")

        # checkpointer 由调用方决定（ChatCompletionAgent 会在有需要时注入 thread_id 等 configurable key）
        checkpointer = self._checkpointer

        # 统一处理 tools
        tool_ignore_errors = use_structured_response
        tools: List[BaseTool] = self._prepare_agent_tools(
            extra_tools=self._extra_tools,
            support_vision=self._support_vision,
            ignore_errors=tool_ignore_errors,
            langchain_middleware=self._langchain_middleware,
        )

        # 统一处理 knowledge_node
        knowledge_node = self._prepare_agent_knowledge_node(
            knowledge_llm=self._knowledge_llm,
            agent_options=prepared_agent_options,
        )

        # 统一处理 model_node
        model_node = self._prepare_agent_model_node(
            llm=self._llm,
            non_thinking_llm=non_thinking_llm,
            tools=tools,
            use_structured_response=use_structured_response,
            enable_query_clarification=self._enable_query_clarification,
            agent_options=prepared_agent_options,
        )

        # 统一处理 tool_node
        tool_node = self._prepare_agent_tool_node(
            tools,
            langchain_middleware=self._langchain_middleware,
            node_options=self._tool_node_options,
        )

        # 初始化 Store
        store = self._prepare_store(store=self._store, file_store=self._file_store)

        # 定制 ReAct chat prompt template
        state_schema = self._state_schema or DefaultState

        # 构建图
        compile_graph, cfg = self._build_graph(
            agent_options=prepared_agent_options,
            state_schema=state_schema,
            callbacks=callbacks,
            debug=self._debug,
            checkpointer=checkpointer,
            store=store,
            interrupt_before=self._interrupt_before,
            interrupt_after=self._interrupt_after,
            name=self._name,
            cache=self._cache,
            knowledge_node=knowledge_node,
            model_node=model_node,
            tool_node=tool_node,
        )

        # 添加适配器
        compile_graph.agent = AgentStreamAdapter(agent_options=prepared_agent_options)
        return compile_graph, cfg
