"""HTTP Chat keeps SSE while delegating construction exclusively to the worker."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_bkplugin.services.agent_builder import AgentBuilder
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_bkplugin.views import chat


@pytest.fixture
def remote_view(monkeypatch):
    resources = Mock(app_code="test-app", tenant_id="tenant")
    resources.get_agent_code.return_value = "agent"
    manager = Mock()
    manager.prepare_chat_history.return_value = ("session", "saved-turn")
    monkeypatch.setattr(chat, "SessionManager", Mock(return_value=manager))
    builder = Mock(side_effect=AssertionError("Web must not build an Agent"))
    monkeypatch.setattr(AgentBuilder, "__init__", builder)
    dispatcher = Mock()
    monkeypatch.setattr(chat, "ChatDispatcher", Mock(return_value=dispatcher))
    monkeypatch.setattr(chat.AgentHelper, "get_authorize_prompt", Mock(return_value=None))
    view = chat.ChatCompletionViewSet()
    view.get_username = Mock(return_value="alice")
    view.get_resource_manager = Mock(return_value=resources)
    view._resolve_chat_turn_id = Mock(return_value="turn")
    view.streaming_response = Mock(side_effect=lambda output, **kw: SimpleNamespace(streaming=True, output=output))
    return SimpleNamespace(view=view, dispatcher=dispatcher, manager=manager, builder=builder, resources=resources)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("removed_flag", [None, False])
def test_create_dispatches_sync_and_resume_without_build(
    remote_view, monkeypatch, settings, stream, resume, removed_flag
):
    if removed_flag is not None:
        settings.BKAI_CHAT_CELERY_ENABLED = removed_flag
    ek = ExecuteKwargs(stream=stream, resume=[{"interruptId": "q", "payload": "answer"}] if resume else None)
    data = dict(
        execute_kwargs=ek,
        session_code="session",
        thread_id="",
        input="" if resume else "hello",
        chat_history=[],
        agent_type="chat",
    )
    serializer = Mock(validated_data=data)
    monkeypatch.setattr(chat, "ChatCompletionRequestSerializer", Mock(return_value=serializer))
    expected = iter(["data: event\n\n"]) if stream else {"answer": "done"}
    remote_view.dispatcher.execute.return_value = expected
    response = remote_view.view.create(SimpleNamespace(data={}, user=SimpleNamespace(username="alice")))
    assert (response.output if stream else response.data) is expected
    assert remote_view.dispatcher.execute.call_args.args[0].resume == ek.resume
    remote_view.builder.assert_not_called()


def test_attach_skips_build_history_and_turn_mutations(remote_view):
    ek = ExecuteKwargs(stream=True, stream_mode="attach")
    data = dict(execute_kwargs=ek, thread_id="", input="", chat_history=[])
    remote_view.view._dispatch_chat(data, "alice", remote_view.resources, "session", "")
    remote_view.manager.prepare_chat_history.assert_not_called()
    remote_view.view._resolve_chat_turn_id.assert_not_called()
    remote_view.builder.assert_not_called()


def test_supplied_history_is_persisted_before_dispatch_not_serialized(remote_view):
    ek = ExecuteKwargs(stream=True)
    data = dict(execute_kwargs=ek, thread_id="thread", input="new", chat_history=[{"role": "user", "content": "old"}])
    remote_view.view._dispatch_chat(data, "alice", remote_view.resources, "", "")
    history = remote_view.manager.prepare_chat_history.call_args.args[1]
    assert [prompt.content for prompt in history] == ["old", "new"]
    assert ek.input == "" and ek.session_code == "session" and ek.turn_id == "saved-turn"
    spec = chat.ChatDispatcher.call_args.args[0]
    assert "chat_history" not in spec.model_dump()
    remote_view.builder.assert_not_called()


@pytest.mark.parametrize("last_role", ["user", "assistant"])
def test_prepare_history_preserves_turn_and_persists_once(last_role):
    manager = Mock()
    manager.get_or_create_by_thread_id.return_value = "session"
    manager.save_content.return_value = {"property": {"turn_id": "saved"}}
    history = [ChatPrompt(role="system", content="context"), ChatPrompt(role=last_role, content="last")]
    session, turn = SessionManager.prepare_chat_history(manager, "thread", history, turn_id="original")
    assert session == "session"
    manager.save_chat_history.assert_called_once_with("session", history[:-1] if last_role == "user" else history)
    assert turn == ("saved" if last_role == "user" else "original")
    assert manager.save_content.call_count == (1 if last_role == "user" else 0)


def test_attach_authorization_failure_never_consumes_stream(remote_view):
    remote_view.resources.retrieve_chat_session.side_effect = PermissionError("forbidden")
    data = dict(execute_kwargs=ExecuteKwargs(stream=True, stream_mode="attach"))
    with pytest.raises(PermissionError):
        remote_view.view._dispatch_chat(data, "alice", remote_view.resources, "session", "")
    remote_view.resources.retrieve_chat_session.assert_called_once_with("session", headers={"X-BKAIDEV-USER": "alice"})
    remote_view.dispatcher.execute.assert_not_called()
    remote_view.builder.assert_not_called()


def test_attach_does_not_create_session_even_with_persist_input(remote_view, monkeypatch):
    ek = ExecuteKwargs(stream=True, stream_mode="attach", persist_input=True)
    data = dict(execute_kwargs=ek, session_code="session", thread_id="", input="", chat_history=[], agent_type="chat")
    monkeypatch.setattr(chat, "ChatCompletionRequestSerializer", Mock(return_value=Mock(validated_data=data)))
    remote_view.view.create(SimpleNamespace(data={}, user=SimpleNamespace(username="alice")))
    remote_view.manager.get_or_create_by_session_code.assert_not_called()
    remote_view.manager.prepare_chat_history.assert_not_called()
    remote_view.builder.assert_not_called()


@pytest.mark.parametrize("stream", [False, True])
def test_dispatch_failure_never_falls_back_to_web(remote_view, monkeypatch, stream):
    data = dict(
        execute_kwargs=ExecuteKwargs(stream=stream),
        session_code="",
        thread_id="thread",
        input="hello",
        chat_history=[],
        agent_type="chat",
    )
    monkeypatch.setattr(chat, "ChatCompletionRequestSerializer", Mock(return_value=Mock(validated_data=data)))
    remote_view.dispatcher.execute.side_effect = RuntimeError("broker unavailable")
    with pytest.raises(Exception, match="broker unavailable"):
        remote_view.view.create(SimpleNamespace(data={}, user=SimpleNamespace(username="alice")))
    remote_view.dispatcher.execute.assert_called_once()
    remote_view.builder.assert_not_called()
    remote_view.view.streaming_response.assert_not_called()


def test_flow_uses_existing_entry_without_chat_dispatch(remote_view, monkeypatch):
    data = dict(
        execute_kwargs=ExecuteKwargs(stream=True),
        session_code="session",
        thread_id="",
        input="hello",
        chat_history=[],
        agent_type="flow",
    )
    monkeypatch.setattr(chat, "ChatCompletionRequestSerializer", Mock(return_value=Mock(validated_data=data)))
    remote_view.view._save_user_input = Mock(return_value="turn")
    remote_view.view._handle_flow_agent = Mock(return_value="flow-response")
    response = remote_view.view.create(SimpleNamespace(data={}, user=SimpleNamespace(username="alice")))
    assert response == "flow-response"
    remote_view.view._handle_flow_agent.assert_called_once()
    remote_view.dispatcher.execute.assert_not_called()
    remote_view.builder.assert_not_called()
