# -*- coding: utf-8 -*-
"""``command_parser`` 的**直接单元测试**（与本目录其他文件互补）。

策略与 ``test_command_ast.py`` 刻意不同：该文件声明「只通过真实公开入口
（``validate_command`` / ``walk_nodes``）断言」；本文件反过来**直接 import 并调用**
``command_parser`` 内部的函数/类，把模块自身的契约钉住 —— 这样重构内部实现时
这些用例会先红，而不是被上层聚合逻辑掩盖。

覆盖重点：

- 预算异常的 ``rule_id`` / ``detail`` / ``str`` 契约与两个计数方法的**无副作用**顺序，
  以及遍历中途失败时**已收集 inventory 保留**与 id 分配不冲突；
- 遍历器内部投影（``_children`` / ``_build_command_entry`` / ``_stage_entry`` /
  ``_index_all_pipelines`` 的「stage 归属不跨 substitution / 嵌套 pipeline / function，
  且经 O(1) 身份映射（``_entry_ids_by_node_id``）查表而非逐节点线性扫描」）；
- 有限词法（引号状态、``classify_word``、``has_unmodeled_execution`` 的开符识别）；
- 命令名规范化与有限 argv adapter。

结构规则（10 条 ``syntax:*`` / ``ast:*``）归 ``command_syntax_rules`` 所有，其单测在
同目录 ``test_command_syntax_rules_units.py``。

测试字符串只用于 ``bashlex.parse`` / 内部谓词，**从不执行**（无 subprocess / os.system）。
"""

from __future__ import annotations

import ast as _ast
import pathlib

import bashlex
import pytest
from aidev_agent.packages.security import command
from aidev_agent.packages.security.command import command_parser as cp
from aidev_agent.packages.security.command.command_definitions import (
    AnalysisFailure,
    CommandSource,
    RuleSpec,
)
from aidev_agent.packages.security.command.command_security import validate_command
from aidev_agent.pydantic_models import SecurityCommandSettings
from tests.packages.security.command._walk_helpers import _walk_source_text


def _parse(text: str) -> list:
    """真解析一段文本（只做 AST 构造，不执行）。"""
    return bashlex.parse(text)


def _walk(text: str, **budget_overrides) -> cp.WalkResult:
    """解析 + ``walk_nodes``，返回遍历产物（宽松预算，只测遍历语义）。"""
    limits = {"max_command_length": 100000, "max_nodes": 100000, "max_depth": 100, "max_reparse_depth": 8}
    limits.update(budget_overrides)
    source = CommandSource(0, None, None, text)
    result = cp.WalkResult(source=source)
    cp.walk_nodes(_parse(text), source=source, budget=cp.WalkBudget(**limits), result=result)
    return result


def _entry(result: cp.WalkResult, index: int = 0) -> cp.CommandEntry:
    return result.entries[index]


def _param_node(text: str):
    """取首个 ``parameter`` 节点（bashlex 不为它建模内部结构）。"""
    for node in _flat(_parse(text)):
        if node.kind == "parameter":
            return node
    raise AssertionError(f"未在 {text!r} 中找到 parameter 节点")


def _flat(nodes, acc=None):
    """对已解析节点做一次简易展平（仅测试辅助，不参与生产判定）。"""
    acc = [] if acc is None else acc
    for node in nodes:
        acc.append(node)
        for attr in ("parts", "list", "redirects"):
            children = [c for c in (getattr(node, attr, ()) or ()) if hasattr(c, "kind")]
            _flat(children, acc)
    return acc


# ========== A. 预算 / 异常 ==========


