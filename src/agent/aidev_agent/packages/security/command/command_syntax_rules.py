# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_syntax_rules

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

结构约束规则（9 条 ``syntax:*`` + 1 条 ``ast:*``）。

本模块的职责边界：

- :data:`SYNTAX_RULES` 的 10 条规则判定条件全部是**结构位置**（节点 kind / op /
  重定向形态 / 命令名路径），无法由 ``Pattern`` 表达，故各自手写谓词；
- 产出的是**结构明细**（``owner_entry_id is None``）——唯一例外是后两条按 entry 归属；
- 谓词消费 ``context.walked``（单 source inventory）而非 entry，故统一派发层对每个
  source 只调用一次（无 entry 上下文）。

**语义分类**：这 10 条的 category 为 ``syntax`` / ``ast``，属「无法判定」族
（``command_rule_validation._NON_HAZARD_BLOCK_CATEGORIES``），**刻意不在**
``BLOCKLIST_CATEGORIES`` 内、不受 ``enable_command_blocklist`` 开关管辖——
它们是解析器的能力边界，不是「命令危险」。故本模块**不并入**
``command_blocklist.ALL_BLOCKLIST_RULES``；本模块只是物理归属地。

依赖方向：``command_syntax_rules → command_parser``（单向）。谓词所需的遍历 / 词法 /
名字解析口径由 ``command_parser`` 提供，本模块只做规则的判定与产出。
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Sequence
from typing import Any

import bashlex.ast as bashast

from .command_definitions import (
    FORBIDDEN_COMMANDS,
    JUSTIFICATION_TEMPLATES,
    CommandSource,
    Pattern,
    RuleContext,
    RuleHit,
    RuleSpec,
    ensure_template_params_filled,
    names,
    render_justification,
)
from .command_parser import (
    CommandEntry,
    WalkResult,
    _check_script_path_allowed,
    _children,
    _normalize_command_name,
    analyze_shell_invocation,
    has_unmodeled_execution,
)

# ========== 本模块拥有的 rule_id 常量 ==========
#
# 这些 id 由**本模块产出**（结构约束 + 未建模参数执行），故字面量的归属地在本模块。

SYNTAX_BACKGROUND = "syntax:background"
SYNTAX_PIPE_AMP = "syntax:pipe_amp"
SYNTAX_FORBIDDEN_COMMAND = "syntax:forbidden_command"
SYNTAX_REDIRECT = "syntax:redirect"
SYNTAX_HEREDOC = "syntax:heredoc"
SYNTAX_HERESTRING = "syntax:herestring"
SYNTAX_BRACE_EXPANSION = "syntax:brace_expansion"
SYNTAX_COMMAND_PATH = "syntax:command_path"
SYNTAX_SCRIPT_PATH = "syntax:script_path"
AST_UNSUPPORTED_PARAMETER_EXECUTION = "ast:unsupported_parameter_execution"

# ========== 语法规则的谓词（本模块拥有）==========
#
# 9 条 ``syntax:*`` + 1 条 ``ast:*`` 的判定条件全部是**结构位置**（节点 kind / op /
# 重定向形态 / 命令名路径），无法由 ``Pattern`` 表达，故各自手写谓词。
# 产出的是**结构明细**（``owner_entry_id is None``）——唯一例外是后两条按 entry 归属。
#
# 谓词消费 ``context.walked``（单 source inventory）而非 entry，故统一派发层对每个
# source 只调用一次（无 entry 上下文）。


def _syntax_hit(
    rule_id: str,
    span: tuple[int, int],
    reason: str,
    *,
    context: RuleContext,
    category: str = "syntax",
    owner_entry_id: int | None = None,
) -> RuleHit:
    """构造一条语法规则命中。

    verdict 读 ``context.spec.verdict``（**不是**硬编码 ``"block"``）：平台用一条同 id 的
    完整声明替换某条可字面化结构规则时，判定必须跟随——与本文件其余「内容读
    ``context.spec.pattern``」的收敛口径一致（``context.spec`` 为 ``None`` 的谓词单测
    场景回落内置默认 ``"block"``）。
    """
    verdict = getattr(context.spec, "verdict", None) or "block"
    return RuleHit(
        rule_id=rule_id,
        verdict=verdict,
        reason=reason,
        category=category,
        owner_entry_id=owner_entry_id,
        span=span,
    )


