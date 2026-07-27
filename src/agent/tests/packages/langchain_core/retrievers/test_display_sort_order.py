# -*- coding: utf-8 -*-
"""细粒度评分策略对应的展示排序单测。"""

import pytest
from aidev_agent.enums import FineGrainedScoreType
from aidev_agent.packages.langchain_core.retrievers.utils import (
    deduplicate_knowledge_file_paths,
    filter_and_select_topk,
    resolve_display_sort_key,
)


@pytest.mark.parametrize(
    "score_type, expected",
    [
        (FineGrainedScoreType.LLM, "fine_grained_score"),
        (FineGrainedScoreType.EXCLUSIVE_SIMILARITY_MODEL, "fine_grained_score"),
        (FineGrainedScoreType.EMBEDDING, "fine_grained_score"),
        (FineGrainedScoreType.ORIGINAL, None),
        ("LLM", "fine_grained_score"),
        ("ORIGINAL", None),
        (None, "fine_grained_score"),
    ],
)
def test_resolve_display_sort_key(score_type, expected):
    assert resolve_display_sort_key(score_type) == expected


def _doc(file_path, uid, fine_grained_score, rrf_score=None):
    metadata = {"file_path": file_path, "uid": uid, "fine_grained_score": fine_grained_score}
    if rrf_score is not None:
        metadata["rrf_score"] = rrf_score
    return {"metadata": metadata}


def test_dedup_scored_mode_orders_by_fine_grained_score():
    docs = [
        _doc("a", "u_a", fine_grained_score=0.90, rrf_score=0.20),
        _doc("b", "u_b", fine_grained_score=0.55, rrf_score=0.80),
    ]
    ordered = deduplicate_knowledge_file_paths(docs, sort_key=resolve_display_sort_key(FineGrainedScoreType.LLM))
    assert [d["metadata"]["uid"] for d in ordered] == ["u_a", "u_b"]


def test_dedup_original_mode_preserves_recall_order():
    docs = [
        _doc("b", "u_b", fine_grained_score=0.55, rrf_score=0.80),
        _doc("a", "u_a", fine_grained_score=0.90, rrf_score=0.20),
    ]
    ordered = deduplicate_knowledge_file_paths(docs, sort_key=resolve_display_sort_key(FineGrainedScoreType.ORIGINAL))
    assert [d["metadata"]["uid"] for d in ordered] == ["u_b", "u_a"]


def test_dedup_default_is_fine_grained_score():
    docs = [
        _doc("a", "u_a", fine_grained_score=0.30, rrf_score=0.90),
        _doc("b", "u_b", fine_grained_score=0.70, rrf_score=0.10),
    ]
    ordered = deduplicate_knowledge_file_paths(docs)
    assert [d["metadata"]["uid"] for d in ordered] == ["u_b", "u_a"]


def test_dedup_rrf_missing_falls_back_no_regression():
    # rrf_score 缺失（旧数据/未透传）时，即使请求 rrf_score 也回退 fine_grained_score，保证无回归。
    docs = [
        _doc("a", "u_a", fine_grained_score=0.90),
        _doc("b", "u_b", fine_grained_score=0.55),
    ]
    ordered = deduplicate_knowledge_file_paths(docs, sort_key="rrf_score")
    assert [d["metadata"]["uid"] for d in ordered] == ["u_a", "u_b"]


def test_filter_topk_original_mode_preserves_recall_order_without_score_filter():
    docs = [
        _doc("b", "u_b", fine_grained_score=0.55, rrf_score=0.80),
        _doc("a", "u_a", fine_grained_score=0.90, rrf_score=0.20),
        _doc("c", "u_c", fine_grained_score=0.05, rrf_score=0.99),  # 阈值过滤掉（fine_grained 太低）
    ]
    result = filter_and_select_topk(
        docs,
        score_threshold=None,
        topk=10,
        sort_key=resolve_display_sort_key(FineGrainedScoreType.ORIGINAL),
    )
    uids = [d["metadata"]["uid"] for d in result]
    assert uids == ["u_b", "u_a", "u_c"]