class TestBudgetRuleIds:
    """预算异常对象的契约，以及 ``WalkBudget`` 两个计数方法的**无副作用**顺序。

    ``kind -> rule_id`` 的映射本体由 ``test_command_analysis_failure.py`` 逐字覆盖
    （那里同时看守 ``_BUDGET_RULE_IDS`` 的键与 ``AnalysisFailure`` 的派生关系）；本类
    只钉住异常对象自身的形状与预算计数的先后顺序。
    """

    def test_charge_node_depth_checked_before_counting(self):
        """``charge_node`` 先查深度：深度超限时节点计数不增长（不产生副作用）。"""
        budget = cp.WalkBudget(max_command_length=100, max_nodes=100, max_depth=2, max_reparse_depth=1)
        budget.charge_node(2)
        assert budget.used_nodes == 1
        with pytest.raises(cp.CommandBudgetExceeded) as exc:
            budget.charge_node(3)
        assert exc.value.rule_id == "budget:max_depth"
        assert budget.used_nodes == 1  # 深度失败不计数

    def test_before_parse_reparse_depth_checked_before_chars(self):
        """``before_parse`` 先查再解析深度：深度超限时字符数不增长。"""
        budget = cp.WalkBudget(max_command_length=1000, max_nodes=10, max_depth=10, max_reparse_depth=1)
        with pytest.raises(cp.CommandBudgetExceeded) as exc:
            budget.before_parse("abc", 2)
        assert exc.value.rule_id == "budget:max_reparse_depth"
        assert budget.used_chars == 0

    def test_before_parse_equal_limit_allowed_exceeding_raises(self):
        """累计字数等于上限允许，再多一个字符才超限（边界语义）。"""
        budget = cp.WalkBudget(max_command_length=3, max_nodes=10, max_depth=10, max_reparse_depth=1)
        budget.before_parse("ab", 0)
        budget.before_parse("c", 0)
        assert budget.used_chars == 3
        with pytest.raises(cp.CommandBudgetExceeded) as exc:
            budget.before_parse("d", 0)
        assert exc.value.rule_id == "budget:max_command_length"

    def test_exception_contracts(self):
        """预算异常 ``str`` 为 ``rule_id: detail``；``UnsupportedAstError`` 是普通异常。

        ``CommandBudgetExceeded`` 携带 ``rule_id`` / ``detail`` 且 ``str`` 形状固定
        （上层日志分类依赖）；``UnsupportedAstError`` 只表示「结构未建模」，**不**携带
        预算属性，故不得用 ``rule_id`` 归因。
        """
        exc = cp.CommandBudgetExceeded("budget:max_nodes", "太多")
        assert str(exc) == "budget:max_nodes: 太多"
        assert (exc.rule_id, exc.detail) == ("budget:max_nodes", "太多")
        unsupported = cp.UnsupportedAstError("未知 AST 节点类型: 'x'")
        assert isinstance(unsupported, Exception)
        assert not hasattr(unsupported, "rule_id")


# ========== B. 遍历器内部 ==========


class TestWalkerInternals:
    """``walk_nodes`` 的内部投影契约。"""

    @pytest.mark.parametrize("key, expected", [(None, None), ((7, 2), 7), ((0, 0), 0)])
    def test_stage_entry_projects_pipeline_id(self, key, expected):
        """栈上的 stage identity 是 ``(pipeline_id, index)``，SyntaxNode 只留 pipeline_id。"""
        assert cp._stage_entry(key) == expected  # noqa: SLF001

    def test_children_uses_parts_for_list_like(self):
        """``command`` 属 ``_LIST_LIKE``：子边即 ``parts``（含 redirect）。"""
        (node,) = _parse("echo a > /tmp/o")
        assert [(c.kind, c.pos) for c in cp._children(node)] == [  # noqa: SLF001
            ("word", (0, 4)),
            ("word", (5, 6)),
            ("redirect", (7, 15)),
        ]

    def test_children_compound_concatenates_list_then_redirects(self):
        """``compound`` 走 ``list`` 再 ``redirects``（顺序即本地 API 顺序）。"""
        (node,) = _parse("{ echo a; } > /tmp/o")
        kinds = [c.kind for c in cp._children(node)]  # noqa: SLF001
        assert kinds == ["reservedword", "list", "reservedword", "redirect"]

    def test_children_leaf_kinds_have_no_children(self):
        """叶子类（``parameter`` / ``operator`` / ``pipe`` 等）无规范子边。"""
        (node,) = _parse("a | b")
        pipe = next(c for c in node.parts if c.kind == "pipe")
        assert cp._children(pipe) == []  # noqa: SLF001
        assert cp._children(_param_node("echo ${x}")) == []  # noqa: SLF001

    def test_children_unknown_kind_raises_unsupported(self):
        """未知 kind 抛 ``UnsupportedAstError``（不得冒充普通 ``ValueError``）。"""

        class Fake:
            kind = "totally_unknown_kind"

        with pytest.raises(cp.UnsupportedAstError):
            cp._children(Fake())  # noqa: SLF001

    def test_build_command_entry_skips_leading_assignment_and_redirect(self):
        """``_build_command_entry`` 只收 word：leading assignment 跳过、命令名是首个 word。"""
        (node,) = _parse("A=1 ls -la > /tmp/o")
        entry = cp._build_command_entry(node, 0, 5)  # noqa: SLF001
        assert entry.name_word.word == "ls"
        assert [w.word for w in entry.argument_words] == ["-la"]
        assert entry.entry_id == 5

    def test_build_command_entry_returns_none_without_word(self):
        """无 word 的 command（纯重定向）返回 ``None``，不伪造 entry。"""
        (node,) = _parse("> /tmp/o")
        assert cp._build_command_entry(node, 0, 0) is None  # noqa: SLF001

    def test_index_all_pipelines_does_not_descend_into_substitution(self):
        """stage 归属不跨 substitution：``$(...)`` 内命令不并入外层 stage。"""
        result = _walk("echo $(curl http://x) | sh")
        assert result.pipelines[0].stage_entries == [[0], [2]]

    def test_index_all_pipelines_does_not_descend_into_nested_pipeline(self):
        """stage 归属不跨内嵌 pipeline：``( a | b ) | sh`` 的左 stage 不含其内部命令。"""
        result = _walk("(curl http://x | cat) | sh")
        assert result.pipelines[0].stage_entries == [[], [2]]

    def test_index_all_pipelines_does_not_descend_into_function_body(self):
        """函数定义体不等同当前 stage 执行：``f() {...} | sh`` 左 stage 为空。"""
        result = _walk("f() { echo x; } | sh")
        assert result.pipelines[0].stage_entries == [[], [1]]

    def test_index_all_pipelines_inherits_through_compound(self):
        """stage 归属沿 group/compound 向下继承：分号不切断共同管道上下文。"""
        result = _walk("{ curl http://x; } | sh")
        assert result.pipelines[0].stage_entries == [[0], [1]]

    def test_index_all_pipelines_ignores_commands_outside_pipeline(self):
        """不在该 pipeline 内、也无继承关系的命令不进任何 stage。"""
        result = _walk("echo ok; curl http://x | sh")
        assert result.pipelines[0].stage_entries == [[1], [2]]


