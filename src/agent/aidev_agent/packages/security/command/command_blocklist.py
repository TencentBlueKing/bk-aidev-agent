# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_blocklist

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

命令黑名单：**AST 上下文谓词**，不做整串正则扫描。

命名契约：本模块即「黑名单」——命中即**硬拒绝**（``verdict="block"``，不可审批）。
与 ``command_allowlist`` 的允许列表（命中即放行）相对；两者都未命中则落入
``command_approval`` 的灰名单审批。故本模块的 ``category`` 值必须全部落在
:data:`BLOCKLIST_CATEGORIES` 内——「block 但不属黑名单族」是语义错位。

十六条 label / category 由本模块的 ``BLOCKLIST_RULES`` 自行定义，不在别处登记。
本模块的判定**只用**下面列出的 AST 上下文，**不调用任何正则**扫描命令。谓词只使用：

- 命令节点的**命令名位置**（经已建模 ``sudo`` 视图得到的内层命令名）；
- 该命令**自身的参数 word**（引号剥离后的字面值或原文 token）；
- walker 提供的**真实 pipeline stage 关系**（仅用于两条 remote_exec 规则）。

因此 ``grep -r "rm -rf"`` / ``cat /etc/token`` 这类「危险词出现在普通参数里」的
形状不再命中；而 ``curl http://x | cat /etc/token`` 也**不再**命中
``exfil_curl_token``（该职责由管道相邻规则 ``curl_pipe_shell`` / ``wget_pipe_shell``
承担，两者不得混用）。

本模块只依赖 ``command_parser``（节点/来源/pipeline 关系）与结果模型，
不 import ``core`` / ``services`` / ``api``。

**定义顺序约定**：函数**自底向上**排列——被调用者先于调用者定义。任何函数只引用
它**上方**已定义的名字，使依赖链单向向下可追溯，也避免「先引用后定义」在 import
期的隐式时序假设。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .command_definitions import (
    JUSTIFICATION_TEMPLATES,
    Pattern,
    RuleContext,
    RuleHit,
    RulePredicate,
    RuleSpec,
    data_predicate_for,
    names,
    render_justification,
)
from .command_parser import (
    CommandEntry,
    WalkResult,
    _literal_args,
    analyze_shell_invocation,
    classify_word,
    effective_command_args,
    effective_command_name,
)

# ========== 各标签的静态判定集合 ==========

_MKFS_RE = re.compile(r"mkfs(?:\..+)?$")
#: 防火墙命令名集合（``firewall_change`` 的名单来源；判定条件是 ``requires_any_flag``）。
_FIREWALL: frozenset[str] = frozenset({"iptables", "ufw"})
#: 包管理器名字集合（``package_install`` 的名单来源）。
#:
#: **``pip`` 族刻意不在内**：``pip`` / ``pip3`` / ``pip3.11`` 是**数字后缀族**
#: （``pip[0-9.]*``），``Pattern`` 表达不了后缀通配，故该族由代码谓词
#: ``_danger_pip_package_install`` 承担（见 ``_PIP_RE``）。
_PACKAGE_MANAGERS = frozenset({"apt", "apt-get", "yum", "dnf", "conda"})
_PIP_RE = re.compile(r"pip[0-9.]*")
_PACKAGE_VERBS = frozenset({"install", "uninstall", "remove", "upgrade", "update"})
#: ``package_install`` 位置定位时**额外**跳过的 token 集合（``apt`` 的静默/无输出选项）。
#:
#: **必须精确列举**：``_positional_operand`` 对**任何** ``-`` 开头的 token 都会跳过，
#: 故未列举的**带值**选项（如 ``-o``）的值会占住操作数位。实测
#: ``apt -o X install vim`` **不命中**是既有行为。
_PACKAGE_SKIP_FLAGS: frozenset[str] = frozenset({"-y", "--yes", "-q", "--quiet"})

# ``chmod`` / ``chown`` 的位置定位**不需要**自己的跳过集：``_positional_operand``
# 对任何 ``-`` 开头的 token 一律跳过（那是一切 flag 的超集），而 chmod/chown 唯一的
# **带值**选项 ``--reference`` 在该函数开头单独处理（它有「无 ``=`` 时多吞一格」的
# 特例语义）。故这两个命令的操作数定位直接复用公共实现，无需额外列举选项。

_SHELL_NAMES = frozenset({"sh", "bash", "zsh"})
#: ``exfil_curl_token`` 的敏感值子串（参数内任意位置命中）。
_TOKEN_RE = re.compile(r"(?:token|secret|password|authorization|api-?key)", re.IGNORECASE)
#: ``dd_disk_write`` 的裸磁盘目标（``of=/dev/<disk>``）。
_DEV_DISK_RE = re.compile(r"of=/dev/(?:sd|vd|hd|nvme|mmcblk|xvd)")
#: ``python_module_package_install`` 的模块名（``python -m pip`` / ``-mpip`` 的取值）。
_PIP_MODULE_RE = re.compile(r"(?:pip[0-9.]*|ensurepip|easy_install)")

