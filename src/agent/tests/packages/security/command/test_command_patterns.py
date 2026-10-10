# -*- coding: utf-8 -*-
"""``Pattern`` 形状与其唯一匹配实现的单元测试。

本文件钉 ``Pattern`` 的**匹配语义**：alternatives / 位置 token / ``skip_flags`` /
``strip_colon`` / ``requires_any_flag`` / 未知组合 fail-loud / ``is_literalizable``，
以及它的序列化 / 反序列化。``Pattern`` 是规则内容的**唯一**形状，
:meth:`Pattern.matches` 是 token 级匹配的**唯一**实现。

约定：``args`` **不含命令名**（命令名单独作为 ``name`` 传入），与
:func:`command_definitions.data_predicate_for` 的调用口径一致。

平台下发通道（``_spec_from_declaration`` 的搬运与准入）由
``test_command_security.py`` 覆盖，不在此。

只读形状与匹配实现，不改任何生产规则、不触碰 ``RULE_SPECS``。
"""

from __future__ import annotations

import json

import pytest
from aidev_agent.packages.security.command.command_definitions import (
    JUSTIFICATION_PARAMS,
    Pattern,
    RuleContext,
    RuleSpec,
    data_predicate_for,
    names,
    render_justification,
)
from aidev_agent.packages.security.command.command_rule_validation import (
    assert_justification_templates_are_consistent,
    justification_params,
    load_time_self_test,
)
from aidev_agent.packages.security.command.command_security import RULE_SPECS, validate_command
from aidev_agent.packages.security.command.command_syntax_rules import (
    SYNTAX_BRACE_EXPANSION,
    SYNTAX_RULES,
)
from aidev_agent.pydantic_models import SecurityCommandSettings

# ========== Pattern 的匹配语义 ==========