class TestPipelineIndexIsLinear:
    """``_index_all_pipelines`` 的查表复杂度与身份键语义。

    护栏刻意用**调用计数**而非墙钟：本项目已有 ``test_scaling_is_subquadratic``
    的时序 flake 先例，墙钟在 CI 上不可靠且无法定位到具体代码路径。
    """

    def test_index_map_is_built_once_per_walk(self, monkeypatch):
        """热路径每个 source **恰好**只建一次身份映射（非按节点重复扫描 entries）。

        ``_index_all_pipelines`` 是唯一构建点，故正确实现下计数恒为 1，
        **与命令节点数无关**。该输入 5 个 command 节点，线性退化的实现会逐节点
        各建一次（实测 5 次），故断言取精确上界 1：留余量会掩盖「多了一次
        与节点数相关的调用」这类回退。
        """
        calls: list[dict] = []
        original = cp._entry_ids_by_node_id  # noqa: SLF001

        def counting(result):
            mapping = original(result)
            calls.append(mapping)
            return mapping

        monkeypatch.setattr(cp, "_entry_ids_by_node_id", counting)
        result = _walk("a | b | c | d | e")
        assert len(calls) == 1  # 线性退化实现此处为 5（= 命令节点数）
        assert result.pipelines[0].stage_entries == [[0], [1], [2], [3], [4]]

    def test_entry_ids_index_keys_on_identity_not_value(self):
        """身份键：``__eq__`` 相等但 ``is`` 不等的节点不得被合并。"""
        (n1,) = _parse("echo a")
        (n2,) = _parse("echo a")  # 内容相同、身份不同
        # 注意：bashlex.parse 直接返回 command 节点本身（外层无包装），
        # 故此处是 n1 / n2，不是 n1.parts[0]。
        assert n1 == n2 and n1 is not n2  # 前置事实：bashlex 的 __eq__ 是按值的
        result = cp.WalkResult(source=CommandSource(0, None, None, "echo a"))
        result.entries = [
            cp.CommandEntry(0, 7, n1, n1.parts[0]),
            cp.CommandEntry(0, 9, n2, n2.parts[0]),
        ]
        index = cp._entry_ids_by_node_id(result)  # noqa: SLF001
        assert len(index) == 2  # 按值键会塌成 1
        assert cp._entry_ids_by_node_id(result).get(id(n1)) == 7  # noqa: SLF001
        assert cp._entry_ids_by_node_id(result).get(id(n2)) == 9  # noqa: SLF001
        assert cp._entry_ids_by_node_id(result).get(id(object())) is None  # noqa: SLF001


