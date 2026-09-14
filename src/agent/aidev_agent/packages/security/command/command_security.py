# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_security

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

命令校验编排入口（AST-only 唯一 parse 所有者）。

职责：

- :func:`validate_command` 是**唯一**的 ``bashlex.parse`` 所有者：按 FIFO 来源队列逐个
  source 完整走「预算 → 空/NUL → parse → walk → 语法/危险/允许列表/参数规则 → 排队静态
  执行文本」；全队列共用同一异常分类边界与同一份请求预算；
- :func:`enforce_command_security` 只消费聚合后的 report：``allow`` 返回、``block`` 立即
  拒绝（不调用风险评估与审批）、``review`` 才进入预分流 / 处置档路径。

输出脱敏**不由本模块提供，也不在本模块触发**：唯一真源在 ``redaction.operations``。
本模块（命令编排）与脱敏彻底解耦。
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import os
import re
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any, Mapping

import bashlex
from bashlex.errors import ParsingError

from aidev_agent.pydantic_models import SecurityCommandSettings

from .command_allowlist import (
    ALLOWLIST_RULES,
)
from .command_approval import require_command_approval
from .command_blocklist import (
    BLOCKLIST_CATEGORIES,
    BLOCKLIST_RULES,
    DYNAMIC_BLOCKLIST_RULES,
    DYNAMIC_EXECUTION_CONTENT,
    INVOCATION_BLOCKLIST_RULES,
    INVOCATION_UNSUPPORTED,
    _rule_args_of,
    _rule_name_of,
)
from .command_definitions import (
    ANALYSIS_INCOMPLETE,
    ANALYSIS_INCOMPLETE_ID,
    BUDGET_RECURSION,
    BUDGET_RECURSION_ID,
    COMMAND_TOO_COMPLEX,
    EMPTY_NO_EXECUTABLE_COMMAND,
    EMPTY_NO_EXECUTABLE_COMMAND_ID,
    INPUT_NULL_BYTE,
    NULL_BYTE,
    PARSE_INTERNAL_ERROR,
    PARSE_INTERNAL_ERROR_ID,
    PARSE_SYNTAX_ERROR,
    PARSE_SYNTAX_ERROR_ID,
    PARSE_UNSUPPORTED_SYNTAX,
    PARSE_UNSUPPORTED_SYNTAX_ID,
    RULE_INTERNAL_ERROR,
    RULE_INTERNAL_ERROR_ID,
    AnalysisFailure,
    CommandFinding,
    CommandReport,
    CommandSource,
    CommandStructureFinding,
    CommandVerdict,
    Pattern,
    RuleConfigError,
    RuleContext,
    RuleHit,
    RulePredicate,
    RuleResult,
    RuleSet,
    RuleSpec,
    build_rule_set,
    data_predicate_for,
    review_unmatched,
    strictest,
    structure_finding,
)
from .command_parser import (
    CommandBudgetExceeded,
    UnsupportedAstError,
    WalkBudget,
    WalkResult,
    analyze_shell_invocation,
    budget_rule_ids,
    classify_word,
    walk_nodes,
)
from .command_rule_validation import assert_rule_invariants
from .command_syntax_rules import SYNTAX_RULE_IDS, SYNTAX_RULES

# ========== 本模块的 rule_id 常量与规则全集 ==========
#
#: ``ast:unknown_node`` 的**归因标识**（分析失败，不是规则）。
#:
#: 值取自 :class:`AnalysisFailure.AST_UNKNOWN_NODE`——id 的唯一真源是枚举；
#: 本常量只服务 ``UnsupportedAstError`` except 分支的调用点（该分支就地产出结构明细，
#: 不经规则求值）。
AST_UNKNOWN_NODE = AnalysisFailure.AST_UNKNOWN_NODE.value


# ========== 规则全集（编排层汇总）==========
#
# 命令规则的**全集**由各产出方模块导出，本模块（编排层）在此汇总。
# 这是「规则由谁拥有」与「谁需要看全量」的分离：拥有者在各自模块，汇总点在此——
# 本模块是**唯一**需要全量的地方（平台配置校验与生效规则表构造）。
#
# **本模块不拥有任何规则**：四条黑名单形态（``args:restricted`` /
# ``dynamic:execution_content`` / ``invocation:unsupported``）在 ``command_blocklist``；
# ``allowlist:allowed`` 在 ``command_allowlist``；``SYNTAX_RULES`` 在 ``command_syntax_rules``。
# 本模块作为聚合 / 编排层只**汇总**它们。
#
# **``review`` 为何不是规则**：它是「该 entry 未命中任何规则」的**处置结果**，
# 不是一条判定。规则描述「什么条件命中」，而 review 描述「什么都没命中」——
# 后者是控制流的 else 分支，不该占规则命名空间（否则需要不可配特例保护、
# 需要谓词反查允许列表才能弃权、且与空规则回落重复）。它的唯一产出点是
# :func:`_evaluate_rules` 的回落分支。
#
# **分析失败不在此**：13 条失败路径（parse/budget/input/empty/analysis/rule/ast）
# 不是规则，由 :class:`~...command_definitions.AnalysisFailure` 枚举承载归因，
# 由 ``_process_source`` 的控制流就地产出结构明细——故它们不进本全集。
#
# 「黑名单族」不变量（双向，见 ``command_rule_validation.assert_rule_invariants`` 第 6 条）：
# ``BLOCKLIST_CATEGORIES`` 与 block 类规则的 category 集合必须**互相包含**。
# 方向「block 类 ⊆ 黑名单族」是关键——它保证凡硬拒绝者都受 ``enable_command_blocklist``
# 开关管辖（``_evaluate_rules`` 按 category 判定）。缺了这一向，就会出现
# 「block 却不受黑名单开关约束」的语义错位。
RULE_SPECS: Mapping[str, RuleSpec] = MappingProxyType(
    {
        spec.rule_id: spec
        for spec in (
            *ALLOWLIST_RULES,  # 1
            *BLOCKLIST_RULES,  # 16（含 ``args:restricted``）
            *DYNAMIC_BLOCKLIST_RULES,  # 1
            *INVOCATION_BLOCKLIST_RULES,  # 1
            *SYNTAX_RULES,  # 10
        )
    }
)


#: :func:`data_predicate_for` 产出闭包的 ``__name__``（唯一实现，见 ``command_definitions``）。
#:
#: 用它判别「本谓词是数据规则的产物、可重建」——比按 rule_id 列名单稳（名单会漂移，
#: 且平台新增的数据规则会自动被判对）。``data_predicate_for`` 产出的并集谓词会把
#: ``__name__`` 改写为 ``_union_<label>``，故一并登记。
_DATA_PREDICATE_NAMES: frozenset[str] = frozenset({"_predicate", "_union_package_install"})


