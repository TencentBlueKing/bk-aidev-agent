"""Channel consumption cannot abandon the session writer's stream."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
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
