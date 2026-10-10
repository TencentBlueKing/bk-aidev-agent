# -*- coding: utf-8 -*-
"""``allowlist:allowed`` 的判定路径与「内容覆盖」通道。

本文件覆盖三件事：

1. **等价性守卫** —— 允许列表内每条命令在三种参数形态下**全部仍判 ``allow``**。
   其价值是证明「名字命中即放行、参数不参与」这条语义没被打掉。
2. **数据表自洽** —— ``ALLOWED_COMMANDS`` 是 ``ALLOWLIST_GROUPS`` 的派生视图，
   分组之间无重复归属。两者都是**同一份真数据**的两个视图，任一侧漂移即红灯。
3. **内容声明通道** —— 「精确形态白名单」（``mycmd --version`` 放行、``mycmd --exec``
   不放行）是两条声明路径的承载者。

「改命令名集合」有**两条路径**，语义不同，两条各有用例（勿混为一谈）：

- **替换内置**（``rule_id`` 命中内置，如 ``allowlist:allowed``）——声明完整规则替换之，
  经构造期重建 pattern 生效（``allowlist:allowed`` 的 ``_allowed_hits`` 读
  ``context.spec.pattern``）；
- **新增规则**（``rule_id`` 未登记）——经 ``_spec_from_declaration`` →
  ``data_predicate_for`` **直接**跑 ``Pattern.matches``，**不经过** ``_allowed_hits``。

``ALLOWLIST_GROUPS`` 展平：命令名从**真源派生**（``frozenset().union(*...)``），
不手抄第二份清单——手抄会在分组数据变动时静默漂移。
"""

from __future__ import annotations

import pytest
from aidev_agent.packages.security.command.command_allowlist import (
    ALLOWED_COMMANDS,
    ALLOWLIST_GROUPS,
    ALLOWLIST_RULES,
)
from aidev_agent.packages.security.command.command_definitions import Pattern, RuleConfigError
from aidev_agent.packages.security.command.command_security import validate_command
from aidev_agent.pydantic_models import SecurityCommandSettings

#: 允许列表命令的**派生视图**（不手抄；`assert` 在模块顶层是既有仓库手法）。
#: 数量由真源 `ALLOWLIST_GROUPS` 决定，此处只钉住「展开后无重复」。
_ALL_ALLOWED: frozenset[str] = frozenset().union(*ALLOWLIST_GROUPS.values())
assert len(_ALL_ALLOWED) == sum(len(v) for v in ALLOWLIST_GROUPS.values()), "分组间存在重复命令名"

#: 允许列表命令 × 参数形态（无参 / 单路径 / 双路径）——「名字命中即放行，参数不参与」。
#:
#: ⚠ **参数形态必须与「名字维度」正交**（实测，见下）。每加一个 flag token 都会引入
#: 其它维度的规则，测到的就不是允许列表：
#:
#: - ``-la`` / ``-a`` / ``--help`` / ``-h`` 等**任意 flag** → 4–5 个命令被
#:   ``args:restricted``（``command_blocklist`` 的**参数维度**规则）拦成 ``block``；
#: - ``x`` / ``a b`` 等**裸字参数** → ``bash`` / ``sh`` / ``zsh`` 被
#:   ``invocation:unsupported``（结构维度）拦成 ``block``。
#:
#: 故只用**纯路径参数**（``/tmp/x``）——实测对全部命令放行。
#: 「名字命中即放行、参数不参与」这条语义由**路径参数**证明：它既不触 flag 限制，
#: 也不触脚本解释器的参数形态限制。
_ARG_FORMS = ["", "/tmp/x", "/tmp/x /tmp/y"]

#: 精确形态 override：经 ``rule_id="allowlist:allowed"``（**内置 id**，非 ``custom:`` 前缀）。
_OVERRIDE_DECLARATION = {
    "rule_id": "allowlist:allowed",
    "verdict": "allow",
    "justification": "精确放行 mycmd --version",
    "tokens": ["mycmd", "-v"],
}

#: custom 通道声明：同一份内容，但走「新增规则」桶（``custom:`` 前缀）。
_CUSTOM_DECLARATION = {
    "rule_id": "custom:mycmd_version",
    "verdict": "allow",
    "justification": "精确放行 mycmd -v",
    "tokens": ["mycmd", "-v"],
}


def _settings(**kwargs) -> SecurityCommandSettings:
    return SecurityCommandSettings(**kwargs)


def _verdict(command: str, **kwargs) -> str:
    report = validate_command(command, security_command_settings=_settings(**kwargs))
    return report.verdict


