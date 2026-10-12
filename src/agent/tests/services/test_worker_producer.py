"""A worker must not return while its stream producer is still executing."""

import threading
from unittest.mock import MagicMock

import pytest
from aidev_agent.services.messages_handler.producer_execution import get_producer_started, worker_producer
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper


def test_worker_context_is_scoped_and_reset():
    started = MagicMock()
    with pytest.raises(RuntimeError), worker_producer("session", started):
        assert get_producer_started("session") is started
        assert get_producer_started("subagent") is None
        raise RuntimeError("failure")
    assert get_producer_started("session") is None


def test_worker_runs_producer_on_caller_thread(monkeypatch):
    helper = GeneratorStreamingHelper(thread_id="session")
    handler = MagicMock()
    handler.is_stopped.return_value = False
    handler.has_pending_messages.return_value = False
    handler.check_cancel_signal.return_value = False
    handler.acquire_producer.return_value = True
    monkeypatch.setattr(helper, "message_handler", handler)
    producer_threads = []
    monkeypatch.setattr(helper, "_run_producer", lambda **kwargs: producer_threads.append(threading.get_ident()))
    started = MagicMock()
    with worker_producer("session", started):
        assert list(helper.stream(iter(()), expected_run_id="run")) == []
    assert producer_threads == [threading.get_ident()]
    started.assert_called_once_with()
    handler.acquire_consumer.assert_not_called()


def test_worker_does_not_consume_existing_replay(monkeypatch):
    helper = GeneratorStreamingHelper(thread_id="session")
    handler = MagicMock()
    handler.is_stopped.return_value = False
    handler.has_pending_messages.return_value = True
    monkeypatch.setattr(helper, "message_handler", handler)
    producer = MagicMock()
    monkeypatch.setattr(helper, "_run_producer", producer)
    with worker_producer("session", lambda: None):
        assert list(helper.stream(iter(()))) == []
    producer.assert_not_called()
    handler.acquire_consumer.assert_not_called()
