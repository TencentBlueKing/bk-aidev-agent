# -*- coding: utf-8 -*-
"""Tests for command approval (aidev_agent.packages.security.command.command_approval)."""

from __future__ import annotations

import json

import aidev_agent.packages.security.command.command_approval as ca
import pytest
from aidev_agent.pydantic_models import SecurityCommandSettings


def _ss(approvers: str = "", disposition: str = "approval") -> SecurityCommandSettings:
    """构造显式安全配置（处置档由调用方传入，不从 env 读）。"""
    return SecurityCommandSettings(command_review_disposition=disposition, command_approval_approvers=approvers)


class _StubTicketRM:
    """只 stub 平台建单出口的 RM（记录 create_tool_approval 的载荷与 username，无远程访问）。"""

    def __init__(self) -> None:
        self.create_calls: list[tuple[dict, str | None]] = []

    def create_tool_approval(self, payload: dict, *, username=None, **kwargs) -> dict:
        self.create_calls.append((payload, username))
        return {"id": "phase10-ticket"}


class TestCommandFingerprint:
    """指纹只做「空白折叠 + 小写」归一化，不做语义等价（同义命令仍应有不同指纹）。"""

    @pytest.mark.parametrize(
        "left, right, same",
        [
            ("  Echo   Hello  ", "echo hello", True),  # 空白折叠 + 大小写归一后等价
            ("echo a", "echo b", False),  # 不同命令必须分叉，否则审计无法区分
        ],
    )
    def test_fingerprint_equivalence(self, left, right, same):
        assert (ca.command_fingerprint(left) == ca.command_fingerprint(right)) is same


class TestRequireCommandApproval:
    """``require_command_approval`` 的守卫与 decision 解析。

    两类守卫刻意不合并成同一个参数化用例：类型守卫（非字符串）与配置守卫（无审批人）
    在失败定位上指向不同原因，合并会让「为什么被拒」变模糊。
    """

    def test_rejects_non_string(self):
        assert ca.require_command_approval(None, security_settings=_ss("u1")) is False
        assert ca.require_command_approval(123, security_settings=_ss("u1")) is False

    def test_rejects_when_no_approvers(self):
        assert ca.require_command_approval("echo hi", security_settings=_ss("")) is False

    def test_approved_decision_returns_true(self, monkeypatch):
        monkeypatch.setattr(ca, "interrupt", lambda value: {"payload": {"approved": True}})
        assert ca.require_command_approval("echo hi", target_runtime="sbx", security_settings=_ss("u1,u2")) is True

    def test_rejected_decision_returns_false(self, monkeypatch):
        monkeypatch.setattr(ca, "interrupt", lambda value: {"payload": {"approved": False}})
        assert ca.require_command_approval("echo hi", security_settings=_ss("u1")) is False

    def test_interrupt_exception_fails_closed(self, monkeypatch):
        def _boom(_value):
            raise RuntimeError("no graph context")

        monkeypatch.setattr(ca, "interrupt", _boom)
        assert ca.require_command_approval("echo hi", security_settings=_ss("u1")) is False


