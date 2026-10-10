# -*- coding: utf-8 -*-
"""Tests for Finding span model and merge semantics (aidev_agent.packages.security.redaction.findings)."""

from __future__ import annotations

import pytest
from aidev_agent.packages.security.redaction.findings import (
    Finding,
    ScanResult,
    merge_spans,
)


def _f(start: int, end: int, rule_id: str = "r", kind: str = "k", priority: int = 50) -> Finding:
    """构造 finding 的测试辅助（confidence 固定 exact）。"""
    return Finding(start=start, end=end, rule_id=rule_id, kind=kind, confidence="exact", priority=priority)


class TestMergeSpans:
    """重叠区间并成 union；相邻但不重叠必须保持独立。"""

    @pytest.mark.parametrize(
        "spans, expected",
        [
            # 完全重叠 → 单一 union
            ([(0, 10), (0, 10)], [(0, 10)]),
            # 部分重叠 → 单一 union
            ([(0, 10), (5, 15)], [(0, 15)]),
            # 相邻但不重叠 → 保持 2 个
            ([(0, 10), (10, 20)], [(0, 10), (10, 20)]),
            # 乱序输入 → 按 start 升序稳定排序
            ([(10, 20), (0, 5)], [(0, 5), (10, 20)]),
            # 单个 finding
            ([(3, 7)], [(3, 7)]),
            # 空列表
            ([], []),
        ],
    )
    def test_merge(self, spans, expected):
        findings = [_f(s, e) for s, e in spans]
        merged = merge_spans(findings)
        assert [(f.start, f.end) for f in merged] == expected

    def test_overlap_keeps_highest_priority_metadata(self):
        """union 内保留 priority 最高者的 rule_id/kind。"""
        findings = [_f(0, 10, rule_id="low", priority=10), _f(5, 15, rule_id="high", priority=90)]
        merged = merge_spans(findings)
        assert len(merged) == 1
        assert merged[0].rule_id == "high"
        assert merged[0].priority == 90

    def test_adjacent_not_merged_keeps_both(self):
        merged = merge_spans([_f(0, 10, rule_id="a"), _f(10, 20, rule_id="b")])
        assert {f.rule_id for f in merged} == {"a", "b"}


class TestScanResult:
    """ScanResult 契约：unique_findings 为合并后 cluster 数，raw_rule_hits 按合并前计数。"""

    def test_unique_findings_after_merge(self):
        raw = [_f(0, 10, rule_id="a"), _f(5, 15, rule_id="b")]
        merged = merge_spans(raw)
        result = ScanResult(redacted_text="x", unique_findings=len(merged), raw_rule_hits={"a": 1, "b": 1})
        assert result.unique_findings == 1

    def test_raw_rule_hits_counts_pre_merge_hits(self):
        """同一 rule_id 出现两次 → 计两次（合并前口径）。"""
        raw = [_f(0, 10, rule_id="dup"), _f(10, 20, rule_id="dup")]
        hits: dict[str, int] = {}
        for f in raw:
            hits[f.rule_id] = hits.get(f.rule_id, 0) + 1
        result = ScanResult(redacted_text="x", unique_findings=len(merge_spans(raw)), raw_rule_hits=hits)
        assert result.raw_rule_hits == {"dup": 2}
        assert result.unique_findings == 2