def _render_justification(context: RuleContext, **values: object) -> str:
    """从 ``context.spec.justification``（模板）渲染原因文案。

    与 ``command_blocklist._spec_justification`` 同一渲染口径，故全仓只有一个
    justification 来源：规则的原因句子只存在 ``justification`` 一处，谓词不硬编码文案；
    需要运行时数据的规则在 ``justification`` 里存 ``str.format`` 模板，此处填充。
    占位符与填充键的一致性由 ``command_definitions`` 的导入期校验 + 运行时守卫共同保证。

    ``context.spec`` 为 ``None``（谓词单测直接构造 ``RuleContext``）时回落空串。
    """
    template = getattr(context.spec, "justification", None)
    if template is None:
        return ""
    ensure_template_params_filled(getattr(context.spec, "rule_id", ""), values)
    return render_justification(template, **values)


def _iter_nodes(result: Any) -> Any:
    """按固定顺序遍历 ``_root_nodes`` 的语法节点（去重、保序）。

    抽成生成器使各语法谓词共享同一遍历语义。顺序契约：本生成器只做「按栈弹出顺序
    产出」，**不重排**；聚合侧对 ``rules`` 做 ``sorted``，对结构明细则按产出顺序保留。
    故各谓词的产出顺序不能依赖遍历顺序以外的假设。
    """
    stack = list(_root_nodes(result))
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        yield node
        kind = node.kind
        if kind == "command" or kind == "word":
            stack.extend(_children(node))
            continue
        stack.extend(_children(node))


def _syntax_background(context: RuleContext) -> Sequence[RuleHit]:
    """``syntax:background``：后台执行符 ``&``。"""
    hits: list[RuleHit] = []
    for node in _iter_nodes(context.walked):
        if node.kind == "operator" and node.op == "&":
            hits.append(
                _syntax_hit(SYNTAX_BACKGROUND, node.pos, "命令中包含后台执行符（&），不允许执行", context=context)
            )
    return hits


def _syntax_pipe_amp(context: RuleContext) -> Sequence[RuleHit]:
    """``syntax:pipe_amp``：``|&`` 操作符。"""
    hits: list[RuleHit] = []
    for node in _iter_nodes(context.walked):
        if node.kind == "pipe" and getattr(node, "pipe", None) == "|&":
            hits.append(_syntax_hit(SYNTAX_PIPE_AMP, node.pos, "命令中包含 |& 操作符，不允许执行", context=context))
    return hits


def _syntax_forbidden_command(context: RuleContext) -> Sequence[RuleHit]:
    """``syntax:forbidden_command``：命令名（**原始 word**）命中无条件禁用集合。

    名字取 :func:`command_parser._entry_name`（原始 word，**不归一化**）——
    故 ``/usr/bin/nohup`` 不命中。

    内容从 ``context.spec.pattern`` 读取（**不是模块级 ``_FORBIDDEN_COMMAND_CONTENT``
    快照**）：后者是导入期定格的，改 spec 内容不会生效——这正是本谓词存在的理由。
    """
    hits: list[RuleHit] = []
    source_text = context.walked.source.text
    pattern = getattr(context.spec, "pattern", None)
    if pattern is None or pattern.is_empty:
        # 无 pattern 登记（不应发生在内置规则上）：保守回落到本模块登记的形状。
        pattern = _FORBIDDEN_COMMAND_CONTENT
    for node in _iter_nodes(context.walked):
        if node.kind != "command":
            continue
        name = _entry_name(context.walked, node, source_text)
        if name is not None and pattern.matches(name, []):
            hits.append(_syntax_hit(SYNTAX_FORBIDDEN_COMMAND, node.pos, f"命令 '{name}' 不允许执行", context=context))
    return hits