class TestCommandReviewPayload:
    """``command_review`` 明细接入 ``args``（不改 reason / 指纹 / schema）。

    明细是**可选键**：不传时 ``toolArgs`` 必须恰好只有 ``command`` 与 ``target_runtime``，
    传时恰好多出 ``command_review`` —— 审批载荷形状是与平台之间的契约，故两种形态在此闭合。
    """

    @staticmethod
    def _capture(monkeypatch) -> list[dict]:
        captured: list[dict] = []
        monkeypatch.setattr(ca, "interrupt", lambda value: captured.append(value) or {"payload": {"approved": True}})
        return captured

    def test_tool_args_key_set_tracks_review_presence(self, monkeypatch):
        """键集随 ``command_review`` 有无而变，且两种形态都不引入额外键。"""
        captured = self._capture(monkeypatch)
        assert ca.require_command_approval("echo hi", target_runtime="sbx", security_settings=_ss("u1")) is True
        assert set(captured[0]["toolArgs"].keys()) == {"command", "target_runtime"}
        assert captured[0]["reason"] == ca.TOOL_APPROVAL_REASON

        review = {"sources": [], "findings": []}
        assert ca.require_command_approval(
            "echo hi", target_runtime="sbx", security_settings=_ss("u1"), command_review=review
        )
        assert set(captured[1]["toolArgs"].keys()) == {"command", "target_runtime", "command_review"}
        assert captured[1]["toolArgs"]["command_review"] == review

    def test_review_payload_is_plain_json_and_preserves_identity(self, monkeypatch):
        """明细逐字透传，且 value 是普通 JSON：``toolCallId`` 精确等于命令指纹。"""
        captured = self._capture(monkeypatch)
        review = {
            "sources": [{"source_id": 0, "parent_id": None, "origin_span": None, "text": "mycmd"}],
            "findings": [
                {
                    "source_id": 0,
                    "entry_id": 0,
                    "span": [0, 5],
                    "command_name": "mycmd",
                    "verdict": "review",
                    "rule_ids": ["whitelist:review"],
                    "rules": [
                        {"rule_id": "whitelist:review", "verdict": "review", "reason": "r", "category": "allowlist"}
                    ],
                }
            ],
        }
        raw = "  mycmd   --ver  "
        assert ca.require_command_approval(
            raw, target_runtime="sbx", security_settings=_ss("u1"), command_review=review
        )
        value = captured[0]
        # 普通 JSON（无 default 兜底），无 dataclass / set / 异常对象
        json.dumps(value)
        json.dumps(value["toolArgs"]["command_review"])
        assert value["toolArgs"]["command_review"] == review
        assert value["toolArgs"]["command"] == raw  # 原始串（含空白）不变
        assert value["toolArgs"]["target_runtime"] == "sbx"
        assert value["toolCallId"] == ca.command_fingerprint(raw)
        assert value["reason"] == ca.TOOL_APPROVAL_REASON


class TestCommandApprovalModeNormalization:
    """review 处置档 fail-closed 归一化（内联在 ``enforce_command_security``）。

    非 ``allow``/``approval``/``block`` 的取值一律回落 ``block``：即便开启预分流，
    也绝不因配置错误进入自动放行路径 —— 归一化的目的就是让「配置写错」表现为
    「更保守」，而不是「更宽松」。用真实 ``enforce_command_security`` 验证该性质。

    注：模型字段是 ``Literal``，正常构造会先被 pydantic 拒绝，故这里用
    ``model_construct`` 绕过校验，直接检视 ``enforce`` 层的兜底。
    """

    @staticmethod
    def _settings(disposition: str) -> SecurityCommandSettings:
        return SecurityCommandSettings.model_construct(
            command_review_disposition=disposition, command_approval_approvers="u1"
        )

    @pytest.mark.parametrize("disposition", ["", "ALLOW", "Approval", "bogus", " allow", "reject"])
    def test_unknown_disposition_never_reaches_assessor_or_approval(self, monkeypatch, disposition):
        """未知/非精确取值（含旧值 reject）→ block：评估器与审批都不得被调用。"""
        from aidev_agent.packages.security.command import command_security as cs

        calls: list[str] = []
        monkeypatch.setattr(ca, "interrupt", lambda value: calls.append("approval") or {"payload": {"approved": True}})
        assessor = type("R", (), {"assess": lambda self, c: calls.append("assess") or "allow"})()
        with pytest.raises(ValueError, match="命令执行被拒绝"):
            cs.enforce_command_security("touch /tmp/x", "local", self._settings(disposition), assessor)
        assert calls == [], f"disposition={disposition!r} 不应进入评估或审批路径"

    def test_exact_allow_passes(self, monkeypatch):
        """精确 ``allow``：review 直接放行（评估器仍可被预分流调用）。"""
        from aidev_agent.packages.security.command import command_security as cs

        calls: list[str] = []
        monkeypatch.setattr(ca, "interrupt", lambda value: calls.append("approval") or {"payload": {"approved": True}})
        cs.enforce_command_security("touch /tmp/x", "local", self._settings("allow"))
        assert calls == [], "allow 档不应进入人工审批"


