import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.events import AIDEV_CHAT_RESUME_FAILED, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_READY
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.services.resume_events import ResumeEvents, resume_events_for


@pytest.fixture
def resume_case():
    published = []
    manager = SimpleNamespace(get_agent_code=lambda: "app", publish_event=published.append)
    observer = ResumeEvents(
        manager, session_code="session", thread_id="graph", turn_id="turn", resume=[{"interruptId": "approval"}]
    )
    events = [
        {"type": "MESSAGES_SNAPSHOT", "messages": [{"content": "private history"}]},
        {"type": "RUN_STARTED", "runId": "run", "threadId": "graph"},
        {"type": "TEXT_MESSAGE_CONTENT", "messageId": "answer", "delta": "审批后"},
        {"type": "TEXT_MESSAGE_CONTENT", "messageId": "answer", "delta": "继续"},
        {"type": "RUN_FINISHED", "runId": "run", "threadId": "graph"},
    ]
    chunks = ["data: " + json.dumps(event, separators=(",", ":")) + "\n\n" for event in events]
    return SimpleNamespace(observer=observer, manager=manager, events=events, chunks=chunks, published=published)


def test_ready_occurs_after_queue_flush_and_terminal_after_persistence(resume_case):
    case = resume_case
    handler = InMemoryQueueMessageHandler()
    original_flush = handler.flush
    handler.flush = Mock(side_effect=original_flush)
    completed = []

    def publish(event):
        assert handler.flush.called
        assert event.name == AIDEV_CHAT_RESUME_READY or completed
        case.published.append(event)

    case.manager.publish_event = publish
    helper = GeneratorStreamingHelper(handler, "graph", producer_observer=case.observer)
    output = list(helper.stream(iter(case.chunks), on_complete=lambda: completed.append(True), expected_run_id="run"))
    assert all(chunk in output for chunk in case.chunks)
    assert [event.name for event in case.published] == [AIDEV_CHAT_RESUME_READY, AIDEV_CHAT_RESUME_FINISHED]
    assert case.published[-1].value["events"][1]["delta"] == "审批后继续"
    assert "private history" not in json.dumps(case.published[-1].value)


@pytest.mark.parametrize("error", [None, RuntimeError("private exception")])
def test_completion_is_once_and_preserves_exact_original_identity(resume_case, error):
    case = resume_case
    for chunk in case.chunks:
        case.observer.on_chunk(chunk)
    case.observer.on_complete(error)
    case.observer.on_complete(error)
    assert len(case.published) == 2
    final = case.published[-1]
    assert final.name == (AIDEV_CHAT_RESUME_FAILED if error else AIDEV_CHAT_RESUME_FINISHED)
    assert final.value["sessionCode"] == "session" and final.value["turnId"] == "turn"
    assert final.value["threadId"] == "graph" and final.value["interruptIds"] == ["approval"]
    assert "private exception" not in final.model_dump_json()


def test_terminal_replay_and_old_interrupt_close_are_not_new_resume(resume_case):
    case = resume_case
    case.observer.on_chunk('data: {"type":"RUN_FINISHED","resume_replay":true}')
    case.observer.on_complete()
    assert case.published == []
    case.observer.enabled = False
    for chunk in case.chunks:
        case.observer.on_chunk(chunk)
    case.observer.on_complete()
    assert case.published == []


def test_failed_ready_publish_retries_same_event_after_producer_finishes(resume_case):
    case = resume_case
    publish = Mock(side_effect=[RuntimeError("DB unavailable"), None, None])
    case.manager.publish_event = publish
    for chunk in case.chunks:
        case.observer.on_chunk(chunk)
    case.observer.on_complete()
    assert publish.call_count == 3
    assert publish.call_args_list[0].args[0] is publish.call_args_list[1].args[0]


@pytest.mark.parametrize("manager", [None, object(), SimpleNamespace(event_publishing_enabled=lambda: False)])
def test_legacy_resource_manager_is_compatible(manager):
    assert resume_events_for(manager, session_code="session", resume=[{"interruptId": "i"}]) is None


def test_missing_runtime_terminal_is_included_in_durable_result(resume_case):
    case = resume_case
    helper = GeneratorStreamingHelper(InMemoryQueueMessageHandler(), "graph", producer_observer=case.observer)
    list(helper.stream(iter(case.chunks[:-1]), expected_run_id="run"))
    assert case.published[-1].value["events"][-1]["type"] == "RUN_FINISHED"
