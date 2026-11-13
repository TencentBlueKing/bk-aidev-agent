"""Producer execution stays owned by the worker until finalization."""

import threading
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.packages.resource_manager.agent import AgentResourceManager
from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.producer import resolve_producer_runner, run_producer_inline
from typing_extensions import get_protocol_members


class InlineResources:
    def get_producer_runner(self):
        return run_producer_inline


class LegacyResources:
    """既有鸭子类型实现，无需新增 producer 方法。"""

    def get_client(self):
        return "existing-client"


@pytest.fixture
def helper(monkeypatch):
    handler = InMemoryQueueMessageHandler()
    instance = GeneratorStreamingHelper(handler, thread_id="runner-test", resource_manager=InlineResources())
    handler.clear(instance.thread_id)
    monkeypatch.setattr(instance, "_schedule_session_cleanup", Mock())
    yield instance
    handler.clear(instance.thread_id)


@pytest.mark.parametrize("inline", [True, False])
def test_runner_preserves_context_and_execution_owner(helper, monkeypatch, inline):
    marker = ContextVar("producer-marker", default="missing")
    token = marker.set("request")
    seen = []
    helper = GeneratorStreamingHelper(
        helper.message_handler,
        thread_id=helper.thread_id,
        resource_manager=InlineResources() if inline else LegacyResources(),
    )
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
    helper._producer_runner = Mock(side_effect=RuntimeError("submission failed"))
    with pytest.raises(RuntimeError, match="submission failed"):
        list(helper.stream(iter([])))
    assert not helper.message_handler.has_active_producer(helper.thread_id)


def test_inline_finalization_failure_reaches_worker(helper, monkeypatch):
    monkeypatch.setattr(helper.message_handler, "flush", Mock(side_effect=RuntimeError("flush failed")))
    with pytest.raises(RuntimeError, match="flush failed"):
        list(helper.stream(iter(["chunk"])))
    assert not helper.message_handler.has_active_producer(helper.thread_id)


def test_existing_producer_does_not_run_callback(helper, monkeypatch):
    helper._producer_runner = Mock()
    monkeypatch.setattr(helper.message_handler, "acquire_producer", Mock(return_value=False))
    try:
        _, resuming, _ = helper._start_or_resume_stream(iter([]), threading.Event(), False)
        assert resuming
        helper._producer_runner.assert_not_called()
    finally:
        helper.message_handler.release_producer(helper.thread_id)


def test_attach_does_not_start_inline_producer(helper):
    helper._producer_runner = Mock()
    _, resuming, _ = helper._start_or_resume_stream(iter([]), threading.Event(), True, attach_only=True)
    assert resuming
    helper._producer_runner.assert_not_called()


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


@pytest.mark.parametrize("manager", [None, LegacyResources(), SimpleNamespace(), Mock(), AgentResourceManager()])
def test_legacy_and_default_resources_keep_thread_execution(manager):
    assert resolve_producer_runner(manager) is None


def test_custom_resource_execution_is_optional():
    assert resolve_producer_runner(InlineResources()) is run_producer_inline
    assert "get_producer_runner" not in get_protocol_members(ResourceManagerProtocol)


def test_helper_uses_resource_manager_policy(helper):
    assert helper._producer_runner is run_producer_inline
