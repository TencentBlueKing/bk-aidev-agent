from unittest.mock import MagicMock

import pytest
from ag_ui.core import EventType, RunStartedEvent, StateSnapshotEvent
from aidev_agent.core.ag_ui.agent import LangGraphAgent


@pytest.mark.asyncio
async def test_run_filters_state_snapshot_from_sse():
    agent = LangGraphAgent.__new__(LangGraphAgent)
    agent.config = {}

    state_snapshot = StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot={"messages": []})
    run_started = RunStartedEvent(type=EventType.RUN_STARTED, thread_id="thread-1", run_id="run-1")

    async def fake_stream_events(_input, _config):
        yield state_snapshot
        yield run_started

    agent._handle_stream_events = fake_stream_events
    run_input = MagicMock()
    run_input.forwarded_props = {}
    run_input.state = {}
    run_input.messages = []
    run_input.thread_id = "thread-1"
    run_input.model_copy.return_value = run_input

    events = [event async for event in agent.run(run_input)]

    assert events == [run_started]
