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
import time
import uuid
from typing import Any, NotRequired, Optional, TypedDict, cast

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from aidev_agent.core.ag_ui.types import ActivityMessage, CustomMessageType
from aidev_agent.enums import ActivityType
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.packages.langchain_core.retrievers.kb_rag import KnowledgeRag, KnowledgeRagRetrieveResult
from aidev_agent.packages.langchain_core.retrievers.utils import (
    normalize_query_for_search,
    resolve_display_sort_key,
)
from aidev_agent.pydantic_models import KnowledgeSettings
from aidev_agent.utils.migrations import migration_knowledge_query_options_from_agent_options_v1

logger = logging.getLogger(__name__)


class KnowledgeInputState(TypedDict):
    """
    知识库召回的 State 输入字段
    """

    query: NotRequired[str]
    input: NotRequired[str]
    messages: NotRequired[list[BaseMessage]]


class KnowledgeOutputState(KnowledgeRagRetrieveResult):
    messages: list[BaseMessage]


class AidevKnowledgeOutputState(KnowledgeRagRetrieveResult):
    retrieved_docs: list


def filter_and_select_topk(
    docs: list, score_threshold: float | None = None, topk: int = 20, sort_key: str = "fine_grained_score"
) -> list:
    """
    根据分数阈值过滤并选择 topk 文档。
    用于 force_process_by_agent 场景下返回原始召回文档。

    Args:
        docs: 召回的文档列表，每个文档包含 metadata.fine_grained_score
        score_threshold: 分数阈值，低于此阈值的文档将被过滤，None 表示不过滤
        topk: 返回的最大文档数量
        sort_key: 展示排序使用的分数字段；EMBEDDING（保留原始顺序）传 ``rrf_score`` 以尊重
            资源侧多路 RRF 融合顺序，缺失时回退 ``fine_grained_score``，无回归。
            过滤阈值仍固定用 ``fine_grained_score``，不受此参数影响。

    Returns:
        过滤并排序后的 topk 文档列表
    """
    if not docs:
        return []

    if score_threshold is not None:
        docs = [doc for doc in docs if doc.get("metadata", {}).get("fine_grained_score", 0) >= score_threshold]

    def _score(doc):
        metadata = doc.get("metadata", {})
        if sort_key in metadata:
            return metadata.get(sort_key) or 0
        return metadata.get("fine_grained_score", 0) or 0

    sorted_docs = sorted(docs, key=_score, reverse=True)

    return sorted_docs[:topk]


class BaseKnowledgeNode:
    """知识库检索节点基类。

    定义知识库检索节点的通用接口和基础实现。
    子类需要实现 process_result 方法来定制结果处理逻辑。

    Attributes:
        llm: 语言模型,用于知识库检索中的相关性判断和内容处理
        knowledge_query_options: 知识库检索配置
        kb_retriever: 知识库检索器实例
        retriever: KnowledgeRag 实例
    """

    def __init__(
        self,
        llm: BaseChatModel,
        knowledge_query_options: KnowledgeSettings,
        chat_history: list[BaseMessage],
        kb_retriever: BkRetriever | None = None,
    ):
        """初始化知识库检索节点。

        Args:
            llm: 语言模型
            knowledge_query_options: 知识库检索配置
            kb_retriever: 可选的知识库检索器，如不提供则创建默认实例
        """
        self.llm = llm
        self.knowledge_query_options = knowledge_query_options
        self.chat_history = chat_history
        self.kb_retriever = kb_retriever or BkRetriever()
        self.retriever = KnowledgeRag(llm, self.kb_retriever)

    def get_query(self, state: KnowledgeInputState) -> str:
        """从 state 中获取查询文本。

        优先级: query > input > messages[-1].content

        Args:
            state: 输入状态

        Returns:
            查询文本
        """
        query = state.get("query")
        if query is None:
            query = state.get("input")
        if query is None:
            messages = state.get("messages")
            if messages:
                query = messages[-1].content
        return normalize_query_for_search(query)


