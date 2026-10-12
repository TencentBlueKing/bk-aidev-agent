"""The worker owns producer execution; no hidden model-execution thread."""

import threading
from unittest.mock import MagicMock

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.messages_handler import EOD_CHUNK, InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper


@pytest.fixture
def helper(monkeypatch):
    helper = GeneratorStreamingHelper(thread_id="inline", defer_cleanup_on_complete=True)
    handler = InMemoryQueueMessageHandler()
    handler.clear(helper.thread_id)
    handler.release_producer(helper.thread_id)
    monkeypatch.setattr(helper, "message_handler", handler)
    monkeypatch.setattr(helper, "_schedule_session_cleanup", MagicMock())
    monkeypatch.setattr(handler, "acquire_consumer", MagicMock())
    monkeypatch.setattr(handler, "release_producer", MagicMock())
    return helper


def test_inline_producer_owns_execution_and_releases_lock(helper):
    executing_threads = []
    complete = MagicMock()

    def source():
        executing_threads.append(threading.get_ident())
        yield 'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"message","delta":"hello"}\n\n'

    assert list(helper.stream(source(), producer_only=True, on_complete=complete, expected_run_id="run")) == []
    assert executing_threads == [threading.get_ident()]
    assert not helper.message_handler.has_active_producer(helper.thread_id)
    assert helper.message_handler.has_pending_messages(helper.thread_id)
    helper.message_handler.acquire_consumer.assert_not_called()
    complete.assert_called_once_with()
    helper.message_handler.release_producer.assert_called_once_with(helper.thread_id)


def test_failure_publishes_terminal_event_and_releases_lock(helper):
    def source():
        raise ValueError("model failed")
        yield

    assert list(helper.stream(source(), producer_only=True, expected_run_id="run")) == []
    assert not helper.message_handler.has_active_producer(helper.thread_id)
    chunks = helper.message_handler.get(helper.thread_id, timeout=1)
    assert any("RUN_ERROR" in str(chunk) for chunk in chunks)
    assert EOD_CHUNK in chunks
    helper.message_handler.acquire_consumer.assert_not_called()


@pytest.mark.parametrize("existing", ["producer", "replay", "attach"])
def test_no_duplicate_production_or_consumption(helper, existing, monkeypatch):
    source = MagicMock()
    if existing == "producer":
        monkeypatch.setattr(helper.message_handler, "acquire_producer", lambda _: False)
    elif existing == "replay":
        helper.message_handler.put(helper.thread_id, "cached")
    assert list(helper.stream(source, producer_only=True, attach_only=existing == "attach")) == []
    source.__iter__.assert_not_called()
    helper.message_handler.acquire_consumer.assert_not_called()


def test_producer_only_is_not_serialized_into_nested_execution():
    kwargs = ExecuteKwargs(producer_only=True)
    assert "producer_only" not in kwargs.model_dump()
    assert not ExecuteKwargs.model_validate(kwargs.model_dump()).producer_only


def test_inline_cancel_publishes_terminal_events(helper):
    cancel_event = threading.Event()
    cancel_event.set()
    assert (
        list(helper.stream(iter(["unused"]), producer_only=True, cancel_event=cancel_event, expected_run_id="run"))
        == []
    )
    chunks = helper.message_handler.get(helper.thread_id, timeout=1)
    assert any("RUN_FINISHED" in str(chunk) for chunk in chunks)
    assert EOD_CHUNK in chunks
    helper.message_handler.release_producer.assert_called_once_with(helper.thread_id)


def test_inline_completion_error_reaches_worker(helper):
    complete = MagicMock(side_effect=RuntimeError("session write failed"))
    with pytest.raises(RuntimeError, match="session write failed"):
        list(helper.stream(iter(()), producer_only=True, on_complete=complete, expected_run_id="run"))
    helper.message_handler.release_producer.assert_called_once_with(helper.thread_id)
    helper.message_handler.acquire_consumer.assert_not_called()


def test_remote_producer_is_registered_before_http_attaches():
    handler = MagicMock()
    handler.has_active_consumer.return_value = False
    handler.has_active_producer.return_value = True
    assert GeneratorStreamingHelper.is_registered("remote-worker", message_handler=handler)
