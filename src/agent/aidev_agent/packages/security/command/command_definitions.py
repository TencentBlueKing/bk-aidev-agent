# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_definitions

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

命令域的全部**基础定义**：一次校验的结果契约（AST-only 唯一报告形状）、规则**内容**
的形状、规则**身份与生效机制**，以及规则拒绝**文案**的集中定义。

本模块是命令包的单向依赖叶子：**只使用标准库**，不 import bashlex、pydantic
或本包其他模块，供 ``command_parser`` / ``command_blocklist`` / ``command_security``
共同消费。数据模块只允许从这里取**词汇、类型与文案**，不得取机制——机制归编排层。

五类定义：

- **结果契约**——:class:`CommandReport` / :class:`CommandFinding` /
  :class:`CommandStructureFinding` / :class:`CommandSource` / :class:`RuleResult`
  与判定三级 :data:`CommandVerdict`；
- **归因标识**——:class:`AnalysisFailure`（「分析没做成」不是规则）；
- **内容形状**——:class:`Pattern`（「一条规则靠什么数据判定」：「有序 token 序列 +
  受控修饰符」），是规则内容的**唯一**形状；它描述**规则内容**而非规则身份，
  故所有数据模块的规则都由它表达，而它本身不依赖任何规则；
- **规则身份与生效机制**——:class:`RuleSpec` / :class:`RuleSet`、
  谓词词汇（:class:`RuleHit` / :class:`RuleContext` /
  :class:`RulePredicate` / :func:`data_predicate_for`) 与
  :func:`build_rule_set`；
- **拒绝文案**——:data:`FORBIDDEN_COMMANDS`、:data:`JUSTIFICATION_TEMPLATES` /
  :data:`JUSTIFICATION_PARAMS`、:func:`render_justification` 与
  :func:`ensure_template_params_filled`（运行时守卫），以及
  :func:`structure_finding` / :func:`review_unmatched` 与各类拒绝提示常量。

**导入期自检不在此**：样例自洽 / justification 占位符一致性的导入期闸门已收拢到
``command_rule_validation``（与规则全集不变量同居一处）；本模块只保留**运行时**
守卫 :func:`ensure_template_params_filled`（每次谓词填文案时调用）。

**关于「形状层是否该承载数据」**：文案（模板与登记表）确实是数据，与形状 / 机制同居
本模块是因为占位符集合要与规则的 ``justification`` 钉成等式，而 ``RuleSpec`` 与
``AnalysisFailure`` 也在本模块——分开会让「模板 ↔ 声明 ↔ 填充」三者的对照跨模块、
漂移难以察觉。规则**判定内容**（``*_RULES``）仍只在各产出方模块，该方向的不变量由
``TestRegistryCoversLiterals`` 与 ``TestDependencyBoundaryIsTwoWay`` 守着。

契约要点：

- 整体判定只有三级 ``allow`` / ``review`` / ``block``，聚合优先级 ``block > review > allow``；
- 每个**实际命令**（有第一个 word 的 ``CommandNode``）恰有一条 :class:`CommandFinding`，
  其中保留**全部**命中规则（``rules``），``rule_ids`` 是其去重派生视图；
- 无命令归属的失败（语法、结构、解析失败、预算超限等）一律单列为
  :class:`CommandStructureFinding`，不覆盖、不伪造 entry；
- 子脚本（``bash -c '...'`` 等）产生独立 :class:`CommandSource`，以半开 ``origin_span``
  指回父 source 中脚本文本 word 的位置，不做跨解码文本的绝对偏移换算。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence

from aidev_agent.pydantic_models import SecurityCommandSettings

# ========== 分析失败的归因标识 ==========


class AnalysisFailure(str, Enum):
    """「分析**没做成**」的归因标识——**不是规则**。

    语义是 fail-closed 兜底（超预算 / 解析失败 / 输入非法 / 空命令 / 遍历未完成 /
    内部错误 / 未知 AST 节点），与「命令危险」是两回事。故它们**不占规则模型**：
    不进 :data:`~...command_security.RULE_SPECS`、不参与规则求值 / 平台下发 / override，
    由 ``_process_source`` 的 ``except`` 分支与 ``_Collector.mark_incomplete``
    在控制流上就地产出 :class:`CommandStructureFinding`。

    **值即 ``CommandStructureFinding.rule_id`` 所用的字符串**，故 ``CommandStructureFinding``
    的字段形状、报告契约、``_is_pure_budget_rejection`` 的判据、行为指纹里的 ``struct``
    元组全部无需转换。``str`` 双继承使既有字符串比较点（如 ``item.rule_id in budget_ids``）
    **无需改写**。

    位置：住本模块（基础定义层）——放进承载机制的那一段会让
    ``command_blocklist`` / ``command_parser`` 需 import 注册表，越界。
    """

    PARSE_SYNTAX_ERROR = "parse:syntax_error"
    PARSE_UNSUPPORTED_SYNTAX = "parse:unsupported_syntax"
    PARSE_INTERNAL_ERROR = "parse:internal_error"
    INPUT_NULL_BYTE = "input:null_byte"
    EMPTY_NO_EXECUTABLE_COMMAND = "empty:no_executable_command"
    ANALYSIS_INCOMPLETE = "analysis:incomplete"
    RULE_INTERNAL_ERROR = "rule:internal_error"
    BUDGET_MAX_COMMAND_LENGTH = "budget:max_command_length"
    BUDGET_MAX_NODES = "budget:max_nodes"
    BUDGET_MAX_DEPTH = "budget:max_depth"
    BUDGET_MAX_REPARSE_DEPTH = "budget:max_reparse_depth"
    BUDGET_RECURSION = "budget:recursion"
    AST_UNKNOWN_NODE = "ast:unknown_node"


# ========== 判定与优先级 ==========

CommandVerdict = Literal["allow", "review", "block"]
"""命令判定三级：``allow`` < ``review`` < ``block``。"""

_VERDICT_PRIORITY: dict[str, int] = {"allow": 0, "review": 1, "block": 2}
"""聚合优先级：``block > review > allow``（全量收集后取最严）。"""


def strictest(verdicts: "list[CommandVerdict] | tuple[CommandVerdict, ...]") -> CommandVerdict:
    """返回给定判定中最严格的一方；空集合返回 ``allow``。

    调用方须自行保证空集合不会被直接当成「整体通过」（见 ``command_security``
    的 ``empty:no_executable_command`` 兜底）。
    """
    verdict: CommandVerdict = "allow"
    for item in verdicts:
        if _VERDICT_PRIORITY[item] > _VERDICT_PRIORITY[verdict]:
            verdict = item
    return verdict


