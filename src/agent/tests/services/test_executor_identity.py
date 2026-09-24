# -*- coding: utf-8 -*-
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

from aidev_agent.services.agent.approval import ApprovalStateHandler
from aidev_agent.services.agent.chat import ChatAgentBuilder, ChatCompletionAgent
from aidev_agent.services.agent.executor_identity import (
    AUTH_HEADER_KEY,
    apply_http_approver_identity,
    collect_approver_tool_names,
    make_mcp_approver_interceptor,
    make_mcp_identity_ctx,
    normalize_executor_identity,
)
from aidev_agent.services.agent.registry import AgentBuildContext


def test_normalize_executor_identity_rules():
    assert normalize_executor_identity("approver", approval_enabled=True) == "approver"
    assert normalize_executor_identity("approver", approval_enabled=False) == "user"
    assert normalize_executor_identity("admin", approval_enabled=True) == "user"
    assert normalize_executor_identity("", approval_enabled=True) == "user"


def test_apply_http_approver_identity_uses_approver_access_token():
    extra = SimpleNamespace(header={AUTH_HEADER_KEY: json.dumps({"access_token": "alice-token"})})
    wrapper = SimpleNamespace(_extra=extra)
    tool = MagicMock()
    tool.name = "weather"
    tool.func = wrapper
    tool.metadata = {"approval": {"executor_identity": "approver"}}
    skipped = MagicMock()
    skipped.name = "echo"
    skipped.func = SimpleNamespace(
        _extra=SimpleNamespace(header={AUTH_HEADER_KEY: json.dumps({"access_token": "keep"})})
    )
    skipped.metadata = {"approval": {"executor_identity": "user"}}

    apply_http_approver_identity(
        [tool, skipped],
        {"app_code": "app", "app_secret": "secret", "access_token": "alice-token"},
        "bob",
        "bob-token",
    )

    auth = json.loads(extra.header[AUTH_HEADER_KEY])
    assert auth == {"access_token": "bob-token"}
    assert json.loads(skipped.func._extra.header[AUTH_HEADER_KEY]) == {"access_token": "keep"}


def test_mcp_interceptor_overrides_headers_only_for_approver_tools():
    ctx = make_mcp_identity_ctx()
    ctx["approver_tools"] = {"echo"}
    ctx["approved_by"] = "bob"
    ctx["approver_access_token"] = "bob-token"
    interceptor = make_mcp_approver_interceptor(ctx, {"app_code": "app", "app_secret": "secret"})

    async def handler(request):
        return request

    echoed = asyncio.run(
        interceptor(MCPToolCallRequest(name="echo", args={}, server_name="srv", headers=None), handler)
    )
    skipped = asyncio.run(
        interceptor(MCPToolCallRequest(name="other", args={}, server_name="srv", headers=None), handler)
    )

    assert json.loads(echoed.headers[AUTH_HEADER_KEY]) == {"access_token": "bob-token"}
    assert skipped.headers is None


def test_mcp_interceptor_requires_approver_access_token():
    ctx = make_mcp_identity_ctx()
    ctx["approver_tools"] = {"echo"}
    ctx["approved_by"] = "bob"
    interceptor = make_mcp_approver_interceptor(ctx, {"app_code": "app", "app_secret": "secret"})

    async def handler(request):
        return request

    with pytest.raises(ToolException, match="正确授权"):
        asyncio.run(interceptor(MCPToolCallRequest(name="echo", args={}, server_name="srv", headers=None), handler))


def test_mcp_interceptor_records_effective_executor_identity():
    ctx = make_mcp_identity_ctx()
    ctx["approver_tools"] = {"echo"}
    ctx["approved_by"] = "bob"
    ctx["approver_access_token"] = "bob-token"
    interceptor = make_mcp_approver_interceptor(
        ctx,
        {"app_code": "app", "app_secret": "secret", "executor": "alice"},
    )

    async def handler(request):
        return request

    with patch("aidev_agent.services.agent.executor_identity.recording_span") as recording_span:
        recording_span.return_value.__enter__.return_value = MagicMock()
        asyncio.run(
            interceptor(MCPToolCallRequest(name="echo", args={}, server_name="srv", headers=None), handler)
        )

    assert recording_span.call_args.args == ("mcp.tools.call",)
    attributes = recording_span.call_args.kwargs["attributes"]
    assert attributes["mcp.server.name"] == "srv"
    assert attributes["mcp.tool.name"] == "echo"
    assert attributes["tool.type"] == "mcp"
    assert attributes["executor.identity"] == "approver"
    assert attributes["executor.username"] == "bob"
    assert attributes["approval.approved_by"] == "bob"
    assert attributes["approval.result"] == "approved"
    assert "secret" not in str(attributes)


