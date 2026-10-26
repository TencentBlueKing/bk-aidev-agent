# -*- coding: utf-8 -*-
"""A2A utils 工具函数单元测试。阶段 26 新增，原 test_progress.py 合并而来。

覆盖：
- build_enriched_result() 返回 AgentResult（D-02）
- sanitize_error_message() 脱敏
- detect_intermediate_step() 步骤描述

注：count_tool_calls 已合并到 consume_sse_stream 内部递增计数器，
原统计逻辑由 consume_sse_stream 返回的 tool_count 直接提供，不再独立测试。
"""

from __future__ import annotations

import json

import pytest
from aidev_agent.core.tools.a2a_tools.types import AgentResult, ExitReason
from aidev_agent.core.tools.a2a_tools.utils import (
    build_enriched_result,
    extract_child_execute_kwargs,
    sanitize_error_message,
)
from aidev_agent.pydantic_models import ExecuteKwargs


class TestBuildEnrichedResult:
    """build_enriched_result() 返回 AgentResult 验证（D-02 / D-07）。"""

    def test_returns_agent_result(self) -> None:
        """build_enriched_result 返回 AgentResult 实例而非 dict。"""
        r = build_enriched_result(status="completed", agent_name="test_agent")
        assert isinstance(r, AgentResult)

    def test_completed_status_fields(self) -> None:
        """completed 状态的 AgentResult 字段值正确。"""
        r = build_enriched_result(
            status="completed",
            agent_name="test_agent",
            summary="Done!",
            tool_calls=3,
            exit_reason=ExitReason.COMPLETED.value,
        )
        assert r.status == "completed"
        assert r.result == "Done!"
        assert r.error is None
        assert r.tool_calls == 3
        assert r.exit_reason == "completed"

    def test_failed_status_with_error_sanitization(self) -> None:
        """failed 状态时 error 字段被脱敏处理。"""
        r = build_enriched_result(
            status="failed",
            agent_name="test_agent",
            error="API error with sk-abc123def456ghi789jkl012mno345pqr678stu",
            exit_reason=ExitReason.BACKEND_ERROR.value,
        )
        assert r.status == "failed"
        assert "sk-" not in r.error
        assert "REDACTED" in r.error

    def test_default_field_values(self) -> None:
        """默认字段值：result="" / error=None / tool_calls=0 / agent_type=""。"""
        r = build_enriched_result(
            status="completed",
            agent_name="test_agent",
        )
        assert r.result == ""
        assert r.error is None
        assert r.tool_calls == 0
        assert r.exit_reason == "completed"
        assert r.agent_type == ""

    def test_agent_type_propagated(self) -> None:
        """agent_type 参数传递到 AgentResult 中。"""
        r = build_enriched_result(
            status="completed",
            agent_name="test_agent",
            agent_type="bkai",
        )
        assert r.agent_type == "bkai"
        d = r.model_dump()
        assert d["agent_type"] == "bkai"

    def test_agent_name_not_in_model(self) -> None:
        """agent_name 参数不包含在返回的 AgentResult 中（D-02）。"""
        r = build_enriched_result(
            status="completed",
            agent_name="my_agent",
        )
        d = r.model_dump()
        assert "agent_name" not in d

    def test_model_dump_json_excludes_none(self) -> None:
        """model_dump_json(exclude_unset=True) 排除 None 字段（D-03）。"""
        r = build_enriched_result(
            status="completed",
            agent_name="test_agent",
        )
        json_str = r.model_dump_json(exclude_unset=True)
        d = json.loads(json_str)
        # error 为 None（默认值，未设置）→ 被排除
        assert "error" not in d


