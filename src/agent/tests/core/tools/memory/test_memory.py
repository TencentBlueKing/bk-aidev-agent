import json
from unittest.mock import MagicMock

import pytest
from aidev_agent.api.bk_aidev import Client
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.tools.memory import PersonalMemoryRuntime
from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.pydantic_models import AgentExecutorKwargs
from bkapi_client_core.client import BaseClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from requests import Request, Response


@pytest.fixture
def runtime():
    manager = MagicMock()
    manager.memory_schemas.return_value = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": "Test memory tool",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }
        for name in ["memory_write", "memory_update", "memory_search"]
    ]
    manager.memory_tool.return_value = {
        "hits": [{"memory_id": "used", "text": "Use Python"}, {"memory_id": "unused", "text": "Prefer tea"}]
    }
    return PersonalMemoryRuntime(
        lambda config: {"username": "alice", "session_id": "session-1", "session_date": "2026-10-09", "messages": []},
        manager=manager,
        reference_model=MagicMock(),
    )


def messages():
    return [
        HumanMessage(content="Which language?", id="user-1"),
        ToolMessage(
            content="memory result",
            tool_call_id="call-1",
            artifact={
                "personal_memory_hits": [
                    {"memory_id": "used", "text": "Use Python"},
                    {"memory_id": "unused", "text": "Prefer tea"},
                ]
            },
        ),
        AIMessage(
            content="Use Python.", id="answer-1", additional_kwargs={"personal_memory_references": ["used", "used"]}
        ),
    ]


def test_tool_uses_host_context_and_keeps_artifact(runtime):
    tool = next(tool for tool in runtime.make_tools() if tool.name == "memory_search")
    result = tool.invoke({"type": "tool_call", "id": "call-1", "name": "memory_search", "args": {"query": "Python"}})
    assert isinstance(result, ToolMessage)
    assert len(result.artifact["personal_memory_hits"]) == 2
    args, kwargs = runtime.manager.memory_tool.call_args
    assert kwargs["username"] == "alice"
    assert args[0]["context"]["session_id"] == "session-1"
    assert args[0]["call"] == {"query": "Python"}
    assert "username" not in tool.args


def test_completed_round_counts_used_subset_only(runtime):
    runtime.complete({"messages": messages()}, {})
    payload = runtime.manager.complete_memory_round.call_args.args[0]
    assert payload["memory_ids"] == ["used"]
    assert payload["round_id"] == "answer-1"
    assert [message["role"] for message in payload["context"]["messages"]] == ["user", "assistant"]
    runtime.reference_model.invoke.assert_not_called()


def test_previous_round_artifacts_are_not_references(runtime):
    history = messages() + [HumanMessage(content="Hello", id="user-2"), AIMessage(content="Hello", id="answer-2")]
    runtime.complete({"messages": history}, {})
    assert runtime.manager.complete_memory_round.call_args.args[0]["memory_ids"] == []
    runtime.reference_model.invoke.assert_not_called()


def test_automatic_audit_does_not_count_all_hits(runtime):
    state = messages()
    state[-1].additional_kwargs = {}
    runtime.reference_model.invoke.return_value = AIMessage(content=json.dumps({"memory_ids": ["used"]}))
    runtime.complete({"messages": state}, {})
    assert runtime.manager.complete_memory_round.call_args.args[0]["memory_ids"] == ["used"]


@pytest.mark.parametrize(
    "answer",
    [
        HumanMessage(content="User input"),
        AIMessage(content="Partial"),
        AIMessage(content="", id="answer-1"),
        AIMessage(
            content="", id="answer-1", tool_calls=[{"id": "call", "name": "memory_search", "args": {"query": "x"}}]
        ),
    ],
)
def test_unfinished_round_is_not_submitted(runtime, answer):
    runtime.complete({"messages": [answer]}, {})
    runtime.manager.complete_memory_round.assert_not_called()


def test_invalid_reference_output_does_not_renew_ttl(runtime):
    state = messages()
    state[-1].additional_kwargs["personal_memory_references"] = ["foreign"]
    runtime.complete({"messages": state}, {})
    assert runtime.manager.complete_memory_round.call_args.args[0]["memory_ids"] == []


def test_runtime_context_is_resolved_per_call(runtime):
    runtime.context_provider = lambda config: {
        "username": config["configurable"]["user"],
        "session_id": "s",
        "session_date": "2026-10-09",
    }
    tool = runtime.make_tool(runtime.manager.memory_schemas.return_value[2]["function"])
    tool.invoke({"query": "x"}, config={"configurable": {"user": "bob"}})
    assert runtime.manager.memory_tool.call_args.kwargs["username"] == "bob"


class Manager(BaseResourceManager):
    def get_client(self, **kwargs):
        return self.client


def test_resource_manager_does_not_allow_header_identity_override(monkeypatch):
    manager = Manager(app_code="app", app_secret="secret")
    manager.client = MagicMock()
    monkeypatch.setattr(manager, "resolve_access_token", lambda name: "alice-token")
    manager.client.api.memory_tool.return_value = {"data": {"hits": []}}
    assert manager.memory_tool({"name": "memory_search"}, username="alice", headers={"X-BKAIDEV-USER": "bob"}) == {
        "hits": []
    }
    assert manager.client.api.memory_tool.call_args.kwargs["headers"] == {}
    manager.client.update_bkapi_authorization.assert_called_once_with(bk_username="alice", access_token="alice-token")