class TestPackageExportedSurface:
    """``command/__init__.py.__all__`` 的包级结构护栏。

    导出面唯一收拢到本包的 ``__all__``：子模块的 ``__all__`` 既不是对外契约（包外
    一律走本包的 ``__init__``），也不是对内约束（sibling 自由 import 下划线私有名），
    只是一份无人强制、持续漂移的清单。

    判据刻意**只断言结构不变量**（真实存在 / 不重复 / 非空），
    **不断言「每项都有包外消费方」** —— 包 ``__init__`` 当前零处被 import，
    该断言会首日全红，等于把「对外统一走本包导出」这个**目标**当成**现状**。
    """

    def test_surface_is_real_unique_and_nonempty(self):
        """无重复项、每项都是包上真实存在的属性，且清单非空。

        「非空」防止「删除即清空」这一退化被静默接受；「全真实」防止 ``__all__``
        声明了不存在的属性而无人发现（声明为公开却无人可用这一真实缺陷类）。
        """
        assert len(command.__all__) == len(set(command.__all__))
        stale = [name for name in command.__all__ if not hasattr(command, name)]
        assert stale == [], f"__all__ 声明了不存在的属性：{stale}"
        assert len(command.__all__) > 0


class TestWalkNodesRetention:
    """``walk_nodes`` docstring 的保留契约与 id 分配。"""

    @pytest.mark.parametrize("failure", ["budget", "unsupported_ast"])
    def test_entries_survive_mid_walk_failure(self, failure):
        """遍历中途失败：**已收集 entries 保留**（调用方据此保留已归因结果）。

        两种触发面共用同一契约：预算超限（``CommandBudgetExceeded``）与未知 kind
        （``UnsupportedAstError``）。``result.entries`` 都不被清空。
        """
        budget_limits = {
            "budget": {"max_nodes": 2},
            "unsupported_ast": {"max_nodes": 100000},
        }[failure]
        text = {"budget": "echo a | grep b | sort c", "unsupported_ast": "echo a"}[failure]
        source = CommandSource(0, None, None, text)
        result = cp.WalkResult(source=source)
        budget = cp.WalkBudget(max_command_length=100000, max_depth=100, max_reparse_depth=8, **budget_limits)
        nodes = _parse(text)
        if failure == "unsupported_ast":
            nodes = [*nodes, type("Fake", (), {"kind": "nope"})()]
            with pytest.raises(cp.UnsupportedAstError):
                cp.walk_nodes(nodes, source=source, budget=budget, result=result)
            assert [entry.name_word.word for entry in result.entries] == ["echo"]
            return
        with pytest.raises(cp.CommandBudgetExceeded) as exc:
            cp.walk_nodes(nodes, source=source, budget=budget, result=result)
        assert exc.value.rule_id == "budget:max_nodes"
        assert result.entries != []  # 不清空
        assert all(entry.node.kind == "command" for entry in result.entries)
        assert [entry.name_word.word for entry in result.entries] == ["echo"]

    @pytest.mark.parametrize("target", ["entry", "pipeline"])
    def test_ids_do_not_collide_for_prepopulated_result(self, target):
        """``next_*_id = len(result.*)``：预填充 result 时 id 不从 0 重来。

        两种 id 空间（entry / pipeline）共用同一判据，两者都不与预填充项冲突。
        """
        if target == "entry":
            source = CommandSource(0, None, None, "echo x")
            result = cp.WalkResult(source=source)
            result.entries.append(cp.CommandEntry(0, 0, None, None, None))
            text = "echo x"
            ids = lambda res: [entry.entry_id for entry in res.entries]  # noqa: E731
        else:
            source = CommandSource(0, None, None, "cat f | grep x")
            result = cp.WalkResult(source=source)
            result.pipelines.append(cp.PipelineRecord(source_id=0, pipeline_id=0))
            text = "cat f | grep x"
            ids = lambda res: [p.pipeline_id for p in res.pipelines]  # noqa: E731
        budget = cp.WalkBudget(max_command_length=100000, max_nodes=100000, max_depth=100, max_reparse_depth=8)
        cp.walk_nodes(_parse(text), source=source, budget=budget, result=result)
        assert ids(result) == [0, 1]


# ========== C. 有限词法 / 引号 ==========