# 未建模执行包装器 —— 这些命令**本身不是危险命令**，但它们把「要真正执行的
# 内容」当作参数/子命令传入（``xargs rm -rf`` / ``env A=1 rm -rf /`` / ``eval "…"``），
# 内层调用不在 AST 建模范围内。归类为动态执行内容（默认 block，可配 review）。
UNMODELED_EXECUTION_WRAPPERS: frozenset[str] = frozenset(
    {"env", "nice", "ionice", "timeout", "stdbuf", "command", "builtin", "exec", "xargs", "su", "eval", "source", "."}
)


# ========== 包管理判定 ==========


def _PACKAGE_MANAGERS_FULL(name: str) -> bool:  # noqa: N802  (保持与集合常量同名可读性)
    return name in _PACKAGE_MANAGERS


def _is_package_install(name: str, args: list[str]) -> bool:
    """包管理器安装/卸载类操作（已知前缀选项 ``-y/--yes/-q/--quiet`` 之外的选项一律不命中）。"""
    if not (_PACKAGE_MANAGERS_FULL(name) or _PIP_RE.fullmatch(name)):
        return False
    for token in args:
        if token in ("-y", "--yes", "-q", "--quiet"):
            continue
        if token.startswith("-"):
            return False
        return token in _PACKAGE_VERBS
    return False


def _python_module_install(entry: CommandEntry, source_text: str) -> bool:
    """``python[0-9.]*`` + ``-m`` / ``-mpip`` 指向包管理模块。"""
    name = classify_word(entry.name_word, source_text)
    if name.kind != "static" or not re.fullmatch(r"python[0-9.]*", name.text):
        return False
    values = [classify_word(word, source_text) for word in entry.argument_words]
    index = 0
    while index < len(values):
        if values[index].kind != "static":
            return False
        token = values[index].text
        if token in ("-u", "-B", "-E", "-s", "-S", "-I"):
            index += 1
            continue
        if token == "-m":
            return index + 1 < len(values) and bool(_PIP_MODULE_RE.fullmatch(values[index + 1].text))
        if token.startswith("-m") and len(token) > 2:
            return bool(_PIP_MODULE_RE.fullmatch(token[2:]))
        return False
    return False


# ========== pipeline 相邻 stage 辅助 ==========


def _entry_by_id(result: WalkResult, entry_id: int) -> CommandEntry | None:
    for entry in result.entries:
        if entry.entry_id == entry_id:
            return entry
    return None


def _stage_command_names(result: WalkResult, entry_ids: list[int], source_text: str) -> set[str]:
    """按 stage 的可能 entry 集合取静态命令名集合（不含内嵌 pipeline/替换/函数体）。"""
    names: set[str] = set()
    for entry_id in entry_ids:
        entry = _entry_by_id(result, entry_id)
        if entry is None:
            continue
        name = classify_word(entry.name_word, source_text)
        if name.kind == "static":
            names.add(name.text)
    return names


def _pipeline_span(pipeline: Any) -> tuple[int, int]:
    stages = pipeline.stages
    if not stages:
        return (0, 0)
    return (stages[0].pos[0], stages[-1].pos[1])


# ========== 命中构造（身份取自 context.spec） ==========


def _hit_for_spec(
    spec: Any | None, entry: Any, *, reason: str | None = None, span: tuple[int, int] | None = None
) -> RuleHit:
    """按**本轮求值的 spec** 构造一条危险规则命中（身份从 ``context.spec`` 取）。

    谓词**自知其 spec**：``command_security._evaluate_rules`` 逐条把 ``spec`` 注入
    ``RuleContext``（见 :attr:`RuleContext.spec`），故谓词无需、也不得反查任何
    ``label -> spec`` 全局表——那样的表会让
    ``命中构造 → 全局表 → BLOCKLIST_RULES → 谓词 → 命中构造`` 构成**定义期循环**
    （只因构造期不调用谓词而侥幸不炸）。

    与既有惯例一致：同样从 ``context.spec`` 读自己的 content，而非模块级快照。

    ``spec`` 为 ``None``（谓词单测直接构造 ``RuleContext``）时回落保守值：``rule_id``
    取空串、``category`` 取 ``None``、``reason`` 取空串——不抛异常，因为这只在测试
    路径发生，且调用方读的 ``rule_id`` 通常另有来源。

    ``verdict`` 固定 ``"block"``（16 条危险规则一律 forbidden）。
    ``span`` 缺省取 ``entry.node.pos``——危险规则都归属某条命令，位置即该命令。
    """
    return RuleHit(
        rule_id=getattr(spec, "rule_id", "") or "",
        verdict="block",
        reason=reason if reason is not None else (getattr(spec, "justification", "") or ""),
        category=getattr(spec, "category", None),
        owner_entry_id=getattr(entry, "entry_id", None),
        span=span if span is not None else entry.node.pos,
    )


