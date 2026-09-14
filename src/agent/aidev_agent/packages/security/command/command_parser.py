# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_parser

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

AST 遍历器、共享预算与有限词法（**不做解析之外的字符串预处理**）。

本模块的职责边界：

- :func:`walk_nodes` 只消费**已经解析**的 bashlex 节点，用显式迭代栈（不用递归）
  遍历规范子边，填写调用方创建的 :class:`WalkResult`，按节点/深度计费；
- :class:`WalkBudget` 由调用方（``command_security``）创建并在 root 与全部子脚本文本
  之间**共享**；它不持有、也不调用 parser；
- :func:`analyze_shell_invocation` 是 bash/sh/zsh 的**有限 argv adapter**，用显式选项表
  定位静态脚本文本 / 静态文件操作数 / 动态或不支持调用——不做「跳过任意 ``-`` 开头参数」
  的猜测，也不因本机未安装某 shell 而改变 SDK 判定策略。

**本模块拥有 4 条 ``budget:<kind>`` 预算 rule_id 的命名**：私有映射
``_BUDGET_RULE_IDS`` 是唯一产出方（:func:`_budget_exceeded` 是唯一命名入口），
公开只读快照经 :func:`budget_rule_ids` 给出——映射本身不导出。

**本模块不产出任何规则**：10 条 ``syntax:*`` / ``ast:*`` 结构规则归
:mod:`command_syntax_rules` 所有，危险名录归 :mod:`command_blocklist` 所有。本模块只
提供它们所需的遍历 / 词法 / 名字解析口径（``walk_nodes`` / ``classify_word`` /
``effective_command_name`` / ``has_unmodeled_execution`` 等）。

本模块不重新解析任何已解析结构，也不把 word 拼回字符串执行；唯一的字符串切面是
``source.text[pos[0]:pos[1]]``（保留原始引号/转义，供局部语法守卫使用）。

上层 ``packages/security`` 依赖约束不变：只用标准库 / 第三方 bashlex / 本包模块。
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import bashlex.ast as bashast

from .command_definitions import (
    AnalysisFailure,
    CommandSource,
)

# 本模块作为数据模块不跑导入期不变量自检：跨模块完备性只能在同时看得见规则全集
# 与 ``command_definitions`` 文案登记表的聚合点 ``command_security`` 调用
# ``command_rule_validation.assert_rule_invariants`` 判定。


# ========== 异常 ==========


class UnsupportedAstError(Exception):
    """遇到未建模的 AST 结构（未知 kind / 非法子边形状）时抛出。

    仅用于「结构未建模」，不得把所有 ``ValueError`` 一律冒充 unknown kind；
    解析失败与规则实现失败各有独立的分类边界（见 ``command_security``）。
    """


class CommandBudgetExceeded(Exception):
    """预算（长度 / 节点 / 深度 / 再解析深度）超限时抛出。"""

    def __init__(self, rule_id: str, detail: str) -> None:
        super().__init__(f"{rule_id}: {detail}")
        self.rule_id = rule_id
        self.detail = detail


#: 预算阶梯的 ``kind -> rule_id`` 映射，**由 :class:`AnalysisFailure` 派生**
#: （id 的唯一真源是枚举，避免映射与枚举脱钩漂移）。
#:
#: 本模块是这 4 条 id 的**唯一产出方**（:func:`_budget_exceeded` 是唯一命名入口）。
#: ``budget:recursion`` **不在**此处：它由 ``command_security`` 在 ``RecursionError``
#: 处直接抛，不经本映射（其 id 是 ``AnalysisFailure.BUDGET_RECURSION``）。
#:
#: 键是短名（``max_nodes`` 等），值与报告中的 ``struct.rule_id`` **逐字相同**
#: （由本模块的导入期自检 + 测试共同看守）。
#:
#: **模块私有**：唯一真源在此，公开只读快照走 :func:`budget_rule_ids`。
_BUDGET_RULE_IDS: dict[str, str] = {
    AnalysisFailure.BUDGET_MAX_COMMAND_LENGTH.value.removeprefix("budget:"): (
        AnalysisFailure.BUDGET_MAX_COMMAND_LENGTH.value
    ),
    AnalysisFailure.BUDGET_MAX_NODES.value.removeprefix("budget:"): AnalysisFailure.BUDGET_MAX_NODES.value,
    AnalysisFailure.BUDGET_MAX_DEPTH.value.removeprefix("budget:"): AnalysisFailure.BUDGET_MAX_DEPTH.value,
    AnalysisFailure.BUDGET_MAX_REPARSE_DEPTH.value.removeprefix("budget:"): (
        AnalysisFailure.BUDGET_MAX_REPARSE_DEPTH.value
    ),
}


def _budget_exceeded(kind: str, detail: str) -> CommandBudgetExceeded:
    """按 ``budget:<kind>`` 形状构造预算异常（rule_id 命名唯一入口）。"""
    return CommandBudgetExceeded(_BUDGET_RULE_IDS[kind], detail)


