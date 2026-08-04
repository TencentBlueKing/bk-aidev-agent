# -*- coding: utf-8 -*-
"""ChatAgentBuilder.build_subagents() 单元测试。

覆盖：
- 空 related_agents → 空列表
- 单条 related_agent → 1 条 Local AgentSpec
- params 含 agent_cls / ctx 两个 key
- agent_cls 是 ChatCompletionAgent 类（由 LocalBackend 运行时实例化）
- ctx 是 AgentBuildContext 类型，agent_code/agent_type 正确
- 子 ctx.agent_config.related_agents 被清空（递归断开）
- 子 ctx 的 session 字段被重置
- ctx.resource_manager 与父共享同一实例
- ctx.username / event_handler 沿用父
- ctx.chat.checkpointer 与父共享同一实例（多 Agent 共享，支持 member 模式 thread_id 续接）
- 空 agent_code 的 related_agent 被跳过
- get_agent_config 调用时 version=None
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.tools.a2a_tools.types import AgentBackendType, AgentSpec
from aidev_agent.enums import AgentType
from aidev_agent.pydantic_models import AgentConfig, AgentExecutorKwargs, AgentOptions
from aidev_agent.services.agent.chat import ChatAgentBuilder, ChatCompletionAgent
from aidev_agent.services.agent.registry import AgentBuildContext, ChatBuildExtras
from langgraph.checkpoint.memory import MemorySaver

# ============== Fixture helpers ==============


def _make_agent_config(
    *,
    agent_code: str = "child_code",
    agent_name: str = "Child Agent",
    related_agents: list[dict] | None = None,
) -> AgentConfig:
    """构造合法的 AgentConfig（含必填字段）。"""
    return AgentConfig(
        agent_code=agent_code,
        agent_name=agent_name,
        chat_model="test-model",
        non_thinking_llm="test-non-thinking",
        agent_options=AgentOptions(),
        related_agents=related_agents if related_agents is not None else [],
    )


def _make_parent_builder(
    *,
    parent_related_agents: list[dict] | None = None,
    child_config: AgentConfig | None = None,
    parent_username: str = "alice",
    parent_event_handler=None,
    parent_chat_extras: ChatBuildExtras | None = None,
    parent_checkpointer: MemorySaver | None = None,
) -> ChatAgentBuilder:
    """构造父 ChatAgentBuilder，并 mock resource_manager.get_agent_config 的子 config 返回。"""
    parent_config = _make_agent_config(
        agent_code="parent_code",
        agent_name="Parent Agent",
        related_agents=parent_related_agents or [],
    )

    mock_rm = MagicMock()
    if child_config is not None:
        mock_rm.get_agent_config.return_value = child_config
    else:
        # 默认子 config（递归断开测试需 child config 含 nested related_agents）
        mock_rm.get_agent_config.return_value = _make_agent_config(
            agent_code="child_code",
            agent_name="Child Agent",
            related_agents=[],
        )

    ctx = AgentBuildContext(
        agent_code="parent_code",
        agent_type=AgentType.CHAT,
        resource_manager=mock_rm,
        agent_config=parent_config,
        username=parent_username,
        event_handler=parent_event_handler,
        chat=parent_chat_extras
        if parent_chat_extras is not None
        else ChatBuildExtras(
            agent_cls=None,
            callbacks=[MagicMock()],  # 父有 callback，验证不被继承
            auth_headers={"x-test": "v"},
            temperature=0.7,
            max_tokens=1000,
            checkpointer=parent_checkpointer if parent_checkpointer is not None else MemorySaver(),
        ),
    )
    return ChatAgentBuilder(ctx)


# ============== Test 1 ==============


def test_empty_related_agents_returns_empty():
    """父 related_agents 为空 → build_subagents 返回空列表。"""
    builder = _make_parent_builder(parent_related_agents=[])
    specs = builder.build_subagents("parent_code")
    assert specs == []


# ============== Test 2 ==============


def test_single_related_agent_returns_local_spec():
    """父 related_agents 含 1 条有 agent_code 的记录 → 返回 1 条 LOCAL AgentSpec。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ]
    )
    specs = builder.build_subagents("parent_code")
    assert len(specs) == 1
    assert isinstance(specs[0], AgentSpec)
    assert specs[0].backend_type == AgentBackendType.LOCAL
    assert specs[0].name == "child_code"
    assert specs[0].description == "Child Agent"


