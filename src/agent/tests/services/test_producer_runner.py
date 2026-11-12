"""Producer execution stays owned by the worker until finalization."""

import threading
from contextvars import ContextVar
from unittest.mock import Mock

import pytest
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.producer import run_producer_inline


@pytest.fixture
def helper(monkeypatch):
    handler = InMemoryQueueMessageHandler()
    instance = GeneratorStreamingHelper(handler, thread_id="runner-test", producer_runner=run_producer_inline)
    handler.clear(instance.thread_id)
    monkeypatch.setattr(instance, "_schedule_session_cleanup", Mock())
    yield instance
    handler.clear(instance.thread_id)


@pytest.mark.parametrize("inline", [True, False])
def test_runner_preserves_context_and_execution_owner(helper, monkeypatch, inline):
    marker = ContextVar("producer-marker", default="missing")
    token = marker.set("request")
    seen = []
    helper.producer_runner = run_producer_inline if inline else None
    monkeypatch.setattr(helper, "_producer", lambda **kw: seen.append((threading.get_ident(), marker.get())))
    try:
        worker, _, _ = helper._start_or_resume_stream(iter([]), threading.Event(), False)
        if worker is not None:
            worker.join(timeout=2)
        assert seen == [(threading.get_ident() if inline else worker.ident, "request")]
    finally:
        marker.reset(token)
        helper.message_handler.release_producer(helper.thread_id)


def test_inline_waits_for_finalization_and_releases_lock(helper):
    completed = []
    output = list(helper.stream(iter(["chunk"]), on_complete=lambda: completed.append("finished")))
    assert "chunk" in output
    assert completed == ["finished"]
    assert not helper.message_handler.has_active_producer(helper.thread_id)


def test_runner_submission_failure_releases_lock(helper):
    helper.producer_runner = Mock(side_effect=RuntimeError("submission failed"))
    with pytest.raises(RuntimeError, match="submission failed"):
        list(helper.stream(iter([])))
    assert not helper.message_handler.has_active_producer(helper.thread_id)


def test_inline_finalization_failure_reaches_worker(helper, monkeypatch):
    monkeypatch.setattr(helper.message_handler, "flush", Mock(side_effect=RuntimeError("flush failed")))
    with pytest.raises(RuntimeError, match="flush failed"):
        list(helper.stream(iter(["chunk"])))
    assert not helper.message_handler.has_active_producer(helper.thread_id)


def test_existing_producer_does_not_run_callback(helper, monkeypatch):
    helper.producer_runner = Mock()
    monkeypatch.setattr(helper.message_handler, "acquire_producer", Mock(return_value=False))
    try:
        _, resuming, _ = helper._start_or_resume_stream(iter([]), threading.Event(), False)
        assert resuming
        helper.producer_runner.assert_not_called()
    finally:
        helper.message_handler.release_producer(helper.thread_id)


def test_attach_does_not_start_inline_producer(helper):
    helper.producer_runner = Mock()
    _, resuming, _ = helper._start_or_resume_stream(iter([]), threading.Event(), True, attach_only=True)
    assert resuming
    helper.producer_runner.assert_not_called()


def test_inline_cancelled_run_never_iterates_business_generator(helper):
    cancel = threading.Event()
    cancel.set()
    generated = Mock()

    def producer():
        generated()
        yield "business chunk"

    output = list(helper.stream(producer(), cancel_event=cancel, expected_run_id="cancelled-run"))
    generated.assert_not_called()
    assert "business chunk" not in output
    assert not helper.message_handler.has_active_producer(helper.thread_id)
