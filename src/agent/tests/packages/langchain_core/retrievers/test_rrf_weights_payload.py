from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.pydantic_models import KnowledgeSettings


def test_index_specific_search_forwards_100_percent_dense_rrf_weights(monkeypatch):
    captured_payload = {}

    def capture_request(_self, request_payload):
        captured_payload.update(request_payload)
        return []

    monkeypatch.setattr(BkRetriever, "_search_knowledge_by_client", capture_request)
    retriever = BkRetriever()
    knowledge_options = KnowledgeSettings(rrf_weights={"dense": 1.0, "sparse": 0.0})

    retriever.search_knowledge_index_specific(
        knowledge_items=[],
        knowledge_bases=[
            {
                "id": 26,
                "index_config": {
                    "vector_indexes": [{"index_name": "full_text", "index_type": "vector-bm25"}],
                },
            }
        ],
        query="error_code=154140707",
        topk=13,
        knowledge_query_options=knowledge_options,
    )

    assert captured_payload["rrf_weights"] == {"dense": 1.0, "sparse": 0.0}
