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
from typing import TYPE_CHECKING, Annotated, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.packages.langchain_core.retrievers.kb_rag import KnowledgeRag
from aidev_agent.pydantic_models import KnowledgeSettings

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


class KnowledgeRetrievalInput(BaseModel):
    """知识库检索工具的输入参数"""

    query: Annotated[str, "用于检索私域知识库的查询文本"]


def make_knowledge_retrieval_tool(
    llm: BaseChatModel,
    knowledge_query_options: KnowledgeSettings,
    chat_history: Optional[list] = None,
) -> Optional[StructuredTool]:
    """构建知识库检索工具。

    该工具将知识库检索功能封装为 StructuredTool，使 LLM 能够在推理过程中
    动态决定是否进行知识库检索，实现 Agentic RAG 能力。

    Args:
        llm: 语言模型，用于知识库检索中的相关性判断和内容处理
        knowledge_query_options: 知识库检索配置
        chat_history: 聊天历史记录

    Returns:
        StructuredTool 实例，如果未配置知识库则返回 None

    Example:
        >>> tool = make_knowledge_retrieval_tool(llm, knowledge_query_options)
        >>> if tool:
        ...     result = tool.invoke({"query": "如何部署蓝鲸平台？"})
    """
    # 如果没有配置知识库，返回 None
    if not knowledge_query_options.knowledge_bases and not knowledge_query_options.knowledge_items:
        return None

    # 提取知识库名称，用于丰富工具描述
    kb_names = []
    if knowledge_query_options.knowledge_bases:
        kb_names = [kb.get("name", "") for kb in knowledge_query_options.knowledge_bases if kb.get("name")]
    
    # 构建工具描述
    base_description = "检索私域知识库以获取相关信息。当需要查询企业内部知识、文档或历史问答时使用此工具。"
    if kb_names:
        kb_names_str = "、".join(kb_names)
        description = f"{base_description}\n当前可检索的知识库名称包括：{kb_names_str}"
    else:
        description = base_description

    def knowledge_retrieval(query: str) -> list:
        """执行知识库检索。

        Args:
            query: 用于检索私域知识库的查询文本

        Returns:
            包含检索决策、知识内容和引用文档的结构化结果
        """
        # 初始化知识库检索器
        kb_retriever = BkRetriever()
        retriever = KnowledgeRag(llm, kb_retriever)

        # 执行知识库检索
        ret = retriever.retrieve(query, knowledge_query_options, input=query, chat_history=chat_history)
        return ret.get("knowledge_content", [])

    return StructuredTool.from_function(
        func=knowledge_retrieval,
        name="knowledge_retrieval",
        description=description,
        args_schema=KnowledgeRetrievalInput,
        metadata={"tool_name": "知识库检索"},
    )