def _syntax_redirect(context: RuleContext, *, heredoc: bool = False, herestring: bool = False) -> Sequence[RuleHit]:
    """重定向家族：``syntax:redirect`` / ``syntax:heredoc`` / ``syntax:herestring``。

    三条规则共享同一个节点遍历（都只看 ``redirect`` 节点），但**各自独立判定**，
    故此处以参数区分本次是要哪一条——避免一个谓词产出三种 rule_id（那会让
    「一条 spec 一个谓词」的对应关系失效）。
    """
    hits: list[RuleHit] = []
    source_id = context.walked.source.source_id
    for node in _iter_nodes(context.walked):
        if node.kind != "redirect":
            continue
        if heredoc:
            if node.type == "<<":
                hits.append(
                    _syntax_hit(
                        SYNTAX_HEREDOC, node.pos, "命令中包含 Here Document 语法（<<），不允许执行", context=context
                    )
                )
        elif herestring:
            if node.type == "<<<":
                hits.append(
                    _syntax_hit(
                        SYNTAX_HERESTRING,
                        node.pos,
                        "命令中包含 Here String 语法（<<<），不允许执行",
                        context=context,
                    )
                )
        else:
            hits.extend(_redirect_hits(node, source_id, context))
    return hits


def _redirect_hits(node: Any, source_id: int, context: RuleContext) -> list[RuleHit]:
    """普通重定向命中（类型 + ``/dev/null`` 豁免）。"""
    del source_id
    redirect_type = node.type
    output = getattr(node, "output", None)
    target = getattr(output, "word", None) if isinstance(output, bashast.node) else None
    if redirect_type in _REDIRECT_EXEMPT_TYPES and target == "/dev/null":
        return []
    # ``<<`` / ``<<<`` 由 ``syntax:heredoc`` / ``syntax:herestring`` 各自的 spec 谓词
    # 产出，本函数只处理普通重定向。
    if redirect_type in ("<<", "<<<"):
        return []
    if redirect_type == "<":
        return [_syntax_hit(SYNTAX_REDIRECT, node.pos, "命令中包含输入重定向（<），不允许使用重定向", context=context)]
    return [
        _syntax_hit(
            SYNTAX_REDIRECT,
            node.pos,
            "命令中包含重定向操作符（>、>>、2>&1 等），不允许使用重定向",
            context=context,
        )
    ]


def _syntax_brace_expansion(context: RuleContext) -> Sequence[RuleHit]:
    """``syntax:brace_expansion``：引号感知的大括号扩展（bashlex 不建模 ``{a,b}``）。"""
    hits: list[RuleHit] = []
    source_text = context.walked.source.text
    for item in context.walked.syntax_nodes:
        node = item.node
        if getattr(node, "kind", None) not in ("word", "assignment"):
            continue
        pos = getattr(node, "pos", None)
        if pos is None:
            continue
        raw = source_text[pos[0] : pos[1]]
        if _brace_expansion_regex_hit(raw):
            hits.append(
                _syntax_hit(SYNTAX_BRACE_EXPANSION, pos, "命令中包含大括号扩展语法（{}），不允许执行", context=context)
            )
    return hits


def _ast_unsupported_parameter(context: RuleContext) -> Sequence[RuleHit]:
    """``ast:unsupported_parameter_execution``：``parameter`` 内含未建模执行结构。"""
    hits: list[RuleHit] = []
    result = context.walked
    source_text = result.source.text
    modeled = _modeled_substitution_offsets(result)
    boundaries = _delimiter_boundaries(source_text)
    scan_cache: dict[tuple[int, int], tuple[bool, int]] = {}
    span_cache: dict[tuple[int, int, str], tuple[int, int]] = {}
    for item in result.syntax_nodes:
        node = item.node
        if getattr(node, "kind", None) != "parameter":
            continue
        pos = getattr(node, "pos", None)
        if pos is None:
            continue
        span_key = (pos[0], pos[1], item.context)
        span = span_cache.get(span_key)
        if span is None:
            span = _scan_span(source_text, item, pos, boundaries)
            span_cache[span_key] = span
        scanned = scan_cache.get(span)
        if scanned is None:
            scanned = has_unmodeled_execution(source_text, span[0], span[1])
            scan_cache[span] = scanned
        hit, offset = scanned
        if hit and offset not in modeled:
            hits.append(
                _syntax_hit(
                    AST_UNSUPPORTED_PARAMETER_EXECUTION,
                    pos,
                    _render_justification(context, text=source_text[pos[0] : pos[1]]),
                    context=context,
                    category="ast",
                )
            )
    return hits


