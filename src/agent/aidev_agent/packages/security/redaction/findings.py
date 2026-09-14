# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.redaction.findings

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

命中模型与 span 合并。

所有 detector 扫描**同一份原始文本**，各自产出
``Finding(start, end, rule_id, kind, confidence, priority)``；重叠区间合并为 union 后
**一次性替换**，替换与计数共享同一 ``ScanResult``。
这样消除历史实现「顺序正则改写 + 两套模式各自 findall」的口径漂移。

公开接口：``Confidence`` / ``Finding`` / ``ScanResult`` / ``merge_spans``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# 命中置信度档位
Confidence = Literal["exact", "high", "medium", "heuristic"]


@dataclass(frozen=True)
class Finding:
    """单条命中（只保留位置与非敏感元数据，绝不保存原文）。

    Args:
        start: 命中区间起始偏移（闭）。
        end: 命中区间结束偏移（开）。
        rule_id: 产出该命中的规则标识（如 ``vendor.openai``）。
        kind: 凭据类型标签（如 ``gpg_key`` / ``vendor_token``）。
        confidence: 置信度档位。
        priority: 优先级（区间重叠合并时保留最高者的元数据）。
    """

    start: int
    end: int
    rule_id: str
    kind: str
    confidence: Confidence
    priority: int


@dataclass(frozen=True)
class ScanResult:
    """一次扫描的完整结果（脱敏文本 + 计数）。

    Args:
        redacted_text: 替换后的文本。
        unique_findings: **合并后**的 cluster 数。
        raw_rule_hits: **合并前**按 ``rule_id`` 的原始命中计数。
    """

    redacted_text: str
    unique_findings: int
    raw_rule_hits: dict[str, int]


def merge_spans(findings: list[Finding]) -> list[Finding]:
    """按 ``start`` 升序稳定排序后，把重叠区间并成 union。

    仅当 ``next.start < cur.end``（真重叠）时合并；``next.start >= cur.end``
    （相邻但不重叠）必须保持独立，不得错误合并。

    union 内保留 ``priority`` 最高的 finding 的 ``rule_id`` / ``kind`` /
    ``confidence``；**``priority`` 相等时保留靠前者（更靠左的那个）** —— 代码为
    ``winner = last if last.priority >= current.priority else current``，等号归
    ``last`` 一侧。位置字段始终取 union 的并集（``start`` 取更小、``end`` 取更大），
    与胜者的优先级无关。
    """
    if not findings:
        return []

    ordered = sorted(findings, key=lambda f: f.start)
    merged: list[Finding] = [ordered[0]]
    for current in ordered[1:]:
        last = merged[-1]
        if current.start < last.end:
            # 真重叠 → 并成 union，保留 priority 最高者的非位置元数据
            winner = last if last.priority >= current.priority else current
            merged[-1] = Finding(
                start=last.start,
                end=max(last.end, current.end),
                rule_id=winner.rule_id,
                kind=winner.kind,
                confidence=winner.confidence,
                priority=winner.priority,
            )
        else:
            merged.append(current)
    return merged


__all__ = [
    # 置信度档位
    "Confidence",
    # 命中模型
    "Finding",
    "ScanResult",
    # span 合并
    "merge_spans",
]