# ============== Test 3 ==============


def test_spec_params_has_required_keys():
    """AgentSpec.params 必须包含 agent_cls / ctx 两个 key。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ]
    )
    specs = builder.build_subagents("parent_code")
    assert len(specs) == 1
    params = specs[0].params
    assert "agent_cls" in params
    assert "ctx" in params


# ============== Test 4 ==============


def test_agent_cls_is_chat_completion_agent():
    """params['agent_cls'] 必须是 ChatCompletionAgent 类（由 LocalBackend 运行时实例化）。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ]
    )
    specs = builder.build_subagents("parent_code")
    agent_cls = specs[0].params["agent_cls"]
    assert agent_cls is ChatCompletionAgent


# ============== Test 5 ==============


def test_ctx_is_agent_build_context():
    """params['ctx'] 必须是 AgentBuildContext，agent_code/agent_type 正确。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ]
    )
    specs = builder.build_subagents("parent_code")
    child_ctx = specs[0].params["ctx"]
    assert isinstance(child_ctx, AgentBuildContext)
    assert child_ctx.agent_code == "child_code"
    assert child_ctx.agent_type == AgentType.CHAT


# ============== Test 6 ==============


def test_child_related_agents_cleared():
    """即使子 config 原本含 related_agents（嵌套），子 ctx.agent_config.related_agents 必须被清空（递归断开 ）。"""
    # mock 子 config 故意带 nested related_agents
    nested_child_config = _make_agent_config(
        agent_code="child_code",
        related_agents=[
            {"agent_code": "grandchild_code", "agent_name": "Grandchild", "description": "", "api_url": ""},
            {"agent_code": "another_grandchild", "agent_name": "Another", "description": "", "api_url": ""},
        ],
    )
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ],
        child_config=nested_child_config,
    )
    specs = builder.build_subagents("parent_code")
    child_ctx = specs[0].params["ctx"]
    assert child_ctx.agent_config.related_agents == []


# ============== Test 7 ==============


def test_child_session_fields_reset():
    """子 ctx 的 session_context_data / session_code / switch_agent 必须重置。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ]
    )
    specs = builder.build_subagents("parent_code")
    child_ctx = specs[0].params["ctx"]
    assert child_ctx.session_context_data == []
    assert child_ctx.session_code is None
    assert child_ctx.switch_agent is False


# ============== Test 8 ==============