def _syntax_command_path(context: RuleContext) -> Sequence[RuleHit]:
    """``syntax:command_path``：命令名路径非法（路径遍历等），归该 entry。"""
    hits: list[RuleHit] = []
    for entry in context.walked.entries:
        try:
            _normalize_command_name(entry.name_word.word)
        except ValueError as exc:
            hits.append(
                _syntax_hit(
                    SYNTAX_COMMAND_PATH,
                    entry.node.pos,
                    _render_justification(context, detail=str(exc)),
                    context=context,
                    owner_entry_id=entry.entry_id,
                )
            )
    return hits


def _syntax_script_path(context: RuleContext) -> Sequence[RuleHit]:
    """``syntax:script_path``：脚本文本 word 不在 ``allowed_script_dirs`` 内，归该 entry。"""
    hits: list[RuleHit] = []
    source_text = context.walked.source.text
    allowed = list(context.allowed_script_dirs)
    for entry in context.walked.entries:
        script_path = _script_operand(entry, source_text)
        if script_path is None:
            continue
        ok, detail = _check_script_path_allowed(script_path, allowed)
        if not ok:
            hits.append(
                _syntax_hit(
                    SYNTAX_SCRIPT_PATH,
                    entry.node.pos,
                    _render_justification(context, detail=detail),
                    context=context,
                    owner_entry_id=entry.entry_id,
                )
            )
    return hits


def _script_operand(entry: CommandEntry, source_text: str) -> str | None:
    """取 shell 命令的静态脚本文件操作数（供脚本目录政策使用）；非 shell 返回 ``None``。"""
    invocation = analyze_shell_invocation(entry, source=CommandSource(entry.source_id, None, None, source_text))
    if invocation.kind == "script_path":
        return invocation.target
    return None


# ========== 语法规则 ==========

_REDIRECT_EXEMPT_TYPES = (">", ">>", "&>")
_BRACE_EXPANSION_RE = re.compile(r"\{[^{}]*,[^{}]*\}")


def _root_nodes(result: WalkResult) -> list[Any]:
    """遍历的顶层节点集合：inventory 中记录的语法节点 + 每个实际命令节点。

    只包含遍历器**真正访问过**的节点（``syntax_nodes`` 记录 compound.redirects、
    command 的 parts 与全部 parameter），外加各 entry 的 command 节点，因此不会
    把未被访问的独立 pipeline/wrapper 结构重复计入，也不会漏掉 commandless 重定向。
    """
    roots: list[Any] = []
    seen: set[int] = set()
    for item in result.syntax_nodes:
        if id(item.node) not in seen:
            seen.add(id(item.node))
            roots.append(item.node)
    for entry in result.entries:
        if id(entry.node) not in seen:
            seen.add(id(entry.node))
            roots.append(entry.node)
    return roots


def _entry_name(result: WalkResult, node: Any, source_text: str) -> str | None:
    for entry in result.entries:
        if entry.node is node:
            return entry.name_word.word
    return None


_WORD_DELIMITERS = " \t\n;|&<>()"


def _delimiter_boundaries(source_text: str) -> list[int]:
    """预计算 source 中全部词分隔符的下标（升序），供 O(log n) 词边界查询。

    不变量：对每个 source 只构建一次，边界查询走二分。调用方若改成逐 parameter 重建，
    词边界查询会退化为线性、整体变成二次方——``test_command_ast_limits.py`` 的调用计数
    护栏钉住了「每个 source 只构建一次」。
    """
    return [index for index, char in enumerate(source_text) if char in _WORD_DELIMITERS]