# 判定条件是实现细节（参数内子串正则 / 跨 entry 关系 / argv 结构），无法由
# ``Pattern`` 表达，故各自手写谓词。它们与数据谓词**同构**：消费同一个
# ``RuleContext``、产出同一个 ``RuleHit``，故统一派发层无需区分两者。
#
# 名字取 ``effective_command_name``（唯一归一化路径，含 ``sudo`` 内层视图），
# 参数取 ``_literal_args``。
#
# **``package_install`` 的 ``pip`` 族补充谓词**：
# 该规则的名字集合含 ``pip[0-9.]*`` **数字后缀族**，``Pattern`` 表达不了后缀通配，
# 故该族**必须**由代码谓词补上，否则 ``pip3 install x`` 从不命中。其余部分
# （``apt`` / ``apt-get`` / … + 动词位置 token）由该规则的 ``pattern`` 承担。


def _resolved_name(entry: Any, walked: WalkResult) -> str | None:
    """规范化后的实际命令名；动态命令名不 normalize / 不查静态名单。

    委托 ``command_parser.effective_command_name`` —— 命令名解析只有这一份实现
    （唯一真源），允许列表与黑名单规则共用同一个已建模 ``sudo`` 视图，避免两套视图漂移。
    """
    return effective_command_name(entry, walked.source.text)


def _spec_justification(context: RuleContext, **values: object) -> str:
    """从 ``context.spec.justification``（模板）渲染本规则的原因文案。

    ``context.spec`` 为 ``None``（谓词单测直接构造 ``RuleContext``）时回落空串——
    生产路径永远带 spec（``_evaluate_rules`` 逐条传入）。
    """
    template = getattr(context.spec, "justification", None)
    if template is None:
        return ""
    return render_justification(template, **values)


# ========== 危险规则代码谓词 ==========


def _danger_mkfs(context: RuleContext) -> Sequence[RuleHit]:
    """``mkfs_format``：``mkfs.<fs>`` 形态或特殊名 ``format``。"""
    entry = context.entry
    if entry is None:
        return ()
    name = effective_command_name(entry, context.walked.source.text)
    if name is not None and (_MKFS_RE.fullmatch(name) or name == "format"):
        return (_hit_for_spec(context.spec, entry),)
    return ()


def _danger_pip_package_install(context: RuleContext) -> Sequence[RuleHit]:
    """``package_install`` 的 **``pip`` 族补充**：``pip`` / ``pip3`` / ``pip3.11`` + 动词。

    该规则的名字集合搬进了 ``Pattern``，但 ``pip[0-9.]*`` 是数字后缀族，``Pattern``
    无法表达。本谓词只负责该族——它与 ``pattern`` 取**并集**，等于原单一代码谓词的判据，
    故命中面不退化。

    动词判定与 ``_is_package_install`` 共用同一实现（**不写第二份**），
    区别只在名字判据由 ``_PIP_RE`` 收窄为 pip 族。
    """
    entry = context.entry
    if entry is None:
        return ()
    source_text = context.walked.source.text
    name = effective_command_name(entry, source_text)
    if name is None or not _PIP_RE.fullmatch(name):
        return ()
    if _is_package_install(name, _literal_args(entry, source_text)):
        return (_hit_for_spec(context.spec, entry),)
    return ()


def _danger_dd(context: RuleContext) -> Sequence[RuleHit]:
    """``dd_disk_write``：``dd`` 且参数里有 ``of=/dev/<disk>``。"""
    entry = context.entry
    if entry is None:
        return ()
    source_text = context.walked.source.text
    name = effective_command_name(entry, source_text)
    if name is None:
        return ()
    args = _literal_args(entry, source_text)
    if name == "dd" and any(_DEV_DISK_RE.search(arg) for arg in args):
        return (_hit_for_spec(context.spec, entry),)
    return ()


def _danger_exfil_curl_token(context: RuleContext) -> Sequence[RuleHit]:
    """``exfil_curl_token``：``curl`` 且参数里有 token/secret 等敏感值。"""
    entry = context.entry
    if entry is None:
        return ()
    source_text = context.walked.source.text
    name = effective_command_name(entry, source_text)
    if name is None:
        return ()
    args = _literal_args(entry, source_text)
    if name == "curl" and any(_TOKEN_RE.search(arg) for arg in args):
        return (_hit_for_spec(context.spec, entry),)
    return ()


def _danger_python_module_package_install(context: RuleContext) -> Sequence[RuleHit]:
    """``python_module_package_install``：``python -m pip install`` 的 argv 结构。"""
    entry = context.entry
    if entry is None:
        return ()
    if _python_module_install(entry, context.walked.source.text):
        return (_hit_for_spec(context.spec, entry),)
    return ()


