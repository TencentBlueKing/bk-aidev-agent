# -*- coding: utf-8 -*-
"""``RuleSpec.resolve_predicate`` 的判定真源：**verdict 来自 ``spec``，不是硬编码**。

本文件承载阶段 13 的核心可证伪证据（``13-RESEARCH.md`` Question G 的 T1 与 M5）。

为什么需要它：``resolve_predicate`` 全仓**零直接测试**（``grep -rn "resolve_predicate" tests/``
零命中），故它的签名与行为改动**不会打红任何既有测试**。没有本文件，本阶段的重构
既无保护也无证据。

失效模式（本文件要钉住的）：``resolve_predicate`` 的 pattern 派生路径曾把
``verdict="block"`` 写死，任何 ``verdict="allow"`` / ``"review"`` 的规则经它装配后
命中会被静默翻成 ``block``。今天的生产代码恰好没有这类调用（``allowlist:allowed``
的谓词是直接赋值的 ``_allowed_hits``，不经 ``resolve_predicate``），故该缺陷是
**latent**：没有「某个命令输出变了」这种端到端信号。唯一诚实的证据是在**测试内**
构造一条走该路径的 allow 规则。

``_make_rule_resolver`` 是本文件被测的 resolver（住在 ``command_blocklist``，复用其
``_rule_name_of`` / ``_rule_args_of``）。测试直取私有符号是本项目既有惯例
（``test_command_blocklist.py`` 直调 ``_DATA_PREDICATE_NAMES`` / ``_predicate_reads_spec_pattern``）。
"""

from __future__ import annotations

import pytest
from aidev_agent.packages.security.command.command_blocklist import _make_rule_resolver
from aidev_agent.packages.security.command.command_definitions import (
    Pattern,
    RuleContext,
    RuleHit,
    RuleResolver,
    RuleSpec,
    names,
)
from tests.packages.security.command._walk_helpers import _walk_source_text


def _resolver() -> RuleResolver:
    """取 ``command_blocklist._make_rule_resolver``（模块级已导入）。"""
    return _make_rule_resolver


def _first_hit(text: str, spec: RuleSpec) -> RuleHit | None:
    """对 ``text`` 真实遍历，用 ``spec`` 的谓词判定，返回首个 hit（无命中返回 None）。"""
    walked, _ = _walk_source_text(text)
    context = RuleContext(walked=walked, entry=walked.entries[0])
    hits = spec.predicate(context)
    return hits[0] if hits else None


def _spec(verdict: str, *, rule_id: str = "r", token: str = "rm") -> RuleSpec:
    """一条带 pattern 的规则，经 ``_make_rule_resolver`` 装配好谓词。"""
    return RuleSpec(
        rule_id=rule_id,
        category="c",
        verdict=verdict,  # type: ignore[arg-type]
        justification="why",
        pattern=Pattern(tokens=(names(token),)),
    ).resolve_predicate(resolver=_resolver())


class TestResolvePredicateDerivesVerdictFromSpec:
    """**机制层可证伪**：派生谓词的判定取自 ``spec.verdict``。

    这是 ``13-RESEARCH.md`` Question G 的 T1。它在修复前 **RED**、修复后 **GREEN** ——
    本阶段不存在端到端行为变化，这是唯一能证明「改动真的修好了什么」的证据。
    """

    @pytest.mark.parametrize("verdict", ["allow", "block", "review"])
    def test_derived_verdict_equals_spec_verdict(self, verdict):
        """三方对照：``allow`` / ``block`` / ``review`` 都必须原样透出。

        为什么必须三方而非只用 ``block``：硬编码 ``"block"`` 的实现会在
        ``verdict="block"`` 的用例上**全绿**，只有非 block 的两条可证伪它。
        """
        hit = _first_hit("rm -rf /tmp", _spec(verdict))
        assert hit is not None, "pattern 应命中 rm"
        assert hit.verdict == verdict, f"派生谓词把 spec.verdict={verdict!r} 改成了 {hit.verdict!r}"

    def test_verdict_is_read_per_spec_not_a_constant(self):
        """同一 resolver、同 pattern、仅 verdict 不同的两条 spec 产出不同判决。"""
        allow_hit = _first_hit("rm -rf /tmp", _spec("allow", rule_id="r"))
        block_hit = _first_hit("rm -rf /tmp", _spec("block", rule_id="r"))
        assert allow_hit is not None and block_hit is not None
        assert allow_hit.verdict == "allow"
        assert block_hit.verdict == "block"
        assert allow_hit.verdict != block_hit.verdict

    def test_control_group_non_matching_command_yields_no_hit(self):
        """对照组（证明上面的断言不是恒真）：不命中即空序列。"""
        assert _first_hit("ls", _spec("allow", token="rm")) is None


class TestResolvePredicateOnAllowRuleKeepsAllow:
    """**M5 反证实验**：模拟「有人把 allow 规则接到 ``resolve_predicate`` 上」。

    今天的生产代码**不做**这件事（``ALLOWLIST_RULES`` 的谓词是直接赋值的手写
    ``_allowed_hits``，从不经 ``resolve_predicate``）。本类在**测试内**做这件事，
    把 latent 失效面转成一个可运行的实验：

    - 修复前：派生谓词带 ``verdict="block"``，与手写谓词取并集后 block 命中先入
      ``seen``，allow 命中因同键被 dedup 丢弃 ⇒ 净结果 **block**（RED）。
    - 修复后：派生谓词带 ``verdict="allow"``，两条命中判定一致 ⇒ 净结果 **allow**（GREEN）。

    ⚠ **必须在测试内局部构造，不得改生产代码**：真把 ``ALLOWLIST_RULES`` 改成走
    ``resolve_predicate`` 会引入 union 形状，改变 ``allowlist:allowed`` 谓词的
    ``__name__``（``_allowed_hits`` → ``_union_allowlist:allowed``），
    直接破坏 ``_DATA_PREDICATE_NAMES`` 判据与行为指纹（P13-I4）。
    """

    def test_union_of_derived_and_handwritten_allow_keeps_allow(self):
        """派生谓词与自带 allow 谓词取并集后，命中 verdict 仍是 ``allow``。

        这是 ``_union_predicates`` 的派发顺序（``[pattern 派生, 自带, extra]``）与
        去重键 ``(rule_id, owner_entry_id, span)`` 的联合验证：两条谓词对同一 entry
        产出同键命中时，**先入者的 verdict 决定结果**。派生谓词排第一，故它的 verdict
        必须正确，否则 allow 被吞。
        """

        def handwritten_allow(context: RuleContext):
            entry = context.entry
            if entry is None:
                return ()
            return (RuleHit(rule_id="r", verdict="allow", reason="allow", owner_entry_id=entry.entry_id),)

        spec = RuleSpec(
            rule_id="r",
            category="c",
            verdict="allow",
            justification="why",
            pattern=Pattern(tokens=(names("rm"),)),
            predicate=handwritten_allow,
        ).resolve_predicate(resolver=_resolver())

        hit = _first_hit("rm -rf /tmp", spec)
        assert hit is not None
        assert hit.verdict == "allow", (
            "union 后 allow 被吞成 block —— 派生谓词仍带硬编码 block，或 union 派发顺序被改（派生谓词必须在最前）"
        )