class TestPatternMatching:
    """``Pattern.matches`` 的全部修饰符行为（每个用例独立于生产规则）。"""

    @pytest.mark.parametrize(
        ("name", "args", "expected"),
        [
            ("rm", ["-rf", "/tmp"], True),
            ("rm", ["-fr", "/tmp"], True),
            ("rm", ["/tmp"], False),
            ("rm", [], False),
            ("ls", ["-rf"], False),
        ],
    )
    def test_alternatives_and_prefix(self, name, args, expected):
        """token 元素为 tuple 表 alternatives；首 token 不匹配即否。"""
        assert Pattern(tokens=("rm", ("-rf", "-fr"))).matches(name, args) is expected

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (["777", "/tmp/x"], True),
            (["644", "/tmp/x"], False),
            (["/tmp/x"], False),
            ([], False),
        ],
    )
    def test_positional_equals(self, args, expected):
        """位置 token 与 ``positional_equals`` 比较（默认 index=0）。"""
        assert (
            Pattern(
                tokens=("chmod",),
                positional_index=0,
                positional_equals=frozenset(
                    {
                        "777",
                    }
                ),
            ).matches("chmod", args)
            is expected
        )

    def test_positional_result_is_independent_of_token_prefix(self):
        """位置比较**独立于** token 前缀：index 到位且值相符即命中。"""
        pattern = Pattern(tokens=("apt-get",), positional_index=0, positional_equals=frozenset({"install"}))
        assert pattern.matches("apt-get", ["install", "vim"]) is True
        assert pattern.matches("apt-get", ["remove", "vim"]) is False

    def test_skip_flags_are_honoured(self):
        """列举的 ``skip_flags`` 参与位置定位。"""
        pattern = Pattern(
            tokens=("apt-get",),
            positional_index=0,
            positional_equals=frozenset({"install"}),
            skip_flags=frozenset({"-y", "--yes"}),
        )
        assert pattern.matches("apt-get", ["-y", "install", "x"]) is True
        assert pattern.matches("apt-get", ["--yes", "install", "x"]) is True

    @pytest.mark.parametrize(
        ("index", "args", "expected"),
        [
            # index=0 取第 1 个非选项 token
            (0, ["install", "vim"], True),
            (0, ["-y", "install", "vim"], True),
            # index=1 取第 2 个非选项 token —— 与 index=0 **必须**可区分
            (1, ["install", "vim"], False),
            (1, ["-y", "install", "vim"], False),
            # index 超出可用操作数 → 不命中（而非抛错 / 误命中）
            (5, ["-y", "install", "vim"], False),
            (0, [], False),
        ],
    )
    def test_positional_index_selects_the_nth_operand(self, index, args, expected):
        """``positional_index`` 真的是「第 N 个非选项 token」，不是被忽略的装饰。

        这条断言是**突变测试的落点**：若把 ``index`` 从 ``_positional_operand`` 的定位
        逻辑中丢掉（恒取第 0 个），``index=1`` 的两例必须变红。
        """
        pattern = Pattern(
            tokens=("apt-get",),
            positional_index=index,
            positional_equals=frozenset({"install"}),
            skip_flags=frozenset({"-y"}),
        )
        assert pattern.matches("apt-get", args) is expected

    def test_unlisted_prefix_flag_breaks_positional_lookup(self):
        """未列举的前缀 flag **不**被跳过——跳过集必须精确，否则会误命中。"""
        pattern = Pattern(
            tokens=("apt-get",),
            positional_index=0,
            positional_equals=frozenset({"install"}),
            skip_flags=frozenset({"-y", "--yes"}),
        )
        # ``-o`` 未列举，是**带值**选项：其值 ``X`` 成为第 0 个非选项 token。
        assert pattern.matches("apt-get", ["-o", "X", "install", "x"]) is False

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (["-F"], True),
            ([], False),
            (["input"], False),
            (["accept", "--dport", "22"], True),
        ],
    )
    def test_requires_any_flag(self, args, expected):
        """``requires_any_flag``：存在**任一** ``-`` 开头参数即满足（不指定具体 flag）。"""
        assert (
            Pattern(
                tokens=(
                    names(
                        "iptables",
                    ),
                ),
                requires_any_flag=True,
            ).matches("iptables", args)
            is expected
        )

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (["root:grp", "f"], True),
            (["root", "f"], True),
            (["bob:grp", "f"], False),
            (["bob", "f"], False),
        ],
    )
    def test_strip_colon(self, args, expected):
        """``strip_colon`` 比较前按第一个 ``:`` 切分取前段。"""
        assert (
            Pattern(
                tokens=("chown",),
                positional_index=0,
                positional_equals=frozenset(
                    {
                        "root",
                    }
                ),
                strip_colon=True,
            ).matches("chown", args)
            is expected
        )

    def test_strip_colon_without_positional_raises(self):
        """``strip_colon`` 单独出现（无位置比较）是无意义组合 → 构造期 fail-loud。"""
        with pytest.raises(ValueError, match="strip_colon"):
            Pattern(tokens=("chown",), strip_colon=True)

    @pytest.mark.parametrize(
        ("name", "expected"),
        [("rm", True), ("RM", False), ("/bin/rm", False), ("sudo", False)],
    )
    def test_name_is_compared_exactly(self, name, expected):
        """名字**精确相等**：不做 basename / sudo / 路径后缀投影。"""
        assert Pattern(tokens=("rm",)).matches(name, ["-rf", "/tmp"]) is expected


