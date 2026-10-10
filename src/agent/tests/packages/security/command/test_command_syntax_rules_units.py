# -*- coding: utf-8 -*-
"""``command_syntax_rules`` 的**直接单元测试**。

本文件覆盖 10 条 ``syntax:*`` / ``ast:*`` 结构规则的谓词与它们专属的辅助函数
（``_root_nodes`` / ``_entry_name`` / ``_scan_span`` / ``_delimiter_boundaries`` /
``_modeled_substitution_offsets`` / ``_redirect_hits`` / ``_brace_expansion_*`` /
``_unquoted_segments`` / ``_script_operand``）。

策略：直接 import 并调用 ``command_syntax_rules`` 内部的函数/谓词，把模块自身的契约
钉住——这样重构内部实现时这些用例会先红，而不是被上层聚合逻辑掩盖。

遍历 / 词法 / 名字解析的口径属 ``command_parser``，其单测仍在
``test_command_parser_units.py``（如 ``has_unmodeled_execution`` / ``classify_word``）。

测试字符串只用于 ``bashlex.parse`` / 内部谓词，**从不执行**（无 subprocess / os.system）。
"""

from __future__ import annotations

import bashlex
import pytest
from aidev_agent.packages.security.command import command_parser as cp
from aidev_agent.packages.security.command import command_syntax_rules as csr
from aidev_agent.packages.security.command.command_definitions import CommandSource, RuleContext


def _parse(text: str) -> list:
    """真解析一段文本（只做 AST 构造，不执行）。"""
    return bashlex.parse(text)


def _walk(text: str) -> cp.WalkResult:
    """解析 + ``walk_nodes``，返回遍历产物（宽松预算，只测遍历语义）。"""
    limits = {"max_command_length": 100000, "max_nodes": 100000, "max_depth": 100, "max_reparse_depth": 8}
    source = CommandSource(0, None, None, text)
    result = cp.WalkResult(source=source)
    cp.walk_nodes(_parse(text), source=source, budget=cp.WalkBudget(**limits), result=result)
    return result


def _entry(result: cp.WalkResult, index: int = 0) -> cp.CommandEntry:
    return result.entries[index]


def _ctx(text: str, **kwargs) -> RuleContext:
    """构造 source 粒度的 ``RuleContext``（谓词不看 entry 时用）。"""
    return RuleContext(walked=_walk(text), entry=None, **kwargs)


# ========== 规则产出：重定向 / 大括号 / 参数守卫 ==========


class TestRedirectFindings:
    """重定向家族：按 ``type`` 分档到各自 rule_id，``/dev/null`` 精确豁免。"""

    @pytest.mark.parametrize(
        "text, expected_rule",
        [
            ("echo a > /tmp/o", "syntax:redirect"),
            ("echo a > /dev/nullx", "syntax:redirect"),
            ("ls < /dev/null", "syntax:redirect"),
            ("sort <<< hi", "syntax:herestring"),
            ("cat <<EOF\nhi\nEOF\n", "syntax:heredoc"),
        ],
    )
    def test_redirect_family_routes_to_its_rule_id(self, text, expected_rule):
        """经 spec 谓词派发到唯一 rule_id（与生产统一派发层同构），且 verdict 恒 ``block``。"""
        context = _ctx(text)
        spec = next(s for s in csr.SYNTAX_RULES if s.rule_id == expected_rule)
        hits = spec.predicate(context)
        assert [h.rule_id for h in hits] == [expected_rule]
        assert hits[0].verdict == "block"

    @pytest.mark.parametrize("text", ["ls > /dev/null", "ls 2> /dev/null", "ls >> /dev/null"])
    def test_exact_dev_null_target_is_exempt(self, text):
        """``>`` / ``>>`` / ``&>`` 且目标**精确** ``/dev/null`` 时豁免。"""
        context = _ctx(text)
        redirects = [n for n in csr._root_nodes(context.walked) if n.kind == "redirect"]
        assert [h for n in redirects for h in csr._redirect_hits(n, 0, context)] == []

    @pytest.mark.parametrize("text", ["cat <<EOF\nhi\nEOF\n", "sort <<< hi"])
    def test_redirect_hits_skips_heredoc_and_herestring(self, text):
        """``_redirect_hits`` 不处理 ``<<`` / ``<<<``——它们由各自的 spec 谓词产出。

        这是「一条 spec 一个谓词」的排他性契约：若 ``_redirect_hits`` 也产出这两种类型，
        同一节点会同时出现 ``:redirect`` 与 ``:heredoc``/``:herestring`` 两条命中。
        """
        context = _ctx(text)
        redirects = [n for n in csr._root_nodes(context.walked) if n.kind == "redirect"]
        assert redirects, "样例须含 redirect 节点，否则本条断言空转"
        assert [h for n in redirects for h in csr._redirect_hits(n, 0, context)] == []


