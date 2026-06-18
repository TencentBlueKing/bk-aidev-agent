# -*- coding: utf-8 -*-
"""E2E integration tests for add_subagent_specs() → build() → invoke() flow and backend call paths.

Test classes:
- TestAddSubagentSpecsE2E: E2E tests for add_subagent_specs → build → invoke (D-04)
- TestBackendCallPath: Backend call path integration tests (D-05)
- TestAgentSpecBoundary: AgentSpec boundary condition tests (TEST-01, TEST-02)

注意：A2A Server 端到端测试已迁移至 test_a2a_backend_e2e.py 中的
TestA2AProtocolE2E / TestA2AServerManualE2E / TestA2ABackendE2E。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.config import settings
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.tools.a2a_tools.bkai_backend import BkAiBackend
from aidev_agent.core.tools.a2a_tools.local_backend import LocalBackend
from aidev_agent.core.tools.a2a_tools.provider import AgentBackendResolver, get_agent_tools
from aidev_agent.core.tools.a2a_tools.types import AgentBackendType, AgentResult, AgentSpec
from aidev_agent.packages.langchain_core.models.mock import MockChatModel, MockResponse
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

# =============================================================================
# TestAddSubagentSpecsE2E — E2E tests for add_subagent_specs() → build() → invoke() flow
# =============================================================================


class TestAddSubagentSpecsE2E:
    """E2E test for add_subagent_specs() → build() → invoke() flow (D-04)."""

    def test_build_and_invoke_with_subagents(self):
        """add_subagent_specs → build → invoke produces state with task_list and bk_agent_team keys."""
        specs = [
            AgentSpec(
                name="helper",
                description="A helper agent",
                backend_type=AgentBackendType.BKAI,
                params={"agent_code": "test_001"},
            ),
        ]
        mock_llm = MockChatModel(
            mock_responses=[
                MockResponse(content="I'll call the helper agent."),
            ],
        )
        builder = ReActAgentBuilder()
        builder.set_llm(mock_llm)
        builder.add_subagent_specs(specs)
        graph, config = builder.build()
        config["configurable"]["thread_id"] = "test-e2e-001"
        # Initialize state with all required TypedDict fields from the merged schema
        result = graph.invoke(
            {
                "messages": [HumanMessage(content="Use the helper agent")],
                "task_list": None,
                "bk_agent_team": {},
                "active_member": None,
            },
            config,
        )
        # Verify state contains expected keys from add_subagent_specs flow
        assert "messages" in result
        assert "task_list" in result  # task management enabled by add_subagent_specs
        assert "bk_agent_team" in result  # TeamInfo state

    @pytest.mark.skip(reason="API changed — _a2a_resolver is None, no register method")
    def test_invoke_with_tool_call_in_state(self):
        """add_subagent_specs → build → invoke with MockChatModel making tool call returns Agent tool in state."""
        specs = [
            AgentSpec(
                name="helper",
                description="A helper agent",
                backend_type=AgentBackendType.BKAI,
                params={"agent_code": "test_001"},
            ),
        ]

        # Mock the backend so Agent tool call doesn't hit real HTTP
        mock_backend = MagicMock()
        mock_backend.execute.return_value = AgentResult(status="completed", result="done")

        mock_llm = MockChatModel(
            mock_responses=[
                # Call 1: LLM calls the Agent tool
                MockResponse(
                    content="",
                    tool_calls=[
                        {"name": "Agent", "args": {"agent_name": "helper", "message": "do task"}, "id": "call_1"}
                    ],
                ),
                # Call 2: LLM returns final text
                MockResponse(content="Task completed"),
            ],
            loop=False,
        )

        builder = ReActAgentBuilder()
        builder.set_llm(mock_llm)
        builder.add_subagent_specs(specs)
        # Override resolver's backend with mock for this test
        # The resolver stores backend classes; we register a mock class that returns our mock instance
        mock_backend_cls = MagicMock(return_value=mock_backend)
        builder._a2a_resolver.register("bkai", mock_backend_cls)

        graph, config = builder.build()
        config["configurable"]["thread_id"] = "test-e2e-002"

        result = graph.invoke(
            {
                "messages": [HumanMessage(content="Call the helper")],
                "task_list": None,
                "bk_agent_team": {},
                "active_member": None,
            },
            config,
        )

        # Verify messages contain AIMessage with tool_calls
        messages = result.get("messages", [])
        ai_messages = [m for m in messages if hasattr(m, "tool_calls") and m.tool_calls]
        assert len(ai_messages) >= 1, "Expected at least one AIMessage with tool_calls"
        agent_tool_calls = [tc for m in ai_messages for tc in m.tool_calls if tc["name"] == "Agent"]
        assert len(agent_tool_calls) >= 1, "Expected at least one 'Agent' tool call"


# =============================================================================
# TestBackendCallPath — Backend call path integration tests (D-05)
# =============================================================================


class TestBackendCallPath:
    """Test that StructuredTool delegates to backend.execute() (D-05)."""

    @pytest.mark.skip(reason="get_agent_tools() no longer accepts resource_manager parameter")
    def test_bkai_backend_call_path(self):
        """BkAiBackend: get_agent_tools → tool.func() → backend.execute() call path."""
        resource_manager = MagicMock()
        resource_manager.api.create_chat_session_content.return_value = {
            "data": {"content": "Sub-agent response"},
        }

        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend)

        specs = [
            AgentSpec(
                name="bkai_helper",
                description="A BKAI agent",
                backend_type=AgentBackendType.BKAI,
                params={"agent_code": "agent_001"},
            ),
        ]
        tools = get_agent_tools(specs, resolver, resource_manager=resource_manager)

        # Invoke the Agent tool's underlying function directly
        # The StructuredTool wraps agent_call which has state: InjectedState
        tools[0].func(
            agent_name="bkai_helper",
            message="analyze this",
            state={},
        )

        # Verify resource_manager was called (BkAiBackend uses it for HTTP)
        resource_manager.api.create_chat_session_content.assert_called_once()

    def test_local_backend_call_path(self):
        """LocalBackend: get_agent_tools → tool.func() → backend.execute() call path."""
        resolver = AgentBackendResolver()
        resolver.register("local", LocalBackend)

        specs = [
            AgentSpec(
                name="local_worker",
                description="A local worker",
                backend_type=AgentBackendType.LOCAL,
                params={},
            ),
        ]
        tools = get_agent_tools(specs, resolver)

        # Mock the LocalBackend's execute to avoid real graph construction
        with patch.object(
            LocalBackend,
            "execute",
            return_value=AgentResult(status="completed", result="local result"),
        ) as mock_execute:
            tools[0].func(
                agent_name="local_worker",
                message="run subtask",
                config={"configurable": {}},
                state={},
            )
            mock_execute.assert_called_once()

    def test_unregistered_backend_returns_failed(self):
        """Agent tool with unregistered backend_type raises ValueError."""
        resolver = AgentBackendResolver()  # Empty resolver — no backends registered

        specs = [
            AgentSpec(name="orphan", description="No backend", backend_type=AgentBackendType.BKAI, params={}),
        ]
        tools = get_agent_tools(specs, resolver)

        # Invoking the tool should raise ValueError because "bkai" is not registered.
        # The resolver.resolve() raises ValueError, which propagates through agent_call
        # up to LangChain's BaseTool._run(), which wraps it as a ToolMessage(status="error").
        with pytest.raises(ValueError, match="bkai"):
            tools[0].func(
                agent_name="orphan",
                message="hello",
                config={"configurable": {}},
                state={},
            )


# =============================================================================
# TestAgentSpecBoundary — AgentSpec boundary condition tests (TEST-01, TEST-02)
# =============================================================================


class TestAgentSpecBoundary:
    """Boundary condition tests for AgentSpec (TEST-01) and AgentBackendResolver (TEST-02)."""

    def test_empty_name_is_accepted(self):
        """AgentSpec with empty name is accepted by Pydantic (no min_length constraint on name)."""
        # Pydantic BaseModel does not enforce min_length on str fields by default
        spec = AgentSpec(name="", description="test", backend_type=AgentBackendType.BKAI, params={})
        assert spec.name == ""

    def test_missing_required_fields_raises_validation_error(self):
        """AgentSpec without required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            AgentSpec()  # Missing all required fields

    def test_invalid_backend_type_raises_validation_error(self):
        """AgentSpec with invalid backend_type raises ValidationError."""
        with pytest.raises(ValidationError):
            AgentSpec(name="test", description="test", backend_type="invalid_type", params={})

    def test_default_values(self):
        """AgentSpec default values are correct."""
        spec = AgentSpec(name="test", description="test desc", backend_type=AgentBackendType.BKAI, params={})
        assert spec.params == {}
        assert spec.timeout_seconds == 300

    def test_resolver_empty_backend_type_raises_valueerror(self):
        """AgentBackendResolver.register with empty string raises ValueError."""
        resolver = AgentBackendResolver()
        with pytest.raises(ValueError, match="backend_type must be non-empty"):
            resolver.register("", object)

    def test_resolver_unregistered_type_error_message(self):
        """AgentBackendResolver.resolve with unregistered type includes available types in error."""
        resolver = AgentBackendResolver()
        spec = AgentSpec(name="test", description="test", backend_type=AgentBackendType.BKAI, params={})
        with pytest.raises(ValueError, match="Available: \\(none\\)"):
            resolver.resolve(spec)