class TestChmodReferenceSkipSemantics:
    """``@chmod --reference`` 的「多跳一格」语义在本层（``Pattern`` 侧）的独立钉住。

    同一语义在注册表侧另有一条用例（``test_command_rules_registry``），两处各自
    独立断言，任一侧退化都会被自己的用例打红。
    """

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            # ``--reference``（无 =）吞掉自身与下一个 token → 再跳 1 格后取到 777
            (["--reference", "/tmp/ref", "777", "/tmp/x"], True),
            # ``--reference=<v>`` 只吞自身 → 777 紧随其后
            (["--reference=/tmp/ref", "777", "/tmp/x"], True),
            # ``--`` 终止符只跳一格，其后 token 仍按操作数取用
            (["--", "777", "/tmp/x"], True),
            # 操作数是 644 而非 777
            (["--reference", "/tmp/ref", "644", "/tmp/x"], False),
        ],
    )
    def test_reference_skip(self, args, expected):
        assert (
            Pattern(
                tokens=("chmod",),
                positional_index=0,
                positional_equals=frozenset(
                    {
                        "777",
                    }
                ),
            ).matches("chmod", args)
            is expected
        )


class TestPatternFailLoud:
    """未知 / 无意义的修饰符组合**绝不静默放行**。"""

    def test_positional_equals_without_index_raises(self):
        with pytest.raises(ValueError) as excinfo:
            Pattern(tokens=("x",), positional_equals=frozenset({"a"}))
        # 消息须带实际取值，供归因
        assert "positional_equals" in str(excinfo.value)
        assert "a" in str(excinfo.value)

    @pytest.mark.parametrize("skip_flags", [frozenset(), frozenset({"-y"})])
    def test_skip_flags_alone_are_allowed(self, skip_flags):
        """``skip_flags`` 本身不构成非法组合（只在位置定位时被消费）。"""
        assert Pattern(tokens=("apt",), skip_flags=skip_flags).matches("apt", ["install"]) is True

    def test_empty_pattern_matches_nothing(self):
        """``Pattern()`` 合法但「无内容」——恒不命中。"""
        empty = Pattern()
        assert empty.matches("anything", []) is False
        assert empty.matches("rm", ["-rf", "/tmp"]) is False

    @pytest.mark.parametrize(
        "tokens",
        [
            ("a", []),  # 空 alternatives
            ("a", ("b", 123)),  # alternatives 含非字符串
            ("a", [["b"]]),  # list 不是 tuple（Codex 的 JSON 形状是 list，内部形状是 tuple）
            ("a", {"b"}),  # set 无顺序语义
        ],
        ids=["empty_tuple", "non_string_item", "list_not_tuple", "set"],
    )
    def test_malformed_tokens_are_rejected_at_construction(self, tokens):
        """畸形 ``tokens`` 构造期 fail-loud —— 这是**隐式形状约定的唯一守卫**。

        约定：每个元素是 ``str``（字面 token）或非空 ``tuple[str, ...]``（alternatives）。
        若让畸形形状通过，派生视图会按下标取 ``tokens[0]`` 并假定它是 alternatives
        元组，从而**静默给出错误的命令名集合**——比抛错危险得多。
        """
        with pytest.raises(ValueError):
            Pattern(tokens=tokens)

    @pytest.mark.parametrize(
        ("pattern", "expected"),
        [
            (Pattern(tokens=(names("rm"),)), True),
            (
                Pattern(
                    tokens=(
                        "rm",
                        names(
                            "-rf",
                        ),
                    )
                ),
                True,
            ),
            (
                Pattern(
                    tokens=("chmod",),
                    positional_index=0,
                    positional_equals=frozenset(
                        {
                            "777",
                        }
                    ),
                ),
                True,
            ),
            (
                Pattern(
                    tokens=(
                        names(
                            "iptables",
                        ),
                    ),
                    requires_any_flag=True,
                ),
                True,
            ),
            (Pattern(), False),
        ],
    )
    def test_is_literalizable(self, pattern, expected):
        """``is_literalizable``：``tokens`` 非空且修饰符组合合法（下发准入判据）。"""
        assert pattern.is_literalizable is expected

    @pytest.mark.parametrize(
        ("pattern", "expected"),
        [
            (Pattern(), True),
            (Pattern(tokens=(names("rm"),)), False),
            (Pattern(positional_index=0, positional_equals=frozenset({"x"})), False),
            (Pattern(tokens=(names("x"),), requires_any_flag=True), False),
        ],
        ids=["no_content", "tokens", "positional_only", "any_flag_only"],
    )
    def test_is_empty_tracks_having_content(self, pattern, expected):
        """``is_empty`` 判「有无可判定内容」：无 token 且未启用位置 / 存在性修饰符。

        与 ``is_literalizable`` **不是**互补关系——``positional_only`` 一例两者皆为假，
        故不得把二者合并成一个属性。
        """
        assert pattern.is_empty is expected


