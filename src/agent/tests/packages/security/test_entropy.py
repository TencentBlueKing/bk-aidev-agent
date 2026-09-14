# -*- coding: utf-8 -*-
"""Tests for the bare-entropy fallback detector (aidev_agent.packages.security.redaction.detectors)."""

from __future__ import annotations

import pytest
from aidev_agent.packages.security.redaction import RedactionPurpose, scan_text
from aidev_agent.packages.security.redaction.detectors import EntropyDetector
from aidev_agent.pydantic_models import SecurityRedactionSettings

_GPG = "QGBZvSrgJ0hZOs9KHJV4jhw4hKFPGI6G"  # len=32 ent=4.4528 cls=3
_B64 = "aUpG7zPe+f6z49nJyz8K8NlHG3mpcvgPUTEPiTUv"  # len=40 ent=4.7153 cls=4 (base64(30B random))


class TestBareEntropyPositive:
    """正例：长度 ≥32 的高熵随机串必须命中，rule_id 走独立命名空间。"""

    @pytest.mark.parametrize(
        "text, hid, rule_id, ent",
        [
            (f"token is {_GPG} here", _GPG, "entropy.bare_alnum", 4.4528),
            (f"value {_B64} end", _B64, "entropy.bare_base64", 4.7153),
            (f"short {_GPG}", _GPG, "entropy.bare_alnum", 4.4528),  # len=32 boundary
        ],
    )
    def test_high_entropy_masked(self, text, hid, rule_id, ent):
        findings = EntropyDetector().scan(text)
        assert len(findings) == 1
        found = findings[0]
        assert found.rule_id == rule_id
        assert text[found.start : found.end] == hid  # span covers exactly the candidate
        assert found.kind == "bare_secret"
        assert found.confidence == "heuristic"


