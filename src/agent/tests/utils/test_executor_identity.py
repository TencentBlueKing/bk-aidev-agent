# -*- coding: utf-8 -*-
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.tools import ToolException
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

from aidev_agent.api.constants import AUTHORIZATION_HEADER
from aidev_agent.packages.interrupt_manager.approval import ApprovalStateHandler
from aidev_agent.packages.langchain_core.tools.base import ApiWrapper
from aidev_agent.packages.resource_manager.base import _mcp_approver_identity_interceptor, _mcp_tool_interceptors
from aidev_agent.utils import executor_identity
from aidev_agent.utils.executor_identity import ApproverIdentity, approver_identity_scope

CALLER_AUTH = json.dumps({"access_token": "caller-token"})
BOB = ApproverIdentity(approved_by="bob", tool_call_id="call_1")


@pytest.fixture
def bkoauth_tokens(monkeypatch):
    tokens = {"bob": "bob-token"}
    fake = SimpleNamespace(get_access_token_by_user=lambda username: SimpleNamespace(access_token=tokens.get(username)))
    monkeypatch.setattr(executor_identity, "bkoauth", fake)
    return tokens


def _api_wrapper() -> ApiWrapper:
    wrapper = ApiWrapper("get", "https://apigw.example/api", header={AUTHORIZATION_HEADER: CALLER_AUTH})
    wrapper.session = MagicMock()
    wrapper.session.request.return_value = MagicMock(headers={"content-type": "application/json"})
    return wrapper


def _sent_auth(wrapper: ApiWrapper) -> str:
    return wrapper.session.request.call_args.kwargs["headers"][AUTHORIZATION_HEADER]


def test_resume_value_carries_approved_by(monkeypatch):
    record = {
        "tool_call_id": "call_1",
        "approve_result": "approved",
        "approved_by": "bob",
        "content": {"outcome": {"type": "success", "interrupts": [{"id": "int-1", "toolCallId": "call_1"}]}},
    }
    monkeypatch.setattr(ApprovalStateHandler, "_list_interrupt_records", lambda self, session_code: [record])

    info = ApprovalStateHandler().query_approval_info_for_interrupt("s1", {"toolCallId": "call_1"})
    assert info["interrupts"][0]["payload"]["approvedBy"] == "bob"

    record.pop("approved_by")
    record["content"]["outcome"]["interrupts"] = [{"id": "int-1", "toolCallId": "call_1"}]
    info = ApprovalStateHandler().query_approval_info_for_interrupt("s1", {"toolCallId": "call_1"})
    assert "payload" not in info["interrupts"][0]


def test_http_tool_uses_approver_token_only_within_scope(bkoauth_tokens):
    wrapper = _api_wrapper()

    with approver_identity_scope(BOB):
        wrapper()
    assert json.loads(_sent_auth(wrapper)) == {"access_token": "bob-token"}

    wrapper()
    assert _sent_auth(wrapper) == CALLER_AUTH


def test_missing_approver_token_raises_before_request(bkoauth_tokens):
    bkoauth_tokens.pop("bob")
    wrapper = _api_wrapper()

    with approver_identity_scope(BOB), pytest.raises(ToolException, match="Agent SaaS"):
        wrapper()
    wrapper.session.request.assert_not_called()


def test_only_token_not_exist_is_reported_as_unauthorized(monkeypatch):
    class FakeTokenNotExist(Exception):
        pass

    def get_token(username):
        raise FakeTokenNotExist() if username == "bob" else ConnectionError("timeout")

    monkeypatch.setattr(executor_identity, "TokenNotExist", FakeTokenNotExist)
    monkeypatch.setattr(executor_identity, "bkoauth", SimpleNamespace(get_access_token_by_user=get_token))

    with approver_identity_scope(BOB), pytest.raises(ToolException, match="Agent SaaS"):
        executor_identity.approver_authorization("http", "tool")
    with approver_identity_scope(ApproverIdentity("carol", "call_2")), pytest.raises(ConnectionError):
        executor_identity.approver_authorization("http", "tool")


def test_mcp_interceptor_uses_approver_token_and_nested_user_scope_clears_it(bkoauth_tokens):
    received: list[MCPToolCallRequest] = []

    async def handler(request):
        received.append(request)

    request = MCPToolCallRequest(name="query", args={}, server_name="bk-mcp", headers=None, runtime=None)

    async def run():
        with approver_identity_scope(BOB):
            await _mcp_approver_identity_interceptor(request, handler)
            with approver_identity_scope(None):
                await _mcp_approver_identity_interceptor(request, handler)

    asyncio.run(run())

    assert json.loads(received[0].headers[AUTHORIZATION_HEADER]) == {"access_token": "bob-token"}
    assert received[1].headers is None


def test_mcp_approver_interceptor_only_mounted_for_apigw_server():
    assert _mcp_approver_identity_interceptor in _mcp_tool_interceptors(
        {"headers": {AUTHORIZATION_HEADER: CALLER_AUTH}}
    )
    assert _mcp_approver_identity_interceptor not in _mcp_tool_interceptors({"headers": {"Authorization": "Bearer x"}})
    assert _mcp_approver_identity_interceptor not in _mcp_tool_interceptors({})
