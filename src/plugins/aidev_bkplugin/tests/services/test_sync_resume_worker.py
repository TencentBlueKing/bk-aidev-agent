"""Synchronous resume must consume its internal stream in the worker."""

import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_bkplugin import chat_tasks
from aidev_bkplugin.services.producer_dispatch import ChatExecutionSpec


@pytest.mark.parametrize("task_entry", [False, True])
def test_sync_resume_returns_answer_with_one_producer_lock(monkeypatch, settings, task_entry):
    backend = InMemoryQueueMessageHandler()
    session = "sync-resume-regression"
    backend.clear(session)
    locked = False
    lock_calls = []
    producer_threads = []

    def acquire(thread_id):
        nonlocal locked
        lock_calls.append("acquire")
        if locked:
            return False
        locked = True
        return True

    def release(thread_id):
        nonlocal locked
        lock_calls.append("release")
        locked = False

    monkeypatch.setattr(backend, "acquire_producer", acquire)
    monkeypatch.setattr(backend, "release_producer", release)
    monkeypatch.setattr(chat_tasks.message_handler_factory, "get", lambda: backend)
    monkeypatch.setattr(GeneratorStreamingHelper, "_schedule_session_cleanup", Mock())
    monkeypatch.setattr(chat_tasks, "close_old_connections", Mock())
    monkeypatch.setattr(chat_tasks.agent_settings, "APP_CODE", "test-app")
    replies = Mock()
    monkeypatch.setattr(chat_tasks, "send_chat_reply", replies)
    resources = SimpleNamespace(event_publishing_enabled=lambda: True)
    settings.BKAI_CHAT_RESOURCE_MANAGER_FACTORY = Mock(return_value=resources)
    agent = SimpleNamespace(resource_manager=resources, model_name="test-model", event_handler=None, chat_history=[{}])

    def produce():
        producer_threads.append(threading.get_ident())
        yield "data: " + json.dumps({"type": "TEXT_MESSAGE_CONTENT", "messageId": "answer", "delta": "resumed answer"})
        yield "data: " + json.dumps(
            {"type": "RUN_FINISHED", "threadId": session, "runId": "resume-run", "outcome": {"type": "success"}}
        )

    def stream(*args):
        helper = GeneratorStreamingHelper(
            backend, thread_id=session, resource_manager=agent.resource_manager, defer_cleanup_on_complete=True
        )
        return helper.stream(produce(), expected_run_id="resume-run")

    agent._stream = stream
    agent.execute = lambda kwargs: ChatCompletionAgent._invoke_resume_with_events(
        agent, None, {"configurable": {}}, {}, [], kwargs
    )
    manager = Mock()
    builder = SimpleNamespace(by_session_code=Mock(return_value=agent), session_manager=manager)
    monkeypatch.setattr(chat_tasks, "AgentBuilder", Mock(return_value=builder))
    spec = ChatExecutionSpec(
        app_code="test-app",
        tenant_id="test-tenant",
        username="alice",
        agent_code="test-agent",
        session_code=session,
        execute_kwargs={"stream": False, "resume": [{"interruptId": "question", "payload": "answer"}]},
    )
    try:
        if task_entry:
            chat_tasks.run_chat_producer("task-id", spec.model_dump(mode="json"), time.time() + 30)
            result = replies.call_args.kwargs["result"]
        else:
            result = chat_tasks.execute_chat_producer(spec, "task-id", time.time() + 30)
        assert result["choices"][0]["delta"]["content"] == "resumed answer"
        assert result["outcome"] == {"type": "success"}
        assert lock_calls == ["acquire", "release"]
        assert producer_threads == [threading.get_ident()]
        manager.save_ai_response.assert_not_called()
    finally:
        backend.clear(session)