class TestBareEntropyNegativeShapes:
    """负例：非凭据标识形状必须零命中（实测熵值见注释，供后人复核判据）。"""

    @pytest.mark.parametrize(
        "text, why",
        [
            ("id 550e8400-e29b-41d4-a716-446655440000 x", "uuid ent=3.3905"),
            ("id 550e8400e29b41d4a716446655440000 x", "no-dash 32-hex ent=3.2482"),
            ("digest " + "a" * 64, "fixed 64-hex shape"),
            ("key 0123456789abcdef0123456789abcdef01234567", "40-hex fingerprint"),
            ("abcdefghijklmnopqrstuvwxyzABCDEF", "monotonic sequence ent=5.0"),
            ("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "repetition ent=0.0"),
            ("这是一段很长的中文说明文字用来测试字符类别不足的情况的补充文字", "non-alnum cls=0"),
            ("x " + "A" * 31 + " x", "len=31 below min_length"),
        ],
    )
    def test_shapes_survive(self, text, why):
        assert EntropyDetector().scan(text) == [], why

    @pytest.mark.parametrize("text", ["", None])
    def test_defensive_input(self, text):
        detector = EntropyDetector()
        assert detector.could_match(text) is False
        assert detector.scan(text) == []


class TestBareEntropyDataUriExclusion:
    """D-08 硬排除：`data:` / `;base64,` 之后的命中被跳过（span 位置判据，非粗粒度）。"""

    @pytest.mark.parametrize(
        "text",
        [
            f'<img src="data:image/png;base64,{_B64}">',  # after ;base64,
            f"data:application/octet-stream,{_B64}",  # after data:
        ],
    )
    def test_container_payload_excluded(self, text):
        assert EntropyDetector().scan(text) == []

    def test_reverse_separated_still_hits(self):
        """反例：`data:` 后带空格分隔，命中不在载荷内 → 仍应命中。"""
        findings = EntropyDetector().scan(f'data: (no payload) "{_GPG}"')
        assert [f.rule_id for f in findings] == ["entropy.bare_alnum"]


class TestBareEntropyAcceptedFalsePositive:
    """D-07 明确接受 base64 图片被命中 —— 记录在案的取舍，不是缺陷。

    若要改此行为须先改 CONTEXT D-07 与 DESIGN §3.6「已知误伤风险」。
    """

    @pytest.mark.parametrize("text", [f"blob {_B64}", f"img {_B64} trailing"])
    def test_base64_blob_is_masked(self, text):
        findings = EntropyDetector().scan(text)
        assert [f.rule_id for f in findings] == ["entropy.bare_base64"]  # ent=4.7153


# ---------------------------------------------------------------------------
# S054 族：含口令符号的裸值（字符集放宽）
# ---------------------------------------------------------------------------

# 交付测试集中的口令字面量：含 ``!``，长度 34，ent=4.6757，cls=3
_PW_SYMBOL = "FixtureOnly!WovuqhlzvUTXDCqieoLIpA"


class TestBareEntropyPasswordSymbols:
    """字符集放宽：含口令符号的裸值不再被切碎（每段 <32 导致零命中）。"""

    @pytest.mark.parametrize(
        "text",
        [
            f"DATABASE_PASSWORD={_PW_SYMBOL}",
            f"REDIS_PASSWORD={_PW_SYMBOL}",
            f'pwd = "{_PW_SYMBOL}"',
            f'令牌 = "{_PW_SYMBOL}"',
            f"machine h login f password {_PW_SYMBOL}",
        ],
    )
    def test_symbol_password_hits(self, text):
        """S054/S055/S065/S071/S089 同构：值含 ``!`` 仍须整段命中。"""
        findings = EntropyDetector().scan(text)
        assert [f.rule_id for f in findings] == ["entropy.bare_password"]
        assert text[findings[0].start : findings[0].end] == _PW_SYMBOL

    def test_symbol_class_requires_alnum(self):
        """纯符号串不是口令（分隔线 / 装饰），不得归入 password 族。"""
        assert EntropyDetector._classify_alphabet("!" * 40) == "other"
        assert EntropyDetector().scan("x " + "!" * 40) == []


class TestEntropyMustNotSwallowStructuredText:
    """两次回归的常驻护栏（放宽字符集时最容易踩的两个坑）。"""

    def test_cjk_prose_not_swallowed(self):
        """白名单必须是 ASCII：取反会把无空白的 CJK 长句整段吞下（S124 回归）。"""
        prose = "用户名林知遥，手机13800000000，邮箱lin@example.invalid"
        assert EntropyDetector().scan(prose) == []
        assert scan_text(prose, purpose=RedactionPurpose.EXPORT).redacted_text == prose

    @pytest.mark.parametrize("purpose", list(RedactionPurpose))
    @pytest.mark.parametrize(
        "prefix, password, suffix, partial",
        [
            ("postgresql://app:", "S3cr3tPw", "@db.internal:5432/prod", None),
            ("mongodb+srv://app:", "S3cr3tPw9xQz", "@cluster0.example.mongodb.net/appdb", None),
            ("postgresql://app:", _PW_SYMBOL, "@db.internal:5432/prod", "Fixtur...LIpA"),
        ],
    )
    def test_dsn_url_not_swallowed(self, prefix, password, suffix, partial, purpose):
        """合并命中后仍只掩码密码；短密码不能因 host 拼接而触发 PARTIAL。"""
        settings = SecurityRedactionSettings(
            enable_redact_bare_entropy=True,
            redact_secrets_min_length=32,
            redact_secrets_entropy_threshold=4.2,
            known_sensitive_values="",
            redact_partial_min_len=32,
            redact_partial_head=6,
            redact_partial_tail=4,
        )
        result = scan_text(f"{prefix}{password}{suffix}", purpose=purpose, settings=settings)
        masked = "[REDACTED:dsn_password]"
        if partial is not None and purpose in (RedactionPurpose.LOG, RedactionPurpose.EXPORT):
            masked = partial
        assert result.redacted_text == f"{prefix}{masked}{suffix}"
        assert result.unique_findings == 1
        assert result.raw_rule_hits.get("dsn") == 1
        if partial is not None:
            assert result.raw_rule_hits.get("entropy.bare_password") == 1

    @pytest.mark.parametrize("password, expected", [("S3cr3tPw9xQz", []), (_PW_SYMBOL, [_PW_SYMBOL])])
    def test_dsn_entropy_span_stops_before_host(self, password, expected):
        text = f"mongodb+srv://app:{password}@cluster0.example.mongodb.net/appdb"
        findings = EntropyDetector().scan(text)
        assert [text[f.start : f.end] for f in findings] == expected


class TestBareEntropyGating:
    """门控与阈值三参数（来自 SecurityRedactionSettings）的实际效果矩阵。"""

    @pytest.mark.parametrize(
        "enabled, expect_hit",
        [(True, True), (False, False)],
    )
    def test_enabled_switch(self, enabled, expect_hit):
        """``enable_redact_bare_entropy`` 经组装层整项排除生效。

        门控不在 detector 上（``EntropyDetector`` 无 ``enabled`` 状态）：
        关闭时它根本不进 ``_detectors_for_scan`` 的列表，故零命中。
        """
        settings = SecurityRedactionSettings(enable_redact_bare_entropy=enabled)
        result = scan_text(f"v {_GPG}", settings=settings)
        assert bool(result.raw_rule_hits) is expect_hit

    @pytest.mark.parametrize(
        "min_length, text, expect_hit",
        [
            (32, f"v {_GPG}", True),  # len=32 satisfies
            (64, f"v {_B64}", False),  # len=40 < 64 no longer hits
        ],
    )
    def test_min_length_threshold(self, min_length, text, expect_hit):
        detector = EntropyDetector(min_length=min_length)
        assert bool(detector.scan(text)) is expect_hit

    @pytest.mark.parametrize(
        "threshold, expect_hit",
        [(4.2, True), (5.0, False)],
    )
    def test_alnum_threshold(self, threshold, expect_hit):
        detector = EntropyDetector(alnum_threshold=threshold)
        assert bool(detector.scan(f"v {_GPG}")) is expect_hit  # ent=4.4528


class TestBareEntropyIndependentCounting:
    """独立计数是校准精度的前提（DESIGN §3.6 / T-06-22）。"""

    def test_rule_id_counted_in_raw_rule_hits(self):
        result = scan_text(f"v {_B64}", purpose=RedactionPurpose.MODEL_OUTPUT)
        assert result.raw_rule_hits.get("entropy.bare_base64") == 1
        assert result.unique_findings == 1

    def test_overlap_with_assignment_counts_both(self):
        """`GPG_KEY=<32-char>` 同时被 assignment 与 entropy 命中：两键并存、cluster 只有 1。"""
        result = scan_text(f"GPG_KEY={_GPG}", purpose=RedactionPurpose.MODEL_OUTPUT)
        # assignment rule_id 用归一化字段名（去分隔符小写）：gpg_key -> gpgkey
        assert result.raw_rule_hits.get("assignment.gpgkey") == 1
        assert result.raw_rule_hits.get("entropy.bare_alnum") == 1
        assert result.unique_findings == 1  # span overlap merged

    def test_end_to_end_redaction_default_on(self):
        """默认真实生效（T-06-19）：MODEL_OUTPUT 下裸值被替换（不依赖字段上下文）。"""
        out = scan_text(f"tool returned {_GPG} from vault", purpose=RedactionPurpose.MODEL_OUTPUT).redacted_text
        assert _GPG not in out