def test_collect_approver_tool_names():
    approver = MagicMock(name="weather")
    approver.name = "weather"
    approver.metadata = {"approval": {"executor_identity": "approver"}}
    user_tool = MagicMock(name="echo")
    user_tool.name = "echo"
    user_tool.metadata = {"approval": {"executor_identity": "user"}}
    assert collect_approver_tool_names([approver, user_tool]) == {"weather"}


def test_normalize_bindings_copies_executor_identity():
    ctx = MagicMock(spec=AgentBuildContext)
    ctx.session_context_data = []
    ctx.agent_config.resources = []
    ctx.agent_config.approval_settings = {
        "strategies": [{"strategy_id": "s1", "approval_name": "默认", "approvers": ["bob"]}],
        "bindings": [
            {
                "resource_type": "tool",
                "tool_id": 1,
                "tool_code": "weather",
                "approval_strategy_id": "s1",
                "approval_enabled": True,
                "executor_identity": "approver",
            }
        ],
    }
    bindings = ChatAgentBuilder(ctx)._normalize_tool_approval_bindings()
    assert bindings[0]["executor_identity"] == "approver"


def test_fetch_approve_result_returns_approved_by():
    handler = ApprovalStateHandler()
    handler._get_latest_interrupt_record = lambda session_code: {  # type: ignore[method-assign]
        "id": 9,
        "property": {"builtin_property": {"approve_result": "approved", "approved_by": "bob"}},
        "content": {"outcome": {"type": "success", "interrupts": []}},
    }
    info = handler.fetch_approve_result("sess")
    assert info["approve_result"] == "approved"
    assert info["approved_by"] == "bob"


def test_switch_tools_to_approver_identity_updates_shared_ctx():
    extra = SimpleNamespace(header={AUTH_HEADER_KEY: json.dumps({"access_token": "tok"})})
    tool = MagicMock()
    tool.name = "weather"
    tool.func = SimpleNamespace(_extra=extra)
    tool.metadata = {"approval": {"executor_identity": "approver"}}
    ctx = make_mcp_identity_ctx()
    ctx["approver_tools"] = {"weather"}
    agent = ChatCompletionAgent.model_construct(
        tools=[tool],
        executor_info={"app_code": "app", "app_secret": "secret"},
        resource_manager=MagicMock(resolve_user_access_token=MagicMock(return_value="bob-token")),
        executor_identity_ctx=ctx,
    )
    agent._switch_tools_to_approver_identity("bob")
    assert ctx["approved_by"] == "bob"
    assert ctx["approver_access_token"] == "bob-token"
    assert json.loads(extra.header[AUTH_HEADER_KEY]) == {"access_token": "bob-token"}
    assert tool.metadata["approval"]["effective_executor_identity"] == "approver"
    assert tool.metadata["approval"]["approved_by"] == "bob"


def test_switch_tools_to_approver_identity_requires_authorized_approver():
    ctx = make_mcp_identity_ctx()
    ctx["approver_tools"] = {"weather"}
    agent = ChatCompletionAgent.model_construct(
        tools=[],
        executor_info={"app_code": "app", "app_secret": "secret"},
        resource_manager=MagicMock(resolve_user_access_token=MagicMock(return_value="")),
        executor_identity_ctx=ctx,
    )

    with pytest.raises(ToolException, match="正确授权"):
        agent._switch_tools_to_approver_identity("bob")


def test_switch_tools_to_approver_identity_skips_token_for_user_tools():
    ctx = make_mcp_identity_ctx()
    resolver = MagicMock()
    agent = ChatCompletionAgent.model_construct(
        tools=[],
        executor_info={"app_code": "app", "app_secret": "secret"},
        resource_manager=MagicMock(resolve_user_access_token=resolver),
        executor_identity_ctx=ctx,
    )

    agent._switch_tools_to_approver_identity("bob")

    resolver.assert_not_called()
    assert ctx["approver_access_token"] == ""


def test_switch_tools_to_approver_identity_requires_approval_operator():
    ctx = make_mcp_identity_ctx()
    ctx["approver_tools"] = {"weather"}
    agent = ChatCompletionAgent.model_construct(
        tools=[],
        executor_info={"app_code": "app", "app_secret": "secret"},
        resource_manager=MagicMock(),
        executor_identity_ctx=ctx,
    )

    with pytest.raises(ToolException, match="审批结果缺少审批人"):
        agent._switch_tools_to_approver_identity("")
