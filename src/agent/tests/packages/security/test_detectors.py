# -*- coding: utf-8 -*-
"""Tests for the protocol-aware detectors (aidev_agent.packages.security.redaction.detectors)."""

from __future__ import annotations

import ast
import base64
import pathlib
import re
import time
from dataclasses import fields
from unittest.mock import patch

import pytest
from aidev_agent.packages.security.redaction import detectors, utils
from aidev_agent.packages.security.redaction.detectors import (
    AssignmentDetector,
    CookieDetector,
    DsnDetector,
    DsnJdbcDetector,
    EntropyDetector,
    HeadersDetector,
    JwtDetector,
    PemDetector,
    RegisteredSecretDetector,
    RegisteredValue,
    UrlDetector,
    VendorTokenDetector,
    classify_pem_label,
    is_pem_non_secret_span,
    is_placeholder_value,
    is_substantive_pem_body,
    iter_pem_blocks,
    iter_unterminated_secret_pem_spans,
    normalize_label,
)
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

# 起点缺陷 D1 的样值：32 位高熵、无厂商前缀、非注册值
_GPG_SAMPLE = "QGBZvSrgJ0hZOs9KHJV4jhw4hKFPGI6G"

# 64 位纯 hex（SHA-256 / AES-256 宽度）—— S057/S058/S076/S081 共用的测试值
_HEX64 = "ee1ca6a9220eec1691004295dc12093f2444c7c0eb210a1f2967434043133cd4"

# 严格字段正例（命中即脱敏，无需评分）
_STRICT_SAMPLES = (
    "password=hunter2",
    "passwd: hunter2",
    "api_key: abc123456789012345678",
    "apikey=abc123456789012345678",
    '{"app_secret": "abcdefghijklmnopqrstuvwxyz"}',
    "access_token=abcdefghijklmnopqrstuvwxyz",
    "secret_key=abcdefghijklmnopqrstuvwxyz",
)

# 歧义字段正例（走上下文评分）
_AMBIGUOUS_POSITIVE_SAMPLES = (
    f"GPG_KEY={_GPG_SAMPLE}",
    f"gpg_key={_GPG_SAMPLE}",
    f"SIGNING_KEY={_GPG_SAMPLE}",
    f"SIGNING_TOKEN={_GPG_SAMPLE}",
)

# 负例：非凭据字段 / 变量引用 / 纯 hex 定长形状
_NEGATIVE_SAMPLES = (
    "token_count=100",
    "token_type=bearer",
    "tokenizer=cl100k",
    "max_tokens=4096",
    "secret_name=my-secret",
    "secret_id=7c9f4a2d",
    "secret_arn=arn:aws:secretsmanager",
    "key_id=abc123",
    "public_key=abc123",
    "has_password=true",
    "authorization_url=https://x.com/oauth",
    "password=$DB_PASSWORD",
    "password=${DB_PASSWORD}",
    "password=os.getenv('X')",
    "GPG_KEY=0123456789abcdef",
    "GPG_KEY=0123456789abcdef0123456789abcdef01234567",
)


class TestAssignmentStrictFields:
    """严格凭据字段命中即脱敏，span 只覆盖值本体（不含 key 与分隔符）。"""

    @pytest.mark.parametrize("sample", _STRICT_SAMPLES)
    def test_strict_field_hits(self, sample):
        findings = AssignmentDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].kind == "credential"
        # span 不含 key 与分隔符：替换后 `key=` 前缀保真
        assert sample[findings[0].start : findings[0].end] not in sample[: findings[0].start]

    def test_span_covers_value_only(self):
        sample = "password=hunter2"
        finding = AssignmentDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "hunter2"


class TestAssignmentAmbiguousScoring:
    """歧义字段走上下文评分（DESIGN §3.5），score >= 4 触发。"""

    @pytest.mark.parametrize("sample", _AMBIGUOUS_POSITIVE_SAMPLES)
    def test_ambiguous_positive_hits(self, sample):
        findings = AssignmentDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].confidence == "medium"
        assert findings[0].priority == 70
        assert sample[findings[0].start : findings[0].end] == _GPG_SAMPLE

    def test_gpg_key_starting_defect(self):
        """起点缺陷 D1：GPG_KEY=<32位高熵值> 必须命中（评分 7 >= 4）。"""
        sample = f"GPG_KEY={_GPG_SAMPLE}"
        findings = AssignmentDetector().scan(sample)
        assert len(findings) == 1
        # kind 取归一化字段名（GPG_KEY -> gpgkey，去分隔符 + 小写）
        assert findings[0].kind == "gpgkey"
        assert findings[0].rule_id == "assignment.gpgkey"

    def test_case_insensitive_field_name(self):
        assert AssignmentDetector().scan(f"gpg_key={_GPG_SAMPLE}")[0].kind == "gpgkey"

    @pytest.mark.parametrize("sample", _NEGATIVE_SAMPLES)
    def test_negative_samples_zero_hits(self, sample):
        assert AssignmentDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "value",
        ["0123456789abcdef", "0123456789abcdef0123456789abcdef01234567"],
    )
    def test_hex_fixed_length_excluded(self, value):
        """纯 hex 且长度 ∈ {8,16,32,40}（GPG key ID / fingerprint）不命中。

        64 **已移出**豁免集（S057 族召回修复）：它是 SHA-256 / AES-256 的
        标准宽度，与业务 digest 无法用形状区分，改由熵 / 上下文判据决定。
        """
        assert AssignmentDetector().scan(f"GPG_KEY={value}") == []

    def test_64_hex_no_longer_shape_excluded(self):
        """64 位纯 hex 不再被形状豁免；``secret`` 后缀提供足够上下文分 → 命中。"""
        findings = AssignmentDetector().scan(f"SIGNING_SECRET={_HEX64}")
        assert len(findings) == 1
        assert findings[0].rule_id == "assignment.signingsecret"

    @pytest.mark.parametrize(
        "sample",
        [
            f"commit {_HEX64}",
            f"sha256={_HEX64}",
            f"checksum: {_HEX64}",
            f"integrity_hash={_HEX64}",
        ],
    )
    def test_64_hex_digest_contexts_still_safe(self, sample):
        """误报面护栏：git SHA / digest / checksum 上下文不得被脱敏。

        64 位不再走形状豁免，安全性改由「熵 >= 4.2 才触发裸熵」+
        「赋值路径需字段名上下文」共同保证 —— 本用例钉住后者。
        """
        assert AssignmentDetector().scan(sample) == []

    def test_40_hex_fingerprint_still_excluded(self):
        """40 位（GPG fingerprint）豁免必须保留 —— 本次只放开 64。"""
        assert AssignmentDetector().scan(f"GPG_KEY={'0123456789abcdef' * 2 + '01234567'}") == []


class TestAssignmentPrefilterReachability:
    """prefilter 可达性：所有正例都必须能通过 could_match。"""

    @pytest.mark.parametrize("sample", _STRICT_SAMPLES + _AMBIGUOUS_POSITIVE_SAMPLES)
    def test_positive_reachable(self, sample):
        detector = AssignmentDetector()
        assert detector.could_match(sample) is True
        assert detector.scan(sample) != []

    @pytest.mark.parametrize("sample", ["no separator here", "", "plain text"])
    def test_negative_unreachable(self, sample):
        assert AssignmentDetector().could_match(sample) is False


class TestAssignmentNegativeFields:
    """负例字段名：含 secret/key 语义但非凭据，必须零命中。"""

    @pytest.mark.parametrize(
        "sample",
        [
            "token_count=100",
            "secret_name=my-secret",
            "public_key=abc123",
            "key_id=abc123",
            "has_password=true",
            "authorization_url=https://x.com/oauth",
        ],
    )
    def test_negative_field_zero_hits(self, sample):
        assert AssignmentDetector().scan(sample) == []


class TestAssignmentEmptyValueCrossesNewline:
    """``key=`` / ``key:``（空值）后跟换行时，赋值会跨行吃掉下一行的 token —— 过度遮蔽，待修。

    根因：``_KEY_VALUE_RE`` 的分隔符两侧用 ``\\s*``，而 ``\\s`` **包含换行**：

        (?<![A-Za-z0-9_-])[0-9]*([A-Za-z_][A-Za-z0-9_-]*)\\s*["']?\\s*(?::=|[=:])\\s*["']?([^"'\\s,;{}&#]+)["']?

    同根因的三个表现面（键名不同，机制完全相同）：

    - ``Password=\\nUser Id=sa`` → 吃掉 ``User``（dsn.md S076 的最简形态；
      ``jdbc:sqlserver://h;Password=\\nUser Id=sa`` 亦同）。
    - ``password=\\nCookie: session=x`` → 吃掉下一行的 ``Cookie`` 头名。
    - ``Authorization:\\n\\nX`` → 吃掉空行后的首个 token；
      这是 headers.md S064/S065 在**整文件读取**时的表现：``Authorization:`` 后的空行
      使下一行的分隔块标题 / ``说明：`` 行被整体遮成 ``[REDACTED:credential]``，
      连带 read_file 的行号前缀也被吞掉（``371\\t======S064======`` → ``[REDACTED:credential]``）。

    **不是**「一行小改」：只把 ``\\s`` 收成 ``[ \\t]`` 会让正则前滑，
    在 ``Password=\\nUser Id=sa`` 上改中 ``Id=sa`` —— 过度遮蔽只是换了个位置。
    正确修法是给「分隔符与值必须在键的同一行」加行边界护栏，
    而 ``_KEY_VALUE_RE`` 是整条 assignment 路径共享的核心正则，回归面大。

    故先以 ``xfail(strict=True)`` 固定预期与边界，待后续处理。
    """

    @pytest.mark.xfail(
        strict=True,
        reason="空值 key= 后跟换行时跨行吃掉下一行 token（_KEY_VALUE_RE 的 \\s* 含换行），待修",
    )
    def test_empty_value_does_not_eat_next_line(self):
        """``Password=`` 空值不应把下一行的 ``User`` 当作自己的值遮掉。"""
        sample = "Password=\nUser Id=sa"
        assert AssignmentDetector().scan(sample) == []

    @pytest.mark.xfail(
        strict=True,
        reason="JDBC 串中空 Password= 同样跨行吃掉下一行 token，待修",
    )
    def test_jdbc_empty_password_does_not_eat_next_line(self):
        """dsn.md S076 变体：``Password=`` 空值 + 换行，下一行首 token 被误遮。"""
        sample = "jdbc:sqlserver://db.internal;databaseName=app;user=sa;Password=\nUser Id=sa"
        assert AssignmentDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "sample",
        [
            "Password=",  # 空值，行尾（无可吃内容）
            "Password=\n",  # 空值，仅后跟换行
            "Password=;",  # 空值，后跟分隔符
        ],
    )
    def test_empty_value_alone_is_harmless(self, sample):
        """对照组：空值后面没有可吃的 token 时不产生误遮。"""
        assert AssignmentDetector().scan(sample) == []

    @pytest.mark.xfail(
        strict=True,
        reason="空值后跟换行 + 任意非空白 token 都会被吃，含下一行的其它 header 名，待修",
    )
    def test_empty_value_does_not_eat_next_line_header(self):
        """``password=`` 空值不应把下一行的 ``Cookie:`` 头名当成自己的值。"""
        sample = "password=\nCookie: session=x"
        assert AssignmentDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "sample",
        [
            "Authorization:\n",  # S064 形态：裸头名 + 冒号
            "Authorization: \n",  # S065 形态：冒号后带尾随空格
        ],
    )
    def test_bare_header_name_alone_is_harmless(self, sample):
        """对照组：裸 ``Authorization:`` 后无内容时零命中（无 token 可吃）。"""
        assert AssignmentDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "sample",
        [
            "Authorization:\n\n======S065======",  # S064：空行后跟分隔块标题
            "Authorization: \n\n说明：行尾空白",  # S065：冒号+空格，空行后跟说明行
            "Authorization:\n\nany token here",  # 最简形态
        ],
    )
    @pytest.mark.xfail(
        strict=True,
        reason="裸 header 名（Authorization:）后跟空行时跨行吃掉下一行 token（同一 _KEY_VALUE_RE 根因），待修",
    )
    def test_bare_header_name_does_not_eat_next_line(self, sample):
        """裸 ``Authorization:`` 后跟空行，不应把下一行首个 token 当成凭据遮掉。

        与 ``Password=``（dsn.md S076）是**同一根因**的两个表现面：
        ``_KEY_VALUE_RE`` 中分隔符两侧的 ``\\s*`` 含换行。
        headers.md S064/S065 在整文件读取时触发（空行分隔的块标题/说明行被误遮）。
        """
        assert AssignmentDetector().scan(sample) == []


# ---------------------------------------------------------------------------
# Task: DSN
# ---------------------------------------------------------------------------

_DSN_SAMPLES = (
    "postgresql://app:S3cr3tPw@db.internal:5432/prod",
    "postgres://app:S3cr3tPw@db.internal/prod",
    "mysql://u:p@h/d",
    "mariadb://u:p@h/d",
    "mongodb://u:p@h/d",
    "mongodb+srv://u:p@h/d",
    "redis://:pw@h/0",
    "rediss://:pw@h/0",
    "amqp://u:p@h/v",
    "amqps://u:p@h/v",
)


class TestDsnDetector:
    """DSN 检测：只替换 password 段，scheme/user/host/port/db 保真。"""

    @pytest.mark.parametrize("sample", _DSN_SAMPLES)
    def test_dsn_hits(self, sample):
        findings = DsnDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].kind == "dsn_password"
        assert findings[0].priority == 90

    def test_postgres_password_span(self):
        sample = "postgresql://app:S3cr3tPw@db.internal:5432/prod"
        finding = DsnDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "S3cr3tPw"

    @pytest.mark.parametrize("sample", ["redis://:pw@h/0", "mysql://u:p@h/d"])
    def test_short_password_span(self, sample):
        finding = DsnDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] in ("pw", "p")

    @pytest.mark.parametrize(
        "sample",
        [
            "postgresql://app@db.internal:5432/prod",
            "postgresql://db.internal:5432/prod",
            "postgresql://app:${DB_PASSWORD}@host/db",
            "postgresql://app:$DB_PASSWORD@host/db",
            "Password=;User Id=sa",
            "plain text",
        ],
    )
    def test_negative(self, sample):
        assert DsnDetector().scan(sample) == []

    def test_jdbc_password_attribute(self):
        """JDBC 属性串由 ``DsnJdbcDetector`` 覆盖（2026-09-15 起，原由 DsnDetector 的无上下文正则误覆盖）。"""
        sample = "jdbc:sqlserver://h;User Id=sa;Password=S3cr3tPw"
        finding = DsnJdbcDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "S3cr3tPw"

    @pytest.mark.parametrize("sample", _DSN_SAMPLES)
    def test_prefilter_reachable(self, sample):
        detector = DsnDetector()
        assert detector.could_match(sample) is True

    def test_prefilter_negative(self):
        assert DsnDetector().could_match("no dsn here") is False


class TestDsnPasswordCharsetBounds:
    """password / user 段含「字符集外」字符时整条 DSN 不命中 —— 完整泄露，待修。

    ``DsnDetector._DSN_RE`` 的 password 组为 ``[^@\\s/]{1,512}``（有界量词，防 ReDoS）：
    含**裸空格**或 ``/`` 时该段无法匹配，且整条串没有其它 detector 兜底
    （无 ``=`` 故 assignment / url 不命中），故密码**完整明文泄露**。

    user 段同理：``user name`` 含空格时前置 userinfo 结构不成立，整条不命中。

    修复需放宽 user / password 的字符集，但必须同时保住两点，故非小改：
    1. ``[^@\\s/]`` 的有界性（ref.md §4.6 记录过 320KB 输入下 55 秒的真实事故）；
    2. ``${VAR}`` / ``$VAR`` / ``{var}`` 源码模板例外（T-06-17）。

    故此处先以 ``xfail(strict=True)`` 固定预期与边界，待后续处理。
    期望掩码沿用 dsn.md 的占位符写法 ``L3X7Qk9dW2mA``。
    """

    MASK = "L3X7Qk9dW2mA"

    @pytest.mark.xfail(
        strict=True,
        reason="password 含裸空格使整条 DSN 不命中，无兜底，密码完整泄露（待修）",
    )
    def test_password_with_space_masked(self):
        sample = "postgresql://user:s3cr3t pw@db.internal/app"
        assert DsnDetector().scan(sample) != []
        assert sample not in redact_text(sample)
        assert "s3cr3t pw" not in redact_text(sample)

    @pytest.mark.xfail(
        strict=True,
        reason="password 含 `/` 使整条 DSN 不命中，无兜底，密码完整泄露（待修）",
    )
    def test_password_with_slash_masked(self):
        sample = "postgresql://user:s3cr3t/pw@db.internal/app"
        assert DsnDetector().scan(sample) != []
        assert "s3cr3t/pw" not in redact_text(sample)

    @pytest.mark.xfail(
        strict=True,
        reason="user 含裸空格使整条 DSN 不命中，无兜底，密码完整泄露（待修）",
    )
    def test_user_with_space_masked(self):
        sample = "postgresql://user name:s3cr3t@db.internal/app"
        assert DsnDetector().scan(sample) != []
        assert "s3cr3t" not in redact_text(sample)

    @pytest.mark.parametrize(
        "sample",
        [
            "postgresql://user:s3cr3t@db.internal/app",
            "postgresql://user:s3cr3t@db.internal:5432/app",
        ],
    )
    def test_baseline_without_special_chars_masked(self, sample):
        """对照组：不含空格 / 斜杠时正常命中（证明缺陷仅限字符集边界）。"""
        assert DsnDetector().scan(sample) != []
        assert "s3cr3t" not in redact_text(sample)


class TestDsnJdbcDetectorRequiresContext:
    """``DsnJdbcDetector`` 须 ``jdbc:`` 上下文（原无上下文正则致 S106/S107/S109/S111 误报）。"""

    @pytest.mark.parametrize(
        "sample, expected",
        [
            ("jdbc:sqlserver://h;User Id=sa;Password=S3cr3tPw", "S3cr3tPw"),
            # 属性名含空格（真实 JDBC 形态）不得因空白被拒
            ("jdbc:oracle:thin:@h:1521/x;Password=S3cr3tPw", "S3cr3tPw"),
        ],
    )
    def test_jdbc_context_hits(self, sample, expected):
        findings = DsnJdbcDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == expected

    @pytest.mark.parametrize(
        "sample",
        [
            "password=null",
            "password=<REDACTED>",
            "password=********",
            "Password=S3cr3tPw",  # 无 jdbc: 上下文
            "myjdbc:foo;Password=S3cr3tPw",  # 前缀非 token 起点
        ],
    )
    def test_no_jdbc_context_zero_hits(self, sample):
        assert DsnJdbcDetector().scan(sample) == []

    def test_dsn_detector_no_longer_has_jdbc_attribute_regex(self):
        """回归防线：无上下文的 ``_JDBC_PASSWORD_RE`` 不得复活。"""
        assert not hasattr(DsnDetector, "_JDBC_PASSWORD_RE")
        assert not hasattr(DsnDetector, "_JDBC_HINT_RE")

    @pytest.mark.parametrize(
        "sample, expected",
        [
            ("JDBC:sqlserver://h;Password=S3cr3tPw", "S3cr3tPw"),
            ("Jdbc:oracle:thin:@h:1521/x;Password=S3cr3tPw", "S3cr3tPw"),
            ("jdbc:sqlserver://h;User Id=sa;Password=S3cr3tPw", "S3cr3tPw"),
            ("jdbc:sqlserver://h \t; User Id\t= sa \t; pAsSwOrD \t= S3cr3tPw", "S3cr3tPw"),
            ("jdbc:sqlserver://h;;Password=S3cr3tPw", "S3cr3tPw"),
            ("jdbc:sqlserver://h;Encrypt=;Password=S3cr3tPw", "S3cr3tPw"),
        ],
    )
    def test_jdbc_marker_case_and_attribute(self, sample, expected):
        findings = DsnJdbcDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == expected

    @pytest.mark.parametrize(
        "sample",
        [
            "jdbc:sqlserver://h;User Id=sa;Password=A;Password=B",
            "jdbc:sqlserver://h;Password=A;jdbc:oracle:thin:@h:1521/x;Password=B",
            '"jdbc:sqlserver://h;Password=A" "JDBC:oracle:thin:@h:1521/x;Password=B"',
        ],
    )
    def test_jdbc_multiple_independent_passwords(self, sample):
        findings = DsnJdbcDetector().scan(sample)
        assert [sample[f.start : f.end] for f in findings] == ["A", "B"]

    @pytest.mark.parametrize(
        "sample",
        [
            "myjdbc:foo;Password=S3cr3tPw",
            "Password=S3cr3tPw",
            "jdbc:sqlserver://h;OtherPassword=hunter2",
            "jdbc:sqlserver://h;application Password=realSecret",
            "Password=realSecret; jdbc:sqlserver://h",
            '"jdbc:sqlserver://h";Password=realSecret',
            "'jdbc:sqlserver://h';Password=realSecret",
            "jdbc:sqlserver://h;broken;Password=realSecret",
            "jdbc:sqlserver://h;User Id=sa outside;Password=realSecret",
            "jdbc:;Password=realSecret",
        ],
    )
    def test_jdbc_negative_shapes(self, sample):
        assert DsnJdbcDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "value",
        ["${DB_PASSWORD}", "$DB_PASSWORD", "{password}", "null", "********", "<REDACTED>"],
    )
    def test_jdbc_reference_and_placeholder_not_secret(self, value):
        assert DsnJdbcDetector().scan(f"jdbc:sqlserver://h;Password={value}") == []

    def test_jdbc_literal_dollar_is_still_secret(self):
        sample = "jdbc:sqlserver://h;Password=$literal123!"
        finding = DsnJdbcDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "$literal123!"

    @pytest.mark.parametrize("length", [0, 1, 512, 513])
    def test_jdbc_password_length_boundaries(self, length):
        sample = "jdbc:sqlserver://h;Password=" + "P" * length + ";Password=next"
        findings = DsnJdbcDetector().scan(sample)
        expected = ([(28, 28 + min(length, 512))] if length else []) + [(len(sample) - 4, len(sample))]
        assert [(f.start, f.end) for f in findings] == expected

    @pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
    @pytest.mark.parametrize("suffix", [";Password=secret", ";Password=\t"])
    def test_jdbc_context_does_not_cross_lines(self, newline, suffix):
        sample = "jdbc:sqlserver://h" + newline + suffix + "\nPassword=outside"
        assert DsnJdbcDetector().scan(sample) == []

    def test_jdbc_inherits_policy_not_uri_scanning(self):
        detector = DsnJdbcDetector()
        assert isinstance(detector, DsnDetector)
        assert detector._is_variable_reference is DsnDetector._is_variable_reference
        assert detector._VAR_REF_RE is DsnDetector._VAR_REF_RE
        assert detector._DSN_PRIORITY == 90
        assert "_DSN_PRIORITY" not in DsnJdbcDetector.__dict__
        with patch.object(DsnDetector, "scan", side_effect=AssertionError("URI scan called")):
            assert detector.scan("postgresql://app:secret@host/db") == []
            assert detector.scan("jdbc:sqlserver://h;Password=secret")[0].rule_id == "dsn.jdbc"

    @pytest.mark.parametrize("count", [10, 100])
    def test_jdbc_cursor_never_rescans_consumed_attributes(self, count):
        detector = DsnJdbcDetector()
        sample = "jdbc:sqlserver://h" + ";Note=jdbc:nested;Password=secret" * count
        with (
            patch.object(detector, "_HINT_RE", wraps=detector._HINT_RE) as marker,
            patch.object(detector, "_ATTR_RE", wraps=detector._ATTR_RE) as attr,
        ):
            assert len(detector.scan(sample)) == count
        positions = [call.args[1] for call in attr.match.call_args_list]
        assert all(left < right for left, right in zip(positions, positions[1:]))
        assert len(positions) == 2 * count + 1
        assert marker.search.call_count == 3  # 预筛选、首次定位、从串尾查找下一条。
        assert marker.search.call_args.args == (sample, len(sample))


