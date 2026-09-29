# -*- coding: utf-8 -*-
"""Tests for the SDK knowledge-query request adapter."""

import pytest
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.pydantic_models import KnowledgeSettings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


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
    assert retriever.query_payload["knowledge_base_id"] == [305]
    assert "qa_response_knowledge_base_id" not in retriever.query_payload
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


@pytest.mark.parametrize("topk", [1, 5, 13])
@pytest.mark.parametrize("channels", [["dense"], ["sparse"], ["dense", "sparse"]])
@pytest.mark.parametrize("mode", ["INIT", "REWRITE"])
def test_query_configuration_preserves_topk_channels_and_policy(topk, channels, mode):
    retriever = CapturingBkRetriever()
    settings = KnowledgeSettings(
        knowledge_resource_rough_recall_topk=topk,
        recall_channels=channels,
        independent_query_mode=mode,
        knowledge_template_id=7,
        knowledge_resource_fine_grained_score_type="EMBEDDING",
        knowledge_resource_reject_threshold=(0.2, 0.8),
    )
    retriever.query_knowledge("needle", settings, [HumanMessage(content="previous")])
    payload = retriever.query_payload
    assert payload["topk"] == payload["document_fragment_count"] == topk
    assert payload["recall_channels"] == channels
    assert payload["independent_query_mode"] == mode
    assert payload["knowledge_template_id"] == 7
    assert payload["knowledge_resource_fine_grained_score_type"] == "EMBEDDING"
    assert payload["knowledge_resource_reject_threshold"] == [0.2, 0.8]
    assert payload["chat_history"] == [{"role": "user", "content": "previous"}]


@pytest.mark.parametrize(
    "name",
    [
        "with_index_specific_search",
        "with_index_specific_search_init",
        "with_index_specific_search_translation",
        "with_query_cls",
        "merge_query_cls_with_resp_or_rewrite",
        "use_independent_query_in_translation",
        "use_translated_query_in_scores",
        "use_independent_query_in_scores",
    ],
)
@pytest.mark.parametrize("value", [False, True])
def test_query_strategy_is_transmitted(name, value):
    retriever = CapturingBkRetriever()
    retriever.query_knowledge("q", KnowledgeSettings(**{name: value}))
    assert retriever.query_payload["query_strategy"][name] is value


@pytest.mark.parametrize("document", [None, {}, {"metadata": []}, {"metadata": {}}])
def test_reject_malformed_documents(document):
    with pytest.raises(RuntimeError):
        BkRetriever._validate_documents([document])


def test_history_excludes_non_dialogue_messages():
    assert BkRetriever._serialize_chat_history([SystemMessage(content="private"), HumanMessage(content="q")]) == [
        {"role": "user", "content": "q"}
    ]


def test_transport_and_valid_document_validation(mocker):
    transport = mocker.Mock(return_value={"documents": [{"metadata": {"__score__": 0.8}}]})
    mocker.patch(
        "aidev_agent.packages.langchain_core.retrievers.bk_retriever.resource_manager"
    ).return_value.knowledge_query = transport
    result = BkRetriever().query_knowledge("q", KnowledgeSettings())
    assert result["documents"][0]["metadata"]["__score__"] == 0.8
    transport.assert_called_once()


@pytest.mark.parametrize(
    "field,value",
    [
        ("qa_response_kb_ids", []),
        ("qa_response_kb_ids", [2]),
        ("qa_response_knowledge_bases", []),
        ("qa_response_knowledge_bases", [{"id": 2}]),
    ],
)
@pytest.mark.parametrize("ordinary", [[], [{"id": 1}]])
def test_retired_qa_configuration_is_ignored(field, value, ordinary):
    settings = KnowledgeSettings(knowledge_bases=ordinary, **{field: value})
    retriever = CapturingBkRetriever()
    retriever.query_knowledge("q", settings)
    assert field not in settings.model_dump()
    assert "qa_response_knowledge_base_id" not in retriever.query_payload
    assert retriever.query_payload["knowledge_base_id"] == [base["id"] for base in ordinary]


def test_legacy_disabled_options_and_retired_expansions_are_not_sent():
    settings = KnowledgeSettings(
        qa_response_kb_ids=[],
        qa_response_knowledge_bases=[],
        with_index_specific_search_keywords=True,
        with_structured_data=True,
        with_es_search_query=True,
        with_es_search_keywords=True,
    )
    retriever = CapturingBkRetriever()
    retriever.query_knowledge("q", settings)
    assert "with_index_specific_search_keywords" not in retriever.query_payload["query_strategy"]
    assert "qa_response_knowledge_base_id" not in retriever.query_payload
    assert "with_structured_data" not in settings.model_dump()
