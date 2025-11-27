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
import traceback
from copy import deepcopy
from typing import Dict, List, Optional, Tuple, ClassVar, Any
from typing import TYPE_CHECKING, Annotated

from langchain.agents.middleware.types import (
    AgentState,
)
from langchain_community.adapters.openai import convert_message_to_dict, convert_dict_to_message
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import ByteStore
from langchain_core.tools import BaseTool
from langgraph.constants import END, START
from langgraph.graph import add_messages
from langgraph.graph.state import StateGraph
from langgraph.store.memory import InMemoryStore
from typing_extensions import TypedDict, TypeVar

from aidev_agent.core.agent.prompts import MULTI_MODAL_PREFIX
from aidev_agent.core.bk_streaming.streaming_protocol import BkAiStreamingProtocol
from aidev_agent.core.extend.intent.prompts import (
    general_qa_prompt_structured_chat,
    DEFAULT_QA_PROMPT_TEMPLATES,
)
from aidev_agent.core.extend.intent.utils import is_model_without_function_calling, \
    is_deepseek_r1_series_models
from aidev_agent.core.knowledge.bk_retriever import BkRetriever
from aidev_agent.core.knowledge.kb_rag import KnowledgeRag
from aidev_agent.core.knowledge.utils import deduplicate_knowledge_file_paths
from aidev_agent.core.utils.async_utils import async_generator_with_timeout, async_to_sync_generator
from aidev_agent.core.utils.tools import get_beijing_now
from aidev_agent.enums import Decision, ContextType
from aidev_agent.packages.langchain.tools.builtin import add_image_to_chat_context
from aidev_agent.services.pydantic_models import AgentOptions

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable
    from langgraph.cache.base import BaseCache
    from langgraph.store.base import BaseStore
    from langgraph.types import Checkpointer
ResponseT = TypeVar("ResponseT")

logger = logging.getLogger(__name__)


class DefaultState(TypedDict):
    input: str
    # 消息历史 人类消息和工具执行消息
    messages: Annotated[List[BaseMessage], add_messages]
    tool_messages: Annotated[List[BaseMessage], add_messages]
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