class TestRuleSpecEntryGuardUnchanged:
    """本层的 entry 守卫：``data_predicate_for`` 在无 entry 时返回空。

    registry 侧另有同语义用例，分工是：那边经 ``RuleContext`` 直取，这边钉
    ``data_predicate_for`` 的入口行为。
    """

    def test_data_predicate_without_entry_yields_no_hits(self):
        predicate = data_predicate_for(Pattern(tokens=(names("rm"),)), rule_id="r", reason="x", verdict="block")
        assert predicate(RuleContext(walked=None, entry=None)) == ()


# ========== 加载期自测 ==========


def _spec(**kwargs) -> RuleSpec:
    """构造一条**只用于自测**的最小 ``RuleSpec``（不登记、不进 ``RULE_SPECS``）。"""
    base = {
        "rule_id": "self_test",
        "category": "test",
        "verdict": "block",
        "justification": "自测用",
        "pattern": Pattern(tokens=(names("rm"),)),
    }
    return RuleSpec(**{**base, **kwargs})


class TestLoadTimeSelfTest:
    """``load_time_self_test`` 的失败行为与跳过判据（失败 = ``AssertionError``）。"""

    def test_match_sample_that_is_not_hit_raises(self):
        """``match`` 里写了不被命中的样例 → 必须抛（样例写错是最典型的失效面）。"""
        spec = _spec(match=(("ls",),))
        with pytest.raises(AssertionError, match="match 样例未被自身 pattern 命中"):
            load_time_self_test([spec])

    def test_not_match_sample_that_is_hit_raises(self):
        """``not_match`` 里写了**被命中**的样例 → 必须抛（否定样例不成立）。"""
        spec = _spec(not_match=(("rm -rf /tmp",),))
        with pytest.raises(AssertionError, match="not_match 样例被自身 pattern 命中"):
            load_time_self_test([spec])
        # 同一 spec 的 match 侧是自洽的（``rm`` 命中 name-only pattern）——证明上抛
        # 来自 not_match 分支，而非 pattern 本身写错。
        load_time_self_test([_spec(match=(("rm -rf /tmp",),))])

    def test_code_rule_is_skipped(self):
        """``pattern is None`` 的规则**跳过**（计划裁决 3：code 规则自测由测试文件承担）。"""
        spec = _spec(pattern=None, match=(("this would never be checked",),))
        load_time_self_test([spec])  # 不抛即通过

    def test_consistent_samples_pass(self):
        spec = _spec(match=(("rm -rf /tmp",),), not_match=(("ls",),))
        load_time_self_test([spec])

    def test_string_samples_are_shlex_split(self):
        """字符串样例按 ``shlex`` 分词（Codex 语义，支持引号）。"""
        spec = _spec(
            pattern=Pattern(tokens=(names("curl"),)),
            match=("curl 'http://x?token=a'",),
            not_match=("wget http://x",),
        )
        load_time_self_test([spec])

    def test_token_tuple_and_string_forms_are_equivalent(self):
        """``("rm -rf /tmp",)`` 与 ``"rm -rf /tmp"`` 等价——两种写法都不必猜。"""
        load_time_self_test([_spec(match=(("rm -rf /tmp",),), not_match=(("ls",),))])
        load_time_self_test([_spec(match=("rm -rf /tmp",), not_match=("ls",))])
        load_time_self_test([_spec(match=(("rm", "-rf", "/tmp"),), not_match=(("ls", "-la"),))])

    def test_empty_match_sample_raises(self):
        """空样例**不得**被当作「无约束」静默放过。"""
        spec = _spec(match=("   ",))
        with pytest.raises(AssertionError, match="match 样例为空"):
            load_time_self_test([spec])

    def test_real_import_passes(self):
        """全 29 条真实规则的自测样例自洽——真实导入不抛。"""
        load_time_self_test(RULE_SPECS.values())

    def test_second_argument_is_optional_in_signature(self):
        """``not_match`` 缺省为空 → 只校验 ``match``（不因缺省而跳过校验）。"""
        spec = _spec(match=(("rm -rf /tmp",),))
        load_time_self_test([spec])