def _scan_span(
    source_text: str, item: Any, pos: tuple[int, int], boundaries: list[int] | None = None
) -> tuple[int, int]:
    """parameter 的有界扫描范围：含所属词但不超过该词右边界。

    行为契约：``owner`` 不在 ``("plain", "double", "single")`` 时退化为
    ``(pos[0] - 1, pos[1])``；``boundaries`` 为 ``None`` 时按本词现建一次（供单测直调）。
    """
    owner = item.context
    start = max(0, pos[0] - 1)
    end = pos[1]
    if owner in ("plain", "double", "single"):
        if boundaries is None:
            boundaries = _delimiter_boundaries(source_text)
        # start：最后一个「位于 pos[0]-1 之前」的分隔符的下一位（无则为 0）。
        left_limit = pos[0] - 1
        last = _last_delimiter_before(boundaries, left_limit)
        start = last + 1 if last is not None else 0
        # end：pos[1] 起第一个分隔符（无则到串尾）。
        nxt = _first_delimiter_at_or_after(boundaries, pos[1])
        end = nxt if nxt is not None else len(source_text)
    return start, end


def _last_delimiter_before(boundaries: list[int], limit: int) -> int | None:
    """返回 ``< limit`` 的最大分隔符下标（无则 ``None``）。"""
    idx = bisect.bisect_left(boundaries, limit) - 1
    return boundaries[idx] if idx >= 0 else None


def _first_delimiter_at_or_after(boundaries: list[int], index: int) -> int | None:
    """返回 ``>= index`` 的最小分隔符下标（无则 ``None``）。"""
    idx = bisect.bisect_left(boundaries, index)
    return boundaries[idx] if idx < len(boundaries) else None


def _brace_expansion_regex_hit(raw: str) -> bool:
    """只在其「同一有效未引用区间」内匹配 ``{`` + 逗号 + ``}``。"""
    return any(_BRACE_EXPANSION_RE.search(segment) for segment in _unquoted_segments(raw))


def _unquoted_segments(raw: str) -> list[str]:
    """把原文按引号状态切分为未引用区段（单引号内容整体丢弃，双引号内容同样不计）。"""
    segments: list[str] = []
    current: list[str] = []
    state = "plain"
    i = 0
    while i < len(raw):
        char = raw[i]
        if state == "plain":
            if char == "\\":
                current.append(" ")
                i += 2
                continue
            if char == "'":
                segments.append("".join(current))
                current = []
                state = "single"
            elif char == '"':
                segments.append("".join(current))
                current = []
                state = "double"
            else:
                current.append(char)
        elif state == "single":
            if char == "'":
                state = "plain"
        elif state == "double":
            if char == "\\":
                i += 2
                continue
            if char == '"':
                state = "plain"
        i += 1
    segments.append("".join(current))
    return segments


def _modeled_substitution_offsets(result: WalkResult) -> set[int]:
    """返回**已由 bashlex 建模**的 substitution 节点开启偏移集合（整 source 一次算好）。

    不变量：零次再解析。已建模的 ``commandsubstitution`` / ``processsubstitution`` 节点在
    :func:`command_parser.walk_nodes` 遍历时即被记录到 ``result.syntax_nodes``，此处只做
    一次集合投影；调用方按整 source 调用一次。
    """
    offsets: set[int] = set()
    for item in result.syntax_nodes:
        if getattr(item.node, "kind", None) not in ("commandsubstitution", "processsubstitution"):
            continue
        pos = getattr(item.node, "pos", None)
        if pos is not None:
            offsets.add(pos[0])
    return offsets


