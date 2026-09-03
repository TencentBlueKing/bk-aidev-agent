# -*- coding: utf-8 -*-
"""Tests for the SDK-to-WEB-API knowledge adapter."""

from unittest.mock import MagicMock

import pytest
from aidev_agent.enums import Decision
from aidev_agent.packages.langchain_core.retrievers.kb_rag import KnowledgeRag
from aidev_agent.pydantic_models import KnowledgeSettings


@pytest.fixture(autouse=True)
def disable_rag_progress_events(mocker):
    mocker.patch("aidev_agent.packages.langchain_core.retrievers.kb_rag.dispatch_rag_event_chunk")


def test_retrieve_consumes_api_result_without_local_rerank():
    api_client = MagicMock()
    final_document = {
        "page_content": "content",
        "metadata": {"relevance_level": "high", "fine_grained_score": 0.8},
    }
    api_client.query_knowledge.return_value = {
        "documents": [final_document],
        "decision": "PRIVATE_QA",
        "knowledge_content": ["content"],
        "reference_documents": [{"metadata": {"file_path": "doc.md"}}],
    }
    knowledge_rag = KnowledgeRag(llm=MagicMock(model_name="fast-model"), kb_retriever=api_client)

    result = knowledge_rag.retrieve("query", KnowledgeSettings(knowledge_bases=[{"id": 1}]))

    assert result["decision"] == Decision.PRIVATE_QA
    assert result["knowledge_resources_emb_recalled"] == [final_document]
    assert result["reference_doc"] == [{"metadata": {"file_path": "doc.md"}}]
    api_client.query_knowledge.assert_called_once()


def test_retrieve_rejects_unknown_api_decision():
    api_client = MagicMock()
    api_client.query_knowledge.return_value = {"documents": [], "decision": "UNKNOWN"}
    knowledge_rag = KnowledgeRag(llm=MagicMock(), kb_retriever=api_client)

    with pytest.raises(ValueError):
        knowledge_rag.retrieve("query", KnowledgeSettings())


def test_retrieve_ignores_removed_sdk_recall_switches():
    api_client = MagicMock()
    api_client.query_knowledge.return_value = {"documents": [], "decision": "GENERAL_QA"}
    knowledge_rag = KnowledgeRag(llm=MagicMock(), kb_retriever=api_client)
    knowledge_settings = KnowledgeSettings(
        with_index_specific_search=False,
        with_index_specific_search_init=False,
        with_index_specific_search_translation=False,
        with_index_specific_search_keywords=False,
        with_es_search_query=False,
        with_es_search_keywords=False,
    )

    result = knowledge_rag.retrieve("query", knowledge_settings)

    assert result["decision"] == Decision.GENERAL_QA
    api_client.query_knowledge.assert_called_once()


def test_retrieve_normalizes_multimodal_input_before_api_call():
    api_client = MagicMock()
    api_client.query_knowledge.return_value = {"documents": [], "decision": "GENERAL_QA"}
    knowledge_rag = KnowledgeRag(llm=MagicMock(), kb_retriever=api_client)
    multimodal_input = [
        {"type": "image_url", "image_url": {"url": "https://example.com/test.png"}},
        {"type": "text", "text": "蓝鲸是什么"},
    ]

    knowledge_rag.retrieve("fallback", KnowledgeSettings(), input=multimodal_input)

    assert api_client.query_knowledge.call_args.args[0] == "蓝鲸是什么"


def test_retrieve_maps_api_relevance_groups_without_rescoring():
    api_client = MagicMock()
    api_client.query_knowledge.return_value = {
        "documents": [
            {"page_content": "high", "metadata": {"relevance_level": "high"}},
            {"page_content": "moderate", "metadata": {"relevance_level": "moderate"}},
        ],
        "decision": "PRIVATE_QA",
    }
    knowledge_rag = KnowledgeRag(llm=MagicMock(), kb_retriever=api_client)

    result = knowledge_rag.retrieve("query", KnowledgeSettings())

    assert [document["page_content"] for document in result["knowledge_resources_highly_relevant"]] == ["high"]
    assert [document["page_content"] for document in result["knowledge_resources_moderately_relevant"]] == ["moderate"]