@dataclass(frozen=True)
class Pattern:
    """一条规则的**可字面化内容**：有序 token 序列 + 受控修饰符。

    ``tokens`` 的元素为 ``str`` 或 ``tuple[str, ...]``——后者表 alternatives
    （Codex 原生语义，如 ``("rm", ("-rf", "-fr"))``）。

    修饰符全部是「token 序列」模型内的扩展，**不含**参数内子串正则
    （``dd_disk_write`` / ``exfil_curl_token`` 因此无法字面化，保留代码谓词）。

    **名字由调用方传入、谓词只做精确相等**（不做 basename / sudo 归一化）：
    本形状**不做** basename / sudo / 路径后缀投影。``sudo rm -rf`` 要命中必须由调用方先
    归一化出 ``rm``；形状层不做归一化，故 ``/usr/bin/nohup`` 这类带路径的命令名不命中
    ——归一化口径由调用方持有。

    修饰符字段说明：

    - ``tokens``：有序 token 前缀。首个 token 不匹配即判否。
    - ``positional_index``：取「跳过 ``-`` 开头 token 与 :attr:`skip_flags` 后的第 N 个
      非选项 token」，与该位置的值做**独立**比较（不要求 token 前缀命中）。``None``
      表示不启用位置匹配。
    - ``positional_equals``：位置 token 的允许取值集合（``strip_colon`` 为真时按第一个
      ``:`` 切分取前段）。
    - ``skip_flags``：位置定位时**额外**跳过的 token 集合（``apt`` 的 ``-y`` / ``--yes``
      等）。未列举的前缀 flag 不跳过——跳过集必须**精确**列举，否则
      ``apt -o X install vim`` 会因「任意 flag 都跳过」而误命中。
    - ``strip_colon``：位置 token 比较前剥掉 ``:group``（``chown root:grp`` -> ``root``）。
    - ``requires_any_flag``：要求参数中存在**任一** ``-`` 开头的 token（不指定具体 flag）。
      这是「命令 + flag」的**放宽变体**（``firewall_change``）。

    Raises:
        ValueError: 修饰符组合无意义（``positional_index is None`` 却有
            :attr:`positional_equals` / :attr:`strip_colon`）。

    注意：``Pattern()``（全空）**是合法的**——它表示「无内容」，:meth:`matches` 恒返回
    ``False``，:attr:`is_literalizable` 为假。它与「无意义的修饰符组合」是两回事，
    后者在构造期就 fail-loud。
    """

    tokens: tuple[str | tuple[str, ...], ...] = ()
    positional_index: int | None = None
    positional_equals: frozenset[str] = frozenset()
    skip_flags: frozenset[str] = frozenset()
    strip_colon: bool = False
    requires_any_flag: bool = False

    def __post_init__(self) -> None:
        """构造期 fail-loud：形状非法即拒（绝不静默忽略）。

        两类非法：

        1. **修饰符组合无意义**（``positional_index is None`` 却给位置相关字段）；
        2. **token 形状非法**——每个元素必须是 ``str``（字面 token）或非空 ``tuple[str, ...]``
           （alternatives）。构造期必须显式守住 token 形状，因为派生视图会按下标取
           ``tokens[0]`` 并假定它是 alternatives 元组——畸形形状会让它们**静默给出
           错误的命令名集合**，那比抛错危险得多。
        """
        for index, token in enumerate(self.tokens):
            if isinstance(token, str):
                continue
            if not isinstance(token, tuple) or not token:
                raise ValueError(  # noqa: TRY003
                    f"Pattern.tokens[{index}] 形状非法：{token!r}；"
                    f"每个元素须为 str 或非空 tuple[str, ...]（用 `names(...)` 构造 alternatives）"
                )
            if not all(isinstance(item, str) for item in token):
                raise ValueError(  # noqa: TRY003
                    f"Pattern.tokens[{index}] 的 alternatives 含非字符串项：{token!r}"
                )

        if self.positional_index is None and (self.positional_equals or self.strip_colon):
            raise ValueError(  # noqa: TRY003  (消息须带实际取值，供归因)
                f"Pattern 的修饰符组合无意义：positional_index=None 却给出 "
                f"positional_equals={sorted(self.positional_equals)!r} / strip_colon={self.strip_colon!r}；"
                f"位置比较需要 positional_index（禁止静默忽略一条未知形状的规则）"
            )

    @property
    def is_empty(self) -> bool:
        """是否没有任何可判定的内容（无 token 且未启用位置 / 存在性修饰符）。"""
        return not self.tokens and self.positional_index is None and not self.requires_any_flag

    @property
    def is_literalizable(self) -> bool:
        """本形状能否进入平台下发通道（能表达为声明式数据）。

        **与「内容是否为可字面化的数据」语义不同，刻意不复用同一个：**

        - ``condition_is_data`` 表达「能否**派生数据谓词**」——即代码能否不写分支地跑数据判定；
        - ``is_literalizable`` 表达「能否**下发**」——即这条规则能否被序列化成声明式数据
          交给平台（若引入平台可配置的管道关系扩展，可能出现「可下发」而仍需代码谓词）。

        二者语义不同，故不复用同一个属性。

        判据 = 「``tokens`` 非空且修饰符组合合法」。修饰符合法性由 :meth:`__post_init__`
        在**构造期**保证，故此处只需判 ``tokens`` 非空。
        """
        return bool(self.tokens)

    def matches(self, name: str, args: list[str]) -> bool:
        """本内容是否被「已解析的命令名 + 参数」命中（**唯一**匹配实现）。

        Args:
            name: 命令名（是否已归一化由调用方决定，本形状不做任何投影）。
            args: 该命令的静态字面参数（含 ``sudo`` 视图下的内层参数）。

        Returns:
            命中为 ``True``。

        Raises:
            ValueError: 修饰符组合在**运行时**未知 / 无意义。构造期已拦下非法组合，
                此处保留显式 raise 是为了让「平台注入的畸形形状」同样 fail-loud。
        """
        return _match_pattern(self, name, args)

    def to_mapping(self) -> dict[str, Any]:
        """把本形状序列化为**纯 JSON 可表达**的 dict（与 :meth:`from_mapping` 成对）。

        这是下发通道的序列化方向：``frozenset`` / ``tuple`` 一律转 ``list``，
        使产物可被 ``json.dumps`` 直接编码（平台契约是 JSON）。

        集合字段用 ``sorted()`` 而非 ``list()``：集合序不稳定，``json.dumps`` 的产物
        必须可复现（否则同一条规则的序列化结果每次不同，「下发内容被改过」这类审计
        判断失效）。``tokens`` 是**有序**的，**不得**排序。

        与 :meth:`from_mapping` 构成**一对**，二者必须同时演进：任何一侧新增字段
        而另一侧未跟上，round-trip 测试立即变红。
        """
        return {
            "tokens": [list(token) if isinstance(token, tuple) else token for token in self.tokens],
            "positional_index": self.positional_index,
            "positional_equals": sorted(self.positional_equals),
            "skip_flags": sorted(self.skip_flags),
            "strip_colon": self.strip_colon,
            "requires_any_flag": self.requires_any_flag,
        }

    @classmethod
    def from_mapping(cls, data: "Mapping[str, Any] | None") -> "Pattern":
        """从映射数据还原一条 :class:`Pattern`（与 :meth:`to_mapping` 成对）。

        **只做规范化，不做合法性判定**：``list`` → ``tuple`` / ``frozenset`` 的转换在此
        完成，而「形状是否合法」的拒收责任**全部**留给 :meth:`__post_init__`（唯一的
        fail-loud 点）。

        这不是风格取舍：若本方法自己再写一套形状判据，就会出现**两套判据**——
        而「第二套判据与真源漂移」会让准入判据与搬运能力不匹配，平台下发一条
        「看起来过了准入」但内容被静默截断的规则。

        ``tokens`` 的元素为 ``str`` 或 ``Sequence[str]``（后者表 alternatives）：
        ``list`` 被转成 ``tuple``，因为 :class:`Pattern` 要求不可变 alternatives。

        **接口落点是唯一真源**：本方法是 :class:`Pattern` 的 ``@classmethod``（不是模块级
        函数）——依赖边界要求 ``command_allowlist`` 等数据模块只能从本模块取类型，
        模块级函数会迫使它们扩 ``_DATA_MODULE_ALLOWED_FROM_BASE`` 白名单。

        Args:
            data: 映射数据（平台 JSON 的原生形状）；``None`` 等价于空映射。

        Returns:
            构造好的 :class:`Pattern`（全空映射 → 恒不命中的「无内容」形状）。

        Raises:
            ValueError: 形状非法 —— **由** :meth:`__post_init__` **抛出**，本方法不拦截。
            TypeError: ``tokens`` / ``positional_equals`` / ``skip_flags`` 的类型不对
                （如把 ``bool`` 传进集合字段）——同样由构造期的显式转换炸出，
                **不是**静默降级为空集。
        """
        source: Mapping[str, Any] = data or {}
        raw_tokens = source.get("tokens") or ()
        tokens: tuple[str | tuple[str, ...], ...] = tuple(
            tuple(item) if isinstance(item, Sequence) and not isinstance(item, str) else item for item in raw_tokens
        )
        return cls(
            tokens=tokens,
            positional_index=source.get("positional_index"),
            positional_equals=frozenset(source.get("positional_equals") or ()),
            skip_flags=frozenset(source.get("skip_flags") or ()),
            strip_colon=bool(source.get("strip_colon", False)),
            requires_any_flag=bool(source.get("requires_any_flag", False)),
        )


def names(*items: str) -> tuple[str, ...]:
    """一个 **alternatives** token：位置上命中其中任意一个即可（Codex 原生语义）。

    它存在的唯一理由是**让「名字集合」这个常用形态可读**。``Pattern.tokens`` 的元素
    是 ``str | tuple[str, ...]``——裸写 ``Pattern(tokens=(("apt", "apt-get"),))`` 的
    双层括号既难读也易错（把 ``("a","b")`` 误写成 ``"a"`` 或 ``[["a","b"]]``）。

    用法（与 Codex 的 ``pattern = ["view", ["list", "show"]]`` 同形）::

        Pattern(tokens=(names("halt", "poweroff", "reboot"),))     # 命令名集合
        Pattern(tokens=("rm", names("-rf", "-fr")))                # 命令 + flag alternatives
        Pattern(tokens=(names("apt", "apt-get"),), positional_equals=frozenset({"install"}))

    这是**一个**通用构造助手，不是五个按用途切分的工厂：``Pattern`` 的其余修饰符
    （``positional_index`` / ``skip_flags`` / ``strip_colon`` / ``requires_any_flag``）
    本就是 dataclass 字段，直接写就好——为每种组合再包一层工厂只会让「Pattern 长什么样」
    被工厂签名掩盖。
    """
    return tuple(items)


# ========== 加载期自测 ==========
#
# 加载期自检（样例自洽 / justification 占位符一致性）已收拢到
# ``command_rule_validation``——那三者（``load_time_self_test`` /
# ``assert_justification_templates_are_consistent`` / ``justification_params``）
# 与规则全集的六类不变量同属「导入期跑一次」的 fail-loud 防线，集中一处便于对照。
# 运行时守卫（:func:`ensure_template_params_filled`）仍留在本模块，与
# :data:`JUSTIFICATION_PARAMS` / :func:`render_justification` 同居。


# ========== Pattern 匹配的辅助 ==========


def _positional_operand(
    args: list[str],
    *,
    flags: frozenset[str],
    strip_colon: bool,
    index: int = 0,
) -> str | None:
    """取「跳过选项后的第 ``index`` 个非选项 word」（即操作数）；不存在返回 ``None``。

    语义是 ``chmod`` / ``chown`` 的操作数定位（两者只差 ``flags`` 集合与是否剥离
    ``:group``）：

    - ``--`` 终止符只被跳过一格，其后 token **仍**按操作数取用；
    - ``--reference``（无 ``=``）吞掉自身与下一个 token（多跳一格）；
      ``--reference=<v>`` 只吞自身。这一不对称是操作数定位的既有口径，已由测试钉住；
    - 命中 ``flags``（或任何 ``-`` 开头的 token）一律跳过；
    - ``strip_colon`` 为真时按第一个 ``:`` 切分，取 owner 部分（``:grp`` -> ``""``）。

    ``index`` 缺省为 0（「第一个非选项 token」）。:class:`Pattern` 的
    ``positional_index`` 经它表达「取第 N 个」——**同一份跳格逻辑**，不建第二套。
    """
    seen = 0
    while index >= 0 and seen < len(args):
        token = args[seen]
        if token == "--":
            seen += 1
            break
        if token == "--reference" or token.startswith("--reference="):
            seen += 1 if token == "--reference" else 0
            seen += 1
            continue
        if token in flags or token.startswith("-"):
            seen += 1
            continue
        if index == 0:
            break
        index -= 1
        seen += 1
    if seen >= len(args) or index != 0:
        return None
    operand = args[seen]
    return operand.split(":", 1)[0] if strip_colon else operand