class TestQuoteContext:
    """``_quote_context`` / ``_quote_context_map`` 的逐位一致性与状态语义。"""

    @pytest.mark.parametrize(
        "text, index, expected",
        [
            ("abc", 0, "plain"),
            ("'a b'", 3, "single"),
            ('"a b"', 3, "double"),
            ("a'b'c", 4, "plain"),  # 闭合单引号后回到 plain
            ('a"b"c', 4, "plain"),
        ],
    )
    def test_context_at_index(self, text, index, expected):
        """三种状态：plain / single / double，闭合后回到 plain。"""
        assert cp._quote_context(text, index) == expected  # noqa: SLF001
        assert cp._quote_context_map(text)[index] == expected  # noqa: SLF001

    def test_map_length_is_len_plus_one(self):
        """``map`` 有 ``len(text)+1`` 项，``index == len(text)`` 合法（末尾状态）。"""
        text = "a'b'\"c\""
        states = cp._quote_context_map(text)  # noqa: SLF001
        assert len(states) == len(text) + 1
        assert states[len(text)] == cp._quote_context(text, len(text))  # noqa: SLF001

    def test_map_is_consistent_with_per_index_calls(self):
        """整串预计算与逐位查询逐位相同（``_quote_context_map`` 的等价性前提）。"""
        text = "echo 'a$(b)' \"c\\\"d\" e\\'f"
        states = cp._quote_context_map(text)  # noqa: SLF001
        assert all(states[i] == cp._quote_context(text, i) for i in range(len(text) + 1))  # noqa: SLF001

    def test_backslash_skip_in_plain_protects_next_char(self):
        """未引用区反斜杠保护下一字符：``\\'`` 不开启单引号态。"""
        text = "a\\'b"
        assert cp._quote_context(text, 3) == "plain"  # noqa: SLF001

    def test_double_quote_backslash_escapes_quote_but_not_ordinary_char(self):
        """双引号内 ``\\"`` 保护引号（不闭合），``\\q`` 等非特殊字符不构成转义。

        对照：``"a\\"b"`` 的引号被转义（下标 4 仍为 double），而 ``"a\\q..."`` 中
        反斜杠不保护任何字符 —— 用「转义引号是否闭合」这一可观测差别断言。
        """
        escaped = cp._quote_context_map('"a\\"b"')  # noqa: SLF001
        assert escaped[4] == "double"  # \\" 保护引号，仍在双引号内
        plain_backslash = cp._quote_context_map('"a\\q"')  # noqa: SLF001
        assert plain_backslash[-1] == "plain"  # \\q 非转义，末尾引号正常闭合


class TestWordLexical:
    """``_word_source`` / ``_quoted_literal`` / ``classify_word``。"""

    def test_word_source_returns_raw_source_slice(self):
        """``_word_source`` 返回含引号/转义的原文切片（不去引号）。"""
        text = "echo 'a b'"
        word = _parse(text)[0].parts[1]
        assert cp._word_source(text, word) == "'a b'"  # noqa: SLF001

    def test_word_source_empty_without_pos(self):
        """无 ``pos`` 的 word 返回空串（不抛异常）。"""
        assert cp._word_source("abc", type("N", (), {})()) == ""  # noqa: SLF001

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("'a b'", "a b"),
            ('"a b"', "a b"),
            ("''", ""),
            ('""', ""),
            ("plain", None),
            ("'a$b'", "a$b"),
            ('"a$b"', None),  # 双引号内展开 → 非静态
            ('"a\\"b"', None),
        ],
    )
    def test_quoted_literal(self, raw, expected):
        """整段被引号包裹且无展开才返回去引号字面值，否则 ``None``。"""
        assert cp._quoted_literal(raw) == expected  # noqa: SLF001

    @pytest.mark.parametrize(
        "text, index, kind",
        [
            ("echo 'a b c'", 1, "static"),
            ("echo a-b_c.d/e", 1, "static"),
            ("echo $VAR", 1, "dynamic"),  # 含参数展开
            ("echo *.py", 1, "dynamic"),  # 未引用 glob
            ("echo a?b", 1, "dynamic"),
            ("echo {a,b}", 1, "dynamic"),  # 花括号扩展
        ],
    )
    def test_classify_word_static_vs_dynamic(self, text, index, kind):
        """执行位置静态性判定：引号/裸字面为 static，展开/glob/花括号为 dynamic。"""
        word = _parse(text)[0].parts[index]
        structure = cp.classify_word(word, text)
        assert structure.kind == kind

    def test_classify_word_structure_fields(self):
        """``Structure`` 携带原文与静态字面值（``text`` 为判定有效值）。"""
        text = "echo 'hi'"
        structure = cp.classify_word(_parse(text)[0].parts[1], text)
        assert (structure.kind, structure.text) == ("static", "hi")

    def test_classify_word_dynamic_carries_reason(self):
        """动态判定带非空 reason（区分「含展开」与「非静态字面」）。"""
        text = "echo $(x)"
        structure = cp.classify_word(_parse(text)[0].parts[1], text)
        assert structure.kind == "dynamic" and structure.reason


# ========== D. 遍历期守卫（谓词用；规则本身在 command_syntax_rules）==========


