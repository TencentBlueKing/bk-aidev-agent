# -*- coding: utf-8 -*-
"""Tests for masking styles and thresholds (aidev_agent.packages.security.redaction.masking)."""

from __future__ import annotations

import pytest
from aidev_agent.packages.security.redaction.masking import (
    REDACT_PLACEHOLDER,
    mask,
)
from aidev_agent.packages.security.redaction.operations import redact_payload, redact_text
from aidev_agent.packages.security.redaction.policy import MaskStyle
from aidev_agent.pydantic_models import SecurityRedactionSettings, SecuritySettings

# 默认阈值（与 SecurityRedactionSettings 默认值一致：masking.py 历史硬编码常量）
_DEFAULTS = {"partial_min_len": 32, "partial_head": 6, "partial_tail": 4}


class TestMaskPartial:
    """partial 风格：长度 >=32 保留首 6 尾 4；长度 <32 整体替换。"""

    @pytest.mark.parametrize(
        "value, kind, expected",
        [
            ("x" * 31, "k", "[REDACTED:k]"),  # 31 < 32 → typed sentinel
            ("x" * 32, "k", "xxxxxx...xxxx"),  # 32 >= 32 → partial（首 6 尾 4）
            ("sk-" + "a" * 36, "vendor_token", "sk-aaa...aaaa"),
            ("ghp_" + "A" * 36, "vendor_token", "ghp_AA...AAAA"),
            ("glpat-" + "c" * 20, "vendor_token", "[REDACTED:vendor_token]"),  # len=26 < 32
        ],
    )
    def test_partial_style(self, value, kind, expected):
        assert mask(value, kind=kind, style=MaskStyle.PARTIAL, **_DEFAULTS) == expected

    def test_boundary_31_vs_32(self):
        """钉死 31/32 相邻边界：31 走 sentinel、32 走 partial。"""
        assert mask("y" * 31, kind="k", style=MaskStyle.PARTIAL, **_DEFAULTS) == "[REDACTED:k]"
        assert mask("y" * 32, kind="k", style=MaskStyle.PARTIAL, **_DEFAULTS) == "yyyyyy...yyyy"


class TestMaskTypedSentinel:
    """typed_sentinel 风格：任意长度一律整体替换，不保留 secret body。"""

    @pytest.mark.parametrize(
        "value",
        [
            "short",
            "x" * 31,
            "x" * 32,
            "sk-" + "a" * 36,
            "x" * 128,
        ],
    )
    def test_always_typed_sentinel(self, value):
        assert (
            mask(value, kind="vendor_token", style=MaskStyle.TYPED_SENTINEL, **_DEFAULTS) == "[REDACTED:vendor_token]"
        )


class TestMaskConfigurable:
    """T-urf-03：阈值经参数注入真正生效（非默认值改变掩码结果）。"""

    @pytest.mark.parametrize(
        "value, thresholds, expected",
        [
            # 放宽阈值：len=10 >= 8 → 保留首 2 尾 2
            ("x" * 10, {"partial_min_len": 8, "partial_head": 2, "partial_tail": 2}, "xx...xx"),
            # 放宽阈值：len=10 < 8? 否 → 仍走 sentinel（阈值=11 时）
            ("x" * 10, {"partial_min_len": 11, "partial_head": 2, "partial_tail": 2}, "[REDACTED:k]"),
            # 只改首尾长度：len=32 默认保留路径但截取位数不同
            ("x" * 32, {"partial_min_len": 32, "partial_head": 3, "partial_tail": 2}, "xxx...xx"),
        ],
    )
    def test_non_default_thresholds_take_effect(self, value, thresholds, expected):
        assert mask(value, kind="k", style=MaskStyle.PARTIAL, **thresholds) == expected

    def test_typed_sentinel_ignores_thresholds(self):
        """typed_sentinel 不受阈值影响（任意长度整体替换）。"""
        assert (
            mask("x" * 10, kind="k", style=MaskStyle.TYPED_SENTINEL, partial_min_len=1, partial_head=1, partial_tail=1)
            == "[REDACTED:k]"
        )

    def test_thresholds_are_required_keyword_only(self):
        """三个阈值必填仅关键字：遗漏即 TypeError（不会静默用旧阈值）。"""
        with pytest.raises(TypeError):
            mask("x" * 32, kind="k", style=MaskStyle.PARTIAL)  # type: ignore[call-arg]


class TestRedactPlaceholder:
    """占位符常量随 D-12 从 redact.py 迁入 masking.py。"""

    def test_placeholder_value(self):
        assert REDACT_PLACEHOLDER == "[REDACTED]"


class TestSecuritySettingsDrivenThresholds:
    """SecurityRedactionSettings 三个字段默认 32/6/4，经 redact_text / redact_payload 注入后生效。"""

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("BKAI_REDACT_PARTIAL_MIN_LEN", raising=False)
        monkeypatch.delenv("BKAI_REDACT_PARTIAL_HEAD", raising=False)
        monkeypatch.delenv("BKAI_REDACT_PARTIAL_TAIL", raising=False)
        settings = SecurityRedactionSettings()
        assert (settings.redact_partial_min_len, settings.redact_partial_head, settings.redact_partial_tail) == (
            32,
            6,
            4,
        )

    @pytest.mark.parametrize(
        "field, override",
        [
            ("redact_partial_min_len", 8),
            ("redact_partial_head", 2),
            ("redact_partial_tail", 3),
        ],
    )
    def test_platform_mapping_override(self, field, override):
        """平台下发值经嵌套 dict 生效。"""
        settings = SecuritySettings(redaction={field: override})
        assert getattr(settings.redaction, field) == override

    def test_settings_injection_changes_redact_text_result(self):
        """非默认阈值经 SecurityRedactionSettings 注入 → redact_text 产出与手传参数一致。"""

        long_secret = "x" * 40
        text = f"password={long_secret}"
        injected = redact_text(
            text,
            settings=SecurityRedactionSettings(redact_partial_min_len=8, redact_partial_head=2, redact_partial_tail=2),
        )
        assert "xx...xx" in injected
        manual = mask(
            long_secret,
            kind="credential",
            style=MaskStyle.PARTIAL,
            partial_min_len=8,
            partial_head=2,
            partial_tail=2,
        )
        assert manual == "xx...xx"

    def test_fallback_path_equals_explicit_default(self):
        """redact_text(text) 与 redact_text(text, settings=SecurityRedactionSettings()) 结果相同。"""

        text = "api_key=" + "a" * 40
        assert redact_text(text) == redact_text(text, settings=SecurityRedactionSettings())

    def test_redact_payload_thresholds_take_effect(self):
        """redact_payload 凭据字段整体掩码路径同样消费注入阈值。"""

        payload = {"password": "x" * 40}
        out = redact_payload(
            payload,
            settings=SecurityRedactionSettings(redact_partial_min_len=8, redact_partial_head=2, redact_partial_tail=2),
        )
        assert out == {"password": "xx...xx"}