def budget_rule_ids() -> frozenset[str]:
    """4 条预算阶梯的 ``budget:<kind>`` rule_id 集合（``budget:recursion`` 不含）。

    公开接口是**函数**而非模块级 dict：调用方只能拿到不可变快照，
    无法就地篡改 id 映射（``_is_pure_budget_rejection`` 的集合代数需要这个集合，
    但不需要、也不应获得写权限）。
    """
    return frozenset(_BUDGET_RULE_IDS.values())


#: 导入期自检（``# pragma: no cover``）：私有映射的 id 集合必须**逐字等于**
#: ``AnalysisFailure`` 的 4 个预算阶梯成员。
#:
#: 漂移后果：``_BUDGET_RULE_IDS`` 的 id 若与枚举脱钩，``CommandBudgetExceeded.rule_id``
#: 与报告 ``rule_id`` 不再相同 → 预算拒绝无法归因。把自检放在枚举旁，使「加一个预算
#: 档位却忘了同步映射」在**导入期**就 fail-loud。
if set(_BUDGET_RULE_IDS.values()) != {  # pragma: no cover - 导入期自检
    AnalysisFailure.BUDGET_MAX_COMMAND_LENGTH.value,
    AnalysisFailure.BUDGET_MAX_NODES.value,
    AnalysisFailure.BUDGET_MAX_DEPTH.value,
    AnalysisFailure.BUDGET_MAX_REPARSE_DEPTH.value,
}:
    raise AssertionError(
        "_BUDGET_RULE_IDS 的 budget id 集合与 AnalysisFailure 的 4 个预算阶梯成员不一致——"
        "预算 id 的唯一真源是 AnalysisFailure 枚举（漂移会让预算拒绝无法归因）。"
    )


# ========== 共享预算 ==========


@dataclass
class WalkBudget:
    """跨 root 与全部子脚本共享的请求级预算。

    四项上限必填（由调用方从 :class:`SecurityCommandSettings` 解析后传入，默认值
    只在模型字段处定义一处）。计数语义：

    - ``used_chars``：累计**未经 strip** 的 source 文本字符数（root + 每个脚本文本）；
    - ``used_nodes``：累计规范子边可达的真实节点数（fd 数字等非节点不计数）；
    - 每 source 的 AST 顶层根深度为 1，子边 +1；
    - ``reparse_depth``：root 脚本为 0，child = parent + 1（**不与结构深度共用**）。

    「等于上限」允许，「超过上限」才抛 :class:`CommandBudgetExceeded`。
    """

    max_command_length: int
    max_nodes: int
    max_depth: int
    max_reparse_depth: int
    used_chars: int = 0
    used_nodes: int = 0

    def before_parse(self, text: str, reparse_depth: int) -> None:
        """每次 ``bashlex.parse`` **之前**调用：先查再解析深度，再累计字符。"""
        if reparse_depth > self.max_reparse_depth:
            raise _budget_exceeded(
                "max_reparse_depth",
                f"脚本再解析深度 {reparse_depth} 超过上限 {self.max_reparse_depth}",
            )
        self.used_chars += len(text)
        if self.used_chars > self.max_command_length:
            raise _budget_exceeded(
                "max_command_length",
                f"累计字符数 {self.used_chars} 超过上限 {self.max_command_length}",
            )

    def charge_node(self, depth: int) -> None:
        """遍历到一个真实节点：先查深度，再累计节点数。"""
        if depth > self.max_depth:
            raise _budget_exceeded("max_depth", f"结构深度 {depth} 超过上限 {self.max_depth}")
        self.used_nodes += 1
        if self.used_nodes > self.max_nodes:
            raise _budget_exceeded("max_nodes", f"节点数 {self.used_nodes} 超过上限 {self.max_nodes}")


# ========== 遍历产物 ==========


@dataclass
class CommandEntry:
    """source 内一个实际命令（有第一个 word 的 ``CommandNode``）。"""

    source_id: int
    entry_id: int
    node: Any
    name_word: Any
    argument_words: list[Any] = field(default_factory=list)
    pipeline_id: int | None = None
    pipeline_index: int = 0


@dataclass
class SyntaxNode:
    """语法位置记录（``parameter`` 附带 quote context）。"""

    source_id: int
    node: Any
    owner_entry_id: int | None = None
    context: str = ""


@dataclass
class PipelineRecord:
    """同一执行上下文中的 pipeline（stage/pipe 有序关系）。"""

    source_id: int
    pipeline_id: int
    stages: list[Any] = field(default_factory=list)
    pipes: list[Any] = field(default_factory=list)
    stage_entries: list[list[int]] = field(default_factory=list)


@dataclass
class WalkResult:
    """一次 source 遍历的完整 inventory。"""

    source: CommandSource = field(default_factory=lambda: CommandSource(0, None, None, ""))
    entries: list[CommandEntry] = field(default_factory=list)
    syntax_nodes: list[SyntaxNode] = field(default_factory=list)
    pipelines: list[PipelineRecord] = field(default_factory=list)


# ========== 遍历 ==========

_LIST_LIKE = ("list", "pipeline", "command", "if", "for", "while", "until", "function")
_LEAF_KINDS = ("tilde", "heredoc", "reservedword", "operator", "pipe")


