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

from typing import Optional, TypedDict

from typing_extensions import NotRequired

from aidev_agent.enums import Decision
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.packages.langchain_core.retrievers.utils import dispatch_rag_event_chunk, normalize_query_for_search
from aidev_agent.pydantic_models import KnowledgeSettings


class KnowledgeRagRetrieveResult(TypedDict):
    """Agent state mapped from the WEB API knowledge-query response."""

    decision: Decision
    knowledge_resources_highly_relevant: list
    knowledge_resources_moderately_relevant: list
    knowledge_resources_lowly_relevant: list
    knowledge_resources_emb_recalled: NotRequired[list]
    knowledge_content: NotRequired[list]
    knowledge_qa_content: NotRequired[list]
    with_qa_response: NotRequired[bool]
    reference_doc: NotRequired[list]
    response: NotRequired[str]


class KnowledgeRag:
    """Thin SDK adapter for the WEB API knowledge-query contract."""

    def __init__(self, llm=None, kb_retriever: BkRetriever | None = None) -> None:
        self.llm = llm or ChatModel.get_setup_instance(model="hunyuan-turbo")
        self.kb_retriever = kb_retriever or BkRetriever()

    def retrieve(
        self, query: str, knowledge_query_options: KnowledgeSettings, chat_history: Optional[list] = None, **kwargs
    ) -> KnowledgeRagRetrieveResult:
        """Submit one API request and map the final knowledge result to Agent state."""

        dispatch_rag_event_chunk("开始召回知识")
        llm = kwargs.get("llm", self.llm)
        llm_code = getattr(llm, "model_name", None) or getattr(llm, "model", None)
        response = kwargs.get("kb_retriever", self.kb_retriever).query_knowledge(
            normalize_query_for_search(kwargs.get("input", query)),
            knowledge_query_options,
            chat_history,
            llm_code=llm_code if isinstance(llm_code, str) else None,
        )
        mapped_result = self._map_api_response(response)
        dispatch_rag_event_chunk("完成召回并分类")
        return mapped_result

    @classmethod
    def _map_api_response(cls, response: dict) -> KnowledgeRagRetrieveResult:
        documents = response.get("documents") or []
        relevance_groups = cls._group_documents_by_relevance(documents)
        mapped_result = KnowledgeRagRetrieveResult(
            decision=Decision(response.get("decision") or ("PRIVATE_QA" if documents else "GENERAL_QA")),
            knowledge_resources_highly_relevant=relevance_groups["high"],
            knowledge_resources_moderately_relevant=relevance_groups["moderate"],
            knowledge_resources_lowly_relevant=relevance_groups["low"],
            knowledge_resources_emb_recalled=documents,
            knowledge_content=response.get("knowledge_content") or [],
            knowledge_qa_content=response.get("knowledge_qa_content") or [],
            with_qa_response=bool(response.get("with_qa_response")),
            reference_doc=response.get("reference_documents") or [],
        )
        if response.get("conclusion"):
            mapped_result["response"] = response["conclusion"]
        return mapped_result

    @staticmethod
    def _group_documents_by_relevance(documents: list[dict]) -> dict[str, list[dict]]:
        relevance_groups = {"high": [], "moderate": [], "low": []}
        for document in documents:
            relevance_level = document.get("metadata", {}).get("relevance_level", "high")
            relevance_groups[relevance_level if relevance_level in relevance_groups else "high"].append(document)
        return relevance_groups