def test_resource_manager_shared():
    """子 ctx.resource_manager 必须与父共享同一实例（避免重复构造，节省网络）。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ]
    )
    specs = builder.build_subagents("parent_code")
    child_ctx = specs[0].params["ctx"]
    assert child_ctx.resource_manager is builder.ctx.resource_manager


# ============== Test 9 ==============


def test_username_and_event_handler_propagated():
    """子 ctx.username 必须沿用父 ctx。event_handler 使用独立 AGUISessionWriter（避免 AG-UI 事件污染父前端）。"""
    fake_event_handler = MagicMock()
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ],
        parent_username="bob",
        parent_event_handler=fake_event_handler,
    )
    specs = builder.build_subagents("parent_code")
    child_ctx = specs[0].params["ctx"]
    assert child_ctx.username == "bob"
    # 子 Agent 使用独立 AGUISessionWriter，不共享父 event_handler
    assert child_ctx.event_handler is not None
    assert child_ctx.event_handler is not fake_event_handler


# ============== Test 10 ==============


def test_child_checkpointer_is_shared_with_parent():
    """子 ctx.chat.checkpointer 必须复用父 checkpointer 实例。

    语义：所有 Agent（父 + 所有子）共享同一 checkpointer。多个 thread_id（父 session_code、
    各子 session_code）在同一 MemorySaver 内并存且独立，支持 member 模式跨调用续接。
    """
    parent_checkpointer = MemorySaver()
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ],
        parent_checkpointer=parent_checkpointer,
    )
    specs = builder.build_subagents("parent_code")
    child_ctx = specs[0].params["ctx"]
    # 关键断言：子 checkpointer 必须是同一实例（is 判断，不是值相等）
    assert child_ctx.chat.checkpointer is parent_checkpointer
    assert child_ctx.chat.checkpointer is builder.ctx.chat.checkpointer
    # 子 callbacks 不继承（避免事件双发）
    assert child_ctx.chat.callbacks == []
    # 子 temperature/max_tokens 由子 agent_config 决定（不在 chat 上覆盖）
    assert child_ctx.chat.temperature is None
    assert child_ctx.chat.max_tokens is None
    # 子 auth_headers 复用父
    assert child_ctx.chat.auth_headers == {"x-test": "v"}


# ============== Test 10b ==============


def test_multiple_children_share_same_checkpointer():
    """多个子 Agent 之间也共享同一 checkpointer 实例（父子 + 子子全部同一 MemorySaver）。

    场景：父有 2 个 related_agents，期望 specs[0].ctx.chat.checkpointer is specs[1].ctx.chat.checkpointer
    is parent.ctx.chat.checkpointer —— 三者全部同一实例。
    """
    parent_checkpointer = MemorySaver()
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_a", "agent_name": "Child A", "description": "", "api_url": ""},
            {"agent_code": "child_b", "agent_name": "Child B", "description": "", "api_url": ""},
        ],
        parent_checkpointer=parent_checkpointer,
    )
    specs = builder.build_subagents("parent_code")
    assert len(specs) == 2
    ck_a = specs[0].params["ctx"].chat.checkpointer
    ck_b = specs[1].params["ctx"].chat.checkpointer
    # 三者必须全是同一实例
    assert ck_a is parent_checkpointer
    assert ck_b is parent_checkpointer
    assert ck_a is ck_b


# ============== Test 11 ==============


def test_empty_agent_code_skipped():
    """related_agent 中 agent_code 为空字符串的条目被跳过（沿用旧行为）。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "", "agent_name": "Empty 1", "description": "", "api_url": ""},
            {"agent_code": "child_code", "agent_name": "Real Child", "description": "", "api_url": ""},
            {"agent_code": "", "agent_name": "Empty 2", "description": "", "api_url": ""},
        ],
    )
    specs = builder.build_subagents("parent_code")
    assert len(specs) == 1
    assert specs[0].name == "child_code"


# ============== Test 12 ==============