def _match_pattern(pattern: Pattern, name: str, args: list[str]) -> bool:
    """``Pattern`` 的**唯一**匹配实现（token 级比较，**无正则**，O(len(args)) 线性）。

    算法（按序）：

    1. 空 ``tokens`` 且无位置 / 存在性修饰符 → ``False``（「无内容」不构成命中）；
    2. 逐 token 与「``name`` + ``args``」拼接后的切口比对：``tokens[0]`` 对 ``name``，
       ``tokens[i>0]`` 对 ``args[i-1]``。``str`` 精确相等；``tuple`` 表 alternatives。
       首个不匹配即 ``False``（长度不足亦为不匹配）；
    3. ``requires_any_flag`` 为真时，要求 ``args`` 中存在任一 ``-`` 开头的 token
       （**不指定具体 flag**）——「命令 + flag」的放宽变体；
    4. ``positional_index`` 非 ``None`` 时，取「跳过 ``-`` 开头 token 与
       ``skip_flags`` 后的第 N 个非选项 token」，**独立于 token 前缀**地与该值比较；
       ``strip_colon`` 为真时按第一个 ``:` 切分取前段；
    5. 无 ``tokens`` 也无 ``positional_index`` 也无 ``requires_any_flag`` → ``False``；
    6. 其余未知情形 → ``ValueError``（fail-loud，绝不静默放行）。

    Raises:
        ValueError: 出现无法解释的修饰符组合（消息带实际取值，供归因）。
    """
    # --- 1. 空内容 ---
    if not pattern.tokens and pattern.positional_index is None and not pattern.requires_any_flag:
        return False

    # --- 2. token 前缀：``tokens[0]`` 对 name，其后对 args（首个不匹配即否） ---
    for index, token in enumerate(pattern.tokens):
        if index == 0:
            actual = name
        elif index <= len(args):
            actual = args[index - 1]
        else:
            return False
        if isinstance(token, str):
            if actual != token:
                return False
        elif actual not in token:
            return False

    # --- 3. 「存在任意 flag」修饰符 ---
    if pattern.requires_any_flag and not any(arg.startswith("-") for arg in args):
        return False

    # --- 4. 位置 token（在 **剔除命令名后的参数** 上定位，与既有 ``_positional_operand`` 同轴） ---
    if pattern.positional_index is not None:
        operand = _positional_operand(
            args,
            index=pattern.positional_index,
            flags=pattern.skip_flags,
            strip_colon=pattern.strip_colon,
        )
        return operand is not None and operand in pattern.positional_equals

    # --- 5 / 6. 走进这里说明有 tokens 或 requires_any_flag 已全部通过 ---
    if pattern.tokens or pattern.requires_any_flag:
        return True
    raise ValueError(  # noqa: TRY003  (消息须带实际取值，供归因)
        f"未知的 Pattern 修饰符组合：{pattern!r}（无法判定，禁止静默放行）"
    )


# ========== 规则谓词的统一词汇 ==========
#
# 本节的三个类型是「规则**如何被判定**」的统一词汇：一条 :class:`RuleSpec` 携带一个
# :class:`RulePredicate`，谓词消费一个 :class:`RuleContext`，产出若干 :class:`RuleHit`。
# 它们住的理由与 :class:`Pattern` 相同——是**形状**而非数据/机制，且必须被
# 所有规则产出方共享。若把它们与机制混在一段，则数据模块（``command_blocklist``
# 等）为了实现自己的谓词必须 import 注册表，方向 2 会立刻越界（见
# ``test_command_rules_registry.TestDependencyBoundaryIsTwoWay``）；放进叶子则所有
# 方向都合法。谓词的**实现**仍留在各自归属模块，本模块只提供形状。


@dataclass(frozen=True)
class RuleHit:
    """一个谓词对**一个判定目标**给出的结论（谓词的返回值元素）。

    存在的意义：谓词一次可能产出多条结论（如一条规则同时给出「命中」与「结构层证据」），
    故返回值是 ``Sequence[RuleHit]``，而不是单个 ``RuleResult``。此外**结构明细本就
    不归属于任何 entry**，用 ``RuleResult`` 硬塞需要伪造一个 entry_id——这正是本形状
    要消除的伪造。

    归属由 ``owner_entry_id`` **判别**，而非由类型判别：

    - ``owner_entry_id is not None``：命令归属命中，聚合时补 ``source_id`` 后落成
      :class:`RuleResult`（供 :class:`CommandFinding.rules`）；
    - ``owner_entry_id is None``：结构命中，落成 :class:`CommandStructureFinding`
      （无 entry 归属，不属于任何一条命令）。

    字段理由：

    - ``rule_id`` / ``verdict`` / ``reason`` / ``category``：与 :class:`RuleResult`
      及 :class:`CommandStructureFinding` 的同名字段一一对应，聚合时**零翻译**——否则
      这里每多一层形状转换，就多一处可能漂移。
    - ``owner_entry_id``：判别字段。``int | None`` 而非额外布尔量，因为聚合方本就需要
      entry_id 才能把命中放进正确的 finding；用真值判别可同时表达「归谁」与「是否归属」。
    - 不加 ``source_id``：本词汇用于**单 source** 的判定单元（见 :class:`RuleContext`），
      source_id 由聚合方从 ``context.walked.source`` 补齐，避免每个谓词都重复携带同一常量。
    - ``span``：结构命中必需（:class:`CommandStructureFinding` 有位置字段）。entry 归属
      的命中也带上位置（通常是该 entry 的 ``node.pos``），使谓词产出**自描述**——
      聚合方无需回头向 walked 反查「这条命中在哪儿」。默认 ``(0, 0)`` 只服务于不含
      位置的构造场景，正常谓词都应显式给出位置。
    - 不加审计字段：平台配置的生效**在构造期**完成（完整声明直接决定 ``RuleSet.specs``
      里的 spec），命中阶段只反映已生效的判定，没有「聚合后改写」这一步。
    """

    rule_id: str
    verdict: CommandVerdict
    reason: str
    category: str | None = None
    owner_entry_id: int | None = None
    span: tuple[int, int] = (0, 0)

    @property
    def is_structure(self) -> bool:
        """是否为无 entry 归属的结构命中（``owner_entry_id is None``）。"""
        return self.owner_entry_id is None


@dataclass(frozen=True)
class RuleContext:
    """一个谓词评估**一个判定单元**时可用的一切。

    内容不是猜的，而是三族现有产出方**实测消费**的并集：

    - ``walked``：单 source 的完整 inventory；三族都在用（语法用 ``syntax_nodes`` /
      ``entries``，危险用 ``entries`` + ``source.text``，结构用 ``entries``）。
    - ``entry``：本次判定的具体命令；``None`` 表示该谓词只产出结构命中
      （如语法 / 调用形态类规则），无需 entry 上下文。
    - ``allowed_script_dirs``：脚本路径允许列表（``syntax:script_path`` 谓词消费）。
    - ``dynamic_execution_policy``：动态执行内容的生效判定（``dynamic:*`` 谓词消费）。
    - ``spec``：本轮求值的**规则本体**（``RuleSpec``）。谓词借此读取**自己的内容**，
      而不去读模块级常量——后者是**导入期快照**，会让「改 spec 内容」不生效。
      类型用 ``Any``：``RuleSpec`` 住在基础定义层（本模块），而后者
      依赖本模块，标注它会成环。

    三处「黑名单开关」**刻意不在此**：``enable_command_blocklist`` 与两条逐规则开关
    决定的是「这条规则本轮要不要跑」，那是**控制流**，已在
    ``command_security._evaluate_rules`` 的派发层解决；谓词只负责「跑起来之后判定什么」。
    把开关下传会让「开关」两处生效（派发层 + 谓词），并绕过 ``_PER_RULE_GATES``
    的集中登记——新增同类规则时不再有单一登记点。
    **类型刻意用 ``Any`` / ``TYPE_CHECKING`` 之外的最弱约束**：``WalkResult`` 与
    ``CommandEntry`` 住在 ``command_parser``，而后者 import 本模块——在此处标注它们的
    类型需要 import ``command_parser``，**立刻成环**。本模块是纯叶子，故以鸭子类型
    （``Any``）表达：谓词本来就只按协议使用 ``walked.entries`` / ``entry.entry_id`` 等
    属性，不依赖具体类。
    """

    walked: Any
    """单 source 的 ``WalkResult``（鸭子类型，刻意不 import ``command_parser``）。"""

    entry: Any | None = None
    """本次判定的 ``CommandEntry``；结构类谓词为 ``None``。"""

    allowed_script_dirs: tuple[str, ...] = ()
    """脚本路径允许列表（``syntax:script_path`` 谓词消费）。"""

    dynamic_execution_policy: str = "block"
    """动态执行内容策略（``dynamic:execution_content`` 的 verdict 来源）。"""

    spec: Any | None = None
    """本轮求值的规则本体（``RuleSpec``，鸭子类型）。

    谓词读**自己的** ``pattern`` / ``justification`` 时用它，而非模块级常量快照——
    后者是导入期快照，会让「改 spec 内容」不生效。平台声明的内容要生效，必须由
    :func:`build_rule_set` 在**构造期**把它落成 ``RuleSet.specs`` 里的 spec
    （完整声明经 ``to_spec`` / ``predicate_for`` 装配出携带新 ``pattern`` 与 ``predicate``
    的 spec）；否则此处读到的仍是内置值。
    """


class RulePredicate(Protocol):
    """规则谓词协议：消费 :class:`RuleContext`，返回若干 :class:`RuleHit`。

    ``Protocol`` 而非抽象基类：谓词既可以是函数（``data_predicate_for`` 产出的闭包），
    也可以是实现该签名的可调用对象；结构化子类型使二者都合法，无需继承。
    """

    def __call__(self, context: RuleContext) -> Sequence[RuleHit]:  # pragma: no cover - 协议
        ...


