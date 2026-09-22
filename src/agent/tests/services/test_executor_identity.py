# -*- coding: utf-8 -*-
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def test_apply_http_approver_identity_rewrites_auth_header_without_access_token():
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
    )

    auth = json.loads(extra.header[AUTH_HEADER_KEY])
    assert auth == {"bk_app_code": "app", "bk_app_secret": "secret", "bk_username": "bob"}
    assert "access_token" not in auth
    assert json.loads(skipped.func._extra.header[AUTH_HEADER_KEY]) == {"access_token": "keep"}


def test_mcp_interceptor_overrides_headers_only_for_approver_tools():
    ctx = make_mcp_identity_ctx()
    ctx["approver_tools"] = {"echo"}
    ctx["approved_by"] = "bob"
    interceptor = make_mcp_approver_interceptor(ctx, {"app_code": "app", "app_secret": "secret"})

    async def handler(request):
        return request

    echoed = asyncio.run(
        interceptor(MCPToolCallRequest(name="echo", args={}, server_name="srv", headers=None), handler)
    )
    skipped = asyncio.run(
        interceptor(MCPToolCallRequest(name="other", args={}, server_name="srv", headers=None), handler)
    )

    assert json.loads(echoed.headers[AUTH_HEADER_KEY]) == {
        "bk_app_code": "app",
        "bk_app_secret": "secret",
        "bk_username": "bob",
    }
    assert skipped.headers is None


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
        executor_identity_ctx=ctx,
    )
    agent._switch_tools_to_approver_identity("bob")
    assert ctx["approved_by"] == "bob"
    assert json.loads(extra.header[AUTH_HEADER_KEY])["bk_username"] == "bob"