def _pipeline_hits(context: RuleContext, *, downloader: str) -> Sequence[RuleHit]:
    """pipeline 相邻 stage 规则的统一实现（``curl_pipe_shell`` / ``wget_pipe_shell``）。

    产出**结构明细**（``owner_entry_id is None``）——pipeline 关系不属于任何单条命令，
    故 span 取整条 pipeline 的范围。

    身份（rule_id / category / justification）从 ``context.spec`` 取（谓词自知其 spec），
    不查任何全局表——理由见 :func:`_hit_for_spec`。

    依赖的 ``_stage_command_names`` / ``_pipeline_span`` 定义在本文件更靠后处：谓词体
    只在**调用期**解析它们，故定义顺序无碍（这也是谓词能住在本模块的原因）。
    """
    result = context.walked
    hits: list[RuleHit] = []
    source_text = result.source.text
    for pipeline in result.pipelines:
        stage_names = [_stage_command_names(result, ids, source_text) for ids in pipeline.stage_entries]
        for left, right in zip(stage_names, stage_names[1:]):
            if downloader in left and right & _SHELL_NAMES:
                hits.append(_hit_for_spec(context.spec, None, span=_pipeline_span(pipeline)))
    return hits


def _danger_curl_pipe_shell(context: RuleContext) -> Sequence[RuleHit]:
    """``curl_pipe_shell``：``curl ... | sh`` 的相邻 stage 关系（产出结构明细）。"""
    return _pipeline_hits(context, downloader="curl")


def _danger_wget_pipe_shell(context: RuleContext) -> Sequence[RuleHit]:
    """``wget_pipe_shell``：``wget ... | bash`` 的相邻 stage 关系（产出结构明细）。"""
    return _pipeline_hits(context, downloader="wget")


# ========== 规则身份与派生辅助 ==========


def _rule_name_of(entry: Any, context: RuleContext) -> str | None:
    return effective_command_name(entry, context.walked.source.text)


def _rule_args_of(entry: Any, context: RuleContext) -> list[str]:
    return _literal_args(entry, context.walked.source.text)


def _make_rule_resolver(spec: RuleSpec) -> RulePredicate:
    """数据规则的**谓词构造器**：给一条 spec，从它的 ``pattern`` 派生谓词。

    这是本模块作为「危险规则拥有者」对 :meth:`RuleSpec.resolve_predicate` 的注入实现
    （:data:`RuleResolver` 形状：``spec -> RulePredicate``）。

    **``verdict`` 取自 ``spec.verdict``，绝不硬编码**：调用点（``BLOCKLIST_RULES`` 的
    容器字面量）与本函数都只写一次「判定从哪来」——忘写 verdict 在结构上不可能。
    历史缺陷是派生路径写死 ``"block"``：本模块 16 条规则恰好全是 ``block``，故缺陷
    潜伏；任何 ``allow`` / ``review`` 规则接上这条路径都会被静默翻成 ``block``。

    归一化口径**复用本模块既有的** :func:`_rule_name_of` / :func:`_rule_args_of`
    （二参 ``(entry, context)`` 契约，不是 ``effective_command_name`` 的
    ``(entry, source_text)``）——单一真源，不在本模块或聚合点另立第二份。

    ``assert`` 守卫：调用点只在 ``self.pattern is not None`` 时调到本函数
    （见 :meth:`RuleSpec.resolve_predicate`），故 ``spec.pattern is not None`` 恒成立；
    ``assert`` 与 :meth:`RuleSpec.resolve_predicate` 的加载期自检同风格
    （该路径在模块导入期即执行）。
    """
    assert spec.pattern is not None, f"规则 {spec.rule_id!r} 无 pattern，不应走数据谓词派生"
    return data_predicate_for(
        spec.pattern,
        rule_id=spec.rule_id,
        reason=spec.justification,
        verdict=spec.verdict,
        category=spec.category,
        name_of=_rule_name_of,
        args_of=_rule_args_of,
    )


def _pip_family_complement(spec: RuleSpec) -> RulePredicate:
    """``package_install`` 的**补充谓词构造器**：补上 ``Pattern`` 表达不了的 pip 族。

    该规则的名字集合含 ``pip[0-9.]*`` **数字后缀族**，``Pattern`` 无此后缀通配语义，
    故该族**必须**由代码谓词补上，否则 ``pip3 install x`` 静默不再命中。
    该谓词与 ``pattern`` 取**并集**，等于原单一代码谓词的判据。

    收 ``spec`` 而（当前）不使用它：签名与 :data:`RuleSpec.resolve_predicate` 的
    ``extra`` 契约一致，将来若该族需按 spec 定制（如读 ``spec.pattern``）无需改签名。
    """
    del spec  # 暂未使用；保留入参以匹配 extra 契约
    return _danger_pip_package_install


# ========== 公开入口 ==========