def data_predicate_for(
    pattern: "Pattern | None",
    *,
    rule_id: str,
    reason: str,
    verdict: CommandVerdict,
    category: str | None = None,
    name_of: Callable[[Any, RuleContext], str | None] | None = None,
    args_of: Callable[[Any, RuleContext], list[str]] | None = None,
) -> RulePredicate:
    """把**可字面化**的内容（:class:`Pattern`）转成一个 :class:`RulePredicate`。

    这是「可字面化规则无需手写函数」的机制：谓词体只是对 :meth:`Pattern.matches`
    的一次调用，唯一真源仍是那个匹配实现，本函数不复制任何判定逻辑。

    签名细节（**已按现有实现核对**）：

    - :meth:`Pattern.matches` 要的是「已解析的命令名 + 参数」两段数据，而非
      ``entry`` 本身——名字是否归一化由调用方决定（见该函数文档）。故本生成器**默认**
      从 ``context.entry`` 取 ``name_word.word``（**原始 word**，与 ``command_parser``
      侧的 forbidden-command 判定同口径）、从 ``entry.argument_words`` 取字面参数；
      调用方可用 ``name_of`` / ``args_of`` 覆盖（危险规则必须覆盖为**已归一化名 +
      已剔动态的字面参数**，否则 ``sudo rm -rf`` 会因 name="sudo" 漏判）；
      无法取得名字时返回空（未命中），不抛异常——谓词只描述命中，失败路径另属分析失败。
    - ``rule_id`` / ``reason`` / ``verdict`` / ``category`` **全部由调用方从
      :class:`RuleSpec` 传入**，使产出的 :class:`RuleHit` **自描述**。刻意不默认空串：
      空 ``rule_id`` 会在聚合时并入错误的分组且无从察觉，把「忘了填身份」变成一次
      **静默的错误结论**，与 fail-loud 的项目取向相反。此处的取舍是「生成器只负责
      **判定**、身份由 spec 提供」，而非让生成器自行编造身份。

    ``pattern`` 为 ``None`` 或空（:attr:`Pattern.is_empty`）的内容 **恒不产出命中**：
    不可字面化的规则必须自带代码谓词（这正是「代码规则必须自带谓词」的判据来源）。

    Args:
        pattern: 规则的可字面化内容；``None`` / 空 pattern 产出常量空谓词。
        rule_id: 命中时写入 hit 的规则标识（来自 :class:`RuleSpec.rule_id`）。
        reason: 命中时写入 hit 的原因文案（来自 spec 的归属模块）。
        verdict: 命中时贡献的判定（:attr:`RuleSpec.verdict`）。
        category: 命中时的分类；``None`` 表示未分类。
        name_of: **可选**命令名解析器 ``(entry, context) -> str | None``；缺省取原始 word。
            危险规则须传 ``effective_command_name``（**已归一化**）。
        args_of: **可选**参数解析器 ``(entry, context) -> list[str]``；缺省取
            ``argument_words`` 原文。危险规则须传 ``_literal_args``（**已剔动态参数**）。

    Returns:
        一个 :class:`RulePredicate`：entry 命中 ``pattern`` 时返回一条 ``RuleHit``，
        否则返回空序列。``context.entry`` 为 ``None`` 时同样返回空（数据谓词不产结构命中）。
    """

    def _predicate(context: RuleContext) -> Sequence[RuleHit]:
        entry = context.entry
        if entry is None:
            return ()
        if pattern is None or pattern.is_empty:
            return ()
        name = name_of(entry, context) if name_of is not None else entry.name_word.word
        if name is None:
            return ()
        args = args_of(entry, context) if args_of is not None else _static_args(entry)
        if not pattern.matches(name, args):
            return ()
        return (
            RuleHit(
                rule_id=rule_id,
                verdict=verdict,
                reason=reason,
                category=category,
                owner_entry_id=entry.entry_id,
                span=getattr(entry.node, "pos", (0, 0)),
            ),
        )

    return _predicate


def _union_predicates(label: str, *predicates: RulePredicate) -> RulePredicate:
    """把若干谓词合成「命中取并集」的一个谓词（同一 ``RuleHit`` 形状，去重保序）。

    去重键取 ``(rule_id, owner_entry_id, span)``——与 ``_evaluate_rules`` 的既有去重键
    **同一口径**，使并入补充面不会让同一条命中被计数两次。

    供 :meth:`RuleSpec.resolve_predicate` 在「pattern 派生 + 自带谓词 + 代码补充面」
    并存时合并。无 ``label`` 之外的副作用。
    """

    def _union(context: RuleContext) -> Sequence[RuleHit]:
        hits: list[RuleHit] = []
        seen: set[tuple[str, int | None, tuple[int, int]]] = set()
        for predicate in predicates:
            for hit in predicate(context):
                key = (hit.rule_id, hit.owner_entry_id, hit.span)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(hit)
        return tuple(hits)

    _union.__name__ = f"_union_{label}"
    return _union


def _static_args(entry: Any) -> list[str]:
    """从 entry 取**静态字面**参数（鸭子类型）。

    ``classify_word`` 住在 ``command_parser``（上游），本叶子不可 import；但
    ``argument_words`` 的元素本就是 word 节点，静态字面参数即其 ``.word`` 文本。
    精确的「静态 / 动态」筛分仍归 ``command_blocklist._literal_args``；数据规则的
    flag / positional 判定只依赖字面 token 的存在性，故此处取原文即等价。
    """
    return [word.word for word in getattr(entry, "argument_words", ()) if getattr(word, "word", None) is not None]


# ========== 来源 ==========


@dataclass(frozen=True)
class CommandSource:
    """一段 shell 文本来源。

    ``source_id`` 按请求内 FIFO 来源发现顺序从 0 发号：root 恒为 0，其后每个可静态
    解码的 shell 脚本文本各占一个 id。

    - ``parent_id`` / ``origin_span``：root 为 ``None`` / ``None``；子来源的
      ``origin_span`` 指向**父 source 文本**中脚本文本 word 的半开 span。
    - ``text``：root 为未经 ``strip`` 的原始命令；子来源为脚本文本原文。
    """

    source_id: int
    parent_id: int | None
    origin_span: tuple[int, int] | None
    text: str


# ========== 规则与明细 ==========


@dataclass(frozen=True)
class RuleResult:
    """单条规则命中或成功记录（规则归属数据的唯一形状）。"""

    rule_id: str
    """稳定规则标识（如 ``rm_recursive_force`` / ``syntax:redirect`` / ``allowlist:allowed``）。"""

    verdict: CommandVerdict
    """本规则贡献的判定（**平台声明的生效值**：规则内容由 ``RuleSet.specs`` 决定）。"""

    reason: str
    """人类可读原因（同一规则多处证据合并后的完整说明）。"""

    category: str | None = None
    """分类（如 ``data_destruction`` / ``allowlist`` / ``syntax``）；未分类为 ``None``。"""


@dataclass(frozen=True)
class CommandFinding:
    """一个实际命令的最终判定与全部规则明细。"""

    source_id: int
    entry_id: int
    span: tuple[int, int]
    command_name: str | None
    verdict: CommandVerdict
    rules: tuple[RuleResult, ...]

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """``rules`` 的去重、字典序派生视图（不维护第二份可写规则数据）。"""
        return tuple(sorted({rule.rule_id for rule in self.rules}))

    @property
    def reasons(self) -> tuple[str, ...]:
        """全部规则原因（``block`` 优先，其次 ``review``，同档保持原顺序）。"""
        ordered = sorted(self.rules, key=lambda rule: -_VERDICT_PRIORITY[rule.verdict])
        return tuple(rule.reason for rule in ordered)


@dataclass(frozen=True)
class CommandStructureFinding:
    """无单一命令归属的结构 / 致命失败明细。

    语法限制、``parameter`` 中未建模的执行结构、解析失败、预算超限等等均以此形状
    单列，保留来源与位置；多个 fatal 并存时逐个保留，不用单槽覆盖。
    """

    source_id: int
    span: tuple[int, int]
    rule_id: str
    verdict: CommandVerdict
    """本规则贡献的判定（**平台声明的生效值**：规则内容由 ``RuleSet.specs`` 决定）。"""

    reason: str
    category: str | None = None


@dataclass(frozen=True)
class CommandReport:
    """整体报告：一个 verdict + 来源表 + 命令明细 + 结构明细。"""

    verdict: CommandVerdict
    sources: tuple[CommandSource, ...]
    findings: tuple[CommandFinding, ...]
    structure_findings: tuple[CommandStructureFinding, ...]

    def source_of(self, source_id: int) -> CommandSource | None:
        """按 ``source_id`` 取来源；不存在返回 ``None``。"""
        for source in self.sources:
            if source.source_id == source_id:
                return source
        return None

    def is_allowed(self) -> bool:
        """是否整体放行（等价于 ``verdict == "allow"``）。"""
        return self.verdict == "allow"


# ==========================================================================
# 规则身份与生效机制
# ==========================================================================
#
# 本段承载规则身份与生效机制，与上文的「结果契约 / 形状词汇」同属**基础定义层**。
# 依赖边界：数据模块（``command_allowlist`` 等）只能从本模块取**类型**，不得取**机制**
# ——该约束由 ``test_command_rules_registry`` 的边界测试守着。