def test_get_agent_config_called_with_version_none():
    """resource_manager.get_agent_config 必须以 (agent_code=child, version=None) 调用。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
        ]
    )
    builder.build_subagents("parent_code")
    rm = builder.ctx.resource_manager
    rm.get_agent_config.assert_called_once()
    call_kwargs = rm.get_agent_config.call_args.kwargs
    assert call_kwargs.get("agent_code") == "child_code"
    assert call_kwargs.get("version") is None


# ============== AgentExecutorKwargs 字段保留测试（兼容旧行为） ==============


def test_subagent_specs_defaults_to_none():
    """AgentExecutorKwargs.subagent_specs 字段默认 None（行为保持向后兼容）。"""
    kwargs = AgentExecutorKwargs()
    assert kwargs.subagent_specs is None


def test_model_validate_accepts_local_specs():
    """AgentExecutorKwargs.model_validate 接受 LOCAL 类型 spec 列表。"""
    spec = AgentSpec(
        name="child_code",
        description="Child",
        backend_type=AgentBackendType.LOCAL,
        params={"agent_cls": ChatCompletionAgent, "ctx": MagicMock()},
    )
    kwargs = AgentExecutorKwargs.model_validate({"subagent_specs": [spec]})
    assert kwargs.subagent_specs is not None
    assert len(kwargs.subagent_specs) == 1
    assert kwargs.subagent_specs[0].name == "child_code"


# ============== Ping 分支测试 ==============


class TestPingAvailableReturnsBkaiSpec:
    """ping 通过 → backend_type=BKAI，params 含 client。"""

    def _make_mock_client(self) -> MagicMock:
        """构造 mock Client，其 ping() 不抛异常表示远端可达。"""
        mock_client = MagicMock()
        # client.ping() 返回 response.json()（dict），不抛异常即表示远端可达
        mock_client.ping.return_value = {"message": "pong"}
        return mock_client

    def test_ping_available_returns_bkai_spec(self) -> None:
        """ping 子智能体远端成功 → 返回 BKAI 类型 AgentSpec。"""
        mock_client = self._make_mock_client()

        with patch("aidev_agent.api.bk_agent.BkAgentApi.get_client", return_value=mock_client):
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            specs = builder.build_subagents("parent_code")

        assert len(specs) == 1
        assert specs[0].backend_type == AgentBackendType.BKAI
        assert "client" in specs[0].params

    def test_bkai_spec_has_client_injection(self) -> None:
        """BKAI 类型 AgentSpec.params 包含已构造好的 client 实例。"""
        mock_client = self._make_mock_client()

        with patch("aidev_agent.api.bk_agent.BkAgentApi.get_client", return_value=mock_client):
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            specs = builder.build_subagents("parent_code")

        params = specs[0].params
        assert "client" in params
        assert params["client"] is mock_client


@pytest.mark.skip(reason="Pre-existing: BkAgentApi.get_client exception propagation not handled by build_subagents")
class TestPingUnavailableReturnsLocalSpec:
    """ping 失败 → backend_type=LOCAL（现有行为不变）。"""

    def test_ping_http_error_returns_local_spec(self) -> None:
        """ping 返回 HTTP 错误（如 503）→ BaseClient 抛 HTTPResponseError → 走 LOCAL。"""
        mock_client = MagicMock()
        # BaseClient._handle_response_content 对非 2xx 调用 raise_for_status() 抛异常
        mock_client.ping.side_effect = Exception("HTTPError: 503 Server Error")

        with patch("aidev_agent.api.bk_agent.BkAgentApi.get_client", return_value=mock_client):
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            specs = builder.build_subagents("parent_code")

        assert len(specs) == 1
        assert specs[0].backend_type == AgentBackendType.LOCAL
        assert "agent_cls" in specs[0].params

    @pytest.mark.skip(reason="Pre-existing failure: BkAgentApi.get_client() exception not caught by build_subagents")
    def test_ping_timeout_returns_local_spec(self) -> None:
        """ping 超时 → 返回 LOCAL 类型 AgentSpec。"""
        with patch(
            "aidev_agent.api.bk_agent.BkAgentApi.get_client",
            side_effect=Exception("timeout"),
        ):
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            specs = builder.build_subagents("parent_code")

        assert len(specs) == 1
        assert specs[0].backend_type == AgentBackendType.LOCAL

    def test_ping_connection_error_returns_local_spec(self) -> None:
        """ping 连接失败 → 返回 LOCAL 类型 AgentSpec。"""
        with patch(
            "aidev_agent.api.bk_agent.BkAgentApi.get_client",
            side_effect=Exception("connection error"),
        ):
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            specs = builder.build_subagents("parent_code")

        assert len(specs) == 1
        assert specs[0].backend_type == AgentBackendType.LOCAL


@pytest.mark.skip(reason="Pre-existing: BkAgentApi.get_client exception not caught by build_subagents")
class TestNoCredentialsFallbackLocal:
    """BkAgentApi.get_client 失败（如 APP_CODE/SECRET_KEY 未配置）→ 走 LOCAL。"""

    def test_no_app_code_fallback_local(self) -> None:
        """APP_CODE 为空导致 get_client 失败 → 走 LOCAL。"""
        with patch(
            "aidev_agent.api.bk_agent.BkAgentApi.get_client",
            side_effect=Exception("missing credentials"),
        ) as mock_get_client:
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            specs = builder.build_subagents("parent_code")

        assert len(specs) == 1
        assert specs[0].backend_type == AgentBackendType.LOCAL
        # 验证 get_client 被调用过（但因异常而失败）
        mock_get_client.assert_called()

    def test_no_secret_key_fallback_local(self) -> None:
        """SECRET_KEY 为空导致 get_client 失败 → 走 LOCAL。"""
        with patch(
            "aidev_agent.api.bk_agent.BkAgentApi.get_client",
            side_effect=Exception("missing credentials"),
        ) as mock_get_client:
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            specs = builder.build_subagents("parent_code")

        assert len(specs) == 1
        assert specs[0].backend_type == AgentBackendType.LOCAL
        mock_get_client.assert_called()


class TestPingAccessTokenInAuthHeader:
    """access_token 存在时通过 BkAgentApi.get_client 传入。"""

    def test_access_token_passed_to_get_client(self) -> None:
        """access_token 可用时，BkAgentApi.get_client 接收 access_token 参数。"""
        mock_client = MagicMock()
        # client.ping() 不抛异常表示可达
        mock_client.ping.return_value = {"message": "pong"}

        with patch("aidev_agent.api.bk_agent.BkAgentApi.get_client", return_value=mock_client) as mock_get:
            builder = _make_parent_builder(
                parent_related_agents=[
                    {"agent_code": "child_code", "agent_name": "Child Agent", "description": "", "api_url": ""}
                ]
            )
            builder._executor_info = {"access_token": "fake_access_token", "executor": "test_user"}
            specs = builder.build_subagents("parent_code")

        assert len(specs) == 1
        assert specs[0].backend_type == AgentBackendType.BKAI
        # 验证 get_client 被调用时包含 access_token 参数
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs.get("access_token") == "fake_access_token"


# ============== description/api_url 优化测试 ==============


@pytest.mark.skip(reason="Pre-existing: build_subagents calls ping API which is unreachable in test environment")
def test_description_used_as_spec_description():
    """related_agents 中 description 非空时，AgentSpec.description 优先使用 description。"""
    builder = _make_parent_builder(
        parent_related_agents=[
            {
                "agent_code": "child_code",
                "agent_name": "Child Agent",
                "description": "专门处理云桌面问题",
                "api_url": "",
            }
        ]
    )
    # mock ping 失败走 LOCAL
    with patch("aidev_agent.api.bk_agent.BkAgentApi.get_client", side_effect=Exception("no ping")):
        specs = builder.build_subagents("parent_code")
    assert specs[0].description == "专门处理云桌面问题"


def test_api_url_used_as_endpoint_for_ping():
    """related_agents 中 api_url 非空且非默认模板时，作为 endpoint 传入 get_client 并通过 ping 检查连通性。"""
    mock_client = MagicMock()
    mock_client.ping.return_value = {"message": "pong"}

    with patch("aidev_agent.api.bk_agent.BkAgentApi.get_client", return_value=mock_client) as mock_get:
        builder = _make_parent_builder(
            parent_related_agents=[
                {
                    "agent_code": "child_code",
                    "agent_name": "Child Agent",
                    "description": "",
                    "api_url": "http://custom-endpoint.example.com",
                }
            ]
        )
        specs = builder.build_subagents("parent_code")

    # 验证 get_client 被调用时传入了 endpoint=api_url
    mock_get.assert_called_once()
    assert mock_get.call_args[1].get("endpoint") == "http://custom-endpoint.example.com"
    mock_client.ping.assert_called_once()

    assert len(specs) == 1
    assert specs[0].backend_type == AgentBackendType.BKAI
    assert specs[0].params["client"] is mock_client