def create_tool_call_prompt_template(
    prefix: Optional[str] = None,
    role_prompt: Optional[str] = None,
    *,
    query_knowledgebase: bool = False,
) -> ChatPromptTemplate:
    """构造 Tool-Calling 场景下使用的 ChatPromptTemplate。

    逻辑参考 ToolCallCommonAgentMixIn.create_agent：
    - system: 多模态前缀 + 角色提示
    - placeholder: chat_history
    - human: 当前用户输入
    - placeholder: agent_scratchpad
    - 可选插入知识库查询的提示语
    """
    messages = [
        (
            "system",
            (prefix or MULTI_MODAL_PREFIX) + ("\n" + role_prompt if role_prompt else "") + "\n",
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
    if query_knowledgebase:
        messages.insert(
            -2,
            (
                "human",
                "根据后续用户提的问题，获取knowledge_item_ids与knowledgebase_ids, 先使用工具查询下知识库。"
                "如果发现knowledge_items或knowledgebase都和主题无关，那就随机挑选一个存在的。",
            ),
        )
        messages.insert(
            -2,
            (
                "ai",
                "好的，接下来我会先查询下知识库，并确保传入了knowledge_item_ids或knowledgebase_ids。",
            ),
        )
    # TODO:
    # 1. 将以上 chat_prompt_template 构建替换成 chat_prompt_template = deepcopy(general_qa_prompt_tool_calling)
    # 2. 适配更新测试样例 test_ws_consumer 逻辑防止出现：
    # KeyError: "Input to ChatPromptTemplate is missing variables {'role_prompt', 'query'}.
    # Expected: ['query', 'role_prompt']
    # Received: ['input', 'files_list', 'knowledge_items', 'knowledge_bases', 'chat_history',
    # 'intermediate_steps', 'agent_scratchpad']
    # Note: if you intended {role_prompt} to be part of the string and not a variable,
    # please escape it with double curly braces like: '{{role_prompt}}'."
    return ChatPromptTemplate.from_messages(messages)


def create_structured_chat_prompt_template() -> ChatPromptTemplate:
    """构造 Structured Chat 场景下使用的 ChatPromptTemplate。

    逻辑参考 StructuredChatCommonAgentMixIn.create_agent：
    - 直接复用 general_qa_prompt_structured_chat，并进行 deepcopy，避免被运行时修改。
    """
    return deepcopy(general_qa_prompt_structured_chat)


class LangGraphV1QABuilder:
    qa_prompt_templates: ClassVar[Dict[str, Any]] = DEFAULT_QA_PROMPT_TEMPLATES

    def __init__(self, llm, knowledge_llm, use_structured_chat, tools, agent_options, react_chat_prompt_template, enable_query_clarification = None):
        self.use_structured_chat = use_structured_chat
        self.llm = llm
        self.knowledge_llm = knowledge_llm
        self.tools = tools or []
        self.agent_options = agent_options
        self.react_chat_prompt_template = react_chat_prompt_template
        self.enable_query_clarification = enable_query_clarification

    def make_intent_node(self):
        """构造意图识别节点。

        对应旧版 AgentExecutor 中的 IntentRecognitionMixin.intent_recognition_pipeline：
        在 LangGraph 中，每次对话只会执行一次该节点，相当于首轮的 intent_recognition。
        """
        llm = self.llm
        agent_options: AgentOptions = self.agent_options
        tools = self.tools

        def intent_node(state: DefaultState, config: RunnableConfig) -> dict:
            """LangGraph 中的意图识别节点实现。"""
            return {}
            from aidev_agent.core.extend.intent.intent_recognition import IntentRecognition

            # 从状态中获取 chat_history，类型为 List[BaseMessage]
            chat_history = state.get("messages", [])

            # deepseek-r1 系列模型需要避免使用 system prompt，这里做一次转换
            if chat_history and is_deepseek_r1_series_models(llm):
                converted_history: List[BaseMessage] = []
                for msg in chat_history:
                    if isinstance(msg, SystemMessage):
                        msg_dict = convert_message_to_dict(msg)
                        msg_dict["role"] = "user"
                        converted_history.append(convert_dict_to_message(msg_dict))
                    else:
                        converted_history.append(msg)
                chat_history = converted_history

            recognition = IntentRecognition()

            recog_results = recognition.exec_intent_recognition(
                query=state["input"],
                llm=llm,
                tools=tools,
                callbacks=config.get("callbacks"),
                chat_history=chat_history,
                agent_options=agent_options,
            )

            # 将意图识别结果写入状态，后续节点可以按需使用
            return {
                "intent_recognition_results": recog_results,
            }

        return intent_node

    def make_knowledge_node(self):
        llm = self.llm
        agent_options: AgentOptions = self.agent_options

        # 如果没有配置知识库，保持节点为空实现
        if (
            not agent_options.knowledge_query_options.knowledge_bases
            and not agent_options.knowledge_query_options.knowledge_items
        ):

            def knowledge_rag_std_node(
                state: KnowledgeInputState,
                config: RunnableConfig,
                *,
                store,
            ):
                return {}

            return knowledge_rag_std_node

        def knowledge_rag_std_node(
            state: KnowledgeInputState,
            config: RunnableConfig,
            *,
            store,
        ):
            """知识检索节点

            - 使用 KnowledgeRag 进行知识库检索
            - 通过 dispatch_custom_event 派发 reference_doc，供前端流式协议使用
            - 同时将 reference_doc 写入 LangGraph Store，方便后续节点或调用方读取
            """
            query = state.get("query")
            if query is None:
                query = state.get("input")

            kb_retriever = BkRetriever()
            retriever = KnowledgeRag(llm, kb_retriever)
            # 将原始 input 传入，便于后续打分等逻辑复用
            ret = retriever.retrieve(query, agent_options, input=state.get("input"))

            decision = ret["decision"]
            reference_doc = None

            if decision == Decision.PRIVATE_QA:
                ret.update(
                    retriever.handle_knowledge_resources(
                        ret,
                        "knowledge_resources_highly_relevant",
                        agent_options=agent_options,
                    )
                )
                reference_doc = deduplicate_knowledge_file_paths(
                    ret["knowledge_resources_highly_relevant"]
                )
            elif decision == Decision.QUERY_CLARIFICATION:
                ret.update(
                    retriever.handle_knowledge_resources(
                        ret,
                        "knowledge_resources_moderately_relevant",
                        agent_options=agent_options,
                    )
                )
                reference_doc = deduplicate_knowledge_file_paths(
                    ret["knowledge_resources_moderately_relevant"]
                )

            if reference_doc:
                # 1. 通过自定义事件向前端推送 reference_doc
                dispatch_custom_event(
                    "custom_event",
                    {"reference_doc": reference_doc},
                    config=config,
                )
                # 2. 将 reference_doc 写入 LangGraph Store，模拟原来的 request_local.current_user_store 行为
                try:
                    store.put(("agent", "context"), "reference_doc", reference_doc)
                except Exception:
                    logger.warning("写入 reference_doc 到 LangGraph Store 失败", exc_info=True)
                # 3. 在本次节点返回中直接带上 reference_doc，便于非流式调用使用
                ret["reference_doc"] = reference_doc

            return ret

        return knowledge_rag_std_node

    def make_model_node(self):
        use_structured_chat = self.use_structured_chat
        agent_options: AgentOptions = self.agent_options
        llm = self.llm
        qa_prompt_templates = self.qa_prompt_templates
        if self.enable_query_clarification is not None:
            enable_query_clarification = self.enable_query_clarification
        else:
            enable_query_clarification = (llm.model_name == "gpt-4o" or "deepseek" in llm.model_name or "qwq" in llm.model_name)
        react_chat_prompt_template = self.react_chat_prompt_template
        tools = self.tools
        rejection_message = self.agent_options.knowledge_query_options.rejection_message
        role_prompt = agent_options.knowledge_query_options.role_prompt
        use_general_knowledge_on_miss = agent_options.knowledge_query_options.is_response_when_no_knowledgebase_match

        def get_chat_prompt_template(decision):
            chat_prompt_template_variable_suffix = "_structured_chat" if use_structured_chat else "_tool_calling"
            if decision == Decision.GENERAL_QA:
                return qa_prompt_templates.get(f"general_qa_prompt{chat_prompt_template_variable_suffix}")
            if decision == Decision.PRIVATE_QA:
                return qa_prompt_templates.get(f"private_qa_prompt{chat_prompt_template_variable_suffix}")
            if decision == Decision.QUERY_CLARIFICATION and enable_query_clarification:
                return qa_prompt_templates.get(f"clarifying_qa_prompt{chat_prompt_template_variable_suffix}")
            if decision == Decision.QUERY_CLARIFICATION and not enable_query_clarification:
                return qa_prompt_templates.get(f"private_qa_prompt{chat_prompt_template_variable_suffix}")
            return react_chat_prompt_template

        def model_node(state: dict):
            """模型推理节点。

            - 根据上一节点给出的 decision 选择合适的 ReAct Prompt
            - 当前仍然直接调用底层 LLM，后续可以在这里接入完整的 ReAct Agent
            """
            decision = state.get("decision", Decision.GENERAL_QA)
            react_chat_prompt_template = get_chat_prompt_template(decision)

            context_type = ''
            if state.get("knowledge_content") and state.get("knowledge_qa_content"):
                context_type = ContextType.BOTH.value
            elif state.get("knowledge_content"):
                context_type = ContextType.PRIVATE.value
            elif state.get('knowledge_qa_content'):
                context_type = ContextType.QA_RESPONSE.value

            if use_structured_chat:
                llm_with_tools = llm
            else:
                llm_with_tools = llm.bind_tools(tools)
            chain = react_chat_prompt_template | llm_with_tools
            # 当前阶段仍然保持最简单的推理逻辑：直接对 input 调用一次 llm
            response = chain.invoke({
                "beijing_now": get_beijing_now(),
                "context_type": context_type,
                "context": state.get("knowledge_content"),
                "qa_context": state.get("knowledge_qa_content"),
                "query": state.get("input"),
                "use_general_knowledge_on_miss": use_general_knowledge_on_miss,
                "chat_history": state["messages"],
                "rejection_response": rejection_message,
                "role_prompt": role_prompt,
                "agent_scratchpad": []
            })
            return {"messages": [response]}

        return model_node


class LangGraphV1QAAgent:
    @staticmethod
    def _prepare_agent_tools(
        extra_tools: List[BaseTool] = None,
        support_vision: bool = False,
        *,
        ignore_errors: bool = False,
    ) -> List[BaseTool]:
        tools: List[BaseTool] = []
        if extra_tools:
            tools.extend(extra_tools or [])
        if support_vision:
            tools.append(add_image_to_chat_context)
        if ignore_errors:
            # NOTE: 在 StructuredChatAgent 中修改 tools 中的参数
            # 使得如果 LLM 调用工具时如果出现以下类型的错误，可以重新尝试，继续进行而不阻碍过程
            for i in range(len(tools)):
                tools[i].handle_validation_error = True
                tools[i].handle_tool_error = True
        return tools

    @staticmethod
    def _prepare_agent_options(
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

    @staticmethod
    def _prepare_agent_memory(chat_history, llm):
        # 根据 deepseek 官方建议 https://github.com/deepseek-ai/DeepSeek-R1?tab=readme-ov-file#usage-recommendations
        # deepseek-r1 系列模型需要避免使用 system prompt
        # 这里统一转一下（否则用户选择“预设角色”可能包含 system prompt）
        # NOTE: 虽然聊天窗侧统一支持了以下转换，但还需要支持插件侧使用，因此这里还是需要做下检测和转换
        if is_deepseek_r1_series_models(llm):
            for i in range(len(chat_history)):
                if isinstance(chat_history[i], SystemMessage):
                    msg = convert_message_to_dict(chat_history[i])
                    msg["role"] = "user"
                    chat_history[i] = convert_dict_to_message(msg)
        return chat_history

    @staticmethod
    def _init_store(
        store: "BaseStore | None",
        *,
        file_store: Optional[ByteStore],
        agent_options: AgentOptions,
    ) -> "BaseStore":
        """使用 LangGraph Store 模拟 request_local.current_user_store。

        - 默认使用 InMemoryStore
        - 预先写入 file_store / image / knowledge_bases / knowledge_items / reference_doc
        """
        if store is None:
            store = InMemoryStore()

        try:
            namespace = ("agent", "context")
            store.put(namespace, "file_store", file_store)
            store.put(namespace, "image", {})
            store.put(
                namespace,
                "knowledge_bases",
                agent_options.knowledge_query_options.knowledge_bases,
            )
            store.put(
                namespace,
                "knowledge_items",
                agent_options.knowledge_query_options.knowledge_items,
            )
            store.put(namespace, "reference_doc", {})
        except Exception:
            logger.warning("初始化 LangGraph Store 时写入上下文失败", exc_info=True)

        return store

    @classmethod
    def get_agent_executor(
        cls,
        llm: BaseChatModel,
        knowledge_llm: BaseChatModel,
        extra_tools: Optional[List[BaseTool]] = None,
        prefix: Optional[str] = None,
        role_prompt: Optional[str] = None,
        suffix: Optional[str] = None,
        format_instructions: Optional[str] = None,
        chat_history: Optional[List[BaseMessage]] = None,
        callbacks: Optional[List] = None,
        knowledge_items: Optional[List[Dict]] = None,
        knowledge_bases: Optional[List[Dict]] = None,
        file_store: Optional[ByteStore] = None,
        support_vision: bool = False,
        llm_token_limit=28000,
        agent_options: Optional[AgentOptions] = None,
        *,
        state_schema: type[AgentState[ResponseT]] | None = None,
        checkpointer: Checkpointer | None = None,
        store: BaseStore | None = None,
        interrupt_before: list[str] | None = None,
        interrupt_after: list[str] | None = None,
        debug: bool = False,
        name: str | None = None,
        cache: BaseCache | None = None,
        intent_recognition_kwargs=None,
        **kwargs,
    ) -> Tuple[Runnable, RunnableConfig]:
        callbacks = callbacks or []
        use_structured_chat = is_model_without_function_calling(llm) and extra_tools
        tool_ignore_errors = use_structured_chat
        # 统一处理 tools
        tools: List[BaseTool] = cls._prepare_agent_tools(extra_tools, support_vision=support_vision, ignore_errors=tool_ignore_errors)
        # 统一处理 agent_options
        prepared_agent_options = cls._prepare_agent_options(
            agent_options,
            knowledge_items=knowledge_items,
            knowledge_bases=knowledge_bases,
            role_prompt=role_prompt,
            intent_recognition_kwargs=intent_recognition_kwargs,
        )
        # 定制，对于标准的ReAct Agent，使用 react_chat_prompt_template 作为需要的 chat_prompt_template
        if use_structured_chat:
            react_chat_prompt_template = create_structured_chat_prompt_template()
        else:
            react_chat_prompt_template = create_tool_call_prompt_template(prefix=prefix, role_prompt=role_prompt)

        if state_schema is None:
            state_schema = DefaultState

        builder = LangGraphV1QABuilder(
            llm=llm,
            knowledge_llm=knowledge_llm,
            tools=tools,
            use_structured_chat=use_structured_chat,
            agent_options=prepared_agent_options,
            react_chat_prompt_template=react_chat_prompt_template
        )

        graph = StateGraph(
            state_schema=state_schema,
        )
        # 意图识别节点迁移
        graph.add_node("intent", builder.make_intent_node())
        graph.add_node("knowledge", builder.make_knowledge_node())
        graph.add_node("model", builder.make_model_node())

        graph.add_edge(START, "intent")
        graph.add_edge("intent", "knowledge")
        graph.add_edge("knowledge", "model")
        graph.add_edge("model", END)

        class AgentStreamAdapter:
            # 流协议处理
            def stream_standard_event(self, agent_e, cfg, input_state, skip_thought=False, timeout: int = 30):
                try:
                    protocol = BkAiStreamingProtocol(
                        skip_thought=skip_thought,
                        timeout=timeout,
                        max_tool_output_len=2000,
                    )
                    _aiter = agent_e.astream_events(
                        input_state,
                        config=cfg,
                        version="v2",
                        timeout=timeout,
                        durability="exit",
                    )
                    _aiter = async_generator_with_timeout(_aiter, timeout=timeout)
                    g = async_to_sync_generator(_aiter)
                    yield from protocol.stream_standard_event(g)
                except Exception as e:
                    print(e)
                    logger.error(traceback.format_exc())

        # 初始化 Store，将当前用户上下文写入
        store = cls._init_store(
            store=store,
            file_store=file_store,
            agent_options=prepared_agent_options,
        )

        compile_graph = graph.compile(
            checkpointer=checkpointer,
            store=store,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
            debug=debug,
            name=name,
            cache=cache,
        )
        compile_graph.agent = AgentStreamAdapter()
        # 配置项添加
        cfg = RunnableConfig()
        cfg["callbacks"] = callbacks
        cfg["configurable"] = {
            "agent_options": prepared_agent_options,
            "debug": debug,
        }
        return compile_graph, cfg