def unmodeled_execution_wrapper_names(result: WalkResult) -> list[str]:
    """返回本 source 中命中「未建模执行包装器」的**规范化命令名**（去重、保序）。

    供 ``command_security._invocation_structure`` 按动态执行策略归类
    （默认 block，可配 review）。仅识别经规范化（``/bin/xargs`` → ``xargs``）后的
    精确命令名；不猜测包装器选项 schema。
    """
    names: list[str] = []
    for entry in result.entries:
        name = effective_command_name(entry, result.source.text)
        if name is not None and name in UNMODELED_EXECUTION_WRAPPERS and name not in names:
            names.append(name)
    return names


# ========== 参数限制（``args:restricted`` 的判据来源）==========

#: uname 仅允许的参数集合（``""`` 表示允许无参数）。
_UNAME_ALLOWED_FLAGS: frozenset[str] = frozenset({"", "-s", "-v"})

#: df 仅允许的参数集合。
_DF_ALLOWED_FLAGS: frozenset[str] = frozenset({"", "-h"})


@dataclass(frozen=True)
class AllowedFlagsOnly:
    """参数限制：**只允许**列出的 flag，其余 ``-`` 开头的参数一律拒绝。

    允许列表式（fail-closed）是**唯一**保留的策略：黑名单式（禁掉列出的 flag）有结构性
    缺陷——禁 ``-a`` 却漏 ``--all`` 就等于没禁，而漏报在这里等于放行。允许列表式天然
    不会漏：没列出的就是不允许。

    非 flag 参数（不以 ``-`` 开头，如 ``df /tmp`` 的 ``/tmp``）一律放行——本类型只管
    选项。空串 ``""`` 在 ``flags`` 里表示「允许无参数」。
    """

    flags: frozenset[str]
    """允许的 flag 集合；``""`` 表示允许无参数（即纯非 flag 参数场景）。"""

    def is_allowed(self, args: list[str]) -> tuple[bool, str]:
        """检查参数是否符合限制；返回 ``(是否允许, 拒绝原因)``。"""
        for arg in args:
            # 非标志参数（不以 - 开头）一律放行
            if not arg.startswith("-"):
                continue
            # 长选项如 --help 不在允许列表中则拒绝
            if arg not in self.flags:
                return False, f"不允许使用参数 '{arg}'"
        return True, ""


#: 命令参数限制映射。
#:
#: 唯一消费者是 ``args:restricted`` 规则（允许列表只判名字维度、不检查参数）。
PARAMETER_RESTRICTIONS: dict[str, AllowedFlagsOnly] = {
    "uname": AllowedFlagsOnly(flags=_UNAME_ALLOWED_FLAGS),
    "df": AllowedFlagsOnly(flags=_DF_ALLOWED_FLAGS),
}


def _args_restricted_hits(context: RuleContext) -> Sequence[RuleHit]:
    """``args:restricted``：命令命中参数限制表且参数不合规。

    参数取 :func:`command_parser.effective_command_args`——与名字解析**同属一个内层
    视图**（``sudo df -h`` 取内层参数），否则 ``sudo`` 视图下参数限制会被 wrapper
    自身参数掩盖。

    **与 ``allowlist:allowed`` 的关系**：本谓词只判「参数维度」，允许列表只判「名字维度」，    两者可对同一条命令**同时产出**——``uname -z`` 既是 ``allowlist:allowed``(allow)
    （名字确在允许列表）也是本规则的 block（参数确越界）。聚合层 ``strictest`` 按
    block > review > allow 得该 finding 的唯一 verdict=block。
    """
    entry = context.entry
    if entry is None:
        return ()
    name = _resolved_name(entry, context.walked)
    if name is None:
        return ()
    restriction = PARAMETER_RESTRICTIONS.get(name)
    if restriction is None:
        return ()
    ok, detail = restriction.is_allowed(effective_command_args(entry, context.walked.source.text))
    if ok:
        return ()
    return (
        RuleHit(
            rule_id=ARGS_RESTRICTED,
            verdict="block",
            reason=_spec_justification(context, name=name, detail=detail),
            # category 取自 spec（而非硬编码）：spec.category 是「命中属于哪个类别」的
            # 唯一真源。硬编码会让 spec 的 category 沦为装饰——改 spec 不生效。
            category=getattr(context.spec, "category", None) or "system_state",
            owner_entry_id=entry.entry_id,
            span=entry.node.pos,
        ),
    )


#: 参数限制的 rule_id 常量（本模块拥有其规则，故字面量归属此）。
ARGS_RESTRICTED = "args:restricted"