@pytest.mark.parametrize("method", ["memory_schemas", "memory_tool", "complete_memory_round"])
def test_memory_credentials_follow_each_call_user(monkeypatch, method):
    manager = Manager(app_code="app", app_secret="secret", username="old-user")
    manager.client = MagicMock()
    monkeypatch.setattr(manager, "resolve_access_token", lambda name: f"{name}-token")
    args = [] if method == "memory_schemas" else [{}]
    for username in ["alice", "bob"]:
        getattr(manager, method)(*args, username=username)
        manager.client.update_bkapi_authorization.assert_called_with(
            bk_username=username, access_token=f"{username}-token"
        )
    assert manager.username == "old-user"


@pytest.mark.parametrize("username", [None, "", "   "])
@pytest.mark.parametrize("method", ["memory_schemas", "memory_tool", "complete_memory_round"])
def test_memory_requires_user_before_creating_client(monkeypatch, method, username):
    manager = Manager(app_code="app", app_secret="secret")
    get_client = MagicMock()
    monkeypatch.setattr(manager, "get_client", get_client)
    args = [] if method == "memory_schemas" else [{}]
    with pytest.raises(ValueError, match="username"):
        getattr(manager, method)(*args, username=username)
    get_client.assert_not_called()


@pytest.mark.parametrize("bound_user", ["", "bob"])
def test_memory_does_not_reuse_another_users_access_token(bound_user):
    manager = Manager(app_code="app", app_secret="secret", username=bound_user, access_token="other-token")
    with pytest.raises(ValueError, match="bound"):
        manager.memory_schemas(username="alice")


def test_memory_rejects_authorization_header_override():
    manager = Manager(app_code="app", app_secret="secret")
    with pytest.raises(ValueError, match="authorization"):
        manager.memory_schemas(username="alice", headers={"x-bkapi-authorization": "foreign"})


def test_memory_clears_previous_client_token_when_current_user_has_none(monkeypatch):
    manager = Manager(app_code="app", app_secret="secret")
    manager.client = BaseClient(endpoint="https://example.com/")
    manager.client.update_bkapi_authorization(bk_app_code="app", bk_username="bob", access_token="bob-token")
    monkeypatch.setattr(manager, "resolve_access_token", lambda name: "")
    client = manager._memory_client("alice")
    prepared = Request("GET", "https://example.com/").prepare()
    client.session.auth(prepared)
    authorization = json.loads(prepared.headers["X-Bkapi-Authorization"])
    assert authorization == {"bk_app_code": "app", "bk_username": "alice"}


@pytest.mark.parametrize("username", [None, "", "   "])
def test_runtime_rejects_empty_host_user(runtime, username):
    runtime.context_provider = lambda config: {"username": username, "session_id": "s", "session_date": "2026-10-09"}
    with pytest.raises(ValueError, match="username"):
        runtime.make_tools()
    runtime.manager.memory_schemas.assert_not_called()


def test_graph_routes_successful_answer_through_memory(runtime):
    builder = ReActAgentBuilder().enable_personal_memory(runtime)
    graph, _ = builder._build_graph(
        state_schema=dict,
        callbacks=[],
        debug=False,
        checkpointer=None,
        store=None,
        interrupt_before=None,
        interrupt_after=None,
        name=None,
        cache=None,
        knowledge_node=None,
        model_node=lambda state: state,
        tool_node=None,
        pv_node=None,
        tools=None,
    )
    graph.invoke({"messages": messages()})
    runtime.manager.complete_memory_round.assert_called_once()


def test_standard_agent_options_enable_runtime(runtime):
    builder = ReActAgentBuilder().set_bkai_options(AgentExecutorKwargs(personal_memory_runtime=runtime))
    assert builder._personal_memory is runtime


@pytest.mark.parametrize(
    "method,action,http_method",
    [
        ("memory_schemas", "schemas", "GET"),
        ("memory_tool", "tool", "POST"),
        ("complete_memory_round", "complete_round", "POST"),
    ],
)
def test_sdk_memory_calls_agent_runtime_routes(monkeypatch, method, action, http_method):
    manager = Manager(app_code="app", app_secret="secret")
    manager.client = Client(endpoint="https://example.com/")
    response = Response()
    response.status_code = 200
    response._content = b'{"result": true, "data": {"ok": true}}'
    handle = MagicMock(return_value=response)
    monkeypatch.setattr(manager.client.session, "handle", handle)
    monkeypatch.setattr(manager, "resolve_access_token", lambda name: "alice-token")
    args = [] if method == "memory_schemas" else [{"context": {"session_id": "s"}}]
    assert getattr(manager, method)(*args, username="alice") == {"ok": True}
    assert handle.call_args.kwargs["url"] == f"https://example.com/openapi/aidev/agents/v1/memory/{action}/"
    assert handle.call_args.kwargs["method"] == http_method