class TestCommandApproversParsing:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("", []),
            ("  ", []),
            (",", []),
            ("a", ["a"]),
            ("a,b", ["a", "b"]),
            ("a, b ,a", ["a", "b"]),
            (" a ,, b ,", ["a", "b"]),
            (",a,", ["a"]),
        ],
    )
    def test_approvers_parsing_contract(self, raw, expected):
        """逗号分隔去空去重并保序（空 / 纯空白 / 前后逗号 / 重复 均须健壮）。"""
        assert ca._command_approvers(SecurityCommandSettings(command_approval_approvers=raw)) == expected


class TestCommandReviewPrepareChain:
    """审批明细从真实生产入口产生，不手造预期 payload。

    入口固定为生产 ``RuntimeBackendResolver`` + ``get_execute_tool`` + ``invoke`` /
    ``ainvoke``；真实 enforce / validate / require_command_approval 全部保留，
    仅隔离两处平台出口：``ca.interrupt``（捕获深拷贝 value 并返回批准）与
    stub RM 的 ``create_tool_approval``（无远程访问）。

    命令含**两个不同 child 来源**且原文相同（``mycmd``）。用真实链路而非手造 payload
    的意义就在于此：只有真实链路能钉住 source 父链与 identity ``(source_id, entry_id)``，
    证明「两个同文兄弟各占独立 id」。
    """

    RAW = "  bash -c 'mycmd'; bash -c 'mycmd'  "

    @staticmethod
    def _run(asynchronous, monkeypatch) -> tuple[list[str], list[dict]]:
        """经生产双入口执行，返回 (sink 原文, 捕获的真实 interrupt value 列表)。"""
        import asyncio
        import copy
        from tempfile import TemporaryDirectory

        from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
        from aidev_agent.core.tools.runtime_tools.provider import RuntimeBackendResolver, get_execute_tool
        from aidev_agent.core.tools.runtime_tools.types import ExecuteResult
        from aidev_agent.pydantic_models import SecuritySettings

        captured: list[dict] = []
        monkeypatch.setattr(
            ca, "interrupt", lambda value: captured.append(copy.deepcopy(value)) or {"payload": {"approved": True}}
        )
        settings = SecuritySettings(
            command=SecurityCommandSettings(
                enable_command_blocklist=True,
                command_review_disposition="approval",
                command_approval_approvers="u1",
            )
        )
        sink: list[str] = []
        with TemporaryDirectory() as tmpdir:
            backend = FilesystemBackend(root_dir=tmpdir)

            def _sync(command, *, config=None, state=None, timeout=None, max_output_size=None):
                sink.append(command)
                return ExecuteResult(output="stub-ok", exit_code=0)

            async def _async(command, *, config=None, state=None, timeout=None, max_output_size=None):
                sink.append(command)
                return ExecuteResult(output="stub-ok", exit_code=0)

            backend.execute = _sync
            backend.aexecute = _async
            resolver = RuntimeBackendResolver(default_runtime="local", security_settings=settings).register_runtime(
                "local", backend
            )
            tool = get_execute_tool(resolver)
            args = {"command": TestCommandReviewPrepareChain.RAW, "target_runtime": "local"}
            asyncio.run(tool.ainvoke(args)) if asynchronous else tool.invoke(args)
        return sink, captured

    @pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
    def test_real_interrupt_value_identity_and_sources(self, asynchronous, monkeypatch):
        """恰一次审批；sources 完整父链 + 两个同文 siblings；指纹/原串/reason 精确。"""
        sink, captured = self._run(asynchronous, monkeypatch)
        assert sink == [self.RAW]  # 整条原文一次执行
        assert len(captured) == 1  # 整条原文一次审批（非逐子命令建单）
        value = captured[0]
        assert value["reason"] == ca.TOOL_APPROVAL_REASON
        assert value["toolCallId"] == ca.command_fingerprint(self.RAW)
        assert value["toolArgs"]["command"] == self.RAW
        assert value["toolArgs"]["target_runtime"] == "local"
        assert "metadata" not in value  # 无顶层 metadata（prepare 要求原始 target 形态）
        self._assert_sources(value["toolArgs"]["command_review"], self.RAW)
        self._assert_review_findings(value["toolArgs"]["command_review"])

    @staticmethod
    def _assert_sources(review: dict, raw: str) -> None:
        """sources 完整父链：root=0，两个同文 child 各占独立 id + 不同 word span。"""
        sources = {s["source_id"]: s for s in review["sources"]}
        assert set(sources) == {0, 1, 2}
        assert sources[0]["parent_id"] is None and sources[0]["text"] == raw
        assert sources[1]["parent_id"] == 0 and sources[2]["parent_id"] == 0
        assert sources[1]["text"] == sources[2]["text"] == "mycmd"
        assert sources[1]["origin_span"] == [10, 17]
        assert sources[2]["origin_span"] == [27, 34]
        assert sources[1]["origin_span"] != sources[2]["origin_span"]

    @staticmethod
    def _assert_review_findings(review: dict) -> None:
        """findings 联合 identity 为 (1,0)/(2,0)，且 ``mycmd`` 零规则命中。

        ``mycmd`` 不在允许列表也不在黑名单，故 review 由控制流产出、``rule_ids == []``。
        审批人另有 ``toolArgs["command"]`` 原串佐证。
        """
        identities = {(f["source_id"], f["entry_id"]) for f in review["findings"]}
        assert identities == {(1, 0), (2, 0)}
        for finding in review["findings"]:
            assert finding["span"] == [0, 5]
            assert finding["command_name"] == "mycmd"
            assert finding["verdict"] == "review"
            assert finding["rule_ids"] == []  # 未命中任何规则
            assert finding["rules"] == []

    @pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
    def test_json_roundtrip_is_lossless(self, asynchronous, monkeypatch):
        """普通 ``json.dumps``（无 default 兜底）往返后全部字段逐项相等。"""
        _, captured = self._run(asynchronous, monkeypatch)
        value = captured[0]
        assert json.loads(json.dumps(value)) == value

    @pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
    def test_prepare_and_ticket_creator_preserve_review(self, asynchronous, monkeypatch):
        """真实 prepare + ItsmTicketCreator：三处 toolArgs 投影均精确保留明细。"""
        from types import SimpleNamespace

        from aidev_agent.packages.interrupt_manager.approval import ApprovalHandler, ItsmTicketCreator

        _, captured = self._run(asynchronous, monkeypatch)
        rm = _StubTicketRM()
        interrupt = SimpleNamespace(value=captured[0], id="phase10-local-interrupt")
        enriched = ApprovalHandler().prepare(interrupt, ItsmTicketCreator(rm, username="u"))

        assert enriched is interrupt  # 就地 enrich，返回同一对象
        assert len(rm.create_calls) == 1  # stub RM 恰建一单
        review = captured[0]["toolArgs"]["command_review"]
        payload, username = rm.create_calls[0]
        assert username == "u"
        assert payload["tool_args"]["command_review"] == review  # 平台建单 tool_args
        assert payload["tool_args"]["command"] == self.RAW
        # 就地 enrich 后：顶层 toolArgs 与 metadata.toolArgs 均保留同一明细
        assert enriched.value["toolArgs"]["command_review"] == review
        assert enriched.value["metadata"]["toolArgs"]["command_review"] == review
        assert enriched.value["reason"] == ca.TOOL_APPROVAL_REASON
        assert enriched.value["toolCallId"] == ca.command_fingerprint(self.RAW)
