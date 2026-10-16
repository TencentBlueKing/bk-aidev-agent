import json
from unittest.mock import MagicMock

import pytest
from aidev_agent.packages.resource_manager import AgentResourceManager, PrivateResourceManager, resource_manager
from aidev_agent.services.agent.memory import automatic_personal_memory
from langchain_core.messages import AIMessage, HumanMessage
from requests import Request, Response

METHODS = [
    ("memory_schemas", "schemas", "GET"),
    ("memory_tool", "tool", "POST"),
    ("complete_memory_round", "complete_round", "POST"),
]


@pytest.fixture
def manager():
    return PrivateResourceManager(
        endpoint="https://example.com/stage/", access_token="alice-token", username="alice", agent_code="agent-a"
    )


@pytest.fixture
def transport(manager, monkeypatch):
    client = manager.get_client()
    response = Response()
    response.status_code = 200
    response._content = b'{"result": true, "data": {"ok": true}}'
    handle = MagicMock(return_value=response)
    monkeypatch.setattr(client.session, "handle", handle)
    monkeypatch.setattr(manager, "get_client", lambda: client)
    return handle, client


@pytest.mark.parametrize("method,action,http_method", METHODS)
def test_private_memory_uses_oauth_and_private_routes(manager, transport, method, action, http_method):
    handle, client = transport
    options = {"username": "alice", "timeout": 2, "headers": {"X-BKAIDEV-USER": "mallory"}}
    if method == "memory_schemas":
        result = manager.memory_schemas(agent_code="agent-a", **options)
    else:
        result = getattr(manager, method)({"agent_code": "agent-a", "memory_epoch": 3}, **options)
    assert result == {"ok": True}
    assert handle.call_args.kwargs["url"] == f"https://example.com/stage/openapi/aidev/private/v1/memory/{action}/"
    assert handle.call_args.kwargs["method"] == http_method
    assert handle.call_args.kwargs["timeout"] == 2
    assert "X-BKAIDEV-USER" not in handle.call_args.kwargs["headers"]
    prepared = Request("GET", "https://example.com/").prepare()
    client.session.auth(prepared)
    assert json.loads(prepared.headers["X-Bkapi-Authorization"]) == {"access_token": "alice-token"}


@pytest.mark.parametrize("field", ["endpoint", "access_token", "username", "agent_code"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_private_manager_requires_bound_identity(field, value):
    options = {"endpoint": "https://example.com/", "access_token": "token", "username": "alice", "agent_code": "a"}
    options[field] = value
    with pytest.raises(ValueError):
        PrivateResourceManager(**options)


@pytest.mark.parametrize("method,action,http_method", METHODS)
@pytest.mark.parametrize("field,value", [("username", "bob"), ("agent_code", "agent-b")])
def test_private_identity_cannot_change_between_calls(manager, transport, method, action, http_method, field, value):
    identity = {"username": "alice", "agent_code": "agent-a", field: value}
    with pytest.raises(ValueError, match="bound"):
        if method == "memory_schemas":
            manager.memory_schemas(**identity)
        else:
            getattr(manager, method)({"agent_code": identity["agent_code"]}, username=identity["username"])
    transport[0].assert_not_called()


def test_private_memory_rejects_auth_override_and_does_not_replace_agent_default(manager, transport):
    with pytest.raises(ValueError, match="authorization"):
        manager.memory_schemas(username="alice", agent_code="agent-a", headers={"x-bkapi-authorization": "other"})
    transport[0].assert_not_called()
    assert manager.get_agent_code() == "agent-a"
    assert isinstance(resource_manager(), AgentResourceManager)


def test_private_clients_never_reuse_another_users_session(manager):
    second = PrivateResourceManager(
        endpoint=manager.endpoint, access_token="bob-token", username="bob", agent_code=manager.agent_code
    )
    alice, bob = manager.get_client(), second.get_client()
    assert alice.session is not bob.session
    for client, expected in [(alice, "alice-token"), (bob, "bob-token")]:
        request = Request("GET", manager.endpoint).prepare()
        client.session.auth(request)
        assert json.loads(request.headers["X-Bkapi-Authorization"]) == {"access_token": expected}


@pytest.fixture
def policy():
    schemas = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": name,
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            },
        }
        for name in ["memory_write", "memory_update", "memory_search"]
    ]
    return {"enabled": True, "agent_code": "agent-a", "memory_epoch": 7, "enabled_at": None, "schemas": schemas}


def test_cli_runtime_discovers_tools_and_submits_completion_over_private(manager, transport, policy):
    handle, _ = transport
    handle.return_value._content = json.dumps({"result": True, "data": policy}).encode()
    user = HumanMessage(content="Use Python", id="u")
    runtime = automatic_personal_memory(manager, "alice", "s", [], [user], agent_code="agent-a")
    assert runtime is not None and len(runtime.make_tools()) == 3
    handle.return_value._content = b'{"result": true, "data": {"hits": []}}'
    runtime.make_tools()[2].invoke({"query": "Python"})
    tool_payload = handle.call_args.kwargs["json"]
    assert tool_payload["agent_code"] == "agent-a" and tool_payload["memory_epoch"] == 7
    handle.return_value._content = b'{"result": true, "data": {"job_id": 1}}'
    runtime.complete({"messages": [user, AIMessage(content="Answer", id="a")]}, {})
    assert handle.call_args.kwargs["url"].endswith("/private/v1/memory/complete_round/")
    assert handle.call_args.kwargs["json"]["memory_epoch"] == 7


@pytest.mark.parametrize("enabled", [False, True])
def test_cli_runtime_skips_disabled_policy_and_preserves_chat_on_http_failure(manager, transport, policy, enabled):
    handle, _ = transport
    policy["enabled"] = enabled
    handle.return_value._content = json.dumps({"result": True, "data": policy}).encode()
    if enabled:
        handle.side_effect = ConnectionError("unavailable")
    assert automatic_personal_memory(manager, "alice", "s", [], [], agent_code="agent-a") is None
