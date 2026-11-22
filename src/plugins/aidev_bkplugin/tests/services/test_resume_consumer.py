"""Channel consumption cannot abandon the session writer's stream."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from aidev_agent.services.messages_handler import EOD_CHUNK, GeneratorStreamingHelper, InMemoryQueueMessageHandler
from aidev_bkplugin.services.agent_execution import AgentExecutor


@pytest.mark.parametrize("fails", [False, True])
def test_consumer_partial_read_always_drains_remaining_output(monkeypatch, fails):
    saved = []

    def source():
        yield "first"
        yield "last"
        saved.append(True)

    def consume(output):
        assert next(output) == "first"
        if fails:
            raise RuntimeError("channel failed")

    monkeypatch.setattr(AgentExecutor, "execute_with_save", lambda *_args, **_kwargs: source())
    kwargs = SimpleNamespace(stream=True)
    arguments = (MagicMock(), kwargs, "session-1", MagicMock())
    if fails:
        with pytest.raises(RuntimeError, match="channel failed"):
            AgentExecutor.run_agent_to_completion(*arguments, consume_stream=consume)
    else:
        AgentExecutor.run_agent_to_completion(*arguments, consume_stream=consume)
    assert saved == [True]
    assert kwargs.background_only is True


def test_attach_after_producer_finished_drains_cached_stream_without_restarting_writer():
    session = "finished-session"
    backend = InMemoryQueueMessageHandler()
    backend.put(session, "cached event")
    backend.put(session, EOD_CHUNK)
    statuses = ["finished"]
    writer = MagicMock(spec=BaseSessionWriter)
    writer.set_streaming_started.side_effect = lambda: statuses.append("running")
    agent = MagicMock(event_handler=writer)
    options = ExecuteKwargs(stream=True, stream_mode="attach")
    helper = GeneratorStreamingHelper(backend, thread_id=session)
    agent.execute.return_value = helper.stream(iter(["new event"]), event_handler=writer, attach_only=True)
    received = []

    AgentExecutor.run_agent_to_completion(agent, options, session, MagicMock(), consume_stream=received.extend)

    assert received == ["cached event"]
    assert statuses == ["finished"]
