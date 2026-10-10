# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_rule_validation

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

命令规则的**导入期（加载期）自检**集中地。

本模块收拢「内置规则的导入期自检」——它们**不是运行时校验**，而是导入 / 加载期
跑一次、失败即 ``raise AssertionError`` 的 fail-loud 防线：

- :func:`load_time_self_test` —— 每条 ``pattern`` 规则的 ``match`` / ``not_match``
  样例自洽（Codex 的「think of them as unit tests」）；
- :func:`assert_justification_templates_are_consistent` —— 规则 ``justification``
  的占位符集合与该规则声明的填充键集合逐字相等；
- :func:`assert_rule_invariants` —— 规则**全集**的六类不变量（计数 / 谓词非空 /
  双向样例 / 样例自洽 / 占位符一致性 / 黑名单形态完备性），由聚合点在定义
  ``RULE_SPECS`` 之后调用。

**与运行时守卫的区别**（刻意不同名、不同文件）：运行时守卫
（``command_definitions.ensure_template_params_filled``）在**每次**谓词填充文案时
调用，读的是同一份声明，但它住在 ``command_definitions``（与
``JUSTIFICATION_PARAMS`` / ``render_justification`` 同居）。本模块只承载
「导入期跑一次」的检查。

依赖方向：本模块是 ``command_definitions`` 与数据模块（``command_blocklist``）的
**下游旁支**——只从中取类型与常量（``RuleSpec`` / ``JUSTIFICATION_PARAMS`` /
``BLOCKLIST_CATEGORIES`` / ``ALL_BLOCKLIST_RULES``）。
**不得** import ``command_security``（聚合点才是 ``RULE_SPECS`` 的产出方，
反向依赖会成环）；全集靠 ``assert_rule_invariants`` 的入参**注入**。
本模块自身**不**在模块级跑任何断言（缺 ``specs``），只定义函数。
"""

from __future__ import annotations

import shlex
import string
from collections.abc import Sequence
from typing import Any, Iterable, Mapping

from .command_blocklist import (
    ALL_BLOCKLIST_RULES,
    BLOCKLIST_CATEGORIES,
)
from .command_definitions import (
    JUSTIFICATION_PARAMS,
    RuleSpec,
)

# ========== 加载期自测 ==========
#
# Codex 的 ``match`` / ``not_match``：「think of them as unit tests」——每条规则自带
# 可证伪样例，在**导入期**校验。本仓库的既有传统是导入期 ``raise AssertionError``
# 的 fail-loud 自检（``command_blocklist`` / ``command_security`` 各有数处），
# 本函数是该传统在「样例校验」上的落地。


def _sample_tokens(sample: "str | Sequence[str]") -> list[str]:
    """把一个样例归一化为 token 列表。

    两种写法都支持（Codex 语义）：

    - ``str``：整串按 ``shlex`` 分词（``"rm -rf /tmp"`` → ``["rm", "-rf", "/tmp"]``）；
    - 序列：**每个元素**是 token（``("rm", "-rf")``）；序列里的 ``str`` 元素若含空白
      亦按 ``shlex`` 分词，使 ``("rm -rf /tmp",)`` 与 ``"rm -rf /tmp"`` 等价
      ——两种写法不必让人猜哪一种是「对的」。

    空串 / 只含空白的元素被跳过（``shlex.split`` 自身对空串返回 ``[]``）。
    **不做** ``re`` 分词；样例是源码内字面量（可信），按 shell 词法解析即可。
    """
    if isinstance(sample, str):
        return shlex.split(sample.strip())
    tokens: list[str] = []
    for item in sample:
        tokens.extend(shlex.split(item.strip()) if isinstance(item, str) else [item])
    return tokens


def load_time_self_test(specs: Iterable[Any]) -> None:
    """加载期校验每条 ``pattern`` 规则的 ``match`` / ``not_match`` 样例。

    对传入的每条规则：

    - ``match`` 中每个样例必须**被该规则的 ``pattern`` 命中**；
    - ``not_match`` 中每个样例必须**不**被命中；
    - ``pattern is None`` 的规则（代码谓词）**跳过**——其自测由测试文件承担。
      取舍（计划裁决 3）：在加载期校验代码谓词需要构造 ``WalkResult`` 与
      ``RuleContext``，成本高于收益；现状已由 ``test_command_blocklist`` /
      ``test_command_rules_registry`` 的语料断言覆盖。

    **校验的是「``pattern`` 能否被该样例命中」，不是「端到端是否命中」**：对
    ``syntax:forbidden_command`` / ``allowlist:allowed`` 这类规则，实际判定由代码
    谓词承担（它读 ``context.spec.pattern`` 的内容），``pattern`` 只是静态集合的载体。
    故本函数证明的是「样例与该 ``pattern`` 自洽」；端到端覆盖由语料断言承担。
    两者的差异是刻意的，勿把本函数误读为端到端自测。

    **不能静默跳过**——「样例写了但没验证」正是本阶段要消除的失效面。
    失败抛 :class:`AssertionError`（**不用** ``RuleConfigError``：那是平台配置错，
    与内置规则自测错归因不同），且消息带 ``rule_id`` 与违规样例，供直接定位。

    Args:
        specs: 规则集合（鸭子类型：只用 ``rule_id`` / ``pattern`` / ``match`` /
            ``not_match`` 四个属性）。

    Raises:
        AssertionError: 某条 ``match`` 样例不被命中，或某条 ``not_match`` 样例被命中。
    """
    for spec in specs:
        pattern = getattr(spec, "pattern", None)
        if pattern is None:
            continue
        rule_id = spec.rule_id
        for sample in spec.match:
            tokens = _sample_tokens(sample)
            if not tokens:
                raise AssertionError(f"规则 {rule_id!r} 的 match 样例为空（无从校验，且多半是笔误）：{sample!r}")
            if not pattern.matches(tokens[0], tokens[1:]):
                raise AssertionError(
                    f"规则 {rule_id!r} 的 match 样例未被自身 pattern 命中：{sample!r}"
                    f"（{pattern!r}）——样例与 pattern 不自洽。"
                )
        for sample in spec.not_match:
            tokens = _sample_tokens(sample)
            if not tokens:
                raise AssertionError(f"规则 {rule_id!r} 的 not_match 样例为空：{sample!r}")
            if pattern.matches(tokens[0], tokens[1:]):
                raise AssertionError(
                    f"规则 {rule_id!r} 的 not_match 样例被自身 pattern 命中：{sample!r}"
                    f"（{pattern!r}）——否定样例必须被拒，否则它不证明任何事。"
                )


def justification_params(template: str) -> frozenset[str]:
    """取 ``template`` 里的占位符名集合（``str.format`` 语法）。

    ``string.Formatter().parse()`` 的字段名可能带属性 / 索引（如 ``{a.b}`` / ``{a[0]}``），
    本仓库只用简单名，故取第一个 ``.`` / ``[`` 之前的部分；无名占位符（``{}``）会
    产生 ``None``，此处跳过（本仓库不使用位置参数占位符——它们无法被键集合校验）。
    """
    names: set[str] = set()
    for _, field_name, _, _ in string.Formatter().parse(template):
        if field_name is None:
            continue
        names.add(field_name.split(".")[0].split("[")[0])
    return frozenset(names)


def assert_justification_templates_are_consistent(specs: Any, *, complete: bool = False) -> None:
    """导入期校验：每条规则的 ``justification`` 占位符集合 == 声明的填充键集合。

    与 :func:`load_time_self_test` **同型**——都是导入期跑一次、失败即抛
    :class:`AssertionError` 的自检（区别于运行时守卫
    ``command_definitions.ensure_template_params_filled``）。二者由编排层聚合点成对
    调用（``command_security`` 的导入期自检），错误归因同型，故同居本模块。

    **为什么需要这道闸门**：``justification`` 会**进入报告路径**（展示给模型与审批人），
    故「模板占位符拼错 / 谓词少填一个键」会**静默**产出残缺文案——校验必须在导入期
    把两侧钉死，而不是等到报告里出现半截句子。

    校验（全部 ``AssertionError``，与 :func:`load_time_self_test` 同型）：

    1. 每条传入规则的 ``justification`` 的占位符集合 == :data:`JUSTIFICATION_PARAMS`
       里声明的键集合 —— 两侧任一漂移都失败；
    2. ``complete=True`` 时（**只在全集规则的聚合点**），额外要求
       :data:`JUSTIFICATION_PARAMS` 的键集合 == 传入规则集合的 id 集合 —— 防止
       「加了一条规则但忘了登记模板参数」。
       数据模块**各自**调用时不查这一条：它们只看得见自己那几条规则，全局完备性
       只有聚合点能判定。

    Args:
        specs: 规则集合（鸭子类型：只用 ``rule_id`` / ``justification``）。
        complete: 传入的是否为**规则全集**。数据模块传 ``False``（缺省），
            编排层的聚合点传 ``True``。

    Raises:
        AssertionError: 任一条校验不成立。
    """
    specs_by_id = {spec.rule_id: spec for spec in specs}

    # 未登记的规则（无论哪个 scope 都是错误——模板参数没声明就无法被校验覆盖）。
    missing_declarations = sorted(set(specs_by_id) - set(JUSTIFICATION_PARAMS))
    if missing_declarations:
        raise AssertionError(
            f"以下规则的 justification 模板参数未登记（JUSTIFICATION_PARAMS 缺条目）："
            f"{missing_declarations}——未登记的规则无法被占位符一致性校验覆盖。"
        )
    if complete:
        extra_declarations = sorted(set(JUSTIFICATION_PARAMS) - set(specs_by_id))
        if extra_declarations:
            raise AssertionError(
                f"JUSTIFICATION_PARAMS 含未登记规则的条目：{extra_declarations}（规则已删除或 id 拼写错误？）"
            )

    for rule_id, spec in specs_by_id.items():
        declared = JUSTIFICATION_PARAMS[rule_id]
        actual = justification_params(spec.justification)
        if declared != actual:
            raise AssertionError(
                f"规则 {rule_id!r} 的 justification 占位符与声明不一致："
                f"模板 {spec.justification!r} 解析出 {sorted(actual)!r}，"
                f"但 JUSTIFICATION_PARAMS 声明 {sorted(declared)!r}"
                f"——占位符拼错会静默产生残缺文案（T-11-15）。"
            )
        if declared and not actual:
            raise AssertionError(
                f"规则 {rule_id!r} 声明了填充键 {sorted(declared)!r}，但 justification "
                f"是纯静态串（{spec.justification!r}）——声明与模板必须一致。"
            )


#: 「无法判定」类 block 的 category 集合（与「已知危险」相对）。
#:
#: 这些规则**也是黑名单形态**（命中即硬拒、不可审批），但打回理由不是「命令危险」，
#: 而是「无法判定」，故刻意不进 ``BLOCKLIST_CATEGORIES``：
#:
#: - ``dynamic`` —— 执行内容静态不可知（``python -c`` / 未建模包装器）；
#: - ``syntax`` —— 调用形态已解析且**结构本身被禁**（后台执行符 / 重定向 / 大括号扩展等，
#:   由 ``command_syntax_rules`` 导出）；
#: - ``ast`` —— 参数中含未建模的执行结构（``ast:unsupported_parameter_execution``，
#:   由 ``command_syntax_rules`` 导出）；
#: - ``invocation`` —— 调用形态已解析但 **argv 未被本 SDK 的 shell adapter 建模**，
#:   无法确定脚本位置（``invocation:unsupported``，由 ``command_blocklist`` 导出）。
#:
#: ``syntax`` / ``ast`` 归属 ``command_syntax_rules``；``dynamic`` / ``invocation``
#: 归属 ``command_blocklist``——故 6c 的「block 必属 ALL_BLOCKLIST_RULES」只覆盖后两者。
#: 四条均不受 ``enable_command_blocklist`` 开关管辖——关掉「已知危险」不应一并关掉结构防线。
#: **新增本集合成员须在此登记并说明其语义**（6b 是精确相等断言，漏登记即 import 期失败）。
_NON_HAZARD_BLOCK_CATEGORIES: frozenset[str] = frozenset({"dynamic", "syntax", "ast", "invocation"})


def assert_rule_invariants(specs: Mapping[str, RuleSpec], *, expected_count: int) -> None:
    """规则全集的**全部导入期不变量**（唯一入口；`# pragma: no cover` 为导入期自检）。

    收拢在此的理由：这些不变量分三类——**单条**级（谓词非空、样例双向自洽）、
    **跨模块**级（id 唯一、计数）、**与 ``command_definitions`` 的模板表耦合**级（占位符一致性）。
    只有聚合点 ``command_security`` 同时看得见三者，且它已 import 其余模块；
    而本模块是下游旁支（不得 import ``command_security``），全集由调用方**注入**。

    依赖方向说明：本函数读 :data:`BLOCKLIST_CATEGORIES` / :data:`ALL_BLOCKLIST_RULES`
    （来自 ``command_blocklist``）与 :data:`_NON_HAZARD_BLOCK_CATEGORIES`（本模块）——
    均为常量，不成环。运行时机制（``build_rule_set`` 等）不在此的消费面内。

    Args:
        specs: ``rule_id -> RuleSpec`` 的规则全集。
        expected_count: 期望的规则条数。**重复 id**（某条规则被两个模块同时导出）
            会让 dict 构造静默覆盖——计数仍然正确而内容错位，故必须显式断言计数。

    Raises:
        AssertionError: 任一不变量不成立。选 ``AssertionError`` 而非
            ``RuleConfigError``：后者是**平台配置错**，这里是**内置规则自测错**，
            归因不同、失败时该看的地方也不同。
    """
    # ---- 1. 计数与幂等：真正的风险是重复 id（dict 静默覆盖）。----
    if len(specs) != expected_count:
        raise AssertionError(f"RULE_SPECS 应为 {expected_count} 条，实为 {len(specs)}；存在重复 rule_id？")
    if any(spec.rule_id != rule_id for rule_id, spec in specs.items()):
        raise AssertionError("RULE_SPECS 存在键与 spec.rule_id 不一致的条目（拷贝粘贴错位？）")

    # ---- 2. 每条规则都必须有判据：缺谓词 = **规则永不生效**（最危险的静默失效）。----
    inert = sorted(rule_id for rule_id, spec in specs.items() if spec.predicate is None)
    if inert:
        raise AssertionError(f"以下规则没有谓词（注册了但永不生效）：{inert}")

    # ---- 3. 可字面化者必须有非空样例（单向自测无效）。----
    missing_samples = sorted(
        rule_id
        for rule_id, spec in specs.items()
        if spec.pattern is not None and (not spec.match or not spec.not_match)
    )
    if missing_samples:
        raise AssertionError(f"以下可字面化规则缺少非空的 match / not_match 样例（单向自测无效）：{missing_samples}")

    # ---- 4. 样例与 pattern 自洽：防「样例是注释、pattern 改了没人发现」。----
    load_time_self_test(specs.values())

    # ---- 5. justification 占位符一致性。----
    # complete=True：聚合点额外要求 JUSTIFICATION_PARAMS 的键集合 == 规则 id 集合，
    # 防「加了规则但忘了登记模板参数」。
    assert_justification_templates_are_consistent(specs.values(), complete=True)

    # ---- 6. 黑名单形态的完备性（三层断言，见下方说明）。----
    #
    # 单纯「block ⇒ 属 BLOCKLIST_CATEGORIES」是**错的**：黑名单有多种形态，
    # 只有「已知危险」那一类入 BLOCKLIST_CATEGORIES。
    #
    #   (A) 已知危险（16 条，含 ``args:restricted``）：命令确实危险 / 参数越界收集
    #       系统信息 → category 在 BLOCKLIST_CATEGORIES 内，受
    #       ``enable_command_blocklist`` 开关管辖；
    #   (B) 无法判定（``dynamic`` / ``syntax`` / ``ast`` / ``invocation`` 四类）：
    #       执行内容静态不可知 / 语法结构被禁 / 参数含未建模执行结构 / 调用形态未被
    #       shell adapter 建模 → 同样硬拒，但理由不是「危险」，
    #       category 刻意不在 BLOCKLIST_CATEGORIES 内（不该被说成命中危险命令，
    #       也不该被业务开关关掉——那是结构防线）；
    #   (C) 分析失败（``ast:unknown_node``）：不是规则，由 AnalysisFailure 承载，
    #       根本不在 RULE_SPECS 内。
    #
    # 故断言分三层：
    #   6a. ``BLOCKLIST_CATEGORIES ⊆ block_categories``——(A) 必为 block，绝非 allow。
    #   6b. ``block_categories ⊆ BLOCKLIST_CATEGORIES ∪ _NON_HAZARD_BLOCK_CATEGORIES``
    #       ——凡 block 者必属 (A) 或 (B)，没有无序形态；两边的精确相等由下方断言保证。
    #   6c. **(A) 类 block 必由 ``command_blocklist`` 导出**——危险名录由该模块拥有，
    #       无一游离在黑名单机制之外。
    block_categories = frozenset(spec.category for spec in specs.values() if spec.verdict == "block")
    if block_categories < BLOCKLIST_CATEGORIES:
        raise AssertionError(
            f"BLOCKLIST_CATEGORIES 未完全落在 block 类规则的 category 集合内：{BLOCKLIST_CATEGORIES - block_categories}"
        )
    # 6b：「无法判定」类 block 的 category 允许清单（显式列举，新增须来此说明理由）。
    non_hazard = block_categories - BLOCKLIST_CATEGORIES
    if non_hazard != _NON_HAZARD_BLOCK_CATEGORIES:
        raise AssertionError(
            "block 类规则的 category 出现了既非「已知危险」也非已登记「无法判定」类的值："
            f"{non_hazard - _NON_HAZARD_BLOCK_CATEGORIES}（若为新增形态，须在本断言登记并说明语义）"
        )
    # 6c：「已知危险」类 block 规则必须由 ``command_blocklist`` 导出。
    #
    # 无例外：``args:restricted`` 是「已知危险」类 block 的一员，与其余危险规则同住
    # ``command_blocklist``。
    hazardous_blocks = frozenset(
        spec.rule_id for spec in specs.values() if spec.verdict == "block" and spec.category in BLOCKLIST_CATEGORIES
    )
    blocklist_ids = frozenset(spec.rule_id for spec in ALL_BLOCKLIST_RULES)
    if hazardous_blocks - blocklist_ids:
        raise AssertionError(
            f"存在「已知危险」类 block 规则未由 command_blocklist 导出（游离在黑名单机制外）："
            f"{hazardous_blocks - blocklist_ids}"
        )
