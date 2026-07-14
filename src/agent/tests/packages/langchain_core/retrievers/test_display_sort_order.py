# -*- coding: utf-8 -*-
"""展示排序按 fine_grained_score_type 分流的单测。

覆盖点②：EMBEDDING（「保留原始顺序」）应尊重资源侧多路 RRF 融合顺序（含 BM25 词法通道），
按 ``rrf_score`` 排序，而不是按各通道量纲不一的 ``fine_grained_score`` 重排导致 BM25 精确命中
被挤到 top2；LLM / EXCLUSIVE_SIMILARITY_MODEL 仍按 ``fine_grained_score`` 重排。
拒答分级仍固定用 ``fine_grained_score``，不受影响。
"""

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
        (FineGrainedScoreType.EMBEDDING, "rrf_score"),
        (FineGrainedScoreType.LLM, "fine_grained_score"),
        (FineGrainedScoreType.EXCLUSIVE_SIMILARITY_MODEL, "fine_grained_score"),
        ("EMBEDDING", "rrf_score"),
        ("LLM", "fine_grained_score"),
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


def test_dedup_embedding_orders_by_rrf_score():
    # BM25 精确命中：rrf 更高但 embedding 相似度更低（量纲不同）。
    docs = [
        _doc("a", "u_a", fine_grained_score=0.90, rrf_score=0.20),  # 语义相近但非目标
        _doc("b", "u_b", fine_grained_score=0.55, rrf_score=0.80),  # BM25 精确命中，应排 top1
    ]
    ordered = deduplicate_knowledge_file_paths(docs, sort_key=resolve_display_sort_key(FineGrainedScoreType.EMBEDDING))
    assert [d["metadata"]["uid"] for d in ordered] == ["u_b", "u_a"]


def test_dedup_llm_orders_by_fine_grained_score():
    docs = [
        _doc("a", "u_a", fine_grained_score=0.90, rrf_score=0.20),
        _doc("b", "u_b", fine_grained_score=0.55, rrf_score=0.80),
    ]
    ordered = deduplicate_knowledge_file_paths(docs, sort_key=resolve_display_sort_key(FineGrainedScoreType.LLM))
    assert [d["metadata"]["uid"] for d in ordered] == ["u_a", "u_b"]


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


def test_filter_topk_embedding_orders_by_rrf_but_threshold_uses_fine_grained():
    docs = [
        _doc("a", "u_a", fine_grained_score=0.90, rrf_score=0.20),
        _doc("b", "u_b", fine_grained_score=0.55, rrf_score=0.80),
        _doc("c", "u_c", fine_grained_score=0.05, rrf_score=0.99),  # 阈值过滤掉（fine_grained 太低）
    ]
    result = filter_and_select_topk(
        docs,
        score_threshold=0.1,
        topk=10,
        sort_key=resolve_display_sort_key(FineGrainedScoreType.EMBEDDING),
    )
    uids = [d["metadata"]["uid"] for d in result]
    assert "u_c" not in uids  # 拒答阈值仍用 fine_grained_score
    assert uids == ["u_b", "u_a"]  # 展示顺序用 rrf_score