class TestBraceExpansion:
    """``_brace_expansion_regex_hit`` 与引号感知。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("{a,b}", True),
            ("x{a,b}y", True),
            ("{ab}", False),
            ("{a,{b}}", False),
            ("'{a,b}'", False),
            ("\\{a,b}", False),
        ],
    )
    def test_regex_hit_requires_same_unquoted_segment(self, raw, expected):
        """``{`` + 逗号 + ``}`` 必须落在同一有效未引用区间（跨引号不算）。"""
        assert csr._brace_expansion_regex_hit(raw) is expected

    def test_findings_scan_word_and_assignment_slices(self):
        """``_syntax_brace_expansion`` 谓词按 word/assignment 原文切片判定。"""
        hits = csr._syntax_brace_expansion(_ctx("A={a,b} echo ok"))
        assert [h.rule_id for h in hits] == ["syntax:brace_expansion"]
        assert hits[0].span == (0, 7)


class TestUnquotedSegments:
    """``_unquoted_segments`` 的按引号状态切分。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("abc", ["abc"]),
            ("'a'b", ["", "b"]),
            ('"a"b', ["", "b"]),
            ("a\\'b", ["a b"]),
        ],
    )
    def test_unquoted_segments(self, raw, expected):
        """按引号状态切分未引用区段（单/双引号内容不计入）。"""
        assert csr._unquoted_segments(raw) == expected


class TestParameterGuardFindings:
    """``_ast_unsupported_parameter``：未建模执行结构（``${...}`` 内 ``$(``/反引号/``<(`）。"""

    @pytest.mark.parametrize(
        "text, hit",
        [
            ("echo ${x:-$(id)}", True),
            ("echo ${x:-`id`}", True),
            ("echo ${x:-<(id)}", True),
            ('echo "${x:-$(id)}"', True),
            ("echo ${x:-fallback}", False),
            ("echo '${x:-$(id)}'", False),  # 单引号字面
        ],
    )
    def test_guard_hit_matrix(self, text, hit):
        """命中返回 ``ast:unsupported_parameter_execution``（category=ast）。"""
        hits = csr._ast_unsupported_parameter(_ctx(text))
        assert bool(hits) is hit
        if hit:
            assert hits[0].rule_id == "ast:unsupported_parameter_execution"
            assert hits[0].category == "ast"

    def test_modeled_substitution_inside_parameter_does_not_trip(self):
        """已被 bashlex 建模的 ``$(...)`` 位置不报未建模（位置精确比对）。"""
        assert csr._ast_unsupported_parameter(_ctx("echo $(id)")) == []


# ========== 已建模替换偏移（零次再解析）==========


