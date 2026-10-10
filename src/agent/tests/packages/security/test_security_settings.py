# -*- coding: utf-8 -*-
"""Tests for SecuritySettings (aidev_agent.pydantic_models) + resource_manager 下发通道。"""

from __future__ import annotations

import pytest
from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.pydantic_models import (
    RuleSpecConfig,
    SecurityCommandSettings,
    SecurityRedactionSettings,
    SecuritySettings,
)
from pydantic import ValidationError
from pydantic_core import PydanticUndefined


class TestSecuritySettingsFieldDefaults:
    """字段级 ``default_factory`` 环境变量兜底（平台下发之下的最后一层默认）。"""

    def test_default_true(self, monkeypatch):
        monkeypatch.delenv("BKAI_ENABLE_TOOL_REDACTION", raising=False)
        monkeypatch.delenv("BKAI_ENABLE_TOOL_UNTRUSTED_SANITIZE", raising=False)
        s = SecuritySettings()
        assert s.enable_tool_redaction is True
        assert s.enable_tool_untrusted_sanitize is False

    def test_default_false_for_review_auto(self, monkeypatch):
        monkeypatch.delenv("BKAI_ENABLE_COMMAND_REVIEW_AUTO", raising=False)
        assert SecuritySettings().command.enable_command_review_auto is False

    def test_env_disable(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_BLOCKLIST", "false")
        assert SecuritySettings().command.enable_command_blocklist is False

    def test_env_disable_dynamic_exec(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_BLOCKLIST_DYNAMIC_EXEC", "false")
        assert SecuritySettings().command.enable_command_blocklist_dynamic_exec is False

    def test_env_disable_unsupported(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_BLOCKLIST_UNSUPPORTED", "false")
        assert SecuritySettings().command.enable_command_blocklist_unsupported is False

    def test_env_disable_syntax_rules(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_SYNTAX_RULES", "false")
        assert SecuritySettings().command.enable_command_syntax_rules is False

    def test_default_false_for_syntax_rules(self, monkeypatch):
        """未设环境变量时结构约束族默认**关闭**（整族默认关闭，属 fail-open 基线）。"""
        monkeypatch.delenv("BKAI_ENABLE_COMMAND_SYNTAX_RULES", raising=False)
        assert SecuritySettings().command.enable_command_syntax_rules is False

    def test_env_enable_review_auto(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_REVIEW_AUTO", "true")
        assert SecuritySettings().command.enable_command_review_auto is True


class TestSecuritySettingsAllFields:
    def test_returns_all_fields(self, monkeypatch):
        monkeypatch.delenv("BKAI_ENABLE_TOOL_REDACTION", raising=False)
        monkeypatch.delenv("BKAI_ENABLE_COMMAND_REVIEW_AUTO", raising=False)
        settings = SecuritySettings()
        assert settings.enable_tool_redaction is True
        assert settings.command.enable_command_review_auto is False
        assert settings.command.command_approval_approvers == ""


class TestSecuritySettingsPlatformMapping:
    """平台下发 dict 直接构造 ``SecuritySettings`` 的两级取值优先级。"""

    def test_mapping_overrides_env(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_BLACKLIST", "true")
        settings = SecuritySettings(command={"enable_command_blocklist": False})
        assert settings.command.enable_command_blocklist is False  # 平台值覆盖环境变量

    def test_mapping_missing_falls_back_to_env(self, monkeypatch):
        monkeypatch.delenv("BKAI_ENABLE_COMMAND_BLACKLIST", raising=False)
        settings = SecuritySettings()
        assert settings.command.enable_command_blocklist is True  # 缺失字段 → 字段默认兜底

    def test_unknown_key_ignored(self):
        settings = SecuritySettings(unknown_feature=True)
        assert "unknown_feature" not in settings.model_dump()

    def test_no_from_env_classmethod(self):
        """``from_env()`` 已删除：统一配置入口是 AgentConfig.security_settings。"""
        assert not hasattr(SecuritySettings, "from_env")


class TestPartialMaskThresholdsConfig:
    """T-urf-03：partial 掩码三个阈值字段（默认 32/6/4，env 可覆盖，平台可下发）。"""

    @pytest.mark.parametrize(
        "field, env_name, expected_default",
        [
            ("redact_partial_min_len", "BKAI_REDACT_PARTIAL_MIN_LEN", 32),
            ("redact_partial_head", "BKAI_REDACT_PARTIAL_HEAD", 6),
            ("redact_partial_tail", "BKAI_REDACT_PARTIAL_TAIL", 4),
        ],
    )
    def test_default_from_env_fallback(self, monkeypatch, field, env_name, expected_default):
        monkeypatch.delenv(env_name, raising=False)
        assert getattr(SecurityRedactionSettings(), field) == expected_default

    @pytest.mark.parametrize(
        "field, env_name, env_value",
        [
            ("redact_partial_min_len", "BKAI_REDACT_PARTIAL_MIN_LEN", 8),
            ("redact_partial_head", "BKAI_REDACT_PARTIAL_HEAD", 2),
            ("redact_partial_tail", "BKAI_REDACT_PARTIAL_TAIL", 5),
        ],
    )
    def test_mapping_override(self, field, env_name, env_value):
        """平台下发值经嵌套 dict 覆盖字段默认（env 变量名仅作对照说明）。"""
        settings = SecuritySettings(redaction={field: env_value})
        assert getattr(settings.redaction, field) == env_value


_BASE_RAW = {
    "agent_name": "sec-agent",
    "prompt_setting": {"llm_code": "test-llm"},
    "knowledgebase_settings": {"knowledgebases": []},
    "conversation_settings": {"commands": []},
    "mcp_server_config": {"mcpServers": {}},
    "role_prompts": [],
}


class _StubRM(BaseResourceManager):
    """覆盖 ``retrieve_agent_config`` 以避开 HTTP，用于验证 security_settings 下发通道。"""

    def __init__(self, security_settings: dict | None):
        super().__init__(app_code="x", app_secret="y")
        self._security_settings = security_settings

    def retrieve_agent_config(self, agent_code: str, version=None, **kwargs) -> dict:
        raw = dict(_BASE_RAW)
        if self._security_settings is not None:
            raw["security_settings"] = self._security_settings
        return raw


class TestAgentConfigSecuritySettingsChannel:
    """`get_agent_config` 是从平台下发构造 SecuritySettings 的唯一入口。"""

    @pytest.mark.parametrize(
        "platform, expected_blacklist",
        [
            ({"command": {"enable_command_blocklist": False}}, False),  # 平台下发覆盖默认
            ({"command": {"enable_command_blocklist": True}}, True),
            (None, True),  # 无 security_settings 字段 → 字段默认
        ],
    )
    def test_platform_values_flow_into_agent_config(self, platform, expected_blacklist):
        rm = _StubRM(platform)
        cfg = rm.get_agent_config("a1")
        assert isinstance(cfg.security_settings, SecuritySettings)
        assert cfg.security_settings.command.enable_command_blocklist is expected_blacklist

    def test_platform_settings_are_construction_point(self):
        """SecuritySettings 由平台下发 dict 构造，AgentConfig 上可直接读到。"""
        rm = _StubRM({"enable_tool_redaction": False})
        cfg = rm.get_agent_config("a1")
        assert cfg.security_settings.enable_tool_redaction is False


class TestRedactionSwitchesAllDisableable:
    """全字段平等：17 个开关**没有不可关闭项**（原 D-06 mandatory 归真层已删除）。

    删除依据：mandatory 层使总开关 ``enable_redact_secrets=False`` 无法真正断开全部能力
    （registered / authorization_headers / private_keys 仍照跑），与
    「所有功能都需要有开关，总开关闭合时必须全部可关」冲突。
    """

    # 除总开关外的全部 ``enable_redact_*`` 分项开关（新增能力时必须同步登记）
    _CHILD_SWITCHES = (
        "enable_redact_registered_secrets",
        "enable_redact_authorization_headers",
        "enable_redact_private_keys",
        "enable_redact_jwt",
        "enable_redact_vendor_tokens",
        "enable_redact_structured_fields",
        "enable_redact_url_credentials",
        "enable_redact_dsn_passwords",
        "enable_redact_cookies",
        "enable_redact_bare_entropy",
    )

    @pytest.mark.parametrize("field", _CHILD_SWITCHES)
    def test_every_child_switch_accepts_platform_false(self, field):
        """每个分项开关都能被平台下发 False 真关闭（不再被静默归真）。"""
        settings = SecuritySettings(redaction={field: False})  # 不抛异常
        assert getattr(settings.redaction, field) is False

    @pytest.mark.parametrize("field", _CHILD_SWITCHES)
    def test_every_child_switch_direct_construction(self, field):
        """直接构造小模型同样不受保护层干预（不存在会改写构造输入的钩子）。"""
        assert getattr(SecurityRedactionSettings(**{field: False}), field) is False

    def test_platform_false_is_no_longer_forced_true(self):
        """原 D-06 归真行为已删除：private_keys=False 保持 False（不再被改写）。"""
        assert SecurityRedactionSettings(enable_redact_private_keys=False).enable_redact_private_keys is False

    def test_master_switch_disableable(self):
        """总开关本身也可被平台下发 False（硬熔断入口）。"""
        settings = SecuritySettings(redaction={"enable_redact_secrets": False})
        assert settings.redaction.enable_redact_secrets is False

    def test_no_switch_is_unreachable(self):
        """护栏：每个 ``enable_redact_*`` 字段都必须在可关闭清单内。

        新增开关若忘记登记，本用例会失败 —— 防止「又冒出一个关不掉的开关」。
        """
        declared = {name for name in SecurityRedactionSettings.model_fields if name.startswith("enable_redact_")}
        assert declared == {"enable_redact_secrets", *self._CHILD_SWITCHES}


class TestOptionalRedactionDisableable:
    """optional 五项脱敏可被逐项关闭。"""

    @pytest.mark.parametrize(
        "field",
        [
            "enable_redact_vendor_tokens",
            "enable_redact_structured_fields",
            "enable_redact_url_credentials",
            "enable_redact_dsn_passwords",
            "enable_redact_cookies",
        ],
    )
    def test_platform_false_respected(self, field):
        settings = SecuritySettings(redaction={field: False})
        assert getattr(settings.redaction, field) is False


class TestBareEntropyConfig:
    """裸熵兜底三配置项：默认值 + 平台覆盖 + 非 mandatory（CONTEXT D-07 / DESIGN §3.6）。"""

    @pytest.mark.parametrize(
        "mapping, expected",
        [
            (None, True),  # 默认开启（全 purpose，默认真实生效）
            ({"enable_redact_bare_entropy": False}, False),  # heuristic 层可关
            ({"enable_redact_bare_entropy": True}, True),
        ],
    )
    def test_enabled_switch(self, mapping, expected):
        settings = SecuritySettings(**({"redaction": mapping} if mapping else {}))
        assert settings.redaction.enable_redact_bare_entropy is expected

    @pytest.mark.parametrize(
        "mapping, expected",
        [
            (None, 32),  # 默认最小长度 32
            ({"redact_secrets_min_length": 16}, 16),  # 平台下发可放宽
        ],
    )
    def test_min_length(self, mapping, expected):
        settings = SecuritySettings(**({"redaction": mapping} if mapping else {}))
        assert settings.redaction.redact_secrets_min_length == expected

    @pytest.mark.parametrize(
        "mapping, expected",
        [
            (None, 4.2),  # 默认 alnum/Base64URL 阈值
            ({"redact_secrets_entropy_threshold": 5.0}, 5.0),
        ],
    )
    def test_entropy_threshold(self, mapping, expected):
        settings = SecuritySettings(**({"redaction": mapping} if mapping else {}))
        assert settings.redaction.redact_secrets_entropy_threshold == expected

    def test_not_mandatory(self):
        """裸熵是 heuristic 层，本就按 design 可关 —— 与全字段平等模型一致。"""
        assert SecurityRedactionSettings(enable_redact_bare_entropy=False).enable_redact_bare_entropy is False


_REDACTION_FIELD_NAMES = {
    "enable_redact_secrets",
    "enable_redact_registered_secrets",
    "enable_redact_authorization_headers",
    "enable_redact_private_keys",
    "enable_redact_jwt",
    "enable_redact_vendor_tokens",
    "enable_redact_structured_fields",
    "enable_redact_url_credentials",
    "enable_redact_dsn_passwords",
    "enable_redact_cookies",
    "enable_redact_bare_entropy",
    "redact_secrets_min_length",
    "redact_secrets_entropy_threshold",
    "redact_partial_min_len",
    "redact_partial_head",
    "redact_partial_tail",
    "known_sensitive_values",
}


class TestSecurityRedactionSettingsStandalone:
    """小配置可独立构造，字段归属与默认值精确（D-02 / D-03 / D-10）。"""

    def test_all_17_field_defaults_readable(self):
        """独立构造时 17 字段默认可读，5 个数值字段为既定默认。"""
        s = SecurityRedactionSettings()
        assert (
            s.redact_secrets_min_length,
            s.redact_secrets_entropy_threshold,
            s.redact_partial_min_len,
            s.redact_partial_head,
            s.redact_partial_tail,
        ) == (32, 4.2, 32, 6, 4)
        assert all(isinstance(getattr(s, name), bool) for name in _REDACTION_FIELD_NAMES if name.startswith("enable_"))

    def test_field_ownership_is_exact(self):
        """小模型恰好 17 字段；父模型持 redaction 且不再持扁平脱敏键。"""
        assert set(SecurityRedactionSettings.model_fields) == _REDACTION_FIELD_NAMES
        assert "redaction" in SecuritySettings.model_fields
        assert not (_REDACTION_FIELD_NAMES & set(SecuritySettings.model_fields))

    def test_nested_dict_and_instance_both_take_effect(self):
        """嵌套 dict 直接构造生效；嵌套实例直接构造同样生效。"""
        via_dict = SecuritySettings(redaction={"enable_redact_bare_entropy": False})
        assert via_dict.redaction.enable_redact_bare_entropy is False
        via_instance = SecuritySettings(redaction=SecurityRedactionSettings(enable_redact_cookies=False))
        assert via_instance.redaction.enable_redact_cookies is False

    def test_default_child_objects_are_isolated(self):
        """default_factory 每次产出独立子对象：改动其一不影响其二。"""
        first, second = SecuritySettings(), SecuritySettings()
        assert first.redaction is not second.redaction
        first.redaction.enable_redact_cookies = False
        assert second.redaction.enable_redact_cookies is True

    def test_legacy_flat_keys_are_ignored(self):
        """旧扁平脱敏键不再支持：不抛异常、被 extra-ignore 忽略、仍走默认 True。"""
        settings = SecuritySettings(enable_redact_secrets=False)
        assert settings.redaction.enable_redact_secrets is True

    def test_non_redaction_top_level_not_regressed(self):
        """非脱敏配置仍留顶层且可经平台顶层键覆盖。"""
        settings = SecuritySettings(enable_tool_result_limit=False)
        assert settings.enable_tool_result_limit is False
        assert settings.enable_tool_redaction is True

    @pytest.mark.parametrize("value", ["false", 0])
    def test_child_switch_coercion_is_pydantic_default(self, value):
        """不再有「归真」干预：非布尔假值走 pydantic 常规转换 ⇒ bool False。"""
        settings = SecurityRedactionSettings(enable_redact_private_keys=value)
        assert settings.enable_redact_private_keys is False

    def test_child_switch_rejects_non_boolean_input(self):
        """None 不是合法布尔，照常 ValidationError（不存在会吞掉它的校验器）。"""
        with pytest.raises(ValidationError):
            SecurityRedactionSettings(enable_redact_private_keys=None)

    def test_serialization_structure(self):
        """序列化后脱敏配置是含 17 键的 dict，顶层无扁平脱敏键。"""
        payload = SecuritySettings().model_dump()
        assert isinstance(payload["redaction"], dict)
        assert set(payload["redaction"]) == _REDACTION_FIELD_NAMES
        assert not (_REDACTION_FIELD_NAMES & set(payload))


class TestRedactionEnvAndPlatformPriority:
    """env 兜底与平台优先：布尔/字符串走工厂，缺失回落 env，显式覆盖 env。"""

    def test_bool_and_string_env_fallback(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENAVLE_REDACT_BARE_ENTROPY", "false")
        monkeypatch.setenv("BKAI_KNOWN_SENSITIVE_VALUES", "env-value")
        s = SecurityRedactionSettings()
        assert s.enable_redact_bare_entropy is False
        assert s.known_sensitive_values == "env-value"

    def test_env_fallback_through_nested_parent(self, monkeypatch):
        monkeypatch.setenv("BKAI_KNOWN_SENSITIVE_VALUES", "env-value")
        assert SecuritySettings().redaction.known_sensitive_values == "env-value"

    def test_platform_value_overrides_env(self, monkeypatch):
        monkeypatch.setenv("BKAI_ENAVLE_REDACT_BARE_ENTROPY", "true")
        settings = SecuritySettings(redaction={"enable_redact_bare_entropy": False})
        assert settings.redaction.enable_redact_bare_entropy is False

    def test_nested_redaction_flows_into_agent_config(self):
        """_StubRM 验证嵌套 redaction 实际进入 AgentConfig。"""
        cfg = _StubRM({"redaction": {"enable_redact_cookies": False}}).get_agent_config("a1")
        assert cfg.security_settings.redaction.enable_redact_cookies is False


class TestRedactionNumericFieldReadTiming:
    """5 个数值字段仍在**类定义时**读取 env：Field.default 是已求值标量。"""

    @pytest.mark.parametrize(
        "field, expected_type",
        [
            ("redact_secrets_min_length", int),
            ("redact_secrets_entropy_threshold", float),
            ("redact_partial_min_len", int),
            ("redact_partial_head", int),
            ("redact_partial_tail", int),
        ],
    )
    def test_default_is_resolved_scalar_not_factory(self, field, expected_type):
        """default 是具体 int/float（非 default_factory、非 PydanticUndefined）。"""

        info = SecurityRedactionSettings.model_fields[field]
        assert info.default is not PydanticUndefined
        assert isinstance(info.default, expected_type)
        assert info.default_factory is None


_COMMAND_FIELD_NAMES = {
    "enable_command_blocklist",
    "enable_command_blocklist_dynamic_exec",
    "enable_command_blocklist_unsupported",
    "enable_command_syntax_rules",
    "enable_command_review_auto",
    "command_review_disposition",
    "command_approval_approvers",
    "allowed_script_dirs",
    "dynamic_execution_policy",
    "max_command_length",
    "max_nodes",
    "max_depth",
    "max_reparse_depth",
    "rules",
}

# 四个预算字段的 (默认, 上限)：唯一真源，模型与测试共用同一组期望值。
_BUDGET_BOUNDS = {
    "max_command_length": (8192, 65536),
    "max_nodes": (20000, 1000000),
    "max_depth": (64, 4096),
    "max_reparse_depth": (8, 64),
}


class TestSecurityCommandSettingsStandalone:
    """命令小配置可独立构造，字段归属与默认值精确（D-01 / D-02 / D-04）。"""

    def test_core_field_defaults(self):
        """核心字段默认可读：族开关 + 审批 + 脚本目录 + 动态策略 block + 四项预算 + 规则下发。

        本用例只覆盖这些**高频消费**字段（整族开关与预算/策略），不逐一列举全部字段——
        字段集合的完整性由 :meth:`test_field_ownership_is_exact` 单独看守。
        """
        s = SecurityCommandSettings()
        assert (
            s.enable_command_blocklist,
            s.enable_command_review_auto,
            s.command_review_disposition,
            s.command_approval_approvers,
            s.allowed_script_dirs,
            s.dynamic_execution_policy,
            s.max_command_length,
            s.max_nodes,
            s.max_depth,
            s.max_reparse_depth,
            s.rules,
        ) == (
            True,
            False,
            "allow",
            "",
            ["/workspace", "/home", "/tmp", "/app"],
            "block",
            8192,
            20000,
            64,
            8,
            [],
        )

    def test_field_ownership_is_exact(self):
        """小模型字段集合与父模型扁平键互不重叠（字段名集合的完整性由本用例看守）。"""
        assert set(SecurityCommandSettings.model_fields) == _COMMAND_FIELD_NAMES
        assert "command" in SecuritySettings.model_fields
        assert not (_COMMAND_FIELD_NAMES & set(SecuritySettings.model_fields))

    def test_nested_dict_and_instance_both_take_effect(self):
        """嵌套 dict 直接构造生效；嵌套实例直接构造同样生效。"""
        via_dict = SecuritySettings(command={"enable_command_blocklist": False})
        assert via_dict.command.enable_command_blocklist is False
        via_instance = SecuritySettings(command=SecurityCommandSettings(enable_command_review_auto=True))
        assert via_instance.command.enable_command_review_auto is True

    def test_syntax_rules_platform_false_takes_effect(self, monkeypatch):
        """结构约束族开关可被平台下发 False 真关闭（环境变量为真也被平台覆盖）。"""
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_SYNTAX_RULES", "true")
        settings = SecuritySettings(command={"enable_command_syntax_rules": False})
        assert settings.command.enable_command_syntax_rules is False

    def test_default_child_objects_are_isolated(self):
        """default_factory 每次产出独立子对象：改动其一不影响其二。"""
        first, second = SecuritySettings(), SecuritySettings()
        assert first.command is not second.command
        first.command.enable_command_blocklist = False
        assert second.command.enable_command_blocklist is True

    def test_legacy_flat_keys_are_ignored(self):
        """旧扁平命令键不再支持：不抛异常、被 extra-ignore 忽略、仍走默认 False。"""
        settings = SecuritySettings(enable_command_review_auto=True)
        assert settings.command.enable_command_review_auto is False

    def test_serialization_structure(self):
        """序列化后命令配置是含全部字段键的 dict，顶层无扁平命令键。"""
        payload = SecuritySettings().model_dump()
        assert isinstance(payload["command"], dict)
        assert set(payload["command"]) == _COMMAND_FIELD_NAMES
        assert not (_COMMAND_FIELD_NAMES & set(payload))

    def test_env_fallback_and_platform_priority_via_nested_parent(self, monkeypatch):
        """env 兜底经嵌套父模型可读；平台嵌套值覆盖 env。"""
        monkeypatch.setenv("BKAI_ENABLE_COMMAND_BLOCKLIST", "false")
        assert SecuritySettings().command.enable_command_blocklist is False
        settings = SecuritySettings(command={"enable_command_blocklist": True})
        assert settings.command.enable_command_blocklist is True

    def test_nested_command_flows_into_agent_config(self):
        """_StubRM 验证嵌套 command 实际进入 AgentConfig。"""
        cfg = _StubRM({"command": {"enable_command_blocklist": False}}).get_agent_config("a1")
        assert cfg.security_settings.command.enable_command_blocklist is False


class TestCommandListFieldDoesNotReadEnv:
    """D-03b：唯一的列表字段不读任何 env —— 设置旧 env 名后默认值必须不变。

    这证明原 ``AIDEV_ALLOWED_SCRIPT_DIRS`` / ``AIDEV_ADDITIONAL_ALLOWED_COMMANDS``
    两条「绕开平台策略下发」的旁路已彻底移除（#3 的核心目标）。
    """

    @pytest.mark.parametrize(
        "env_name, env_value",
        [
            ("AIDEV_ALLOWED_SCRIPT_DIRS", "/evil"),
        ],
    )
    def test_legacy_env_vars_have_no_effect(self, monkeypatch, env_name, env_value):
        """D-03b：设置旧 env 名后，列表字段仍保持硬编码默认值（旁路已彻底移除）。"""
        monkeypatch.setenv(env_name, env_value)
        s = SecurityCommandSettings()
        assert s.allowed_script_dirs == ["/workspace", "/home", "/tmp", "/app"]


class TestCommandListFieldPlatformChannel:
    """唯一的列表字段的平台下发通道（D-02 / T-09-11）。"""

    def test_platform_list_override(self):
        """平台经嵌套 dict 以 JSON 数组下发列表字段，覆盖硬编码默认。"""
        settings = SecuritySettings(command={"allowed_script_dirs": ["/srv"]})
        assert settings.command.allowed_script_dirs == ["/srv"]

    @pytest.mark.parametrize("bad", ["/srv", 123, {"a": 1}])
    def test_platform_scalar_input_rejected(self, bad):
        """非数组输入（字符串/整数/对象）被 pydantic 拒绝（平台下发形态须为 JSON 数组）。"""
        with pytest.raises(ValidationError):
            SecuritySettings(command={"allowed_script_dirs": bad})

    def test_platform_legacy_key_is_inert(self):
        """旧键 enable 前的 command_blacklist 按 extra="ignore" 静默失效（回落默认 True）。"""
        settings = SecuritySettings(command={"command_blacklist": False})
        assert settings.command.enable_command_blocklist is True


class TestCommandReviewDisposition:
    """review 处置三档（allow / approval / block）的取值契约与 env 兜底。"""

    def test_default_is_allow(self, monkeypatch):
        """默认 allow——未命中任何规则时自动放行（尽量不影响业务）。"""
        monkeypatch.delenv("BKAI_COMMAND_REVIEW_DISPOSITION", raising=False)
        assert SecurityCommandSettings().command_review_disposition == "allow"

    @pytest.mark.parametrize("value", ["allow", "approval", "block"])
    def test_accepts_three_dispositions(self, value):
        assert SecurityCommandSettings(command_review_disposition=value).command_review_disposition == value

    def test_env_fallback(self, monkeypatch):
        monkeypatch.setenv("BKAI_COMMAND_REVIEW_DISPOSITION", "allow")
        assert SecurityCommandSettings().command_review_disposition == "allow"

    @pytest.mark.parametrize("bad", ["manual", "smart", "", "ALLOW"])
    def test_invalid_value_rejected_at_construction(self, bad):
        """非法取值由 Literal 在构造期拒绝（旧 manual/smart 不再合法）。"""
        with pytest.raises(ValidationError):
            SecurityCommandSettings(command_review_disposition=bad)


class TestCommandPolicyBudgets:
    """动态执行策略与四项预算的严格类型 / 边界契约（D-09 / D-18 / D-19）。

    直接模型构造与经父模型嵌套构造两入口覆盖同一非法矩阵。
    """

    @pytest.mark.parametrize("field, default, upper", [(f, *v) for f, v in _BUDGET_BOUNDS.items()])
    def test_defaults_and_bounds_accepted(self, field, default, upper):
        """默认值、下界 1 与上界本身均被接受（StrictInt 严格整数）。"""
        for value in (default, 1, upper):
            via_model = SecurityCommandSettings(**{field: value})
            via_mapping = SecuritySettings(command={field: value})
            assert getattr(via_model, field) == value
            assert getattr(via_mapping.command, field) == value

    @pytest.mark.parametrize("field", list(_BUDGET_BOUNDS))
    @pytest.mark.parametrize("bad", [0, -1, True, False, 1.0, 3.5, "1", "many", None, [], {}])
    def test_budget_illegal_values_rejected(self, field, bad):
        """bool / 浮点 / 字符串数字 / 容器等一律不被强制转换（两入口一致）。"""
        with pytest.raises(ValidationError):
            SecurityCommandSettings(**{field: bad})
        with pytest.raises(ValidationError):
            SecuritySettings(command={field: bad})

    @pytest.mark.parametrize("field, _, upper", [(f, *v) for f, v in _BUDGET_BOUNDS.items()])
    def test_budget_above_upper_rejected(self, field, _, upper):
        """上限 + 1 被拒（ge=1 与 le 上限共同构成闭区间）。"""
        with pytest.raises(ValidationError):
            SecuritySettings(command={field: upper + 1})

    @pytest.mark.parametrize("policy", ["block", "review"])
    def test_dynamic_policy_legal_values(self, policy):
        assert SecurityCommandSettings(dynamic_execution_policy=policy).dynamic_execution_policy == policy
        via_mapping = SecuritySettings(command={"dynamic_execution_policy": policy})
        assert via_mapping.command.dynamic_execution_policy == policy

    @pytest.mark.parametrize("bad", ["allow", "ALLOW", "permit", "", None, True])
    def test_dynamic_policy_illegal_values_rejected(self, bad):
        """无 allow 档位：Literal 只接受 block/review（两入口一致）。"""
        with pytest.raises(ValidationError):
            SecurityCommandSettings(dynamic_execution_policy=bad)
        with pytest.raises(ValidationError):
            SecuritySettings(command={"dynamic_execution_policy": bad})

    @pytest.mark.parametrize("field, expected_type", [(f, int) for f in _BUDGET_BOUNDS])
    def test_default_is_scalar_not_factory(self, field, expected_type):
        """默认是具体标量（非 default_factory、非 PydanticUndefined）。"""

        info = SecurityCommandSettings.model_fields[field]
        assert info.default is not PydanticUndefined
        assert isinstance(info.default, expected_type)
        assert info.default_factory is None

    def test_json_schema_bounds_match_contract(self):
        """JSON schema 的 minimum/maximum 与四项预算契约一致。"""
        props = SecurityCommandSettings.model_json_schema()["properties"]
        for field, (default, upper) in _BUDGET_BOUNDS.items():
            assert props[field]["minimum"] == 1
            assert props[field]["maximum"] == upper
            assert props[field]["default"] == default


class TestCommandPolicyFieldsDoNotReadEnv:
    """新五字段零 env 读取：设置 AIDEV_ / BKAI_ 两前缀后默认值必须不变（T10-C2）。"""

    _DEFAULTS = {
        "dynamic_execution_policy": "block",
        "max_command_length": 8192,
        "max_nodes": 20000,
        "max_depth": 64,
        "max_reparse_depth": 8,
    }

    @pytest.mark.parametrize("field", list(_DEFAULTS))
    @pytest.mark.parametrize("prefix", ["AIDEV_", "BKAI_"])
    def test_new_fields_ignore_legacy_env(self, monkeypatch, field, prefix):
        """两前缀 × 五字段大写后缀：设置与默认不同的 env 值后默认不变。"""
        monkeypatch.setenv(prefix + field.upper(), "1" if field != "dynamic_execution_policy" else "review")
        assert getattr(SecurityCommandSettings(), field) == self._DEFAULTS[field]
        assert getattr(SecuritySettings().command, field) == self._DEFAULTS[field]


class TestCommandPolicyPlatformChannel:
    """五字段经真实平台配置构造可达（_StubRM → get_agent_config）。"""

    def test_new_fields_flow_into_agent_config(self):
        """小正值 max_nodes=3 等五个平台值全部进入 AgentConfig.security_settings.command。"""
        platform = {
            "command": {
                "dynamic_execution_policy": "review",
                "max_command_length": 1024,
                "max_nodes": 3,
                "max_depth": 16,
                "max_reparse_depth": 2,
            }
        }
        cfg = _StubRM(platform).get_agent_config("a1")
        command = cfg.security_settings.command
        assert command.dynamic_execution_policy == "review"
        assert command.max_command_length == 1024
        assert command.max_nodes == 3
        assert command.max_depth == 16
        assert command.max_reparse_depth == 2

    def test_new_fields_default_when_platform_silent(self):
        """平台不下发新字段时回落模型标量默认（零 env，两前缀均设也不受影响，见上一个类）。"""
        cfg = _StubRM({"command": {"enable_command_blocklist": True}}).get_agent_config("a1")
        command = cfg.security_settings.command
        assert command.dynamic_execution_policy == "block"
        assert command.max_nodes == 20000


# ========== 规则可配置化：schema 与 fail-closed ==========


class TestRuleConfigSchema:
    """``rules`` 统一下发形态的形状级校验（Phase 11 D-10）。

    本类只覆盖**本层可判定**的约束。rule_id 是否已登记 / 是否可配 / 是否可字面化需查
    命令包的规则注册表，依赖方向不允许 ``pydantic_models`` 反向导入，故那部分校验由
    命令层的 ``build_rule_set`` 负责（见 test_command_rule_config.py）。
    """

    def test_defaults_are_empty(self):
        """规则下发默认为空——不配置即保持全部内置规则原样。"""
        assert SecurityCommandSettings().rules == []

    def test_accepts_valid_declaration(self):
        """合法下发声明可构造，category 有默认值。**无前缀要求**。"""

        rule = RuleSpecConfig(
            rule_id="no_nc",
            verdict="block",
            justification="nc 不允许使用",
            tokens=["nc"],
        )
        assert rule.category == "custom"
        assert rule.tokens == ["nc"]

    def test_tokens_default_to_empty(self):
        """``tokens`` 默认空——但 ``enabled=True`` 的声明**必须**给内容（命令层闸门拒空）。"""

        assert RuleSpecConfig(rule_id="rm_recursive_force", verdict="review", justification="x").tokens == []

    def test_disable_only_declaration_needs_no_verdict(self):
        """``enabled=False``（按 id 关闭）只需 ``rule_id``——不产出命中，故不要求 verdict/justification。"""

        rule = RuleSpecConfig(rule_id="mkfs_format", enabled=False)
        assert rule.verdict is None
        assert rule.justification is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"rule_id": "x", "justification": "x"},  # enabled=true 但 verdict 缺失
            {"rule_id": "x", "verdict": "permit", "justification": "x"},  # 非法判定
            {"rule_id": "x", "verdict": "block", "justification": ""},  # 空文案
            {"verdict": "block", "justification": "x"},  # rule_id 缺失
            {"rule_id": "", "verdict": "block", "justification": "x"},  # 空 id
            {"rule_id": "x", "verdict": "block"},  # enabled=true 但 justification 缺失
        ],
        ids=[
            "missing_verdict",
            "bad_verdict",
            "empty_justification",
            "missing_rule_id",
            "empty_rule_id",
            "missing_justification",
        ],
    )
    def test_invalid_declaration_rejected(self, payload):
        """下发声明的字段级约束逐个 fail-closed。

        尤其 ``enabled=True`` 时 ``verdict`` **必填**——这是对 Codex（默认 allow）的有意偏离：
        缺省 allow 会让未知命令从 review 翻成 allow，等于静默取消人工审批。
        """

        with pytest.raises(ValidationError):
            RuleSpecConfig(**payload)

    def test_extra_key_in_nested_model_is_rejected(self):
        """子模型 extra=forbid：拼错字段名（如 descision）必须报错而非静默忽略。"""

        with pytest.raises(ValidationError):
            RuleSpecConfig(rule_id="x", descision="block", justification="x")

    def test_duplicate_rule_ids_rejected(self):
        """``rules`` 内部 rule_id 重复 → 构造期报错（否则哪条规则生效未定义）。"""

        payload = {
            "rules": [
                {"rule_id": "dup", "verdict": "block", "justification": "a", "tokens": ["nc"]},
                {"rule_id": "dup", "verdict": "review", "justification": "b", "tokens": ["socat"]},
            ]
        }
        with pytest.raises(ValidationError, match="重复"):
            SecurityCommandSettings(**payload)

    def test_rule_config_flows_from_platform_nested_dict(self):
        """规则下发经平台嵌套 dict 直接构造生效。"""
        platform = {
            "command": {
                "rules": [
                    {
                        "rule_id": "rm_recursive_force",
                        "verdict": "review",
                        "justification": "降级为审批",
                        "tokens": ["rm"],
                    },
                    {"rule_id": "no_nc", "verdict": "block", "justification": "nc 禁用", "tokens": ["nc"]},
                ]
            }
        }
        cfg = _StubRM(platform).get_agent_config("a1")
        command = cfg.security_settings.command
        assert [r.rule_id for r in command.rules] == ["rm_recursive_force", "no_nc"]

    def test_legacy_two_fields_are_silently_ignored(self):
        """旧双字段 key 经 extra=ignore 静默失效——有意的契约变更（外部须同步迁移）。

        这是**行为契约变更**：旧键不报错、也不生效。断言它"不生效"是为了钉住这个事实——
        若哪天旧键意外复活，本用例会红。
        """
        platform = {
            "command": {
                "rule_overrides": {"rm_recursive_force": {"verdict": "allow"}},
                "custom_rules": [{"rule_id": "custom:no_nc", "verdict": "block", "reason": "x"}],
            }
        }
        cfg = _StubRM(platform).get_agent_config("a1")
        assert cfg.security_settings.command.rules == []

    def test_rule_config_does_not_read_env(self, monkeypatch):
        """规则下发零 env：两个前缀都设也不受影响（与其余平台专属字段同型）。"""
        for prefix in ("AIDEV_", "BKAI_"):
            for suffix in ("RULES", "RULE_OVERRIDES", "CUSTOM_RULES"):
                monkeypatch.setenv(f"{prefix}{suffix}", '[{"rule_id": "custom:x", "verdict": "block"}]')
        assert SecurityCommandSettings().rules == []


# ========== 规则声明的修饰符字段（12-03：Pattern 全六维的下发通道）==========


#: `package_install` 的平台等价形态；同时是平台嵌套 dict 端到端形状测试的输入。
_SKIP_FLAGS_CASE = {
    "rule_id": "custom:apt_install",
    "verdict": "block",
    "justification": "docker 镜像内不得自行安装软件包",
    "tokens": ["apt"],
    "positional_index": 0,
    "positional_equals": ["install"],
    "skip_flags": ["-y", "--yes"],
}


class TestRuleConfigModifiers:
    """``RuleSpecConfig`` 的五个修饰符字段（12-03：补齐 :class:`Pattern` 全六维）。

    本类只覆盖**本层可判定**的约束：类型与字段名。修饰符的**组合语义**
    （如 ``positional_index`` 缺省却给出 ``positional_equals``）刻意**不在**本层校验——
    那会让 pydantic 成为第二套形状判据（C-02 的同型错误）；唯一 fail-loud 点是
    :meth:`Pattern.__post_init__`，准入侧由 ``build_rule_set`` 归一为
    ``RuleConfigError``。

    ⚠ **一条计划中的拒收用例被实测推翻**：计划里的 ``{"positional_index": "0"}``
    （字符串数字）**不会**抛 ``ValidationError``——pydantic 默认（非 strict）模式下
    ``"0"`` 被强制转成 ``0``，构造成功。故它**不在**下方拒收表里，
    其实际行为由 ``test_positional_index_accepts_coercible_string`` 显式钉住
    （而不是留一条会假绿/假红的断言）。
    """

    def test_modifier_defaults(self):
        """五个修饰符的默认值：不启用任何修饰（``None`` / ``[]`` / ``[]`` / ``False`` / ``False``）。"""

        rule = RuleSpecConfig(rule_id="custom:x", verdict="block", justification="x", tokens=["x"])
        assert rule.positional_index is None
        assert rule.positional_equals == []
        assert rule.skip_flags == []
        assert rule.strip_colon is False
        assert rule.requires_any_flag is False

    def test_chmod_777_shape(self):
        """能表达 ``chmod_777``：命令名 + 第 0 个位置 token 精确等于 777。"""

        rule = RuleSpecConfig(
            rule_id="custom:no_777",
            verdict="block",
            justification="x",
            tokens=["chmod"],
            positional_index=0,
            positional_equals=["777"],
        )
        assert rule.positional_index == 0
        assert rule.positional_equals == ["777"]

    def test_package_install_shape_skip_flags_is_list_not_bool(self):
        """能表达 ``package_install``；``skip_flags`` **必须是 list**——C-01 的类型防线。

        改造前 ``_spec_from_declaration`` 把 ``skip_flags=True`` 传进 ``frozenset[str]``
        字段（只因该路径从不设 ``positional_index`` 才没炸）。此用例钉住声明层的类型。
        """

        rule = RuleSpecConfig(**_SKIP_FLAGS_CASE)
        assert rule.skip_flags == ["-y", "--yes"]
        assert isinstance(rule.skip_flags, list)
        assert rule.skip_flags != [True]

    def test_firewall_change_shape(self):
        """能表达 ``firewall_change``：名字 + 「存在任一 - 开头参数」（不指定具体 flag）。"""

        rule = RuleSpecConfig(
            rule_id="custom:firewall",
            verdict="block",
            justification="x",
            tokens=["iptables"],
            requires_any_flag=True,
        )
        assert rule.requires_any_flag is True
        assert rule.positional_index is None

    def test_chown_root_shape(self):
        """能表达 ``chown_root``：位置 token 比较前剥掉 ``:group``。"""

        rule = RuleSpecConfig(
            rule_id="custom:chown_root",
            verdict="block",
            justification="x",
            tokens=["chown"],
            positional_index=0,
            positional_equals=["root"],
            strip_colon=True,
        )
        assert rule.strip_colon is True

    def test_platform_json_reaches_modifiers(self):
        """平台嵌套 dict 形态可达全部修饰符——平台实际走这条路径。"""
        settings = SecuritySettings(command={"rules": [_SKIP_FLAGS_CASE]})
        rule = settings.command.rules[0]
        assert rule.positional_index == 0
        assert rule.positional_equals == ["install"]
        assert rule.skip_flags == ["-y", "--yes"]

    def test_positional_index_accepts_coercible_string(self):
        """实测记录：``"0"`` 被 pydantic 强制转为 ``0``（非 strict 模式），**不**报错。

        计划原把这条列为拒收用例，实测推翻（见类 docstring）。
        本用例把实测行为显式钉住，避免它悄悄变成另一副样子。
        """

        rule = RuleSpecConfig(
            rule_id="custom:x",
            verdict="block",
            justification="x",
            tokens=["x"],
            positional_index="0",
        )
        assert rule.positional_index == 0

    @pytest.mark.parametrize(
        "payload",
        [
            {"positional_index": -1},  # ge=0
            {"positional_index": 65},  # le=64
            {"skip_flags": True},  # C-01 类型防线：bool 不是 list
            {"positional_equals": "777"},  # 标量而非数组
            {"require_any_flag": True},  # 拼错字段名（正确是 requires_any_flag）
            {"positional_equals": [1, 2]},  # 非字符串元素
        ],
        ids=[
            "positional_index_below_ge",
            "positional_index_above_le",
            "skip_flags_bool_not_list",
            "positional_equals_scalar",
            "misspelled_require_any_flag",
            "positional_equals_non_string_items",
        ],
    )
    def test_modifier_shape_rejected(self, payload):
        """修饰符字段的类型 / 取值级约束逐个 fail-closed（**逐条实测确认会抛**）。

        最后两条尤其重要：

        - ``require_any_flag`` 是**拼错的字段名**（正确为 ``requires_any_flag``）——
          靠 ``extra="forbid"`` 拦下。静默忽略会让运营者以为规则已生效（T-12-10）。
        - ``skip_flags=True`` 是 C-01 的类型防线：声明层就不接受 bool。
        """

        with pytest.raises(ValidationError):
            RuleSpecConfig(rule_id="custom:x", verdict="block", justification="x", tokens=["x"], **payload)
