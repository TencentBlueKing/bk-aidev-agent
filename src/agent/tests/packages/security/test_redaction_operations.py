# -*- coding: utf-8 -*-
"""Tests for the redaction operations layer (aidev_agent.packages.security.redaction.operations)."""

from __future__ import annotations

import inspect

import pytest
from aidev_agent.packages.security.redaction import operations
from aidev_agent.packages.security.redaction.operations import (
    _detectors_for_scan,
    count_sensitive_hits,
    redact_for_export,
    redact_payload,
    redact_text,
    scan_text,
)
from aidev_agent.packages.security.redaction.policy import RedactionPurpose
from aidev_agent.pydantic_models import SecurityRedactionSettings

_GPG_SAMPLE = "QGBZvSrgJ0hZOs9KHJV4jhw4hKFPGI6G"  # len=32，GPG key 样值


class TestRedactTextGpgKey:
    """起点缺陷 D1：GPG_KEY=<32字符样值> 在三种 purpose 下均被替换。"""

    @pytest.mark.parametrize(
        "purpose",
        [RedactionPurpose.LOG, RedactionPurpose.MODEL_OUTPUT, RedactionPurpose.EXPORT],
    )
    def test_gpg_key_redacted_all_purposes(self, purpose):
        out = redact_text(f"GPG_KEY={_GPG_SAMPLE}", purpose=purpose)
        assert _GPG_SAMPLE not in out

    @pytest.mark.parametrize(
        "value",
        ["0123456789abcdef", "0123456789abcdef0123456789abcdef01234567"],
    )
    def test_gpg_hex_identifiers_untouched(self, value):
        """16 位 key ID / 40 位 fingerprint 是纯 hex 定长串，不误伤。"""
        out = redact_text(f"GPG_KEY={value}", purpose=RedactionPurpose.LOG)
        assert value in out