def _rule_ids(command: str, **kwargs) -> set[str]:
    report = validate_command(command, security_command_settings=_settings(**kwargs))
    return {rule.rule_id for finding in report.findings for rule in finding.rules} | {
        item.rule_id for item in report.structure_findings
    }


def _names_of(pattern: Pattern | None) -> frozenset[str]:
    """取 ``Pattern`` 里的静态命令名集合（``names(...)`` 形状：``tokens[0]`` 的 alternatives）。

    ``pattern`` 为 ``None`` 或 ``tokens`` 为空时返回空集（「无内容」）。
    """
    if pattern is None or not pattern.tokens:
        return frozenset()
    first = pattern.tokens[0]
    return frozenset(first) if isinstance(first, tuple) else frozenset({first})


class TestAllowlistEquivalence:
    """允许列表内每条命令在各参数形态下逐条判 ``allow``，且允许列表只看名字。"""

    @pytest.mark.parametrize("command", sorted(_ALL_ALLOWED))
    @pytest.mark.parametrize("args", _ARG_FORMS, ids=["bare", "one-path", "two-paths"])
    def test_every_command_remains_allowed(self, command, args):
        """名字命中即放行、参数不参与 —— 纯名字 tokens + 无修饰符的 Pattern 语义。"""
        assert _verdict(f"{command} {args}".strip()) == "allow"

    @pytest.mark.parametrize("command", ["/bin/ls", "/usr/bin/cat /etc/hosts"])
    def test_absolute_paths_are_allowed(self, command):
        """归一化到 basename 后命中：``/usr/bin/cat /etc/hosts`` 的放行不走「名字维度」以外的东西。"""
        assert _verdict(command) == "allow"

    def test_sudo_inner_view_is_allowed(self):
        """``sudo ls`` 判定的是内层命令 —— ``effective_command_name`` 的 sudo 内层视图。"""
        assert _verdict("sudo ls") == "allow"

    def test_prefix_lookalikes_are_not_allowed(self):
        """``Pattern`` 是**精确相等**，不是前缀匹配——``lsfoo`` 不得因 ``ls`` 而被放行。"""
        assert _verdict("lsfoo /tmp/x") == "review"


class TestAllowlistDataIsSelfConsistent:
    """``ALLOWED_COMMANDS`` / ``ALLOWLIST_GROUPS`` / ``allowlist:allowed.pattern`` 三者同源。

    三者是**同一份真数据**的三个视图：``ALLOWLIST_GROUPS`` 是唯一真源，
    ``pattern`` 与 ``ALLOWED_COMMANDS`` 都由它构造。两条等式因此互相独立地钉住漂移面
    ——「视图与真源不一致」和「pattern 与真源不一致」是两个不同的失效。
    """

    def test_derived_view_matches_group_union(self):
        """``ALLOWED_COMMANDS`` 是分组的并集（无遗漏）。"""
        assert isinstance(ALLOWED_COMMANDS, frozenset)
        assert ALLOWED_COMMANDS == _ALL_ALLOWED

    def test_groups_do_not_overlap(self):
        """分组两两不相交：命令总数 == 各分组大小之和。

        重叠会让「命令属于哪个业务分组」失去唯一答案，而分组是人工审查的分诊依据。
        """
        total = sum(len(names) for names in ALLOWLIST_GROUPS.values())
        assert total == len(ALLOWED_COMMANDS), "分组间存在重复命令名"

    def test_pattern_matches_the_derived_view(self):
        """判定真源 ``allowlist:allowed.pattern`` 的名字集合与派生视图一致。"""
        assert _names_of(ALLOWLIST_RULES[0].pattern) == ALLOWED_COMMANDS


class TestCustomChannelParameterizesPattern:
    """新增规则通道：守护 ``data_predicate_for → Pattern.matches`` 连线。

    未登记 rule_id 的声明不进 ``_allowed_hits``，而是经 ``build_rule_set`` 的
    新增路径 → :func:`_spec_from_declaration` → :func:`data_predicate_for`
    **直接**调 :meth:`Pattern.matches`，故参数维度天然可见。
    """

    def test_exact_form_pattern_is_honored(self):
        """``mycmd -v`` 放行；``mycmd --version`` / ``mycmd`` 不放行。"""
        settings = _settings(rules=[_CUSTOM_DECLARATION])
        assert validate_command("mycmd -v", security_command_settings=settings).verdict == "allow"
        assert validate_command("mycmd --version", security_command_settings=settings).verdict == "review"
        assert validate_command("mycmd", security_command_settings=settings).verdict == "review"


