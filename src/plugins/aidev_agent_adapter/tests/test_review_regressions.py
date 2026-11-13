import asyncio
import fcntl
import io
import json
import os
import zipfile

import pytest
from acp.schema import AgentMessageChunk, TextContentBlock, ToolCallStart
from ag_ui.core import CustomEvent, ToolCallArgsEvent, ToolCallEndEvent, ToolCallStartEvent
from aidev_agent_adapter.config_sync import ConfigSynchronizer, render_mcp, unpack_skill
from aidev_agent_adapter.events import EventMapper
from aidev_agent_adapter.journal import Journal
from aidev_agent_adapter.platform import PlatformError


def text_update(value):
    return AgentMessageChunk(session_update="agent_message_chunk", content=TextContentBlock(type="text", text=value))


def test_text_tool_text_has_separate_message_lifecycles(tmp_path):
    journal = Journal(tmp_path / "journal", "id")
    try:
        journal.claim("r", "t", {})
        mapper = EventMapper(journal, "r", "t")
        mapper.update(text_update("before"))
        mapper.update(
            ToolCallStart(session_update="tool_call", tool_call_id="tool", title="search", status="completed")
        )
        mapper.update(text_update("after"))
        mapper.finish("end_turn")
        events = [item["event"] for item in journal.replay("r")]
        types = [event["type"] for event in events]
        assert types.index("TEXT_MESSAGE_END") < types.index("TOOL_CALL_START")
        starts = [event["messageId"] for event in events if event["type"] == "TEXT_MESSAGE_START"]
        assert len(set(starts)) == 2
    finally:
        journal.close()


def test_restart_closes_open_messages_and_tools(tmp_path):
    root = tmp_path / "journal"
    journal = Journal(root, "id")
    journal.claim("r", "t", {})
    mapper = EventMapper(journal, "r", "t")
    mapper.update(text_update("partial"))
    mapper.update(
        ToolCallStart(
            session_update="tool_call",
            tool_call_id="tool",
            title="search",
            status="in_progress",
            raw_input={"q": "saved"},
        )
    )
    journal.close()
    journal = Journal(root, "id")
    try:
        types = [item["event"]["type"] for item in journal.replay("r")]
        assert types.count("TEXT_MESSAGE_START") == types.count("TEXT_MESSAGE_END")
        assert types.count("TOOL_CALL_START") == types.count("TOOL_CALL_END")
        assert types[-1] == "RUN_ERROR"
    finally:
        journal.close()


def test_future_replay_cursor_is_rejected(tmp_path):
    journal = Journal(tmp_path / "journal", "id")
    try:
        journal.claim("r", "t", {})
        with pytest.raises(ValueError, match="cursor"):
            journal.replay("r", 999)
    finally:
        journal.close()


async def test_extra_skill_in_existing_snapshot_is_rejected(settings, platform):
    sync = ConfigSynchronizer(settings, platform)
    snapshot = await sync.sync()
    extra = snapshot.workspace / "skills/extra/SKILL.md"
    extra.parent.mkdir()
    extra.write_text("unselected skill")
    try:
        with pytest.raises(ValueError, match="modified"):
            await sync.sync()
    finally:
        await platform.close()


async def test_skill_code_participates_in_revision(settings, platform, api_data):
    sync = ConfigSynchronizer(settings, platform)
    before = await sync.sync()
    api_data["skill"]["skill_code"] = "renamed"
    try:
        after = await sync.sync()
        assert before.revision != after.revision
        assert (after.workspace / "skills/renamed/SKILL.md").exists()
        assert not (after.workspace / "skills/sample").exists()
    finally:
        await platform.close()