@dataclass(frozen=True)
class RuleSpec:
    """单条规则的元数据（唯一的规则身份形状）。

    字段集 = Codex 概念模型的 ``pattern`` / ``decision`` / ``justification``
    （``match`` / ``not_match`` 承载加载期自测样例），加上本仓库需要的身份与机制字段。
    规则就是规则：**所有规则都可被平台配置**（替换 / 关闭），无「可配性」例外字段。

    ``verdict`` 直接用报告契约的 :data:`CommandVerdict`（``allow`` / ``review`` / ``block``）——
    无「Codex 词 → 本仓库词」的翻译层：术语对齐的价值在概念，不在字段拼写，
    而 ``review`` 比 ``prompt`` 更准确（它确实走人工审批）。

    **对 Codex 的唯一有意偏离：``decision`` 必填、无默认值。** Codex 的
    ``decision`` 默认 ``allow``；本仓库若照搬，未知命令会从 ``review`` 翻成
    ``allow``，等于静默取消全部未知命令的人工审批（fail-open）。
    本仓库的 fail-closed 立场是「空规则 entry 不得判 allow」（``command_security``
    的 ``_evaluate_rules`` 在零规则命中时回落 ``review``，正是该语义的载体），
    故 ``decision`` 必填，缺省即 ``TypeError``。

    ``pattern`` 是「这条规则靠什么数据判定」的**可字面化**形状
    （:class:`Pattern`，定义在 :mod:`...command_definitions`）；``None`` 表示
    内容不可字面化（代码谓词 / 未登记）。:attr:`literalizable` 是下发通道准入判据：
    只有可字面化的规则能进下发通道。

    ``predicate`` 是「这条规则**如何**被判定」的可调用体（:class:`RulePredicate`）。
    类型取材于叶子模块而非本模块，以维持本模块「模块级同包依赖只有
    ``command_definitions``」的边界。可字面化的规则**通常不必手写它**——用
    :meth:`resolve_predicate` 从 ``pattern`` 派生即可（唯一真源仍是 pattern）。

    ``match`` / ``not_match`` 是加载期自测样例（Codex：
    "think of them as unit tests"）——由
    ``command_rule_validation.load_time_self_test`` 校验。
    """

    rule_id: str
    category: str
    verdict: CommandVerdict
    justification: str
    pattern: Pattern | None = None
    predicate: RulePredicate | None = None
    match: tuple[tuple[str, ...], ...] = ()
    not_match: tuple[tuple[str, ...], ...] = ()

    @property
    def literalizable(self) -> bool:
        """本规则能否进入平台下发通道（能表达为声明式数据）。

        ``pattern`` 非空且其修饰符组合可被声明式表达（:attr:`Pattern.is_literalizable`）。
        平台的 ``RuleSpecConfig.tokens`` 走同一判据，故「能下发」与「本地能派生谓词」
        不会出现两套结论。
        """
        return self.pattern is not None and self.pattern.is_literalizable

    def resolve_predicate(
        self,
        *,
        resolver: RuleResolver,
        extra: Callable[[RuleSpec], RulePredicate] | None = None,
    ) -> RuleSpec:
        """返回**谓词已定**的副本：可字面化者由 ``pattern`` 派生，否则用自带 ``predicate``。

        这是「可字面化规则不手写谓词」的机制归属地：``pattern`` 在容器字面量里只写一遍，
        谓词在此**就地**派生——不再需要构造后再遍历补齐的第二个容器。

        取值规则（任一情形都保证 ``predicate`` 非空）：

        - ``pattern`` 非空 → 调 ``resolver(self)`` 派生。派生谓词的 ``verdict`` 由
          resolver **自身**从 ``spec.verdict`` 读取——调用点与本方法都**不写** verdict，
          故「忘传 verdict」在结构上不可能（不是靠调用点自觉）。若 ``self.predicate``
          **也**有值（规则自带、且读 ``context.spec.pattern`` 的代码谓词，如
          ``syntax:forbidden_command``），两者取**并集**。
        - ``pattern`` 为空 → 用自带 ``predicate``。
        - 给了 ``extra`` → 以**本 spec**为入参调用它，产出补充谓词并一并取**并集**。

        Args:
            resolver: **谓词构造器** ``spec -> RulePredicate``（:data:`RuleResolver`）。
                必填、无默认值——缺省即 ``TypeError``，与 :class:`RuleSpec` 的
                ``decision`` 必填同型（fail-loud）：叶子层无法提供默认实现
                （归一化口径住在数据模块，会成环），而静默回落 ``None`` 会让规则永不生效。
                实现由**知情方注入**——数据模块（``command_blocklist``）或聚合点。
            extra: 可选的**补充谓词构造器** ``spec -> RulePredicate``——用于 ``Pattern``
                表达不了的那部分判据（如 ``package_install`` 无法表达的 ``pip[0-9.]*``
                数字后缀族）。之所以收**构造器**而非谓词本身：补充谓词常需要按 spec
                定制闭包（读 ``spec.pattern`` 等），且这样调用点就是一行 ``extra=...``，
                不必另立一张 ``label -> 谓词`` 的旁表。

        Raises:
            AssertionError: 既无 ``pattern``、又无自带谓词，且无 ``extra``——
                该规则会永不生效，属加载期错误（fail-loud）。
        """
        predicates: list[RulePredicate] = []
        if self.pattern is not None:
            predicates.append(resolver(self))
        if self.predicate is not None:
            predicates.append(self.predicate)
        if extra is not None:
            predicates.append(extra(self))
        if not predicates:
            raise AssertionError(  # pragma: no cover - 加载期自检
                f"规则 {self.rule_id!r} 既无 pattern、又无谓词（会永不生效）"
            )
        if len(predicates) == 1:
            return replace(self, predicate=predicates[0])
        return replace(self, predicate=_union_predicates(self.rule_id, *predicates))


#: 谓词构造器：给一条 spec，产出它的**代码侧**谓词。
#:
#: 由聚合点（``command_security``）或危险规则的数据模块（``command_blocklist``）构造并注入
#: —— 因为归一化口径（``effective_command_name`` / ``_literal_args``）住在 ``command_blocklist`` /
#: ``command_parser``，而本模块是**依赖叶子**，不得 import 它们（会成环，由
#: ``test_base_module_does_not_import_data_modules`` 与
#: ``test_base_module_sibling_deps_are_only_deferred_aggregation`` 双向钉死）。
#:
#: 形状与 :meth:`RuleSpec.resolve_predicate` 的 ``extra`` 参数**逐字同形**
#: （``Callable[[RuleSpec], RulePredicate]``）——本阶段把「注入 Callable 给叶子」这一
#: 已在 ``build_rule_set`` 的 ``to_spec`` / ``predicate_for`` 上验证过的手法，
#: 推广到 ``resolve_predicate`` 的主路径。
#:
#: **本模块只声明形状、零实现**：任何默认实现都要 import ``effective_command_name``，
#: 会在 import 期成环。
RuleResolver = Callable[["RuleSpec"], RulePredicate]


# ========== 平台规则配置错误 ==========


class RuleConfigError(ValueError):
    """平台规则配置非法（不可字面化 / 关闭未登记 id / 遮蔽代码谓词规则 / 关闭分析失败标识）。

    构造期 fail-closed：宁可让配置加载失败，也不静默忽略——运营者以为规则已关
    而它仍在生效，是最危险的失败模式。
    """


# ========== 一次校验的完整规则视图 ==========


@dataclass(frozen=True)
class RuleSet:
    """一次 ``validate_command`` 的**规则视图**（显式、不可变、每请求构造一次）。

    只承载**规则相关**的三件东西——前两件是 :func:`build_rule_set` 的派生结果，
    第三件由调用方按开关过滤后填入：

    - ``specs``：内置规则 ∪ 平台声明的生效规则的**合并结果**。同 rule_id 的完整声明
      即替换该内置（身份不变、内容/判定变为声明值）；未登记 id 即新增。
      这是**身份全集**，与开关无关；
    - ``disabled``：被平台**按 id 关闭**的 rule_id 集合（``enabled=false`` 声明）。
      被关闭的规则**仍在 ``specs`` 里**（身份保留），但不进 ``active_specs``——
      构造期的成员关系物化，使 ``_evaluate_rules`` 无需知道「关闭」这件事；
    - ``active_specs``：``specs`` 去掉 ``disabled``、再经**开关过滤**后的**可跑子集**——
      ``_evaluate_rules`` 只遍历它。过滤（``command_security._active_specs``）发生在
      聚合点，故本对象**不持有任何开关的值**，只承载开关对成员关系的物化结果。

    **「全集 vs 可跑子集」是本类刻意的两个字段**，不可塌缩为一个：
    ``specs`` 答「这条规则是什么」（身份，与开关 / 关闭无关），``active_specs`` 答
    「本轮跑哪些」（成员关系，随关闭与开关变化）。若只用 ``active_specs`` 一个字段，
    「平台声明的 rule_id 是替换内置还是新增」这类身份判定会被开关污染。

    **配置在哪里生效：全部在构造期。** 平台声明在 :func:`build_rule_set` 里落成
    ``specs``（内容 + 谓词）与 ``disabled``；命中阶段只反映已生效的判定，
    **没有**「聚合后改写 finding」这一步（故本类不再持有 overrides 表）。

    **请求级配置值不属于本对象。** 它们（``allowed_script_dirs`` /
    ``dynamic_execution_policy``）是平台原始输入，由 ``SecurityCommandSettings``
    直接携带，与 :class:`RuleSet` **并列**传入 ``_process_source`` / ``_evaluate_rules``。
    放行平台白名单命令的通道是**本对象 ``specs`` 里的 allow 规则声明**，
    不是请求级旁路参数。
    若把它们的**值**塞进本对象，会导致「叫 RuleSet 却装着编排配置」的名实不符，
    并让 :func:`build_rule_set` 需要四处 duck-typed ``getattr`` 复制配置——
    职责被污染。故按「派生产物 vs 原始输入」分层。
    （注意区分：开关的**值**不在本对象里；开关的**效果**通过 ``active_specs`` 物化。）

    构建入口唯一：:func:`build_rule_set`。``active_specs`` 由该函数以
    「未过滤 = 全集」初始化，再由调用方（``validate_command``）用
    ``dataclasses.replace`` 填入「去 disabled + 开关过滤」后的结果。

    ``_evaluate_rules`` 遍历 ``active_specs``，**不**读模块级全局 ``RULE_SPECS``。
    """

    specs: Mapping[str, RuleSpec]
    active_specs: Mapping[str, RuleSpec]
    disabled: frozenset[str] = frozenset()