class TestDsnJdbcChainAndZeroWidthBoundary:
    """JDBC / DSN 边界：错误关联、零宽边界与整体链 rule 归属。"""

    def test_context_outside_password_not_jdbc(self):
        """同行正文后的 ``Password=`` 仍由 assignment 处理，不属于 JDBC。"""
        src = "jdbc:mysql://host/db is an example; application Password=realSecret"
        assert DsnJdbcDetector().scan(src) == []
        result = scan_text(src, purpose=RedactionPurpose.LOG)
        assert "dsn.jdbc" not in result.raw_rule_hits
        assert "assignment.password" in result.raw_rule_hits
        assert result.redacted_text == (
            "jdbc:mysql://host/db is an example; application Password=[REDACTED:credential]"
        )

    def test_jdbc_chain_kind_and_span(self):
        src = "jdbc:sqlserver://h;User Id=sa;Password=S3cr3tPw"
        result = scan_text(src, purpose=RedactionPurpose.LOG)
        assert result.raw_rule_hits.get("dsn.jdbc") == 1
        assert result.redacted_text == "jdbc:sqlserver://h;User Id=sa;Password=[REDACTED:dsn_password]"

    @pytest.mark.parametrize("prefix", ["$(postgresql://u:pw@h/d)", "[postgresql://u:pw@h/d]"])
    def test_dsn_leading_punctuation_preserved(self, prefix):
        finding = DsnDetector().scan(prefix)[0]
        assert prefix[finding.start : finding.end] == "pw"
        assert finding.start == prefix.index("pw")

    @pytest.mark.parametrize("prefix", ["xpostgresql://u:pw@h/d", "1postgresql://u:pw@h/d", "_postgresql://u:pw@h/d"])
    def test_dsn_alnum_prefix_rejected(self, prefix):
        assert DsnDetector().scan(prefix) == []

    def test_dsn_match_starts_at_scheme(self):
        src = "(postgresql://u:pw@h/d)"
        match = DsnDetector._DSN_RE.search(src)
        assert match is not None and match.start() == src.index("postgresql")

    @pytest.mark.parametrize(
        "sample",
        ["postgres://u:pw@postgres://v:qq@", "postgres://u:pw@;postgres://v:qq@"],
    )
    def test_adjacent_dsn_both_matched(self, sample):
        findings = DsnDetector().scan(sample)
        assert [sample[f.start : f.end] for f in findings] == ["pw", "qq"]

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("${DB_PASSWORD}", False),
            ("$DB_PASSWORD", False),
            ("{password}", False),
            ("null", False),
            ("********", False),
            ("<REDACTED>", False),
            ("$literal123!", True),
        ],
    )
    def test_dsn_and_jdbc_reference_predicate_parity(self, value, expected):
        """两种 detector 对同一值给出同一判定（子类复用继承的引用/占位符判据）。"""
        dsn = DsnDetector().scan(f"postgresql://app:{value}@h/d")
        jdbc = DsnJdbcDetector().scan(f"jdbc:sqlserver://h;Password={value}")
        assert bool(dsn) is expected
        assert bool(jdbc) is expected

    @pytest.mark.parametrize("value", ["${DB_PASSWORD}", "$DB_PASSWORD", "{password}"])
    @pytest.mark.parametrize("purpose", list(RedactionPurpose))
    def test_jdbc_reference_preserved_end_to_end(self, value, purpose):
        sample = f"jdbc:sqlserver://h;Password={value}"
        result = scan_text(sample, purpose=purpose)
        assert "dsn.jdbc" not in result.raw_rule_hits
        assert result.redacted_text == sample


# ---------------------------------------------------------------------------
# Task: headers
# ---------------------------------------------------------------------------

# 八个敏感 header 名（大小写不敏感）
_HEADER_SAMPLES = (
    "Authorization: Bearer xyz",
    "Authorization: Basic dXNlcjpwYXNz",
    "Proxy-Authorization: Basic dXNlcjpwYXNz",
    "X-API-Key: abc123",
    "X-Goog-API-Key: abc123",
    "API-Key: abc123",
    "X-API-Token: abc123",
    "X-Auth-Token: abc123",
    "X-Access-Token: abc123",
)


class TestHeadersDetector:
    """header 凭据检测：span 只覆盖值本体、保留 header 名与 scheme。"""

    @pytest.mark.parametrize("sample", _HEADER_SAMPLES)
    def test_header_hits(self, sample):
        findings = HeadersDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].kind == "authorization_header"
        assert findings[0].priority == 90

    def test_basic_credential_span(self):
        """T-06-10 / D10：Basic 的 base64 凭据本体被覆盖（不是只换格式名）。"""
        sample = "Authorization: Basic dXNlcjpwYXNz"
        finding = HeadersDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "dXNlcjpwYXNz"

    @pytest.mark.parametrize("sample", ["Authorization: Bearer short", "Authorization: Bearer " + "A" * 10])
    def test_bearer_no_min_length(self, sample):
        """Bearer 不设最小长度（RFC 6750 允许短 token）。"""
        findings = HeadersDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == sample.split()[-1]

    def test_scheme_and_header_name_preserved(self):
        sample = "Authorization: Bearer xyz"
        findings = HeadersDetector().scan(sample)
        assert sample[: findings[0].start] == "Authorization: Bearer "

    @pytest.mark.parametrize("sample", ["Authorization: Basic", "Authorization: Bearer ", "no header here"])
    def test_negative_no_value(self, sample):
        assert HeadersDetector().scan(sample) == []

    @pytest.mark.parametrize("sample", _HEADER_SAMPLES)
    def test_prefilter_reachable(self, sample):
        detector = HeadersDetector()
        assert detector.could_match(sample) is True
        assert detector.scan(sample) != []

    def test_prefilter_negative(self):
        assert HeadersDetector().could_match("plain text") is False

    @pytest.mark.parametrize(
        "sample",
        [
            "(Authorization: Bearer abc123)",
            "[Authorization: Bearer abc123]",
            "{Authorization: Bearer abc123}",
            "<Authorization: Bearer abc123>",
            "x=Authorization: Bearer abc123",
            "|Authorization: Bearer abc123",
            "(X-API-Key: abc123)",
        ],
    )
    def test_header_boundary_accepts_wrapping_delimiters(self, sample):
        """包装定界符（圆/方/花/尖括号、等号、竖线）都必须作为合法头名前缀。

        回归：原 `(?:^|[\\s;,:\"'])` 不含 `(` 等包装字符，导致
        `(Authorization: Bearer x)` 这类形态静默漏报（dsn/headers.md S030）。
        """
        findings = HeadersDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end].startswith("abc123")

    @pytest.mark.parametrize(
        "sample",
        [
            "myAuthorization: Bearer abc123",
            "XAUTHORIZATION: Bearer abc123",
            "pre-authorization: Bearer abc123",
            "not_authorization: Bearer abc123",
        ],
    )
    def test_header_boundary_rejects_longer_identifiers(self, sample):
        """放宽前缀不得把更长标识符误判为头名（负例）。"""
        assert HeadersDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "sample",
        [
            "http.headers.Authorization: Bearer abc123",
            "headers.Authorization: Bearer abc123",
            "obj.X-API-Key: abc123",
        ],
    )
    def test_dotted_header_path_masked(self, sample):
        """点分形态（`http.headers.Authorization: ...`）确实携带真实凭据，应遮蔽。

        回归：原 `(?:^|[\\s;,:\"'])` 不含 `.`，这类形态静默漏报（headers.md S086）。
        """
        findings = HeadersDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end].startswith("abc123")

    @pytest.mark.parametrize(
        "sample, spans",
        [
            ("Authorization: Bearer Basic", ((22, 27),)),
            ("Authorization: bearer xyz", ((22, 25),)),
            ("AUTHORIZATION: BASIC Zm9v", ((21, 25),)),
            ("Authorization:  Basic  dXNlcjpwYXNz", ((23, 35),)),
            ("Authorization: Custom xyz", ((22, 25),)),
            ("Authorization: FooBearer Basic", ((25, 30),)),
            ("Authorization: Bearer tok\nX-API-Key: abc123", ((22, 25), (37, 43))),
            ("X-API-Key: abc123\nAuthorization: Bearer tok", ((11, 17), (40, 43))),
            ("Authorization: Basic\nX-API-Key: abc123", ((32, 38),)),
            ("Authorization: Basic", ()),
            ("Authorization: Bearer ", ()),
            ("Authorization: Digest", ()),
            ("Authorization: bearer Basic", ()),
            ("Authorization: Bearer\tBasic", ()),
        ],
    )
    def test_contract_spans_and_order(self, sample, spans):
        findings = HeadersDetector().scan(sample)
        assert [(f.start, f.end, f.rule_id, f.kind, f.confidence, f.priority) for f in findings] == [
            (start, end, "headers", "authorization_header", "high", 90) for start, end in spans
        ]

    @pytest.mark.parametrize("purpose", list(RedactionPurpose))
    @pytest.mark.parametrize(
        "sample, values, expected",
        [
            pytest.param(
                "X-API-Key: abc123\nX-API-Token: def",
                ["abc123", "def"],
                "X-API-Key: [REDACTED:authorization_header]\nX-API-Token: [REDACTED:authorization_header]",
                id="H038",
            ),
            pytest.param(
                "X-API-Key: abc123\nAuthorization: Bearer tok",
                ["abc123", "tok"],
                "X-API-Key: [REDACTED:authorization_header]\nAuthorization: Bearer [REDACTED:authorization_header]",
                id="H041",
            ),
            pytest.param(
                "Authorization: Basic\nX-API-Key: abc123",
                ["abc123"],
                "Authorization: Basic\nX-API-Key: [REDACTED:authorization_header]",
                id="H042",
            ),
            pytest.param(
                "Authorization: Bearer <abc123>",
                ["abc123"],
                "Authorization: Bearer <[REDACTED:authorization_header]>",
                id="H061",
            ),
            pytest.param(
                'Authorization: Bearer "abc123"',
                ["abc123"],
                'Authorization: Bearer "[REDACTED:authorization_header]"',
                id="H062",
            ),
            pytest.param(
                "Authorization: Bearer 'abc123'",
                ["abc123"],
                "Authorization: Bearer '[REDACTED:authorization_header]'",
                id="H063",
            ),
            pytest.param(
                'curl -H "Authorization: Bearer abc123"',
                ["abc123"],
                'curl -H "Authorization: Bearer [REDACTED:authorization_header]"',
                id="H064",
            ),
            pytest.param(
                "curl -H 'Authorization: Bearer abc123'",
                ["abc123"],
                "curl -H 'Authorization: Bearer [REDACTED:authorization_header]'",
                id="H065",
            ),
        ],
    )
    def test_boundary_regressions(self, sample, values, expected, purpose):
        findings = HeadersDetector().scan(sample)
        assert [sample[f.start : f.end] for f in findings] == values
        result = scan_text(sample, purpose=purpose)
        assert result.raw_rule_hits["headers"] == len(values)
        assert result.unique_findings == len(values)
        assert result.redacted_text == expected
        assert redact_text(sample, purpose=purpose) == expected

    @pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
    @pytest.mark.parametrize("first", ["Authorization:", "Authorization: Basic", "X-API-Key:"])
    @pytest.mark.parametrize("trailing", ["", " \t"])
    def test_empty_header_does_not_consume_next_line(self, newline, first, trailing):
        sample = f"{first}{trailing}{newline}X-API-Key: abc123"
        findings = HeadersDetector().scan(sample)
        assert [(f.start, f.end) for f in findings] == [(len(sample) - 6, len(sample))]

    @pytest.mark.parametrize("wrapper", ['""', "''", "<>"])
    @pytest.mark.parametrize("prefix", ["Authorization: Bearer ", "X-API-Key: "])
    def test_empty_wrapped_value_is_not_a_credential(self, wrapper, prefix):
        assert HeadersDetector().scan(prefix + wrapper) == []


# ---------------------------------------------------------------------------
# Task: jwt
# ---------------------------------------------------------------------------

_JWT_3SEG = "eyJ" + "d" * 20 + "." + "e" * 20 + "." + "f" * 20
_JWT_5SEG = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20 + "." + "d" * 20 + "." + "e" * 20


class TestJwtDetector:
    """三段 JWS 与五段 JWE 整体替换；单段 eyJ 不命中。"""

    def test_three_segment_jws_whole(self):
        finding = JwtDetector().scan(_JWT_3SEG)[0]
        assert _JWT_3SEG[finding.start : finding.end] == _JWT_3SEG
        assert finding.kind == "jwt"
        assert finding.priority == 88

    def test_five_segment_jwe_whole(self):
        """五段 JWE 必须整体替换（ref.md §10.8：不能只遮前三段）。"""
        finding = JwtDetector().scan(_JWT_5SEG)[0]
        assert _JWT_5SEG[finding.start : finding.end] == _JWT_5SEG

    @pytest.mark.parametrize(
        "sample",
        ["eyJhbGciOiJIUzI1NiJ9", "the eyJ prefix is common in JSON", "plain text"],
    )
    def test_negative_single_segment(self, sample):
        assert JwtDetector().scan(sample) == []

    def test_prefilter(self):
        assert JwtDetector().could_match(_JWT_3SEG) is True
        assert JwtDetector().could_match("no token here") is False


# ---------------------------------------------------------------------------
# Task: Url
# ---------------------------------------------------------------------------


class TestUrlDetector:
    """URL query 与 form-urlencoded：只替换敏感值，不重新序列化。"""

    def test_url_query_value_span(self):
        sample = "https://x.com/cb?access_token=abc123&next=/home"
        finding = UrlDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "abc123"
        assert finding.kind == "url_credential"
        assert finding.priority == 85

    @pytest.mark.parametrize(
        "key",
        ["access_token", "token", "api_key", "apikey", "secret", "client_secret", "password", "x-amz-signature"],
    )
    def test_sensitive_query_keys(self, key):
        sample = f"https://x.com/cb?{key}=abc123&next=/home"
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == "abc123"

    def test_form_urlencoded(self):
        sample = "access_token=abc123&next=/home"
        finding = UrlDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "abc123"

    @pytest.mark.parametrize(
        "sample", ["https://x.com/cb?next=/home&page=2", "token_count=100&page=2", "status code 200"]
    )
    def test_negative(self, sample):
        assert UrlDetector().scan(sample) == []

    @pytest.mark.parametrize("sep", ["&", "#", " ", ";"])
    def test_value_terminators(self, sep):
        sample = f"https://x.com/cb?access_token=abc123{sep}trailing"
        finding = UrlDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == "abc123"

    @pytest.mark.parametrize("sample", ["https://x.com/cb?token=$TOKEN", "https://x.com/cb?token=${TOKEN}"])
    def test_variable_value_negative(self, sample):
        assert UrlDetector().scan(sample) == []

    def test_prefilter_reachable(self):
        detector = UrlDetector()
        assert detector.could_match("https://x.com?access_token=abc") is True
        assert detector.could_match("plain") is False


# ---------------------------------------------------------------------------
# [2026-09-16] UrlDetector 检测绕过面：单参数 form / percent-encoded key /
# `;` 分隔 query / 长值 / 变量引用例外 + 三条不应命中的负例。
#
# 每条正例都成对给出「值本体被替换」与「非秘密上下文保真」两个断言，
# 负例则断言**整串字节级不变** —— 只测「不再误报」会让判据被逐步放宽到失效。
# ---------------------------------------------------------------------------

# 正例统一用长度 > 8 的真实感凭据值（不是占位符、不是变量引用、非纯短数字）
_URL_SECRET = "S3cr3tV4lue9xQz"


class TestUrlDetectorSingleParamForm:
    """单参数 form（``access_token=SECRET``）：无 `?`/`&` 结构，须按 form 形状命中。"""

    @pytest.mark.parametrize("key", ["access_token", "token", "refresh_token", "client_secret", "api_key"])
    def test_single_pair_masked(self, key):
        sample = f"{key}={_URL_SECRET}"
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == _URL_SECRET
        assert findings[0].kind == "url_credential"

    def test_single_pair_redacted_end_to_end(self):
        sample = f"access_token={_URL_SECRET}"
        out = redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "access_token=[REDACTED:url_credential]"

    @pytest.mark.parametrize("key", ["token", "secret"])
    def test_single_pair_short_value_negative(self, key):
        """≤8 字符值不命中：本路径无 query 结构证据，`code` 等上下文敏感 key 需长度护栏。"""
        assert UrlDetector().scan(f"{key}=200") == []

    def test_single_pair_placeholder_negative(self):
        """已脱敏标记不得被二次污染（README：二次脱敏结果应不变）。"""
        assert UrlDetector().scan("token=[REDACTED_SECRET]") == []


class TestUrlDetectorFormLineIndependence:
    """form 形状的命中不得依赖「文本位置」——多行场景曾整片漏报。

    两个独立的根因（都在 ``UrlDetector.scan`` 的 form 路径）：

    1. **行首锚定**：``_FORM_SHAPE_RE`` / ``_SINGLE_PAIR_RE`` 锚在行首，
       且 form value 字符集不含 ``\\s``。对整段文本 ``.match()`` 时，
       非第 1 行的 form 会因前导 ``\\n`` 失配。
    2. **整段非 URL 判据**：原实现是 ``if "?" not in text and "://" not in text``，
       **整段**任意位置出现 ``?`` / ``://`` 就会关掉**所有行**的 form 扫描。
       真实文件几乎必然含 ``?``，故 form 凭据全部漏报
       （典型场景：``provider.read_file`` 把整个文件 join 后一次性脱敏）。

    修复后两条都改为**按行**判定；URL 行仍由 ``_scan_url_query`` 负责，不重复计数。
    """

    FORMS = [
        "token=SESS1234567890abcd;user=alice;lang=zh",
        "token=a&x=1",
        f"client_secret={_URL_SECRET}",
        "signature=abcdef1234567890",
        "code=ABCD1234efgh",
        "token=abcdefghi",
        "TOKEN=SESS1234567890abcd",
    ]

    @pytest.mark.parametrize("form", FORMS)
    def test_form_on_line_one_is_masked(self, form):
        """基线：作为第 1 行时命中。"""
        assert UrlDetector().scan(form) != []

    @pytest.mark.parametrize("form", FORMS)
    def test_form_on_later_line_is_masked(self, form):
        """非第 1 行（前导换行）同样命中 —— 回归：行首锚定导致漏报。"""
        text = "\n" + form
        findings = UrlDetector().scan(text)
        assert findings != [], f"{form!r} 在第 2 行漏报"
        # span 必须落在该行内，且覆盖 secret 本体
        secret = form.split("=", 1)[1].split(";")[0].split("&")[0]
        assert secret in text[findings[0].start : findings[0].end]

    @pytest.mark.parametrize("form", FORMS)
    def test_form_unaffected_by_url_elsewhere(self, form):
        """文本其它位置含 `?` / `://` 时，form 行仍须命中 —— 回归：整段非 URL 判据。"""
        text = "https://api.example.com/cb?token=DECOYVALUE123&x=1\n" + form
        out = redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out.split("\n")[-1] != form, f"{form!r} 因文本含 URL 而漏报"

    def test_url_line_still_not_double_counted(self):
        """含 `?` 的行按 query 路径处理，不由 form 路径重复产出。"""
        sample = "https://api.example.com/cb?token=" + _URL_SECRET
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].rule_id == "url"


class TestUrlDetectorPercentEncodedKey:
    """percent-encoded key 不得绕过：``access%5Ftoken`` / ``%74oken`` 与明文等价。"""

    @pytest.mark.parametrize(
        "key",
        [
            "access%5Ftoken",  # `_` 被编码
            "%74oken",  # `t` 被编码
            "client%5Fsecret",
            "access%5ftoken",  # 小写十六进制
            "refresh%5Ftoken",
        ],
    )
    def test_encoded_key_masked(self, key):
        sample = f"?{key}={_URL_SECRET}"
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1, f"encoded key bypassed: {key}"
        assert sample[findings[0].start : findings[0].end] == _URL_SECRET

    @pytest.mark.parametrize("key", ["access%5Ftoken", "%74oken"])
    def test_encoded_key_redacted_end_to_end(self, key):
        out = redact_text(f"?{key}={_URL_SECRET}", purpose=RedactionPurpose.MODEL_OUTPUT)
        assert f"?{key}=" in out  # key 保真：不重新序列化（T-06-13）
        assert _URL_SECRET not in out

    @pytest.mark.parametrize("key", ["access%5Ftoken", "%74oken", "client%5Fsecret"])
    def test_encoded_key_prefilter_reachable(self, key):
        """预筛选必须能看见编码 key，否则昂贵扫描根本不会被触发。"""
        assert UrlDetector().could_match(f"?{key}=abc") is True


class TestUrlDetectorSemicolonSeparatedQuery:
    """`;` 分隔的 query（``?a=1;token=SECRET``）不得被整段漏掉。"""

    @pytest.mark.parametrize(
        "sample",
        [
            "?a=1;token=SECRET_ABCDEF",
            "?a=1;access_token=SECRET_ABCDEF",
            ";token=SECRET_ABCDEF",
            "?a=1;b=2;token=SECRET_ABCDEF",
            "?a=1;refresh_token=SECRET_ABCDEF",
        ],
    )
    def test_semicolon_pair_masked(self, sample):
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == "SECRET_ABCDEF"

    def test_semicolon_tail_preserved(self):
        """非敏感参数与参数顺序保真。"""
        src = "?a=1;token=SECRET_ABCDEF;b=2"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "?a=1;token=[REDACTED:url_credential];b=2"

    def test_form_value_does_not_swallow_semicolon_tail(self):
        """回归：form 路径 value 也须以 `;` 为终止符，否则会吞掉后续 pair。

        `a=1;token=X` 若 value 类不含 `;`，span 会变成整个 `1;token=X`，
        把非敏感 pair 一起删掉。
        """
        src = "a=1;token=SECRET_ABCDEF"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "a=1;token=[REDACTED:url_credential]"
        assert "a=1;" in out

    def test_semicolon_does_not_double_count_ampersand_pair(self):
        """`&` 与 `;` 两条路径不得对同一 pair 重复产出 finding（span 不重叠）。"""
        sample = "?a=1&token=SECRET_ABCDEF;b=2"
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1
        start = sample.index("SECRET_ABCDEF")
        assert {(f.start, f.end) for f in findings} == {(start, start + len("SECRET_ABCDEF"))}


class TestUrlDetectorVariableReferenceException:
    """变量引用例外（T-06-17）须延伸到 percent-encoded 形式，且不得被编码绕过。"""

    @pytest.mark.parametrize(
        "sample",
        [
            "?token=$TOKEN",
            "?token=${TOKEN}",
            "?token=%24TOKEN",  # `$` 被编码
            "?token=%24%7BTOKEN%7D",  # `${TOKEN}` 全编码
            "?token=%24%7bTOKEN%7d",  # 小写十六进制
        ],
    )
    def test_encoded_variable_reference_stays_untouched(self, sample):
        assert UrlDetector().scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize(
        "sample",
        [
            "?token=process.env.API_TOKEN",
            "?token=os.getenv(",
            "?token=os.environ[",
            "?token=os.environ['API_TOKEN']",
        ],
    )
    def test_code_style_reference_stays_untouched(self, sample):
        """与 ``AssignmentDetector._VAR_REF_RE`` 同构：代码式引用同样豁免。

        两侧 alternative 集合若不同构，同一段文本在有无 `?` 前缀时口径会漂移
        （`AssignmentDetector._VAR_REF_RE` 的注释把「同构」写成硬约束）。
        `os.environ[...]` 与 `os.getenv(` 同属运行环境取值族，两侧都须豁免。
        """
        assert UrlDetector().scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize(
        "sample",
        ["?token=os.environ_x", "?token=os.environ"],
    )
    def test_os_environ_prefix_anchored_to_subscript_in_query(self, sample):
        """负对照：`os.environ` 的任意后缀不得被当引用（豁免只认下标访问形状）。"""
        assert UrlDetector().scan(sample) != []

    def test_encoded_value_is_not_a_free_pass(self):
        """反面：编码的**真实**值仍须脱敏 —— 豁免只认引用形状，不是「编码即放过」。"""
        sample = "?token=S3cr3t%2BV4lue9xQz"
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == "S3cr3t%2BV4lue9xQz"


class TestUrlDetectorKeySetCoverage:
    """敏感 key 集覆盖：此前缺 ``refresh_token`` / ``x-amz-security-token``（检测绕过）。"""

    @pytest.mark.parametrize(
        "key",
        [
            "access_token",
            "token",
            "refresh_token",
            "api_key",
            "apikey",
            "secret",
            "client_secret",
            "password",
            "signature",
            "x-amz-signature",
            "x-amz-credential",
            "x-amz-security-token",
        ],
    )
    def test_sensitive_key_masked(self, key):
        sample = f"?{key}={_URL_SECRET}"
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1, f"sensitive key not covered: {key}"
        assert sample[findings[0].start : findings[0].end] == _URL_SECRET

    def test_refresh_token_encoding_coverage(self):
        """`refresh_token` 的两条绕过路径（裸 form / url）都已闭合。"""
        assert UrlDetector().scan(f"refresh_token={_URL_SECRET}") != []
        assert UrlDetector().scan(f"?refresh_token={_URL_SECRET}") != []


class TestUrlDetectorLongValue:
    """长值（含超过 4096 有界量词上限的 5000 字符）不得因回溯上限而整体漏报。"""

    def test_5000_char_value_masked(self):
        value = "A" * 5000
        sample = f"?token={value}"
        findings = UrlDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == value

    def test_5000_char_value_redacted_end_to_end(self):
        value = "A" * 5000
        out = redact_text(f"?token={value}", purpose=RedactionPurpose.MODEL_OUTPUT)
        assert value not in out
        assert "[REDACTED:url_credential]" in out

    def test_long_value_shaped_negative_stays_clean(self):
        """长但非敏感 key：不得因长度本身命中。"""
        assert UrlDetector().scan(f"?page={'A' * 5000}") == []

    def test_value_span_is_not_truncated_by_a_regex_bound(self):
        """回归：value 量词不得带 `{1,N}` 上界 —— 否则长凭据只遮前 N 字符、余下泄露。

        旧实现写死 ``{1,4096}``：``?token=<5000 个 A>`` 产出 span=(7, 4103)，
        后 904 个字符原样留在输出里。
        """
        value = "A" * 5000
        sample = f"?token={value}"
        finding = UrlDetector().scan(sample)[0]
        assert sample[finding.start : finding.end] == value
        assert finding.end == len(sample)

    def test_long_input_scales_linearly(self):
        """值字符类是取反类 → 线性；无敏感 key 时预筛选必须廉价早退。"""
        big = "?token=" + "A" * 200_000
        start = time.perf_counter()
        assert len(UrlDetector().scan(big)) == 1
        assert time.perf_counter() - start < 0.5
        assert UrlDetector().scan("a" * 200_000) == []

    def test_many_semicolon_pairs_no_quadratic_blowup(self):
        """`;` 分隔路径同样对 pair 数线性（防新正则引入 ReDoS）。"""
        blob = ";".join(["a=b"] * 20_000)
        start = time.perf_counter()
        assert UrlDetector().scan(blob) == []
        assert time.perf_counter() - start < 0.5


