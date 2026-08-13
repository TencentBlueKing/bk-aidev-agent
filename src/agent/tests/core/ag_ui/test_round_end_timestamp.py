# -*- coding: utf-8 -*-
"""本轮对话收尾事件写入墙钟毫秒，续流回放不打戳。"""

import json

from ag_ui.core import EventType, RunErrorEvent, RunFinishedEvent
from ag_ui.encoder import EventEncoder

from aidev_agent.utils.event import emit_run_finished_event, stamp_round_end_event


def test_stamp_round_end_event_writes_wall_clock_ms(monkeypatch):
    monkeypatch.setattr("aidev_agent.utils.event.wall_clock_ms", lambda: 1_710_000_000_000)
    finished = RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="t1", run_id="run-1")
    error = RunErrorEvent(type=EventType.RUN_ERROR, message="模型调用异常")

    stamp_round_end_event(finished)
    stamp_round_end_event(error)

    assert finished.timestamp == 1_710_000_000_000
    assert error.timestamp == 1_710_000_000_000


def test_resume_replay_run_finished_has_no_timestamp(monkeypatch):
    monkeypatch.setattr("aidev_agent.utils.event.wall_clock_ms", lambda: 1_710_000_000_000)
    event = RunFinishedEvent(
        type=EventType.RUN_FINISHED,
        thread_id="t1",
        run_id="interrupt-1",
        resume_replay=True,
    )

    stamp_round_end_event(event)
    payload = json.loads(EventEncoder().encode(event).removeprefix("data: ").strip())

    assert event.timestamp is None
    assert "timestamp" not in payload


def test_emit_run_finished_event_includes_timestamp(monkeypatch):
    monkeypatch.setattr("aidev_agent.utils.event.wall_clock_ms", lambda: 1_710_000_000_000)

    payload = json.loads(
        emit_run_finished_event(thread_id="t1", run_id="run-1").removeprefix("data: ").strip()
    )

    assert payload["type"] == "RUN_FINISHED"
    assert payload["timestamp"] == 1_710_000_000_000