# =============================================================================
# TestBkAiBackendE2E — E2E 真实 API 网关调用测试
# =============================================================================


requires_api_credentials = pytest.mark.skipif(
    not all([settings.APP_CODE, settings.SECRET_KEY]),
    reason="需要 BKAI_E2E_ENABLED=1 及 APP_CODE 和 SECRET_KEY 环境变量",
)


@pytest.mark.e2e
@requires_api_credentials
class TestBkAiBackendE2E:
    """E2E 真实 API 网关调用测试。"""

    @pytest.mark.skip(reason="E2E test requires valid BKAI API gateway connectivity")
    def test_invoke_ai_judge(self):
        """调用 ai-judge-0319 子智能体，验证返回结构。

        宽松断言策略：验证 status=completed 且 result 非空。
        """
        from aidev_agent.api.bk_agent import BkAgentApi

        backend = BkAiBackend()
        client = BkAgentApi.get_client(agent_code="ai-judge-0319")
        spec = AgentSpec(
            name="ai-judge-0319",
            description="Judge agent",
            backend_type=AgentBackendType.BKAI,
            params={"agent_code": "ai-judge-0319", "client": client},
        )
        result = backend.execute(spec, "hello", session_code="e2e_test_session")

        print(result)
        assert result.status == "completed", f"Expected completed, got: {result}"
        assert result.result, f"Expected non-empty result, got: {result}"

    @pytest.mark.skip(reason="E2E test requires valid BKAI API gateway connectivity")
    def test_invoke_ai_judge_response_structure(self):
        """探测真实响应格式，记录响应结构用于迭代解析逻辑。

        此测试打印完整响应，帮助理解 API 网关返回格式。
        """
        from aidev_agent.api.bk_agent import BkAgentApi

        backend = BkAiBackend()
        client = BkAgentApi.get_client(agent_code="ai-judge-0319")
        spec = AgentSpec(
            name="ai-judge-0319",
            description="Judge agent",
            backend_type=AgentBackendType.BKAI,
            params={"agent_code": "ai-judge-0319", "client": client},
        )
        result = backend.execute(spec, "hello", session_code="e2e_test_session")

        # 验证返回结构包含必要字段
        assert result.status is not None
        # 如果 completed，验证 result 字段存在
        if result.status == "completed":
            assert result.result is not None