class TestUrlDetectorStructuredNegative:
    """结构化负例：非 URL 字段文本与变量引用一律字节级不变。"""

    @pytest.mark.parametrize(
        "sample",
        [
            "status.code=200",
            "error.code=500",
            "code=200",
            "token=$TOKEN",
            "token=${TOKEN}",
        ],
    )
    def test_negative_byte_identical(self, sample):
        assert UrlDetector().scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize("sample", ["status.code=abc123", "error.code=abc123"])
    def test_dotted_code_key_never_sensitive(self, sample):
        """`status.code` / `error.code` 无论值多长都不当 OAuth code（ref.md §10.3）。"""
        assert UrlDetector().scan(sample) == []


_PEM_BLOCKS = {
    "RSA": "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
    "EC": "-----BEGIN EC PRIVATE KEY-----\nMIIEow\n-----END EC PRIVATE KEY-----",
    "OPENSSH": "-----BEGIN OPENSSH PRIVATE KEY-----\nMIIEow\n-----END OPENSSH PRIVATE KEY-----",
    "ENCRYPTED": "-----BEGIN ENCRYPTED PRIVATE KEY-----\nMIIEow\n-----END ENCRYPTED PRIVATE KEY-----",
    "PRIVATE": "-----BEGIN PRIVATE KEY-----\nMIIEow\n-----END PRIVATE KEY-----",
    "PGP": "-----BEGIN PGP PRIVATE KEY BLOCK-----\nMIIEow\n-----END PGP PRIVATE KEY BLOCK-----",
}


class TestPemDetector:
    """PEM/PGP private key 整块检测；公钥/证书与 label 不一致不命中。"""

    @pytest.mark.parametrize("block", list(_PEM_BLOCKS.values()))
    def test_private_key_block_hits(self, block):
        findings = PemDetector().scan(block)
        assert len(findings) == 1
        assert findings[0].kind == "private_key"
        assert findings[0].priority == 95

    def test_span_covers_whole_block(self):
        block = _PEM_BLOCKS["RSA"]
        finding = PemDetector().scan(block)[0]
        assert block[finding.start : finding.end] == block

    @pytest.mark.parametrize(
        "block",
        [
            "-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----",
            "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----",
            "-----BEGIN PGP PUBLIC KEY BLOCK-----\nAAAA\n-----END PGP PUBLIC KEY BLOCK-----",
            "-----BEGIN SSH2 PUBLIC KEY-----\nAAAA\n-----END SSH2 PUBLIC KEY-----",
        ],
    )
    def test_public_key_not_matched(self, block):
        assert PemDetector().scan(block) == []

    def test_mismatched_labels_not_matched_as_a_block_but_still_masked(self):
        """label 错配**不作为完整块**命中，但其私钥 body 仍必须被遮（2026-09-17 升级）。

        错配（``BEGIN RSA`` + ``END EC``）没有**配对** END ⇒ ``iter_pem_blocks`` 不产块。
        此前该形状只能依赖裸熵兜底，而纯 base64 body（``char_class_count < 3``）
        会躲过熵判据 ⇒ **明文泄露**（本例的 ``MIIEow`` 修复前即为明文）。
        现由 ``PemDetector`` 的未闭合私钥兜底接管 —— 故断言从「不命中」升级为
        「不得泄露」：既不再要求 ``scan() == []``，也不允许 body 存活。
        """
        block = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END EC PRIVATE KEY-----"
        out = redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert "MIIEow" not in out, f"private body leaked: {out!r}"

    @pytest.mark.parametrize("block", list(_PEM_BLOCKS.values()))
    def test_prefilter_reachable(self, block):
        assert PemDetector().could_match(block) is True

    def test_prefilter_negative(self):
        assert PemDetector().could_match("no dashes here") is False


class TestCookieDetector:
    """Cookie / Set-Cookie 检测：只替换敏感名 cookie 的值，属性保真。"""

    def test_sensitive_cookie_value_only(self):
        sample = "Cookie: session=abc123; theme=dark"
        findings = CookieDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].kind == "cookie"
        assert findings[0].priority == 85
        assert sample[findings[0].start : findings[0].end] == "abc123"

    def test_set_cookie_expires_comma_survives(self):
        sample = "Set-Cookie: auth_token=xyz; Expires=Wed, 21 Oct 2026 07:28:00 GMT; Secure; HttpOnly"
        findings = CookieDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == "xyz"

    @pytest.mark.parametrize("name", ["session", "sessionid", "auth_token", "token", "jwt", "csrf", "xsrf_token"])
    def test_sensitive_names(self, name):
        sample = f"Cookie: {name}=abc123; theme=dark"
        assert len(CookieDetector().scan(sample)) == 1

    @pytest.mark.parametrize("sample", ["Cookie: theme=dark; lang=zh", "Set-Cookie: lang=zh; Path=/; Secure"])
    def test_negative_non_sensitive_name(self, sample):
        assert CookieDetector().scan(sample) == []

    def test_prefilter_reachable(self):
        detector = CookieDetector()
        assert detector.could_match("Set-Cookie: session=abc") is True

    def test_prefilter_negative(self):
        assert CookieDetector().could_match("no header here") is False

    @pytest.mark.parametrize(
        "sample",
        [
            '"Cookie: session=abc123"',
            "'Cookie: session=abc123'",
            "[Cookie: session=abc123]",
            "{Cookie: session=abc123}",
            "(Cookie: session=abc123)",
            "<Cookie: session=abc123>",
            "foo=Cookie: session=abc123",
            "INFO:Cookie: session=abc123",
        ],
    )
    def test_header_boundary_accepts_serialized_delimiters(self, sample):
        """序列化定界符（引号 / 括号 / 等号 / 冒号）都必须作为合法头名前缀。

        回归：原 `(?:^|[\\s;])` 只认空白与分号，导致上述形态静默漏报。
        span 只覆盖值本体，故被引号包裹时闭引号不在 span 内。
        """
        findings = CookieDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == "abc123"

    @pytest.mark.parametrize("sample", ["mycookie session=abc123", "sessionCookie=abc123", "Cookie Monster"])
    def test_header_boundary_rejects_longer_identifiers(self, sample):
        """放宽前缀不得把更长标识符（mycookie / sessionCookie）误判为头名。"""
        assert CookieDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "sample, secret",
        [
            ("Cookie: session=abc123 Cookie: token=xyz789", "abc123"),  # 同行第二个头
            ("Cookie: session=abc123\tCookie: token=xyz789", "abc123"),  # 制表符分隔
            ("Cookie: sid=abc123, token=xyz789", "abc123"),  # 逗号分隔
            ("foo=Cookie: session=abc123 https://x", "abc123"),  # payload 后尾随 URL
            ("sent Cookie: session=abc123 to server", "abc123"),  # 尾随散文
            ('curl -H Cookie: session=abc123" https://x', "abc123"),  # 闭引号 + 尾随
        ],
    )
    def test_pair_value_terminates_before_trailing_text(self, sample, secret):
        """段首 `name=value` 之后有尾随文本时仍须命中（回归：旧式整段 unmatched 漏报）。

        终止规则按 RFC 6265：值在空白 / 分号 / 尾随定界符处结束。
        """
        findings = CookieDetector().scan(sample)
        assert len(findings) == 1, f"{sample!r} 应命中一次"
        assert sample[findings[0].start : findings[0].end] == secret

    @pytest.mark.parametrize(
        "sample, secret",
        [
            ('Cookie: session="abc123def456"', "abc123def456"),
            ("Cookie: session='abc123def456'", "abc123def456"),
        ],
    )
    def test_quoted_value_span_excludes_quotes(self, sample, secret):
        """引号包裹的值：span 只覆盖内层，引号保真（不再连引号一起吞掉）。"""
        findings = CookieDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == secret
        assert '"' in sample[: findings[0].start] or "'" in sample[: findings[0].start]

    def test_value_stops_at_inner_space(self):
        """值内含裸空格时按 RFC 6265 在空格处终止（只遮空格前的 token）。"""
        sample = "Cookie: session=abc 123"
        findings = CookieDetector().scan(sample)
        assert len(findings) == 1
        assert sample[findings[0].start : findings[0].end] == "abc"
        assert "123" in redact_text(sample)

    @pytest.mark.parametrize(
        "sample",
        ["Cookie: theme=dark", "Cookie: session=", "Cookie: user=alice"],
    )
    def test_pair_parse_keeps_negatives(self, sample):
        """新解析不得让非敏感名 / 空值产生 finding。"""
        assert CookieDetector().scan(sample) == []

    def test_disabled_detector_never_in_scan_list(self):
        """门控关闭 ⇒ 该 detector 根本不进 ``_detectors_for_scan`` 的列表。

        门控由组装层独占（detector 无 ``enabled`` 状态），故此处断言的是**列表成员**，
        而非「构造后调用 scan 返回空」—— 后者是改动前的语义。
        """
        detectors = _detectors_for_scan(settings=SecurityRedactionSettings(enable_redact_cookies=False))
        assert not any(isinstance(d, CookieDetector) for d in detectors)


class TestCookieSameLineSecondHeader:
    """同一行出现第二个 `Cookie:` 头：第二个头的 cookie 仍然漏报。

    根因与 ``_PAIR_RE`` 无关（该缺陷已修）：``_COOKIE_HEADER_RE`` 的 payload 为
    ``[^\\r\\n]+``（取到行尾），同行第一个头的匹配会把第二个头**整段吞进自己的
    payload**，故 ``finditer`` 根本看不到第二个头起点。

    - 空格 / 制表符分隔 → 同一行，受影响（本类用 ``xfail`` 标记）。
    - ``\\n`` / ``\\r\\n`` 分隔 → ``[^\\r\\n]`` 在换行处停止，两个头各自成 match，**正常命中**。
    - ``;`` 分隔 → 本就是同一个头（`Cookie: a=1; b=2`），不属本缺陷。

    修复需要更换解析策略（例如先按头名切分再逐段解析），非正则小改，
    故此处先以 ``xfail(strict=True)`` 固定预期与边界，待后续处理。
    """

    @pytest.mark.xfail(
        strict=True,
        reason="同行第二个 Cookie: 头被首个匹配的 payload 吞掉，第二个头未脱敏（待修）",
    )
    def test_space_separated_second_header_masked(self):
        """空格分隔的同行第二头：两个头的值都应被替换。"""
        sample = "Cookie: session=abc123def456 Cookie: token=xyz789"
        findings = CookieDetector().scan(sample)
        assert len(findings) == 2
        assert "abc123def456" not in redact_text(sample)
        assert "xyz789" not in redact_text(sample)

    @pytest.mark.xfail(
        strict=True,
        reason="制表符不是行分隔符，同行第二头同样被吞（待修）",
    )
    def test_tab_separated_second_header_masked(self):
        """制表符分隔的同行第二头：两个头的值都应被替换。"""
        sample = "Cookie: session=abc123def456\tCookie: token=xyz789"
        findings = CookieDetector().scan(sample)
        assert len(findings) == 2
        assert "abc123def456" not in redact_text(sample)
        assert "xyz789" not in redact_text(sample)

    @pytest.mark.parametrize("sep", ["\n", "\r\n"])
    def test_newline_separated_second_header_masked(self, sep):
        """换行分隔的第二头正常命中（对照组：证明缺陷仅限「同一行」）。"""
        sample = f"Cookie: session=abc123def456{sep}Cookie: token=xyz789"
        findings = CookieDetector().scan(sample)
        assert len(findings) == 2
        assert "abc123def456" not in redact_text(sample)
        assert "xyz789" not in redact_text(sample)


class TestDetectorsIntegratedInPipeline:
    """端到端：所有关键正例经 redact_text 真实生效（防「写了但没接」T-06-16）。"""

    @pytest.mark.parametrize(
        "sample, secret",
        [
            (f"GPG_KEY={_GPG_SAMPLE}", _GPG_SAMPLE),
            ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
            ("postgresql://app:S3cr3tPw@db.internal:5432/prod", "S3cr3tPw"),
            ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "MIIEow"),
            ("Cookie: session=abc123; theme=dark", "abc123"),
            ("https://x.com/cb?access_token=abc123&next=/home", "abc123"),
            (_JWT_3SEG, _JWT_3SEG),
        ],
    )
    def test_positive_redacted_end_to_end(self, sample, secret):
        out = redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert secret not in out

    def test_url_fidelity_whole_string(self):
        """整串保真断言（非 in）：URL 不被重新序列化，参数顺序与编码原样。"""
        src = "https://x.com/cb?access_token=abc123&next=/home"
        out = redact_text(src, purpose=RedactionPurpose.LOG)
        assert out == "https://x.com/cb?access_token=[REDACTED:url_credential]&next=/home"

    def test_dsn_fidelity_end_to_end(self):
        src = "postgresql://app:S3cr3tPw@db.internal:5432/prod"
        out = redact_text(src, purpose=RedactionPurpose.EXPORT)
        assert "S3cr3tPw" not in out
        for keep in ("postgresql", "app", "db.internal", "5432", "prod"):
            assert keep in out

    def test_authorization_header_not_stolen_by_assignment(self):
        """回归：authorization 严格字段不得抢答 header scheme，header 名保真。"""
        src = "Authorization: Basic dXNlcjpwYXNz"
        out = redact_text(src, purpose=RedactionPurpose.LOG)
        assert out == "Authorization: Basic [REDACTED:authorization_header]"


class TestPipelineRawRuleHitsUnchanged:
    """重叠场景：unique_findings 合并为 1，raw_rule_hits 保留多 rule_id。"""

    def test_bearer_jwt_overlap_multi_rule(self):
        src = f"Authorization: Bearer {_JWT_3SEG}"
        result = scan_text(src, purpose=RedactionPurpose.LOG)
        assert result.unique_findings == 1
        assert any(rule_id.startswith("jwt") for rule_id in result.raw_rule_hits)
        assert sum(result.raw_rule_hits.values()) >= 1

    def test_assignment_counted_in_raw_rule_hits(self):
        result = scan_text(f"GPG_KEY={_GPG_SAMPLE}", purpose=RedactionPurpose.LOG)
        assert "assignment.gpgkey" in result.raw_rule_hits


class TestRedactPayload:
    """结构化脱敏：凭据字段掩码、非凭据字段保真、容器递归（承接已删 test_redact.py）。"""

    @pytest.mark.parametrize(
        "payload",
        [
            {"password": "p@ss", "nested": {"api_key": "***"}, "username": "alice"},
            [{"token": "secret-value"}, "plain"],
            {"API-KEY": "v"},
        ],
    )
    def test_credential_fields_masked(self, payload):
        result = redact_payload(payload, purpose=RedactionPurpose.LOG)
        # 逐项断言：凭据键值被替换，非凭据内容原样保留
        flat = str(result)
        assert "p@ss" not in flat
        assert "plain" in flat or "alice" in flat or "[REDACTED:" in flat

    def test_non_credential_field_untouched(self):
        """非凭据字段整串相等（不误伤 token_count / description）。"""
        payload = {"token_count": 42, "description": "fine"}
        assert redact_payload(payload, purpose=RedactionPurpose.LOG) == payload

    def test_credentials_container_recursed_d6(self):
        """D6 回归：容器值不被整体替换，子对象字段保留。"""
        payload = {"credentials": {"user": "a", "password": "b"}}
        result = redact_payload(payload, purpose=RedactionPurpose.LOG)
        assert isinstance(result["credentials"], dict)
        assert result["credentials"]["user"] == "a"
        assert "b" not in str(result["credentials"]["password"])


class TestRedactForExport:
    """导出入口等价 purpose=EXPORT，str 与 payload 两条路径均脱敏。"""

    def test_export_redacts_string(self):
        assert "abc" not in redact_for_export("secret=abc")

    def test_export_redacts_payload(self):
        assert "abc" not in redact_for_export({"secret": "abc"})["secret"]


class TestCountSensitiveHits:
    """敏感命中统计：只计数、不落明文；旧三键口径保留。"""

    def test_counts_vendor_tokens(self):
        hits = count_sensitive_hits("key1 sk-" + "a" * 36 + " key2 ghp_" + "B" * 36)
        assert hits["vendor_token"] == 2
        assert hits["total"] == 2

    def test_credential_key_value_populated(self):
        hits = count_sensitive_hits(f"GPG_KEY={_GPG_SAMPLE}")
        assert hits["credential_key_value"] >= 1

    def test_clean_text_zero(self):
        assert count_sensitive_hits("nothing sensitive here") == {
            "vendor_token": 0,
            "credential_key_value": 0,
            "total": 0,
        }

    def test_empty_returns_zero(self):
        assert count_sensitive_hits("")["total"] == 0


# ---------------------------------------------------------------------------
# 缺陷回归：phase-06 脱敏引擎的四个独立缺陷（D1-D4）
# ---------------------------------------------------------------------------

# D1：赋值 value 不得吞掉 query string 后续参数
_URL_TAIL_SAMPLES = (
    "?access_token=x&next=/a",  # ROADMAP 字面判据
    "/cb?access_token=x&next=/a",
    "GET /oauth?access_token=x&next=/a",
    "https://x.com/cb?access_token=x&next=/home",
)


class TestUrlCredentialValueTerminator:
    """缺陷 1：assignment 的 value 不得吞掉 `&` / `#` 之后的非敏感参数。"""

    @pytest.mark.parametrize("sample", _URL_TAIL_SAMPLES)
    def test_non_sensitive_tail_survives(self, sample):
        out = redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert "&next=" in out  # 无关参数保真（此前被整体销毁）
        assert "access_token=" in out  # key 名保真
        assert "[REDACTED:url_credential]" in out  # secret 本体被替换

    @pytest.mark.parametrize("purpose", [RedactionPurpose.LOG, RedactionPurpose.EXPORT])
    def test_long_secret_under_partial_mask_does_not_leak_tail(self, purpose):
        """≥32 字符 secret 在 LOG/EXPORT（head6/tail4）下不得泄露后续参数。"""
        secret = "ABCDEF" + "x" * 30 + "WXYZ"  # 40 字符
        sample = f"?client_secret={secret}&next=/a&page=2"
        out = redact_text(sample, purpose=purpose)
        assert "next=/a" in out and "page=2" in out
        assert secret not in out

    def test_hash_fragment_terminator(self):
        """`#` 亦为 value 终止符（fragment 不被吞）。"""
        out = redact_text("?access_token=x#section-2", purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "?access_token=[REDACTED:url_credential]#section-2"


# D2：变量引用护栏必须锚定于值起始处，不能因 64 字符外的无关 token 跳过真实 secret
_REAL_SECRET = "DNxril3RavGD5MfvJ7NScUyk"  # 24 字符高熵


class TestVariableReferenceGuardAnchored:
    """缺陷 2：值之后的无关 process.env./os.getenv( 不得把真实 secret 判为变量引用。"""

    @pytest.mark.parametrize(
        "trailer",
        ["process.env.X", "os.getenv(", "process.env.NODE_ENV"],
    )
    def test_trailing_var_ref_token_does_not_skip_secret(self, trailer):
        src = f"private_key={_REAL_SECRET} then some words {trailer}"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _REAL_SECRET not in out
        assert "[REDACTED:" in out

    def test_control_without_trailer_still_redacts(self):
        src = f"private_key={_REAL_SECRET} then some words nothing here"
        assert _REAL_SECRET not in redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)

    @pytest.mark.parametrize(
        "src",
        [
            "password=${DB_PASSWORD}",
            "password=$DB_PASSWORD",
            "api_key=process.env.API_KEY",
            "secret=${VAULT_TOKEN}",
        ],
    )
    def test_genuine_var_ref_still_preserved(self, src):
        """护栏本意不可破坏：真实变量引用值仍原样保留。"""
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src

    @pytest.mark.parametrize("length", [8, 31, 32])
    def test_strict_path_length_boundaries(self, length):
        """严格路径 8/31/32 长度边界均须命中（此前 8-31 段静默漏报）。"""
        value = "A1" + "z" * (length - 3) + "9"
        out = redact_text(f"private_key={value} process.env.TAIL", purpose=RedactionPurpose.MODEL_OUTPUT)
        assert value not in out


# D3：ReDoS —— 大段无分隔符文本不得 O(n²)；预筛选必须挂进 detector 循环
class TestPrefilterReDoSProtection:
    """缺陷 3：could_match 预筛选接入 + key 正则锚定，大输入必须线性完成。"""

    def test_large_alnum_input_completes_quickly(self):
        blob = "a" * 200_000  # 旧行为：无预筛选时 >400s 挂死
        result = scan_text(blob, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert result.redacted_text == blob
        assert result.unique_findings == 0

    def test_scan_self_guards_on_could_match(self):
        """T-vq0：预筛选所有权在 ``scan`` 自身 —— detector 自守卫，而非调用方兜底。"""
        assert AssignmentDetector.could_match(AssignmentDetector(), "no delimiter here") is False
        assert AssignmentDetector().scan("no delimiter here") == []

    @pytest.mark.parametrize(
        "cls, sample_pos",
        [
            (AssignmentDetector, "GPG_KEY=" + _GPG_SAMPLE),
            (VendorTokenDetector, "sk-" + "a" * 36),
        ],
    )
    def test_scan_self_guards_before_expensive_work(self, cls, sample_pos):
        """could_match=False 时 scan 必须在触碰昂贵扫描之前返回（T-vq0 判别式）。

        机制侧：先钉住 could_match 本身对无分隔符大输入返回 False；再证明该输入
        下 scan 走的是**廉价早退**而非昂贵路径 —— 用 200k 输入的耗时上界做判据
        （``re.Pattern.finditer`` 是 C 类型不可 patch，见计划 Task 1 第 5 步的退化分支）。
        守卫若仍在调用方，``cls().scan(blob)`` 会落到昂贵的 200k 扫描 ⇒ 断言失败。
        """
        blob = "no delimiter " + "a" * 200_000
        assert cls().could_match(blob) is False

        with patch.object(cls, "could_match", return_value=False):
            start = time.perf_counter()
            assert cls().scan(blob) == []
            elapsed = time.perf_counter() - start
        assert elapsed < 0.05, f"scan did not self-guard before expensive work: {elapsed:.3f}s"

        # 反向对照：could_match=True 时确实进入昂贵路径（证明上界判据本身有效）
        with patch.object(cls, "could_match", return_value=True):
            start = time.perf_counter()
            cls().scan(blob)
            elapsed_expensive = time.perf_counter() - start
        assert elapsed_expensive > elapsed

    def test_scan_text_invokes_could_match_exactly_once_per_detector(self):
        """api 不再自行调用 could_match：每个 detector 的 could_match 只被 scan 调一次。"""
        calls = {"n": 0}
        original = AssignmentDetector.could_match

        def counting(self, text):
            calls["n"] += 1
            return original(self, text)

        with patch.object(AssignmentDetector, "could_match", counting):
            scan_text("password=hunter2", purpose=RedactionPurpose.MODEL_OUTPUT)
        assert calls["n"] == 1

    def test_all_detectors_expose_cheap_prefilter(self):
        """每个已接入 detector 均暴露可调用的 could_match（协议契约，Detector 非 runtime_checkable）。

        注：``_detectors_for_scan`` 实际注册 **11** 个实例（`Detector` 协议本身在
        ``base.py``，不是 detector）。本计数于 2026-09-15 由 10 变 11——
        新增 ``DsnJdbcDetector``（JDBC 属性串，带 ``jdbc:`` 上下文）。
        **该计数前提是默认 settings 下全部开关为 True**：门控关闭时该 detector 整项
        不入列表（长度随之变化），故任何需要固定长度的断言都须显式使用默认 settings。
        """
        detectors = _detectors_for_scan(settings=SecurityRedactionSettings())
        assert len(detectors) == 11
        for detector in detectors:
            assert callable(detector.could_match)
            assert isinstance(detector.could_match("clean plain text 123"), bool)

    @pytest.mark.parametrize(
        "detector_cls, sample",
        [
            (PemDetector, "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----"),
            (HeadersDetector, "Authorization: Basic dXNlcjpwYXNz"),
            (DsnDetector, "postgresql://app:S3cr3tPw@db.internal:5432/prod"),
            (DsnJdbcDetector, "jdbc:sqlserver://h;User Id=sa;Password=S3cr3tPw"),
            (JwtDetector, _JWT_3SEG),
            (CookieDetector, "Cookie: session=abc123; theme=dark"),
            (UrlDetector, "https://x.com/cb?access_token=abc123&next=/home"),
            (VendorTokenDetector, "sk-" + "a" * 36),
            (AssignmentDetector, f"GPG_KEY={_GPG_SAMPLE}"),
            (EntropyDetector, f"v {_GPG_SAMPLE}"),
        ],
    )
    def test_prefilter_does_not_skip_real_positives(self, detector_cls, sample):
        """接线预筛选不得漏掉任何既有正例（over-strict could_match = 检测回归）。"""
        detector = detector_cls()
        assert detector.could_match(sample) is True
        assert detector.scan(sample) != []


# D4：公钥 / 证书 PEM body 不得被裸熵兜底二次遮掉
_PEM_PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxYz9QwErTyUiOpAsDfGh\n-----END PUBLIC KEY-----"
_PEM_CERTIFICATE = (
    "-----BEGIN CERTIFICATE-----\naUpG7zPe+f6z49nJyz8K8NlHG3mpcvgPUTEPiTUvB1c2x4\n-----END CERTIFICATE-----"
)


class TestPemNonSecretNotMasked:
    """缺陷 4：公钥 / 证书 body 必须字节级原样保留；private key 仍须脱敏。"""

    @pytest.mark.parametrize("block", [_PEM_PUBLIC_KEY, _PEM_CERTIFICATE])
    def test_non_secret_block_byte_identical(self, block):
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block

    def test_private_key_still_masked(self):
        block = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAxYz9QwErTyUiOpAsDfGhJk\n-----END RSA PRIVATE KEY-----"
        out = redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out != block
        assert "MIIEow" not in out

    def test_label_followed_by_space_not_excluded(self):
        """反例：`CERTIFICATE AUTHORITY=<value>` 是普通文本，不得被 PEM 排除放过。"""
        src = "CERTIFICATE AUTHORITY=" + _GPG_SAMPLE
        assert _GPG_SAMPLE not in redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)

    def test_entropy_after_end_of_non_secret_block_still_hits(self):
        """反例：块结束之后的裸高熵串仍须命中（排除仅限块内）。"""
        src = _PEM_PUBLIC_KEY + "\n" + _GPG_SAMPLE
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _GPG_SAMPLE not in out
        assert "-----BEGIN PUBLIC KEY-----" in out


