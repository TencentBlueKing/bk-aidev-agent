# -*- coding: utf-8 -*-
"""Tests for the SDK knowledge-query request adapter."""

import pytest
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.pydantic_models import KnowledgeSettings
from langchain_core.messages import AIMessage, HumanMessage


class CapturingBkRetriever(BkRetriever):
    def __init__(self):
        self.query_payload = None

    @property
    def _query_instance(self):
        def query(payload: dict) -> dict:
            self.query_payload = payload
            return {"documents": []}

        return query


def test_query_knowledge_sends_one_complete_api_request():
    retriever = CapturingBkRetriever()
    settings = KnowledgeSettings(
        knowledge_bases=[{"id": 305}],
        knowledge_items=[{"id": 99}],
        qa_response_kb_ids=[307],
        recall_channels=["dense", "sparse"],
        rrf_weights={"dense": 0.4, "sparse": 0.6},
    )

    response = retriever.query_knowledge(
        "errorcode是154140719",
        settings,
        [HumanMessage(content="previous question"), AIMessage(content="previous answer")],
        llm_code="fast-model",
    )

    assert response == {"documents": []}
    assert retriever.query_payload["type"] == "nature"
    assert retriever.query_payload["raw"] is False
    assert retriever.query_payload["knowledge_base_id"] == [305, 307]
    assert retriever.query_payload["qa_response_knowledge_base_id"] == [307]
    assert retriever.query_payload["knowledge_id"] == [99]
    assert retriever.query_payload["chat_history"] == [
        {"role": "user", "content": "previous question"},
        {"role": "assistant", "content": "previous answer"},
    ]
    assert retriever.query_payload["recall_channels"] == ["dense", "sparse"]
    assert retriever.query_payload["rrf_weights"] == {"dense": 0.4, "sparse": 0.6}
    assert retriever.query_payload["llm_code"] == "fast-model"


@pytest.mark.parametrize("rrf_weights", [{"dense": 1.0, "sparse": 0.0}, {"dense": 0.0, "sparse": 1.0}])
def test_query_knowledge_forwards_extreme_rrf_weights(rrf_weights):
    retriever = CapturingBkRetriever()

    retriever.query_knowledge("query", KnowledgeSettings(rrf_weights=rrf_weights))

    assert retriever.query_payload["rrf_weights"] == rrf_weights


def test_query_knowledge_forwards_scalar_filter_and_empty_vector_channels():
    retriever = CapturingBkRetriever()
    settings = KnowledgeSettings(recall_channels=[], scalar_expression='eq("status", "enabled")')

    retriever.query_knowledge("query", settings)

    assert retriever.query_payload["recall_channels"] == []
    assert retriever.query_payload["filter"] == {"scalar": [{"expression": 'eq("status", "enabled")'}]}


def test_query_knowledge_omits_unspecified_optional_fields():
    retriever = CapturingBkRetriever()

    retriever.query_knowledge("query", KnowledgeSettings(recall_channels=None, knowledge_template_id=None))

    assert "recall_channels" not in retriever.query_payload
    assert "knowledge_template_id" not in retriever.query_payload
