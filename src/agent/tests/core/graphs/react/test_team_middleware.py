# -*- coding: utf-8 -*-
"""Tests for Team middleware as a ReAct enhancement.

Tests cover:
- TeamInfo TypedDict fields
- TeamPromptMiddleware prompt injection
- TeamConfig configuration container
- ReActAgentBuilder.add_subagent_specs integration

工具过滤（tool_deny / tool_allow / spawn_depth）已下沉到装配期，不再属于 Team
中间件的职责；对应用例见 test_tool_loading_mode.py。
"""

from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.graphs.react.team_middleware import TeamConfig, TeamInfo, TeamPromptMiddleware
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext, PromptSlots
from aidev_agent.core.tools.a2a_tools.types import AgentBackendType, AgentSpec
from langchain_core.runnables import RunnableConfig

# =============================================================================
# TeamInfo Tests
# =============================================================================


class TestTeamInfo:
    """Tests for TeamInfo TypedDict."""

    def test_team_info_has_expected_fields(self):
        """Test that TeamInfo has bk_agent_team field."""
        assert "bk_agent_team" in TeamInfo.__annotations__


# =============================================================================
# TeamPromptMiddleware Tests
# =============================================================================


class TestTeamPromptMiddleware:
    """Tests for TeamPromptMiddleware."""

    def test_middleware_injects_member_info(self):
        """Test that middleware injects Team member descriptions into system prompt."""
        specs = [
            AgentSpec(
                name="helper",
                description="A helper agent",
                backend_type=AgentBackendType.BKAI,
                params={"agent_code": "test"},
            ),
            AgentSpec(
                name="analyst",
                description="An analyst agent",
                backend_type=AgentBackendType.LOCAL,
                params={},
            ),
        ]
        middleware = TeamPromptMiddleware(specs=specs)
        ctx = ProcessorContext(state={}, config=RunnableConfig())
        ctx.prompt_slots = PromptSlots(system="Base system prompt")
        called = False

        def next_fn():
            nonlocal called
            called = True

        middleware(ctx, next_fn)
        assert called
        assert "Team Members" in ctx.prompt_slots.system
        assert "helper" in ctx.prompt_slots.system
        assert "analyst" in ctx.prompt_slots.system
        assert "task" in ctx.prompt_slots.system
        assert "member" in ctx.prompt_slots.system

    def test_middleware_empty_specs(self):
        """Test that middleware with empty specs just calls next()."""
        middleware = TeamPromptMiddleware(specs=[])
        ctx = ProcessorContext(state={}, config=RunnableConfig())
        ctx.prompt_slots = PromptSlots(system="Base")
        middleware(ctx, lambda: None)
        assert ctx.prompt_slots.system == "Base"

    def test_middleware_appends_to_existing_prompt(self):
        """Test that middleware appends to an existing system prompt."""
        specs = [AgentSpec(name="worker", description="A worker", backend_type=AgentBackendType.BKAI, params={})]
        middleware = TeamPromptMiddleware(specs=specs)
        ctx = ProcessorContext(state={}, config=RunnableConfig())
        ctx.prompt_slots = PromptSlots(system="You are a helpful assistant.")
        middleware(ctx, lambda: None)
        assert "You are a helpful assistant." in ctx.prompt_slots.system
        assert "worker" in ctx.prompt_slots.system


# =============================================================================
# TeamConfig Tests
# =============================================================================


class TestTeamConfig:
    """Tests for TeamConfig configuration container."""

    def test_default_config(self):
        """Test default TeamConfig values."""
        config = TeamConfig()
        assert config.specs == []
        assert config.resolver is None

    def test_config_with_specs(self):
        """Test TeamConfig with specs."""
        specs = [AgentSpec(name="a", description="b", backend_type=AgentBackendType.BKAI, params={})]
        config = TeamConfig(specs=specs, resolver="mock-resolver")
        assert len(config.specs) == 1
        assert config.resolver is not None


# =============================================================================
# ReActAgentBuilder.add_subagent_specs Integration Tests
# =============================================================================


class TestReActAgentBuilderAddSubagentSpecs:
    """Tests for ReActAgentBuilder.add_subagent_specs method."""

    def test_add_subagent_specs_returns_builder(self):
        """Test that add_subagent_specs returns builder for chaining and extends specs."""
        builder = ReActAgentBuilder()
        specs = [AgentSpec(name="a", description="b", backend_type=AgentBackendType.BKAI, params={})]
        result = builder.add_subagent_specs(specs)
        assert result is builder
        assert builder._a2a_specs == specs
        # add_subagent_specs 仅添加 specs，不自动启用 a2a tool 和 task
        assert builder._enable_a2a_tool is False
        assert builder._a2a_resolver is None

    def test_add_subagent_specs_empty_specs(self):
        """Test that add_subagent_specs with empty specs returns builder without side effects."""
        builder = ReActAgentBuilder()
        result = builder.add_subagent_specs([])
        assert result is builder
        assert builder._a2a_specs == []
        assert builder._a2a_resolver is None
        assert builder._enable_a2a_tool is False

    def test_add_subagent_specs_enables_task(self):
        """add_subagent_specs 不再隐式启用 task，需显式调用 enable_task()。"""
        builder = ReActAgentBuilder()
        specs = [AgentSpec(name="a", description="b", backend_type=AgentBackendType.BKAI, params={})]
        builder.add_subagent_specs(specs)
        assert builder._enable_task is False