def _stage_entry(stage_key: tuple[int, int] | None) -> int | None:
    """栈上的 stage identity 是 ``(pipeline_id, stage_index)``；SyntaxNode 只记录 pipeline_id。"""
    return stage_key[0] if stage_key is not None else None


def _children(node: Any) -> list[Any]:
    """按 bashlex 规范子边返回子节点（顺序即本地 API 顺序）。

    - ``function`` **只走 parts**（body 已包含在 parts 中，恰好到达一次）；
    - ``compound`` 走 ``list`` 再 ``redirects``；
    - ``word`` / ``assignment`` 走 ``parts``；
    - ``redirect`` 仅在 ``output`` 是节点时访问 output，再访问存在的 ``heredoc``；
    - ``parameter`` 无规范子边（本地 bashlex 的 ``${...}`` 分支不递归建模内部结构）。
    """
    kind = node.kind
    if kind in _LIST_LIKE:
        return list(getattr(node, "parts", ()) or ())
    if kind == "compound":
        return list(getattr(node, "list", ()) or ()) + list(getattr(node, "redirects", ()) or ())
    if kind in ("word", "assignment"):
        return list(getattr(node, "parts", ()) or ())
    if kind == "redirect":
        children: list[Any] = []
        output = getattr(node, "output", None)
        if isinstance(output, bashast.node):
            children.append(output)
        heredoc = getattr(node, "heredoc", None)
        if isinstance(heredoc, bashast.node):
            children.append(heredoc)
        return children
    if kind in ("commandsubstitution", "processsubstitution"):
        command = getattr(node, "command", None)
        return [command] if isinstance(command, bashast.node) else []
    if kind == "parameter" or kind in _LEAF_KINDS:
        return []
    raise UnsupportedAstError(f"未知 AST 节点类型: {kind!r}")


def walk_nodes(
    nodes: Iterable[Any],
    *,
    source: CommandSource,
    budget: WalkBudget,
    result: WalkResult,
) -> None:
    """遍历**已解析**的 ``nodes``，把 inventory 填入调用方创建的 ``result``。

    使用显式迭代栈（不递归），因此不会与 bashlex 的 Python 递归叠加；遍历中途抛出
    ``CommandBudgetExceeded`` / ``UnsupportedAstError`` 时，**已经收集的 inventory
    仍然保留**，调用方据此保留已归因的结果（``result.entries`` 不被清空）。

    该函数不 parse、不调 ``validate_command``、不合成 wrapper 内的 CommandNode。
    """
    stack: list[tuple[Any, int, tuple[int, int] | None]] = []
    for root in reversed(list(nodes)):
        stack.append((root, 1, None))

    next_entry_id = len(result.entries)
    next_pipeline_id = len(result.pipelines)

    # 整串各位置的引号状态一次算好（O(n)），供每个 parameter 直接查表，
    # 避免逐点从 0 重扫。
    quote_states = _quote_context_map(source.text)

    while stack:
        node, depth, stage_key = stack.pop()
        budget.charge_node(depth)
        kind = node.kind

        in_entry: int | None = None

        if kind == "command":
            entry = _build_command_entry(node, source.source_id, next_entry_id)
            if entry is not None:
                next_entry_id += 1
                if stage_key is not None:
                    entry.pipeline_id = stage_key[0]
                    entry.pipeline_index = stage_key[1]
                result.entries.append(entry)
                in_entry = entry.entry_id
            for part in node.parts:
                result.syntax_nodes.append(SyntaxNode(source_id=source.source_id, node=part, owner_entry_id=in_entry))
        elif kind == "parameter":
            # 记录 parameter 及其**所属词**的 quote context。扫描范围由
            # ``command_syntax_rules._scan_span`` 按 context + ``_delimiter_boundaries``
            # 二分自算，此处不下传词范围。
            result.syntax_nodes.append(
                SyntaxNode(
                    source_id=source.source_id,
                    node=node,
                    owner_entry_id=stage_key[0] if stage_key is not None else None,
                    context=quote_states[node.pos[0]] if node.pos[0] < len(quote_states) else "plain",
                )
            )
        elif kind == "pipeline":
            pipeline = PipelineRecord(source_id=source.source_id, pipeline_id=next_pipeline_id)
            next_pipeline_id += 1
            stages = [part for part in node.parts if part.kind != "pipe"]
            pipeline.pipes = [part for part in node.parts if part.kind == "pipe"]
            for stage in stages:
                pipeline.stages.append(stage)
            result.pipelines.append(pipeline)
            # pipe 节点本身也要进入语法 inventory（|& 规则依赖它）。
            for part in pipeline.pipes:
                result.syntax_nodes.append(
                    SyntaxNode(source_id=source.source_id, node=part, owner_entry_id=_stage_entry(stage_key))
                )
            # 反向入栈：stage 与其自身子上下文共用同一 pipeline identity。
            # 同时为每个 stage 上的条目记录 stage 序号（不跨 source、不从展平邻接推断）。
            stage_index = 0
            for part in reversed(node.parts):
                if part.kind == "pipe":
                    continue
                stack.append((part, depth + 1, (pipeline.pipeline_id, len(pipeline.stages) - 1 - stage_index)))
                stage_index += 1
            continue
        elif kind == "compound":
            for redirect in node.redirects:
                result.syntax_nodes.append(SyntaxNode(source_id=source.source_id, node=redirect, owner_entry_id=None))
        elif kind in ("operator", "pipe"):
            # 语法位置记录：供「后台 &」「|&」等无条件节点限制使用。
            result.syntax_nodes.append(
                SyntaxNode(source_id=source.source_id, node=node, owner_entry_id=_stage_entry(stage_key))
            )
        elif kind in ("commandsubstitution", "processsubstitution"):
            # 记录**已建模**的替换节点：parameter 守卫可直接查这些位置判断
            # ``$(...)`` / ``<(...)`` 是否已由 bashlex 建模，无需对每个 parameter 重新 parse。
            result.syntax_nodes.append(
                SyntaxNode(source_id=source.source_id, node=node, owner_entry_id=_stage_entry(stage_key))
            )

        children = _children(node)
        # 反向入栈，保证 DFS 顺序与本地 API 顺序一致（稳定输出）。
        # stage 归属沿 list/compound/if/for/while/until 向下继承；进入独立
        # substitution 时重置（其内部命令不并入外层 stage）。
        child_stage = stage_key
        if kind in ("commandsubstitution", "processsubstitution"):
            child_stage = None
        for child in reversed(children):
            stack.append((child, depth + 1, child_stage))

    # 遍历完成后统一按真实节点关系计算每个 pipeline 的 stage → entry 映射：
    # 此时 entries 已全部就位，且 entry 自带 pipeline_id（创建时由继承的 stage 决定）。
    _index_all_pipelines(result)