class TestModeledSubstitutionOffsets:
    """已建模替换偏移：只从已遍历节点投影，且**零次再解析**。"""

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("echo $(pwd)", {5}),
            ("diff <(ls) <(ls)", {5, 11}),
            ("echo a b", set()),
        ],
    )
    def test_projects_offsets_from_walked_nodes(self, text, expected):
        """``$(...)`` / ``<(...)`` 的开启偏移被识别；无替换时为空集（不误报）。"""
        assert csr._modeled_substitution_offsets(_walk(text)) == expected

    def test_performs_no_reparse(self, monkeypatch):
        """真正的不变量：本函数不得调用 ``bashlex.parse``。

        把 ``bashlex.parse`` 换成即抛的替身（经 ``bashlex.ast`` 引用同一模块对象）；
        若函数内部重新解析则本用例必红。
        """
        walked = _walk("echo $(pwd) x")

        def _boom(*args, **kwargs):
            raise AssertionError("_modeled_substitution_offsets 不得重新 parse")

        monkeypatch.setattr(bashlex, "parse", _boom)
        assert csr._modeled_substitution_offsets(walked) == {5}

    def test_offsets_require_prior_walk(self):
        """替换节点必须先被 ``walk_nodes`` 记录，投影才可见（无重新发现）。

        未 walk 的 ``WalkResult`` 只持有 ``source``，此时投影必为空集；walk 之后才见 ``{5}``。
        """
        source = CommandSource(0, None, None, "echo $(pwd)")
        result = cp.WalkResult(source=source)
        assert csr._modeled_substitution_offsets(result) == set()
        cp.walk_nodes(
            _parse(source.text),
            source=source,
            budget=cp.WalkBudget(1000, 1000, 10, 1),
            result=result,
        )
        assert csr._modeled_substitution_offsets(result) == {5}


# ========== 谓词专属辅助：span 算术 / 节点投影 / 脚本操作数 ==========


class TestSpanArithmetic:
    """``_delimiter_boundaries`` / ``_scan_span`` / 二分定位。"""

    def test_delimiter_boundaries_lists_word_separators(self):
        """预计算的分隔符下标升序，集合为 ``_WORD_DELIMITERS``。"""
        assert csr._delimiter_boundaries("a b|;c") == [1, 3, 4]

    @pytest.mark.parametrize(
        "boundaries, query, side, expected",
        [
            ([1, 3, 5], 0, "before", None),
            ([1, 3, 5], 3, "before", 1),
            ([1, 3, 5], 4, "before", 3),
            ([1, 3, 5], 10, "before", 5),
            ([1, 3, 5], 0, "at_or_after", 1),
            ([1, 3, 5], 3, "at_or_after", 3),
            ([1, 3, 5], 6, "at_or_after", None),
        ],
    )
    def test_delimiter_lookup_by_bisect(self, boundaries, query, side, expected):
        """两个镜像的二分查询：``< query`` 的最大值 / ``>= query`` 的最小值（无则 ``None``）。"""
        lookup = csr._last_delimiter_before if side == "before" else csr._first_delimiter_at_or_after
        assert lookup(boundaries, query) == expected

    @pytest.mark.parametrize(
        "text, expected_span, pass_boundaries",
        [
            ("echo x${a}y z", (5, 11), True),
            ("A=${x:-$(id)} echo ok", (0, 13), False),
        ],
    )
    def test_scan_span_bounds(self, text, expected_span, pass_boundaries):
        """``_scan_span`` 含所属词、不越过该词右边界（``boundaries=None`` 时自建）。

        第一条显式传入 ``boundaries``，第二条走自建分支——两条路径都要被行使。
        另断言：同参重复调用同值（确定性），以及 ``SyntaxNode`` 不携带所属词的原文范围
        （扫描范围按分隔符二分现算）。
        """
        item = next(i for i in _walk(text).syntax_nodes if i.node.kind == "parameter")
        if pass_boundaries:
            bounds = csr._delimiter_boundaries(text)
            assert csr._scan_span(text, item, item.node.pos, bounds) == expected_span
            assert csr._scan_span(text, item, item.node.pos, bounds) == csr._scan_span(text, item, item.node.pos)
        else:
            assert csr._scan_span(text, item, item.node.pos) == expected_span
        assert not hasattr(item, "owner_pos")


class TestRootNodes:
    """``_root_nodes`` 的去重与 entry 节点收纳。"""

    def test_root_nodes_dedupes_and_includes_entries(self):
        """``_root_nodes`` 去重且包含 entry 的 command 节点（供无条件节点规则）。"""
        result = _walk("echo a")
        roots = csr._root_nodes(result)
        assert len({id(n) for n in roots}) == len(roots)  # 无重复
        assert _entry(result).node in roots