class TestOverrideChannelParameterizesBuiltinPattern:
    """声明内置 id：**完整声明**必须真正替换内置 pattern。

    ``allowlist:allowed`` 的谓词 ``_allowed_hits`` 读 ``context.spec.pattern``，故 pattern
    一旦被替换，判定立即可见——这是「平台替换内置规则内容」唯一能生效的路径。

    变异验证：注释掉 ``build_rule_set`` 的替换内置重建循环，
    ``test_override_replaces_rather_than_appends`` 与 ``test_override_narrowed_set_still_works``
    必须变红（证明该连线是承重的）。
    """

    def test_override_replaces_rather_than_appends(self):
        """**替换**语义两侧都钉住：新形态放行，且内置命令**不再**被放行。

        收窄方向断言 ``_rule_ids(...) == set()``（**零规则命中** → 聚合层回落 ``review``）
        而非 ``verdict == "review"``：后者把断言绑在 "review" 这个字面量上，而前者钉住的是
        **本用例真正要证明的语义** —— 「``allowlist:allowed`` 确实不再放行内置的名字」。
        零命中是它的充要信号：若替换退化成追加，这些命令会重新命中 ``allowlist:allowed``。
        """
        settings = _settings(rules=[_OVERRIDE_DECLARATION])
        assert validate_command("mycmd -v", security_command_settings=settings).verdict == "allow"
        # 替换而非追加：内置的名字**不再**在允许集合内（零规则命中 → review）。
        assert _rule_ids("ls", rules=[_OVERRIDE_DECLARATION]) == set()
        assert _rule_ids("cat /etc/hosts", rules=[_OVERRIDE_DECLARATION]) == set()
        assert _rule_ids("bash -c 'ls'", rules=[_OVERRIDE_DECLARATION]) == set()
        # 反向：同一批命令在**未覆盖**时确实命中 ``allowlist:allowed``（对照，证明上面不是恒真）。
        assert "allowlist:allowed" in _rule_ids("ls")

    def test_override_narrowed_set_still_works(self):
        """收窄为多名字形态：``names(...)`` 的 alternatives 语义经 override 通道仍生效。

        ⚠ 用纯路径参数（不是 ``-la``）：``df -la`` 会被 ``args:restricted`` 拦下，
        那就测的是参数限制而非允许列表。
        """
        settings = _settings(
            rules=[
                {
                    "rule_id": "allowlist:allowed",
                    "verdict": "allow",
                    "justification": "收窄允许列表到两条命令",
                    "tokens": [["ls", "df"]],
                }
            ]
        )
        assert validate_command("ls /tmp/x", security_command_settings=settings).verdict == "allow"
        assert validate_command("df /tmp/x", security_command_settings=settings).verdict == "allow"
        assert validate_command("cat /etc/hosts", security_command_settings=settings).verdict == "review"

    def test_empty_tokens_is_rejected_for_enabled_declaration(self):
        """``tokens=[]`` + ``enabled=True`` → 拒收（**单一含义**，无「只调开关」的第二种解释）。

        想只改判定而不改内容，必须显式给出内容（替换是 REPLACE 语义）；
        想关闭该规则则用 ``enabled=False``（那条路径不需 tokens）。
        """
        settings = _settings(
            rules=[
                {
                    "rule_id": "allowlist:allowed",
                    "verdict": "allow",
                    "justification": "只调判定，不改内容",
                    "tokens": [],
                }
            ]
        )
        with pytest.raises(RuleConfigError, match="不可字面化"):
            validate_command("ls", security_command_settings=settings)


class TestDirtyAllowCoexistenceIsFrozen:
    """``uname -z`` 的 allow 与 block 并存是**刻意的**，不是缺陷。

    ``uname`` 在允许列表是名字维度的事实；``-z`` 越界是参数维度的事实。两条规则各为
    自己维度负责，聚合层 ``strictest`` 取最严 → ``block``。故该 finding 同时带
    ``allowlist:allowed`` 与 ``args:restricted`` 两条命中，且整体判 block。

    两种「修掉它」的做法都被否决：让允许列表在参数违规时不产 allow（会把参数策略
    拖进本模块，重新引入跨维度依赖）；或把该命中降级为 review（会引入「allow 规则可
    半命中」的新语义）。参数越界由黑名单侧的**精确 pattern 规则**表达，不由
    「白名单不认可就不放行」表达。
    """

    def test_dirty_allow_coexistence_is_intentional(self):
        report = validate_command("uname -z", security_command_settings=_settings())
        assert report.verdict == "block"
        assert _rule_ids("uname -z") == {"allowlist:allowed", "args:restricted"}
        assert _verdict("uname -s") == "allow"