def _build_command_entry(node: Any, source_id: int, entry_id: int) -> CommandEntry | None:
    """从 ``command`` 节点提取命令名 word 与参数 words（跳过 leading assignment/redirect）。"""
    words: list[Any] = []
    for part in node.parts:
        if getattr(part, "kind", None) == "word":
            words.append(part)
    if not words:
        return None
    return CommandEntry(
        source_id=source_id,
        entry_id=entry_id,
        node=node,
        name_word=words[0],
        argument_words=list(words[1:]),
    )


def _index_all_pipelines(result: WalkResult) -> None:
    """按真实节点关系为每个 pipeline 计算 stage → entry_id 映射。

    stage 的「可能命令集合」沿 list / group / subshell / 条件 / 循环向下继承；
    内嵌 pipeline（有独立上下文）、substitution（跨 source/替换）与函数定义体
    （不等同当前 stage 执行）不计入。stage 内部的分号不切断共同管道上下文。

    节点 → entry_id 的解析走 :func:`_entry_ids_by_node_id` 构建的 O(1) 身份映射，
    在 pipeline 循环**之前**只建一次；若在 stage 循环内逐节点线性扫描 ``result.entries``，
    复杂度会退化为 ``Σ(各 stage 节点数 × entries 数)``。
    """
    mapping = _entry_ids_by_node_id(result)
    for pipeline in result.pipelines:
        stage_ids: list[list[int]] = []
        for stage in pipeline.stages:
            ids: list[int] = []
            stack = [stage]
            while stack:
                current = stack.pop()
                kind = current.kind
                if kind == "command":
                    entry_id = mapping.get(id(current))
                    if entry_id is not None and entry_id not in ids:
                        ids.append(entry_id)
                    stack.extend(reversed(_children(current)))
                    continue
                if kind in ("commandsubstitution", "processsubstitution", "pipeline", "function"):
                    continue
                stack.extend(reversed(_children(current)))
            stage_ids.append(sorted(ids))
        pipeline.stage_entries = stage_ids


def _entry_ids_by_node_id(result: WalkResult) -> dict[int, int]:
    """``id(node) -> entry_id`` 身份索引：构建 O(n)，查表 O(1)。

    用 ``id()`` 而非节点对象作 key：bashlex 的 ``node`` 自定义了按 ``__dict__``
    比较的 ``__eq__``/``__hash__``，故 ``{node: ...}`` 会合并内容相同的节点，
    破坏身份语义（等值节点会被静默合并成一条，见 :func:`_index_all_pipelines` 的查表口径）。

    GC 安全性：本映射在调用方内构建并只在该调用方内消费，期间 ``result.entries``
    持有全部 ``entry.node`` 的强引用，无 key 节点可能在映射存续期内被回收。
    """
    return {id(entry.node): entry.entry_id for entry in result.entries}


# ========== 有限词法（静态 / 动态判定与局部守卫）==========


def _quote_context(text: str, index: int) -> str:
    """从 ``text`` 起点扫描到 ``index``，返回进入该位置时的有限词法状态。

    状态取值：``plain``（未引用）/ ``single``（单引号）/ ``double``（双引号）。
    未引用区反斜杠保护下一字符；双引号内反斜杠只保护 shell 规定的一组字符
    （``$ `` ` `` `` `` ` ``、``"``、``\\`` 及换行），其余字符的原样反斜杠不是转义。
    """
    # 单点查询复用整串预计算（线性一次）。
    return _quote_context_map(text)[index]


