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
from typing import Dict, List, Optional, Tuple
from typing import TYPE_CHECKING, Annotated

from langchain.agents.middleware.types import (
    AgentState,
)
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import ByteStore
from langchain_core.tools import BaseTool
from langgraph.constants import END, START
from langgraph.graph import add_messages
from langgraph.graph.state import StateGraph
from typing_extensions import TypedDict, TypeVar

from aidev_agent.core.bk_streaming.streaming_protocol import BkAiStreamingProtocol
from aidev_agent.core.extend.intent.utils import deduplicate_knowledge_file_paths
from aidev_agent.core.knowledge.bk_retriever import BkRetriever
from aidev_agent.core.knowledge.kb_rag import KnowledgeRag
from aidev_agent.core.utils.async_utils import async_generator_with_timeout, async_to_sync_generator
from aidev_agent.enums import Decision
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


def intent_std_node(state: DefaultState) -> dict:
    return {}


class KnowledgeInputState(TypedDict):
    input: str
    query: str


class LangGraphV1QABuilder:
    def __init__(self, llm, knowledge_llm, tools, agent_options):
        self.llm = llm
        self.knowledge_llm = knowledge_llm
        self.tools = tools or []
        self.agent_options = agent_options

    def make_intent_node(self):
        return intent_std_node

    def make_knowledge_node(self):
        llm = self.llm
        agent_options: AgentOptions = self.agent_options
        if not agent_options.knowledge_query_options.knowledge_bases and not  agent_options.knowledge_query_options.knowledge_items:
            def knowledge_rag_std_node(state: KnowledgeInputState):
                return {}
            return knowledge_rag_std_node

        def knowledge_rag_std_node(state: KnowledgeInputState, config: RunnableConfig):
            query = state.get("query")
            if query is None:
                query = state.get("input")

            kb_retriever = BkRetriever()
            retriever = KnowledgeRag(llm, kb_retriever)
            ret = retriever.retrieve(query, agent_options)

            decision = ret["decision"]

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
                if reference_doc:
                    dispatch_custom_event(
                        "custom_event",
                        {"reference_doc": reference_doc},
                        config=config,
                    )

            if decision == Decision.QUERY_CLARIFICATION:
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
                    dispatch_custom_event(
                        "custom_event",
                        {"reference_doc": reference_doc},
                        config=config,
                    )

            return ret

        return knowledge_rag_std_node

    def make_model_node(self):
        llm = self.llm

        def model_node(state: dict):
            response = llm.invoke(state["input"])
            return {"message": [response]}

        return model_node


class LangGraphV1QAAgent:
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
        **kwargs,
    ) -> Tuple[Runnable, RunnableConfig]:
        if state_schema is None:
            state_schema = DefaultState

        builder = LangGraphV1QABuilder(
            llm = llm,
            knowledge_llm = knowledge_llm,
            tools = extra_tools,
            agent_options = agent_options,
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
                    protocol = BkAiStreamingProtocol(skip_thought=skip_thought, timeout=timeout, max_tool_output_len=2000)
                    _aiter = agent_e.astream_events(
                        input_state, config=cfg, version="v2", timeout=timeout, durability="exit"
                    )
                    _aiter = async_generator_with_timeout(_aiter, timeout=timeout)
                    g = async_to_sync_generator(_aiter)
                    yield from protocol.stream_standard_event(g)
                except Exception as e:
                    print(e)
                    logger.error(traceback.format_exc())

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
        cfg["configurable"] = {
            "agent_options": agent_options,
            "debug": True,
        }
        return compile_graph, cfg