class TestEveryPatternRuleCarriesBothSamples:
    """**每条** ``pattern`` 规则都自带非空的双向样例（覆盖断言）。"""

    def test_every_pattern_rule_has_non_empty_samples(self):
        """防止「只写 ``match`` 不写 ``not_match``」的**单向自测**。"""
        pattern_rules = [spec for spec in RULE_SPECS.values() if spec.pattern is not None]
        assert pattern_rules  # 非空，防止断言在空集合上恒真
        offenders = [spec.rule_id for spec in pattern_rules if not spec.match or not spec.not_match]
        assert offenders == []

    def test_the_expected_pattern_rules_are_covered(self):
        """可字面化的规则集合被钉住（新增/删除可字面化规则必须显式改这条）。"""
        expected = {
            "shutdown_reboot",
            "user_management",
            "shred_file",
            "rm_recursive_force",
            "rm_forbidden",
            "chmod_777",
            "chown_root",
            "package_install",
            "firewall_change",
            "syntax:forbidden_command",
            "allowlist:allowed",
        }
        assert {spec.rule_id for spec in RULE_SPECS.values() if spec.pattern is not None} == expected

    def test_code_rules_declare_no_samples(self):
        """``pattern=None`` 的规则**不**写样例——它们的自测归测试文件（裁决 3）。"""
        code_rules = [spec for spec in RULE_SPECS.values() if spec.pattern is None]
        assert code_rules
        assert all(not spec.match and not spec.not_match for spec in code_rules)

    def test_positional_with_name_set_uses_alternatives(self):
        """位置匹配 + 名字集合：``tokens[0]`` 是 ``names(...)`` 的 alternatives（单 token）。"""
        pattern = Pattern(
            tokens=(names("apt", "yum"),),
            positional_index=0,
            positional_equals=frozenset(
                {
                    "install",
                }
            ),
            skip_flags=frozenset({"-y"}),
        )
        assert pattern.tokens == (("apt", "yum"),)
        assert pattern.matches("apt", ["-y", "install", "x"]) is True
        assert pattern.matches("dnf", ["install", "x"]) is False


# ========== Pattern 的序列化 / 反序列化 ==========


_CANONICAL_PATTERNS = [
    ("bare_name", Pattern(tokens=("shred",))),
    ("name_set", Pattern(tokens=(names("halt", "poweroff", "reboot", "shutdown"),))),
    ("name_and_flag_alternatives", Pattern(tokens=("rm", names("-rf", "-fr")))),
    ("positional", Pattern(tokens=("chmod",), positional_index=0, positional_equals=frozenset({"777"}))),
    (
        "positional_strip_colon",
        Pattern(tokens=("chown",), positional_index=0, positional_equals=frozenset({"root"}), strip_colon=True),
    ),
    (
        "name_set_positional_skip_flags",
        Pattern(
            tokens=(names("apt", "apt-get"),),
            positional_index=0,
            positional_equals=frozenset({"install"}),
            skip_flags=frozenset({"-y", "--yes"}),
        ),
    ),
    ("any_flag", Pattern(tokens=(names("iptables", "ip6tables"),), requires_any_flag=True)),
]