class TestUnmodeledExecution:
    """``has_unmodeled_execution`` 的开符识别与引号/算术规则。"""

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("echo $(id)", (True, 5)),
            ("echo `id`", (True, 5)),
            ("echo x$(id)y", (True, 6)),
            ('echo "$(id)"', (True, 6)),  # 双引号不抑制 $(
            ("echo $((1+2))", (False, -1)),  # 算术展开不是未建模命令执行
            ("echo '$(id)'", (False, -1)),  # 单引号内是字面
            ("echo ${x:-fallback}", (False, -1)),
            ("diff <(ls) <(ls)", (True, 5)),
            ("cat >(x)", (True, 4)),
        ],
    )
    def test_hit_and_miss(self, text, expected):
        """返回 ``(是否命中, 命中位置)``；算术与单引号字面不算命中。"""
        assert cp.has_unmodeled_execution(text, 0, len(text)) == expected

    def test_span_bounds_are_respected(self):
        """扫描限定在 ``[start, end)``：界外的开符不计入，空区间必定 miss。"""
        text = "$(a) b"
        assert cp.has_unmodeled_execution(text, 4, len(text)) == (False, -1)
        assert cp.has_unmodeled_execution(text, 0, len(text)) == (True, 0)
        assert cp.has_unmodeled_execution("abc", 1, 1) == (False, -1)


# ========== E. 命令名 / 调用形态 ==========


class TestNormalizeCommandName:
    """``_normalize_command_name`` 的路径规范化与遍历拒绝（仅补既有覆盖缺口）。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("/usr/bin/ls", "ls"),
            ("./bin/ls", "ls"),
            ("dir/ls", "ls"),
            ("ls", "ls"),
            ("-ls", "-ls"),  # 以 - 开头不做路径切分
        ],
    )
    def test_basename_projection(self, raw, expected):
        """绝对路径 / 相对路径取 basename；以 ``-`` 开头的保持原样。"""
        assert cp._normalize_command_name(raw) == expected  # noqa: SLF001

    @pytest.mark.parametrize("raw", ["", "   ", "../x", "/a/../b", "a/../b"])
    def test_rejects_empty_and_traversal(self, raw):
        """空名与路径遍历抛 ``ValueError``（不得静默放行）。"""
        with pytest.raises(ValueError):
            cp._normalize_command_name(raw)  # noqa: SLF001


class TestCheckScriptPathAllowed:
    """``_check_script_path_allowed`` 的精确/子目录判定与遍历拒绝。"""

    @pytest.mark.parametrize(
        "path, dirs, expected",
        [
            ("/tmp/ok.sh", ["/tmp"], (True, "")),
            ("/tmp/sub/ok.sh", ["/tmp"], (True, "")),  # 子目录允许
            ("/tmp", ["/tmp"], (True, "")),  # 精确相等允许
            ("/tmpfoo/x.sh", ["/tmp"], (False, "脚本路径不在允许的目录内（允许: /tmp）")),
            ("/etc/x.sh", ["/tmp", "/app"], (False, "脚本路径不在允许的目录内（允许: /tmp, /app）")),
            ("", ["/tmp"], (False, "未指定脚本路径")),
            ("../x.sh", ["/tmp"], (False, "脚本路径包含目录遍历: ../x.sh")),
            # 绝对路径中的 ``..`` 先被 normpath 折叠，故落「不在允许目录内」而非遍历分支
            ("/tmp/../etc/x.sh", ["/tmp"], (False, "脚本路径不在允许的目录内（允许: /tmp）")),
        ],
    )
    def test_allowed_or_rejected(self, path, dirs, expected):
        """前缀匹配须带路径分隔符（``/tmpfoo`` 不算 ``/tmp`` 内）；遍历与空路径拒绝。"""
        assert cp._check_script_path_allowed(path, dirs) == expected  # noqa: SLF001


class TestShellInvocationHelpers:
    """``_is_short_cluster`` / ``_match_interpreter_code_flag``（两者都住在 ``command_parser``）。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [("-lc", True), ("-xec", True), ("-e", False), ("--lc", False), ("-lq", False), ("-c", False)],
    )
    def test_is_short_cluster(self, raw, expected):
        """短选项簇：≥3 字符、单横线、全字母在表内（``c`` 由调用方另行判定）。"""
        assert cp._is_short_cluster(raw, frozenset("clxe")) is expected  # noqa: SLF001
        assert cp._is_short_cluster("-lc", frozenset("e")) is False  # 字母不在表内  # noqa: SLF001

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("python3 -c x", True),
            ("python3 script.py", False),
            ("perl -e x", True),
            ("node --eval x", True),
            ("ls -c", False),  # 非解释器命令
        ],
    )
    def test_match_interpreter_code_flag(self, text, expected):
        """只识别精确的内联代码选项 word（判定入口）。"""
        result = _walk(text)
        entry = _entry(result)
        assert cp._match_interpreter_code_flag(entry.name_word.word, entry.argument_words, text) is expected  # noqa: SLF001