def _quote_context_map(text: str) -> list[str]:
    """返回 ``text`` 中**每个下标处**进入时的有限词法状态（单次左到右扫描）。

    ``result[index]`` 即 ``_quote_context(text, index)``（``index == len(text)`` 合法）。
    """
    n = len(text)
    states: list[str] = [""] * (n + 1)
    state = "plain"
    i = 0
    while i < n:
        # 当前位置（进入 i 之前）的状态；反斜杠跳步时，被跳过的下一位置沿用同状态。
        states[i] = state
        char = text[i]
        if state == "plain":
            if char == "\\":
                states[i + 1] = state
                i += 2
                continue
            if char == "'":
                state = "single"
            elif char == '"':
                state = "double"
        elif state == "single":
            if char == "'":
                state = "plain"
        elif state == "double":
            if char == "\\":
                nxt = text[i + 1] if i + 1 < n else ""
                if nxt in ("$", "`", '"', "\\", "\n"):
                    states[i + 1] = state
                    i += 2
                    continue
            elif char == '"':
                state = "plain"
        i += 1
    states[n] = state
    return states


@dataclass(frozen=True)
class Structure:
    """一段原文的静态性判定结果。"""

    kind: str
    """``static`` / ``dynamic`` / ``unsupported``。"""

    text: str
    """静态字面值（``static`` 时有效），或动态/不支持的原始片段。"""

    reason: str = ""


_BARE_WORD_RE = re.compile(r"[A-Za-z0-9_.\-+/:=@,%^]+")


def _word_source(source_text: str, word: Any) -> str:
    """取 word 在当前 source 内的原文片段（含引号/转义）。"""
    pos = getattr(word, "pos", None)
    if pos is None:
        return ""
    return source_text[pos[0] : pos[1]]


def classify_word(word: Any, source_text: str) -> Structure:
    """判定一个 word 在**执行位置**是否是静态可确定的字面值。

    静态判据（三条之一，且不含任何展开子节点）：

    1. 原文切片完全落在单引号内（``'...'``）；
    2. 原文切片由双引号包裹且内部无展开/转义（``"..."``）；
    3. 原文切片是**裸字面**：不含引号、反斜杠、``$``、反引号、glob 元字符
       （``*`` / ``?`` / ``[`` ) 与花括号扩展（``{``）。

    其余（ANSI-C / locale 引号、未引用 glob、反斜杠转义、参数/替换）一律
    :class:`Structure` ``dynamic``——即执行内容不确定，由策略决定 block 还是 review。
    """
    raw = _word_source(source_text, word)
    if not raw:
        return Structure("dynamic", raw, "无法定位命令名原文")
    if getattr(word, "parts", None):
        return Structure("dynamic", raw, "命令名含展开（参数/替换）")

    quoted = _quoted_literal(raw)
    if quoted is not None:
        return Structure("static", quoted)
    if _BARE_WORD_RE.fullmatch(raw):
        return Structure("static", raw)
    return Structure("dynamic", raw, "命令名不是静态可确定的字面值")


def _quoted_literal(raw: str) -> str | None:
    """整段被单/双引号包裹且内部无展开时返回去引号字面值，否则 ``None``。"""
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'" and "'" not in raw[1:-1]:
        return raw[1:-1]
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        inner = raw[1:-1]
        if any(ch in inner for ch in ("$", "`", "\\", '"')):
            return None
        return inner
    return None


def has_unmodeled_execution(source_text: str, start: int, end: int) -> tuple[bool, int]:
    """在 ``[start, end)`` 的未引用/双引号区间中查找未建模的执行开启符。

    返回 ``(是否命中, 命中位置)``。识别的开启符：``$(``（非单纯算术 ``$((``）、
    活动反引号、未引用的 ``<(`` / ``>(``。单引号区段内全部忽略（字面文本），
    未引用区的反斜杠保护下一字符，双引号内反斜杠只保护 shell 规定字符——
    双引号**不**抑制 ``$(`` 与反引号。

    调用方负责确认该位置是否已有同 source、同词上下文且开启位置精确相同的真实
    substitution 节点；本函数只做有限词法扫描。
    """
    state = _quote_context(source_text, start)
    i = start
    while i < end:
        char = source_text[i]
        if state == "plain":
            if char == "\\":
                i += 2
                continue
            if char == "'":
                state = "single"
            elif char == '"':
                state = "double"
            elif char == "$" and i + 1 < end and source_text[i + 1] == "(":
                if i + 2 < end and source_text[i + 2] == "(":
                    i += 3
                    continue  # 算术展开：本阶段不解析，但不属「未建模命令执行」
                return True, i
            elif char == "`" or char in "<>" and i + 1 < end and source_text[i + 1] == "(":
                return True, i
        elif state == "single":
            if char == "'":
                state = "plain"
        elif state == "double":
            if char == "\\":
                nxt = source_text[i + 1] if i + 1 < end else ""
                if nxt in ("$", "`", '"', "\\", "\n"):
                    i += 2
                    continue
            elif char == '"':
                state = "plain"
            elif char == "$" and i + 1 < end and source_text[i + 1] == "(":
                if i + 2 < end and source_text[i + 2] == "(":
                    i += 3
                    continue
                return True, i
            elif char == "`":
                return True, i
        i += 1
    return False, -1