class TestPatternMappingRoundTrip:
    """``to_mapping`` / ``from_mapping`` 是**一对**：任何字段增减都须两侧同步。"""

    @pytest.mark.parametrize(("name", "pattern"), _CANONICAL_PATTERNS, ids=[n for n, _ in _CANONICAL_PATTERNS])
    def test_round_trip_is_identity(self, name, pattern):
        """7 种真实形态 round-trip 恒等（含 ``BLOCKLIST_RULES`` 的全部写法）。"""
        assert Pattern.from_mapping(pattern.to_mapping()) == pattern

    def test_mapping_is_json_encodable(self):
        """序列化产物是纯 JSON 可表达数据（``frozenset`` / 仅-tuple 类型不得漏出）。"""

        for name, pattern in _CANONICAL_PATTERNS:
            json.dumps(pattern.to_mapping())

    def test_mapping_keys_are_stable(self):
        """键集合被钉死 —— 「加字段必须两侧同步」的**可证伪闸门**。"""
        expected = {"tokens", "positional_index", "positional_equals", "skip_flags", "strip_colon", "requires_any_flag"}
        assert set(Pattern().to_mapping()) == expected

    def test_accepts_platform_json_shape(self):
        """``from_mapping`` 接受平台 JSON 原生 ``list`` 形态（也接受 tuple / frozenset）。"""
        p = Pattern.from_mapping(
            {
                "tokens": ["rm", ["-rf", "-fr"]],
                "positional_index": 0,
                "positional_equals": ["install"],
                "skip_flags": ["-y"],
            }
        )
        assert p.tokens == ("rm", ("-rf", "-fr"))
        assert p.positional_equals == frozenset({"install"})
        assert p.skip_flags == frozenset({"-y"})

    def test_str_token_is_not_split(self):
        """``str`` 也是 ``Sequence``，必须先排除 —— 否则 ``"rm"`` 会被拆成 ``("r","m")``。"""
        assert Pattern.from_mapping({"tokens": ["rm"]}).tokens == ("rm",)

    def test_empty_mapping_and_none_are_equivalent(self):
        """``from_mapping({})`` / ``from_mapping(None)`` 等价于 ``Pattern()``（全空合法）。"""
        assert Pattern.from_mapping({}) == Pattern.from_mapping(None) == Pattern()


class TestPatternMappingRejectsMalformedShapes:
    """非法形状仍**只由** ``__post_init__`` 拒收，``from_mapping`` 不自己再写判据。

    实测记录：``{"tokens": [""]}`` **是合法的**（空串是合法的字面 token，``__post_init__``
    只拒绝「非 str 且非非空 tuple」），故它不在此拒绝表中。``{"strip_colon": True}`` 与
    ``{"positional_equals": ["x"]}`` 都因「``positional_index is None`` 却有位置字段」
    被 ``__post_init__`` 拒；``{"skip_flags": True}`` 因 ``bool`` 冒充集合被拒。
    """

    @pytest.mark.parametrize(
        "payload",
        [
            {"positional_equals": ["x"]},  # positional_index is None 却有位置字段
            {"strip_colon": True},  # 同上
            {"tokens": [[[]]]},  # alternatives 含非字符串
            {"tokens": ["x"], "skip_flags": True},  # bool 冒充集合（类型错，须拒收）
        ],
        ids=["positional_without_index", "strip_colon_without_index", "non_str_alternative", "bool_skip_flags"],
    )
    def test_malformed_shapes_are_rejected(self, payload):
        with pytest.raises((ValueError, TypeError)):
            Pattern.from_mapping(payload)

    def test_empty_string_token_is_legal(self):
        """如实记录：「预期非法」的 ``{"tokens": [""]}`` 实测**合法**（空串是 str）。"""
        assert Pattern.from_mapping({"tokens": [""]}).tokens == ("",)

    def test_skip_flags_type_contract_is_frozenset(self):
        """``skip_flags`` 入参（合法 JSON ``list``）被归一为 ``frozenset``，不是静默变空集。

        ``bool`` 冒充集合的拒收已由 ``test_malformed_shapes_are_rejected[bool_skip_flags]``
        参数化覆盖，此处只钉「合法入参 → 正确的容器类型」。
        """
        assert isinstance(Pattern.from_mapping({"tokens": ["x"], "skip_flags": ["-y"]}).skip_flags, frozenset)


