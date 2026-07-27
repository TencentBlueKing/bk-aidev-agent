import pytest
from aidev_agent.enums import FineGrainedScoreType
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.pydantic_models import KnowledgeSettings


@pytest.mark.parametrize(
    "rrf_weights",
    [
        {"dense": 1.0, "sparse": 0.0},
        {"dense": 0.0, "sparse": 1.0},
    ],
)
def test_index_specific_search_forwards_extreme_rrf_weights(monkeypatch, rrf_weights):
    captured_payload = {}

    def capture_request(_self, request_payload):
        captured_payload.update(request_payload)
        return []

    monkeypatch.setattr(BkRetriever, "_search_knowledge_by_client", capture_request)
    retriever = BkRetriever()
    knowledge_options = KnowledgeSettings(rrf_weights=rrf_weights)

    retriever.search_knowledge_index_specific(
        knowledge_items=[],
        knowledge_bases=[
            {
                "id": 26,
                "index_config": {
                    "vector_indexes": [{"index_name": "gid", "index_type": "vector-multi_column"}],
                },
            }
        ],
        query="error_code=154140707",
        topk=13,
        knowledge_query_options=knowledge_options,
    )

    assert captured_payload["rrf_weights"] == rrf_weights


def test_index_specific_search_forwards_scalar_and_explicit_empty_vector_channels(monkeypatch):
    captured_payload = {}

    def capture_request(_self, request_payload):
        captured_payload.update(request_payload)
        return []

    monkeypatch.setattr(BkRetriever, "_search_knowledge_by_client", capture_request)
    retriever = BkRetriever()
    knowledge_options = KnowledgeSettings(
        recall_channels=[],
        scalar_expression='eq("status", "enabled")',
    )

    retriever.search_knowledge_index_specific(
        knowledge_items=[],
        knowledge_bases=[
            {
                "id": 26,
                "index_config": {
                    "vector_indexes": [{"index_name": "full_text", "index_type": "vector-multi_column"}],
                },
            }
        ],
        query="",
        topk=7,
        knowledge_query_options=knowledge_options,
    )

    assert captured_payload["recall_channels"] == []
    assert captured_payload["scalar"] == {"expression": 'eq("status", "enabled")'}


def test_index_specific_search_omits_channels_when_not_configured(monkeypatch):
    captured_payload = {}

    def capture_request(_self, request_payload):
        captured_payload.update(request_payload)
        return []

    monkeypatch.setattr(BkRetriever, "_search_knowledge_by_client", capture_request)
    retriever = BkRetriever()

    retriever.search_knowledge_index_specific(
        knowledge_items=[],
        knowledge_bases=[],
        query="legacy",
        topk=5,
        knowledge_query_options=KnowledgeSettings(),
    )

    assert "recall_channels" not in captured_payload
    assert "scalar" not in captured_payload


def test_index_specific_search_forces_dense_channel_for_embedding(monkeypatch):
    captured_payload = {}
    monkeypatch.setattr(
        BkRetriever, "_search_knowledge_by_client", lambda _self, data: captured_payload.update(data) or []
    )

    BkRetriever().search_knowledge_index_specific(
        knowledge_items=[],
        knowledge_bases=[],
        query="legacy",
        topk=5,
        knowledge_query_options=KnowledgeSettings(
            knowledge_resource_fine_grained_score_type=FineGrainedScoreType.EMBEDDING
        ),
    )

    assert captured_payload["recall_channels"] == ["dense"]