#: 本模块导出的 16 条危险规则规格（rule_id == label）。
#:
#: 顺序即报告里的命中优先级顺序。每条就地用 :meth:`RuleSpec.resolve_predicate` 定值
#: 谓词：可字面化者由 ``pattern`` 派生（``package_install`` 另并入补充面），
#: 不可字面化者用自带的代码谓词，理由写在其条目上方的注释里。
BLOCKLIST_RULES: tuple[RuleSpec, ...] = (
    # ---- 1. 递归强制删除：命令 + flag ----
    RuleSpec(
        rule_id="rm_recursive_force",
        category="data_destruction",
        verdict="block",
        justification="命中危险命令规则 rm_recursive_force",
        pattern=Pattern(tokens=("rm", names("-rf", "-fr"))),
        match=("rm -rf /tmp",),
        not_match=("rm /tmp",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 2. rm 命令整体禁用：纯命令名（不看参数）----
    RuleSpec(
        rule_id="rm_forbidden",
        category="data_destruction",
        verdict="block",
        justification="命中危险命令规则 rm_forbidden",
        pattern=Pattern(tokens=("rm",)),
        match=("rm /tmp",),
        not_match=("rmx /tmp",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 3. 格式化文件系统（不可字面化：需正则 mkfs(\..+)?$ 与特殊名 format）----
    RuleSpec(
        rule_id="mkfs_format",
        category="data_destruction",
        verdict="block",
        justification="命中危险命令规则 mkfs_format",
        predicate=_danger_mkfs,
    ),
    # ---- 4. 关机 / 重启 / 停机：纯命令名集合 ----
    RuleSpec(
        rule_id="shutdown_reboot",
        category="system_state",
        verdict="block",
        justification="命中危险命令规则 shutdown_reboot",
        pattern=Pattern(tokens=(names("halt", "poweroff", "reboot", "shutdown"),)),
        match=("reboot",),
        not_match=("ls",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 5. 权限置 777：命令 + 第 0 个位置参数精确相等 ----
    RuleSpec(
        rule_id="chmod_777",
        category="privilege",
        verdict="block",
        justification="命中危险命令规则 chmod_777",
        pattern=Pattern(tokens=("chmod",), positional_index=0, positional_equals=frozenset({"777"})),
        match=("chmod 777 /tmp/x",),
        not_match=("chmod 644 /tmp/x",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 6. 用户与口令管理：纯命令名集合 ----
    RuleSpec(
        rule_id="user_management",
        category="privilege",
        verdict="block",
        justification="命中危险命令规则 user_management",
        pattern=Pattern(tokens=(names("adduser", "passwd", "useradd", "usermod", "visudo"),)),
        match=("useradd bob",),
        not_match=("useraddx bob",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 7. 防火墙变更：名字集合 + 「存在任意 - 开头参数」 ----
    RuleSpec(
        rule_id="firewall_change",
        category="system_state",
        verdict="block",
        justification="命中危险命令规则 firewall_change",
        pattern=Pattern(tokens=(names(*sorted(_FIREWALL)),), requires_any_flag=True),
        match=("iptables -F",),
        not_match=("iptables",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 8. 包安装：名字集合 + 动词位置 token（pip 族另由 _pip_family_complement 补）----
    RuleSpec(
        rule_id="package_install",
        category="package_management",
        verdict="block",
        justification="命中危险命令规则 package_install",
        pattern=Pattern(
            tokens=(names(*sorted(_PACKAGE_MANAGERS)),),
            positional_index=0,
            positional_equals=frozenset(_PACKAGE_VERBS),
            skip_flags=_PACKAGE_SKIP_FLAGS,
        ),
        match=("apt-get install x",),
        not_match=("apt-get removey x",),
    ).resolve_predicate(resolver=_make_rule_resolver, extra=_pip_family_complement),
    # ---- 9. curl 管道到 shell（不可字面化：需 pipeline stage 相邻性）----
    RuleSpec(
        rule_id="curl_pipe_shell",
        category="remote_exec",
        verdict="block",
        justification="curl 输出直接管道到 shell 解释器（下载即执行）",
        predicate=_danger_curl_pipe_shell,
    ),
    # ---- 10. wget 管道到 shell（不可字面化：需 pipeline stage 相邻性）----
    RuleSpec(
        rule_id="wget_pipe_shell",
        category="remote_exec",
        verdict="block",
        justification="wget 输出直接管道到 shell 解释器（下载即执行）",
        predicate=_danger_wget_pipe_shell,
    ),
    # ---- 11. dd 写裸磁盘（不可字面化：需参数内正则 of=/dev/(...)）----
    RuleSpec(
        rule_id="dd_disk_write",
        category="data_destruction",
        verdict="block",
        justification="命中危险命令规则 dd_disk_write",
        predicate=_danger_dd,
    ),
    # ---- 12. shred 覆写：纯命令名 ----
    RuleSpec(
        rule_id="shred_file",
        category="data_destruction",
        verdict="block",
        justification="命中危险命令规则 shred_file",
        pattern=Pattern(tokens=("shred",)),
        match=("shred /tmp/x",),
        not_match=("shredx",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 13. curl 携带敏感值外发（不可字面化：需参数内子串正则）----
    RuleSpec(
        rule_id="exfil_curl_token",
        category="exfiltration",
        verdict="block",
        justification="命中危险命令规则 exfil_curl_token",
        predicate=_danger_exfil_curl_token,
    ),
    # ---- 14. 属主改 root：命令 + 位置参数（剥 :group）----
    RuleSpec(
        rule_id="chown_root",
        category="privilege",
        verdict="block",
        justification="命中危险命令规则 chown_root",
        pattern=Pattern(
            tokens=("chown",),
            positional_index=0,
            positional_equals=frozenset({"root"}),
            strip_colon=True,
        ),
        match=("chown root /tmp/x",),
        not_match=("chown bob /tmp/x",),
    ).resolve_predicate(resolver=_make_rule_resolver),
    # ---- 15. python -m pip 安装（不可字面化：需解析 argv 结构）----
    RuleSpec(
        rule_id="python_module_package_install",
        category="package_management",
        verdict="block",
        justification="命中危险命令规则 python_module_package_install",
        predicate=_danger_python_module_package_install,
    ),
    # ---- 16. 参数越界：命令名合法但参数不合规（不可字面化：需查参数限制表）----
    RuleSpec(
        rule_id=ARGS_RESTRICTED,
        category="system_state",
        verdict="block",
        justification=JUSTIFICATION_TEMPLATES[ARGS_RESTRICTED],
        predicate=_args_restricted_hits,
    ),
)


# 每条规则的「为何不可字面化」写在对应条目的上方注释里。
# 本模块是数据模块，不跑导入期不变量自检：谓词/样例/占位符等校验收拢在聚合点
# ``command_security`` 调用的 ``command_rule_validation.assert_rule_invariants``
# ——只有那里同时看得见规则全集与
# ``command_definitions`` 的模板表，本模块无法判定跨模块完备性。


#: 黑名单**族类别**（六个）。
#:
#: 这是本模块拥有的标签的**类别分类法**；供拒绝文案归因（判定某条命中是否属于
#: 「已知危险」语义）。以字面量列出而非派生，使 taxonomy 成为显式契约。
#:
#: **不变量（见 ``command_rule_validation.assert_rule_invariants``）**：
#:
#: - ``BLOCKLIST_CATEGORIES ⊆ block 类规则的 category 集合``——本族必为 block，
#:   绝不是 allow 放行项；
#: - 凡 block 类规则必属 :data:`ALL_BLOCKLIST_RULES`——**都是黑名单形态**；
#: - 但反向不成立：本族的成员是「**已知危险**」；而
#:   :data:`DYNAMIC_BLOCKLIST_RULES` / :data:`INVOCATION_BLOCKLIST_RULES` 是
#:   「**无法判定**」（执行内容静态不可知 / 调用形态未建模）——它们同样是 blocklist
#:   形态、同样硬拒，但理由不是「命令危险」，故 category 不在本集合内。
#:   （``syntax`` / ``ast`` 两类同属「无法判定」，但住在 ``command_syntax_rules``、
#:   不在本模块内。）
#:
#: 区分这两者的实际意义：``enable_command_blocklist`` 开关按 category 判定，
#: 只应关掉「已知危险」族；「无法判定」类属结构防线，不受业务开关管辖。
BLOCKLIST_CATEGORIES: frozenset[str] = frozenset(
    {
        "data_destruction",
        "exfiltration",
        "privilege",
        "system_state",
        "remote_exec",
        "package_management",
    }
)


# ========== 已知危险之外的两种黑名单形态 ==========
#
# ``BLOCKLIST_RULES`` 收录的是「**已知危险**」——命中理由有实据：命令确实危险
# （``rm -rf`` 会删盘）或参数确已越界（``uname -a`` 收集系统信息）。
# 以下集合同样是**黑名单形态**（命中即硬拒、不可审批），但打回理由不是「危险」
# 而是「**无法判定**」：
#
# - ``DYNAMIC_BLOCKLIST_RULES`` —— 执行内容静态不可知（category ``dynamic``）；
# - ``INVOCATION_BLOCKLIST_RULES`` —— 调用形态未被 shell adapter 建模（category ``invocation``）。
#
# 两者 category 刻意**不**入 ``BLOCKLIST_CATEGORIES``——「解析失败」不该被说成
# 「命中危险命令」，也不该被业务开关关掉（业务开关只应管「已知危险」）。


# ---------- 无法判定类（两种）----------


def _dynamic_execution_content_hits(context: RuleContext) -> Sequence[RuleHit]:
    """``dynamic:execution_content``：动态执行内容的**全部三个面**。

    - **entry 面**：命令名本身动态（含替换 / 变量）——归属该 entry；
    - **结构面（解释器内联代码）**：``python -c`` / ``perl -e`` 等；
    - **结构面（未建模包装器）**：``eval`` / ``source`` / ``xargs`` / ``env`` 等。

    三者的 verdict 都取自 ``context.dynamic_execution_policy``（规则层 override
    优先于该字段）——故本规则的 block 是**策略可调**的，不是固有属性。
    合并成一个谓词是**正确的**：它们本就是同一条规则的三个触发面，
    拆成两条 spec 反而会让平台配置只能改到一半。
    """
    entry = context.entry
    if entry is not None:
        # entry 面：命令名动态（含替换 / 变量）。
        if classify_word(entry.name_word, context.walked.source.text).kind != "static":
            return (
                RuleHit(
                    rule_id=DYNAMIC_EXECUTION_CONTENT,
                    verdict=context.dynamic_execution_policy,  # type: ignore[arg-type]
                    reason=_spec_justification(context, name=entry.name_word.word),
                    category="dynamic",
                    owner_entry_id=entry.entry_id,
                    span=entry.node.pos,
                ),
            )
        return ()

    # 结构面：只在 source 粒度（entry=None）产出，避免与 entry 面重复计数。
    hits: list[RuleHit] = []
    wrapper_names = set(unmodeled_execution_wrapper_names(context.walked))
    for candidate in context.walked.entries:
        invocation = analyze_shell_invocation(candidate, source=context.walked.source)
        if (
            invocation.kind in ("dynamic", "interpreter_code")
            or _resolved_name(candidate, context.walked) in wrapper_names
        ):
            hits.append(
                RuleHit(
                    rule_id=DYNAMIC_EXECUTION_CONTENT,
                    verdict=context.dynamic_execution_policy,  # type: ignore[arg-type]
                    reason=_spec_justification(context, name=candidate.name_word.word),
                    category="dynamic",
                    owner_entry_id=None,
                    span=candidate.node.pos,
                )
            )
    return hits


def _invocation_unsupported_hits(context: RuleContext) -> Sequence[RuleHit]:
    """``invocation:unsupported``：shell 调用形态已解析但执行语义未建模（结构明细）。"""
    hits: list[RuleHit] = []
    for entry in context.walked.entries:
        invocation = analyze_shell_invocation(entry, source=context.walked.source)
        if invocation.kind == "unsupported":
            hits.append(
                RuleHit(
                    rule_id=INVOCATION_UNSUPPORTED,
                    verdict="block",
                    reason=_spec_justification(context, name=entry.name_word.word, detail=invocation.detail),
                    category="invocation",
                    owner_entry_id=None,
                    span=entry.node.pos,
                )
            )
    return hits


#: 动态执行内容的 rule_id 常量（本模块拥有其规则，故字面量归属此）。
DYNAMIC_EXECUTION_CONTENT = "dynamic:execution_content"

#: ``invocation:unsupported`` 的 rule_id 常量。
INVOCATION_UNSUPPORTED = "invocation:unsupported"

#: 动态执行类黑名单：执行内容**静态不可知**（含解释器内联代码 / 未建模包装器）。
#:
#: verdict 取自 ``dynamic_execution_policy``，可为 block 或 review——platform 可调。
#: category ``dynamic`` 刻意不在 ``BLOCKLIST_CATEGORIES`` 内：理由不是「危险」，
#: 而是「无法判定」。规则可由平台单独处置（关闭 / 替换）。
DYNAMIC_BLOCKLIST_RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        rule_id=DYNAMIC_EXECUTION_CONTENT,
        category="dynamic",
        verdict="block",
        justification=JUSTIFICATION_TEMPLATES[DYNAMIC_EXECUTION_CONTENT],
        predicate=_dynamic_execution_content_hits,
    ),
)

#: 解析边界类黑名单：调用形态已解析但**执行语义未建模**。
#:
#: category ``invocation`` 不在 ``BLOCKLIST_CATEGORIES`` 内——这是解析器的能力边界
#: （解不了的形态不敢放行），不是「命令危险」。与 ``syntax`` 的区别：``syntax`` 说的是
#: **语法结构被禁**（结构本身已被 bashlex 建模，是主动禁止），``invocation`` 说的是
#: **调用形态未被本 SDK 的 argv adapter 建模**（脚本位置无法确定）。
INVOCATION_BLOCKLIST_RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        rule_id=INVOCATION_UNSUPPORTED,
        category="invocation",
        verdict="block",
        justification=JUSTIFICATION_TEMPLATES[INVOCATION_UNSUPPORTED],
        predicate=_invocation_unsupported_hits,
    ),
)

#: 本模块导出的**全部**黑名单规则（各形态的并集）。
#:
#: ``command_security`` 据此汇总规则全集；「凡已知危险类 block 规则必属本集合」是
#: 导入期不变量，保证没有危险命令规则游离在黑名单机制之外。
ALL_BLOCKLIST_RULES: tuple[RuleSpec, ...] = (
    *BLOCKLIST_RULES,
    *DYNAMIC_BLOCKLIST_RULES,
    *INVOCATION_BLOCKLIST_RULES,
)
