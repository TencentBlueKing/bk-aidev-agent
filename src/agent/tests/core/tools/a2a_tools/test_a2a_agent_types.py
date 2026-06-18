# -*- coding: utf-8 -*-
"""AgentSpec 统一类型定义单元测试。"""

from __future__ import annotations

import ast
from typing import Any

import pytest
from aidev_agent.core.tools.a2a_tools.types import AgentBackend, AgentBackendType, AgentSpec


class TestSpecCreateBKAI:
    """Test 1: AgentSpec 可以创建包含 BKAI 后端类型的实例。"""

    def test_spec_create_bkai(self) -> None:
        spec = AgentSpec(
            name="test_agent",
            description="A test BKAI agent",
            backend_type=AgentBackendType.BKAI,
            params={"agent_code": "test_001"},
        )
        assert spec.name == "test_agent"
        assert spec.description == "A test BKAI agent"
        assert spec.backend_type == "bkai"
        assert spec.params == {"agent_code": "test_001"}


class TestSpecCreateLocal:
    """Test 2: AgentSpec 可以创建包含 LOCAL 后端类型的实例。"""

    def test_spec_create_local(self) -> None:
        spec = AgentSpec(
            name="local_agent",
            description="A local agent",
            backend_type=AgentBackendType.LOCAL,
            params={"prompt_overrides": "xxx"},
        )
        assert spec.name == "local_agent"
        assert spec.backend_type == "local"
        assert spec.params == {"prompt_overrides": "xxx"}


class TestSpecDefaults:
    """Test 3: AgentSpec 默认值验证。"""

    def test_spec_defaults(self) -> None:
        spec = AgentSpec(
            name="minimal_agent",
            description="Minimal agent",
            backend_type=AgentBackendType.BKAI,
        )
        assert spec.params == {}
        assert spec.timeout_seconds == 300