# ========== 命令名规范化 / 脚本路径 ==========


def _normalize_command_name(raw_name: str) -> str:
    """规范化命令名：提取 basename、拒绝路径遍历、处理特殊形式。"""
    name = raw_name.strip()

    if not name:
        raise ValueError("空命令名")

    if ".." in name:
        raise ValueError(f"命令名包含路径遍历: {raw_name}")

    if name.startswith("/"):
        normalized = os.path.normpath(name)
        if ".." in normalized:
            raise ValueError(f"命令路径包含遍历: {raw_name}")
        return os.path.basename(normalized)

    if name.startswith(("./", "../")) or ("/" in name and not name.startswith("-")):
        normalized = os.path.normpath(name)
        if ".." in normalized:
            raise ValueError(f"命令路径包含遍历: {raw_name}")
        return os.path.basename(normalized)

    return name


# ========== 命令名与参数解析（唯一归一化路径；含 sudo 内层视图）==========
#
# 这一组是**纯解析**能力：命令名归一化 + 已建模的 ``sudo`` 内层视图，产出一个
# 「有效的」名字与参数。它**不认识任何规则**，是危险规则 / 允许列表 / 参数限制共同
# 消费的底层口径，故归 parser 层。

#: ``sudo`` 中**带一个静态值**的选项（其后一个 word 是选项值，不是内层命令）。
_SUDO_VALUE_OPTIONS = frozenset({"-u", "--user", "-g", "--group"})
#: ``sudo`` 中**无值**的选项（只吞自身）。
_SUDO_NO_VALUE = frozenset({"-n", "--non-interactive"})


def _sudo_argv(entry: CommandEntry, source_text: str) -> list[str] | None:
    """有限 sudo schema：无选项、``-n``、``-u/--user`` ``-g/--group``（各带一个静态值）、``--``。

    其余选项（含动态值）返回 ``None``，表示「已解析但执行语义未建模」。
    """
    words = entry.argument_words
    index = 0
    while index < len(words):
        raw = _word_source(source_text, words[index])
        if raw == "--":
            index += 1
            break
        if raw in _SUDO_NO_VALUE:
            index += 1
            continue
        if raw in _SUDO_VALUE_OPTIONS:
            if index + 1 >= len(words):
                return None
            value = classify_word(words[index + 1], source_text)
            if value.kind != "static":
                return None
            index += 2
            continue
        if raw.startswith("-"):
            return None
        break
    remaining: list[str] = []
    for word in words[index:]:
        value = classify_word(word, source_text)
        if value.kind != "static":
            return None
        remaining.append(value.text)
    return remaining


def _sudo_inner_name(entry: CommandEntry, source_text: str) -> str | None:
    argv = _sudo_argv(entry, source_text)
    return argv[0] if argv else None


def _sudo_inner_args(entry: CommandEntry, source_text: str) -> list[str]:
    argv = _sudo_argv(entry, source_text)
    return argv[1:] if argv else []


def effective_command_name(entry: CommandEntry, source_text: str) -> str | None:
    """规范化后的实际命令名（经已建模 sudo 内部视图）。非静态字面名返回 ``None``。

    必须走与允许列表相同的规范化（``/bin/rm`` -> ``rm``），否则路径限定的危险命令
    会绕过黑名单。

    ``sudo <inner> ...`` 解析为**内层**命令名（``sudo ls`` -> ``ls``）；``_sudo_argv``
    返回 ``None``（未建模的 sudo 选项形态 / 动态选项值）时保持 ``"sudo"`` —— 该名字不在
    静态允许列表里，故调用方一律落到 ``review``，属 fail-closed（绝不因内层名而变成 ``allow``）。

    本函数是命令名解析的**唯一真源**：危险规则与允许列表判定共用，避免两套 sudo 视图漂移。
    """
    name = classify_word(entry.name_word, source_text)
    if name.kind != "static":
        return None
    resolved = name.text
    if resolved == "sudo":
        inner = _sudo_inner_name(entry, source_text)
        if inner is not None:
            resolved = inner
    try:
        return _normalize_command_name(resolved)
    except ValueError:
        return None


def _literal_args(entry: CommandEntry, source_text: str) -> list[str]:
    """静态字面参数（含 sudo 视图的内层参数）。动态参数不参与谓词。"""
    args = [
        value.text
        for value in (classify_word(word, source_text) for word in entry.argument_words)
        if value.kind == "static"
    ]
    if classify_word(entry.name_word, source_text).text == "sudo":
        return _sudo_inner_args(entry, source_text)
    return args