# 规则全集的六类导入期不变量（计数 / 谓词非空 / 双向样例 / 样例自洽 / 占位符一致性 /
# 黑名单形态完备性）已收拢到 ``command_rule_validation.assert_rule_invariants``——
# 它连同「无法判定」类 category 允许清单（``_NON_HAZARD_BLOCK_CATEGORIES``）同居一处。
# 本模块是**唯一**能看到规则全集的地方，故只在此处注入 ``RULE_SPECS`` 并调用。
assert_rule_invariants(RULE_SPECS, expected_count=29)

logger = logging.getLogger(__name__)

# ========== 队列与异常分类 ==========


class _Collector:
    """请求级收集器：来源表、命令明细、结构明细、来源队列与已知失败。"""

    def __init__(self, budget: WalkBudget) -> None:
        self.budget = budget
        self.sources: list[CommandSource] = []
        self.findings: list[CommandFinding] = []
        self.structure: list[CommandStructureFinding] = []
        self.queue: list[tuple[int, int]] = []  # (source_id, reparse_depth)
        self.incomplete = False

    def register_source(
        self, parent_id: int | None, origin_span: tuple[int, int] | None, text: str, depth: int
    ) -> CommandSource:
        source = CommandSource(source_id=len(self.sources), parent_id=parent_id, origin_span=origin_span, text=text)
        self.sources.append(source)
        self.queue.append((source.source_id, depth))
        return source

    def mark_incomplete(self, source_id: int, span: tuple[int, int], detail: str) -> None:
        """预算/递归耗尽：追加 ``analysis:incomplete`` block 并停止后续来源收集。

        不能把「未遍历完」表现成完整 allow，也不能让后续来源静默消失。
        """
        self.incomplete = True
        self.queue.clear()
        self.structure.append(
            structure_finding(
                source_id, span, ANALYSIS_INCOMPLETE_ID, f"{ANALYSIS_INCOMPLETE}（{detail}）", category="resource"
            )
        )


def _looks_like_pure_comment(text: str) -> bool:
    """逐行忽略空白后，每个非空行都以 ``#`` 开头（含空/纯空白输入）。"""
    lines = [line.strip() for line in text.splitlines()]
    meaningful = [line for line in lines if line]
    return all(line.startswith("#") for line in meaningful)


def _predicate_name_of(entry: Any, context: RuleContext) -> str | None:
    """数据规则的**名字口径**：归一化名（``/usr/bin/nc`` → ``nc``、``sudo nc`` 取内层）。

    真源在 :func:`command_blocklist._rule_name_of`（危险规则与本模块共用一份实现），
    本函数只是**转发**：保留它是因为 :func:`_spec_from_declaration` 在**构造 spec 的中途**
    就需要口径，此时还没有 spec 对象可供 :data:`RuleResolver` 使用。

    签名必须是 ``(entry, context)`` 的**二参**形态——这是
    :func:`data_predicate_for` 对 ``name_of`` / ``args_of`` 的契约（它按
    ``name_of(entry, context)`` 调用）。**不能**直接把
    :func:`effective_command_name`（签名 ``(entry, source_text)``）传进去：
    它的第二参是 source **文本**，而契约注入的是 :class:`RuleContext`，
    错配后会以 ``RuleContext`` 下标记号取 source，运行期抛
    ``'RuleContext' object is not subscriptable``。
    """
    return _rule_name_of(entry, context)


def _predicate_args_of(entry: Any, context: RuleContext) -> list[str]:
    """数据规则的参数口径——真源在 :func:`command_blocklist._rule_args_of`，本函数转发。

    与 :func:`_predicate_name_of` 成对、同由聚合点持有，理由同上：
    :func:`_spec_from_declaration` 在 spec 尚未成形时需要口径。
    二参签名的契约同 :func:`_predicate_name_of`。
    """
    return _rule_args_of(entry, context)


def _is_spec_pattern_attribute(node: ast.AST) -> bool:
    """``<...>.spec.pattern`` 属性链形态。"""
    if not (isinstance(node, ast.Attribute) and node.attr == "pattern"):
        return False
    inner = node.value
    return isinstance(inner, ast.Attribute) and inner.attr == "spec"