def build_rule_set(
    settings: SecurityCommandSettings,
    all_specs: Mapping[str, RuleSpec],
    *,
    to_spec: Callable[[Any], RuleSpec] | None = None,
    predicate_for: "Callable[[RuleSpec, Pattern, Sequence[Any]], RulePredicate] | None" = None,
) -> RuleSet:
    """从 :class:`SecurityCommandSettings` 与**规则全集**构造一次校验的完整规则视图。

    返回 :class:`RuleSet`——**唯一**的规则集合构建入口。平台声明在这里被**统一**编译：

    - ``enabled=False`` 的声明 → 收集进 ``disabled``（按 id 关闭，内容是原样不动的）；
    - ``enabled=True`` 的声明 → 编译成 ``specs`` 里的一条 spec（同 rule_id 覆盖内置，
      未登记 id 即新增——**同一条路径**，无「改内置 vs 新增」之分）。

    ``active_specs`` 初值为「全集去掉 disabled」。开关过滤由聚合点在
    ``validate_command`` 里另行 ``replace`` 填入（本模块是依赖叶子，不得 import
    开关词汇）。**没有「聚合后改写 finding」这一步**——禁用靠不进 ``active_specs``、
    改档位靠 spec 自带 verdict，二者都在构造期决定。

    **谓词在构造期定型（本函数的又一条保证）**：返回前统一为 ``merged_specs`` 里
    每条 ``predicate is None`` 的 spec 就地按 ``pattern`` 派生谓词
    （:func:`data_predicate_for`，与旧派发期回落同口径）。故 ``specs`` /
    ``active_specs`` 中**不存在**无谓词的条目；既无谓词又无可字面化 pattern 的 spec
    在此 fail-closed 报错（永不生效 = 加载期错误）。由此派发层
    （``command_security._evaluate_rules``）直接消费 ``spec.predicate``，不再派生。

    ``settings`` 的**类型是真实的上游模型**（:class:`SecurityCommandSettings`，
    模块级 import）。依赖方向 ``packages/security`` → ``pydantic_models`` 是正向，
    不成环：``pydantic_models`` 不 import 本包（反向才是违规）。规则全集的**类型**
    只用到 :class:`RuleSpec`，其**位置**（谁聚合）由调用方决定——编排层传
    ``command_security.RULE_SPECS``，测试可传自定义小全集。

    fail-closed 判据（构造期，任一违反即 :class:`RuleConfigError`）：

    1. **代码谓词遮蔽**：``enabled=True`` + rule_id 命中**代码谓词内置**
       （``not spec.literalizable``）——声明式内容会**遮蔽**其代码判定
       （静默解除一条代码规则），故拒绝。要关它请用 ``enabled=False``，
       要改判据请新增一条不同 rule_id 的规则；
    2. **不可字面化**：``enabled=True`` + 声明**不可字面化**（``tokens`` 为空 / 形状非法）
       —— 该判据对「替换内置」与「新增」**同一套**（这正是消除双重含义的关键）。

    **不设「关闭未登记 id」闸门**：``enabled=False`` 指向一条未登记的 rule_id 是被
    允许的（该 id 只进 ``disabled``，不产出 spec）。运营者先新增、后不再需要，
    改 ``enabled=False`` 比删规则更常见，拒绝它没有安全收益。

    本函数在**每次** ``validate_command`` 都会跑一遍，是规则配置 fail-closed 的
    **唯一**校验点（``command_security.validate_command`` 的第一件事即调用它）。

    Args:
        settings: 命令防护配置（:class:`SecurityCommandSettings`；取 ``settings.rules``
            作为平台声明列表）。
        all_specs: ``rule_id -> RuleSpec`` 的规则全集；命中内置即「替换」，未命中即「新增」。
        to_spec: **未登记 id**（新增规则）的声明→:class:`RuleSpec` 转换器，由聚合点注入。
            ``None`` 时有新增规则则 fail-closed 报错——静默丢弃一条平台规则是最危险的失败模式。
        predicate_for: **替换内置规则**的谓词重建器 ``(base_spec, pattern, tokens) -> RulePredicate``，
            同样由聚合点注入。用于「被替换的内置规则**自带谓词且不读 ``pattern``**」的情形
            —— 那些规则换 pattern 不会自动跟随，必须显式重建谓词。本模块是依赖叶子，
            重建需要 ``effective_command_name`` / ``effective_command_args`` 这类归一化口径
            （住在 ``command_parser`` / ``command_blocklist``），故只能注入。
            ``None`` 时若出现「替换内置」则 fail-closed 报错。
    """
    raw_rules = settings.rules

    # 按单一开关 ``enabled`` 分流——**这是唯一的分叉**。
    # ``enabled=False`` 的声明只关闭（内容字段一律忽略），``enabled=True`` 的声明是完整规则。
    #
    # **关闭未登记的 rule_id 是允许的**：平台下发一条 ``enabled=False`` 的全新 id
    # （可能是先前新增、后又不再需要的规则）应被接受——运营者配置后发现不需要，
    # 改成 ``enabled=False`` 比「删掉规则」更常见。该 id 只进 ``disabled``，
    # 不产出任何 spec（``merged_specs`` 从内置全集起，未登记 id 不会凭空出现）。
    to_disable = [r for r in raw_rules if not bool(getattr(r, "enabled", True))]
    to_declare = [r for r in raw_rules if bool(getattr(r, "enabled", True))]

    # 闸门 3（遮蔽代码谓词内置）：命中内置但该内置不可字面化（判定是代码语义），
    # 用纯声明式内容替换会静默解除其代码判定——这是最危险的失败模式，故拒绝。
    declare_unknown: list[Any] = []
    shadow_code_predicate: list[str] = []
    for declaration in to_declare:
        base = all_specs.get(declaration.rule_id)
        if base is None:
            declare_unknown.append(declaration)
        elif not base.literalizable:
            shadow_code_predicate.append(declaration.rule_id)
    if shadow_code_predicate:
        raise RuleConfigError(
            f"以下内置规则的判定是代码语义（不可字面化），不可用声明式内容替换：{sorted(shadow_code_predicate)}；"
            f"要用声明式内容替换一条内置规则，该内置规则必须可字面化；"
            f"要关闭它请下发同 id 且 enabled=false 的声明；要改判据请新增一条不同 rule_id 的规则"
        )

    # 闸门 4（不可字面化）：enabled=True 的声明**必须**有可字面化内容，对「替换内置」
    # 与「新增」**同一判据**（消除「空 tokens 对内置=调开关 / 对新增=非法」的双重含义）。
    not_literalizable = sorted(r.rule_id for r in to_declare if not _declaration_is_literalizable(r))
    if not_literalizable:
        raise RuleConfigError(
            f"以下声明不可字面化（tokens 为空或形状非法），无法建立判定，故不允许下发：{not_literalizable}；"
            f"enabled=true 的声明必须给出可字面化内容（tokens + 位置/flag 修饰符的可表达组合），"
            f"代码型判定须内置；若只想关闭某条规则请用 enabled=false"
        )

    # 装配：``merged_specs`` 从内置全集起，``enabled=True`` 的声明逐条覆盖 / 新增。
    merged_specs: dict[str, RuleSpec] = dict(all_specs)

    # 新增规则（未登记 id）→ 注入的 ``to_spec``；缺转换器即 fail-closed。
    if declare_unknown and to_spec is None:
        raise RuleConfigError(
            f"存在 {len(declare_unknown)} 条未登记 id 的规则声明，但未提供 to_spec 转换器："
            f"{sorted(r.rule_id for r in declare_unknown)}；这是调用方的装配错误（不应静默忽略）"
        )
    for declaration in declare_unknown:
        # 形状非法的声明会由装配点的 ``Pattern.from_mapping`` 抛 ``ValueError`` /
        # ``TypeError``。**归一为 ``RuleConfigError``**（与上方 fail-closed 判据同型），
        # 裸 ValueError 会让调用方无从归因。
        try:
            merged_specs[declaration.rule_id] = to_spec(declaration)
        except (ValueError, TypeError) as exc:
            raise RuleConfigError(
                f"下发规则 {declaration.rule_id!r} 的形状非法，无法装配（规则不会生效）：{exc}"
            ) from exc

    # 替换内置规则（命中 all_specs 且可字面化）→ 重建 pattern + predicate。
    #
    # 两处 rebuild 缺一不可：
    # - ``pattern``：内容真源。``_allowed_hits`` 读 ``context.spec.pattern``，
    #   故换了 pattern，允许列表判定**自动**跟随；
    # - ``predicate``：``spec.predicate`` 一旦非 ``None`` 就被派发层径直使用
    #   （构造期补齐只填 ``None`` 者）。故自带谓词且读 pattern 的规则
    #   （``allowlist:allowed`` 的 ``_allowed_hits``）不必重建，但由
    #   :func:`data_predicate_for` 派生的规则（含 ``package_install`` 的并集）
    #   必须重建，否则新 pattern 永远走不到判定里。
    #
    # 重建由**注入**的 ``predicate_for`` 完成（本模块是依赖叶子，不得 import
    # ``command_blocklist`` / ``command_parser`` 取归一化口径）。
    replaces_builtin = [d for d in to_declare if d.rule_id in all_specs]
    if replaces_builtin and predicate_for is None:
        raise RuleConfigError(
            f"存在 {len(replaces_builtin)} 条替换内置规则的声明，但未提供 predicate_for 重建器："
            f"{sorted(d.rule_id for d in replaces_builtin)}；无法让新内容真正生效"
            f"（会静默沿用旧判定）；这是调用方的装配错误"
        )
    for declaration in replaces_builtin:
        base = merged_specs[declaration.rule_id]
        pattern = Pattern.from_mapping(_declaration_mapping_for_pattern(declaration))
        # **先**把新判定 / 文案 / 分类落到 spec 上，**再**用它重建谓词：
        # ``predicate_for``（数据规则路径）会把 ``base.verdict`` 烘进每条命中，
        # 故它必须看到**替换后**的 verdict，否则判定替换不生效（谓词仍产出内置档位）。
        replaced = replace(
            base,
            verdict=declaration.verdict,
            justification=declaration.justification,
            category=declaration.category,
            pattern=pattern,
        )
        merged_specs[declaration.rule_id] = replace(
            replaced,
            predicate=predicate_for(replaced, pattern, getattr(declaration, "tokens", None) or ()),
        )

    # 构造期**统一补齐谓词**：落到 ``specs`` / ``active_specs`` 的每条 spec 其
    # ``predicate`` 必非空——这是「谓词在构造期定型」的唯一落点，使派发层
    # （``command_security._evaluate_rules``）无需任何回落 / 派生逻辑。
    #
    # 为什么在**这里**而不是派发期：内置 spec 已在各自模块导入时装配谓词
    # （``command_rule_validation.assert_rule_invariants`` 第 2 条钉死），但
    #   - 运行期**注入**的 base spec（测试 monkeypatch ``RULE_SPECS``，其 ``predicate``
    #     为 ``None``）与
    #   - ``_predicate_for_content_override`` 对「纯数据规则」返回 ``None`` 的替换路径
    # 都可能带 ``None``。若留给派发期派生，则「spec 有判定」这一保证散落在两处
    # （构造期 + 派发期各一半），且派发层被迫认识 ``Pattern`` / ``data_predicate_for``
    # ——职责越界。收拢到此：构造期答「这条规则怎么判」，派发期只负责跑。
    #
    # 派生口径与旧派发期回落**逐字一致**（``reason`` 文案尤其）：不传 ``name_of`` /
    # ``args_of``，沿用 ``data_predicate_for`` 缺省（原始 word + 静态参数）。
    for rule_id, spec in merged_specs.items():
        if spec.predicate is not None:
            continue
        pattern = spec.pattern
        if pattern is None or pattern.is_empty:
            # 既无代码谓词、又无可字面化内容 ⇒ 该规则**永不生效**。这是加载期错误，
            # 不得静默放过（静默会让运营者以为规则已下发）。
            raise RuleConfigError(
                f"规则 {rule_id!r} 既无 predicate、又无可字面化 pattern（会永不生效）："
                f"代码型规则必须自带谓词；可数据驱动的规则必须有非空 pattern"
            )
        merged_specs[rule_id] = replace(
            spec,
            predicate=data_predicate_for(
                pattern,
                rule_id=spec.rule_id,
                reason=f"命中规则 {spec.rule_id}",
                verdict=spec.verdict,
                category=spec.category,
            ),
        )

    disabled = frozenset(r.rule_id for r in to_disable)
    # ``active_specs`` 初值 = 全集去掉 disabled（开关过滤由聚合点 replace 填入）。
    active_specs = {rule_id: spec for rule_id, spec in merged_specs.items() if rule_id not in disabled}
    return RuleSet(
        specs=merged_specs,
        active_specs=active_specs,
        disabled=disabled,
    )


