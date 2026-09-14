# -*- coding: utf-8 -*-
"""Tests for command risk assessor (review auto pre-triage).

Covers the fail-closed contract of ``CommandRiskAssessor.assess``:
non-string commands, missing LLM, LLM exceptions and invalid outputs all
must fall back to ``approval`` (never auto-approve).
"""

from __future__ import annotations

from typing import Any

from aidev_agent.packages.security.command.command_risk_assessor import CommandRiskAssessor, RiskAssessment


class _StructuredLLM:
    """Fake LLM that supports ``with_structured_output``."""

    def __init__(self, disposition: Any = "allow", reason: str = "") -> None:
        self._disposition = disposition
        self._reason = reason

    def with_structured_output(self, schema: Any) -> "_StructuredLLM":
        return self

    def invoke(self, prompt: str) -> RiskAssessment:
        return RiskAssessment(disposition=self._disposition, reason=self._reason)  # type: ignore[arg-type]


class _TextOnlyLLM:
    """Fake LLM without structured output; returns raw JSON text."""

    def __init__(self, content: str) -> None:
        self._content = content

    def with_structured_output(self, schema: Any) -> Any:
        raise AttributeError("structured output unsupported")

    def invoke(self, prompt: str) -> Any:
        return type("Message", (), {"content": self._content})()


class _BoomLLM:
    """Fake LLM that raises on every call."""

    def with_structured_output(self, schema: Any) -> Any:
        raise RuntimeError("boom")


class TestCommandRiskAssessor:
    def test_non_string_command_returns_approval(self):
        assessor = CommandRiskAssessor(_StructuredLLM("allow"))
        assert assessor.assess(None) == "approval"
        assert assessor.assess(123) == "approval"
        assert assessor.assess("   ") == "approval"

    def test_missing_llm_returns_approval(self):
        assessor = CommandRiskAssessor(None)
        assert assessor.assess("rm -rf /") == "approval"

    def test_allow_disposition(self):
        assessor = CommandRiskAssessor(_StructuredLLM("allow"))
        assert assessor.assess("ls -la") == "allow"

    def test_block_disposition(self):
        assessor = CommandRiskAssessor(_StructuredLLM("block"))
        assert assessor.assess("rm -rf /") == "block"

    def test_approval_disposition(self):
        assessor = CommandRiskAssessor(_StructuredLLM("approval"))
        assert assessor.assess("some-unknown-tool") == "approval"

    def test_invalid_disposition_falls_back_to_approval(self):
        # 文本 LLM 返回非法 disposition 值 → assess 防御逻辑回退 approval
        assessor = CommandRiskAssessor(_TextOnlyLLM('{"disposition": "bogus", "reason": "x"}'))
        assert assessor.assess("ls") == "approval"

    def test_legacy_risk_field_is_ignored(self):
        # 旧字段名 ``risk`` 不再被读取：无 disposition 字段 → 回退 approval
        assessor = CommandRiskAssessor(_TextOnlyLLM('{"risk": "low", "reason": "x"}'))
        assert assessor.assess("ls") == "approval"

    def test_llm_exception_falls_back_to_approval(self):
        assessor = CommandRiskAssessor(_BoomLLM())
        assert assessor.assess("ls") == "approval"

    def test_text_llm_json_fallback(self):
        assessor = CommandRiskAssessor(_TextOnlyLLM('{"disposition": "allow", "reason": "safe"}'))
        assert assessor.assess("ls") == "allow"

    def test_text_llm_invalid_json_falls_back_to_approval(self):
        assessor = CommandRiskAssessor(_TextOnlyLLM("not json"))
        assert assessor.assess("ls") == "approval"