class TestSanitizeErrorMessage:
    """sanitize_error_message() 脱敏验证。"""

    def test_redacts_api_key(self) -> None:
        """脱敏 sk- 前缀的 API key。"""
        msg = "Error: sk-abc123def456ghi789jkl012mno345"
        result = sanitize_error_message(msg)
        assert "sk-" not in result
        assert "REDACTED_API_KEY" in result

    def test_redacts_access_token(self) -> None:
        """脱敏 access_token 参数值。"""
        msg = "Error with access_token=my_secret_token_12345"
        result = sanitize_error_message(msg)
        assert "my_secret_token" not in result
        assert "REDACTED" in result

    def test_redacts_bearer_token(self) -> None:
        """脱敏 Bearer token。"""
        msg = "Auth failed: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        result = sanitize_error_message(msg)
        assert "eyJhbGci" not in result
        assert "REDACTED" in result

    def test_preserves_clean_message(self) -> None:
        """干净消息保持不变。"""
        msg = "Something went wrong"
        assert sanitize_error_message(msg) == msg

    def test_redacts_project_api_key(self) -> None:
        """D-10：sk-proj- 前缀的项目级 OpenAI key 被脱敏。"""
        msg = "Error: sk-proj-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOP123456"
        result = sanitize_error_message(msg)
        assert "sk-proj-" not in result
        assert "REDACTED_API_KEY" in result

    def test_redacts_url_encoded_access_token(self) -> None:
        """D-10：URL 编码的 access_token（%3D）被脱敏。"""
        msg = "token=access_token%3Dsecrettoken1234567890xyz"
        result = sanitize_error_message(msg)
        assert "secrettoken1234567890" not in result
        assert "REDACTED" in result

    def test_redacts_bk_token(self) -> None:
        """D-10：蓝鲸 bk_token 被脱敏。"""
        msg = "auth bk_token=mybksecret1234567890abc"
        result = sanitize_error_message(msg)
        assert "mybksecret1234567890" not in result
        assert "REDACTED" in result

    def test_redacts_app_secret(self) -> None:
        """D-10：蓝鲸 app_secret 被脱敏。"""
        msg = "config app_secret=myappsecret1234567890def"
        result = sanitize_error_message(msg)
        assert "myappsecret1234567890" not in result
        assert "REDACTED" in result

    def test_redacts_app_code(self) -> None:
        """D-10：蓝鲸 app_code 被脱敏。"""
        msg = "app_code=bk-app-code-12345"
        result = sanitize_error_message(msg)
        assert "bk-app-code-12345" not in result
        assert "REDACTED" in result

    def test_redacts_url_encoded_bearer(self) -> None:
        """D-10：URL 编码的 Bearer token（%20）被脱敏。"""
        msg = "Bearer%20eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        result = sanitize_error_message(msg)
        assert "eyJhbGci" not in result
        assert "REDACTED" in result


# ============== 工具加载模式（mode）继承 ==============


class TestChildExecuteKwargsModeInheritance:
    """REQ-6 / AC-11：A2A 子 Agent 的 ``mode`` 与父一致，不回落也不升级。

    子对象由 ``ek.model_copy()`` 全量继承；BKAI 远端以 ``execute_kwargs.model_dump()``
    构造 HTTP payload（``bkai_backend.py``），故此处直接断言复制与序列化两条路径。
    """

    @pytest.mark.parametrize("mode", ["dontInterrupt", "dontAsk"])
    def test_child_inherits_non_default_mode(self, mode: str) -> None:
        parent = ExecuteKwargs(mode=mode)
        child = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": parent}}, state=None, session_code="child", caller_bk_app_code=""
        )
        assert child.mode == mode

    def test_child_inherits_default_mode(self) -> None:
        child = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": ExecuteKwargs()}},
            state=None,
            session_code="child",
            caller_bk_app_code="",
        )
        assert child.mode == "default"

    def test_child_without_parent_execute_kwargs_falls_back_to_default(self) -> None:
        child = extract_child_execute_kwargs({}, state=None, session_code="child", caller_bk_app_code="")
        assert child.mode == "default"

    @pytest.mark.parametrize("mode", ["default", "dontInterrupt", "dontAsk"])
    def test_serialized_payload_contains_mode(self, mode: str) -> None:
        """BKAI 远端 payload（``execute_kwargs.model_dump()``）带出父 mode。"""
        parent = ExecuteKwargs(mode=mode)
        child = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": parent}}, state=None, session_code="child", caller_bk_app_code=""
        )
        payload = {"execute_kwargs": child.model_dump()}
        assert payload["execute_kwargs"]["mode"] == mode