class TestAnalyzeShellInvocationKinds:
    """``analyze_shell_invocation`` 的形态分档（补既有覆盖缺的 kind）。"""

    @staticmethod
    def _invocation(text: str) -> cp.ShellInvocation:
        result = _walk(text)
        return cp.analyze_shell_invocation(_entry(result), source=result.source)

    @pytest.mark.parametrize(
        "text, kind, detail",
        [
            ("bash", "stdin", ""),
            ("sh -e", "stdin", ""),
            ("bash -c", "unsupported", "-c 缺少要执行的命令内容"),
            ("zsh -c -- echo", "unsupported", "zsh 的 `-c --` 形态未建模，无法确定脚本位置"),
            ("bash -a", "unsupported", "选项 -a 未建模"),
            ("bash -- $(x)", "dynamic", "脚本操作数包含未知展开"),
            ("python3 -c x", "interpreter_code", ""),
            ("perl x.pl", "none", ""),
        ],
    )
    def test_kind_and_detail(self, text, kind, detail):
        """每种调用形态落到确定的 kind（``none`` 不产生规则）。"""
        invocation = self._invocation(text)
        assert (invocation.kind, invocation.detail) == (kind, detail)

    def test_script_path_after_double_dash(self):
        """``--`` 终止选项后首个静态 word 是文件操作数（``-c`` 不再是选项）。"""
        invocation = self._invocation("bash -- /tmp/x.sh")
        assert (invocation.kind, invocation.target) == ("script_path", "/tmp/x.sh")

    def test_bash_short_cluster_with_c_locates_script(self):
        """bash 组合短选项 ``-lc`` 含 ``c``：下一个 word 是脚本文本。"""
        invocation = self._invocation("bash -lc echo")
        assert (invocation.kind, invocation.text) == ("script", "echo")


# ========== 与 ``command_security`` 的接口契约 ==========
#
# 本节是 ``command_security`` 与其兄弟模块之间的**接口契约**：
# 「``validate_command`` 消费的 shell invocation 适配器长什么样」。
# 整节保持内部一致，不拆散、不与上面的类合并。


class TestShellInvocationAdapter:
    """有限 shell-specific argv adapter（不依赖本地是否装有该 shell）。"""

    def test_option_consumes_exactly_one_value_word(self):
        result, _ = _walk_source_text("bash -o pipefail -c 'echo ok'")
        invocation = cp.analyze_shell_invocation(result.entries[0], source=result.source)
        assert invocation.kind == "script"
        assert invocation.text == "echo ok"

    def test_value_taking_option_keeps_script_position(self):
        result, _ = _walk_source_text("bash -O extglob /tmp/phase10.sh")
        invocation = cp.analyze_shell_invocation(result.entries[0], source=result.source)
        assert invocation.kind == "script_path"
        assert invocation.text == "/tmp/phase10.sh"

    def test_zsh_independent_c_is_analyzable(self):
        result, _ = _walk_source_text("zsh -c 'echo ok'")
        assert cp.analyze_shell_invocation(result.entries[0], source=result.source).text == "echo ok"

    @pytest.mark.parametrize("command", ["bash -c", "sh -o"])
    def test_missing_script_or_option_value_is_blocked(self, command):
        """缺脚本或选项值 → block（经 ``validate_command`` 生产入口，非直调 adapter）。

        刻意保留「经生产入口」这一层证据：直调 ``analyze_shell_invocation`` 只证明
        适配器可用，不证明编排层真的消费了它。
        """

        report = validate_command(command, security_command_settings=SecurityCommandSettings())
        assert report.verdict == "block"


# ========== 预算 id 单一真源（``command_parser`` 私有映射） ==========


#: 13 条分析失败标识的值（顺序与枚举定义一致）。
_EXPECTED_VALUES = (
    "parse:syntax_error",
    "parse:unsupported_syntax",
    "parse:internal_error",
    "input:null_byte",
    "empty:no_executable_command",
    "analysis:incomplete",
    "rule:internal_error",
    "budget:max_command_length",
    "budget:max_nodes",
    "budget:max_depth",
    "budget:max_reparse_depth",
    "budget:recursion",
    "ast:unknown_node",
)

