# -*- coding: utf-8 -*-
"""Tests for the SDK-to-WEB-API knowledge adapter."""

from unittest.mock import MagicMock

import pytest
from aidev_agent.core.graphs.react.graph import DefaultState
from aidev_agent.core.nodes.model.basic_middleware import get_context_type_from_state
from aidev_agent.enums import Decision
from aidev_agent.packages.langchain_core.retrievers.kb_rag import KnowledgeRag
from aidev_agent.pydantic_models import KnowledgeSettings
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


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


@pytest.mark.parametrize("decision", ["PRIVATE_QA", "QUERY_CLARIFICATION", "GENERAL_QA"])
def test_retrieve_preserves_api_order_thresholds_and_references(decision):
    documents = (
        [
            {"page_content": "first", "metadata": {"relevance_level": "high", "fine_grained_score": 0.01}},
            {"page_content": "second", "metadata": {"relevance_level": "high", "fine_grained_score": 0.99}},
        ]
        if decision != "GENERAL_QA"
        else []
    )
    api_result = {
        "documents": documents,
        "decision": decision,
        "knowledge_content": [doc["page_content"] for doc in documents],
        "reference_documents": [{"metadata": {"file_path": doc["page_content"]}} for doc in documents],
    }
    api_client = MagicMock()
    api_client.query_knowledge.return_value = api_result
    rag = KnowledgeRag(llm=MagicMock(), kb_retriever=api_client)

    result = rag.retrieve("query", KnowledgeSettings(knowledge_resource_rough_recall_topk=1))

    assert result["knowledge_resources_emb_recalled"] == documents
    assert result["reference_doc"] == api_result["reference_documents"]
    assert result["knowledge_content"] == api_result["knowledge_content"]
    assert result["decision"] == Decision(decision)
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
        with_es_search_keywords=True,
        with_structured_data=True,
    )

    result = knowledge_rag.retrieve("query", knowledge_settings)

    assert result["decision"] == Decision.GENERAL_QA
    api_client.query_knowledge.assert_called_once()


@pytest.mark.parametrize("legacy_input", [False, True])
def test_retrieve_keeps_raw_input_until_request_boundary(legacy_input):
    api_client = MagicMock()
    api_client.query_knowledge.return_value = {"documents": [], "decision": "GENERAL_QA"}
    knowledge_rag = KnowledgeRag(llm=MagicMock(), kb_retriever=api_client)
    multimodal_input = [
        {"type": "image_url", "image_url": {"url": "https://example.com/test.png"}},
        {"type": "text", "text": "蓝鲸是什么"},
    ]

    if legacy_input:
        knowledge_rag.retrieve("fallback", KnowledgeSettings(), input=multimodal_input)
    else:
        knowledge_rag.retrieve(multimodal_input, KnowledgeSettings())

    assert api_client.query_knowledge.call_args.args[0] == multimodal_input
    api_client.query_knowledge.assert_called_once()


@pytest.mark.parametrize("legacy_input", [False, True])
@pytest.mark.parametrize("supports_multimodal", [False, True])
def test_retrieve_applies_capability_at_real_request_boundary(mocker, legacy_input, supports_multimodal):
    manager = mocker.patch("aidev_agent.packages.langchain_core.retrievers.bk_retriever.resource_manager")
    request = manager.return_value.knowledge_query
    request.return_value = {"documents": [], "decision": "GENERAL_QA"}
    rag = KnowledgeRag(llm=MagicMock())
    options = KnowledgeSettings(supports_multimodal_query=supports_multimodal)
    content = [{"type": "text", "text": "query"}, {"type": "image_url", "image_url": "https://example.com/a.png"}]

    if legacy_input:
        rag.retrieve("fallback", options, input=content)
    else:
        rag.retrieve(content, options)

    request.assert_called_once()
    assert request.call_args.args[0]["query"] == (content if supports_multimodal else "query")


@pytest.mark.parametrize(
    "query, expected",
    [("蓝鲸是什么", "蓝鲸是什么"), ("", ""), (None, ""), (42, "42"), ({"text": "query"}, "{'text': 'query'}")],
)
def test_retrieve_normalizes_non_list_input_before_api_call(query, expected):
    api_client = MagicMock()
    api_client.query_knowledge.return_value = {"documents": [], "decision": "GENERAL_QA"}
    knowledge_rag = KnowledgeRag(llm=MagicMock(), kb_retriever=api_client)

    knowledge_rag.retrieve(query, KnowledgeSettings())

    api_client.query_knowledge.assert_called_once()
    assert api_client.query_knowledge.call_args.args[0] == expected


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


def test_api_conclusion_is_preserved():
    result = KnowledgeRag._map_api_response({"documents": [], "conclusion": "Goodbye"})
    assert result["response"] == "Goodbye"


def test_retired_qa_response_cannot_reactivate_special_context():
    result = KnowledgeRag._map_api_response(
        {
            "documents": [],
            "knowledge_content": ["ordinary row"],
            "knowledge_qa_content": ["retired QA"],
            "with_qa_response": True,
        }
    )
    assert result["knowledge_content"] == ["ordinary row"]
    assert result["knowledge_qa_content"] == []
    assert result["with_qa_response"] is False


@pytest.mark.parametrize("previous_qa", [[], ["previous QA"]])
@pytest.mark.parametrize("ordinary,context_type", [([], ""), (["ordinary row"], "private")])
def test_retrieval_clears_retired_qa_from_persisted_state(previous_qa, ordinary, context_type):
    graph = StateGraph(DefaultState)
    response = {"documents": [], "knowledge_content": ordinary}
    graph.add_node("knowledge", lambda state: KnowledgeRag._map_api_response(response))
    graph.add_edge(START, "knowledge")
    graph.add_edge("knowledge", END)
    compiled = graph.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "compatibility-thread"}}
    compiled.update_state(config, {"messages": [], "knowledge_qa_content": previous_qa, "with_qa_response": True})
    result = compiled.invoke({"messages": []}, config)
    assert result["knowledge_content"] == ordinary
    assert result["knowledge_qa_content"] == []
    assert result["with_qa_response"] is False
    assert get_context_type_from_state(result) == context_type
    assert compiled.get_state(config).values["knowledge_qa_content"] == []