def effective_command_args(entry: CommandEntry, source_text: str) -> list[str]:
    """:func:`effective_command_name` 对应的静态字面参数（非 sudo 时为该 entry 自身参数）。

    ``sudo <inner> <args>`` 返回**内层**命令的参数（``sudo df -h`` -> ``["-h"]``）；
    非 sudo 命令返回自身静态字面参数。参数限制查询必须与本函数配套使用，否则
    ``sudo`` 视图下的参数限制会失效。
    """
    return _literal_args(entry, source_text)


def _check_script_path_allowed(script_path: str, allowed_dirs: list[str]) -> tuple[bool, str]:
    """检查脚本路径是否在允许的目录内（精确命中或子目录命中）。"""
    if not script_path:
        return False, "未指定脚本路径"

    normalized = os.path.normpath(script_path)

    if ".." in normalized:
        return False, f"脚本路径包含目录遍历: {script_path}"

    for allowed_dir in allowed_dirs:
        allowed_normalized = os.path.normpath(allowed_dir)
        if normalized == allowed_normalized:
            return True, ""
        if normalized.startswith(allowed_normalized + os.sep):
            return True, ""

    return False, f"脚本路径不在允许的目录内（允许: {', '.join(allowed_dirs)}）"


# ========== 有限 shell-specific argv adapter ==========

SHELL_NAMES: tuple[str, ...] = ("bash", "sh", "zsh")

# 解释器的「内联代码」选项表。``python -c '...'`` / ``perl -e '...'`` 等把一段
# **内联代码**作为执行内容传入；外层允许列表（``python`` / ``python3`` 属
# ``_SCRIPT_COMMANDS``）会因此让整条命令落 ``allowlist:allowed``。这里把内联代码
# 建模为「动态执行内容」（默认 block，可配 review），与 shell ``-c`` 一致。
# 键为**规范化后**的解释器名（``/usr/bin/python3`` → ``python3``）。
_INTERPRETER_CODE_FLAGS: dict[str, frozenset[str]] = {
    "python": frozenset({"-c"}),
    "python2": frozenset({"-c"}),
    "python3": frozenset({"-c"}),
    "perl": frozenset({"-e", "-E"}),
    "ruby": frozenset({"-e"}),
    "node": frozenset({"-e", "-p", "--eval", "--print"}),
    "php": frozenset({"-r"}),
    "lua": frozenset({"-e"}),
    "tclsh": frozenset({"-c"}),
    "osascript": frozenset({"-e"}),
}


def _match_interpreter_code_flag(name: str, words: list[Any], source_text: str) -> bool:
    """判断该命令 argv 是否命中「解释器 + 内联代码选项」。

    仅识别**精确的**内联代码选项 word（如 ``-c`` / ``-e`` / ``--eval``）；不带内联
    代码选项的解释器调用（如 ``python script.py`` / ``perl script.pl``）不受影响，
    保持静态脚本政策（仍走允许列表/脚本目录政策）。
    """
    flags = _INTERPRETER_CODE_FLAGS.get(name)
    if flags is None:
        return False
    return any(_word_source(source_text, word) in flags for word in words)


@dataclass(frozen=True)
class ShellInvocation:
    """shell 调用形态的静态分析结果。

    ``kind`` 取值：

    - ``none``：不是已建模的 shell 调用（调用方不据此产生规则）；
    - ``script``：定位到静态脚本文本（**由 validate 排队 parse，adapter 不 parse**）；
    - ``script_path``：定位到静态脚本文件操作数（走脚本目录政策）；
    - ``stdin``：shell 无操作数且未用 ``-c``（读标准输入执行，执行源不在本阶段范围）；
    - ``dynamic``：脚本/选项值含未知展开；
    - ``interpreter_code``：解释器 + 内联代码选项（``python -c`` / ``perl -e`` 等）
      ——内联代码内容未知，归类为动态执行内容；
    - ``unsupported``：调用形态未建模（如紧连 ``-cCONTENT``、缺脚本、缺选项值）。
    """

    kind: str
    text: str = ""
    target: str = ""
    detail: str = ""


# 每个 shell 的显式选项表（不猜测「跳过任意 - 开头参数」）
_SHELL_OPTIONS: dict[str, dict[str, Any]] = {
    "bash": {
        "c_flag": True,
        "no_value": frozenset({"-l", "-x", "-e", "--noprofile", "--norc", "--login", "--verbose", "--errexit"}),
        "short_cluster": frozenset("clxe"),
        "value_options": frozenset({"-o", "-O", "--options"}),
        "c_before_dashdash_ok": False,
    },
    "sh": {
        "c_flag": True,
        "no_value": frozenset({"-e", "-x"}),
        "short_cluster": None,
        "value_options": frozenset({"-o", "-O", "--options"}),
        "c_before_dashdash_ok": False,
    },
    "zsh": {
        "c_flag": True,
        "no_value": frozenset({"-e", "-x"}),
        "short_cluster": None,
        "value_options": frozenset({"-o", "-O", "--options"}),
        "c_before_dashdash_ok": True,
    },
}


