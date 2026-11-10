"""Resource/model ownership must not overwrite the MCP/Skill executor identity."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aidev_agent.api.constants import TENANT_HEADER
from aidev_agent.packages.resource_manager.agent import AgentResourceManager
from aidev_agent.pydantic_models import AgentConfig
from aidev_agent.services.agent.chat import ChatAgentBuilder


@pytest.fixture
def runtime_builder(mocker):
    manager = AgentResourceManager(app_code="global-app", app_secret="example", username="caller", tenant_id="abc")
    mocker.patch.object(manager, "resolve_access_token", return_value="caller-token")
    config = AgentConfig(
        agent_code="global-app",
        agent_name="Global",
        chat_model="same-code",
        non_thinking_llm="same-code",
        fast_llm="same-code",
        tenant_id="system",
        agent_info={"prompt_setting": {"fallback_vision_model": "same-code"}},
    )
    ctx = SimpleNamespace(
        agent_config=config,
        resource_manager=manager,
        chat=None,
        username="caller",
        session_code="s",
        session_context_data=[],
    )
    return ChatAgentBuilder(ctx)


@pytest.mark.parametrize(
    "method", ["build_chat_model", "build_chat_model_non_thinking", "build_chat_model_fast", "build_chat_model_vision"]
)
@pytest.mark.parametrize("resource_tenant,expected", [("system", "system"), ("", "abc")])
def test_all_models_use_config_owner(runtime_builder, mocker, method, resource_tenant, expected):
    runtime_builder.ctx.agent_config.tenant_id = resource_tenant
    mocker.patch("aidev_agent.services.agent.chat.settings.LLM_GW_ENDPOINT", "https://gateway.example.com/v1")
    factory = mocker.patch("aidev_agent.services.agent.chat.ChatModel.get_setup_instance")
    getattr(runtime_builder, method)()
    assert factory.call_args.kwargs["tenant_id"] == expected
    assert runtime_builder.ctx.resource_manager.tenant_id == "abc"


@pytest.mark.parametrize("caller_tenant", ["abc", "other"])
def test_skill_sandbox_uses_original_executor(runtime_builder, mocker, caller_tenant):
    manager = runtime_builder.ctx.resource_manager
    manager.tenant_id = caller_tenant
    client = mocker.Mock()
    mocker.patch("aidev_agent.packages.resource_manager.base.BkPaaSSandboxApi.get_client", return_value=client)
    executor = runtime_builder.build_executor_info()
    manager.get_paas_sbx_client(executor)
    assert executor["executor"] == "caller"
    assert executor["access_token"] == "caller-token"
    client.update_headers.assert_called_once_with({TENANT_HEADER: caller_tenant})
    assert runtime_builder.ctx.agent_config.tenant_id == "system"


@pytest.mark.parametrize("caller_tenant", ["abc", "other"])
def test_mcp_execution_keeps_original_tenant(runtime_builder, mocker, caller_tenant):
    manager = runtime_builder.ctx.resource_manager
    manager.tenant_id = caller_tenant
    executor = runtime_builder.build_executor_info()
    config = {"tool": {"url": "https://tools.example.com/mcp", "transport": "sse", "credential_type": "blueapps"}}
    client = mocker.Mock(get_tools=AsyncMock(return_value=[]))
    factory = mocker.patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient", return_value=client)
    mocker.patch("aidev_agent.packages.resource_manager.base.run_coro_sync", side_effect=lambda fn: asyncio.run(fn()))
    manager.construct_mcp(config, username="caller", executor_info=executor)
    headers = factory.call_args.args[0]["tool"]["headers"]
    assert headers[TENANT_HEADER] == caller_tenant
    assert runtime_builder.ctx.agent_config.tenant_id == "system"
    assert "headers" not in config["tool"]