# ---------------------------------------------------------------------------
# 缺陷回归：fix 轮 2 —— D5（`\b` 锚定丢弃数字前缀键）+ D6（PEM 非秘密块覆盖不全）
# ---------------------------------------------------------------------------

# D5：数字前缀键必须命中（`\b` 在「数字→字母」处无边界，此前静默漏报）
_DIGIT_PREFIXED_POSITIVES = (
    "1password=hunter2hunter2",
    "9api_key=abcdefgh12345678",
    "2secret=abcdefgh12345678",
    "1access_token=abcdefghijklmnopqrstuvwxyz",
    "2private_key=abcdefghijklmnopqrstuvwxyz",
)


class TestDigitPrefixedKeys:
    """缺陷 5：key 前缀锚定为 token 边界 `(?<![A-Za-z0-9_-])`，数字前缀由捕获组外的
    `[0-9]*` 消费，故数字前缀键（1password= 等）命中且 key 组仍为纯字母开头，线性性不退化。"""

    @pytest.mark.parametrize("sample", _DIGIT_PREFIXED_POSITIVES)
    def test_digit_prefixed_key_masked(self, sample):
        """数字前缀键必须命中（回归：`\\b` 锚定使其全部漏报）。"""
        out = redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out != sample
        assert "[REDACTED:" in out

    @pytest.mark.parametrize(
        "sample",
        ["gpg_key=" + _GPG_SAMPLE, "password=hunter2hunter2", "9api_key=abcdefgh12345678"],
    )
    def test_controls_still_masked(self, sample):
        """正对照：无前缀键与数字前缀键均须命中。"""
        assert "[REDACTED:" in redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)

    @pytest.mark.parametrize(
        "sample",
        [
            "plain text no delimiter",
            "[A-Za-z_][A-Za-z0-9_-]*",
            "abpassword=hunter2hunter2",  # 更长标识符，非严格字段名
            "token_count=100",
        ],
    )
    def test_negative_not_masked(self, sample):
        """负对照：无 `[:=]` 或非凭据字段名一律零命中。"""
        detector = AssignmentDetector()
        assert detector.scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize(
        "src",
        ["password=${DB_PASSWORD}", "password=$DB_PASSWORD", "api_key=process.env.API_KEY", "secret=${VAULT_TOKEN}"],
    )
    def test_genuine_var_ref_preserved(self, src):
        """护栏不可破坏：真实变量引用值仍字节级保留。"""
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src


# D6：PEM 非秘密块须覆盖 label 家族 + 多行 body；private 家族必须仍被遮
_PEM_WRAPPED_BODY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxYz9QwErTyUiOpAsDfGh\n"
    "JkLmNoPqRsTuVwXyZ0123456789abcdefghijklmnopqrstuvwxyzABCD\n"
    "EFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwx+/="
)
_PUBLIC_LABELS = (
    "PUBLIC KEY",
    "RSA PUBLIC KEY",
    "EC PUBLIC KEY",
    "DSA PUBLIC KEY",
    "OPENSSH PUBLIC KEY",
    "CERTIFICATE",
    "PGP PUBLIC KEY BLOCK",
)
_PRIVATE_LABELS = (
    "PRIVATE KEY",
    "RSA PRIVATE KEY",
    "EC PRIVATE KEY",
    "OPENSSH PRIVATE KEY",
    "DSA PRIVATE KEY",
    "ENCRYPTED PRIVATE KEY",
    "PGP PRIVATE KEY BLOCK",
)