def _declaration_mapping_for_pattern(declaration: Any) -> dict[str, Any]:
    """把声明摊平成 :meth:`Pattern.from_mapping` 认得的映射（**替换内置规则**路径用）。

    与 ``command_security._declaration_mapping`` 是**刻意重复**的一份字段清单：
    本模块是依赖叶子（不得 import ``command_security``），而准入判据
    :func:`_declaration_is_literalizable` 已内联同一份清单——若为消除重复而抽公共 helper，
    会让它依赖调用方是否记得注入，反而新增静默失效面。
    """
    return {
        "tokens": list(getattr(declaration, "tokens", None) or ()),
        "positional_index": getattr(declaration, "positional_index", None),
        "positional_equals": list(getattr(declaration, "positional_equals", None) or ()),
        "skip_flags": list(getattr(declaration, "skip_flags", None) or ()),
        "strip_colon": bool(getattr(declaration, "strip_colon", False)),
        "requires_any_flag": bool(getattr(declaration, "requires_any_flag", False)),
    }


def _declaration_is_literalizable(declaration: Any) -> bool:
    """一条 ``enabled=True`` 声明能否构成**可下发的声明式内容**（闸门 4 判据，**唯一**来源）。

    判据 = 「:meth:`Pattern.from_mapping` 能成功构造出**非空** ``Pattern``」。
    **不手写第二套形状校验**：准入判据与搬运能力必须是同一份实现——若准入只看
    ``tokens``，平台就能下发一条「看起来过了准入」但修饰符被静默截断的规则。
    第二套判据会在下次补字段时再次漂移，故此处让准入与搬运看同一份实现
    （字段清单经 :func:`_declaration_mapping_for_pattern` 单点给出）。

    **空内容一律不可字面化**（返回 ``False``）：``enabled=True`` 的声明必须有可字面化
    内容——这条判据对「替换内置」与「新增」**同一套**，不再有「空 = 只调开关」的第二含义。
    只想关闭某条规则请用 ``enabled=false``（那条路径根本不查本判据）。

    鸭子类型读取：本模块是依赖叶子，不得 import ``RuleSpecConfig``。

    Args:
        declaration: 平台声明（鸭子类型：只读六个形状字段）。

    Returns:
        形状合法**且非空**时为 ``True``；空内容 / 形状非法 / 无意义组合时为 ``False``。
    """
    fields = _declaration_mapping_for_pattern(declaration)
    if not any((fields["tokens"], fields["positional_index"] is not None, fields["requires_any_flag"])):
        return False  # 无声明式内容：enabled=true 的声明不允许
    try:
        Pattern.from_mapping(fields)
    except (ValueError, TypeError):
        return False
    return True


# ==========================================================================
# 拒绝文案与归因常量
# ==========================================================================
#
# 三类内容集中于此，使同一语义在解析层与编排层两条路径上逐字一致：
# 拒绝文案、justification 模板与占位符一致性闸门、基础设施 / 硬拒归因常量。
#
# 位置说明：本段**是**数据（文案字面量、规则登记表），而本模块同时承载形状与机制。
# 之所以同居一处：文案的占位符集合要与规则的 ``justification`` 钉成等式，
# 而规则身份（``RuleSpec``）与归因枚举（``AnalysisFailure``）也在本模块，
# 分开会让「模板 ↔ 声明 ↔ 填充」三者的对照跨模块、漂移难以察觉。
# 代价是「本模块只提供形状与类型」不再是绝对约束——数据模块仍只允许取词汇与类型，
# 该方向的不变量由 ``TestDependencyBoundaryIsTwoWay`` 继续守着。


# 以命令名整体禁止的无条件限制命令（不受黑名单开关 / allow 规则放行影响）。
# 内容由**本模块拥有**（字面量）：它同时是 ``syntax:forbidden_command`` 规则的取数来源，
# 集中在文案模块使「命令名禁用面」与「其拒绝文案」同处一文件，改名只需改一处。
FORBIDDEN_COMMANDS: frozenset[str] = frozenset({"nohup", "setsid", "disown", "screen", "tmux"})


def structure_finding(
    source_id: int,
    span: tuple[int, int],
    rule_id: str,
    reason: str,
    *,
    verdict: str = "block",
    category: str | None = "syntax",
) -> CommandStructureFinding:
    """构造一条结构明细（默认硬 block）。"""
    return CommandStructureFinding(
        source_id=source_id,
        span=span,
        rule_id=rule_id,
        verdict=verdict,  # type: ignore[arg-type]
        reason=reason,
        category=category,
    )


def review_unmatched(name: str) -> str:
    """``review`` 的处置文案——该 entry 未命中任何规则，转第三方判断。

    覆盖的是「**未命中任何规则**」（既非 allow 也非 block），而非「不在允许列表」——
    故措辞不得暗示允许列表的存在。该结果在控制流内渲染（见 :data:`REVIEW_UNMATCHED`）。
    """
    return REVIEW_UNMATCHED.format(name=name)


# ========== justification 模板 ==========
#
# **只模板化最外层**：``spec.justification`` 管规则自己的句式；内层 ``detail`` 由
# ``AllowedFlagsOnly``（``command_whitelist`` 的 ``f"不允许使用参数 '{arg}'"``）
# 产出，**不迁移**——它是参数限制表的一部分，不是规则文案。
#
# 两处语义的区分：
#
# - **常量句式**（``f"命中危险命令规则 {label}"``）：``label`` 即 ``rule_id``，
#   不是运行时数据 → ``justification`` 存**纯静态串**，无需占位符；
# - **需运行时数据**（``f"命令 '{name}' {detail}"``）：``justification`` 存带占位符的
#   **模板**，谓词填充。
#
# 模板用 ``str.format`` 语法（``{name}``）。**风险**：占位符拼错会**静默产生残缺文案**
# ——`"{nam}"` 在填充时会 ``KeyError``（fail-loud），但「模板里少写一个占位符」只会少
# 显示一段信息、不抛错。故下方 ``JUSTIFICATION_PARAMS`` 与导入期自检一起，把
# 「模板占位符集合」与「谓词实际填充的键集合」钉成等式（可证伪）。

