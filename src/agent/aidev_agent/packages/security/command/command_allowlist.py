# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_allowlist

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

命令允许列表数据表（纯数据，无算法）。

集中维护允许列表命令集合，以及本模块**自己拥有**的规则规格。

**本模块只判定「名字维度」**：命令名在不在允许列表。参数是否合法归
``command_blocklist`` 的 ``args:restricted``；两条规则可对同一命令同时产出，
聚合层 ``strictest`` 按 block > review > allow 得出唯一 verdict。

这样切分的理由是避免跨维度依赖：若本模块也管参数，它就得持有参数限制表，
而「名字在允许列表」这个事实本身与参数无关。

归属约定：数据模块拥有自己的规则内容（命令名集合）并导出 ``*_RULES``；
基础定义模块（``command_definitions``）只提供 :class:`RuleSpec` 类型与生效机制，
**不拥有具体规则**。本模块依赖它的**类型**（``RuleSpec``）与内容形状（``Pattern``），
不反向依赖它们取内容——反向取内容会让依赖成环，并使「谁的规则内容归谁」重新变成两处。
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Sequence

from .command_definitions import (
    JUSTIFICATION_TEMPLATES,
    Pattern,
    RuleContext,
    RuleHit,
    RuleSpec,
    ensure_template_params_filled,
    names,
    render_justification,
)
from .command_parser import effective_command_args, effective_command_name

# ========== 允许列表命令定义 ==========

#: 允许列表的**分组内容**（本模块是唯一归属地）。
#:
#: 分组由业务语义划分（系统信息 / 文件 / 内容 / 基础工具 / 压缩 / 脚本），
#: 对人工审查有用，不只是为了组织代码。
ALLOWLIST_GROUPS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "system_info": frozenset({"pwd", "date", "hostname", "whoami", "id", "uptime", "uname", "free"}),
        "file_dir": frozenset({"ls", "dir", "cd", "stat", "readlink", "file", "df", "cp", "mv", "mkdir"}),
        "file_content": frozenset(
            {"cat", "head", "tail", "grep", "egrep", "wc", "sort", "uniq", "cut", "tr", "awk", "sed", "diff"}
        ),
        "basic_tool": frozenset({"echo", "printf", "true", "false", "sleep", "clear", "reset"}),
        "archive": frozenset({"tar", "gzip", "zip"}),
        "script": frozenset({"bash", "sh", "zsh", "python", "python3"}),
    }
)

#: ``ALLOWED_COMMANDS`` / ``ALLOWLIST_RULES[0].pattern`` 的**原始字面量归属**（由分组派生，不手写第二份）。
#:
#: 三者（``ALLOWLIST_GROUPS`` / ``ALLOWLIST_RULES[0].pattern`` / ``ALLOWED_COMMANDS``）
#: **同源**于 ``ALLOWLIST_GROUPS``：分组是唯一真数据，pattern 由它构造，派生视图也由它构造。
#: 不手写第二份的理由是防漂移——两份清单必然在某一刻不一致，而「哪一份才是真的」无从判定。
#: 故既有断言 ``ALLOWED_COMMANDS == pattern 的名字集合`` 恒成立。
_ALLOWED_COMMANDS_SOURCE: frozenset[str] = frozenset().union(*ALLOWLIST_GROUPS.values())

# ========== 本模块拥有的规则规格 ==========

#: 本模块的规则 id 常量（字面量的归属地）。
#:
#: 只有 ``allowlist:allowed`` —— 允许列表是**明确允许**，命中即 allow。未命中任何规则的
#: 处置（review）不由本模块表达：那是 ``command_security`` 的控制流（见其
#: ``_evaluate_rules``），不是一条规则。
ALLOWLIST_ALLOWED = "allowlist:allowed"