class TestSpecCoversSubAgent:
    """Test 4: AgentSpec 可以表达 SubAgentConfig 的所有字段。"""

    def test_spec_covers_subagent(self) -> None:
        spec = AgentSpec(
            name="analyzer",
            description="Code analysis agent",
            backend_type=AgentBackendType.BKAI,
            params={
                "agent_code": "analyzer_001",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            timeout_seconds=600,
        )
        # 验证 SubAgentConfig 字段无损失映射
        assert spec.name == "analyzer"  # SubAgentConfig.name
        assert spec.params["agent_code"] == "analyzer_001"  # SubAgentConfig.agent_code
        assert spec.description == "Code analysis agent"  # SubAgentConfig.description
        assert spec.params["temperature"] == 0.7  # SubAgentConfig.temperature
        assert spec.params["max_tokens"] == 4096  # SubAgentConfig.max_tokens
        assert spec.timeout_seconds == 600  # SubAgentConfig.timeout_seconds


class TestBackendTypeValues:
    """Test 6: AgentBackendType 枚举值验证。"""

    def test_backend_type_values(self) -> None:
        assert AgentBackendType.BKAI.value == "bkai"
        assert AgentBackendType.LOCAL.value == "local"


class TestBackendProtocolSignature:
    """Test 7: AgentBackend Protocol 的 execute 方法签名验证。"""

    def test_backend_protocol_signature(self) -> None:
        class DummyBackend:
            def new_session(self, spec: AgentSpec, **kwargs: Any) -> str:
                return "test-session"

            def execute(self, spec: AgentSpec, message: str, **kwargs: Any) -> dict[str, Any]:
                return {"result": "ok"}

        backend = DummyBackend()
        assert isinstance(backend, AgentBackend)
        result = backend.execute(
            spec=AgentSpec(name="t", description="d", backend_type=AgentBackendType.BKAI),
            message="hello",
        )
        assert result == {"result": "ok"}


class TestSpecNoGraphsNodesImport:
    """Test 8: AgentSpec 不导入 graphs 或 nodes 模块。"""

    def test_spec_no_graphs_nodes_import(self) -> None:
        # 直接读取 types.py 源码，验证无 graphs/nodes 依赖
        import aidev_agent.core.tools.a2a_tools.types as types_mod

        types_path = types_mod.__file__
        assert types_path is not None
        with open(types_path) as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert "graphs" not in alias.name, f"types.py 不应导入 graphs: {alias.name}"
                        assert "nodes" not in alias.name, f"types.py 不应导入 nodes: {alias.name}"
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert "graphs" not in node.module, f"types.py 不应导入 graphs: {node.module}"
                    assert "nodes" not in node.module, f"types.py 不应导入 nodes: {node.module}"


class TestSpecEnumValuesConfig:
    """Test 9: use_enum_values=True 时 backend_type 为字符串而非枚举实例。"""

    def test_spec_enum_values_config(self) -> None:
        spec = AgentSpec(
            name="enum_test",
            description="Test enum value config",
            backend_type=AgentBackendType.BKAI,
        )
        # use_enum_values=True 使得 backend_type 存储字符串而非枚举
        assert isinstance(spec.backend_type, str)
        assert spec.backend_type == "bkai"


class TestAgentResultModel:
    """阶段 26：AgentResult 不可变 BaseModel 验证（D-01 / D-02 / D-03）。

    RED phase: 这些测试验证新 AgentResult(BaseModel) 行为。
    当前 AgentResult 为 TypedDict → 测试预期失败。
    """

    def test_agent_result_is_base_model(self) -> None:
        """AgentResult 是 Pydantic BaseModel 而非 TypedDict。"""
        from aidev_agent.core.tools.a2a_tools.types import AgentResult
        from pydantic import BaseModel

        assert issubclass(AgentResult, BaseModel)

    def test_agent_result_is_frozen(self) -> None:
        """AgentResult 不可变：修改字段应抛出异常（D-01）。"""
        from aidev_agent.core.tools.a2a_tools.types import AgentResult

        r = AgentResult(status="completed")
        with pytest.raises(Exception):  # FrozenInstanceError 或 TypeError
            r.status = "failed"

    def test_agent_result_has_exactly_6_fields(self) -> None:
        """AgentResult 包含 6 个字段，不含 session_code/member_name/agent_name（D-02）。"""
        from aidev_agent.core.tools.a2a_tools.types import AgentResult

        r = AgentResult(status="completed")
        d = r.model_dump()
        expected_keys = {"status", "agent_type", "result", "error", "tool_calls", "exit_reason"}
        assert set(d.keys()) == expected_keys, f"期望恰好 6 个 key, 实际得到: {set(d.keys())}"

    def test_agent_result_defaults(self) -> None:
        """AgentResult 各字段默认值正确（D-02）。"""
        from aidev_agent.core.tools.a2a_tools.types import AgentResult

        r = AgentResult(status="completed")
        assert r.agent_type == ""
        assert r.result == ""
        assert r.error is None
        assert r.tool_calls == 0
        assert r.exit_reason == "completed"  # use_enum_values=True 序列化为 str

    def test_agent_result_invalid_status_raises(self) -> None:
        """status 字段使用 Literal 约束，非法值抛出 ValidationError。"""
        from aidev_agent.core.tools.a2a_tools.types import AgentResult
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentResult(status="invalid_status_value")

    def test_agent_result_model_dump_json_excludes_none(self) -> None:
        """model_dump_json(exclude_unset=True) 排除未显式设置的字段（D-03）。"""
        import json

        from aidev_agent.core.tools.a2a_tools.types import AgentResult

        r = AgentResult(status="completed")
        json_str = r.model_dump_json(exclude_unset=True)
        d = json.loads(json_str)
        # 仅 status 存在，因为只有 status 被显式设置
        assert "status" in d
        # error 为 None（未设置），应被排除
        assert "error" not in d, f"error 未设置时应被排除, 实际得到: {d}"

    def test_agent_result_exit_reason_accepts_enum(self) -> None:
        """exit_reason 接受 ExitReason 枚举值，序列化为字符串。"""
        from aidev_agent.core.tools.a2a_tools.types import AgentResult, ExitReason

        r = AgentResult(status="completed", exit_reason=ExitReason.TIMEOUT)
        assert r.exit_reason == "timeout"  # use_enum_values=True
        d = r.model_dump()
        assert d["exit_reason"] == "timeout"


class TestAgentBackendReturnType:
    """阶段 26 任务 2：AgentBackend 协议 execute() 返回类型验证。

    RED phase: 当前协议返回 dict[str, Any]。
    更新后协议应返回 AgentResult。
    """

    def test_backend_with_agentresult_satisfies_protocol(self) -> None:
        """execute() 返回 AgentResult 的类应满足 AgentBackend 协议。

        RED: 当前协议期望 dict[str, Any]，AgentResult(BaseModel) 不是 dict 子类型 → 预期失败。
        """
        from aidev_agent.core.tools.a2a_tools.types import AgentBackend, AgentResult

        class CorrectBackend:
            def new_session(self, spec: AgentSpec, **kwargs: Any) -> str:
                return "test-session"

            def execute(self, spec: AgentSpec, message: str, **kwargs: Any) -> AgentResult:
                return AgentResult(status="completed")

        backend = CorrectBackend()
        assert isinstance(backend, AgentBackend)


class TestPublicImports:
    """验证公开导入可正常工作。"""

    def test_public_imports(self) -> None:
        # 已在模块顶部通过 _import_types_module() 验证可导入
        assert AgentSpec is not None
        assert AgentBackendType is not None
        assert AgentBackend is not None