#: 本模块导出的规则规格（9 条 ``syntax:*`` + 1 条 ``ast:*``）。
SYNTAX_RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        rule_id=SYNTAX_BACKGROUND,
        category="syntax",
        verdict="block",
        justification="后台执行符（&）",
        predicate=_syntax_background,
    ),
    RuleSpec(
        rule_id=SYNTAX_PIPE_AMP,
        category="syntax",
        verdict="block",
        justification="|& 操作符",
        predicate=_syntax_pipe_amp,
    ),
    RuleSpec(
        rule_id=SYNTAX_FORBIDDEN_COMMAND,
        category="syntax",
        verdict="block",
        justification="命中无条件禁用命令集",
        pattern=Pattern(tokens=(names(*FORBIDDEN_COMMANDS),)),
        predicate=_syntax_forbidden_command,
        # 样例即「**原始 word** 语义」的可证伪载体：谓词用 ``_entry_name``（不归一化），
        # 故 ``/usr/bin/nohup`` **不**命中。
        match=("nohup x",),
        not_match=("/usr/bin/nohup x",),
    ),
    RuleSpec(
        rule_id=SYNTAX_REDIRECT,
        category="syntax",
        verdict="block",
        justification="重定向操作符（> / >> / < / 2>&1 等）",
        predicate=_syntax_redirect,
    ),
    RuleSpec(
        rule_id=SYNTAX_HEREDOC,
        category="syntax",
        verdict="block",
        justification="Here Document（<<）",
        predicate=lambda context: _syntax_redirect(context, heredoc=True),
    ),
    RuleSpec(
        rule_id=SYNTAX_HERESTRING,
        category="syntax",
        verdict="block",
        justification="Here String（<<<）",
        predicate=lambda context: _syntax_redirect(context, herestring=True),
    ),
    RuleSpec(
        rule_id=SYNTAX_BRACE_EXPANSION,
        category="syntax",
        verdict="block",
        justification="大括号扩展（{{a,b}}）",
        predicate=_syntax_brace_expansion,
    ),
    RuleSpec(
        rule_id=SYNTAX_COMMAND_PATH,
        category="syntax",
        verdict="block",
        justification=JUSTIFICATION_TEMPLATES[SYNTAX_COMMAND_PATH],
        predicate=_syntax_command_path,
    ),
    RuleSpec(
        rule_id=SYNTAX_SCRIPT_PATH,
        category="syntax",
        verdict="block",
        justification=JUSTIFICATION_TEMPLATES[SYNTAX_SCRIPT_PATH],
        predicate=_syntax_script_path,
    ),
    RuleSpec(
        rule_id=AST_UNSUPPORTED_PARAMETER_EXECUTION,
        category="ast",
        verdict="block",
        justification=JUSTIFICATION_TEMPLATES[AST_UNSUPPORTED_PARAMETER_EXECUTION],
        predicate=_ast_unsupported_parameter,
    ),
)

#: ``syntax:forbidden_command`` 的 **pattern**（判定路径的读取点）。
#:
#: 判定必须消费 spec 内容而非 ``command_definitions.FORBIDDEN_COMMANDS`` 常量：常量仅作为字面量
#: 归属地，spec pattern 才是判定真源。方向由本派生决定 —— 改 spec 内容即改行为。
_FORBIDDEN_COMMAND_CONTENT: Pattern = next(
    spec.pattern for spec in SYNTAX_RULES if spec.rule_id == SYNTAX_FORBIDDEN_COMMAND
)

#: 本模块 10 条规则的 rule_id 集合（``enable_command_syntax_rules`` 闸门的判据）。
#:
#: 派发层用它而非 ``spec.category in {"syntax", "ast"}``：``invocation:unsupported``
#: 的调用形态同属解析器能力边界，但由 ``command_blocklist`` 拥有、有独立开关
#: ``enable_command_blocklist_unsupported``；按 category 判定会把它一并吞掉，
#: 使同一条规则受两个开关管辖。集合在此派生，令「模块拥有者 = 开关管辖面」始终一致。
SYNTAX_RULE_IDS: frozenset[str] = frozenset(spec.rule_id for spec in SYNTAX_RULES)