def analyze_shell_invocation(
    entry: CommandEntry,
    *,
    source: CommandSource,
) -> ShellInvocation:
    """解析 shell 调用 argv，定位静态脚本文本 / 静态文件操作数 / 动态或不支持形态。

    - 带值选项（``-o`` / ``-O`` / ``--options``）精确消耗其后一个 word；
    - ``-c`` 之后的 ``--`` 按已核验语义跳过（bash / sh）；zsh 的该额外形状标记 unsupported；
    - ``--`` 出现在 ``-c`` 之前时终止选项，后续 ``-c`` 视为文件操作数；
    - 已识别 ``-c`` 但缺少脚本 / 选项缺值 → ``unsupported``；
    - 静态判定用与执行位置相同的有限词法（未引用/引号/转义），**不做**去引号字符串重 parse。

    非 shell 的解释器（``python`` / ``perl`` / ...）若带内联代码选项
    （``-c`` / ``-e`` / ``--eval`` 等）→ ``interpreter_code``，交由上层归类为动态执行
    内容；不带该选项时保持 ``none``（静态脚本政策不变）。
    """
    name = entry.name_word.word
    if name not in SHELL_NAMES:
        # 先规范化（``/usr/bin/python3`` → ``python3``），再判定内联代码选项。
        # 仅在**确有**内联代码选项时改变判定，否则保持 ``none``（不误伤静态脚本调用）。
        try:
            normalized = _normalize_command_name(name)
        except ValueError:
            return ShellInvocation("none")
        if _match_interpreter_code_flag(normalized, entry.argument_words, source.text):
            return ShellInvocation("interpreter_code")
        return ShellInvocation("none")

    spec = _SHELL_OPTIONS[name]
    words = entry.argument_words
    source_text = source.text

    index = 0
    c_seen = False
    options_terminated = False

    while index < len(words):
        word = words[index]
        raw = _word_source(source_text, word)
        literal = classify_word(word, source_text)

        if not options_terminated and raw == "--":
            options_terminated = True
            index += 1
            continue

        if options_terminated:
            # ``--`` 之后：第一个静态 word 是文件操作数（`-c` 不再是选项）。
            if literal.kind == "static":
                return ShellInvocation("script_path", text=literal.text, target=literal.text)
            return ShellInvocation("dynamic", text=raw, detail="脚本操作数包含未知展开")

        if raw == "-c":
            c_seen = True
            index += 1
            if index < len(words) and _word_source(source_text, words[index]) == "--":
                if name == "zsh":
                    return ShellInvocation("unsupported", detail="zsh 的 `-c --` 形态未建模，无法确定脚本位置")
                index += 1
            if index >= len(words):
                return ShellInvocation("unsupported", detail="-c 缺少要执行的命令内容")
            script_word = words[index]
            script = classify_word(script_word, source_text)
            if script.kind != "static":
                return ShellInvocation(
                    "dynamic", text=_word_source(source_text, script_word), detail="脚本文本包含未知展开"
                )
            return ShellInvocation("script", text=script.text, target=script.text)

        if raw in spec["value_options"]:
            if index + 1 >= len(words):
                return ShellInvocation("unsupported", detail=f"选项 {raw} 缺少取值")
            value = classify_word(words[index + 1], source_text)
            if value.kind != "static":
                return ShellInvocation("dynamic", text=raw, detail=f"选项 {raw} 的取值包含未知展开")
            index += 2
            continue

        if raw in spec["no_value"]:
            index += 1
            continue

        cluster = spec["short_cluster"]
        if cluster is not None and _is_short_cluster(raw, cluster):
            # 组合短选项（如 -lc/-xec）：含 c 时下一个 word 是脚本。
            if "c" in raw:
                c_seen = True
                index += 1
                if index >= len(words):
                    return ShellInvocation("unsupported", detail=f"选项 {raw} 中的 -c 缺少要执行的命令内容")
                script = classify_word(words[index], source_text)
                if script.kind != "static":
                    return ShellInvocation(
                        "dynamic", text=_word_source(source_text, words[index]), detail="脚本文本包含未知展开"
                    )
                return ShellInvocation("script", text=script.text, target=script.text)
            index += 1
            continue

        if raw.startswith("-"):
            return ShellInvocation("unsupported", detail=f"选项 {raw} 未建模")

        if literal.kind == "static":
            return ShellInvocation("script_path", text=literal.text, target=literal.text)
        return ShellInvocation("dynamic", text=raw, detail="脚本操作数包含未知展开")

    if c_seen:
        return ShellInvocation("unsupported", detail="-c 缺少要执行的命令内容")
    # 无操作数、未用 -c 的交互式/标准输入执行：本阶段不建模其执行源（由调用方按策略处理），
    # 不属「调用形态未建模」，故返回 ``none``（命令自身规则照常运行）。
    return ShellInvocation("stdin")


def _is_short_cluster(raw: str, alphabet: frozenset[str]) -> bool:
    """判断是否为「由已知字母组成且含 ``c`` 的短选项簇」（如 ``-lc`` / ``-xec``）。"""
    if len(raw) < 3 or not raw.startswith("-") or raw.startswith("--"):
        return False
    letters = raw[1:]
    return all(letter in alphabet for letter in letters)