class AgentKnowledgeNode(BaseKnowledgeNode):
    """Agent 知识库召回阶段的节点实现。

    用于 Agent 对话流程中的知识库召回，会：
    - 派发 REFERENCE_DOCUMENT 事件供前端流式协议使用
    - 将 reference_doc 写入 LangGraph Store 方便后续节点读取
    - 返回包含 messages 的完整状态（包含 ActivityMessage）
    """

    def __call__(
        self,
        state: KnowledgeInputState,
        config: RunnableConfig,
        *,
        store,
    ) -> KnowledgeOutputState:
        """执行知识库检索节点。

        Args:
            state: 输入状态
            config: Runnable 配置
            store: LangGraph Store 实例

        Returns:
            输出状态
        """
        t1 = time.time()
        dispatch_custom_event(
            CustomMessageType.KNOWLEDGE_RAG_START.value,
            data={},
            config=config,
        )

        query = self.get_query(state)
        ret = self.retriever.retrieve(query, self.knowledge_query_options, self.chat_history, input=query)

        duration = round(time.time() - t1, 4) * 1000
        result = self.process_result(ret, config, store, duration)

        dispatch_custom_event(
            CustomMessageType.KNOWLEDGE_RAG_END.value,
            data={},
            config=config,
        )
        return result

    def process_result(
        self,
        ret: KnowledgeRagRetrieveResult,
        config: RunnableConfig,
        store: Any,
        duration: float,
    ) -> KnowledgeOutputState:
        """处理检索结果，生成 Agent 对话所需的输出状态。

        包含引用文档事件派发、Store 写入和 ActivityMessage 生成。

        Args:
            ret: 知识库检索结果
            config: Runnable 配置
            store: LangGraph Store 实例
            duration: 检索耗时（毫秒）

        Returns:
            包含 messages、reference_doc 等信息的输出状态
        """
        reference_doc = ret.get("reference_doc") or []
        message_id = uuid.uuid4().hex

        if reference_doc:
            # 处理引用文档
            reference_doc = [each["metadata"] for each in reference_doc]
            reference_doc = [
                {"originFile": each["preview_path"], "url": each["path"], "name": each["display_name"]}
                for each in reference_doc
            ]
        # 流处理：通过自定义事件向前端推送 reference_doc
        # 如果没有引用文档, 派发空消息，此时 reference_doc 为 []
        dispatch_custom_event(
            CustomMessageType.KNOWLEDGE_RAG_RESULT.value,
            data={"message_id": message_id, "data": reference_doc, "duration": duration},
            config=config,
        )
        # 流处理：为 messages 提供 ActivityMessage
        ret = cast(KnowledgeOutputState, ret)
        ret["messages"] = [
            ActivityMessage(
                activity_type=ActivityType.REFERENCE_DOCUMENT.value,
                content=reference_doc,
                id=message_id,
                additional_kwargs={"duration": duration},
            )
        ]
        return ret


class AidevKnowledgeNode(BaseKnowledgeNode):
    """AIDev 产品页面检索测试的节点实现。

    用于 AIDev 产品页面的知识库检索测试场景 (force_process_by_agent=True)，会：
    - 返回 knowledge_resources_emb_recalled（所有召回资源，带细粒度分数）
    - 返回 retrieved_docs（根据分数阈值过滤后的 topk 文档）
    """

    def __init__(
        self,
        llm: BaseChatModel,
        knowledge_query_options: KnowledgeSettings | None = None,
        kb_retriever: BkRetriever | None = None,
        score_threshold: float | None = None,
        topk: int = 20,
        chat_history: list[BaseMessage] | None = None,
        **kwargs,
    ):
        """初始化 AIDev 产品页面检索测试节点。

        Args:
            llm: 语言模型
            knowledge_query_options: 知识库检索配置
            kb_retriever: 可选的知识库检索器
            score_threshold: 分数阈值，用于过滤 retrieved_docs
            topk: 返回的最大文档数量
            chat_history: 查询预处理使用的会话历史
        其他：
            with_scalar_data 参数应该由 knowledge_query_options.with_scalar_data 进行调整
        """
        if knowledge_query_options is None:
            agent_options = kwargs.get("agent_options")
            if agent_options is None:
                raise ValueError("knowledge_query_options is required when agent_options is not provided")
            knowledge_query_options = migration_knowledge_query_options_from_agent_options_v1(agent_options)

        super().__init__(llm, knowledge_query_options, chat_history or [], kb_retriever)
        self.score_threshold = score_threshold
        self.topk = topk

    def __call__(
        self,
        state: KnowledgeInputState,
        config: RunnableConfig,
        *,
        store,
    ) -> AidevKnowledgeOutputState:
        """bkai平台知识库检索节点
        Args:
            state: 输入状态
            config: Runnable 配置
            store: LangGraph Store 实例

        Returns:
            输出状态
        """
        query = self.get_query(state)
        ret = self.retriever.retrieve(query, self.knowledge_query_options, self.chat_history, input=query)
        # 获取所有 embedding 召回的资源（带细粒度分数）
        knowledge_resources_emb_recalled = ret.get("knowledge_resources_emb_recalled", [])

        # 根据分数阈值过滤并选择 topk 文档
        ret = cast(AidevKnowledgeOutputState, ret)
        ret["retrieved_docs"] = filter_and_select_topk(
            knowledge_resources_emb_recalled,
            self.score_threshold,
            self.topk,
            sort_key=resolve_display_sort_key(self.knowledge_query_options.knowledge_resource_fine_grained_score_type),
        )
        return ret


def make_knowledge_node(
    llm: BaseChatModel,
    knowledge_query_options: KnowledgeSettings,
    chat_history: Optional[list] = None,
):
    """构建知识库检索节点。
    Args:
        llm: 语言模型,用于知识库检索中的相关性判断和内容处理
        knowledge_query_options: 知识库检索配置

    Returns:
        可用于 LangGraph node 的 callable,接受 (state, config, *, store) 参数

    Note:
        如果 knowledge_query_options 中未配置知识库 (knowledge_bases 和 knowledge_items 均为空),
        实际检索时会根据配置返回空结果或抛出异常。
    """
    return AgentKnowledgeNode(
        llm=llm,
        knowledge_query_options=knowledge_query_options,
        chat_history=chat_history,
    )