class TestRedactTextVendor:
    """厂商 token 按 purpose 选择掩码风格。"""

    def test_partial_under_log(self):
        assert (
            redact_text("prefix sk-" + "a" * 36 + " suffix", purpose=RedactionPurpose.LOG)
            == "prefix sk-aaa...aaaa suffix"
        )

    def test_typed_sentinel_under_model_output(self):
        out = redact_text("prefix sk-" + "a" * 36 + " suffix", purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "prefix [REDACTED:openai_key] suffix"


class TestRedactTextIdempotence:
    """幂等：redact(redact(x)) == redact(x)；未命中区间字节级不变。"""

    @pytest.mark.parametrize("purpose", [RedactionPurpose.LOG, RedactionPurpose.MODEL_OUTPUT, RedactionPurpose.EXPORT])
    def test_idempotent(self, purpose):
        text = "token sk-" + "a" * 36 + " and GPG_KEY=" + _GPG_SAMPLE
        once = redact_text(text, purpose=purpose)
        assert redact_text(once, purpose=purpose) == once

    def test_unmatched_segments_preserved(self):
        text = "plain prefix " + "sk-" + "a" * 36 + " plain suffix"
        out = redact_text(text, purpose=RedactionPurpose.LOG)
        assert out.startswith("plain prefix ")
        assert out.endswith(" plain suffix")


class TestRedactPayload:
    """D6 修复：凭据容器递归进入，不整体丢弃。"""

    def test_credentials_container_recursed(self):
        payload = {"credentials": {"user": "a", "password": "b"}}
        out = redact_payload(payload, purpose=RedactionPurpose.LOG)
        assert isinstance(out["credentials"], dict)
        assert out["credentials"]["user"] == "a"
        assert out["credentials"]["password"] != "b"

    def test_top_level_credential_field_replaced(self):
        out = redact_payload({"api_key": "somevalue"}, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out["api_key"] == "[REDACTED:credential]"

    def test_nested_list_recursed(self):
        out = redact_payload({"items": [{"password": "x"}]}, purpose=RedactionPurpose.LOG)
        assert out["items"][0]["password"] != "x"

    @pytest.mark.parametrize("switch", ["enable_redact_secrets", "enable_redact_structured_fields"])
    def test_credential_mask_respects_switches(self, switch):
        """凭据字段整体掩码受总开关与 structured_fields 分项管辖（与文本引擎口径一致）。"""
        payload = {"password": "hunter2xyz"}
        off = redact_payload(payload, settings=SecurityRedactionSettings(**{switch: False}))
        assert off["password"] == "hunter2xyz"
        on = redact_payload(payload, settings=SecurityRedactionSettings())
        assert on["password"] != "hunter2xyz"

    def test_master_switch_off_returns_payload_unchanged(self):
        """总开关关闭时整棵子树不脱敏（硬熔断，含嵌套容器）。"""
        payload = {"outer": {"password": "x"}, "list": [{"token": "y"}], "plain": "sk-" + "a" * 36}
        assert redact_payload(payload, settings=SecurityRedactionSettings(enable_redact_secrets=False)) == payload


class TestScanText:
    """ScanResult 契约：raw_rule_hits 键为 rule_id。"""

    def test_raw_rule_hits_keyed_by_rule_id(self):
        result = scan_text("prefix sk-" + "a" * 36 + " suffix", purpose=RedactionPurpose.LOG)
        assert "vendor.openai" in result.raw_rule_hits
        assert result.unique_findings >= 1

    def test_empty_text_returns_zero(self):
        result = scan_text("", purpose=RedactionPurpose.LOG)
        assert result.unique_findings == 0
        assert result.raw_rule_hits == {}


class TestLegacyCompat:
    """兼容旧调用口径。"""

    def test_count_sensitive_hits_keys(self):
        hits = count_sensitive_hits("key sk-" + "a" * 36)
        assert set(hits) == {"vendor_token", "credential_key_value", "total"}

    def test_redact_for_export_uses_export_purpose(self):
        payload = {"secret": "abc"}
        assert redact_for_export(payload)["secret"] != "abc"


# ===== preserve_line_breaks（保留原有行分隔符）=====
#
# 语义：启用时**只改变替换输出** —— 命中区间折叠为占位符的同时，保留其
# 原有的行分隔符（``len(value.split("\n")) - 1`` 个 ``"\n"`` **原样保留**，
# 不是新增），占位符占首行、其余被遮行留空。
# 检测集合 / span 合并 / ``raw_rule_hits`` 在任何取值下都相同。

# PemDetector 整块命中的前提是 body 为**实质内容**。这里统一用真实私钥样值与
# 低熵但非空 body（``A``）—— 后者能命中恰恰证明块配对成立（不是熵兜底）。
_PEM_PREFIX = "-----BEGIN PRIVATE KEY-----"
_PEM_SUFFIX = "-----END PRIVATE KEY-----"
_PEM_BODY = "MIIEowIBAAKCAQEAxYz9QwErTyUiOpAsDfGhJkLmNoPqRsTuVwXyZ0123456789"
_PEM_BLOCK = f"{_PEM_PREFIX}\n{_PEM_BODY}\n{_PEM_SUFFIX}"  # body 高熵（同时触发裸熵）
_PEM_BLOCK_LOW_ENTROPY = f"{_PEM_PREFIX}\nA\n{_PEM_SUFFIX}"  # body 低熵，仅 pem 命中
_PEM_SHELL = f"{_PEM_PREFIX}\n{_PEM_SUFFIX}"  # 空 body 空壳 → 不命中
_VENDOR = "sk-" + "a" * 36
_MULTILINE_VALUE = f"line-a\n{_VENDOR}\nline-c"

# (输入, 保行输出, 默认输出) —— LF / CRLF / CR 三种换行
_PRESERVE_CASES: list[tuple[str, str, str]] = [
    # 高熵 body：被遮 3 行 → 占位符 + 2 个 LF（分隔符数量守恒）
    (_PEM_BLOCK, "[REDACTED:private_key]\n\n", "[REDACTED:private_key]"),
    # 低熵 body：同为空 block，证明是 PemDetector 命中而非熵兜底
    (_PEM_BLOCK_LOW_ENTROPY, "[REDACTED:private_key]\n\n", "[REDACTED:private_key]"),
    # CRLF
    (
        f"{_PEM_PREFIX}\r\n{_PEM_BODY}\r\n{_PEM_SUFFIX}",
        "[REDACTED:private_key]\n\n",
        "[REDACTED:private_key]",
    ),
    # 前后文 + 多行掩码：未命中内容字节级不变，行分隔符守恒
    (
        f"before\n{_PEM_BLOCK}\nafter",
        "before\n[REDACTED:private_key]\n\n\nafter",
        "before\n[REDACTED:private_key]\nafter",
    ),
]


class TestPreserveLineBreaks:
    """保行替换：保留原有行分隔符，不压缩行数。"""

    @pytest.mark.parametrize(("text", "preserved", "default"), _PRESERVE_CASES)
    def test_preserve_keeps_original_separators(self, text, preserved, default):
        assert redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT, preserve_line_breaks=True) == preserved
        assert redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT) == default

    @pytest.mark.parametrize(("text", "preserved", "default"), _PRESERVE_CASES)
    def test_default_false_is_byte_identical(self, text, preserved, default):
        """硬约束：不传 / 传 False 的输出逐字节相同（回归护栏）。"""
        implicit = redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT)
        explicit = redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT, preserve_line_breaks=False)
        assert implicit == explicit == default
        assert explicit != preserved  # 确认该样例确实能区分两种模式

    @pytest.mark.parametrize(
        ("text", "preserved"),
        [
            (_PEM_BLOCK, "[REDACTED:private_key]\n\n"),
            (_PEM_BLOCK_LOW_ENTROPY, "[REDACTED:private_key]\n\n"),
            (
                "before\n" + _PEM_BLOCK + "\nafter",
                "before\n[REDACTED:private_key]\n\n\nafter",
            ),
        ],
    )
    def test_masked_region_line_span_is_conserved(self, text, preserved):
        """被遮区间原有 N 个分隔符 ⇒ 输出仍 N 个（不压缩、不新增）。"""
        out = redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT, preserve_line_breaks=True)
        assert out == preserved
        assert out.count("\n") == preserved.count("\n")

    def test_multiline_vendor_secret_is_single_line_span(self):
        """厂商 token 的 span 是**单行** ⇒ 无换行可保，保行模式是空操作。

        这条同时固定住「保行只在跨行 span 上有区别」这一事实，
        避免以后误以为该参数会改动单行命中。
        """
        text = f"before\nline-a\n{_VENDOR}\nline-c\nafter"
        preserved = redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT, preserve_line_breaks=True)
        assert preserved == redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert preserved == "before\nline-a\n[REDACTED:openai_key]\nline-c\nafter"

    def test_empty_shell_block_is_not_redacted(self):
        """空 body 空壳**不命中** ⇒ 保行开关是空操作（原文逐字保留）。"""
        for preserve in (True, False):
            out = redact_text(_PEM_SHELL, purpose=RedactionPurpose.MODEL_OUTPUT, preserve_line_breaks=preserve)
            assert out == _PEM_SHELL

    @pytest.mark.parametrize(
        "text",
        ["no secret here\nim just\nplain text\n", "trailing\n", "\n", ""],
    )
    def test_no_hit_is_byte_identical(self, text):
        assert redact_text(text, purpose=RedactionPurpose.LOG, preserve_line_breaks=True) == text
        assert redact_text(text, purpose=RedactionPurpose.LOG, preserve_line_breaks=True) == redact_text(
            text, purpose=RedactionPurpose.LOG
        )

    def test_single_line_hit_is_unchanged(self):
        """单行命中无换行可保 ⇒ 与默认替换逐字相同。"""
        text = f"token {_VENDOR} here"
        assert (
            redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT, preserve_line_breaks=True)
            == redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT)
            == "token [REDACTED:openai_key] here"
        )

    def test_purpose_still_controls_mask_style(self):
        """保行不改变掩码风格（partial 仍 partial）。"""
        text = "before\n" + _VENDOR + "\nafter"
        out = redact_text(text, purpose=RedactionPurpose.LOG, preserve_line_breaks=True)
        assert out.startswith("before\nsk-a")
        assert "[REDACTED:" not in out