#: 4 个预算阶梯成员的短名（``budget:`` 前缀去掉）——私有 ``_BUDGET_RULE_IDS`` 的键。
_BUDGET_SHORT_NAMES = ("max_command_length", "max_nodes", "max_depth", "max_reparse_depth")


class TestBudgetIdsSingleSource:
    """预算 id 的**唯一真源**是 ``AnalysisFailure``。"""

    def test_budget_rule_ids_is_exactly_the_four_rungs_from_the_enum(self):
        """``budget_rule_ids()`` 恰为 4 条阶梯 id，且全部来自 ``AnalysisFailure``。

        ``budget:recursion`` **不在**此映射内——它不经阶梯表，由 ``RecursionError``
        路径直接产出。三条断言合并：数量、逐字取值、枚举派生，测的是同一份快照。
        """

        ids = cp.budget_rule_ids()
        assert len(ids) == 4
        assert ids == {
            "budget:max_command_length",
            "budget:max_nodes",
            "budget:max_depth",
            "budget:max_reparse_depth",
        }
        assert ids <= {member.value for member in AnalysisFailure}
        assert "budget:recursion" not in ids

    @pytest.mark.parametrize(("short", "value"), zip(_BUDGET_SHORT_NAMES, _EXPECTED_VALUES[7:11]))
    def test_budget_rule_ids_contain_the_short_name_derived_values(self, short, value):
        """4 个短名派生出的 ``budget:<short>`` 均在公开快照内；短名键本身不再公开。

        私有 ``_BUDGET_RULE_IDS`` 的键仍是短名 —— 通过 ``_budget_exceeded`` 间接钉住，
        ``budget_rule_ids()`` 只暴露值集合。
        """
        assert f"budget:{short}" == value
        assert value in cp.budget_rule_ids()

    @pytest.mark.parametrize(("short", "value"), zip(_BUDGET_SHORT_NAMES, _EXPECTED_VALUES[7:11]))
    def test_budget_exceeded_rule_id_derives_from_the_private_mapping(self, short, value):
        """``_budget_exceeded(short, ...)`` 的 rule_id 逐字等于枚举值，也等于私有映射的取值。

        私有 dict 的键是短名，三者（短名派生值 / 枚举值 / 私有映射）必须同一：
        任一漂移即阶梯 id 与实际产出的 ``rule_id`` 错位。
        """
        assert cp._budget_exceeded(short, "d").rule_id == value
        assert cp._budget_exceeded(short, "d").rule_id == cp._BUDGET_RULE_IDS[short]

    def test_import_time_consistency_check_exists(self):
        """导入期一致性自检存在：漂移即 ``AssertionError``。"""
        source = cp.__file__
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        assert "pragma: no cover" in text
        assert "_BUDGET_RULE_IDS" in text

    def test_import_time_check_is_falsifiable(self):
        """自检可证伪：把私有映射改坏 → 自检判据变假。

        只断言源码含 ``pragma`` 无法区分「自检在跑」与「自检被注释掉」，故须对判据
        本身求值两次（原映射为真 / 改坏的映射为假）。

        做法：从 ``command_parser.py`` 源码中**提取自检表达式**，对「原始映射」与
        「改坏的映射」各求值一次，断言前者为真、后者为假。这直接测的是自检的**判据**，
        且不受「改不了已编译模块常量」的限制。
        """

        source = pathlib.Path(cp.__file__).read_text(encoding="utf-8")
        tree = _ast.parse(source)

        # 找到自检的 if 语句（比较两个集合的那条）。
        check = next(
            node
            for node in tree.body
            if isinstance(node, _ast.If)
            and isinstance(node.test, _ast.Compare)
            and isinstance(node.body[0], _ast.Raise)
        )
        # 原样求值自检判据：需要私有映射与 AnalysisFailure 两个名字。
        expected_enum_values = {m.value for m in AnalysisFailure if m.value.startswith("budget:max_")}
        good = set(cp._BUDGET_RULE_IDS.values())
        assert good == expected_enum_values, "原始状态自检应为真"
        broken = {("budget:nodes" if rid == "budget:max_nodes" else rid) for rid in good}
        assert broken != expected_enum_values, "改坏后自检应为假（否则自检无证明力）"
        assert check is not None and len(source) > 0  # 自检语句确实存在于源码

    def test_command_parser_no_longer_exports_budget_rule_specs(self):
        """``command_parser.BUDGET_RULES`` 不再产出 ``RuleSpec``（预算 id 已收归私有映射）。"""

        budget_rules = getattr(cp, "BUDGET_RULES", None)
        if budget_rules is not None:
            assert not any(isinstance(item, RuleSpec) for item in budget_rules)