def _is_spec_pattern_getattr(node: ast.AST) -> bool:
    """``getattr(<...>.spec, "pattern", <默认>)`` 反射取值形态。"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Name) and func.id == "getattr"):
        return False
    if len(node.args) < 2:
        return False
    target, attr_name = node.args[0], node.args[1]
    if not (isinstance(target, ast.Attribute) and target.attr == "spec"):
        return False
    return isinstance(attr_name, ast.Constant) and attr_name.value == "pattern"


def _predicate_reads_spec_pattern(predicate: RulePredicate) -> bool:
    """谓词是否读 ``context.spec.pattern``（**AST 判据**，不是猜名字）。

    「读 ``context.spec.pattern`` 的谓词自动跟随新 pattern」是 ``allowlist:allowed``
    的 ``_allowed_hits`` 能免于重建的唯一理由，故该判断必须可证伪。取谓词源码 parse
    成 AST，找是否存在对 ``<...>.spec`` 的 ``pattern`` 取值。取不到 / 解析不了源码
    （C 扩展 / ``exec`` 产物 / 语法不兼容）时保守返回 ``False``——那会把该规则送进
    fail-closed 分支，而不是静默沿用旧谓词。

    **必须看 AST 而非对源码文本做子串 / 正则匹配**：文本匹配会把
    **docstring 与注释**里的 ``context.spec.pattern`` 也算作「读了 pattern」，于是
    「谓词其实不读 pattern、只在文档里提了一句」的规则会走进这一分支，被判定为
    「会自动跟随新 pattern」而**跳过重建**——正是本分支要消灭的静默沿用旧内容。
    这类误判只靠删注释就能触发，且不报错，属 fail-open。AST 判据只认真实的
    取值表达式，注释 / 字符串字面量天然不参与。

    两种**真实取值形态**都要认（漏认后者会把一条本可覆盖的规则误推入 fail-closed）：

    1. 属性链 ``<...>.spec.pattern``：``Attribute(attr="pattern")`` 且其 ``value`` 是
       ``Attribute(attr="spec")``；
    2. 反射取值 ``getattr(<...>.spec, "pattern", ...)``：``Call`` 的 ``func`` 是名为
       ``getattr`` 的 ``Name``、第一个实参是 ``Attribute(attr="spec")``、第二个实参是
       字符串常量 ``"pattern"``。

    不要求 ``spec`` 的持有者是字面 ``context``——谓词可先取别名；宽一点更保守
    （多判为「读 pattern」只会少重建自带代码谓词，不会静默沿用旧内容）。
    """
    try:
        source = textwrap.dedent(inspect.getsource(predicate))
        tree = ast.parse(source)
    except (OSError, TypeError, SyntaxError):  # pragma: no cover - 正常谓词都有源码
        return False
    return any(_is_spec_pattern_attribute(node) or _is_spec_pattern_getattr(node) for node in ast.walk(tree))


def _declaration_mapping(declaration: Any) -> dict[str, Any]:
    """把一条平台声明摊平成 :meth:`Pattern.from_mapping` 认得的映射（鸭子类型）。

    **不能**直接传 ``declaration`` 给 ``from_mapping``：那会让形状层需要知道
    ``RuleSpecConfig`` 的形状（它是 pydantic 模型，且形状层是依赖叶子，
    不得 import ``pydantic_models``）。此处显式列字段，使「声明里有哪些下发维度」
    在**一处**可见——准入判据与搬运能力由此看同一份字段清单。

    字段清单与本模块无关的第二份副本住在 ``command_definitions._declaration_is_literalizable``
    （准入判据）。**刻意不抽公共 helper**：那会让准入判据依赖调用方是否记得注入，
    反而新增一个静默失效面（详见该函数 docstring）。
    """
    return {
        "tokens": list(getattr(declaration, "tokens", None) or ()),
        "positional_index": getattr(declaration, "positional_index", None),
        "positional_equals": list(getattr(declaration, "positional_equals", None) or ()),
        "skip_flags": list(getattr(declaration, "skip_flags", None) or ()),
        "strip_colon": bool(getattr(declaration, "strip_colon", False)),
        "requires_any_flag": bool(getattr(declaration, "requires_any_flag", False)),
    }


def _predicate_for_content_override(base: RuleSpec, pattern: Pattern, tokens: Sequence[Any]) -> RulePredicate:
    """为**被内容覆盖**的内置规则重建谓词。

    只在「内置规则自带谓词、且该谓词**不读** ``context.spec.pattern``」时才是必需的：
    那种情况下换了 ``pattern`` 也走不到判定里（谓词一旦非 ``None`` 就径直使用它）。

    **走哪条重建路径由 ``base.predicate`` 的既有形状决定，逐条实测得出**（不靠猜）：

    - ``base.predicate is None``（纯数据规则）→ 就地按**新** ``pattern`` 派生，
      重跑 :func:`data_predicate_for`（``base`` 无原口径可依，故用缺省 name_of / args_of）。
      ``command_blocklist`` 一族虽经 :func:`data_predicate_for` 装配，但装配结果已烘进
      ``spec.predicate``，故此处命中下一条分支（重跑同一个生成器）而非本分支。
    - ``base.predicate`` 是 :func:`data_predicate_for` 的产物 → 重跑生成器，
      并沿用**该规则原有的** ``name_of`` / ``args_of`` 口径。
    - ``base.predicate`` 是自带代码谓词且**读** ``context.spec.pattern``
      （``allowlist:allowed`` 的 ``_allowed_hits``）→ **原样返回**。它自动跟随新
      pattern——这正是把判定收敛到 pattern 的关键收益，不得在此重复装配判据。
    - 其余（自带代码谓词且**不读** pattern，如 ``mkfs_format`` 的 ``_danger_mkfs``）→
      **fail-closed 报错**。这类规则的判定逻辑本就无法用 token 数据表达
      （它读的是「磁盘设备名」这类语义），静默沿用旧谓词 = 运营者以为换了内容而它没换。

    Args:
        base: 被覆盖的内置规则（含其原 ``predicate`` 与 —— 对数据规则而言 —— 原口径）。
        pattern: 由覆盖内容构造的 :class:`Pattern`（唯一真源 :meth:`Pattern.from_mapping`）。
        tokens: 原始覆盖内容（供论证 / 报错文案；重建本身只用 ``pattern``）。
    """
    predicate = base.predicate
    if predicate is None:
        # 纯数据规则：base 无原口径，按缺省口径就地派生（谓词必须在构造期定型，
        # 不留给派发期——见 ``command_definitions.build_rule_set``）。
        return data_predicate_for(
            pattern,
            rule_id=base.rule_id,
            reason=base.justification,
            verdict=base.verdict,
            category=base.category,
        )

    if getattr(predicate, "__name__", "") in _DATA_PREDICATE_NAMES:
        # 数据规则：重跑同一个生成器，使 pattern 与判定同步。
        #
        # 口径**必须**走 :func:`_predicate_name_of` / :func:`_predicate_args_of`
        # （二参 ``(entry, context)``）：直接把 ``effective_command_name`` 传进来是错的
        # ——它的第二参是 source 文本而非 :class:`RuleContext`，``data_predicate_for``
        # 会按 ``name_of(entry, context)`` 调用，于是 ``classify_word`` 对
        # ``RuleContext`` 下标取 source，抛 ``'RuleContext' object is not subscriptable``，
        # 被 ``validate_command`` 兜成 ``rule:internal_error``（block）——即
        # **任何**数据规则一旦被内容覆盖，全部命令都变 block。
        return data_predicate_for(
            pattern,
            rule_id=base.rule_id,
            reason=base.justification,
            verdict=base.verdict,
            category=base.category,
            name_of=_predicate_name_of,
            args_of=_predicate_args_of,
        )

    if _predicate_reads_spec_pattern(predicate):
        # 谓词读 ``context.spec.pattern`` → 自动跟随新 pattern。
        return predicate

    raise RuleConfigError(
        f"规则 {base.rule_id!r} 的谓词既不从 pattern 派生、也不读 ``context.spec.pattern``，"
        f"故下发内容覆盖无法生效（{getattr(predicate, '__name__', predicate)!r}）；"
        f"这类规则的判定是代码语义（非 token 数据），不支持内容覆盖——"
        f"若确需覆盖，应改为数据形态或新增一条规则"
    )


def _spec_from_declaration(declaration: Any) -> RuleSpec:
    """把一条平台下发的规则声明转成 :class:`RuleSpec`（**新增规则**的装配点）。

    「替换内置规则」走另一条路径（``build_rule_set`` 里对命中 ``all_specs`` 的
    声明做 ``replace(base, ...)`` + 注入的 ``predicate_for`` 重建谓词），因为替换要
    **继承**内置的身份（``match`` / ``not_match`` 自测样例等），而新增是从零构造一条。

    住在聚合点（本模块）而非基础定义模块：后者是依赖叶子，不得 import
    规则数据模块（``effective_command_name`` / ``effective_command_args`` 住在
    ``command_blocklist``）。边界由跨模块 AST 测试钉死，故装配责任归「谁聚合谁负责」。

    **形状搬运为纯调用**：``Pattern.from_mapping`` 是「声明 → 形状」的
    **唯一**实现（住在形状层），本函数只调用它，不做字段级的部分翻译。
    类型契约因此由一处保证，漂移在结构上不可能：``skip_flags`` 声明为
    ``frozenset[str]``，若在此直接构造 ``Pattern`` 并传入布尔值，仅在
    「该路径从不设 ``positional_index``、故 ``_match_pattern`` 从不消费
    ``skip_flags``」时才不会当场报错。

    ``verdict`` 取自 ``declaration.verdict``（**不**用 :meth:`RuleSpec.resolve_predicate`
    的硬编码 ``"block"``）：后者是给内置 block 规则用的，平台下发 allow/review 规则时
    用它会让规则判定被静默改写。

    ``predicate`` 依 ``pattern`` 就地派生（``data_predicate_for``）——
    这正是「加一条 spec 即生效」的机制，故此处不重复装配判定逻辑。
    名字口径按危险规则的既有做法取**归一化名**，使 ``sudo nc`` / ``/usr/bin/nc`` 都能命中。

    **不再有「空 pattern」早退分支**：``enabled=True`` 的声明必须可字面化
    （``build_rule_set`` 的闸门 4 已挡下空内容），走到这里必然有非空 pattern。
    早退分支若保留，会产出一条 ``pattern=None`` / ``predicate=None`` 的 spec——
    「进了生效表却永不求值」，正是要消除的失效面。
    """
    pattern = Pattern.from_mapping(_declaration_mapping(declaration))
    return RuleSpec(
        rule_id=declaration.rule_id,
        category=declaration.category,
        verdict=declaration.verdict,
        justification=declaration.justification,
        pattern=pattern,
        predicate=data_predicate_for(
            pattern,
            rule_id=declaration.rule_id,
            reason=declaration.justification,
            verdict=declaration.verdict,
            category=declaration.category,
            name_of=_predicate_name_of,
            args_of=_predicate_args_of,
        ),
    )


#: 逐条规则开关：``rule_id -> (settings) -> bool``，返回 False 表示该规则本轮不贡献。
#:
#: 只登记「category 不在 ``BLOCKLIST_CATEGORIES`` 内、因而不受 ``enable_command_blocklist``
#: 管辖」的规则 —— 今天恰有两条，各有独立开关（用户要求「各管一条」）。
#: 按 rule_id 显式列举而非按 category 派生：粒度是「一条规则一个开关」，
#: category 表达不出这个粒度（``dynamic`` / ``syntax`` 各自只对应一条）。
#: 消费点是 :func:`_active_specs`。
_PER_RULE_GATES: dict[str, Callable[[Any], bool]] = {
    DYNAMIC_EXECUTION_CONTENT: lambda s: s.enable_command_blocklist_dynamic_exec,
    INVOCATION_UNSUPPORTED: lambda s: s.enable_command_blocklist_unsupported,
}


def _active_specs(specs: Mapping[str, RuleSpec], settings: Any) -> dict[str, RuleSpec]:
    """按开关从规则集合里剔除**本轮不参与**的规则，产出可跑子集。

    从前这三条闸门住在 ``_evaluate_rules`` 的派发循环里（三个 ``continue``）。
    收拢到构造期后，``_evaluate_rules`` 只需遍历已经处理好的
    :attr:`RuleSet.active_specs`，对开关**零知识**。

    三条判据的**粒度刻意不同**（不是冗余，是真实语义差异，勿合并）：

    1. ``enable_command_blocklist`` 整族 —— 按 ``category in BLOCKLIST_CATEGORIES``
       判定，**不是** rule_id 名单。故运行期注入的新危险 spec 同样受开关约束。
    2. ``_PER_RULE_GATES`` 两条 —— 按 ``rule_id`` 显式映射。它们各自的 category
       （``dynamic`` / ``invocation``）不在 ``BLOCKLIST_CATEGORIES`` 内，
       故整族开关管不到它们；粒度是「一条规则一个开关」，category 表达不出。
    3. ``enable_command_syntax_rules`` 整族 —— 按 ``rule_id in SYNTAX_RULE_IDS`` 集合
       划定管辖面，与「哪个模块拥有这些规则」一致。**不用 category**：
       ``invocation:unsupported`` 的调用形态同属解析器能力边界，但由
       ``command_blocklist`` 拥有、有独立开关，按 category 会把它一并吞掉，
       使同一条规则受两个开关管辖。

    Args:
        specs: 规则全集（``RuleSet.specs``，含被覆盖内置规则的内容重建结果）。
        settings: 请求级配置（duck-typing，只读三个开关）。
    """
    blacklist_enabled = settings.enable_command_blocklist
    active: dict[str, RuleSpec] = {}
    for rule_id, spec in specs.items():
        if not blacklist_enabled and spec.category in BLOCKLIST_CATEGORIES:
            continue
        if rule_id in _PER_RULE_GATES and not _PER_RULE_GATES[rule_id](settings):
            continue
        if not settings.enable_command_syntax_rules and rule_id in SYNTAX_RULE_IDS:
            continue
        active[rule_id] = spec
    return active


def _collect_hit(
    hit: RuleHit,
    owned: dict[int, list[RuleResult]],
    collector: _Collector,
    source_id: int,
) -> None:
    """把一条 :class:`RuleHit` 按归属放进命令明细或结构明细（零翻译）。"""
    if hit.is_structure:
        collector.structure.append(
            CommandStructureFinding(
                source_id=source_id,
                span=hit.span,
                rule_id=hit.rule_id,
                verdict=hit.verdict,
                reason=hit.reason,
                category=hit.category,
            )
        )
        return
    owned.setdefault(hit.owner_entry_id, []).append(  # type: ignore[arg-type]
        RuleResult(
            rule_id=hit.rule_id,
            verdict=hit.verdict,
            reason=hit.reason,
            category=hit.category,
        )
    )


def _script_word_span(entry: Any, source: CommandSource) -> tuple[int, int]:
    """脚本文本 word 在父 source 中的半开 span（adapter 已保证其为静态单一 word）。"""
    invocation = analyze_shell_invocation(entry, source=source)
    for word in entry.argument_words:
        value = classify_word(word, source.text)
        if value.kind == "static" and value.text == invocation.text:
            return word.pos
    return entry.node.pos


def _queue_child_scripts(walked: WalkResult, source: CommandSource, reparse_depth: int, collector: _Collector) -> None:
    """把可静态解码的 shell 脚本文本作为新来源入 FIFO 队列（**唯一** 的再解析入口）。"""
    for entry in walked.entries:
        invocation = analyze_shell_invocation(entry, source=source)
        if invocation.kind != "script":
            continue
        span = _script_word_span(entry, source)
        collector.register_source(
            parent_id=source.source_id, origin_span=span, text=invocation.text, depth=reparse_depth + 1
        )


def _evaluate_rules(
    walked: WalkResult,
    collector: _Collector,
    *,
    rule_set: RuleSet,
    settings: SecurityCommandSettings,
) -> None:
    """**统一规则派发层**：遍历规则集合，逐条跑各自的谓词，合并成每 entry 唯一 finding。

    这里是「规则如何生效」的**唯一**入口。它不认识语法 / 危险 / 允许列表任何一族——
    只做三件事：

    1. 构造本 source 的 :class:`RuleContext`（配置与 inventory 的唯一载体）；
    2. 按 ``rule_set.active_specs`` 的顺序，**直接取**每条 spec 的 ``predicate`` 并调用
       ——**无特性分支、无派生**（谓词已在 :func:`build_rule_set` 构造期定型）；
    3. 按 ``RuleHit.owner_entry_id`` 判别归属：有归属并入该 entry 的 ``rules``，
       无归属落 ``structure_findings``。

    由此「加一条 spec 即生效」在**这一层**无需任何改动：新 spec 只要在构造期带上
    ``predicate`` 就自动被遍历到（无谓词的规则由构造期补齐 / fail-closed 拦下）。

    谓词仍**住在各自归属模块**，故本模块不 import 任何具体判定逻辑；
    ``command_blocklist`` / ``command_parser`` / ``command_allowlist`` 各自提供
    自己的谓词，依赖方向不变。

    **对开关零知识**：本函数遍历的是 ``rule_set.active_specs``——一个**已经按开关
    过滤好**的可跑子集（过滤在 ``validate_command`` 里由 :func:`_active_specs` 完成）。
    故此处**不得**出现 ``enable_command_blocklist`` / ``_PER_RULE_GATES`` /
    ``SYNTAX_RULE_IDS`` / ``BLOCKLIST_CATEGORIES`` 任何名字。
    ``settings`` 仍传入，但**只**用于构造 ``RuleContext`` 的两个运行时字段
    （``allowed_script_dirs`` / ``dynamic_execution_policy``）——它们是谓词的**输入**，
    不是「哪些规则生效」的判据。

    **规则集合来自显式入参**：遍历 ``rule_set.active_specs`` 而非模块级全局
    ``RULE_SPECS``。这使「注入一条新规则」只能经生产路径（显式参数）生效——
    monkeypatch 模块级全局对生产路径是 NO-OP 式的假绿。

    Args:
        walked: 该 source 的完整 inventory。
        collector: 请求级收集器（结构明细与命令明细的唯一出口）。
        rule_set: **本请求构造出的**规则视图（``specs`` + ``active_specs`` +
            生效覆盖 + 不可配集合）。只是 :func:`build_rule_set` 的**派生结果**
            ——请求级配置不在其中。
        settings: 本次请求的**原始配置**，此处仅取 ``allowed_script_dirs`` /
            ``dynamic_execution_policy`` 构造 :class:`RuleContext`。
            平台白名单命令**不在**请求级配置里——它经由 ``rule_set.active_specs`` 的
            allow 规则表达（``custom:`` 前缀）。
    """
    owned: dict[int, list[RuleResult]] = {}
    source_id = walked.source.source_id

    # ---- 结构类：按 source 跑一次（entry 为 None），产出无 entry 归属的结构明细。
    # 这些谓词自行遍历 inventory，故与 entry 遍历分开——同一条 spec 只跑一次，不重复。
    def _context(entry: Any | None, spec: RuleSpec) -> RuleContext:
        return RuleContext(
            walked=walked,
            entry=entry,
            allowed_script_dirs=tuple(settings.allowed_script_dirs),
            dynamic_execution_policy=settings.dynamic_execution_policy,
            spec=spec,
        )

    # 每条谓词在两种粒度上各跑一轮：source 级（``entry=None``）与每个 entry 级。
    # 谓词自行决定对哪种粒度产出命中——本层**不需要**维护「这条规则属于哪一族」的名单
    # （那种名单正是漂移来源：漏登记 = 规则静默失效，且必须随每条新规则手工更新）。
    #
    # 去重按 ``(rule_id, owner_entry_id, span)``：同一条规则对同一归属、同一位置只记
    # 一次，使「两种粒度都会产出」的谓词不会重复计数。
    #
    # ``context.spec`` 逐条传入：谓词读**自己的内容**（而非模块级常量快照）。
    # ⚠ **「读自己的 spec」本身不等于「平台能改内容」**：平台声明要生效，必须经
    # ``build_rule_set`` 在**构造期**把它落成 ``RuleSet.specs`` 里的 spec
    # （替换内置 → 重建 pattern + predicate）。只读 spec 而 spec 内容没人替换，
    # 等于读到的仍是内置值。未经该连线的规则：内容以内置为准，改声明不会改行为。
    #
    # 谓词在**构造期已定型**（``build_rule_set`` 统一补齐），故本层直接消费
    # ``spec.predicate``——这里**不再**派生、也**不再**有「无谓词则跳过」的分支
    # （跳过等于让一条规则静默失效；无谓词的 spec 根本进不来）。
    seen: set[tuple[str, int | None, tuple[int, int]]] = set()
    for entry in [None, *walked.entries]:
        for spec in rule_set.active_specs.values():
            predicate = spec.predicate
            assert predicate is not None, f"规则 {spec.rule_id!r} 无谓词（构造期应已补齐）"
            for hit in predicate(_context(entry, spec)):
                key = (hit.rule_id, hit.owner_entry_id, hit.span)
                if key in seen:
                    continue
                seen.add(key)
                _collect_hit(hit, owned, collector, source_id)

    for entry in walked.entries:
        rules = sorted(owned.get(entry.entry_id, ()), key=lambda rule: rule.rule_id)
        collector.findings.append(
            CommandFinding(
                source_id=source_id,
                entry_id=entry.entry_id,
                span=entry.node.pos,
                command_name=entry.name_word.word,
                # **``review`` 的唯一产出点**：本 entry 未命中任何规则
                # ——既不在允许列表（allow）、也不在任一黑名单（block）——故交给第三方
                # （smart 评估器或人工）判断。它不是规则：没有 rule_id、不进
                # ``RULE_SPECS``、不可配置，``rules`` 保持空元组（``rules == ()``
                # 本身就是「零规则命中」的充要信号）。
                #
                # 注意 ``strictest([])`` 按定义为 ``allow``——那是 fail-open。
                # 「一条规则都没命中」与「确认安全」是两回事，故空规则一律 review。
                #
                # 文案在此就地渲染（不经 ``JUSTIFICATION_TEMPLATES``：那是**规则**
                # 文案表，review 不是规则）。有规则命中的 entry 走上面的分派，不经此处。
                verdict=strictest([rule.verdict for rule in rules]) if rules else "review",
                rules=tuple(rules),
            )
        )


def _evaluate_partial(
    walked: WalkResult,
    collector: _Collector,
    *,
    rule_set: RuleSet,
    settings: SecurityCommandSettings,
) -> None:
    """预算/资源耗尽时，对「已经收集的 inventory」尽力产出**已归因**的规则结果。

    与 :func:`_evaluate_rules` 共用**同一套谓词**（本条只对其产出做筛除），因此不存在
    第二份判定逻辑；差异仅在产出筛选策略。

    **绝不产出 allow**：遍历未完成意味着「这条命令没被看全」，此时给 allow 就是
    fail-open（攻击面是「主动制造预算超限以换取放行」）。遍历失败本身已由调用方追加
    ``analysis:incomplete``（block）兜住整体 verdict，故这里的取舍是「可以少报成功，
    但绝不能多报成功」。

    ``rule_set`` 是**本请求构造出的**规则集合（由调用方传入），不读模块级全局
    ``RULE_SPECS``。
    """
    try:
        _evaluate_rules(walked, collector, rule_set=rule_set, settings=settings)
    except Exception:  # noqa: BLE001  (尽力而为；失败归因由 analysis:incomplete 承担)
        return
    kept: list[CommandFinding] = []
    for finding in collector.findings:
        rules = tuple(rule for rule in finding.rules if rule.verdict != "allow")
        if not rules:
            continue
        kept.append(replace(finding, rules=rules, verdict=strictest([rule.verdict for rule in rules])))
    collector.findings[:] = kept


# ========== 单 source 处理 ==========


def _process_source(
    source: CommandSource,
    reparse_depth: int,
    collector: _Collector,
    *,
    rule_set: RuleSet,
    settings: SecurityCommandSettings,
) -> None:
    """完整处理一个 source；任何阶段失败都转成可归因的结构明细，绝不抛到调用方。

    **入参是「派生产物 + 原始输入」两层**：

    - ``rule_set``：本请求的规则视图（``specs`` + 已过滤的 ``active_specs`` +
      生效覆盖），由 :func:`validate_command` 构造；
    - ``settings``：请求级**原始配置**（脚本目录 / 动态策略 / 预算上限）。
      与 :class:`RuleSet` 并列传入，不塞进同一对象——那是「派生产物 vs 原始输入」
      的分层，塞一起会名实不符。

    两者随请求重建，平台改配置立即生效。规则集合由 :func:`validate_command`
    **内部**构造（``build_rule_set`` + ``_active_specs``），本函数只转发。
    """
    text = source.text
    source_id = source.source_id
    full_span = (0, len(text))

    try:
        collector.budget.before_parse(text, reparse_depth)
    except CommandBudgetExceeded as exc:
        collector.structure.append(
            structure_finding(source_id, full_span, exc.rule_id, exc.detail, category="resource")
        )
        collector.mark_incomplete(source_id, full_span, exc.detail)
        return

    stripped = text.strip()
    if not stripped:
        collector.structure.append(
            structure_finding(
                source_id, full_span, EMPTY_NO_EXECUTABLE_COMMAND_ID, EMPTY_NO_EXECUTABLE_COMMAND, category="input"
            )
        )
        return
    if "\x00" in text:
        collector.structure.append(
            structure_finding(source_id, full_span, INPUT_NULL_BYTE, NULL_BYTE, category="input")
        )
        return

    try:
        nodes = bashlex.parse(text)
    except ParsingError as exc:
        collector.structure.append(
            structure_finding(
                source_id, full_span, PARSE_SYNTAX_ERROR_ID, f"{PARSE_SYNTAX_ERROR}: {exc}", category="parse"
            )
        )
        return
    except NotImplementedError as exc:
        collector.structure.append(
            structure_finding(
                source_id,
                full_span,
                PARSE_UNSUPPORTED_SYNTAX_ID,
                f"{PARSE_UNSUPPORTED_SYNTAX}: {exc}",
                category="parse",
            )
        )
        return
    except RecursionError:
        collector.structure.append(
            structure_finding(source_id, full_span, BUDGET_RECURSION_ID, BUDGET_RECURSION, category="resource")
        )
        collector.mark_incomplete(source_id, full_span, BUDGET_RECURSION)
        return
    except AttributeError as exc:
        if _looks_like_pure_comment(text):
            collector.structure.append(
                structure_finding(
                    source_id, full_span, EMPTY_NO_EXECUTABLE_COMMAND_ID, EMPTY_NO_EXECUTABLE_COMMAND, category="input"
                )
            )
        else:
            collector.structure.append(
                structure_finding(
                    source_id, full_span, PARSE_INTERNAL_ERROR_ID, f"{PARSE_INTERNAL_ERROR}: {exc}", category="parse"
                )
            )
        return

    walked = WalkResult(source=source)
    try:
        walk_nodes(nodes, source=source, budget=collector.budget, result=walked)
    except CommandBudgetExceeded as exc:
        collector.structure.append(
            structure_finding(source_id, full_span, exc.rule_id, exc.detail, category="resource")
        )
        _evaluate_partial(walked, collector, rule_set=rule_set, settings=settings)
        collector.mark_incomplete(source_id, full_span, exc.detail)
        return
    except UnsupportedAstError as exc:
        collector.structure.append(structure_finding(source_id, full_span, AST_UNKNOWN_NODE, str(exc), category="ast"))
        return
    except RecursionError:
        collector.structure.append(
            structure_finding(source_id, full_span, BUDGET_RECURSION_ID, BUDGET_RECURSION, category="resource")
        )
        collector.mark_incomplete(source_id, full_span, BUDGET_RECURSION)
        return

    try:
        _evaluate_rules(walked, collector, rule_set=rule_set, settings=settings)
    except RecursionError:
        collector.structure.append(
            structure_finding(source_id, full_span, BUDGET_RECURSION_ID, BUDGET_RECURSION, category="resource")
        )
        collector.mark_incomplete(source_id, full_span, BUDGET_RECURSION)
        return
    except Exception as exc:  # noqa: BLE001  (规则级意外失败必须可归因，不伪报为空成功)
        collector.structure.append(
            structure_finding(
                source_id, full_span, RULE_INTERNAL_ERROR_ID, f"{RULE_INTERNAL_ERROR}: {exc}", category="internal"
            )
        )
        return

    _queue_child_scripts(walked, source, reparse_depth, collector)


# ========== validate ==========


def validate_command(
    command: str,
    *,
    security_command_settings: SecurityCommandSettings,
) -> CommandReport:
    """校验命令并返回唯一聚合报告（**不发起审批、不挂起图执行**）。

    配置**只**来自单一 :class:`SecurityCommandSettings` 实例：没有逐字段 kwarg，
    也没有 ``None`` 表示「未覆盖」的分支。该参数**必填**——省略配置会让网关在
    未知配置下判定 ``allow``，属 fail-open，故不提供默认值。

    Args:
        command: 待校验的命令字符串（非 ``str`` 直接 ``TypeError``）。
        security_command_settings: 命令防护配置（允许列表目录 / 预算 / 动态策略 /
            黑名单开关）。必填，无默认值。

    Raises:
        TypeError: ``command`` 非 ``str``，或 ``security_command_settings`` 为 ``None``。
    """
    if not isinstance(command, str):
        raise TypeError(f"命令必须是字符串，收到 {type(command).__name__}")
    if security_command_settings is None:
        raise TypeError("security_command_settings 必填，不能为 None（缺失配置会导致 fail-open）")

    settings = security_command_settings
    # 规则视图的构建发生**在这里**（构造期）：平台声明被统一编译成 ``specs``（替换 / 新增）
    # 与 ``disabled``（按 id 关闭），``active_specs`` 初值为「全集去掉 disabled」。
    # ``to_spec`` / ``predicate_for`` 由本模块注入——本模块是聚合点，允许 import 规则数据
    # 模块；基础定义模块是依赖叶子，不得 import 它们（边界由测试钉死）。
    rule_set = build_rule_set(
        settings, RULE_SPECS, to_spec=_spec_from_declaration, predicate_for=_predicate_for_content_override
    )
    # 开关过滤发生**在这里**（构造期，非评估期）：把开关关掉的规则从可跑集合里剔除，
    # 使 ``_evaluate_rules`` 只遍历 ``active_specs``、对开关零知识。
    # 传入的 ``rule_set.active_specs`` 已不含被平台关闭的规则（build_rule_set 去 disabled）。
    # 过滤住在聚合点（本模块）——``_active_specs`` 需要 ``BLOCKLIST_CATEGORIES`` /
    # ``_PER_RULE_GATES`` / ``SYNTAX_RULE_IDS``，这些不能进依赖叶子。
    rule_set = replace(rule_set, active_specs=_active_specs(rule_set.active_specs, settings))
    budget = WalkBudget(
        max_command_length=settings.max_command_length,
        max_nodes=settings.max_nodes,
        max_depth=settings.max_depth,
        max_reparse_depth=settings.max_reparse_depth,
    )

    collector = _Collector(budget)
    collector.register_source(parent_id=None, origin_span=None, text=command, depth=0)

    while collector.queue:
        source_id, reparse_depth = collector.queue.pop(0)
        source = next(item for item in collector.sources if item.source_id == source_id)
        _process_source(source, reparse_depth, collector, rule_set=rule_set, settings=settings)

    # 收集结果：平台配置的生效**已在构造期完成**（``active_specs`` 已排除被关闭的规则、
    # 被替换规则的 spec 已带新内容与判定），故此处不再有「聚合后施加」这一步。
    findings = tuple(sorted(collector.findings, key=lambda item: (item.source_id, item.entry_id)))
    structure = tuple(sorted(collector.structure, key=lambda item: (item.source_id, item.span, item.rule_id)))

    verdicts: list[CommandVerdict] = [item.verdict for item in findings]
    verdicts.extend(item.verdict for item in structure)
    if not verdicts:
        structure = structure + (
            structure_finding(
                0, (0, len(command)), EMPTY_NO_EXECUTABLE_COMMAND_ID, EMPTY_NO_EXECUTABLE_COMMAND, category="input"
            ),
        )
        verdicts.append("block")
    overall = strictest(verdicts)

    return CommandReport(
        verdict=overall,
        sources=tuple(collector.sources),
        findings=findings,
        structure_findings=structure,
    )


# ========== 路径验证 ==========


def validate_path(path: str, *, allowed_prefixes: list[str] | None = None) -> str:
    r"""验证并规范化文件路径以确保安全。

    通过防止目录遍历攻击和强制一致格式来确保路径安全可用。
    所有路径都会被规范化为使用正斜杠并以前导斜杠开头。

    此函数设计用于虚拟文件系统路径，会拒绝 Windows 绝对路径
    （如 C:/...、F:/...）以保持一致性并防止路径格式歧义。

    Args:
        path: 要验证和规范化的路径
        allowed_prefixes: 可选的允许路径前缀列表。如果提供，
            规范化后的路径必须以其中一个前缀开头

    Returns:
        规范化的标准路径，避免 a/../../b 这种情况出现

    Raises:
        ValueError: 当路径包含遍历序列（`..`）、
            是 Windows 绝对路径（如 C:/...）、或不以允许的前缀开头时抛出
    """
    if re.match(r"^[a-zA-Z]:", path):
        msg = (
            f"Windows absolute paths are not supported: {path}. "
            "Please use virtual paths starting with / (e.g., /workspace/file.txt)"
        )
        raise ValueError(msg)

    normalized = os.path.normpath(path)
    normalized = normalized.replace("\\", "/")

    if ".." in normalized.split("/"):
        msg = f"Path traversal not allowed: {path}"
        raise ValueError(msg)

    if allowed_prefixes is not None and not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
        msg = f"Path must start with one of {allowed_prefixes}: {path}"
        raise ValueError(msg)

    return normalized


def _is_blocklist_category(category: str | None) -> bool:
    """该 category 是否属于黑名单族（用于黑名单拒绝文案）。

    黑名单族即 ``BLOCKLIST_CATEGORIES`` 定义的六类：数据破坏 / 外泄 / 提权 / 系统状态 /
    远程执行 / 软件包管理。其余（syntax / parse / budget / input / empty / analysis /
    rule / ast / invocation / allowlist / dynamic）都不是黑名单命中：
    它们要么是结构约束，要么是分析失败，要么是放行或兜底判定。

    注意：``arguments`` 不在列举内——参数限制规则 ``args:restricted`` 归
    ``system_state`` 类别，故此处没有该类别。
    """
    return category in BLOCKLIST_CATEGORIES


# ========== 命令安全编排 ==========


def _format_report_details(report: CommandReport) -> str:
    """把完整明细格式化成面向工具的拒绝文案（不丢 fatal、不丢任一来源失败）。

    **``rules`` 为空的 finding 补 ``review_unmatched`` 文案**：
    ``review`` 不是规则，``rules == ()`` 是其唯一信号——若原样拼接，
    拒绝文案会变成「命令执行被拒绝：」后面空无一物，模型无从得知为何被拒。
    故此处为该情形渲染固定文案（含命令名）。
    """
    details: list[str] = []
    for finding in report.findings:
        if finding.verdict == "allow":
            continue
        if finding.rules:
            details.extend(finding.reasons)
        else:
            # 零规则命中 → review。这是它唯一的信号，必须在此翻译成人可读的文案。
            details.append(review_unmatched(finding.command_name or "?"))
    details.extend(item.reason for item in report.structure_findings)
    return "; ".join(detail for detail in details if detail)


def _is_pure_budget_rejection(report: CommandReport) -> bool:
    """报告是否属于「**纯**资源超限」——只有预算/递归耗尽，没有任何危险或语法命中。

    这类拒绝的成因是「命令太复杂以至于分析跑不完」，而非命令本身有害。故应向模型
    给出单一、可操作的表述（``命令复杂度过高``），而不是把内部计费细节
    （「节点数 4 超过上限 3」「后续来源未继续遍历」）拼给模型看。

    「纯」是刻意的：若同时命中危险规则（如 ``rm -rf``）或语法限制（如后台 ``&``），
    那些命中信息量更大，应照常呈现，不被复杂度文案遮蔽。
    """
    budget_ids = budget_rule_ids() | {ANALYSIS_INCOMPLETE_ID}
    hit = {item.rule_id for item in report.structure_findings}
    if not (hit & budget_ids):
        return False
    # 有任何非预算类的问题（危险命中 / 语法 / 解析 / 参数…）就不算「纯」。
    other_structure = hit - budget_ids
    if other_structure:
        return False
    return not any(finding.rules for finding in report.findings)


def _blocklist_detail(report: CommandReport) -> str:
    """黑名单命中部分的文案（含 label/category）。

    判据**由类别（category）决定**：黑名单类 = 该规则的 category 属于
    :data:`BLOCKLIST_CATEGORIES`。这样新增黑名单标签时只要 category 正确就自动
    进入本文案，无需同步第二处清单——手工维护的 rule_id 跳过集与前缀元组是两份
    会漂移的清单，且二者口径本就不完全一致。``command_rule_validation.assert_rule_invariants``
    第 6 条的
    双向相等断言保证「block ⇒ 属黑名单族」，故本判据不会漏掉任何 block 命中。
    """
    parts: list[str] = []
    for finding in report.findings:
        for rule in finding.rules:
            if rule.verdict != "block":
                continue
            if _is_blocklist_category(rule.category):
                parts.append(f"{rule.rule_id}({rule.category})")
    for item in report.structure_findings:
        # 出结构明细的黑名单命中（管道远程执行）同样按类别判定。
        if _is_blocklist_category(item.category):
            parts.append(f"{item.rule_id}({item.category})")
    return "; ".join(dict.fromkeys(parts))


def _build_command_review(report: CommandReport) -> dict[str, Any]:
    """构造 ``args["command_review"]``：普通 JSON 对象（无 dataclass / AST / set）。

    只呈现「命中了什么规则、为何需要审批」（``findings`` 里每条 rule 的
    verdict / reason / category 与审计字段）。不附「本 agent 的规则配置摘要」——
    审批人关心的是判定依据，不是配置从哪来。
    """
    review_sources: list[dict[str, Any]] = []
    reviewed_ids = {finding.source_id for finding in report.findings if finding.verdict == "review"}
    included: set[int] = set()
    by_id = {source.source_id: source for source in report.sources}
    for source_id in sorted(reviewed_ids):
        chain: list[CommandSource] = []
        cursor: int | None = source_id
        while cursor is not None and cursor in by_id and cursor not in included:
            chain.append(by_id[cursor])
            included.add(cursor)
            cursor = by_id[cursor].parent_id
        for source in reversed(chain):
            review_sources.append(
                {
                    "source_id": source.source_id,
                    "parent_id": source.parent_id,
                    "origin_span": list(source.origin_span) if source.origin_span is not None else None,
                    "text": source.text,
                }
            )

    findings = [
        {
            "source_id": finding.source_id,
            "entry_id": finding.entry_id,
            "span": list(finding.span),
            "command_name": finding.command_name,
            "verdict": finding.verdict,
            "rule_ids": list(finding.rule_ids),
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "verdict": rule.verdict,
                    "reason": rule.reason,
                    "category": rule.category,
                }
                for rule in finding.rules
            ],
        }
        for finding in report.findings
        if finding.verdict == "review"
    ]

    payload: dict[str, Any] = {"sources": review_sources, "findings": findings}

    json.dumps(payload)  # 契约自检：必须是普通 JSON（无 default 兜底）
    return payload


def enforce_command_security(
    command: str,
    target_runtime: str,
    security_settings: SecurityCommandSettings,
    risk_assessor: Any | None = None,
) -> None:
    """执行命令前进行统一安全防护（AST 全量判定 → 风险/审批）。

    - `block`：立即 `ValueError`（fail-closed），绝不调用风险评估或审批；
    - `allow`：正常返回；
    - `review`：先按 ``command_review_disposition`` 归一化处置档（非法值 fail-closed 为
        ``block``）。**仅当处置档为 ``approval``** 且 ``enable_command_review_auto`` 开启
        且有评估器时，才用评估器预分流以减少人工审批量（allow 省掉审批 / block 拒绝 /
        approval 落回审批）。随后单次三档派发：``allow`` 放行 / ``approval`` 对整条原始命令
        发起一次审批并附 :func:`_build_command_review` 明细 / ``block`` 拒绝
        （拒绝文案复用 ``report`` 明细，理由不丢失）。

    `enforce` 把整个 `security_settings` 对象交给 :func:`validate_command`
    （单一配置真源，无逐字段投影）。

    拒绝文案不含脱敏处理：文案为静态措辞 + 命令/原因，不可能包含 backend
    注入的敏感值（那些值只随沙箱输出泄漏，脱敏在 core provider 侧完成）。

    Args:
        command: 模型生成的待执行 shell 命令。
        target_runtime: 目标运行时标识（写入审批单，便于审计）。
        security_settings: 命令防护配置（**必填**，无 None fallback）
        risk_assessor: 命令风险评估器（`enable_command_review_auto` 预分流用）。
            None 时跳过预分流，直接走处置档。

    Raises:
        AttributeError: ``security_settings`` 为 ``None``（必填契约，不做静默兜底）。
    """
    # 显式守卫「必填」契约：validate_command 允许缺省 settings（用模型默认），
    # 但 enforce 是生产入口，绝不允许 None 静默回落默认配置。
    if security_settings is None:
        raise AttributeError("enforce_command_security 需要显式的 SecurityCommandSettings（不允许 None）")

    report = validate_command(command, security_command_settings=security_settings)

    if report.verdict == "allow":
        return

    if report.verdict == "block":
        blocklist = _blocklist_detail(report)
        if blocklist:
            raise ValueError(f"命令执行被拒绝（命令黑名单）：{blocklist}")
        # 纯资源超限：给模型单一、可操作的表述，而不是内部计费明细。
        # 判据见 _is_pure_budget_rejection（要求无任何危险/语法命中）。
        if _is_pure_budget_rejection(report):
            raise ValueError(f"命令执行被拒绝：{COMMAND_TOO_COMPLEX}")
        raise ValueError(f"命令执行被拒绝：{_format_report_details(report)}")

    # review：可选智能预分流 → 三档处置（allow / approval / block）。
    # 处置档 fail-closed 归一化：未知取值一律回落 block（不因配置错误引入自动放行）。
    disposition = security_settings.command_review_disposition
    if disposition not in ("allow", "approval", "block"):
        disposition = "block"

    # 预分流（需求「review 是否在处理前由 smart 预处理」）：其目的是**减少人工审批量**，
    # 故仅在处置档为 approval 时才值得跑；allow / block 档已能自动决定，跑评估器是纯开销，
    # 且会覆盖部署的显式选择。仍需开关开启且注入了评估器。
    # 评估器返回与处置档同一套词汇，故结果直接作为处置：allow 放行（省掉审批）/ block 拒绝；
    # approval（含评估失败）表示「无法自动判定」，维持审批。
    if disposition == "approval" and security_settings.enable_command_review_auto and risk_assessor is not None:
        disposition = risk_assessor.assess(command)

    # 单次三档派发（预分流与配置档共用同一处置）。
    if disposition == "allow":
        return
    if disposition == "block":
        raise ValueError(f"命令执行被拒绝：{_format_report_details(report)}")

    # disposition == "approval"：整条命令一次审批（无审批人 / interrupt 异常由
    # require_command_approval 内部 fail-closed 返回 False）。
    if require_command_approval(
        command,
        target_runtime=target_runtime,
        security_settings=security_settings,
        command_review=_build_command_review(report),
    ):
        return
    raise ValueError("命令审批未通过，已取消执行。")