#: 需运行时数据的规则的 **justification 模板**（``str.format`` 语法）。
#:
#: 每个模板的占位符集合必须与 :data:`JUSTIFICATION_PARAMS` 的声明一致（导入期自检）。
#: 模板本身**只描述句式**，不携带任何规则判定逻辑。
JUSTIFICATION_TEMPLATES: dict[str, str] = {
    "args:restricted": "命令 '{name}' {detail}",
    "dynamic:execution_content": "命令 '{name}' 的执行内容无法静态确定",
    "invocation:unsupported": "命令 '{name}' 的调用形态不受支持: {detail}",
    "allowlist:allowed": "命令 '{name}' 在允许列表中",
    "syntax:script_path": "Shell 脚本{detail}",
    "syntax:command_path": "命令路径不合法: {detail}",
    "ast:unsupported_parameter_execution": "参数 '{text}' 中含未建模的执行结构，不允许执行",
}

# **类型 A（常量句式）的 ``justification`` 不在此模块。**
#
# 常量句式的规则（危险命令 15 条 + syntax/ast 的静态串）的文案**各自住在定义该规则的
# 模块里**：危险规则在 ``command_blocklist._RULE_DEFS`` 的 ``justification`` 字段，
# syntax/ast 在 ``command_syntax_rules.SYNTAX_RULES``。原因：这类文案与规则判据一一对应，
# 分开放会让「改了判据没改文案」成为静默漂移；同处一文件则改动时必然同时看到两者。
#
# 本模块只保留**需运行时数据**的模板：同一句式被多个消费方共用，集中才能保证逐字一致。
# 占位符一致性的**声明**（``JUSTIFICATION_PARAMS``）也留在此处，紧邻模板便于对照。


def render_justification(template: str, **values: object) -> str:
    """按 ``template`` 渲染规则原因文案（缺失键即 ``KeyError``，fail-loud）。

    刻意**不**用 ``format_map`` + 默认字典：占位符拼错必须立刻炸，而不是渲染出
    半截文案。渲染失败属**编程错误**（内置规则的模板与填充点同源），故不做兜底。
    """
    return template.format(**values)


# ``justification_params``（占位符名集合解析）已随导入期自检迁至
# ``command_rule_validation``——它唯一的生产消费方是
# ``assert_justification_templates_are_consistent``。


#: ``rule_id -> 该规则的 ``justification`` 模板所需的填充键集合``（声明式登记）。
#:
#: **为什么在此处、为什么是声明而非 ``RuleSpec`` 字段**：
#:
#: - 放在本模块：它是**文案的归属地**（本模块集中定义全部需填充的 ``reason`` 文案），
#:   而模板本身就是文案；住基础定义模块会让「机制」承载「数据」。
#: - 不加 ``RuleSpec`` 字段：校验只需一个映射，为此扩张规则模型（平台可见的形状）
#:   不划算——模型的每个字段都是下发契约的一部分。
#:
#: 键集合的**真源**是各谓词体的填充点（``_args_restricted_hits`` 填 ``name`` / ``detail``）；
#: 本表是它的**声明**，由 ``command_rule_validation.assert_justification_templates_are_consistent``
#: 与 ``spec.justification`` 的占位符集合比对。二者任一侧漂移即导入期 fail-loud。
JUSTIFICATION_PARAMS: dict[str, frozenset[str]] = {
    # ---- 需运行时数据的规则（模板 + 填充）----
    "args:restricted": frozenset({"name", "detail"}),
    "dynamic:execution_content": frozenset({"name"}),
    "invocation:unsupported": frozenset({"name", "detail"}),
    "allowlist:allowed": frozenset({"name"}),
    "syntax:script_path": frozenset({"detail"}),
    "syntax:command_path": frozenset({"detail"}),
    "ast:unsupported_parameter_execution": frozenset({"text"}),
    # ---- 常量句式的规则：纯静态串，零占位符（显式登记，使「忘了登记」不可能）----
    "shutdown_reboot": frozenset(),
    "user_management": frozenset(),
    "shred_file": frozenset(),
    "rm_recursive_force": frozenset(),
    "rm_forbidden": frozenset(),
    "chmod_777": frozenset(),
    "chown_root": frozenset(),
    "package_install": frozenset(),
    "firewall_change": frozenset(),
    "mkfs_format": frozenset(),
    "curl_pipe_shell": frozenset(),
    "wget_pipe_shell": frozenset(),
    "dd_disk_write": frozenset(),
    "exfil_curl_token": frozenset(),
    "python_module_package_install": frozenset(),
    "syntax:background": frozenset(),
    "syntax:pipe_amp": frozenset(),
    "syntax:forbidden_command": frozenset(),
    "syntax:redirect": frozenset(),
    "syntax:heredoc": frozenset(),
    "syntax:herestring": frozenset(),
    "syntax:brace_expansion": frozenset(),
}


def ensure_template_params_filled(rule_id: str, values: Mapping[str, object]) -> None:
    """**运行时**守卫：某次填充提供的键集合必须覆盖该规则**声明**的键集合。

    这是「谓词填充点」与「声明」之间的第二道闸门——导入期校验
    （``command_rule_validation.assert_justification_templates_are_consistent``）
    保证「模板 ↔ 声明」一致，本函数保证「填充 ↔ 声明」一致。二者合起来使
    「模板 ↔ 填充」也一致，即使三者分居多个文件。

    与 ``command_rule_validation`` 的两个导入期自检（``load_time_self_test`` /
    ``assert_justification_templates_are_consistent``）
    **不同型**：那两者是**导入期**自检（跑一次、失败即导入失败），本函数是**运行时**
    守卫（每次谓词填充 justification 都调用），故命名不用 ``assert_`` 前缀，避免
    被误读为「只在导入期跑一次的断言」。失败抛 ``KeyError``（模板缺键的归因），
    而非 ``AssertionError``。
    """
    declared = JUSTIFICATION_PARAMS.get(rule_id)
    if declared is None:
        return  # 未登记的 id（平台注入的规则）不做此校验
    missing = sorted(declared - set(values))
    if missing:
        raise KeyError(
            f"规则 {rule_id!r} 的 justification 模板需要 {sorted(declared)!r}，"
            f"但填充只提供了 {sorted(values)!r}（缺 {missing}）"
        )


# ---- 解析 / 资源类（编排层使用）----

PARSE_SYNTAX_ERROR = "命令语法错误（可能是引号不匹配或语法不被支持）"
PARSE_UNSUPPORTED_SYNTAX = "命令使用了 bashlex 暂不支持的语法"
PARSE_INTERNAL_ERROR = "命令解析内部错误"
RULE_INTERNAL_ERROR = "命令规则执行内部错误"
EMPTY_NO_EXECUTABLE_COMMAND = "未检测到可执行的命令（空输入、纯空白或纯注释）"
NULL_BYTE = "命令中包含空字节，不允许执行"
BUDGET_RECURSION = "命令结构过于复杂，解析资源超限"
ANALYSIS_INCOMPLETE = "检测未完成：预算或资源超限，后续来源未继续遍历"

#: 纯资源超限时对模型给出的**统一**表述（不含内部计费细节）。
#:
#: 「纯」= 只有预算/递归耗尽、没有任何危险或语法命中。此时向模型讲「节点数 4 超过
#: 上限 3」这类计费明细没有可操作性，反而暴露内部机制；告诉它「命令复杂度过高、
#: 请简化」才是可用指引。内部细节仍保留在 StructureFinding 的 reason 里供审计。
COMMAND_TOO_COMPLEX = "命令复杂度过高"

#: ``review`` 的处置文案 —— 「未命中任何规则，转第三方判断」。
#:
#: ``review`` **不是规则**：它没有 rule_id、不进 ``RULE_SPECS``、不占
#: ``JUSTIFICATION_TEMPLATES``（那是**规则**文案表）；它由 ``_evaluate_rules`` 的
#: else 分支产出——该 entry 既不在允许列表（allow）、也不在任一黑名单（block）——
#: 故文案在控制流内渲染，不进模板表。
#:
#: 用 ``str.format`` 句式以便在控制流内填入命令名；调用方负责填充。
REVIEW_UNMATCHED = "命令 '{name}' 未命中任何规则，需第三方判断（smart 评估或人工审批）"


# ========== 本模块拥有的 rule_id 常量（基础设施 / 硬拒）==========
#
# 这些 id 描述的命令编排层失败路径（解析失败 / 预算超限 / 空命令 / 内部错误）。
#
# **值的唯一真源是 :class:`AnalysisFailure` 枚举**：这里只保留**常量名**（调用点按名
# 引用，故枚举值调整时无需改调用点），值取自 ``AnalysisFailure.<X>.value``。
# 分析失败**不是规则**——它们不占 ``RuleSpec``，不参与规则求值 / 下发 / override；
# 它们是控制流就地产生的归因标识，无需（也不应）出现在平台可配置的规则模型里。

PARSE_SYNTAX_ERROR_ID = AnalysisFailure.PARSE_SYNTAX_ERROR.value
PARSE_UNSUPPORTED_SYNTAX_ID = AnalysisFailure.PARSE_UNSUPPORTED_SYNTAX.value
PARSE_INTERNAL_ERROR_ID = AnalysisFailure.PARSE_INTERNAL_ERROR.value
INPUT_NULL_BYTE = AnalysisFailure.INPUT_NULL_BYTE.value
EMPTY_NO_EXECUTABLE_COMMAND_ID = AnalysisFailure.EMPTY_NO_EXECUTABLE_COMMAND.value
ANALYSIS_INCOMPLETE_ID = AnalysisFailure.ANALYSIS_INCOMPLETE.value
RULE_INTERNAL_ERROR_ID = AnalysisFailure.RULE_INTERNAL_ERROR.value
BUDGET_RECURSION_ID = AnalysisFailure.BUDGET_RECURSION.value