class TestPreserveLineBreaksDetectionUnchanged:
    """该参数只作用于替换阶段 —— 检测 / span / 计数零影响。"""

    @pytest.mark.parametrize(
        "text",
        [
            _PEM_BLOCK,
            _PEM_BLOCK_LOW_ENTROPY,
            _PEM_SHELL,
            "before\n" + _MULTILINE_VALUE + "\nafter",
            "token sk-" + "a" * 36 + " and GPG_KEY=" + _GPG_SAMPLE + "\n",
        ],
    )
    @pytest.mark.parametrize("purpose", [RedactionPurpose.LOG, RedactionPurpose.MODEL_OUTPUT, RedactionPurpose.EXPORT])
    def test_counts_and_spans_identical(self, text, purpose):
        default = scan_text(text, purpose=purpose)
        preserved = scan_text(text, purpose=purpose, preserve_line_breaks=True)
        assert preserved.raw_rule_hits == default.raw_rule_hits
        assert preserved.unique_findings == default.unique_findings

    def test_low_entropy_body_hit_is_pem_not_entropy(self):
        """低熵 body ``A`` 命中 ⇒ 是 PemDetector 整块命中（非熵兜底）。"""
        assert scan_text(_PEM_BLOCK_LOW_ENTROPY, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits == {"pem": 1}


class TestPreserveLineBreaksScope:
    """参数只落在指定入口上（API 范围护栏）。"""

    def test_parameter_present_on_specified_entries(self):
        for name in ("scan_text", "redact_text", "_apply_replacements"):
            assert "preserve_line_breaks" in inspect.signature(getattr(operations, name)).parameters, name

    @pytest.mark.parametrize("name", ["redact_payload", "redact_for_export"])
    def test_parameter_absent_from_out_of_scope_entries(self, name):
        """``redact_payload`` / ``redact_for_export`` **不**接受该参数（避免扩大出口面）。"""

        assert "preserve_line_breaks" not in inspect.signature(getattr(operations, name)).parameters

    def test_helper_is_private(self):
        """保行辅助函数是模块私有，不进 ``__all__``。"""

        assert hasattr(operations, "_preserve_line_breaks_in")
        assert not any("preserve_line_breaks" in n for n in operations.__all__)


# ===== SecurityRedactionSettings 入口覆盖（D-04）=====


class TestSmallConfigEntries:
    """四个公开入口显式消费 ``SecurityRedactionSettings``：已知值与阈值实际生效。"""

    KNOWN = "known-value-abcdefghijklmnop"
    ASSIGNMENT = f"password={KNOWN}"

    @staticmethod
    def _settings(**overrides):
        return SecurityRedactionSettings(**overrides)

    def test_scan_text_consumes_small_config_known_values(self):
        result = scan_text(self.ASSIGNMENT, settings=self._settings(known_sensitive_values=self.KNOWN))
        assert self.KNOWN not in result.redacted_text
        assert any(rule_id.startswith("registered") for rule_id in result.raw_rule_hits)

    def test_redact_text_consumes_small_config_known_values(self):
        assert self.KNOWN not in redact_text(
            self.ASSIGNMENT, settings=self._settings(known_sensitive_values=self.KNOWN)
        )

    def test_redact_payload_consumes_small_config_thresholds(self):
        out = redact_payload(
            {"password": "x" * 40},
            settings=self._settings(redact_partial_min_len=8, redact_partial_head=2, redact_partial_tail=2),
        )
        assert out == {"password": "xx...xx"}

    def test_count_sensitive_hits_consumes_small_config(self):
        """assignment 样例计入 credential_key_value / total；已知值不并入三键口径。"""
        hits = count_sensitive_hits(self.ASSIGNMENT, settings=self._settings(known_sensitive_values=self.KNOWN))
        assert set(hits) == {"vendor_token", "credential_key_value", "total"}
        assert hits["credential_key_value"] >= 1
        assert hits["total"] == hits["vendor_token"] + hits["credential_key_value"]

    @pytest.mark.parametrize(
        "entry",
        [
            lambda t: scan_text(t).redacted_text,
            lambda t: redact_text(t),
            lambda t: redact_payload({"password": t}),
            lambda t: count_sensitive_hits(t),
        ],
    )
    def test_none_settings_fallback_path_is_safe(self, entry):
        """settings=None 仍按默认小配置回落，不抛异常（D-04 / T-07-04）。"""
        secret = "sk-" + "a" * 36
        assert entry(f"token is {secret}") is not None
        assert secret not in str(entry(f"token is {secret}"))


class TestRedactionLayerSwitches:
    """分层开关接线：``enable_redact_*`` 实际门控对应 detector（防「配了但不生效」）。

    全字段平等：没有任何 detector 不可关闭，总开关是硬熔断。
    """

    @staticmethod
    def _settings(**overrides):
        return SecurityRedactionSettings(**overrides)

    # (开关名, 样例文本, 被遮时不出现在输出里的秘密, 预期的独立命中规则)
    # 样例刻意选「只被目标 detector 命中」的形态，避免被其它层兜底遮住而掩盖开关失效。
    OPTIONAL_CASES = [
        ("enable_redact_cookies", "Cookie: session=abc123SECRET", "abc123SECRET", "cookie"),
        ("enable_redact_vendor_tokens", "key sk-" + "a" * 36, "a" * 36, "vendor.openai"),
        ("enable_redact_url_credentials", "https://h/p?token=" + "b" * 32 + "&x=1", "b" * 32, "url"),
        ("enable_redact_dsn_passwords", "postgresql://u:" + "c" * 32 + "@h/d", "c" * 32, "dsn"),
        ("enable_redact_structured_fields", "passwd=" + "d" * 32, "d" * 32, "assignment.passwd"),
    ]

    @pytest.mark.parametrize("switch, sample, secret, rule", OPTIONAL_CASES)
    def test_optional_switch_off_disables_detector(self, switch, sample, secret, rule):
        """开关打开时目标 detector 独立命中；关闭后该规则不再出现、秘密明文存活。"""
        before = scan_text(sample)
        assert rule in before.raw_rule_hits, f"样例须由 {rule} 独立命中"
        assert secret not in redact_text(sample)

        after = scan_text(sample, settings=self._settings(**{switch: False}))
        assert rule not in after.raw_rule_hits
        assert secret in after.redacted_text

    @pytest.mark.parametrize("switch, sample, secret, rule", OPTIONAL_CASES)
    def test_master_switch_off_disables_all_optional(self, switch, sample, secret, rule):
        """总开关 ``enable_redact_secrets=False`` 关闭全部 optional 层。"""
        after = scan_text(sample, settings=self._settings(enable_redact_secrets=False))
        assert rule not in after.raw_rule_hits
        assert secret in after.redacted_text

    # (原 mandatory 开关名, 样例文本, 被遮时不出现在输出里的秘密, 该开关独自提供的规则, 关闭后仍在的兜底规则)
    # 这三项原为「不可关闭」（D-06 静默归真），现已与 optional 平等：分项开关真关闭。
    #
    # 注意最后一栏：Bearer 样例同时被 ``headers`` 与 ``vendor.bearer`` 命中
    # （同一 span，priority 90 vs 80 由 merge_spans 取高者）。关闭 headers 后
    # vendor.bearer 仍在，故秘密**仍被遮** —— 这类样例只能断言「本规则消失」，
    # 不能断言「明文存活」。registered 是精确值匹配，与其它层无重叠口径，可断言明文存活。
    _KNOWN = "super-secret-token-value-abc123"
    FORMERLY_MANDATORY_CASES = [
        ("enable_redact_authorization_headers", "Authorization: Bearer " + "e" * 32, "e" * 32, "headers", True),
        (
            "enable_redact_private_keys",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEow==\n-----END RSA PRIVATE KEY-----",
            "MIIEow==",
            "pem",
            False,
        ),
        ("enable_redact_registered_secrets", _KNOWN, _KNOWN, "registered:known", False),
    ]

    @classmethod
    def _extra_for(cls, switch: str) -> dict:
        """``registered`` 需要显式注入已知值才能命中；其余样例用默认 settings 即可。"""
        return {"known_sensitive_values": cls._KNOWN} if switch == "enable_redact_registered_secrets" else {}

    @pytest.mark.parametrize("switch, sample, secret, rule, multilayered", FORMERLY_MANDATORY_CASES)
    def test_formerly_mandatory_switch_off_disables_detector(self, switch, sample, secret, rule, multilayered):
        """原 mandatory 三项现可逐项关闭：该规则不再出现；无兜底层时明文存活。"""
        extra = self._extra_for(switch)
        assert rule in scan_text(sample, settings=self._settings(**extra)).raw_rule_hits, f"样例须由 {rule} 命中"
        assert secret not in redact_text(sample, settings=self._settings(**extra))

        after = scan_text(sample, settings=self._settings(**{**extra, switch: False}))
        assert rule not in after.raw_rule_hits
        if not multilayered:
            assert secret in after.redacted_text

    @pytest.mark.parametrize("switch, sample, secret, rule, multilayered", FORMERLY_MANDATORY_CASES)
    def test_master_switch_off_disables_formerly_mandatory(self, switch, sample, secret, rule, multilayered):
        """总开关是硬熔断：原 mandatory 层同样被关闭 —— 引擎完全不跑，无任何命中。"""
        extra = self._extra_for(switch)
        assert scan_text(sample, settings=self._settings(**extra)).raw_rule_hits != {}

        after = scan_text(sample, settings=self._settings(**{**extra, "enable_redact_secrets": False}))
        assert after.raw_rule_hits == {}
        assert after.redacted_text == sample

    def test_jwt_switch_is_wired(self):
        """``enable_redact_jwt`` 是真开关：关闭后 ``jwt.jws`` 不再命中。

        注意 ``jwt.jws`` 来自 ``JwtDetector``（rule_id=``jwt``）；样例里的
        ``vendor.jwt`` 是 ``VendorTokenDetector`` 的**同名规则**，由
        ``enable_redact_vendor_tokens`` 控制 —— 两个 detector 对 JWT 形态有重叠覆盖，
        故断言必须精确到 ``jwt.jws``，不能只看 ``vendor.jwt``。
        """
        sample = "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        assert "jwt.jws" in scan_text(sample).raw_rule_hits

        after = scan_text(sample, settings=self._settings(enable_redact_jwt=False))
        assert "jwt.jws" not in after.raw_rule_hits

    def test_jwt_switch_off_does_not_touch_vendor_jwt(self):
        """两个 JWT 类规则由各自开关独立控制，互不牵连。"""
        sample = "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        hits = scan_text(sample, settings=self._settings(enable_redact_jwt=False)).raw_rule_hits
        assert "vendor.jwt" in hits
        assert "jwt.jws" not in hits

    def test_all_switches_off_yields_empty_detector_list(self):
        """全部开关关闭 ⇒ ``_detectors_for_scan`` 返回空列表（引擎完全不跑）。

        「所有功能都需要有开关」的结构性证据：不存在任何遗漏登记、恒被构造的 detector。
        """

        all_off = {name: False for name in self._settings().model_fields if name.startswith("enable_redact_")}
        assert _detectors_for_scan(settings=self._settings(**all_off)) == []

    def test_master_switch_returns_empty_even_with_children_on(self):
        """总开关是硬熔断：子项全开也无法穿透（无优先级冲突语义）。"""

        assert _detectors_for_scan(settings=self._settings(enable_redact_secrets=False)) == []

    def test_default_settings_still_register_all_eleven(self):
        """默认全开时列表仍为 11 个（本次改动不改默认检测集合）。"""

        assert len(_detectors_for_scan(settings=self._settings())) == 11