def _allowed_hits(context: RuleContext) -> Sequence[RuleHit]:
    """``allowlist:allowed`` 的命中判定：命令名（**已归一化**）被 ``spec.pattern`` 命中。

    判定走 :meth:`Pattern.matches` —— **唯一**匹配实现，本模块不复制任何判定逻辑。
    匹配实现收在一处，是为了让六维度（``tokens`` / ``positional_index`` /
    ``positional_equals`` / ``skip_flags`` / ``strip_colon`` / ``requires_any_flag``）
    对允许列表**全部可见**：允许列表只给 ``tokens`` 一项内容，其余修饰符的语义由
    匹配实现统一提供，本模块无需新引擎、无需正则、无新修饰符。

    名字与参数都取**已归一化 / 内层视图**（:func:`command_parser.effective_command_name` /
    :func:`command_parser.effective_command_args`），使 ``sudo ls`` / ``/bin/ls`` 都能命中。
    两者必须**同源**：只归一化名字而参数取外层，会让 ``sudo mycmd -v`` 因 name 是
    ``mycmd`` 而 args 是 ``["sudo","mycmd","-v"]`` 而错判。

    **纯名字 tokens + 无修饰符的 ``Pattern`` 语义就是「名字命中即放行、参数不参与」**
    （:func:`_match_pattern` 第 2 步命中后走第 5 步 ``return True``）。参数参与与否由
    pattern 的内容决定，不由本函数硬编码，故本函数对内置命令逐条等价于
    「名字在允许集合内」（由 ``tests/packages/security/command/test_command_allowlist.py``
    的参数矩阵钉住）。

    **内容与判定都来自 ``context.spec``，不是模块级常量 / 硬编码字面量**：
    ``pattern`` 来自 ``context.spec.pattern``（不是 ``ALLOWED_COMMANDS``，那是导入期常量）；
    ``verdict`` 来自 ``context.spec.verdict``（不是硬编码 ``"allow"``）。二者读 spec 使
    「改 spec 内容 / 判定即改行为」对本规则**自动成立**——平台用一条同 id 的完整声明替换
    本规则时，两者都跟随。

    **本谓词只判定「名字维度」，不检查参数**：``uname`` 在允许列表是事实，不因参数越界
    而改变。``uname -z`` 会**同时**命中 ``allowlist:allowed`` (allow) 与
    ``args:restricted`` (block)——两条规则各为自己维度负责，聚合层 ``strictest`` 按
    block > review > allow 得出该 finding 的唯一 verdict = block。
    若在此处加一道「参数违规即不产 allow」的抑制，本模块就会越界管参数、引入跨维度依赖
    （被迫持有参数限制表），且允许列表判定不再等价于「名字在允许列表」。
    参数越界由黑名单侧的**精确 pattern 规则**表达，不由「白名单不认可就不放行」表达。
    """
    entry = context.entry
    if entry is None:
        return ()
    source_text = context.walked.source.text
    name = effective_command_name(entry, source_text)
    if name is None:
        return ()
    args = effective_command_args(entry, source_text)
    if not context.spec.pattern.matches(name, args):
        return ()
    ensure_template_params_filled(context.spec.rule_id, {"name": name})
    return (
        RuleHit(
            rule_id=ALLOWLIST_ALLOWED,
            verdict=context.spec.verdict,
            reason=render_justification(context.spec.justification, name=name),
            category="allowlist",
            owner_entry_id=entry.entry_id,
            span=getattr(entry.node, "pos", (0, 0)),
        ),
    )


#: 本模块导出的规则规格。
#:
#: 只含 ``allowlist:allowed`` —— 「命令名在允许列表内」的判定。
#: 「未命中任何规则」的处置（review）不是规则，由 ``command_security`` 的控制流产出，
#: 故不在本模块、也不占规则命名空间。
ALLOWLIST_RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        rule_id=ALLOWLIST_ALLOWED,
        category="allowlist",
        verdict="allow",
        justification=JUSTIFICATION_TEMPLATES[ALLOWLIST_ALLOWED],
        # ``pattern`` 是**判定真源**：``_allowed_hits`` 调 ``context.spec.pattern.matches``，
        # 故平台用一条同 id 的完整声明替换本规则的内容（构造期重建 pattern）
        # 对本规则**自动生效**——把内容与判定放在同一个字段上，是这一自动性的前提。
        pattern=Pattern(tokens=(names(*_ALLOWED_COMMANDS_SOURCE),)),
        predicate=_allowed_hits,
        # 样例校验的是「pattern 能否被命中」，**不是**端到端是否命中——但本规则的
        # 实际判定**就是** ``pattern.matches``，故这里的自洽校验与端到端判定同轴。
        # 端到端覆盖另由 ``test_command_allowlist`` 的命令 × 参数形态矩阵承担。
        match=("ls",),
        not_match=("lsfoo",),
    ),
)

#: 基础允许列表全集 —— **``ALLOWLIST_GROUPS`` 的派生视图**。
#:
#: 构造方向：``ALLOWLIST_GROUPS``（真数据）→ ``_ALLOWED_COMMANDS_SOURCE``
#: → ``ALLOWLIST_RULES[0].pattern`` → 本视图。三者同源，不存在第二份可写副本，
#: 不变式 ``ALLOWED_COMMANDS == ALLOWLIST_GROUPS 的并集``
#: 由 ``tests/packages/security/command/test_command_allowlist.py`` 钉住。
#:
#: 从真数据直接派生（而非从 pattern 的 ``tokens[0]`` 反解）的理由：判定不再拆 tokens，
#: 反解会假设 tokens 的内部形状，而那属于匹配实现的细节。
#:
#: ⚠ 本视图是**导入期快照**，只服务审计 / 平台展示 / 既有调用点；**判定**读
#: ``context.spec.pattern``（见 :func:`_allowed_hits`）。两者内置时同值，
#: 有内容覆盖时 pattern 变而本视图不变——这是刻意的（快照不该随请求变化）。
ALLOWED_COMMANDS: frozenset[str] = _ALLOWED_COMMANDS_SOURCE

# 本模块**不跑导入期不变量自检**（样例自洽 / 占位符一致性）：自检须同时看得见规则全集
# 与 ``command_definitions`` 的模板表，而本模块作为数据模块无从判定跨模块完备性，故收拢到聚合点
# ``command_security`` 调用的 ``command_rule_validation.assert_rule_invariants``。

# 参数限制（``PARAMETER_RESTRICTIONS`` / ``AllowedFlagsOnly`` / 查询口径）**整体属于**
# ``command_blocklist``：本模块只判定「名字维度」，参数策略是黑名单的 ``args:restricted``
# 的职责。两者各管一个维度，聚合层 ``strictest`` 按 block > review > allow 得出唯一 verdict。