class TestEntryName:
    """``_entry_name`` 的节点身份匹配。"""

    def test_entry_name_returns_word_or_none(self):
        """``_entry_name`` 只对已登记 command 节点返回命令名。"""
        result = _walk("echo a")
        assert csr._entry_name(result, _entry(result).node, "echo a") == "echo"
        assert csr._entry_name(result, object(), "echo a") is None


class TestScriptOperand:
    """``_script_operand`` 只对 shell 返回静态脚本操作数。"""

    def test_script_operand_only_for_shell(self):
        """``_script_operand`` 只对 shell 返回操作数；非 shell 返回 ``None``。"""
        shell = _walk("bash /tmp/ok.sh")
        plain = _walk("echo /tmp/ok.sh")
        assert csr._script_operand(_entry(shell), shell.source.text) == "/tmp/ok.sh"
        assert csr._script_operand(_entry(plain), plain.source.text) is None


# ========== 谓词统一派发：命令归属 vs 结构明细 ==========


class TestEvaluateSyntaxRules:
    """语法规则谓词的产出（命令归属 hit + 结构 hit）。

    判定统一走各 ``RuleSpec.predicate``（即 ``command_syntax_rules`` 内各自手写的谓词）。
    本类用下面的 ``_run`` 辅助复现**统一派发层的求值语义**（source 级 + entry 级），
    故它断言的仍是「这套谓词产出什么」，与生产路径同构。
    """

    @staticmethod
    def _run(text: str, *, allowed_script_dirs: list[str] | None = None) -> tuple[dict, list]:
        """跑全部语法谓词，返回 ``(entry_id -> rule_ids, structure_rule_ids)``。

        按 ``RuleContext`` 的两种粒度各跑一次（与 ``_evaluate_rules`` 的遍历顺序一致），
        以 ``(rule_id, owner_entry_id, span)`` 去重。
        """
        result = _walk(text)
        dirs = tuple(allowed_script_dirs or [])
        used: set[tuple] = set()
        owned: dict[int, list[str]] = {}
        structure: list = []
        for entry in [None, *result.entries]:
            context = RuleContext(walked=result, entry=entry, allowed_script_dirs=dirs)
            for spec in csr.SYNTAX_RULES:
                if spec.predicate is None:  # pragma: no cover - 10 条都有谓词
                    continue
                for hit in spec.predicate(context):
                    key = (hit.rule_id, hit.owner_entry_id, hit.span)
                    if key in used:
                        continue
                    used.add(key)
                    if hit.is_structure:
                        structure.append(hit)
                    else:
                        owned.setdefault(hit.owner_entry_id, []).append(hit.rule_id)
        return owned, structure

    def test_returns_owned_map_and_structure_list(self):
        """产出分两部分：有 entry 归属的 hit 与无归属的结构 hit。"""
        owned, structure = self._run("echo a")
        assert isinstance(owned, dict) and isinstance(structure, list)

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("echo a > /tmp/o", ["syntax:redirect"]),
            ("echo {a,b}", ["syntax:brace_expansion"]),
        ],
    )
    def test_structure_finding_rule_ids(self, text, expected):
        """无命令归属的规则落结构明细，不进 owned map（重定向与大括号扩展同档）。"""
        owned, structure = self._run(text)
        assert owned == {}
        assert [f.rule_id for f in structure] == expected

    @pytest.mark.parametrize("name", ["nohup", "setsid", "screen"])
    def test_forbidden_command_is_structure_finding(self, name):
        """无条件禁用命令落结构明细（独立于黑名单开关）。"""
        _, structure = self._run(f"{name} x")
        assert [f.rule_id for f in structure] == ["syntax:forbidden_command"]

    def test_script_path_rule_is_owned_by_entry(self):
        """脚本目录政策失败归**命令归属**（键为 entry_id）。"""
        owned, structure = self._run("bash /etc/x.sh", allowed_script_dirs=["/tmp"])
        assert structure == []
        assert owned == {0: ["syntax:script_path"]}

    def test_script_path_within_allowed_dir_is_clean(self):
        """允许目录内脚本不产出规则（正向对照，避免无法证伪）。"""
        owned, structure = self._run("bash /tmp/ok.sh", allowed_script_dirs=["/tmp"])
        assert owned == {} and structure == []