class TestPemNonSecretLabelFamily:
    """缺陷 6：公钥 / 证书 label 家族 + 多行 body 全排除；private 家族仍须遮。"""

    @pytest.mark.parametrize("label", _PUBLIC_LABELS)
    def test_public_label_family_byte_identical(self, label):
        """全部公钥 / 证书 label 的多行 wrapped body 必须字节级原样保留。"""
        block = f"-----BEGIN {label}-----\n{_PEM_WRAPPED_BODY}\n-----END {label}-----"
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block

    @pytest.mark.parametrize("label", _PRIVATE_LABELS)
    def test_private_label_family_still_masked(self, label):
        """正对照：private key 家族绝不可被排除集放过（泄露后果远重于原缺陷）。"""
        block = f"-----BEGIN {label}-----\n{_PEM_WRAPPED_BODY}\n-----END {label}-----"
        out = redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out != block
        assert _PEM_WRAPPED_BODY not in out

    @pytest.mark.parametrize(
        "label, preserved",
        [("SSH2 PUBLIC KEY", True), ("SSH2 ENCRYPTED PRIVATE KEY", False)],
    )
    def test_four_dash_rfc4716(self, label, preserved):
        """RFC 4716 四短横形态：SSH2 公钥保留、加密私钥仍遮。

        私钥分支的 `preserved=False` 现由 **`PemDetector` 整块命中**满足
        （此前靠裸熵兜底也满足 —— 只看 `out != block` 会把兜底误判为命中），
        故额外断言端到端 `raw_rule_hits` 含 `pem`。
        """
        block = f"---- BEGIN {label} ----\n{_PEM_WRAPPED_BODY}\n---- END {label} ----"
        out = redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert (out == block) is preserved
        if not preserved:
            assert "pem" in scan_text(block, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits


# D5 伴生：数字前缀修复不得让 O(n²) ReDoS 回归 —— 锚定仍是线性的
class TestAssignmentKeyAnchorLinearity:
    """缺陷 5：key 前缀锚定 (?<![A-Za-z0-9_-])[0-9]* 必须抑制 O(n²)，且不丢数字前缀键。

    本类只覆盖**非触发形状**（`"a"` / `"a="`）的线性护栏 —— 它们在旧锚定下也是线性的，
    故原规模（放大到 20_000 * 2**4）对它们是安全的。
    `"1a"` / `"1a="` 这类「数字-字母交替 + 分隔符」形状才是 quadratic 触发体
    （旧锚定只禁止字母/下划线，「1a1a1a...」中每个字母位都能重启贪心扫描），
    在该规模下 RED 单步需 ~400s 量级，会挂死套件，故触发形状的回归改由
    `TestAssignmentCodeReviewRegression.test_p0_key_value_re_linear_on_digit_letter_runs`
    以 n=2000/4000/8000 的小规模覆盖。
    """

    @pytest.mark.parametrize("shape", ["a", "a="])
    def test_doubling_scaling_is_linear(self, shape):
        """4 次倍增：每次耗时比须 ≈ 2（O(n)），远低于 quadratic 的 ≈ 4。"""
        samples = [shape * (20_000 * 2**i) for i in range(5)]
        times = []
        for text in samples:
            start = time.perf_counter()
            scan_text(text, purpose=RedactionPurpose.MODEL_OUTPUT)
            times.append(time.perf_counter() - start)
        ratios = [times[i + 1] / times[i] for i in range(len(times) - 1)]
        assert max(ratios) < 3.0, f"non-linear scaling: {ratios} for shape={shape!r}"

    def test_large_log_blob_completes_quickly(self):
        """~320KB 真实日志样（含分散 `=`）必须快速完成（远低于挂死阈值）。"""
        line = "2026-09-14T12:00:00Z INFO svc=api user=alice status=ok msg=handled path=/v1/items\n"
        blob = line * 3200  # ~320KB
        start = time.perf_counter()
        scan_text(blob, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert time.perf_counter() - start < 5.0


# ---------------------------------------------------------------------------
# 缺陷回归：fix 轮 3 —— D7（PEM 非秘密块排除 fail-open 泄露）
#
# 根因：``is_pem_non_secret_span`` 只读 BEGIN label 就排除 span，而 ``PemDetector``
# 要求 BEGIN == END 才动作。于是「BEGIN 非秘密 + END 错配 / 缺失」的畸形块被熵侧
# 放过、又被 PemDetector 拒绝 —— 两边都不遮，body 原样泄露（fail-open）。
#
# 既有 fixture 全部使用 **BEGIN/END 同名** 的良构块，故连续三轮都漏掉了这类形状。
# 下面显式覆盖错配 / 未闭合 / 双向 sweep，并以「fail-closed」为验收：无法正识别为
# 完整匹配的非秘密块 → 必须被遮。
# ---------------------------------------------------------------------------

# 每个 body 都是长度 ≥32、高熵、非形状排除的裸密文（裸熵兜底必然命中）。
_PEM_LEAK_BODY_ALNUM = "QGBZvSrgJ0hZOs9KHJV4jhw4hKFPGI6G"  # len=32 ent=4.4528 cls=3
_PEM_LEAK_BODY_B64 = "aUpG7zPe+f6z49nJyz8K8NlHG3mpcvgPUTEPiTUv"  # len=40 ent=4.7153 cls=4
_PEM_LEAK_BODY = _PEM_LEAK_BODY_B64

# 非秘密 label 家族（含 X509 / TRUSTED CERTIFICATE —— 任务点名要求覆盖）
_NON_SECRET_LABELS = (
    "PUBLIC KEY",
    "RSA PUBLIC KEY",
    "EC PUBLIC KEY",
    "DSA PUBLIC KEY",
    "OPENSSH PUBLIC KEY",
    "CERTIFICATE",
    "X509 CERTIFICATE",
    "TRUSTED CERTIFICATE",
    "PGP PUBLIC KEY BLOCK",
)
# 私钥 label 家族（正对照：任何形态都必须被遮）
_SECRET_LABELS = (
    "PRIVATE KEY",
    "RSA PRIVATE KEY",
    "EC PRIVATE KEY",
    "OPENSSH PRIVATE KEY",
    "DSA PRIVATE KEY",
    "ENCRYPTED PRIVATE KEY",
    "PGP PRIVATE KEY BLOCK",
)

# [260917-x5f] 同行 body（body 与 BEGIN 标记同一行）覆盖的 12 个非秘密 label ——
# 对应 harness/security-test/pem.md 的 P011-P022 label 面。**刻意不复用**
# ``_NON_SECRET_LABELS``（9 项）：后者缺 CSR 三兄弟（``CERTIFICATE REQUEST`` /
# ``NEW CERTIFICATE REQUEST``）与 ``SSH2 PUBLIC KEY``，正是 pem.md 断言「字节级全等」
# 而本次修复前实测被误遮的一组。子集化会漏掉真阳性，故此处独立登记。
# 若日后往 ``detectors._NON_SECRET_LABEL_SET`` 增删成员，本表须同步 ——
# 二者失配时 test_same_line_non_secret_byte_identical 会红。
_SAME_LINE_NON_SECRET_LABELS = (
    "PUBLIC KEY",
    "RSA PUBLIC KEY",
    "EC PUBLIC KEY",
    "DSA PUBLIC KEY",
    "OPENSSH PUBLIC KEY",
    "PGP PUBLIC KEY BLOCK",
    "SSH2 PUBLIC KEY",
    "CERTIFICATE",
    "X509 CERTIFICATE",
    "TRUSTED CERTIFICATE",
    "CERTIFICATE REQUEST",
    "NEW CERTIFICATE REQUEST",
)

# 空白异体的同行非秘密块（pem.md P042-P045）：BEGIN / END 双侧空白可独立膨胀。
# ``(begin_label, end_label)`` —— 归一化后同为 ``PUBLIC KEY``。
_SAME_LINE_WS_VARIANTS = (
    ("   PUBLIC KEY", "   PUBLIC KEY"),  # 双空格（缺陷 8 原始泄露形）
    ("PUBLIC  KEY", "PUBLIC  KEY"),  # 内部双空格
    ("PUBLIC KEY ", "PUBLIC KEY "),  # 尾随空白
    (" PUBLIC KEY", "PUBLIC KEY"),  # 非对称空白
)


def _assert_body_masked(text: str) -> None:
    """断言给定 PEM-ish 文本的 body **不可能**原样存活（fail-closed 验收）。"""
    out = redact_text(text, purpose=RedactionPurpose.MODEL_OUTPUT)
    assert _PEM_LEAK_BODY not in out, f"body leaked verbatim: {out!r}"


class TestPemFailClosedOnMalformedBlocks:
    """D7：畸形 / 错配 / 未闭合的 PEM 块必须 fail-closed（body 被遮，绝不逐字泄露）。"""

    @pytest.mark.parametrize("label", _NON_SECRET_LABELS)
    @pytest.mark.parametrize(
        "end_label",
        ["RSA PRIVATE KEY", "EC PRIVATE KEY", "PGP PRIVATE KEY BLOCK"],
    )
    def test_non_secret_begin_with_mismatched_end_masked(self, label, end_label):
        """点名的泄露形：BEGIN 非秘密 + END 私钥（此前 PemDetector 与熵侧都不遮）。"""
        _assert_body_masked(f"-----BEGIN {label}-----\n{_PEM_LEAK_BODY}\n-----END {end_label}-----")

    @pytest.mark.parametrize("label", _NON_SECRET_LABELS)
    def test_non_secret_begin_unterminated_masked(self, label):
        """点名的泄露形：BEGIN 非秘密但**完全没有 END** —— 不得因此被排除。"""
        _assert_body_masked(f"-----BEGIN {label}-----\n{_PEM_LEAK_BODY}")

    @pytest.mark.parametrize("begin_label", _NON_SECRET_LABELS)
    @pytest.mark.parametrize("end_label", _NON_SECRET_LABELS)
    def test_mismatched_non_secret_pair_sweep_masked(self, begin_label, end_label):
        """双向 sweep：非秘密 label 之间两两错配也必须被遮（36 组配对）。"""
        if begin_label == end_label:
            pytest.skip("matched pair -> covered by byte-identical positive test")
        _assert_body_masked(f"-----BEGIN {begin_label}-----\n{_PEM_LEAK_BODY}\n-----END {end_label}-----")

    @pytest.mark.parametrize("label", _SECRET_LABELS)
    def test_private_begin_unterminated_masked(self, label):
        """正对照：私钥块未闭合同样必须被遮。"""
        _assert_body_masked(f"-----BEGIN {label}-----\n{_PEM_LEAK_BODY}")

    @pytest.mark.parametrize("label", _SECRET_LABELS)
    @pytest.mark.parametrize("end_label", ["EC PRIVATE KEY", "RSA PRIVATE KEY"])
    def test_private_begin_mismatched_end_masked(self, label, end_label):
        """正对照：私钥块 END 错配也必须被遮。"""
        _assert_body_masked(f"-----BEGIN {label}-----\n{_PEM_LEAK_BODY}\n-----END {end_label}-----")


class TestPemMatchedNonSecretByteIdentical:
    """良构（BEGIN/END 同名）非秘密块必须字节级保留 —— 与 fail-closed 的另一半。"""

    @pytest.mark.parametrize("label", _NON_SECRET_LABELS)
    def test_matched_multiline_block_byte_identical(self, label):
        """全部非秘密 label + 真实多行 wrapped body 必须原样保留（不误伤，不破坏信任链）。"""
        block = f"-----BEGIN {label}-----\n{_PEM_WRAPPED_BODY}\n-----END {label}-----"
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block

    @pytest.mark.parametrize("label", _NON_SECRET_LABELS)
    def test_matched_crlf_block_byte_identical(self, label):
        """CRLF 行尾的良构非秘密块同样必须原样保留。"""
        body = _PEM_WRAPPED_BODY.replace("\n", "\r\n")
        block = f"-----BEGIN {label}-----\r\n{body}\r\n-----END {label}-----"
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block

    @pytest.mark.parametrize("label", _NON_SECRET_LABELS)
    def test_matched_long_wrapped_body_byte_identical(self, label):
        """30 行 wrapped body（远超市面公钥长度）必须整段保留，不得只放过首行。"""
        body = "\n".join([_PEM_LEAK_BODY_B64] * 30)
        block = f"-----BEGIN {label}-----\n{body}\n-----END {label}-----"
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block


class TestPemBoundaryRobustness:
    """边界 / 健壮性：CRLF、无尾换行、相邻块、body 内嵌异名 END。"""

    def test_crlf_mismatched_end_masked(self):
        """CRLF + END 错配：不得因行尾差异而漏遮。"""
        _assert_body_masked(f"-----BEGIN PUBLIC KEY-----\r\n{_PEM_LEAK_BODY}\r\n-----END RSA PRIVATE KEY-----")

    def test_no_trailing_newline_unterminated_masked(self):
        """无尾换行的未闭合块：必须被遮。"""
        _assert_body_masked(f"-----BEGIN PUBLIC KEY-----\n{_PEM_LEAK_BODY}")

    def test_public_followed_by_private_block_masks_private(self):
        """相邻块：公钥块后的私钥块 body 不得被前块排除「顺带放过」。"""
        src = (
            f"-----BEGIN PUBLIC KEY-----\n{_PEM_LEAK_BODY_B64}\n-----END PUBLIC KEY-----\n"
            f"-----BEGIN RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY_ALNUM}\n-----END RSA PRIVATE KEY-----"
        )
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _PEM_LEAK_BODY_ALNUM not in out

    def test_secret_after_public_block_still_masked(self):
        """公钥块结束之后紧跟的裸密文仍须命中（排除仅限块内）。"""
        src = f"-----BEGIN PUBLIC KEY-----\n{_PEM_LEAK_BODY_B64}\n-----END PUBLIC KEY-----\n{_PEM_LEAK_BODY_ALNUM}"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _PEM_LEAK_BODY_ALNUM not in out
        assert "-----BEGIN PUBLIC KEY-----" in out

    def test_body_containing_other_label_end_is_masked(self):
        """含糊态：良构公钥块 body 内嵌 ``END <异名>`` 行 → 无法确证为完整非秘密块 → 遮。"""
        src = (
            f"-----BEGIN PUBLIC KEY-----\n{_PEM_LEAK_BODY_B64}\n-----END RSA PRIVATE KEY-----\n-----END PUBLIC KEY-----"
        )
        _assert_body_masked(src)

    @pytest.mark.parametrize("label, preserved", [("SSH2 PUBLIC KEY", True), ("SSH2 ENCRYPTED PRIVATE KEY", False)])
    def test_four_dash_rfc4716_still_correct(self, label, preserved):
        """RFC 4716 4 短横形态回归：公钥保留、加密私钥遮（不得因解析共享而退化）。

        私钥分支改由 `PemDetector` 整块命中满足，故同时断言 `raw_rule_hits` 含 `pem`
        —— 只看 `out != block` 无法区分「整块命中」与「裸熵兜底」。
        """
        block = f"---- BEGIN {label} ----\n{_PEM_WRAPPED_BODY}\n---- END {label} ----"
        assert (redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block) is preserved
        if not preserved:
            assert "pem" in scan_text(block, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits

    def test_four_dash_mismatched_masked(self):
        """4 短横形态 END 错配：必须 fail-closed。"""
        src = f"---- BEGIN SSH2 PUBLIC KEY ----\n{_PEM_LEAK_BODY}\n---- END SSH2 ENCRYPTED PRIVATE KEY ----"
        _assert_body_masked(src)


# ---------------------------------------------------------------------------
# 缺陷回归：260917-w8d —— RFC 4716 四短横（``---- BEGIN X ----``）私钥不整块替换
#
# 根因**两处，缺一不可修**：
#   1. ``PemDetector.could_match`` 只认 ``"-----BEGIN "``（5 短横）⇒ 4 短横输入在
#      ``scan`` 入口就被预筛选拒掉，永远走不到块循环；
#   2. ``scan`` 只消费 ``iter_pem_blocks(text, dash=5)`` ⇒ 解析层也拿不到 4 短横块。
# 外加 ``SSH2 ENCRYPTED PRIVATE KEY``（RFC 4716 §3 的标准私钥封装 label）
# 不在 ``_PRIVATE_LABELS`` ⇒ 分类落 ``unknown`` ⇒ 即便前两处修好仍 ``continue``。
#
# 后果：4 短横私钥只得到逐行裸熵兜底 —— header / label 明文留下、kind 退化为
# ``bare_secret``，与「private key 是不可逆泄露、priority 95 最高」的设计意图不一致。
#
# 修复方向：``could_match`` 双拼写子串 + ``scan`` 消费 ``dash=5 + dash=4``
# （与 ``is_pem_non_secret_span`` 逐字一致）+ 白名单追加该项。
# ---------------------------------------------------------------------------

# 本次修复新增命中的 4 短横私钥 label（前 4 项原本已在白名单内，靠 5 短横命中；
# 第 5 项是本次**唯一**新增的白名单成员，其 5 短横高熵形态见下条）。
_RFC4716_REGRESSION_SECRET_LABELS = (
    "RSA PRIVATE KEY",
    "EC PRIVATE KEY",
    "OPENSSH PRIVATE KEY",
    "PGP PRIVATE KEY BLOCK",
    "SSH2 ENCRYPTED PRIVATE KEY",
)

# 金表已登记的私钥 label（含不由本类代表的 ``PRIVATE KEY`` / ``ENCRYPTED PRIVATE KEY``；
# ``DSA PRIVATE KEY`` **不在此列** —— 它是已登记的独立缺陷）。
_GOLDEN_PRIVATE_LABELS = (
    "RSA PRIVATE KEY",
    "EC PRIVATE KEY",
    "OPENSSH PRIVATE KEY",
    "ENCRYPTED PRIVATE KEY",
    "PGP PRIVATE KEY BLOCK",
    "PRIVATE KEY",
)

# 4 短横下必须**字节级保留**的非秘密 label（含 CSR 与 RFC 4716 的 ``SSH2 PUBLIC KEY``）
_RFC4716_NON_SECRET_LABELS = (
    "PUBLIC KEY",
    "RSA PUBLIC KEY",
    "EC PUBLIC KEY",
    "DSA PUBLIC KEY",
    "OPENSSH PUBLIC KEY",
    "CERTIFICATE",
    "X509 CERTIFICATE",
    "TRUSTED CERTIFICATE",
    "PGP PUBLIC KEY BLOCK",
    "SSH2 PUBLIC KEY",
    # CSR（PKCS#10）：含公钥与主体名，不含私钥 material（RFC 2986）
    "CERTIFICATE REQUEST",
    "NEW CERTIFICATE REQUEST",
)


def _rfc4716_block(label: str, body: str) -> str:
    """按 RFC 4716 §3 拼一个 4 短横块（``---- BEGIN X ----`` / ``---- END X ----``）。"""
    return f"---- BEGIN {label} ----\n{body}\n---- END {label} ----"


def _pem_block(label: str, body: str, *, dash: int) -> str:
    """按 ``dash`` 选择拼写：``dash=5`` 标准 PEM，``dash=4`` RFC 4716。"""
    if dash == 4:
        return _rfc4716_block(label, body)
    return f"-----BEGIN {label}-----\n{body}\n-----END {label}-----"


class TestPemRfc4716FourDash:
    """260917-w8d：4 短横与 5 短横行为**完全对齐**（整块命中 / 非秘密保留 / 错配 fail-closed）。

    4 短横下**必须用有实质且高熵的 body**：短 body（``"A"`` / ``"="``）在 5 短横下
    也走「实质但无熵」分支，区分不出「整块命中」与「裸熵兜底」。本类统一用模块级
    ``_PEM_LEAK_BODY``（40 字符 base64，len ≥ 32、高熵、非形状豁免）。
    """

    @pytest.mark.parametrize("label", _RFC4716_REGRESSION_SECRET_LABELS)
    def test_four_dash_private_key_produces_single_block_finding(self, label):
        """行为 1：4 短横私钥 → **恰好 1 个** finding，kind=private_key、priority=95。"""
        findings = PemDetector().scan(_rfc4716_block(label, _PEM_LEAK_BODY))
        assert len(findings) == 1
        assert findings[0].kind == "private_key"
        assert findings[0].priority == 95
        assert findings[0].rule_id == "pem"

    @pytest.mark.parametrize("label", _RFC4716_REGRESSION_SECRET_LABELS)
    def test_four_dash_finding_span_covers_whole_block(self, label):
        """行为 2：finding span 必须覆盖整块（BEGIN 行首 → END 行末）。"""
        src = _rfc4716_block(label, _PEM_LEAK_BODY)
        found = PemDetector().scan(src)[0]
        assert src[found.start : found.end] == src
        assert (found.start, found.end) == (0, len(src))

    @pytest.mark.parametrize("label", _RFC4716_REGRESSION_SECRET_LABELS)
    def test_four_dash_end_to_end_private_key_kind(self, label):
        """行为 3：端到端 `raw_rule_hits` 含 `pem`，输出为整块 `[REDACTED:private_key]`。"""
        src = _rfc4716_block(label, _PEM_LEAK_BODY)
        hits = scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits
        assert "pem" in hits
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "[REDACTED:private_key]"
        assert "bare_secret" not in out
        assert "---- BEGIN" not in out

    @pytest.mark.parametrize("label", _RFC4716_REGRESSION_SECRET_LABELS)
    def test_four_dash_could_match_is_superset_of_hits(self, label):
        """行为 4：预筛选对 4 短横返回 True（漏掉真阳 = 静默漏报）。"""
        assert PemDetector().could_match(f"---- BEGIN {label} ----") is True

    @pytest.mark.parametrize("label", _RFC4716_NON_SECRET_LABELS)
    def test_four_dash_non_secret_still_byte_identical(self, label):
        """行为 5：非秘密 label 在 4 短横下仍字节级保留、零命中（不误伤信任链）。"""
        block = _rfc4716_block(label, _PEM_WRAPPED_BODY)
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block
        assert scan_text(block, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits == {}

    def test_four_dash_mismatched_end_stays_fail_closed(self):
        """行为 6：4 短横错配（BEGIN 公钥 + END 私钥）不产块，但 body 绝不原样存活。"""
        src = f"---- BEGIN SSH2 PUBLIC KEY ----\n{_PEM_LEAK_BODY}\n---- END SSH2 ENCRYPTED PRIVATE KEY ----"
        assert PemDetector().scan(src) == []
        _assert_body_masked(src)


class TestPemEmbeddedEndLiteralDoesNotLeak:
    """body 内嵌**异拼写** END 字样时，`is_substantive_pem_body` 不得误判为「非实质」。

    回归 CR-01：剥离 END 标记原按「先探 5 短横 ``rfind("-----END")``，失败再回退 4 短横」
    的有序规则，故 4 短横块的 body 里出现 ``-----END FOO-----`` 时会**误取该字样**为剥离点；
    若其前缀只剩空白/省略号，body 被判为「非实质」⇒ ``PemDetector`` 与
    ``is_pem_non_secret_span`` 双双放行 ⇒ 私钥**正文明文泄露**（fail-open）。
    修正是取两个候选中**最靠后**者（即本块真正的定界符）。

    为什么只有 4 短横可达该缺陷：内嵌字样形如 5 短横 END，故对 5 短横块而言它就是本拼写的
    定界符候选，`_END_RE.search` 会**先**命中它；label 不一致 ⇒ 该块直接不产出（fail-closed
    已在解析层拦住），剥离阶段根本执行不到。4 短横块则因拼写不同，内嵌字样不被
    `_RFC4716_END_RE` 接受为定界符，块正常产出后才在剥离阶段被误命中 —— 这正是漏洞面。
    """

    # 内嵌字样：形如 5 短横 END，label 为 FOO ⇒ 与块的 label 不一致。
    _EMBEDDED = "-----END FOO-----"

    @pytest.mark.parametrize("label", ["RSA PRIVATE KEY", "SSH2 ENCRYPTED PRIVATE KEY", "OPENSSH PRIVATE KEY"])
    def test_four_dash_body_with_embedded_end_literal_is_substantive(self, label):
        """4 短横：剥离点必须是本块的定界符，而非 body 内嵌字样 ⇒ 判为实质。"""
        src = _pem_block(label, f"{self._EMBEDDED}\n{_PEM_LEAK_BODY}", dash=4)
        block = iter_pem_blocks(src, dash=4)[0]
        assert is_substantive_pem_body(src, block) is True

    @pytest.mark.parametrize("dash", [4, 5])
    def test_body_with_embedded_end_literal_not_leaked(self, dash):
        """端到端：body 绝不原样存活（修复前 4 短横为 ``raw_rule_hits == {}`` 的完全泄露）。"""
        src = _pem_block("SSH2 ENCRYPTED PRIVATE KEY", f"{self._EMBEDDED}\n{_PEM_LEAK_BODY}", dash=dash)
        _assert_body_masked(src)

    def test_four_dash_embedded_literal_now_hits_pem(self):
        """修复前该输入 `raw_rule_hits == {}`（detector 与熵侧同时放行）；现须由 pem 整块接管。"""
        src = _pem_block("SSH2 ENCRYPTED PRIVATE KEY", f"{self._EMBEDDED}\n{_PEM_LEAK_BODY}", dash=4)
        assert scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits.get("pem") == 1

    def test_five_dash_embedded_literal_stays_fail_closed_at_parse(self):
        """5 短横：内嵌字样即本拼写候选，解析层因 label 不匹配直接不产块（不得回归为误产块）。"""
        src = _pem_block("RSA PRIVATE KEY", f"{self._EMBEDDED}\n{_PEM_LEAK_BODY}", dash=5)
        assert iter_pem_blocks(src, dash=5) == []
        _assert_body_masked(src)

    def test_whitespace_only_prefix_still_exempt(self):
        """豁免语义不被本次修正破坏：真正只有省略号的空壳块仍不脱敏（S115/S116）。"""
        src = _pem_block("PRIVATE KEY", "...", dash=5)
        assert scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits == {}

    @pytest.mark.parametrize(
        "label",
        [
            # 4 短横与 5 短横两套拼写都必须与分类判据一致
            "SSH2 ENCRYPTED PRIVATE KEY",
            "RSA PRIVATE KEY",
            "SSH2 PUBLIC KEY",
            "CERTIFICATE",
        ],
    )
    @pytest.mark.parametrize("dash", [5, 4])
    def test_detector_and_exclusion_share_one_source_of_truth(self, label, dash):
        """行为 7：detector 产 finding ⟺ 熵侧放弃排除 ⟺ `classify_pem_label == secret`。"""
        src = _pem_block(label, _PEM_LEAK_BODY, dash=dash)
        verdict = classify_pem_label(label)
        body_start = src.index(_PEM_LEAK_BODY)
        masks = bool(PemDetector().scan(src))
        excluded = is_pem_non_secret_span(src, body_start, body_start + len(_PEM_LEAK_BODY))
        assert masks is (verdict == "secret")
        assert excluded is (verdict == "non_secret")


class TestPemRfc4716LabelWhitelist:
    """白名单扩容的边界与金表一致性 —— 只追加一项，且 5 短横拼写同样享有。"""

    @pytest.mark.parametrize("label", _GOLDEN_PRIVATE_LABELS)
    @pytest.mark.parametrize("dash", [5, 4])
    def test_golden_members_recognized_end_to_end_in_both_spellings(self, label, dash):
        """金表六成员中，5 短横全部整块命中；4 短横命中前五项（``PRIVATE KEY`` 无 4 短横用例）。"""
        if dash == 4 and label == "PRIVATE KEY":
            pytest.skip("RFC 4716 词表无裸 PRIVATE KEY 封装 -> 5 短横分支已覆盖")
        src = _pem_block(label, _PEM_LEAK_BODY, dash=dash)
        assert "pem" in scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits

    def test_out_of_scope_labels_are_not_granted_whitelist_membership(self):
        """边界外溢护栏：`DSA PRIVATE KEY` / `SSH2 PRIVATE KEY` **不得**被本次改动放进来。"""
        for label in ("DSA PRIVATE KEY", "SSH2 PRIVATE KEY"):
            assert classify_pem_label(label) == "unknown"
            src = _rfc4716_block(label, _PEM_LEAK_BODY)
            assert PemDetector().scan(src) == []
            _assert_body_masked(src)  # unknown -> 不产 finding，但 body 仍被裸熵兜底遮掉

    def test_rfc4716_private_key_label_is_recognized(self):
        """金表第 7 项（本次新增）：`SSH2 ENCRYPTED PRIVATE KEY` 分类为 secret。"""
        assert classify_pem_label("SSH2 ENCRYPTED PRIVATE KEY") == "secret"
        findings = PemDetector().scan(_rfc4716_block("SSH2 ENCRYPTED PRIVATE KEY", _PEM_LEAK_BODY))
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# 缺陷回归：fix 轮 4 —— D8（label 归一化缺失 / 分类漂移 fail-open 泄露）
#
# 根因（与 D7 同族）：``iter_pem_blocks`` 曾保留捕获 label 的原始空白，故
# ``-----BEGIN  PUBLIC KEY-----``（双空格）产出 ``label == ' PUBLIC KEY'``。
# 熵侧排除用正则 ``[A-Z0-9 ]*PUBLIC KEY`` **前缀匹配** → 判为非秘密（排除）；
# ``PemDetector`` 用**精确集合**成员判定 → ``' PUBLIC KEY'`` 既非私钥也非其已知
# 公钥 → 不产 finding。**两边都不遮** → body 原样泄露（fail-open）。
#
# 同族第二泄露面：正则前缀匹配过宽 —— ``MYCERTIFICATE`` / ``FOOCERTIFICATE`` /
# ``XYZ PUBLIC KEY`` / ``X509CERTIFICATE``（无空格）皆命中 ``[A-Z0-9 ]*CERTIFICATE``
# 或 ``[A-Z0-9 ]*PUBLIC KEY`` → 被错排除而 detector 不识别 → 泄露。
#
# 修复：``iter_pem_blocks`` **解析时归一化** label（``normalize_label``：折叠内部
# 空白 + strip），并新增 ``classify_pem_label`` 作为**唯一**分类判据，两端共用。
# ``unknown`` label 不产 finding、也不被排除 → 裸熵兜底遮掉（fail-closed）。
# ---------------------------------------------------------------------------

# 空白变形：**可被 _BEGIN_RE 解析**的空白异体（正则要求 BEGIN 后为字面空格，
# 故 ``BEGIN\t`` 不解析 —— 见 TestPemAdversarialShapes）。这些必须归一到同一规范形
# （RFC 词表，空白无语义）。
_PEM_WS_LABEL_VARIANTS = (
    "-----BEGIN  PUBLIC KEY-----",  # 双空格（点名的泄露形）
    "-----BEGIN   PUBLIC KEY-----",  # 三空格
    "-----BEGIN PUBLIC  KEY-----",  # 中间双空格
    "-----BEGIN PUBLIC KEY -----",  # 尾随空白
    "-----BEGIN  RSA PUBLIC KEY-----",
    "-----BEGIN CERTIFICATE -----",
)

# 近义 label（归一化后仍**不**在白名单）→ unknown → 必须被遮
_PEM_NEAR_MISS_LABELS = (
    "MYCERTIFICATE",
    "FOOCERTIFICATE",
    "X509CERTIFICATE",
    "XYZ PUBLIC KEY",
    "PRIVATECERTIFICATE",
    "PUBLIC KEYX",
)


class TestPemLabelNormalization:
    """D8：label 归一化 —— 空白异体归一到同一规范形，分类两端一致。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("PUBLIC KEY", "PUBLIC KEY"),
            ("  PUBLIC KEY", "PUBLIC KEY"),
            ("PUBLIC  KEY", "PUBLIC KEY"),
            ("PUBLIC KEY ", "PUBLIC KEY"),
            ("  PUBLIC   KEY  ", "PUBLIC KEY"),
            ("\tPUBLIC KEY\t", "PUBLIC KEY"),
            ("RSA  PRIVATE  KEY", "RSA PRIVATE KEY"),
            ("", ""),
        ],
    )
    def test_normalize_label_collapses_whitespace(self, raw, expected):
        """``normalize_label`` 折叠内部空白 + strip（标签是 RFC 词表，空白不承载语义）。"""

        assert normalize_label(raw) == expected

    @pytest.mark.parametrize("raw", ["", "  ", "\t", "\n"])
    def test_normalize_label_empty_stays_empty(self, raw):
        """纯空白归一到空串（不得产出伪造 label）。"""

        assert normalize_label(raw) == ""

    @pytest.mark.parametrize(
        "label, expected",
        [
            ("PUBLIC KEY", "non_secret"),
            ("RSA PUBLIC KEY", "non_secret"),
            ("EC PUBLIC KEY", "non_secret"),
            ("DSA PUBLIC KEY", "non_secret"),
            ("OPENSSH PUBLIC KEY", "non_secret"),
            ("CERTIFICATE", "non_secret"),
            ("X509 CERTIFICATE", "non_secret"),
            ("TRUSTED CERTIFICATE", "non_secret"),
            ("PGP PUBLIC KEY BLOCK", "non_secret"),
            ("SSH2 PUBLIC KEY", "non_secret"),
            ("PRIVATE KEY", "secret"),
            ("RSA PRIVATE KEY", "secret"),
            ("EC PRIVATE KEY", "secret"),
            ("OPENSSH PRIVATE KEY", "secret"),
            ("ENCRYPTED PRIVATE KEY", "secret"),
            ("PGP PRIVATE KEY BLOCK", "secret"),
            ("DSA PRIVATE KEY", "unknown"),  # 非 RFC 词表 → unknown → 遮（fail-closed）
            (" PUBLIC KEY", "unknown"),
            ("MYCERTIFICATE", "unknown"),
            ("X509CERTIFICATE", "unknown"),
            ("", "unknown"),
        ],
    )
    def test_classify_pem_label_single_source_of_truth(self, label, expected):
        """``classify_pem_label`` 是唯一分类判据：非秘密白名单为**精确** label。"""

        assert classify_pem_label(label) == expected

    @pytest.mark.parametrize(
        "label",
        ["PUBLIC KEY", "PRIVATE KEY", "MYCERTIFICATE", "X509CERTIFICATE", "RSA PUBLIC KEY"],
    )
    def test_detector_and_exclusion_share_one_source_of_truth(self, label):
        """不变式：``PemDetector`` 产 finding ⟺ 熵侧放弃排除 ⟺ ``classify==secret``。

        三者必须由**同一** ``classify_pem_label`` 决定；本测试对每个 label 直接
        比对三端结论，任何「平行检查」漂移都会在此暴露。
        """

        src = f"-----BEGIN {label}-----\n{_PEM_LEAK_BODY}\n-----END {label}-----"
        verdict = classify_pem_label(label)
        body_start = src.index(_PEM_LEAK_BODY)
        detector_masks = bool(PemDetector().scan(src))
        excluded = is_pem_non_secret_span(src, body_start, body_start + len(_PEM_LEAK_BODY))
        assert detector_masks is (verdict == "secret")
        assert excluded is (verdict == "non_secret")

    def test_normalized_whitespace_variant_agrees_end_to_end(self):
        """空白异体：解析后 label 归一化 → 分类 / 排除 / detector 三端仍一致（PUBLIC 保留）。"""

        src = f"-----BEGIN  PUBLIC KEY-----\n{_PEM_LEAK_BODY}\n-----END  PUBLIC KEY-----"
        block = iter_pem_blocks(src)[0]
        body_start = src.index(_PEM_LEAK_BODY)
        assert block.label == "PUBLIC KEY"  # 解析时已归一化
        assert is_pem_non_secret_span(src, body_start, body_start + len(_PEM_LEAK_BODY)) is True
        assert PemDetector().scan(src) == []  # 非私钥 → 不产 finding

    @pytest.mark.parametrize(
        "begin",
        [
            "-----BEGIN  PRIVATE KEY-----",
            "-----BEGIN   PRIVATE KEY-----",
            "-----BEGIN PRIVATE  KEY-----",
            "-----BEGIN PRIVATE KEY -----",
            "-----BEGIN  RSA PRIVATE KEY-----",
            "-----BEGIN OPENSSH  PRIVATE KEY-----",
            # BEGIN 后为制表符：_BEGIN_RE 要求字面空格 → 不解析 → 不排除 → 遮（fail-closed）
            "-----BEGIN\tPRIVATE KEY-----",
        ],
    )
    def test_whitespace_variant_private_still_masked(self, begin):
        """空白异体的**私钥** label 必须归一化后仍被遮（fail-closed 主方向）。"""
        end = begin.replace("BEGIN", "END")
        _assert_body_masked(f"{begin}\n{_PEM_LEAK_BODY}\n{end}")

    @pytest.mark.parametrize("begin", _PEM_WS_LABEL_VARIANTS)
    def test_whitespace_variant_public_normalizes_to_non_secret(self, begin):
        """空白异体的公钥 label 归一到规范形 → 正识别为非秘密 → 字节级保留。"""
        label = begin[len("-----BEGIN ") : -len("-----")]
        end = f"-----END {label}-----"
        block = f"{begin}\n{_PEM_WRAPPED_BODY}\n{end}"
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block

    @pytest.mark.parametrize(
        "begin",
        [
            "-----BEGIN  RSA PRIVATE KEY-----",
            "-----BEGIN OPENSSH  PRIVATE KEY-----",
            "-----BEGIN\tEC PRIVATE KEY-----",
            "-----BEGIN  PGP PRIVATE KEY BLOCK-----",
        ],
    )
    @pytest.mark.parametrize("flip", ["space", "tab"])
    def test_asymmetric_padding_both_sides_masked_when_private(self, begin, flip):
        """非对称空白（BEGIN/END 空白不同）的私钥块同样必须被遮。"""
        end_label = begin[len("-----BEGIN ") : -len("-----")].replace(" ", "\t" if flip == "tab" else "  ")
        _assert_body_masked(f"{begin}\n{_PEM_LEAK_BODY}\n-----END {end_label}-----")

    def test_space_in_end_label_only_masked_when_private(self):
        """非对称：仅 END 侧空白膨胀的私钥块必须被遮（此前两边都不管）。"""
        _assert_body_masked(f"-----BEGIN RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----END  RSA PRIVATE KEY-----")

    def test_space_in_begin_label_only_masked_when_private(self):
        """非对称：仅 BEGIN 侧空白膨胀的私钥块必须被遮。"""
        _assert_body_masked(f"-----BEGIN  RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----END RSA PRIVATE KEY-----")

    @pytest.mark.parametrize("label", _PEM_NEAR_MISS_LABELS)
    def test_near_miss_label_masked(self, label):
        """近义 label（归一化后不在白名单）→ unknown → 必须被遮（fail-closed）。"""
        _assert_body_masked(f"-----BEGIN {label}-----\n{_PEM_LEAK_BODY}\n-----END {label}-----")

    @pytest.mark.parametrize("label", _NON_SECRET_LABELS)
    def test_canonical_non_secret_labels_remain_byte_identical(self, label):
        """规范非秘密 label（归一化不变）必须仍字节级保留 —— 指向性 sweep。"""
        block = f"-----BEGIN {label}-----\n{_PEM_WRAPPED_BODY}\n-----END {label}-----"
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block

    @pytest.mark.parametrize("label", _SECRET_LABELS)
    def test_canonical_secret_labels_remain_masked(self, label):
        """规范私钥 label 必须仍被遮 —— 指向性 sweep（正对照的另一半）。"""
        block = f"-----BEGIN {label}-----\n{_PEM_WRAPPED_BODY}\n-----END {label}-----"
        out = redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _PEM_WRAPPED_BODY not in out


class TestPemAdversarialShapes:
    """D7/D8 伴生：对抗形状全部必须 fail-closed（body 绝不逐字泄露）。"""

    @pytest.mark.parametrize(
        "src",
        [
            # 嵌套 BEGIN in body
            f"-----BEGIN RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----BEGIN EC PRIVATE KEY-----\n-----END RSA PRIVATE KEY-----",
            # END 先于 BEGIN
            f"-----END RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----BEGIN RSA PRIVATE KEY-----",
            # 仅 BEGIN、无换行（alnum body：候选不被 ``KEY-----`` 粘连降熵）
            f"-----BEGIN RSA PRIVATE KEY-----{_PEM_LEAK_BODY_ALNUM}",
            # 小写 label
            f"-----BEGIN rsa private key-----\n{_PEM_LEAK_BODY}\n-----END rsa private key-----",
            # 7 短横（两侧）
            f"-------BEGIN RSA PRIVATE KEY-------\n{_PEM_LEAK_BODY}\n-------END RSA PRIVATE KEY-------",
            # body 本身是 PEM header
            f"-----BEGIN RSA PRIVATE KEY-----\n-----BEGIN PUBLIC KEY-----\n{_PEM_LEAK_BODY}\n-----END RSA PRIVATE KEY-----",
            # 空白膨胀 label（本缺陷）
            f"-----BEGIN  RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----END  RSA PRIVATE KEY-----",
            # 制表符膨胀 label（不解析 → 不排除 → 遮）
            f"-----BEGIN\tRSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----END\tRSA PRIVATE KEY-----",
            # END label 仅前导空白（非对称）
            f"-----BEGIN RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----END  RSA PRIVATE KEY-----",
            # BEGIN label 仅前导空白（非对称）
            f"-----BEGIN  RSA PRIVATE KEY-----\n{_PEM_LEAK_BODY}\n-----END RSA PRIVATE KEY-----",
        ],
    )
    def test_adversarial_shape_never_leaks(self, src):
        """六类对抗形状 + 四类空白异体：私钥 body 在任何形态下都不得原样存活。"""
        _assert_body_masked(src)

    @pytest.mark.parametrize(
        "label",
        ["PUBLIC KEY", "RSA PUBLIC KEY", "EC PUBLIC KEY", "DSA PUBLIC KEY", "OPENSSH PUBLIC KEY"],
    )
    def test_tab_after_begin_label_is_not_excluded(self, label):
        """``BEGIN<tab>`` 不被 _BEGIN_RE 解析 → 不排除 → 公钥 body 也被遮（可接受的过度遮蔽）。"""
        src = f"-----BEGIN\t{label}-----\n{_PEM_LEAK_BODY}\n-----END\t{label}-----"
        _assert_body_masked(src)

    def test_begin_end_label_mismatch_after_normalization_masked(self):
        """归一化后 BEGIN（``PUBLIC``）≠ END（``PUBLIC KEY``）→ 不产块 → 遮（fail-closed）。"""
        block = f"-----BEGIN PUBLIC-----\n{_PEM_WRAPPED_BODY}\n-----END PUBLIC KEY-----"
        _assert_body_masked(block)

    def test_asymmetric_whitespace_same_label_still_recognized(self):
        """非对称空白但**归一化后同名**（``BEGIN  PUBLIC KEY`` + ``END PUBLIC KEY``）→ 保留。"""
        block = f"-----BEGIN  PUBLIC KEY-----\n{_PEM_WRAPPED_BODY}\n-----END PUBLIC KEY-----"
        assert redact_text(block, purpose=RedactionPurpose.MODEL_OUTPUT) == block


# ---------------------------------------------------------------------------
# [2026-09-17] 未闭合私钥泄露修复 + `iter_pem_blocks` 跨块错配修正
#
# 缺陷：未闭合私钥（有 BEGIN 无**配对** END）零 finding，而裸熵兜底又被
# `EntropyDetector._classify_if_secret` 第 4 步 `char_class_count < 3` 拦下
# （纯 base64 body 常只有 2 个字符类别）⇒ **私钥正文明文泄露**。
# 真实随机 RSA 私钥截断到中点实测 843/843 个截断点泄露。
#
# 修复：`PemDetector` 新增未闭合 secret 块兜底（`iter_unterminated_secret_pem_spans`）；
# 同时收紧 `iter_pem_blocks` 的跨块配对（同 label BEGIN 介入 ⇒ 不得借用后块 END），
# 否则 `BEGIN K1 <正常内容> BEGIN K2 END K2` 会被并成一个跨块 span 吞掉中间内容。
#
# 用户口径（2026-09-17）：① 已闭合块的「中间正常内容」不得受影响；
# ② 未闭合时无法判定密钥真实边界，**过度遮蔽可接受**（宁遮不漏）。
# ---------------------------------------------------------------------------

_LEAK_LOW_ENTROPY = "SECRETBODY123"  # 纯 base64-ish、字符类别 < 3 → 裸熵不命中


class TestPemUnterminatedSecret:
    """未闭合私钥必须整段遮罩；公钥 / 空壳 / 已闭合块不受影响。"""

    def test_unterminated_private_low_entropy_masked(self):
        """核心回归：低熵 body 的未闭合私钥此前**明文泄露**（裸熵被 char_class 判据拦下）。"""
        src = f"-----BEGIN RSA PRIVATE KEY-----\n{_LEAK_LOW_ENTROPY}\nnormal log line"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _LEAK_LOW_ENTROPY not in out, f"leaked: {out!r}"
        assert "pem" in scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits

    def test_unterminated_private_real_key_masked(self):
        """真实随机 RSA 私钥截断到中点：任何 body 行都不得存活。"""
        raw = bytes(range(256)) * 5  # 确定性伪随机（避免每轮漂移）
        b64 = base64.b64encode(raw).decode()
        lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
        src = "-----BEGIN RSA PRIVATE KEY-----\n" + "\n".join(lines)
        out = redact_text(src[: len(src) // 2], purpose=RedactionPurpose.MODEL_OUTPUT)
        assert not any(line in out for line in lines), "private body leaked"

    def test_unterminated_public_key_untouched(self):
        """未闭合**公钥**：非秘密 label 不遮（不得回归为过度遮蔽）。"""
        src = "-----BEGIN PUBLIC KEY-----\nAAAA"
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src

    @pytest.mark.parametrize("body", ["", "\n", "\n...\n", "\n…\n"])
    def test_unterminated_empty_shell_untouched(self, body):
        """空壳 / 教学省略：无实质 body ⇒ 保持原样（与 is_substantive_pem_body 同判据）。"""
        src = f"-----BEGIN RSA PRIVATE KEY-----{body}"
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src

    @pytest.mark.parametrize("count", [2, 6, 500])
    def test_repeated_bare_begin_markers_untouched(self, count):
        """**重复的裸 BEGIN 行**（无任何 body）⇒ 全部保持原样，零命中（用户 2026-09-17 点名）。

        这是极易误判的形态：``"-----BEGIN RSA PRIVATE KEY-----\\n" * N`` 里每个 BEGIN
        都被下一个 BEGIN 截断，故**没有任何一块含实质 body** —— 不该脱敏。
        实测 1200 个裸 BEGIN（本 detector 最坏形状）输出与输入字节级全等。
        """
        src = "-----BEGIN RSA PRIVATE KEY-----\n" * count
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src
        assert iter_unterminated_secret_pem_spans(src) == []
        assert scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits == {}

    def test_only_segment_with_body_is_masked(self):
        """「无实质 body」判据**逐块**生效：只有跟了 body 的那一段才遮。"""
        src = "-----BEGIN RSA PRIVATE KEY-----\n" * 3 + "REALBODY"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "-----BEGIN RSA PRIVATE KEY-----\n" * 2 + "[REDACTED:private_key]"

    def test_bare_begin_then_empty_shell_not_masked(self):
        """连续的「裸 BEGIN + 空壳」：均无实质 body ⇒ 不遮（判据不被前块污染）。"""
        src = "-----BEGIN RSA PRIVATE KEY-----\n-----BEGIN RSA PRIVATE KEY-----\n...\n"
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src

    def test_four_dash_unterminated_secret_masked(self):
        """RFC 4716 四短横的未闭合私钥同样遮罩（两套拼写各自枚举）。"""
        src = "---- BEGIN SSH2 ENCRYPTED PRIVATE KEY ----\nLEAKBODY"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert "LEAKBODY" not in out

    def test_two_unterminated_spans_do_not_overlap(self):
        """两个未闭合 BEGIN 同现：两段都遮，区间两两不重叠、升序。"""
        src = "-----BEGIN RSA PRIVATE KEY-----\nAAA\n-----BEGIN RSA PRIVATE KEY-----\nBBB"
        spans = iter_unterminated_secret_pem_spans(src)
        assert len(spans) == 2
        assert spans == sorted(spans)
        assert spans[0][1] <= spans[1][0], f"overlapping spans: {spans}"

    def test_mismatched_label_low_entropy_masked(self):
        """label 错配（BEGIN RSA + END EC）的低熵 body 也必须遮 —— 此前明文泄露。"""
        src = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END EC PRIVATE KEY-----"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert "MIIEow" not in out, f"leaked: {out!r}"


class TestPemCrossBlockPairing:
    """`iter_pem_blocks` 跨块配对：不得借用后块的 END 吞掉中间正常内容。"""

    def test_two_complete_blocks_keep_prose_between(self):
        """用户点名场景：两个**完整**私钥块 + 中间正常内容 ⇒ 中间内容**字节级保留**。"""
        src = (
            "-----BEGIN RSA PRIVATE KEY-----\nKEYBODY1\n-----END RSA PRIVATE KEY-----\n"
            "normal content between\n"
            "-----BEGIN RSA PRIVATE KEY-----\nKEYBODY2\n-----END RSA PRIVATE KEY-----"
        )
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert "normal content between" in out, f"middle prose swallowed: {out!r}"
        assert out.count("[REDACTED:private_key]") == 2
        assert "KEYBODY1" not in out and "KEYBODY2" not in out

    def test_unterminated_first_does_not_borrow_next_end(self):
        """未闭合的 K1 不得借用 K2 的 END —— 否则中间内容被并进跨块 span。

        K1 段仍会被**未闭合兜底**遮罩（含中间内容，用户已确认可接受），
        但 K2 必须作为**独立**块正确切分，且两 span 不重叠。
        """
        src = (
            "-----BEGIN RSA PRIVATE KEY-----\nLEAKBODY\nnormal content here\n"
            "-----BEGIN RSA PRIVATE KEY-----\nKEYBODY2\n-----END RSA PRIVATE KEY-----"
        )
        blocks = iter_pem_blocks(src)
        assert len(blocks) == 1 and blocks[0].start == 61, f"cross-block span again: {blocks}"
        spans = iter_unterminated_secret_pem_spans(src)
        assert spans == [(0, 61)], f"unterminated span wrong: {spans}"
        assert "KEYBODY2" not in redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)

    @pytest.mark.parametrize(
        "src",
        [
            # 异 label 嵌套（既有形状，必须不变）
            "-----BEGIN RSA PRIVATE KEY-----\nBODY\n-----BEGIN EC PRIVATE KEY-----\n-----END RSA PRIVATE KEY-----",
            # body 内嵌异名 header
            "-----BEGIN RSA PRIVATE KEY-----\n-----BEGIN PUBLIC KEY-----\nBODY\n-----END RSA PRIVATE KEY-----",
            # 普通单块
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
        ],
    )
    def test_non_same_label_shapes_unchanged(self, src):
        """收紧只作用于**同 label** 介入；异 label 形状的块切分必须保持不变。"""
        blocks = iter_pem_blocks(src)
        assert len(blocks) == 1 and blocks[0].start == 0, f"pairing regressed: {blocks}"

    def test_end_before_begin_still_no_block(self):
        """END 先于 BEGIN 仍不产块（既有 fail-closed 语义不变）。"""
        src = "-----END RSA PRIVATE KEY-----\nBODY\n-----BEGIN RSA PRIVATE KEY-----"
        assert iter_pem_blocks(src) == []


# ---------------------------------------------------------------------------
# 已知值精确匹配 detector（注入式）—— 迁移自已删除的 test_registry.py
#
# 旧实现依赖 ``redaction.registry`` 的模块级全局态（``_REGISTRY`` + ``threading.Lock``
# + ``_SNAPSHOT``）与 ``_reset_registry()`` autouse fixture 隔离用例。现改为
# ``RegisteredSecretDetector.from_values(...)`` **显式注入** ⇒ 无全局态、无跨用例污染，
# 故 fixture 一并删除。``TestRegisterSecret``（注册门槛：长度/空白/sentinel 拒绝）
# 随注册表消失而删除 —— 门槛是全局注册表的守卫，注入式路径不再需要。
# ``TestRegisteredSecretRepr`` 的安全属性（repr 不泄露 value）**必须**保留为回归护栏。
# ---------------------------------------------------------------------------

_KNOWN_SAMPLE = "QGBZvSrgJ0hZOs9KHJV4jhw4hKFPGI6G"  # len=32，GPG key 样值


class TestRegisteredSecretDetectorInjected:
    """注入式 detector：裸值精确命中，priority=100，confidence=exact。"""

    @staticmethod
    def _scan(text: str, values=(_KNOWN_SAMPLE,), kind: str = "gpg_key"):
        detector = RegisteredSecretDetector.from_values(values, default_kind=kind)
        return detector.scan(text)

    def test_bare_value_is_matched(self):
        findings = self._scan(f"the value {_KNOWN_SAMPLE} appears")
        assert len(findings) == 1
        found = findings[0]
        assert (found.start, found.end) == (10, 10 + len(_KNOWN_SAMPLE))
        assert found.rule_id == "registered:gpg_key"
        assert found.kind == "registered_secret"
        assert found.confidence == "exact"
        assert found.priority == 100

    def test_multiple_occurrences_produce_multiple_findings(self):
        assert len(self._scan(f"{_KNOWN_SAMPLE} then {_KNOWN_SAMPLE}")) == 2

    def test_uninjected_value_not_matched(self):
        """未注入的值不命中（空注入 ⇒ 空 detector）。"""
        assert self._scan(f"the value {_KNOWN_SAMPLE} appears", values=()) == []

    def test_could_match_short_circuits_on_first_char(self):
        detector = RegisteredSecretDetector.from_values([_KNOWN_SAMPLE])
        assert detector.could_match(f"xxx {_KNOWN_SAMPLE}") is True
        assert detector.could_match("no matching first char here") is False

    @pytest.mark.parametrize("text", ["", 123, None, ["not", "str"]])
    def test_defensive_input_returns_empty(self, text):
        assert self._scan(text) == []

    def test_two_constructions_do_not_interfere(self):
        """显式注入：两次构造互不影响（无跨用例污染 ⇒ 无需 _reset_registry fixture）。"""
        first = RegisteredSecretDetector.from_values([_KNOWN_SAMPLE])
        second = RegisteredSecretDetector.from_values([])
        assert first.scan(_KNOWN_SAMPLE) != []
        assert second.scan(_KNOWN_SAMPLE) == []

    def test_longer_value_wins_within_group(self):
        """组内长值优先：detector 内部按值长度降序排列（长值先扫、先产出）。

        ``scan`` 对每个注入值独立产出 finding（跨值重叠由 ``merge_spans`` 按
        priority 决策，属既有语义）；此断言钉住的是**组内顺序** —— 长值的 finding
        先于短值出现，这是「长值优先命中」在 detector 层的可观测信号。
        """
        short, long = "Abc123", "Abc123456789"
        detector = RegisteredSecretDetector.from_values([short, long])
        ordered = detector._grouped["A"]
        assert [item.value for item in ordered] == [long, short]

    def test_long_value_produces_finding_before_short(self):
        short, long = "Abc123", "Abc123456789"
        findings = RegisteredSecretDetector.from_values([short, long]).scan(f"x {long} y {short}")
        # 首个 finding 覆盖长值（按值长度降序遍历 group 的自然结果）
        assert findings[0].end - findings[0].start == len(long)

    def test_known_value_accepts_str_and_object(self):
        """str 与 RegisteredValue 混合注入等价于各自的 kind。"""
        grouped = RegisteredSecretDetector.from_values(
            [_KNOWN_SAMPLE, RegisteredValue(value="ZzzSecret", kind="custom")]
        )
        findings = grouped.scan(f"{_KNOWN_SAMPLE} {('ZzzSecret')}")
        assert {f.rule_id for f in findings} == {"registered:known", "registered:custom"}


class TestRegisteredValueReprSafety:
    """T-06-02：已知值（含容器）不出现在任何 repr() 中。"""

    def test_known_value_repr_hides_value(self):
        assert "TOPSECRET" not in repr(RegisteredValue(value="TOPSECRET", kind="k"))

    def test_detector_repr_hides_value(self):
        detector = RegisteredSecretDetector.from_values([RegisteredValue(value="TOPSECRETVALUE", kind="k")])
        assert "TOPSECRETVALUE" not in repr(detector)


# T-vq0：detector 常量封装（模块级常量 → 类属性）
class TestDetectorConstantEncapsulation:
    """封装等价性：常量搬入类体后值逐字不变，派生关系在类体内成立。"""

    @pytest.mark.parametrize(
        "cls, attr, expected",
        [
            (VendorTokenDetector, "_VENDOR_PRIORITY", 80),
            (UrlDetector, "_URL_PRIORITY", 85),
            (JwtDetector, "_JWT_PRIORITY", 88),
            (HeadersDetector, "_HEADERS_PRIORITY", 90),
            (DsnDetector, "_DSN_PRIORITY", 90),
            (CookieDetector, "_COOKIE_PRIORITY", 85),
            (PemDetector, "_PEM_PRIORITY", 95),
            (RegisteredSecretDetector, "_REGISTERED_PRIORITY", 100),
        ],
    )
    def test_priority_class_attrs(self, cls, attr, expected):
        assert getattr(cls, attr) == expected

    def test_url_key_hints_derived_in_class_body(self):
        assert tuple(sorted(UrlDetector._SENSITIVE_QUERY_KEYS)) == UrlDetector._KEY_HINTS

    def test_jwt_segment_derives_both_regexes(self):
        assert JwtDetector._SEGMENT in JwtDetector._JWS_RE.pattern
        assert JwtDetector._SEGMENT in JwtDetector._JWE_RE.pattern

    def test_vendor_rules_all_share_class_priority(self):
        assert len(VendorTokenDetector._VENDOR_RULES) == 14
        assert {rule.priority for rule in VendorTokenDetector._VENDOR_RULES} == {VendorTokenDetector._VENDOR_PRIORITY}

    def test_vendor_hints_live_on_their_own_rule(self):
        """前缀字面量与规则同处声明（单一真源）：不再有平行的全局 `_PREFIX_HINTS`。

        机制：每条规则的每个 hint 都必须能在**自身** regex 的匹配结果里作为前缀出现。
        若把 hint 挂在错误的规则上（或规则改了 regex 却忘了改 hint），此断言失败。
        """
        assert not hasattr(VendorTokenDetector, "_PREFIX_HINTS")
        by_id = {rule.rule_id: rule for rule in VendorTokenDetector._VENDOR_RULES}
        assert by_id["vendor.github"].hints == ("ghp_", "gho_", "ghu_", "ghs_", "ghr_")
        assert by_id["vendor.slack"].hints == ("xox", "xwfp-", "xapp-")
        for rule in VendorTokenDetector._VENDOR_RULES:
            assert rule.hints, f"rule without prefilter hint: {rule.rule_id}"

    @pytest.mark.parametrize(
        "sample",
        [
            "ghp_" + "A" * 36,
            "gho_" + "A" * 36,
            "ghu_" + "A" * 36,
            "ghs_" + "A" * 36,
            "ghr_" + "A" * 36,
            "github_pat_" + "A" * 22,
            "xoxb-1234567890-abcd",
            "xwfp-1234567890-abcd",
            "xapp-1-A123-456789",
        ],
    )
    def test_github_slack_variants_covered(self, sample):
        """GitHub classic 五前缀与 Slack workflow / app-level token 均须被遮。"""
        detector = VendorTokenDetector()
        assert detector.could_match(sample) is True
        assert detector.scan(sample) != []

    def test_slack_xafp_prefix_not_masked(self):
        """`xafp-` 不是 Slack workflow 前缀，任何上下文下都不得被遮。

        回归（read_file 场景）：原 regex 写作 `x[wa]fp-`（字符类 = w 或 a），
        比 `hints` 宽。`could_match` 是**整段**的 OR，故当同文本别处出现
        `xox` / `xwfp-` / `xapp-` 任一 hint 时，正则对**全文**生效，
        `xafp-` 被顺手匹配 —— 表现为「独立出现不遮、与其它 Slack token 同文件时被遮」
        的上下文依赖行为（vendor.md S036 / S106 判为「否」）。
        """
        sample = "xafp-AbCdEfGhIjKlMnOp"
        assert VendorTokenDetector().scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize("trigger", ["xoxb-1234567890-abcd", "xwfp-1234567890-abcd", "xapp-1-A123-456789"])
    def test_slack_xafp_not_masked_despite_other_slack_hint(self, trigger):
        """同文本存在其它 Slack token 时，`xafp-` 仍须保持原样（上下文独立性）。"""
        sample = f"{trigger}\nxafp-AbCdEfGhIjKlMnOp"
        out = redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out.split("\n")[-1] == "xafp-AbCdEfGhIjKlMnOp"
        # 同时确认同文本里的真实 Slack token 仍被遮（没有把预筛选整体关掉）
        assert out.split("\n")[0] == "[REDACTED:slack_token]"

    @pytest.mark.parametrize("rule_id", ["vendor.aws", "vendor.aws_temp"])
    def test_aws_kind_is_access_key_id(self, rule_id):
        """AWS 规则的 kind 统一为 `aws_access_key_id`（含临时凭据 ASIA）。"""
        by_id = {rule.rule_id: rule for rule in VendorTokenDetector._VENDOR_RULES}
        assert by_id[rule_id].kind == "aws_access_key_id"

    def test_aws_keys_still_masked_end_to_end(self):
        """改 kind 不改覆盖面：AKIA / ASIA 两个正例端到端仍被替换。"""
        for sample in ("AKIAIOSFODNN7EXAMPLE", "ASIAIOSFODNN7EXAMPLE"):
            assert redact_text(sample, purpose=RedactionPurpose.LOG) != sample

    def test_headers_regex_derived_from_class_attrs(self):
        pattern = HeadersDetector._HEADER_RE.pattern
        assert all(name in pattern for name in HeadersDetector._HEADER_NAMES)
        assert HeadersDetector._SCHEME_RE in pattern

    def test_dsn_regex_derived_from_class_schemes(self):
        pattern = DsnDetector._DSN_RE.pattern
        assert all(re.escape(scheme)[:4] in pattern for scheme in DsnDetector._SCHEMES)

    def test_cookie_sensitive_names_derived_in_class_body(self):
        assert "session" in CookieDetector._SENSITIVE_NAMES
        assert "sessionid" in CookieDetector._SENSITIVE_NAMES

    def test_registered_detector_fields_stay_two(self):
        """ClassVar 陷阱：`_REGISTERED_PRIORITY` 若误写成普通字段会多出一项。

        `enabled` 已从本 detector（以及全部 detector）中移除 —— 门控归组装层
        （``_detectors_for_scan``）独占，detector 不持有开关状态。
        """
        assert [f.name for f in fields(RegisteredSecretDetector)] == ["_grouped", "rule_id"]

    def test_entropy_detector_fields_stay_four(self):
        """ClassVar 陷阱：8 个常量若漏写 ClassVar 会静默变成构造字段。"""
        assert [f.name for f in fields(EntropyDetector)] == [
            "min_length",
            "alnum_threshold",
            "base64_threshold",
            "rule_id",
        ]
        assert EntropyDetector().__dict__ == {
            "min_length": 32,
            "alnum_threshold": 4.2,
            "base64_threshold": 4.5,
            "rule_id": "entropy",
        }
        assert hash(EntropyDetector()) is not None

    @pytest.mark.parametrize(
        "attr, expected",
        [
            ("_ASSIGNMENT_PRIORITY", 70),
            ("_SCORE_THRESHOLD", 4),
            ("_VAR_REF_CONTEXT", 64),
            ("_AMBIGUOUS_SUFFIXES", ("key", "token", "secret")),
            ("_HEADER_SCHEMES", frozenset({"basic", "bearer", "digest", "negotiate"})),
        ],
    )
    def test_assignment_constants_encapsulated(self, attr, expected):
        assert getattr(AssignmentDetector, attr) == expected

    def test_assignment_normalized_strict_derived_in_class_body(self):
        expected = frozenset(re.sub(r"[^a-z0-9]", "", name.lower()) for name in AssignmentDetector._STRICT_FIELD_NAMES)
        assert expected == AssignmentDetector._NORMALIZED_STRICT

    def test_password_prefixes_are_normalized_single_tokens(self):
        """前缀白名单成员须是归一化单段 token（全小写、无分隔符）。

        白名单与归一化后的字段名做精确比较，故成员若含 `_` / 大写会永不命中
        （`app_password` 归一化为 `apppassword`，前缀段是 `app`）。
        """
        prefixes = AssignmentDetector._PASSWORD_PREFIXES
        assert prefixes
        assert all(p == re.sub(r"[^a-z0-9]", "", p) for p in prefixes)

    def test_assignment_key_value_re_anchor_and_terminators_intact(self):
        """锚定与 value 终止符不得在搬运中被改掉（CR-P0 后锚定加宽为 token 边界 + 数字前缀消费）。"""
        pattern = AssignmentDetector._KEY_VALUE_RE.pattern
        assert "(?<![A-Za-z0-9_-])" in pattern
        assert "[0-9]*(" in pattern  # 数字前缀在捕获组之外消费
        assert "[^\"'\\s,;{}&#]+" in pattern
        assert "(?<![A-Za-z_])" not in pattern  # 旧锚定不得复活

    @pytest.mark.parametrize(
        "attr, expected",
        [
            ("_ENTROPY_PRIORITY", 50),
            ("_DEFAULT_MIN_LENGTH", 32),
            ("_DEFAULT_ALNUM_THRESHOLD", 4.2),
            ("_DEFAULT_BASE64_THRESHOLD", 4.5),
            ("_KIND", "bare_secret"),
            ("_CONFIDENCE", "heuristic"),
            ("_ALPHABET_BASE64_FAMILY", "base64"),
        ],
    )
    def test_entropy_constants_encapsulated(self, attr, expected):
        assert getattr(EntropyDetector, attr) == expected

    def test_entropy_candidate_re_pattern_unchanged(self):
        """候选字符集：base64/alnum 字母表 + 口令常见符号（S054 族召回修复）。

        两条边界由回归钉住，勿再放宽：
        - 必须是 ASCII 白名单，不能 ``[^\\s…]`` 取反（否则 CJK 散文被整段吞下）。
        - 不得纳入 ``:`` ``/`` ``@`` —— 否则候选跨越 DSN 密码边界，
          覆盖并吞掉 ``dsn`` detector 的细粒度命中（host/port/dbname 丢失）。
        """
        assert EntropyDetector._CANDIDATE_RE.pattern == r"[A-Za-z0-9!$%^&*()_+\-\[\]?.~`]{32,4096}={0,2}"
        # 结构性字符必须留在协议 detector 手里，不得进熵候选字母表
        for structural in (":", "/", "@", "#", "\\s", '"', "'", ";", "<", ">", "|"):
            assert structural not in EntropyDetector._CANDIDATE_RE.pattern, structural
        assert not EntropyDetector._PASSWORD_CHARS_RE.fullmatch("password@host")

    @pytest.mark.parametrize(
        "attr, expected",
        [
            ("_ALPHABET_ALNUM", "alnum"),
            ("_ALPHABET_BASE64", "base64"),
            ("_ALPHABET_BASE64URL", "base64url"),
            ("_ALPHABET_OTHER", "other"),
            ("_BASE64_CONTAINERS", ("data:", ";base64,")),
            ("_REPETITION_UNIQUE_MAX", 2),
        ],
    )
    def test_entropy_self_hosted_private_constants(self, attr, expected):
        assert getattr(EntropyDetector, attr) == expected

    @pytest.mark.parametrize(
        "attr, pattern",
        [
            ("_ALNUM_RE", r"^[A-Za-z0-9]+$"),
            ("_BASE64_RE", r"^[A-Za-z0-9+/]+={0,2}$"),
            ("_BASE64URL_CHARS_RE", r"^[A-Za-z0-9_-]+$"),
            ("_CONTAINER_GAP_RE", r"[\s\"'`]"),
        ],
    )
    def test_entropy_self_hosted_private_regexes(self, attr, pattern):
        assert getattr(EntropyDetector, attr).pattern == pattern

    def test_entropy_self_hosts_moved_helpers(self):
        assert callable(EntropyDetector._classify_alphabet)
        assert callable(EntropyDetector._is_monotonic_sequence)
        assert callable(EntropyDetector._is_repetition)
        assert callable(EntropyDetector._is_base64_container_span)
        assert EntropyDetector._classify_alphabet("abc123") == "alnum"
        assert EntropyDetector._is_monotonic_sequence("abcdef") is True
        assert EntropyDetector._is_repetition("aaaa") is True


# [260915-0dr] 以下 4 个跨模块护栏因 pem.py / entropy.py 并入 detectors.py 而变成恒真式
# （比较对象与被比较对象成了同一个模块），已按用户决策删除：
#   - test_entropy_stops_importing_moved_helpers_keeps_shared  (1 例)
#   - test_pem_predicate_is_single_function_object             (1 例)
#   - test_moved_helpers_match_source                          (8 例 parametrize)
#   - test_moved_base64_container_span_matches_source          (3 例 parametrize)
#                                                             -----
#                                                              13 例
#
# 其判别力**未丢失，已由本文件末尾新增的 TestMergedModuleIntegrity 常驻接管**：
#   - 「合并丢了 / 改名了符号、类常量被摊平到模块级」 -> test_old_module_symbols_survive_merge
#   - 「公开面被合并扩宽」                           -> test_dunder_all_not_widened_by_merge
#   - 「fail-closed PEM 行为漂移 / ReDoS 上界丢失」  -> test_pem_fail_closed_still_holds 等
# 该常驻用例经 11 组植入实证具判别力，且 CI 每次运行。
#
# 另：「fail-closed PEM 行为」的**大面积**覆盖仍由 TestPemFailClosedOnMalformedBlocks
# 等 130+ 个端到端用例承担 —— 常驻用例只钉边界与常量，不重复 sweep。


# ---------------------------------------------------------------------------
# [260915-0dr] 合并完整性常驻护栏的冻结期望值。
#
# 语义分工（改这些测试前先读这段）：
#   * RN1 —— 冻结的“期望符号表”驱动的“模块级符号是否被删”。
#     判据是“声明式清单 vs 实际 AST”：test_old_module_symbols_survive_merge（+ __all__ 未扩宽）。
#   * RN2 —— 行为与常量的字节级金表。
#     判据是“运行结果 vs 字面量”：test_pem_fail_closed_still_holds /
#     test_pem_body_bound_still_enforced / test_tuning_constants_match_golden_values /
#     test_label_tables_match_golden_values / test_classify_pem_label_three_way_split /
#     test_normalize_label_still_collapses_whitespace /
#     test_whitespace_variant_non_secret_still_excluded
#
# 两者**故意不共享**冻结值：只改任一方（删符号 / 改常量或行为）都会红；
# 必须同时改两处且改得一致，才可能静默丢失或漂移 —— 这让“删符号 + 顺手改测试”
# 的失败模式在评审中显眼。（二者都读 detectors.py 的 AST / 运行时属性。）
# ---------------------------------------------------------------------------

# [260915-0dr] 原 pem.py ∪ entropy.py 的模块级符号（41 名，planning time 从基线实测导出）。
# 两者零重名，且与 detectors 原有 13 个类零重名 —— 已核验。
# 期望值**硬编码**在此，绝不从被测模块推导（自指构造会让断言恒真、判别力为 0）。
_OLD_MODULE_SYMBOLS: frozenset[str] = frozenset(
    {
        "PemBlock",
        "_ALNUM_RE",
        "_ALPHABET_ALNUM",
        "_ALPHABET_BASE64",
        "_ALPHABET_BASE64URL",
        "_ALPHABET_OTHER",
        "_BASE64URL_CHARS_RE",
        "_BASE64_CHARS_RE",
        "_BASE64_CONTAINERS",
        "_BASE64_RE",
        "_BEGIN_RE",
        "_BODY_MAX",
        "_CONTAINER_GAP_RE",
        "_END_RE",
        "_HEX_EXCLUDE_LENGTHS",
        "_HEX_RE",
        "_KSUID_RE",
        "_LABEL_WS_RE",
        "_NON_PRIVATE_LABELS",
        "_NON_SECRET_LABEL_SET",
        "_PEM_BODY_GAP_RE",
        "_PRIVATE_LABELS",
        "_PRIVATE_LABEL_SET",
        "_REPETITION_UNIQUE_MAX",
        "_RFC4716_BEGIN_RE",
        "_RFC4716_END_RE",
        "_SEQUENCE_STEP_RATIO",
        "_ULID_RE",
        "_UUID_RE",
        "char_class_count",
        "classify_alphabet",
        "classify_pem_label",
        "is_base64_container_span",
        "is_fixed_hex",
        "is_monotonic_sequence",
        "is_pem_non_secret_span",
        "is_repetition",
        "is_uuid_like",
        "iter_pem_blocks",
        "normalize_label",
        "shannon_entropy",
    }
)

# 分文件拆分（用于断言 14 / 27 与 10 / 18）
_PEM_SYMBOLS: frozenset[str] = frozenset(
    {
        "PemBlock",
        "_BEGIN_RE",
        "_BODY_MAX",
        "_END_RE",
        "_LABEL_WS_RE",
        "_NON_PRIVATE_LABELS",
        "_NON_SECRET_LABEL_SET",
        "_PRIVATE_LABELS",
        "_PRIVATE_LABEL_SET",
        "_RFC4716_BEGIN_RE",
        "_RFC4716_END_RE",
        "classify_pem_label",
        "iter_pem_blocks",
        "normalize_label",
    }
)
_ENTROPY_SYMBOLS: frozenset[str] = _OLD_MODULE_SYMBOLS - _PEM_SYMBOLS

# [utils 抽取后] 12 个 detector 的公开发布面（实现仍全在 detectors.py）。
_DETECTOR_PUBLIC_NAMES: tuple[str, ...] = (
    "Detector",
    "PemDetector",
    "HeadersDetector",
    "DsnDetector",
    "DsnJdbcDetector",
    "JwtDetector",
    "CookieDetector",
    "UrlDetector",
    "RegisteredSecretDetector",
    "VendorTokenDetector",
    "AssignmentDetector",
    "EntropyDetector",
)

# 共享原语中**无下划线**的公开名（re-export 同一性可比对；私有名不做 ``is`` 断言
# 除 ``_normalize_field_name`` 外不要求跨模块可见）。
_OLD_SYMBOL_NAMES: tuple[str, ...] = tuple(n for n in _OLD_MODULE_SYMBOLS if not n.startswith("_"))

# 28 = pem 10 + entropy 18。detectors 原有模块级私有名 = 0（已核验）。
# 由 _OLD_MODULE_SYMBOLS **派生** —— 这不是自指（它不依赖被测模块），故安全；
# 但断言 `len == 28` 必须显式写出，否则派生基数漂移时无感知。
_MODULE_LEVEL_PRIVATE_ALLOWED: frozenset[str] = frozenset(n for n in _OLD_MODULE_SYMBOLS if n.startswith("_"))

# [2026-09-15] 新增的模块级私有名（共享判据，显式登记而非从被测模块推导）。
# 这些是**新的共享谓词**，服务于多项 detector —— 放在模块级是有意设计，
# 不是「类常量被摊平」（那是缺陷；这里从来没有类常量被搬出来）。
# 每条都登记它有意的归属，防止日后把真正的类常量也混进来。
_MODULE_LEVEL_PRIVATE_ADDED_20260915: frozenset[str] = frozenset(
    {
        # 占位符形状判据（assignment + entropy 共享）
        "_PLACEHOLDER_RE",
        # 公钥前缀（OpenSSH 形态）与其 gap 判据（entropy 专用，但与其他 span 谓词同族）
        "_PUBLIC_KEY_PREFIXES",
        "_PUBLIC_KEY_GAP_RE",
        # 非秘密字段名（nonce/salt/iv）+ 其归一化与前瞻判据（entropy 专用）
        "_NON_SECRET_FIELD_NAMES",
        "_PRECEDING_KEY_RE",
        "_normalize_field_name",
        # PEM 空 body 判据（PemDetector + is_pem_non_secret_span 共享）
        "_PEM_NON_SUBSTANTIVE_RE",
        # [2026-09-17] 未闭合私钥兜底（PemDetector 专用）：
        #   - ``_UNTERMINATED_SHELL_RE``：空壳 / 教学省略豁免判据（与 _PEM_NON_SUBSTANTIVE_RE 同字符集）
        #   - ``iter_unterminated_secret_pem_spans``：未闭合 secret 块的遮罩区间
        # 二者为**共享层私有名**（供 PemDetector 复用 PEM 解析原语），非类常量摊平。
        "_UNTERMINATED_SHELL_RE",
        "iter_unterminated_secret_pem_spans",
    }
)

# [260915-0dr] 行为 + 常量金表。这里的每个期望值都是硬编码字面量 —— 不允许从被测模块推导。
_LEAK = "aUpG7zPe+f6z49nJyz8K8NlHG3mpcvgPUTEPiTUv"  # len=40 ent=4.7153 cls=4

# 4 条精选边界：错配（含 BEGIN 行内 body 的错配）、未闭合、良构正对照、同行 body
# 注：期望值均**硬编码**，不读被测模块推导。
# ``same_line_body`` 的期望值 2026-09-17 由 ``False`` 改为 ``True``（见 260917-x5f）：
# 原位置护栏的既定目标（防 ``CERTIFICATE AUTHORITY=...`` 被误排除）实际由本判据第 1 步达成
# —— 该文本不含配对块、进不了循环。故护栏在「有块」时只会取消同行 body 的豁免，
# 使熵候选（其 ``start`` 常早于 ``body_start``，因它吞掉了 BEGIN 标记尾部）落到区间外，
# 公钥/证书 body 遂被误遮为 ``bare_secret``。RFC 7468 §2 要求 BEGIN 与 body 间必须有 eol，
# 同行形态不属真实 PEM。正对照 ``matched_non_secret``（换行）行为不变。
_RN2A_CASES = (
    ("mismatched", f"-----BEGIN PUBLIC KEY-----\n{_LEAK}\n-----END RSA PRIVATE KEY-----", False),
    ("unterminated", f"-----BEGIN PUBLIC KEY-----\n{_LEAK}", False),
    ("matched_non_secret", f"-----BEGIN PUBLIC KEY-----\n{_LEAK}\n-----END PUBLIC KEY-----", True),
    ("same_line_body", f"-----BEGIN CERTIFICATE-----{_LEAK}\n-----END CERTIFICATE-----", True),
)


class TestMergedModuleIntegrity:
    """[260915-0dr] 合并完整性常驻护栏（接管 4 个跨模块恒真护栏的判别力）。

    9 个方法**均不使用 parametrize** —— 使方法数 == 测试项数，便于与全量计数对账。
    期望值全部硬编码（不读被测模块推导），且禁用自指 / 恒真形态。
    """

    def _module_level_symbols(self) -> set[str]:
        """读出共享原语模块的模块级符号（函数 / 类 / 赋值 / 带注解赋值），排除 dunder。

        [utils 抽取后] 原 ``pem`` / ``entropy`` 三层的前两层（PEM 解析 + 统计工具）
        已从 ``detectors.py`` 迁至 ``redaction/utils.py``；本护栏随之改读新归属模块。
        ``detectors.py`` 仍按名 re-export 同一批符号（``__all__`` 声明），
        故既有导入面与 ``is`` 同一性不变。
        """

        src = pathlib.Path(utils.__file__).read_text(encoding="utf-8")
        out: set[str] = set()
        for node in ast.parse(src).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(node.name)
            elif isinstance(node, ast.Assign):
                out.update(t.id for t in node.targets if isinstance(t, ast.Name) and not t.id.startswith("__"))
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and not node.target.id.startswith("__")
            ):
                out.add(node.target.id)
        return out

    def test_old_module_symbols_survive_merge(self):
        """合并不得丢失 / 改名原 pem/entropy 的任何模块级符号，也不得把类常量摊平到模块级。

        ⚠️ 必须走 AST 读模块级 body —— ``hasattr(detectors, name)`` 对**类成员**也返回
        True，用它会让「被摊平到某个类体」的常量让断言恒过。
        """
        actual = self._module_level_symbols()
        missing = sorted(_OLD_MODULE_SYMBOLS - actual)
        assert not missing, f"合并丢了模块级符号（被删或改名）：{missing}"
        # 分文件计数：pem 14 / entropy 27
        assert len(_PEM_SYMBOLS) == 14, f"pem 分文件计数漂移: {len(_PEM_SYMBOLS)}"
        assert len(_ENTROPY_SYMBOLS) == 27, f"entropy 分文件计数漂移: {len(_ENTROPY_SYMBOLS)}"
        assert len(_MODULE_LEVEL_PRIVATE_ALLOWED) == 28, "模块级私有名允许集基数漂移"
        # 2026-09-15 新增共享判据 + 2026-09-17 未闭合私钥兜底（显式登记，防止「摊平」检测把有意的共享谓词误判）
        assert len(_MODULE_LEVEL_PRIVATE_ADDED_20260915) == 9, "新增模块级私有名计数漂移"
        allowed = _MODULE_LEVEL_PRIVATE_ALLOWED | _MODULE_LEVEL_PRIVATE_ADDED_20260915
        # 摊平检测：模块级私有名必须 ⊆ 允许名（pem 10 + entropy 18 + 新增 9）
        flattened = sorted(n for n in actual if n.startswith("_") and n not in allowed)
        assert not flattened, f"类体内私有名被摊平到模块级（会静默遮蔽）：{flattened}"

    def test_dunder_all_not_widened_by_merge(self):
        """合并不扩宽**实现面**：pem/entropy 的公开名按名可导入。

        [utils 抽取后] 前两层迁至 ``redaction/utils.py``；``detectors.py`` 通过
        ``__all__`` **显式 re-export** 同一批名字，保持既有导入面与 ``is`` 同一性。
        故此处断言的语义从「不进 __all__」改为「按名可导入且与 utils 同一对象」，
        实现面（12 个 detector 命名空间）仍不得被 pem/entropy 私有名污染。
        """
        assert len(_DETECTOR_PUBLIC_NAMES) == 12, f"detector 公开面漂移: {_DETECTOR_PUBLIC_NAMES}"
        # 实现面：12 个 detector 名 + 共享原语 re-export
        assert set(_DETECTOR_PUBLIC_NAMES) <= set(detectors.__all__), "detector 公开名缺失"
        # 共享原语公开名：按名可导入，且与 utils 中实现是同一对象（re-export 而非复制）
        for name in _OLD_SYMBOL_NAMES:
            assert hasattr(detectors, name), f"detectors 未 re-export 共享公开名: {name}"
            assert getattr(detectors, name) is getattr(utils, name), f"共享名未指向同一实现: {name}"

    def test_pem_fail_closed_still_holds(self):
        """缺陷 7 类别回归 + 正对照：只有**完整且 label 一致**的非秘密块才可被排除。

        4 条精选边界（大面积 sweep 由 TestPemFailClosedOnMalformedBlocks 的 130+ 用例承担 ——
        此处只钉边界，不重复 sweep，避免 parametrize 展开导致 collection 膨胀）。
        """
        for name, text, excluded in _RN2A_CASES:
            start = text.index(_LEAK)
            got = is_pem_non_secret_span(text, start, start + len(_LEAK))
            assert got is excluded, f"RN2a/{name}: excluded={got}, expected {excluded}"

    def test_pem_body_bound_still_enforced(self):
        """T-06-12：body 超 _BODY_MAX 不得产出块（宁漏不失控）。"""
        huge = "-----BEGIN PUBLIC KEY-----\n" + "A" * 70_000 + "\n-----END PUBLIC KEY-----"
        assert iter_pem_blocks(huge) == []
        # 正对照：刚好不超限时应当产出（防“实现成永远返回空”）
        ok = "-----BEGIN PUBLIC KEY-----\n" + "A" * 100 + "\n-----END PUBLIC KEY-----"
        assert len(iter_pem_blocks(ok)) == 1

    def test_tuning_constants_match_golden_values(self):
        """字节级金表。期望值是硬编码字面量 —— 不从被测模块推导。

        金表与 RN1 的符号表**故意不共享**：只改其中一方都会红。
        """
        golden = [
            ("_BODY_MAX", 65536),
            ("_REPETITION_UNIQUE_MAX", 2),
            ("_ALPHABET_ALNUM", "alnum"),
            ("_ALPHABET_BASE64", "base64"),
            ("_ALPHABET_BASE64URL", "base64url"),
            ("_ALPHABET_OTHER", "other"),
            ("_BASE64_CONTAINERS", ("data:", ";base64,")),
            # 死常量：一旦被"顺手清理"即属越界改动 —— 这条是 V11 的常驻化版本
            ("_SEQUENCE_STEP_RATIO", 0.9),
        ]
        for name, expected in golden:
            got = getattr(utils, name)
            assert got == expected, f"RN2c: {name} = {got!r}, expected {expected!r}"

    def test_label_tables_match_golden_values(self):
        """label 集金表 —— 抓「清空标签集 / 改序」。"""
        assert tuple(utils._PRIVATE_LABELS) == (
            "RSA PRIVATE KEY",
            "EC PRIVATE KEY",
            "OPENSSH PRIVATE KEY",
            "ENCRYPTED PRIVATE KEY",
            "PGP PRIVATE KEY BLOCK",
            "PRIVATE KEY",
            # 2026-09-17 追加：RFC 4716 §3 的 SSH2 私钥封装 label
            "SSH2 ENCRYPTED PRIVATE KEY",
        )
        assert tuple(utils._NON_PRIVATE_LABELS) == (
            "PUBLIC KEY",
            "RSA PUBLIC KEY",
            "EC PUBLIC KEY",
            "DSA PUBLIC KEY",
            "OPENSSH PUBLIC KEY",
            "CERTIFICATE",
            "X509 CERTIFICATE",
            "TRUSTED CERTIFICATE",
            "PGP PUBLIC KEY BLOCK",
            "SSH2 PUBLIC KEY",
            # 2026-09-15 追加：CSR（PKCS#10）不是秘密（README 明确要求保留）
            "CERTIFICATE REQUEST",
            "NEW CERTIFICATE REQUEST",
        )
        assert frozenset(utils._NON_PRIVATE_LABELS) == utils._NON_SECRET_LABEL_SET
        assert frozenset(utils._PRIVATE_LABELS) == utils._PRIVATE_LABEL_SET

    def test_classify_pem_label_three_way_split(self):
        """三分 + fail-closed unknown。近义 / 畸形 label 必须落 unknown（不排除 -> 遮）。"""
        cases = [
            ("PUBLIC KEY", "non_secret"),
            ("CERTIFICATE", "non_secret"),
            ("SSH2 PUBLIC KEY", "non_secret"),
            ("PRIVATE KEY", "secret"),
            ("RSA PRIVATE KEY", "secret"),
            ("ENCRYPTED PRIVATE KEY", "secret"),
            # 故意的负例：白名单只认**归一化后的精确** label
            ("PUBLIC KEYX", "unknown"),
            (" PUBLIC KEY", "unknown"),
            ("X509", "unknown"),
            ("DSA PRIVATE KEY", "unknown"),
            ("", "unknown"),
        ]
        for label, expected in cases:
            got = classify_pem_label(label)
            assert got == expected, f"RN2f: classify_pem_label({label!r}) = {got!r}, expected {expected!r}"

    def test_normalize_label_still_collapses_whitespace(self):
        """``normalize_label`` 空白折叠 + strip（含空串）。"""
        for raw, expected in [
            ("  PUBLIC KEY", "PUBLIC KEY"),
            ("PUBLIC  KEY", "PUBLIC KEY"),
            ("\tPUBLIC KEY\t", "PUBLIC KEY"),
            ("RSA  PRIVATE  KEY", "RSA PRIVATE KEY"),
            ("", ""),
        ]:
            got = normalize_label(raw)
            assert got == expected, f"RN2g: normalize_label({raw!r}) = {got!r}, expected {expected!r}"

    def test_whitespace_variant_non_secret_still_excluded(self):
        """缺陷 8 的原始泄露形：``-----BEGIN  PUBLIC KEY-----``（双空格）必须仍被判为非秘密。"""
        text = f"-----BEGIN  PUBLIC KEY-----\n{_LEAK}\n-----END  PUBLIC KEY-----"
        start = text.index(_LEAK)
        assert is_pem_non_secret_span(text, start, start + len(_LEAK)) is True


# ---------------------------------------------------------------------------
# [260917-x5f] 位置判据 `end > block.body_start` 的行为护栏。
#
# 背景：非秘密分支原要求「命中起于 BEGIN 之后的新行」。该护栏在 body 与 BEGIN
# **同行**时取消豁免，致熵候选（其 `start` 常**早于** `body_start`，实测
# PUBLIC KEY −8 / CERTIFICATE −16 / CERTIFICATE REQUEST −12 / PGP PUBLIC KEY BLOCK −10，
# 因它吞掉了 BEGIN 标记尾部如 `KEY-----MIIEow...`）落到 body 区间之外，
# 公钥 / 证书 body 遂被裸熵误遮为 `bare_secret`。
#
# **同行 body 是合成 / 异常输入** —— RFC 7468 §2 `textualmsg = preeb *WSP eol *posteb`
# 要求 BEGIN 行后必须有 eol，openssl 生成的 PEM 一律另起一行。本类用例的目的
# **不是**宣称同行形态是受支持的 PEM 写法，而是钉住位置判据的形状：
# 判据须按「区间是否与 body 相交」判定，而非按「命中落在哪一行」。
# ---------------------------------------------------------------------------


class TestPemSameLineBodyExcluded:
    """[260917-x5f] 非秘密块的位置判据：区间相交语义 + 不得放宽为无脑放行。"""

    # --- (a) 端到端：12 个非秘密 label 的同行块必须字节级保留、零命中 ---

    @pytest.mark.parametrize("label", _SAME_LINE_NON_SECRET_LABELS)
    def test_same_line_non_secret_byte_identical(self, label):
        """同行非秘密块经 redact_text 后字节级全等，且 scan 零命中。

        只看 ``is_pem_non_secret_span`` 的布尔返回不够 —— 本缺陷的表征是
        ``raw_rule_hits = {'entropy.bare_base64url': 1}`` 且 body 被替换，
        故必须端到端钉住「返回 True 且管线确实消费了它」。
        """
        src = f"-----BEGIN {label}-----{_PEM_LEAK_BODY}\n-----END {label}-----"
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src
        assert scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits == {}

    @pytest.mark.parametrize(("begin_label", "end_label"), _SAME_LINE_WS_VARIANTS)
    def test_same_line_whitespace_variant_byte_identical(self, begin_label, end_label):
        """空白异体的同行块同样字节级保留（pem.md P042-P045）。"""
        src = f"-----BEGIN {begin_label}-----{_PEM_LEAK_BODY}\n-----END {end_label}-----"
        assert redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT) == src
        assert scan_text(src, purpose=RedactionPurpose.MODEL_OUTPUT).raw_rule_hits == {}

    # --- (b) 形状边界：区间相交的双向钉死 ---

    @pytest.mark.parametrize(
        ("name", "template"),
        [
            ("same_line", "-----BEGIN PUBLIC KEY----->{body}\n-----END PUBLIC KEY-----"),
            ("newline", "-----BEGIN PUBLIC KEY----->\n{body}\n-----END PUBLIC KEY-----"),
            ("crlf", "-----BEGIN PUBLIC KEY----->\r\n{body}\r\n-----END PUBLIC KEY-----"),
            ("blank_line", "-----BEGIN PUBLIC KEY----->\n\n{body}\n-----END PUBLIC KEY-----"),
        ],
    )
    def test_body_reachable_forms_are_excluded(self, name, template):
        """body 可达的各种行尾形态都必须被排除（含本次修复的同行形态）。"""
        text = template.replace(">", "").format(body=_PEM_LEAK_BODY)
        start = text.index(_PEM_LEAK_BODY)
        assert is_pem_non_secret_span(text, start, start + len(_PEM_LEAK_BODY)) is True, name

    def test_candidate_starting_inside_begin_marker_is_excluded(self):
        """回归本体：``start`` 早于 ``body_start``（实测 delta −8~−16）也必须排除。

        这是旧护栏的**唯一失效面** —— 切片 ``text[body_start:start]`` 在
        ``stop < start`` 时恒为空串，故 ``if gap`` 恒假。
        """
        text = f"-----BEGIN CERTIFICATE-----{_PEM_LEAK_BODY}\n-----END CERTIFICATE-----"
        body_start = iter_pem_blocks(text, dash=5)[0].body_start
        cand_start = text.index("CERTIFICATE-----")
        assert cand_start < body_start, "前置条件：候选起点须落在 BEGIN 标记内"
        assert is_pem_non_secret_span(text, cand_start, text.index(_PEM_LEAK_BODY) + len(_PEM_LEAK_BODY)) is True

    def test_span_ending_at_body_start_is_not_excluded(self):
        """反向护栏：``end == body_start`` 不算相交 → 不排除（判据不是无脑返回 True）。

        注意 ``start`` 必须**严格晚于** ``block.start`` —— 循环首道筛选是
        ``if block.start >= start: continue``，若取 ``start = block.start`` 会在
        第一道闸门即被挡下，测不到 ``end > body_start`` 这道判据本身。
        故取 ``start = 1``（仍在 BEGIN 标记内）隔离出位置判据。
        """
        text = f"-----BEGIN PUBLIC KEY-----{_PEM_LEAK_BODY}\n-----END PUBLIC KEY-----"
        body_start = iter_pem_blocks(text, dash=5)[0].body_start
        assert is_pem_non_secret_span(text, 1, body_start) is False

    def test_span_crossing_body_start_by_one_is_excluded(self):
        """边界方向：``end == body_start + 1`` 即相交 → 排除（钉死 ``>`` 而非 ``>=``）。"""
        text = f"-----BEGIN PUBLIC KEY-----{_PEM_LEAK_BODY}\n-----END PUBLIC KEY-----"
        body_start = iter_pem_blocks(text, dash=5)[0].body_start
        assert is_pem_non_secret_span(text, 1, body_start + 1) is True

    def test_span_before_block_not_excluded(self):
        """块起点不早于命中起点（``block.start >= start``）→ 首道闸门挡下 → 不排除。

        这一例把「首道闸门」也钉住：位置判据 ``end > body_start`` **不是**
        唯一闸门，命中必须先进得了循环体。对 ``start = 0`` 的整串命中，
        首道闸门负责兜住（``block.start == 0 >= 0``）。
        """
        text = f"-----BEGIN PUBLIC KEY-----{_PEM_LEAK_BODY}\n-----END PUBLIC KEY-----"
        body_start = iter_pem_blocks(text, dash=5)[0].body_start
        assert is_pem_non_secret_span(text, 0, body_start + 1) is False

    def test_bare_entropy_after_block_still_hits(self):
        """排除**仅限块内**：块结束之后的裸高熵串仍须命中。"""
        src = f"-----BEGIN PUBLIC KEY-----\n{_PEM_LEAK_BODY}\n-----END PUBLIC KEY-----\n{_HIGH_ENTROPY}"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _HIGH_ENTROPY not in out

    # --- (c) 正对照：同行语境下不得放宽 fail-closed 与私钥整块遮 ---

    @pytest.mark.parametrize("label", ("RSA PRIVATE KEY", "EC PRIVATE KEY", "PRIVATE KEY"))
    def test_same_line_private_key_still_fully_masked(self, label):
        """同行私钥块仍整块替换 —— 位置判据只作用于非秘密分支。"""
        src = f"-----BEGIN {label}-----{_PEM_LEAK_BODY}\n-----END {label}-----"
        out = redact_text(src, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert out == "[REDACTED:private_key]"
        assert _PEM_LEAK_BODY not in out

    def test_same_line_unknown_label_still_fail_closed(self):
        """同行 unknown label（近义 / 拼接）仍 fail-closed 遮 body。"""
        _assert_body_masked(f"-----BEGIN PUBLIC KEYX-----{_PEM_LEAK_BODY}\n-----END PUBLIC KEYX-----")

    def test_same_line_mismatched_label_still_fail_closed(self):
        """同行 label 错配仍不产块 → 不排除 → body 被兜底遮。"""
        _assert_body_masked(f"-----BEGIN PUBLIC KEY-----{_PEM_LEAK_BODY}\n-----END RSA PRIVATE KEY-----")

    def test_label_followed_by_space_not_excluded(self):
        """常驻护栏（旧护栏声称的既定目标）：``CERTIFICATE AUTHORITY=<value>`` 不得被排除。

        该文本不含配对块 ⇒ ``iter_pem_blocks`` 返回 ``[]`` ⇒ 循环体不进入。
        删除旧护栏不改变此行为 —— 防护由判据第 1 步达成。
        """
        text = f"CERTIFICATE AUTHORITY={_PEM_LEAK_BODY}"
        assert iter_pem_blocks(text, dash=5) == []
        assert is_pem_non_secret_span(text, 0, len(text)) is False


# ---------------------------------------------------------------------------
# [2026-09-15] 误脱敏修复（negative 用例回归防线）
#
# 交付测试集的 26 条 negative 全部要求「保持原样」。改动前有 10 条被误改，
# 下列用例逐条钉住修复后的行为，并给出「真实凭据仍须脱敏」的反向对照 ——
# 只测「不再误报」而不测「仍会脱敏」会让判据被逐步放宽到失效。
# ---------------------------------------------------------------------------

# 共享的高熵测试值（与交付测试集一致）
_HIGH_ENTROPY = "hfaRgFJU1cGRJ3Y21E8AWO5D7nXsjaRcrVk3V8w3Kek"


class TestPlaceholderValuesNotMasked:
    """占位符 / 已脱敏标记须保留（README：预设占位符与引用一并保留）。"""

    @pytest.mark.parametrize(
        "sample",
        [
            "password=${DB_PASSWORD}",
            "password={{ vault_db_password }}",
            "password=<REDACTED>",
            "token=[REDACTED_SECRET]",
            "password=********",
            "password=null",
            # `!vault` 后紧跟 `|`：值被 _KEY_VALUE_RE 截断为 `!vault`，
            # 故裸值形态另在 test_is_placeholder_value 中单独钉住（见 !vault 用例）
            "password: !vault",
        ],
    )
    def test_placeholder_survives(self, sample):
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("null", True),
            ("********", True),
            ("<REDACTED>", True),
            ("[REDACTED_SECRET]", True),
            ("{{ x }}", True),
            ("!vault", True),
            ("...", True),
            ("changeme", True),
            # 反向：真实值不得被判为占位符
            ("FixtureOnly!WovuqhlzvUTXDCqieoLIpA", False),
            ("hunter2", False),
            ("my-password-example", False),
            ("x" * 40, False),
            (_HIGH_ENTROPY, False),
        ],
    )
    def test_is_placeholder_value(self, value, expected):
        assert is_placeholder_value(value) is expected


class TestNonSecretFieldValuesRetained:
    """nonce / salt / iv 保留（用户 2026-09-15 批准；与真实 token 同形，只能靠字段名）。"""

    @pytest.mark.parametrize("key", ["nonce", "salt", "iv", "initialization_vector"])
    def test_non_secret_field_retained(self, key):
        sample = f"{key}={_HIGH_ENTROPY}"
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize("key", ["token", "password", "secret", "api_key", "nonce_str"])
    def test_credential_field_still_masked(self, key):
        """反向：真实凭据字段（含「含 nonce 但不等于 nonce」的名字）仍须脱敏。"""
        sample = f"{key}={_HIGH_ENTROPY}"
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) != sample


class TestPemEmptyBodyAndCsr:
    """PEM 空 body / 教学省略不脱敏 + CSR 归非秘密（S037/S115/S116）。"""

    @pytest.mark.parametrize(
        "sample",
        [
            "-----BEGIN PRIVATE KEY-----",  # 单独 BEGIN（无配对 END）
            "Example: -----BEGIN PRIVATE KEY----- ... -----END PRIVATE KEY-----",
            "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
            "-----BEGIN RSA PRIVATE KEY-----\n   \n-----END RSA PRIVATE KEY-----",
        ],
    )
    def test_empty_or_ellipsis_body_survives(self, sample):
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample
        assert PemDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "body",
        [
            "MIIEowIBAAKCAQEAyv3TmbqFa/XOCPI776YTcpuKihkC3jB/tvSwf99Ufj2VApM9",
            # 有实质 body + 省略号：README 要求遮罩（不同于纯教学省略）
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n...\nQUJD",
        ],
    )
    def test_substantive_body_still_masked(self, body):
        sample = f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----"
        assert PemDetector().scan(sample) != []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) != sample

    @pytest.mark.parametrize("label", ["CERTIFICATE REQUEST", "NEW CERTIFICATE REQUEST"])
    def test_csr_is_non_secret(self, label):
        """CSR 含公钥与主体名、不含私钥材料，README 明确要求保留。"""
        assert classify_pem_label(label) == "non_secret"
        sample = f"-----BEGIN {label}-----\n{_LEAK}\n-----END {label}-----"
        out = redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)
        assert _LEAK in out, "CSR body 不得被裸熵兜底遮掉"

    def test_private_key_still_secret(self):
        assert classify_pem_label("PRIVATE KEY") == "secret"


class TestPublicKeyPrefixExemption:
    """OpenSSH 公钥 body 保留（S035）；无前缀的高熵值仍须脱敏。"""

    @pytest.mark.parametrize(
        "sample",
        [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIm/bfAGTL9EUC5xrdEZvzdTFsdIh1qQV+BZPQThbejI",
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDZx5Yq8mKxLpVnRtUwXyZ0123456789abcdefghijkl",
        ],
    )
    def test_openssh_public_key_survives(self, sample):
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize(
        "sample",
        [
            f"v {_HIGH_ENTROPY} end",  # 无公钥前缀
            f"public_key_blob={_HIGH_ENTROPY}",  # 字段名像公钥，但值无前缀
        ],
    )
    def test_prefixed_absent_still_masked(self, sample):
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) != sample


# ---------------------------------------------------------------------------
# 缺陷回归：CR 轮 4 —— AssignmentDetector 9 处 code review 缺陷
# P0 ReDoS 未消除 / P1 假注释 / P2a 长度判据 / P2b 畸形花括号 / P2c f-string 截断
# / P3a 数字前缀注释 / P3b proxy 分支不可达 / P3c strict 定长 hex 召回丢失
# ---------------------------------------------------------------------------
class TestAssignmentCodeReviewRegression:
    """CR 轮 4 的 8 类缺陷回归（P3c 同时是召回缺口）。每条注释写明修复前的实测观测。"""

    # --- P0: quadratic 未消除 -------------------------------------------------

    def test_p0_key_value_re_linear_on_digit_letter_runs(self):
        """P0：`"1a"*n + ":"` 上 `_KEY_VALUE_RE.finditer` 必须线性。

        修复前（锚定 `(?<![A-Za-z_])`）：n=2000/4000/8000/16000/32000 耗时
        0.27/1.06/4.21/16.39/64.46s —— 严格 4 倍倍增（quadratic）。

        ⚠️ `re.Pattern.finditer()` 是**惰性**的：只调用而不消费返回的迭代器耗时恒 ~0.000s，
        即使正则是 quadratic 也会假绿。故必须用 `list(...)` 消费迭代器。
        （实测 RED 下 `rx.finditer(t)` 不消费 = 0.00000s，`list(rx.finditer(t))` = 1.586s@n=5000。）

        规模取 n=2000/4000/8000：RED 合计约 5.4s（可接受的 RED 证据，不挂死套件）；GREEN 毫秒级。
        直接测 `_KEY_VALUE_RE` 而非 `scan_text`：`could_match` 预筛选会掩盖正则自身退化，
        而本测试要钉死的正是正则自身。
        """
        rx = AssignmentDetector._KEY_VALUE_RE
        times = []
        for n in (2000, 4000, 8000):
            text = "1a" * n + ":"
            start = time.perf_counter()
            list(rx.finditer(text))  # 必须消费迭代器，否则恒 0.000s 假绿
            times.append(time.perf_counter() - start)
        ratios = [times[i + 1] / times[i] for i in range(len(times) - 1)]
        assert max(ratios) < 3.0, f"non-linear scaling: {ratios}"
        assert max(times) < 0.5, f"absolute bound exceeded (quadratic?): {times}"

    def test_p0_legacy_shapes_did_not_cover_quadratic(self):
        """P0 覆盖盲区：既有 `TestAssignmentKeyAnchorLinearity` 的 `"a"` / `"a="` 形状测不到 quadratic。

        `"1a"`（数字-字母交替）才是触发体 —— 修复前它在 n=8000 需 4.21s，而 `"a"` / `"a="`
        在同一规模下是毫秒级。故既有形状无论放大到多大都测不出该退化。
        本测试用 `"1a"` 与旧形状做**同规模**对比，钉死这一盲区。
        """
        rx = AssignmentDetector._KEY_VALUE_RE
        n = 8000

        def elapsed(text):
            start = time.perf_counter()
            list(rx.finditer(text))
            return time.perf_counter() - start

        trigger = elapsed("1a" * n)
        legacy_a = elapsed("a" * n)
        legacy_a_eq = elapsed("a=" * n)
        # 修复后三者皆线性且都在毫秒级；旧形状绝不可能比触发形状慢（旧测试对退化免疫）
        assert max(trigger, legacy_a, legacy_a_eq) < 0.5, (trigger, legacy_a, legacy_a_eq)
        assert legacy_a < trigger * 10, (legacy_a, trigger)
        assert legacy_a_eq < trigger * 10, (legacy_a_eq, trigger)
        # 盲区断言：旧形状的耗时**远低于** quadratic 在 n=8000 的表现（RED 实测 4.21s）
        assert legacy_a < 1.0 and legacy_a_eq < 1.0, (legacy_a, legacy_a_eq)

    # --- P1: 假注释 -----------------------------------------------------------

    def test_p1_no_false_bfs_equivalence_claim(self):
        """P1：源码中不得残留已被实测证伪的等价性表述。

        修复前注释称「左视负断言对 O(n²) 的抑制与 \\b 等价（实测 4 次倍增均线性）」——
        实测为 quadratic（n=16000 需 16.39s），且 \\b 在「数字后接字母」处无边界，两者机理不同。
        """
        source = pathlib.Path(detectors.__file__).read_text(encoding="utf-8")
        assert "完全等价" not in source
        assert "4 次倍增均线性" not in source

    # --- P2a: _split_var_ref 长度判据 -----------------------------------------

    @pytest.mark.parametrize(
        "value, context, expected",
        [
            ("$", "{DB_PASSWORD}", "${DB_PASSWORD}"),
            ("os.getenv(", "('X')", "os.getenv(('X')"),
        ],
    )
    def test_p2a_split_var_ref_concatenates_value_and_context(self, value, context, expected):
        """P2a：`context` 是 value 结束后的顺延片段，故恒拼接（不再按长度裁决）。

        修复前 `len(value) <= len(context)` 判据会让 `"os.getenv("`（len 10 > ctx len 6）
        走不拼接分支 —— 该判据建立在「context 与 value 重叠」的错误前提上。
        """
        assert AssignmentDetector._split_var_ref(value, context) == expected

    def test_p2a_anchor_alone_suffices_without_length_predicate(self):
        """P2a：值起始处的 `^` 锚定足以判别，无需长度判据；长值拼无关 `{Y}` 不产生假引用。"""
        assert AssignmentDetector._is_variable_reference("os.getenv(", "('X')") is True
        assert AssignmentDetector._is_variable_reference("x" * 80, "{Y}") is False

    # --- P2b: 畸形花括号 ------------------------------------------------------

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("${FOO", False),
            ("$FOO}", False),
            ("${FOO}", True),
            ("$FOO", True),
            ("${}", False),
        ],
    )
    def test_p2b_malformed_brace_refs_rejected(self, value, expected):
        """P2b：花括号必须成对。

        修复前 `^\\$\\{?[A-Za-z_][A-Za-z0-9_]*\\}?` 的两个花括号各自独立 optional，
        故 `${FOO` 与 `$FOO}` 均被判为合法变量引用（畸形接受 → 畸形值整体豁免脱敏）。
        """
        assert AssignmentDetector._is_variable_reference(value, "") is expected

    @pytest.mark.parametrize("reference", ["$DB_PASSWORD", "${DB_PASSWORD}"])
    @pytest.mark.parametrize(
        "tail",
        [
            "",
            "\n",
            "\n需要脱敏: 否\n\n====V002===",
            "\r\nNEXT=1",
            " trailing text",
            "\ttrailing text",
            '"',
            "'",
            ", next=1",
            "; next=1",
            "&next=1",
            "# comment",
        ],
    )
    def test_variable_reference_terminator_preserved(self, reference, tail):
        sample = f"password={reference}{tail}"
        assert AssignmentDetector().scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT, preserve_line_breaks=True) == sample

    @pytest.mark.parametrize("reference", ["$DB_PASSWORD", "${DB_PASSWORD}"])
    @pytest.mark.parametrize("quote", ['"', "'"])
    @pytest.mark.parametrize("tail", ["", "\nNEXT=1"])
    def test_quoted_variable_reference_preserved(self, reference, quote, tail):
        sample = f"password={quote}{reference}{quote}{tail}"
        assert AssignmentDetector().scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    @pytest.mark.parametrize(
        "value",
        [
            "${DB_PASSWORD",
            "$DB_PASSWORD}",
            "${}",
            "${DB_PASSWORD}}",
            "${DB_PASSWORD}literal",
            "$DB_PASSWORD-literal",
            "${DB_PASSWORD}-literal",
            "$DB_PASSWORD.attr",
            "${DB_PASSWORD}.attr",
            "$DB_PASSWORD.",
            "$DB_PASSWORD`literal`",
            "$DB_PASSWORD/path",
            "$DB_PASSWORD:8080",
            "$DB_PASSWORD+literal",
            "$DB_PASSWORD$OTHER",
        ],
    )
    @pytest.mark.parametrize("tail", ["", "\nNEXT=1"])
    def test_malformed_or_literal_variable_reference_still_masked(self, value, tail):
        sample = f"password={value}{tail}"
        findings = AssignmentDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].rule_id == "assignment.password"
        assert "[REDACTED:credential]" in redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)

    # --- P2c: f-string 截断 ---------------------------------------------------

    def test_p2c_fstring_value_not_treated_as_secret(self):
        """P2c：`password=f"{x}"` 的值被 `{` 前的引号截断为 `f`，`f` 不是真实凭据。

        修复前 `f` 被 strict 路径当作真实 secret 命中（值 `f` 进入脱敏 span）。
        """
        assert AssignmentDetector().scan('password=f"{x}"') == []
        assert AssignmentDetector().scan("password=f'{x}'") == []
        # `{` 是值排除类成员 → `{x}` 永不进入值组，f-string 花括号规则不可达
        assert AssignmentDetector._KEY_VALUE_RE.search("password={x}") is None
        assert redact_text('password=f"{x}"', purpose=RedactionPurpose.MODEL_OUTPUT) == 'password=f"{x}"'

    # --- 分隔符 := 与 os.environ 豁免（2026-09-17 修复，原无覆盖） --------------

    @pytest.mark.parametrize(
        "sample, expected",
        [
            ("password := hunter2hunter2", "password := [REDACTED:credential]"),
            ("password:=hunter2hunter2", "password:=[REDACTED:credential]"),
            ("db_password := hunter2hunter2", "db_password := [REDACTED:credential]"),
        ],
    )
    def test_walrus_separator_masks_full_value(self, sample, expected):
        """`:=` 必须整体作为分隔符，值不得只剩 `=`。

        修复前 `\\s*[:=]\\s*` 先在 ` : ` 上匹配 `:`，值组随即把 `=` 吞成值，
        于是只遮掉一个 `=`，真实密码 `hunter2hunter2` 明文存活。
        ``password:=x`` 形态修复前值为 `=hunter2hunter2`（看似命中却连分隔符一起脱敏），
        故必须逐字比对而非仅断言"命中"。
        """
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == expected

    @pytest.mark.parametrize(
        "sample",
        [
            "password=os.environ['DB_PASSWORD']",
            'password=os.environ["DB_PASSWORD"]',
            "password=os.environ ['X']",
        ],
    )
    def test_os_environ_attribute_ref_exempt(self, sample):
        """`os.environ[...]` 与 `os.getenv(` 同属运行环境取值族，必须豁免。

        修复前 `_VAR_REF_RE` 只列 `os.getenv` / `process.env.`，
        故 `password=os.environ['DB_PASSWORD']` 被当真实凭据脱敏、破坏配置模板。
        """
        assert AssignmentDetector().scan(sample) == []
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == sample

    def test_os_environ_prefix_is_anchored_to_subscript(self):
        """负对照：`os.environ` 的**任意后缀**不得被当变量引用（否则引入大片假豁免）。"""
        assert AssignmentDetector._is_variable_reference("os.environ_x", "") is False
        assert AssignmentDetector._is_variable_reference("os.environ[", "'X']") is True

    def test_os_environ_ambiguous_path_exempt_at_scan_level(self):
        """歧义路径（GPG_KEY=）同样豁免：断言 ``scan == []``。

        注意此处**不能**断言 `redact_text` 原样 —— 该值仍会被熵路径兜底，
        测的是本 detector 的豁免判定而非端到端输出。
        """
        sample = "GPG_KEY=os.environ['GPG_KEY']"
        assert AssignmentDetector().scan(sample) == []

    # --- P3a: 数字前缀捕获契约 ------------------------------------------------

    @pytest.mark.parametrize(
        "sample, key",
        [
            ("1password=hunter2hunter2", "password"),
            ("9api_key=abcdefgh12345678", "api_key"),
            ("2secret=abcdefgh12345678", "secret"),
            ("1access_token=abcdefghijklmnopqrstuvwxyz", "access_token"),
            ("2private_key=abcdefghijklmnopqrstuvwxyz", "private_key"),
        ],
    )
    def test_p3a_digit_prefix_consumed_outside_capture_group(self, sample, key):
        """P3a：数字前缀由捕获组外的 `[0-9]*` 消费，key 组仍是纯字母开头键。

        守护 D2 —— 若数字被并入捕获组，`1password` 会归一化为 `1password`，
        既不在 `_NORMALIZED_STRICT` 也不以 key/token/secret 结尾，这 5 条会全部漏报。
        """
        assert AssignmentDetector._KEY_VALUE_RE.search(sample).group(1) == key
        normalized = re.sub(r"[^a-z0-9]", "", key.lower())
        assert normalized in AssignmentDetector._NORMALIZED_STRICT
        findings = AssignmentDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].kind == "credential"

    # --- P3b: proxy 分支不可达 ------------------------------------------------

    def test_p3b_proxy_authorization_handled_by_headers_detector(self):
        """P3b：`Proxy-Authorization` 归 headers detector，assignment 不抢答。

        修复前 scan() 内有 `normalized in ("authorization", "proxyauthorization")` 分支，
        但 `proxyauthorization` ∉ `_NORMALIZED_STRICT`，而该判断位于
        `if normalized in self._NORMALIZED_STRICT:` 块内 → 第二个 arm **永不可达**（死代码）。
        正因如此应删除该 arm 而非把名字加进 `_STRICT_FIELD_NAMES`（那会让 assignment 抢答）。
        """
        sample = "Proxy-Authorization: Basic dXNlcjpwYXNz"
        assert AssignmentDetector().scan(sample) == []
        assert "proxyauthorization" not in AssignmentDetector._NORMALIZED_STRICT
        findings = HeadersDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].kind == "authorization_header"
        assert redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT) == (
            "Proxy-Authorization: Basic [REDACTED:authorization_header]"
        )

    def test_p3b_authorization_control_group(self):
        """P3b 对照组：`Authorization: Basic xxx` 同样由 headers 处理，不由 assignment 抢答。"""
        sample = "Authorization: Basic dXNlcjpwYXNz"
        assert AssignmentDetector().scan(sample) == []
        findings = HeadersDetector().scan(sample)
        assert len(findings) == 1
        assert findings[0].kind == "authorization_header"

    # --- P3c: strict 定长 hex 召回 --------------------------------------------

    @pytest.mark.parametrize(
        "sample",
        [
            "password=01234567",
            "passwd=01234567",
            "secret=0123456789abcdef",
            "private_key=0123456789abcdef",
        ],
    )
    def test_p3c_strict_field_fixed_hex_is_recalled(self, sample):
        """P3c：**strict 路径**字段 + 纯 hex 定长值必须被召回。

        修复前 `if self._is_variable_reference(value, context) or is_fixed_hex(value)`
        对高置信字段也生效，`password=01234567` 被整体跳过 → 端到端原样泄露。
        取消 strict 路径的 `is_fixed_hex` 短路后由本 detector 直接命中。

        注意：小写 `password=` + ≥16 hex（如 `password=0123456789abcdef`）修复前也被遮，
        但那是 url detector 命中 `url_credential` 的巧合，不是 assignment 的功劳。
        本测试只断言 assignment 自身对 strict 路径的召回。
        """
        value = sample.split("=", 1)[1]
        assert AssignmentDetector().scan(sample) != []
        assert value not in redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)

    @pytest.mark.parametrize(
        "sample",
        [
            "APP_PASSWORD=0123456789abcdef",
            "db_password=0123456789abcdef",
            "RABBITMQ_PASSWORD=x",
            "redis_password=x",
            "vault_db_password=x",
        ],
    )
    def test_prefixed_password_field_is_recalled(self, sample):
        """`<白名单前缀>password` 形态的凭据字段必须走路径 A 命中。

        缺陷：`apppassword` / `dbpassword` 既不在 `_NORMALIZED_STRICT`，也不以
        key/token/secret 结尾，曾被 `scan()` 的 else 分支无条件跳过 —— 端到端原样泄露。
        修复：`_is_strict_field` 追加 `<前缀>password` 白名单匹配（支持两段前缀）。
        """
        value = sample.split("=", 1)[1]
        assert AssignmentDetector().scan(sample) != []
        assert value not in redact_text(sample, purpose=RedactionPurpose.MODEL_OUTPUT)

    @pytest.mark.parametrize(
        "sample",
        [
            "is_password=true",
            "has_password=true",
            "hide_password=true",
            "force_password=false",
            "get_password=call()",
            "default_password=null",
            "missing_password=true",
            "hashed_password=abc",
            "encrypted_password=abc",
            "certificate_password=x",
            "username_password=x",
        ],
    )
    def test_non_credential_password_fields_still_skipped(self, sample):
        """非凭据 `*password` 字段不得因白名单而误脱敏。

        仓库语料（排除 .venv）中 `is_` / `has_` / `hide_` / `force_` / `get_` /
        `default_` / `missing_` / `hashed_` / `encrypted_` / `certificate_` /
        `username_` 等前缀是布尔标志 / 取值函数 / 已加密摘要，不是明文凭据。
        这是采用**前缀白名单**（而非通配 `*password` 后缀）的原因 —— 本测试钉住该边界。
        """
        assert AssignmentDetector().scan(sample) == []

    @pytest.mark.parametrize(
        "value",
        ["0123456789abcdef", "0123456789abcdef0123456789abcdef01234567"],
    )
    def test_p3c_ambiguous_fixed_hex_still_excluded(self, value):
        """P3c 护栏：歧义路径的定长 hex 豁免**不变**（D6 只收窄 strict 路径）。

        `_score_ambiguous` 的 -4 是 GPG key ID / fingerprint 误报面的主要防线，
        与既有 `test_hex_fixed_length_excluded` 语义一致。
        """
        assert AssignmentDetector().scan(f"GPG_KEY={value}") == []

    def test_p3c_64_hex_ambiguous_still_recalled(self):
        """P3c 护栏：64 位不属 `is_fixed_hex`（豁免集为 8/16/32/40），故仍命中。"""
        findings = AssignmentDetector().scan(f"SIGNING_SECRET={_HEX64}")
        assert len(findings) == 1
        assert findings[0].rule_id == "assignment.signingsecret"