# ========== justification 模板化与占位符一致性 ==========


class TestJustificationTemplates:
    """``justification`` 模板的渲染与占位符一致性校验。"""

    def test_render_substitutes_all_placeholders_and_fails_loud_on_missing_key(self):
        """填充齐全是替换，填充不足是 ``KeyError``——「绝不渲染半截文案」两向闭合。

        两向放同一用例：它们测的是同一契约（模板占位符集合 == 填充键集合）的两面，
        分开写会让「缺键时静默返回半截串」这种退化只打红其中一条，掩盖契约本身。
        """

        template = "命令 '{name}' {detail}"
        assert render_justification(template, name="uname", detail="不允许") == "命令 'uname' 不允许"
        with pytest.raises(KeyError):
            render_justification(template, name="uname")

    def test_justification_params_extracts_names(self):
        assert justification_params("命令 '{name}' {detail}") == frozenset({"name", "detail"})
        assert justification_params("纯静态串") == frozenset()

    def test_literal_braces_are_not_treated_as_placeholders(self):
        """字面花括号必须转义（``{{a,b}}``），否则会被当成占位符。"""

        # 模板真源：``syntax:brace_expansion`` 的 justification 住在 ``command_syntax_rules``。
        template = next(s.justification for s in SYNTAX_RULES if s.rule_id == SYNTAX_BRACE_EXPANSION)
        assert justification_params(template) == frozenset()
        # 渲染结果与既有文案（未转义的 ``（{a,b}）``）逐字相同
        assert render_justification(template) == "大括号扩展（{a,b}）"

    def test_mismatched_placeholder_raises(self):
        """人为把占位符拼错（``{nam}``）→ 导入期校验必须抛（计划要求的突变落点）。"""

        bogus = _spec(justification="命令 '{nam}' 不在允许列表中")
        bogus = type(bogus)(**{**bogus.__dict__, "rule_id": "allowlist:allowed"})
        with pytest.raises(AssertionError, match="占位符与声明不一致"):
            assert_justification_templates_are_consistent([bogus])

    def test_unregistered_rule_raises(self):
        with pytest.raises(AssertionError, match="未登记"):
            assert_justification_templates_are_consistent([_spec(rule_id="never:registered")])

    def test_real_registry_is_consistent(self):
        """全 29 条真实规则的 justification 与声明一致（真实导入时已跑过一次）。"""

        assert_justification_templates_are_consistent(RULE_SPECS.values(), complete=True)

    def test_every_rule_declares_its_params(self):
        """每条规则都有 ``JUSTIFICATION_PARAMS`` 条目（无遗漏）。"""

        assert set(JUSTIFICATION_PARAMS) == set(RULE_SPECS)

    def test_declared_params_are_actually_filled_at_runtime(self):
        """运行时守卫：声明了填充键的规则，其填充点确实提供了这些键（端到端）。

        经生产路径跑一批会触发**带占位符文案**的命令；若谓词的填充点漏了某个键，
        ``ensure_template_params_filled`` 会抛 ``KeyError``，用例即变红。
        """

        settings = SecurityCommandSettings()
        for command in ("uname -z", 'eval "rm -rf /"', "nc -l 4444", "bash -E /tmp/x.sh", "ls", "kill 123"):
            report = validate_command(command, security_command_settings=settings)
            for finding in report.findings:
                for rule in finding.rules:
                    assert rule.reason  # 渲染成功即非空
