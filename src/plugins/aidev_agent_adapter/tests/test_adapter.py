import asyncio
import json

import pytest
from acp.schema import AgentMessageChunk, TextContentBlock
from aidev_agent_adapter.adapter import Adapter
from aidev_agent_adapter.events import EventMapper
from aidev_agent_adapter.journal import Journal


async def collect(adapter, run_id="r1", thread_id="t1", text="hello", after=0):
    await adapter.submit(run_id, thread_id, text)
    return [event async for event in adapter.events(run_id, after)]


async def test_real_stdio_mapping_and_duplicate_request(adapter):
    events = await collect(adapter)
    types = [item["event"]["type"] for item in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    assert types.count("TEXT_MESSAGE_CONTENT") == 2  # identical valid deltas are not discarded
    args = [item["event"] for item in events if item["event"]["type"] == "TOOL_CALL_ARGS"]
    assert [json.loads(item["delta"]) for item in args] == [{"q": "final"}]
    assert all(item["threadId"] == "t1" and item["runId"] == "r1" for item in events)
    assert len({item["eventId"] for item in events}) == len(events)
    assert await collect(adapter, after=3) == events[3:]


@pytest.mark.parametrize("field", ["text", "thread_id"])
async def test_same_run_cannot_be_rebound(adapter, field):
    await collect(adapter)
    values = {"text": "hello", "thread_id": "t1"}
    values[field] = "other"
    with pytest.raises(ValueError, match="different request"):
        await adapter.submit("r1", **values)


async def test_consumer_disconnect_replays_without_rerunning(adapter):
    await adapter.submit("r1", "t1", "slow")
    stream = adapter.events("r1")
    first = await anext(stream)
    await stream.aclose()
    rest = [item async for item in adapter.events("r1", first["sequence"])]
    assert first["event"]["type"] == "RUN_STARTED"
    assert rest[-1]["event"]["type"] == "RUN_FINISHED"
    assert not any(item["event"]["type"] == "RUN_STARTED" for item in rest)


@pytest.mark.parametrize("text", ["crash", "timeout"])
async def test_transport_failure_is_terminal_and_not_retried(adapter, text):
    adapter.settings.prompt_timeout = 0.3
    events = await collect(adapter, text=text)
    assert events[-1]["event"]["type"] == "RUN_ERROR"
    assert events[-1]["event"]["code"] == "EXECUTION_UNKNOWN"
    assert await collect(adapter, text=text) == events
    second = await collect(adapter, run_id="r2", thread_id="t2")
    assert second[-1]["event"]["type"] == "RUN_ERROR"


@pytest.mark.parametrize("text", ["permission", "cancelled"])
async def test_permission_denied_and_agent_stop_reason(adapter, text):
    events = await collect(adapter, text=text)
    assert events[-1]["event"]["type"] == "RUN_FINISHED"
    assert events[-1]["event"]["result"]["stopReason"] == ("cancelled" if text == "cancelled" else "end_turn")


async def test_serial_turns_keep_session(adapter):
    await adapter.submit("r1", "t1", "slow")
    await adapter.submit("r2", "t1", "hello")
    for run_id in ("r1", "r2"):
        events = [item async for item in adapter.events(run_id)]
        assert events[-1]["event"]["type"] == "RUN_FINISHED"
    assert adapter._sessions == {"t1": "session-1"}


async def test_cancel_before_task_scheduled_is_terminal(adapter):
    await adapter.submit("r1", "t1", "hello")
    await adapter.cancel("r1")
    events = [item async for item in adapter.events("r1")]
    assert events[-1]["event"]["code"] == "CANCELLED_BEFORE_DISPATCH"


async def test_cancel_inflight_does_not_report_success(adapter):
    await adapter.submit("r1", "t1", "slow")
    await asyncio.sleep(0.1)
    await adapter.cancel("r1")
    events = [item async for item in adapter.events("r1")]
    assert events[-1]["event"]["type"] == "RUN_ERROR"
    assert not any(item["event"]["type"] == "RUN_FINISHED" for item in events)


def test_journal_restart_recovers_once_and_identity_is_bound(tmp_path):
    journal = Journal(tmp_path / "journal", "identity")
    journal.claim("run", "thread", {"input": "x"})
    EventMapper(journal, "run", "thread")
    journal.close()
    journal = Journal(tmp_path / "journal", "identity")
    assert [event["event"]["type"] for event in journal.replay("run")] == ["RUN_STARTED", "RUN_ERROR"]
    journal.close()
    with pytest.raises(ValueError, match="identity mismatch"):
        Journal(tmp_path / "journal", "other")
    journal = Journal(tmp_path / "journal", "identity")
    assert len(journal.replay("run")) == 2
    journal.close()


def test_late_updates_cannot_follow_terminal(tmp_path):
    journal = Journal(tmp_path / "journal", "id")
    journal.claim("run", "thread", {})
    mapper = EventMapper(journal, "run", "thread")
    mapper.finish("end_turn")
    mapper.update(
        AgentMessageChunk(session_update="agent_message_chunk", content=TextContentBlock(type="text", text="late"))
    )
    mapper.finish(error="LATE")
    assert len(journal.replay("run")) == 2
    journal.close()


def test_two_instances_cannot_own_same_journal(tmp_path):
    journal = Journal(tmp_path / "journal", "id")
    with pytest.raises(RuntimeError, match="already running"):
        Journal(tmp_path / "journal", "id")
    journal.close()


async def test_terminal_emitted_while_consumer_pauses_is_not_lost(adapter):
    await adapter.submit("r1", "t1", "hello")
    stream = adapter.events("r1")
    await anext(stream)
    while not adapter.journal.terminal("r1"):
        await asyncio.sleep(0.02)
    remaining = [item async for item in stream]
    assert remaining[-1]["event"]["type"] == "RUN_FINISHED"


async def test_restart_replays_old_run_but_rejects_lost_thread(adapter):
    old = await collect(adapter)
    await adapter.close()
    restarted = Adapter(adapter.settings, adapter.snapshot)
    try:
        assert await collect(restarted) == old
        events = await collect(restarted, run_id="r2")
        assert events[-1]["event"]["code"] == "SESSION_NOT_RECOVERABLE"
        new = await collect(restarted, run_id="r3", thread_id="new-thread")
        assert new[-1]["event"]["type"] == "RUN_FINISHED"
    finally:
        await restarted.close()


async def test_foreign_acp_session_cannot_contaminate_run(adapter):
    await adapter.submit("r1", "t1", "slow")
    async with asyncio.timeout(2):
        while adapter._active is None:
            await asyncio.sleep(0.01)
    await adapter.session_update(
        "foreign-session",
        AgentMessageChunk(session_update="agent_message_chunk", content=TextContentBlock(type="text", text="foreign")),
    )
    events = [item async for item in adapter.events("r1")]
    assert all(item["event"].get("delta") != "foreign" for item in events)
