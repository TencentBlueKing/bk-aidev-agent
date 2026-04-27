# -*- coding: utf-8 -*-
"""AgentProtocol / AgentBuildContext / agent_registry 契约测试

覆盖：
- ``agent_registry``（``SimpleFactory`` 实例）默认注册 / 取实现类 / 未注册行为。
- AgentBuildContext 字段透传（含 ``**extra``）。
- ChatCompletionAgent.build / FlowAgentCompletionAgent.build classmethod 契约。
- 工厂调用链（``AgentInstanceFactory.build_agent`` → ``agent_class().build(ctx)``）。
- R2 修复：chat agent 字段名 ``knowledges`` 取 ``build_knowledge_items`` 的返回值。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.enums import AgentBuildType, AgentType
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from aidev_agent.services.agent import (
    AgentBuildContext,
    AgentInstanceFactory,
    ChatBuildExtras,
    ChatCompletionAgent,
    FlowAgentCompletionAgent,
    FlowBuildExtras,
    agent_registry,
)
from aidev_agent.services.agent.chat import ChatAgentBuilder
from aidev_agent.services.common_agent import CommonQAAgent
from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager
from aidev_agent.services.pydantic_models import AgentOptions
from aidev_agent.utils.factory import SimpleFactory
from langgraph.checkpoint.memory import MemorySaver


def _make_agent_config(agent_code: str = "agent-x", **overrides) -> AgentConfig:
    """构造一个最小化的 AgentConfig，用于直接装入 ctx.agent_config。"""
    base = dict(
        agent_code=agent_code,
        agent_name=agent_code,
        chat_model="mock-llm",
        non_thinking_llm="mock-llm",
        agent_options=AgentOptions(),
    )
    base.update(overrides)
    return AgentConfig(**base)


def _make_chat_ctx(
    agent_code: str = "agent-x",
    *,
    session_code: str | None = "session-1",
    callbacks=None,
    agent_cls=CommonQAAgent,
    session_context_data=None,
    switch_agent: bool = False,
    event_handler=None,
) -> AgentBuildContext:
    """构造 chat 路径的 AgentBuildContext（无 factory 反向引用）。"""
    return AgentBuildContext(
        agent_code=agent_code,
        agent_type=AgentType.CHAT,
        agent_config=_make_agent_config(agent_code),
        config_manager_class=AgentConfigManager,
        resource_manager=MagicMock(name="rm"),
        session_code=session_code,
        username="alice",
        session_context_data=list(session_context_data or []),
        switch_agent=switch_agent,
        event_handler=event_handler,
        chat=ChatBuildExtras(
            agent_cls=agent_cls,
            callbacks=list(callbacks or []),
            checkpointer=MemorySaver(),
        ),
    )


# ============================== agent_registry ==============================


class TestAgentRegistry:
    def test_default_registrations_present(self):
        """默认注册中心包含 CHAT / FLOW 两类"""
        keys = list(agent_registry.keys())
        assert AgentType.CHAT in keys
        assert AgentType.FLOW in keys
        assert AgentType.CHAT in agent_registry
        assert AgentType.FLOW in agent_registry

    def test_must_get_returns_implementation_class(self):
        """``must_get`` 返回的就是 Agent 实现类本身"""
        assert agent_registry.must_get(AgentType.CHAT) is ChatCompletionAgent
        assert agent_registry.must_get(AgentType.FLOW) is FlowAgentCompletionAgent

    def test_must_get_unregistered_raises_runtime_error(self):
        """``must_get`` 对未注册类型抛 ``RuntimeError``（``SimpleFactory`` 默认行为）"""
        registry: SimpleFactory[AgentType, type] = SimpleFactory("agent-test")
        with pytest.raises(RuntimeError, match="not exists"):
            registry.must_get(AgentType.CHAT)


# ============================== AgentBuildContext ==============================


class TestAgentBuildContext:
    def test_default_fields(self):
        ctx = AgentBuildContext(
            agent_code="x",
            agent_type=AgentType.CHAT,
            agent_config=_make_agent_config("x"),
            config_manager_class=AgentConfigManager,
            resource_manager=MagicMock(),
        )
        assert ctx.agent_code == "x"
        assert ctx.agent_type == AgentType.CHAT
        assert ctx.session_context_data == []
        assert ctx.switch_agent is False
        assert ctx.event_handler is None
        assert ctx.chat is None
        assert ctx.flow is None
        assert ctx.extra == {}

    def test_extra_passthrough_keeps_only_non_flow_fields(self):
        """flow 专属字段在工厂层迁移到 ctx.flow，extra 仅留余项"""
        ctx = AgentBuildContext(
            agent_code="x",
            agent_type=AgentType.FLOW,
            agent_config=_make_agent_config("x"),
            config_manager_class=AgentConfigManager,
            resource_manager=MagicMock(),
            flow=FlowBuildExtras(task_id="T-1", poll_interval=0.5),
            extra={"trace_id": "tx-1"},
        )
        assert ctx.flow.task_id == "T-1"
        assert ctx.flow.poll_interval == 0.5
        assert ctx.extra == {"trace_id": "tx-1"}


# ============================== ClassVar 元数据 ==============================


class TestAgentClassVar:
    def test_chat_agent_classvar(self):
        assert ChatCompletionAgent.agent_type == AgentType.CHAT
        assert hasattr(ChatCompletionAgent, "build")
        assert callable(ChatCompletionAgent.build)

    def test_flow_agent_classvar(self):
        assert FlowAgentCompletionAgent.agent_type == AgentType.FLOW
        assert hasattr(FlowAgentCompletionAgent, "build")
        assert callable(FlowAgentCompletionAgent.build)


# ============================== ChatCompletionAgent.build ==============================


def _patch_chat_builder(knowledges=None):
    """patch ``ChatAgentBuilder``，使其装配方法返回 pydantic 校验通过的真实值

    返回 (patcher, builder_mock)。调用方需 ``patcher.start()`` / ``patcher.stop()``，
    或使用 with 语法。
    """
    builder_mock = MagicMock(spec=ChatAgentBuilder)
    builder_mock.build_chat_model.return_value = MockChatModel(responses=["hi"])
    builder_mock.build_non_thinking_llm.return_value = None
    builder_mock.build_skills.return_value = ["skill_a"]
    builder_mock.build_tools.return_value = []
    builder_mock.build_knowledge_bases.return_value = [{"id": "kb1"}]
    builder_mock.build_knowledge_items.return_value = knowledges or [{"id": "ki1"}, {"id": "ki2"}]
    builder_mock.build_chat_history.return_value = []
    builder_mock.build_agent_options.return_value = AgentOptions()
    builder_mock.build_agent_prompt.return_value = "prompt"
    builder_mock.build_executor_info.return_value = {"executor": "u"}
    builder_mock.build_checkpointer.return_value = MemorySaver()
    builder_mock.get_role_prompt.return_value = "role"
    builder_mock.handle_agent_switch.return_value = None
    builder_mock.mcp_fetch_failures = []
    return patch(
        "aidev_agent.services.agent.chat.ChatAgentBuilder",
        return_value=builder_mock,
    ), builder_mock


class TestChatCompletionAgentBuild:
    def test_build_populates_core_fields(self):
        ctx = _make_chat_ctx()
        patcher, builder_mock = _patch_chat_builder()
        with patcher:
            agent = ChatCompletionAgent().build(ctx)
        assert isinstance(agent, ChatCompletionAgent)
        assert agent.agent_cls is ctx.chat.agent_cls
        assert agent.callbacks == ctx.chat.callbacks
        assert agent.thread_id == ctx.session_code
        builder_mock.handle_agent_switch.assert_called_once_with()

    def test_build_knowledges_field_uses_build_knowledge_items(self):
        """R2 修复：build_chat_agent_args 旧 key 'knowledge_items' → 'knowledges'"""
        expected_items = [{"id": "ki1"}, {"id": "ki2"}]
        ctx = _make_chat_ctx()
        patcher, _ = _patch_chat_builder(knowledges=expected_items)
        with patcher:
            agent = ChatCompletionAgent().build(ctx)
        # 历史 bug：旧实现 key 写成 'knowledge_items' 被 pydantic 静默丢弃，
        # 致使 agent.knowledges 永远为 None；本 feat 已修复。
        assert agent.knowledges == expected_items

    def test_build_event_handler_passthrough(self):
        sentinel = MagicMock(name="event_handler")
        ctx = _make_chat_ctx(event_handler=sentinel)
        patcher, _ = _patch_chat_builder()
        with patcher:
            agent = ChatCompletionAgent().build(ctx)
        assert agent.event_handler is sentinel


# ============================== FlowAgentCompletionAgent.build ==============================


def _make_flow_ctx(
    *,
    session_code: str | None = "sess-1",
    username: str | None = "alice",
    resource_manager=None,
    flow: FlowBuildExtras | None = None,
    event_handler=None,
) -> AgentBuildContext:
    rm = resource_manager if resource_manager is not None else MagicMock(name="default_rm")
    return AgentBuildContext(
        agent_code="agent-x",
        agent_type=AgentType.FLOW,
        agent_config=_make_agent_config("agent-x"),
        config_manager_class=AgentConfigManager,
        resource_manager=rm,
        session_code=session_code,
        username=username,
        flow=flow,
        event_handler=event_handler,
    )


class TestFlowAgentCompletionAgentBuild:
    def test_build_uses_flow_resource_manager(self):
        flow_rm = MagicMock(name="flow_rm")
        flow_rm.start_flow_agent = lambda **kw: {"task_id": "T"}
        ctx = _make_flow_ctx(
            flow=FlowBuildExtras(
                flow_resource_manager=flow_rm,
                task_id="preset-task",
                flow_start_params={"k": "v"},
                poll_interval=0.1,
                poll_timeout=1.0,
            ),
        )
        agent = FlowAgentCompletionAgent().build(ctx)
        assert isinstance(agent, FlowAgentCompletionAgent)
        assert agent.resource_manager is flow_rm  # flow.flow_resource_manager 优先
        assert agent.session_code == "sess-1"
        assert agent.task_id == "preset-task"
        assert agent.flow_start_params == {"k": "v"}
        assert agent.poll_interval == 0.1
        assert agent.poll_timeout == 1.0
        assert agent.username == "alice"

    def test_build_falls_back_to_ctx_resource_manager(self):
        default_rm = MagicMock(name="default_rm")
        default_rm.start_flow_agent = lambda **kw: {"task_id": "T"}
        ctx = _make_flow_ctx(
            session_code=None,
            username=None,
            resource_manager=default_rm,
            flow=FlowBuildExtras(),
        )
        agent = FlowAgentCompletionAgent().build(ctx)
        assert agent.resource_manager is default_rm

    def test_build_event_handler_passthrough(self):
        rm = MagicMock(name="rm")
        rm.start_flow_agent = lambda **kw: {"task_id": "T"}
        sentinel = MagicMock(name="event_handler")
        ctx = _make_flow_ctx(
            session_code=None,
            username=None,
            resource_manager=rm,
            flow=FlowBuildExtras(),
            event_handler=sentinel,
        )
        agent = FlowAgentCompletionAgent().build(ctx)
        assert agent.event_handler is sentinel


# ============================== 工厂端到端 ==============================


class TestFactoryEndToEnd:
    def test_unsupported_agent_type_rejected(self):
        with pytest.raises(ValueError, match="Unsupported agent_type"):
            AgentInstanceFactory.build_agent(
                agent_type=AgentType.TASK,
                build_type=AgentBuildType.DIRECT,
                session_context_data=[],
            )

    def test_session_required_for_session_build_type(self):
        """SESSION 构建期必须提供 session_code"""
        with pytest.raises(ValueError, match="session_code is required"):
            AgentInstanceFactory.build_agent(
                agent_type=AgentType.CHAT,
                build_type=AgentBuildType.SESSION,
                session_code=None,
            )

    def test_flow_direct_build_through_factory(self):
        """flow 路径走 DIRECT，extra 透传到 FlowAgent.build"""
        flow_rm = MagicMock(name="flow_rm")
        flow_rm.start_flow_agent = lambda **kw: {"task_id": "T"}

        agent = AgentInstanceFactory.build_agent(
            agent_type=AgentType.FLOW,
            build_type=AgentBuildType.DIRECT,
            session_code="sess-2",
            session_context_data=[],
            username="bob",
            flow_resource_manager=flow_rm,
            task_id="task-9",
            flow_start_params={"a": 1},
            poll_interval=0.2,
            poll_timeout=2.0,
        )
        assert isinstance(agent, FlowAgentCompletionAgent)
        assert agent.task_id == "task-9"
        assert agent.flow_start_params == {"a": 1}
        assert agent.session_code == "sess-2"
        assert agent.poll_interval == 0.2
        assert agent.poll_timeout == 2.0
        assert agent.resource_manager is flow_rm
        assert agent.username == "bob"