def test_executable_skill_script_remains_executable(tmp_path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as package:
        package.writestr("SKILL.md", "sample")
        script = zipfile.ZipInfo("scripts/run.sh")
        script.external_attr = 0o100755 << 16
        package.writestr(script, "#!/bin/sh\nexit 0\n")
    unpack_skill(output.getvalue(), tmp_path / "skill", 10000)
    assert (tmp_path / "skill/scripts/run.sh").stat().st_mode & 0o777 == 0o700


def test_platform_endpoint_is_part_of_instance_identity(settings):
    other = settings.model_copy(update={"endpoint": "https://another-platform.example"})
    assert settings.identity != other.identity


def test_hermes_sse_transport_is_not_dropped():
    server = {"url": "https://mcp.example/stream", "transport": "sse"}
    assert render_mcp({"docs": server}, "hermes")["docs"]["transport"] == "sse"


async def test_cancelled_unsent_request_does_not_poison_thread(adapter):
    await adapter.submit("cancelled", "thread", "unused")
    await adapter.cancel("cancelled")
    await adapter.submit("next", "thread", "hello")
    events = [item async for item in adapter.events("next")]
    assert events[-1]["event"]["type"] == "RUN_FINISHED"
    cancelled = adapter.journal.replay("cancelled")
    assert [item["event"]["type"] for item in cancelled] == ["RUN_STARTED", "RUN_ERROR"]


async def test_queue_limit_still_allows_duplicate_reconnect(adapter):
    adapter.settings.max_pending_runs = 1
    await adapter.submit("first", "thread", "slow")
    await adapter.submit("first", "thread", "slow")
    with pytest.raises(RuntimeError, match="queue"):
        await adapter.submit("second", "thread", "hello")
    assert not adapter.journal.contains("second")
    events = [item async for item in adapter.events("first")]
    assert events[-1]["event"]["type"] == "RUN_FINISHED"


async def test_privileged_auth_header_is_not_copied(settings, platform):
    server = {
        "url": "https://platform.example/mcp",
        "headers": {
            "x-bkapi-authorization": json.dumps({"bk_app_secret": "fixture-only"}),
            "x-bk-tenant-id": "wrong-tenant",
        },
    }
    headers = platform.prepare_mcp(server)["headers"]
    assert json.loads(headers["X-Bkapi-Authorization"]) == {"access_token": "test-only-token"}
    assert headers["X-Bk-Tenant-Id"] == "tenant"
    await platform.close()


async def test_cancel_cannot_overlap_the_next_turn(adapter, controlled_connection):
    connection = controlled_connection
    await adapter.submit("r1", "thread", "first")
    await asyncio.wait_for(connection.first_started.wait(), 1)
    cancellation = asyncio.create_task(adapter.cancel("r1"))
    await asyncio.wait_for(connection.cancel_entered.wait(), 1)
    try:
        connection.finish_first.set()
        await adapter.submit("r2", "thread", "next")
        await asyncio.sleep(0.05)
        assert not connection.second_started.is_set()
    finally:
        connection.finish_cancel.set()
        await cancellation
    events = [item async for item in adapter.events("r2")]
    assert events[-1]["event"]["type"] == "RUN_ERROR"


async def test_event_mapping_failure_interrupts_prompt(adapter, monkeypatch):
    original = adapter.journal.append

    def append(run_id, event, **kwargs):
        if event.type == "TEXT_MESSAGE_CONTENT":
            raise ValueError("synthetic conversion failure")
        original(run_id, event, **kwargs)

    monkeypatch.setattr(adapter.journal, "append", append)
    adapter.settings.prompt_timeout = 20
    await adapter.submit("r", "t", "mapping")
    async with asyncio.timeout(1):
        events = [item async for item in adapter.events("r")]
    assert events[-1]["event"]["code"] == "EVENT_MAPPING_FAILED"
    types = [item["event"]["type"] for item in events]
    assert types.count("TEXT_MESSAGE_START") == types.count("TEXT_MESSAGE_END")


@pytest.mark.parametrize("after", [-1, True, 0.5, "1"])
def test_invalid_cursor_types_rejected(tmp_path, after):
    journal = Journal(tmp_path / "journal", "id")
    try:
        journal.claim("r", "t", {})
        with pytest.raises(ValueError, match="cursor"):
            journal.replay("r", after)
    finally:
        journal.close()


@pytest.mark.parametrize("engine", ["openclaw", "hermes"])
async def test_unmanaged_runtime_files_do_not_block_sync(settings, platform, engine):
    settings.engine = engine
    sync = ConfigSynchronizer(settings, platform)
    previous = await sync.sync()
    (previous.workspace / "MEMORY.md").write_text("runtime memory")
    try:
        assert (await sync.sync()).revision == previous.revision
    finally:
        await platform.close()


@pytest.mark.parametrize("change", ["symlink", "mode", "missing"])
async def test_managed_skill_mutation_is_rejected(settings, platform, change):
    sync = ConfigSynchronizer(settings, platform)
    snapshot = await sync.sync()
    target = snapshot.workspace / "skills/sample/SKILL.md"
    if change == "mode":
        target.chmod(0o644)
    else:
        target.unlink()
        if change == "symlink":
            target.symlink_to(snapshot.workspace / "SOUL.md")
    try:
        with pytest.raises(ValueError, match="modified"):
            await sync.sync()
    finally:
        await platform.close()


@pytest.mark.parametrize("returned_version,accepted", [("2.0", True), ("3.0", False)])
async def test_explicit_skill_pin_is_not_replaced_by_latest(settings, platform, api_data, returned_version, accepted):
    settings.skill_versions = {1: "2.0"}
    api_data["agent"]["related_skills"]["skills"][0]["version"] = "3.0"  # platform display version
    api_data["skill"]["version"] = returned_version
    try:
        if accepted:
            assert (await platform.fetch()).skills[0]["version"] == "2.0"
        else:
            with pytest.raises(PlatformError, match="version mismatch"):
                await platform.fetch()
    finally:
        await platform.close()


async def test_unused_version_pin_is_rejected(settings, platform):
    settings.skill_versions = {999: "2.0"}
    try:
        with pytest.raises(PlatformError, match="selected bound"):
            await platform.fetch()
    finally:
        await platform.close()


async def test_fifo_cannot_block_snapshot_validation(settings, platform):
    sync = ConfigSynchronizer(settings, platform)
    snapshot = await sync.sync()
    target = snapshot.workspace / "skills/sample/SKILL.md"
    target.unlink()
    os.mkfifo(target)
    try:
        with pytest.raises(ValueError, match="modified"):
            await sync.sync()
    finally:
        await platform.close()


def test_recovery_after_partial_tool_end_is_idempotent(tmp_path):
    root = tmp_path / "journal"
    journal = Journal(root, "id")
    journal.claim("r", "t", {})
    journal.append("r", ToolCallStartEvent(tool_call_id="tool", tool_call_name="search"))
    journal.append("r", ToolCallArgsEvent(tool_call_id="tool", delta='{"q":"x"}'))
    journal.append("r", ToolCallEndEvent(tool_call_id="tool"))
    journal.close()
    journal = Journal(root, "id")
    try:
        events = journal.replay("r")
        journal.abort("r", "EXECUTION_UNKNOWN", "retry")
        assert journal.replay("r") == events
        types = [item["event"]["type"] for item in events]
        assert types.count("TOOL_CALL_ARGS") == types.count("TOOL_CALL_END") == types.count("TOOL_CALL_RESULT") == 1
    finally:
        journal.close()


def test_duplicate_request_and_replay_cross_page_boundary(tmp_path):
    journal = Journal(tmp_path / "journal", "id")
    try:
        assert journal.claim("r", "t", {})
        for _ in range(260):
            journal.append("r", CustomEvent(name="fixture", value="same"))
        journal.abort("r", "EXECUTION_UNKNOWN", "done")
        first = journal.replay("r")
        rest = journal.replay("r", first[-1]["sequence"])
        assert len(first) == 256 and len(rest) == 6
        assert not journal.claim("r", "t", {})
        assert len({item["eventId"] for item in first + rest}) == 262
    finally:
        journal.close()


@pytest.mark.parametrize("event_count", [0, 1])
def test_legacy_journal_recovery_preserves_uncertain_dispatch(tmp_path, event_count):
    root = tmp_path / "journal"
    journal = Journal(root, "id")
    journal.claim("r", "t", {})
    with journal.db:
        journal.db.execute("DROP INDEX runs_thread")
        journal.db.execute("ALTER TABLE runs DROP COLUMN dispatched")
        if not event_count:
            journal.db.execute("DELETE FROM events")
    journal.close()
    recovered = Journal(root, "id")
    try:
        assert recovered.has_thread("t", "another-run")
        assert [item["event"]["type"] for item in recovered.replay("r")] == ["RUN_STARTED", "RUN_ERROR"]
    finally:
        recovered.close()


def test_duplicate_tool_terminal_does_not_split_following_text(tmp_path):
    journal = Journal(tmp_path / "journal", "id")
    try:
        journal.claim("r", "t", {})
        mapper = EventMapper(journal, "r", "t")
        tool = ToolCallStart(session_update="tool_call", tool_call_id="tool", title="search", status="completed")
        mapper.update(tool)
        mapper.update(text_update("one"))
        mapper.update(tool)
        mapper.update(text_update("two"))
        mapper.finish("end_turn")
        types = [item["event"]["type"] for item in journal.replay("r")]
        assert types.count("TEXT_MESSAGE_START") == types.count("TEXT_MESSAGE_END") == 1
        assert types.count("TOOL_CALL_START") == 1
    finally:
        journal.close()


def test_recovery_keeps_last_observed_tool_arguments(tmp_path):
    root = tmp_path / "journal"
    journal = Journal(root, "id")
    journal.claim("r", "t", {})
    mapper = EventMapper(journal, "r", "t")
    mapper.update(
        ToolCallStart(
            session_update="tool_call",
            tool_call_id="tool",
            title="search",
            status="in_progress",
            raw_input={"q": "saved"},
        )
    )
    journal.close()
    journal = Journal(root, "id")
    try:
        args = [item["event"]["delta"] for item in journal.replay("r") if item["event"]["type"] == "TOOL_CALL_ARGS"]
        assert args == [json.dumps({"q": "saved"})]
    finally:
        journal.close()


def test_message_id_switch_and_empty_chunk(tmp_path):
    journal = Journal(tmp_path / "journal", "id")
    try:
        journal.claim("r", "t", {})
        mapper = EventMapper(journal, "r", "t")
        mapper.update(text_update(""))
        mapper.update(text_update("implicit"))
        mapper.update(
            AgentMessageChunk(
                session_update="agent_message_chunk",
                message_id="default",
                content=TextContentBlock(type="text", text="explicit"),
            )
        )
        mapper.finish("end_turn")
        starts = [item for item in journal.replay("r") if item["event"]["type"] == "TEXT_MESSAGE_START"]
        assert len(starts) == 2
    finally:
        journal.close()


@pytest.mark.parametrize("engine", ["openclaw", "hermes"])
async def test_empty_selection_is_repeatable_and_stray_prompt_rejected(settings, platform, engine):
    settings.engine = engine
    settings.include_prompt = False
    settings.skill_ids = []
    settings.mcp_names = []
    sync = ConfigSynchronizer(settings, platform)
    try:
        snapshot = await sync.sync()
        assert (await sync.sync()).revision == snapshot.revision
        prompt = (snapshot.workspace if engine == "openclaw" else snapshot.path) / "SOUL.md"
        prompt.write_text("not selected")
        with pytest.raises(ValueError, match="modified"):
            await sync.sync()
    finally:
        await platform.close()


@pytest.mark.parametrize("engine", ["openclaw", "hermes"])
async def test_symlinked_managed_root_is_rejected(settings, platform, engine):
    settings.engine = engine
    sync = ConfigSynchronizer(settings, platform)
    try:
        snapshot = await sync.sync()
        root = snapshot.workspace if engine == "openclaw" else snapshot.path
        original = root / "skills"
        original.rename(root / "renamed-skills")
        original.symlink_to(root / "renamed-skills", target_is_directory=True)
        with pytest.raises(ValueError, match="modified"):
            await sync.sync()
    finally:
        await platform.close()


async def test_concurrent_sync_keeps_published_snapshot(settings, platform):
    sync = ConfigSynchronizer(settings, platform)
    previous = await sync.sync()
    try:
        with (settings.root / ".sync.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(RuntimeError, match="in progress"):
                await ConfigSynchronizer(settings, platform).sync()
        assert (settings.root / "current").resolve() == previous.path
    finally:
        await platform.close()


async def test_invalid_mcp_headers_fail_before_writing(platform):
    try:
        with pytest.raises(PlatformError, match="invalid MCP headers"):
            platform.prepare_mcp({"url": "https://platform.example/mcp", "headers": {"header": 123}})
    finally:
        await platform.close()


def test_journal_initialization_failure_releases_lock(tmp_path):
    root = tmp_path / "journal"
    root.mkdir()
    path = root / "events.sqlite3"
    path.symlink_to(tmp_path / "unrelated")
    with pytest.raises(ValueError, match="symlinked"):
        Journal(root, "id")
    path.unlink()
    journal = Journal(root, "id")
    try:
        with pytest.raises(KeyError):
            journal.replay("missing")
        with pytest.raises(KeyError):
            journal.append("missing", CustomEvent(name="test", value=None))
    finally:
        journal.close()


def test_recovery_does_not_duplicate_completed_tools(tmp_path):
    root = tmp_path / "journal"
    journal = Journal(root, "id")
    journal.claim("r", "t", {})
    mapper = EventMapper(journal, "r", "t")
    mapper.update(ToolCallStart(session_update="tool_call", tool_call_id="tool", title="search", status="completed"))
    mapper.update(text_update("unfinished answer"))
    journal.close()
    journal = Journal(root, "id")
    try:
        events = journal.replay("r")
        journal.append("r", CustomEvent(name="late", value=None))
        assert journal.replay("r") == events
        assert sum(item["event"]["type"] == "TOOL_CALL_RESULT" for item in events) == 1
        assert events[-1]["event"]["type"] == "RUN_ERROR"
    finally:
        journal.close()


def test_recovery_transaction_rolls_back_on_write_failure(tmp_path, monkeypatch):
    journal = Journal(tmp_path / "journal", "id")
    try:
        journal.claim("r", "t", {})
        EventMapper(journal, "r", "t").update(text_update("partial"))
        before = journal.replay("r")
        append = journal._append

        def fail_terminal(run_id, event, **kwargs):
            if kwargs.get("terminal"):
                raise RuntimeError("synthetic write failure")
            append(run_id, event, **kwargs)

        monkeypatch.setattr(journal, "_append", fail_terminal)
        with pytest.raises(RuntimeError):
            journal.abort("r", "EXECUTION_UNKNOWN", "interrupted")
        assert journal.replay("r") == before
        assert not journal.terminal("r")
        monkeypatch.setattr(journal, "_append", append)
        journal.abort("r", "EXECUTION_UNKNOWN", "retry")
        assert journal.terminal("r")
    finally:
        journal.close()
