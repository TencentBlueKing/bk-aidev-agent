# -*- coding: utf-8 -*-
"""只读回答流（services.answer_stream）单测：假 handler 遇到任何写方法都会报错，用来证明只读。"""

import json
from types import SimpleNamespace

import pytest
from aidev_bkplugin.services.answer_stream import (
    EOD_MARKER,
    SSE_PING,
    StreamSettings,
    StreamTarget,
    StreamUnsupported,
    TargetNotFound,
    history_answer,
    resolve_target,
    stream_answer,
)

HEARTBEAT = "<HEARTBEAT>"


def frame(**payload):
    return f"data: {json.dumps(payload)}\n\n"


def run_started():
    return frame(type="RUN_STARTED", threadId="s1", runId="r")


def text(delta, message_id="m1"):
    return frame(type="TEXT_MESSAGE_CONTENT", messageId=message_id, delta=delta)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeHandler:
    """模拟 replay handler：按批次返回消息；记录调用，确认没有写操作。"""

    def __init__(self, batches, clock, *, exists_after=0.0, delete_after_batches=None):
        self.batches = list(batches)
        self.clock = clock
        self.exists_after = exists_after
        self.delete_after_batches = delete_after_batches
        self.log = []
        self.served = 0
        self.offsets = []

    def has_pending_messages(self, thread_id):
        self.log.append("has_pending")
        if self.clock() < self.exists_after:
            return False
        return self.delete_after_batches is None or self.served < self.delete_after_batches

    def get_messages_since(self, thread_id, offset, timeout=None):
        self.log.append("get")
        self.offsets.append(offset)
        if not self.batches:
            self.clock.now += timeout
            raise TimeoutError
        batch = self.batches.pop(0)
        self.served += 1
        return batch, offset + len(batch)

    def __getattr__(self, name):  # 任何写操作（mark_completed/clear/acquire_consumer…）都视为违规
        raise AssertionError(f"read-only stream must not call {name}")


def events(chunks):
    out = []
    for chunk in chunks:
        if chunk == SSE_PING:
            out.append(("ping", None))
            continue
        lines = chunk.strip().split("\n")
        out.append((lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])))
    return out


def run(batches, state=lambda: 2, settings=None, **handler_kwargs):
    clock = FakeClock()
    handler = FakeHandler(batches, clock, **handler_kwargs)
    target = StreamTarget(trace_id="t1", session_code="s1")
    chunks = list(stream_answer(target, handler, state, settings or StreamSettings(), clock=clock, sleep=clock.sleep))
    return events(chunks), handler


def deltas(evts, frame_type="TEXT_MESSAGE_CONTENT"):
    return "".join(data["delta"] for name, data in evts if name == "agui" and data["type"] == frame_type)


# ---------- resolve_target ----------


def schedule(state=2, storage=None, raw=None):
    data = raw if raw is not None else json.dumps({"context": {"storage": storage or {}}})
    return SimpleNamespace(state=state, data=data)


def test_resolve_target_ok():
    target = resolve_target("t1", schedule(storage={"session_code": "s1", "agent_type": "chat"}))
    assert target == StreamTarget("t1", "s1")


def test_resolve_target_not_found():
    with pytest.raises(TargetNotFound):
        resolve_target("t1", None)


@pytest.mark.parametrize(
    "sched",
    [
        schedule(state=4, storage={"session_code": "s1"}),  # 已结束但没有 turn_id
        schedule(state=3, storage={"session_code": "s1"}),
        schedule(storage={}),
        schedule(storage={"session_code": "s1", "agent_type": "flow"}),
        schedule(raw="not json"),
    ],
)
def test_resolve_target_unsupported(sched):
    with pytest.raises(StreamUnsupported):
        resolve_target("t1", sched)


@pytest.mark.parametrize(
    "data",
    [None, [], 1, "text", {"context": ["invalid"]}, {"context": {"storage": ["invalid"]}}],
)
def test_resolve_target_rejects_invalid_structure(data):
    with pytest.raises(StreamUnsupported):
        resolve_target("t1", schedule(raw=json.dumps(data)))


@pytest.mark.parametrize("session_code", [["s1"], {"code": "s1"}, 1, True])
def test_resolve_target_rejects_non_string_session_code(session_code):
    with pytest.raises(StreamUnsupported):
        resolve_target("t1", schedule(storage={"session_code": session_code}))


@pytest.mark.parametrize("field,value", [("turn_id", ["u1"]), ("plugin_username", ["admin"])])
def test_resolve_target_rejects_invalid_history_identity(field, value):
    storage = {"session_code": "s1", "turn_id": "u1", "plugin_username": "admin", field: value}
    with pytest.raises(StreamUnsupported):
        resolve_target("t1", schedule(state=4, storage=storage))


@pytest.mark.parametrize("state", [4, 5])
def test_resolve_target_finished(state):
    storage = {"session_code": "s1", "turn_id": "u1", "plugin_username": "admin"}
    target = resolve_target("t1", schedule(state=state, storage=storage))
    assert target == StreamTarget("t1", "s1", finished=True, turn_id="u1", username="admin")


# ---------- history_answer ----------


def history(contents, settings=None):
    target = StreamTarget("t1", "s1", finished=True, turn_id="u1")
    return events(list(history_answer(target, contents, settings or StreamSettings())))


def test_history_returns_thinking_of_this_turn():
    contents = [
        {"role": "user", "content": "问题", "property": {"turn_id": "u1"}},
        {"role": "reasoning", "content": ["旧"], "duration": 5, "property": {"turn_id": "u0"}},
        {"role": "reasoning", "content": ["想一", "想二"], "duration": 1803.0, "property": {"turn_id": "u1"}},
        {"role": "assistant", "content": "回答", "property": {"turn_id": "u1"}},
    ]
    evts = history(contents)
    assert evts[0] == ("ready", {"output_key": "output"})
    assert evts[-1] == ("end", {"reason": "history"})
    frames = [data for name, data in evts if name == "agui"]
    assert [f["type"] for f in frames] == [
        "THINKING_START",
        "THINKING_TEXT_MESSAGE_START",
        "THINKING_TEXT_MESSAGE_CONTENT",
        "THINKING_TEXT_MESSAGE_END",
        "THINKING_TEXT_MESSAGE_START",
        "THINKING_TEXT_MESSAGE_CONTENT",
        "THINKING_TEXT_MESSAGE_END",
        "THINKING_END",
    ]
    assert deltas(evts, "THINKING_TEXT_MESSAGE_CONTENT") == "想一想二"
    assert frames[-1]["duration"] == 1803.0
    assert not deltas(evts)  # 正文以正式输出为准，不返回


@pytest.mark.parametrize("content", ['["想"]', "想", ["想"]])
def test_history_reasoning_content_formats(content):
    evts = history([{"role": "reasoning", "content": content, "property": {"turn_id": "u1"}}])
    assert deltas(evts, "THINKING_TEXT_MESSAGE_CONTENT") == "想"


def test_history_without_thinking_or_disabled():
    assert [n for n, _ in history([{"role": "assistant", "content": "a", "property": {"turn_id": "u1"}}])] == [
        "ready",
        "end",
    ]
    contents = [{"role": "reasoning", "content": ["想"], "property": {"turn_id": "u1"}}]
    only_text = StreamSettings(event_types=frozenset({"TEXT_MESSAGE_CONTENT"}))
    assert [n for n, _ in history(contents, only_text)] == ["ready", "end"]


@pytest.mark.parametrize(
    "allowed",
    [
        frozenset(),
        frozenset({"THINKING_START"}),
        frozenset({"THINKING_TEXT_MESSAGE_CONTENT"}),
        frozenset({"THINKING_END"}),
    ],
)
def test_history_obeys_event_allowlist(allowed):
    contents = [{"role": "reasoning", "content": ["private thought"], "duration": 10, "property": {"turn_id": "u1"}}]
    evts = history(contents, StreamSettings(event_types=allowed))
    assert evts[0] == ("ready", {"output_key": "output"})
    assert evts[-1] == ("end", {"reason": "history"})
    assert {payload["type"] for name, payload in evts if name == "agui"} == allowed
    if "THINKING_TEXT_MESSAGE_CONTENT" not in allowed:
        assert not deltas(evts, "THINKING_TEXT_MESSAGE_CONTENT")


# ---------- stream_answer ----------


def test_streams_text_in_order_and_ends_on_eod():
    evts, handler = run([[run_started(), text("你"), text("你")], [text("好"), EOD_MARKER]])
    assert evts[0] == ("ready", {"output_key": "output"})
    assert deltas(evts) == "你你好"  # 连续相同文本都保留
    assert evts[-1] == ("end", {"reason": "completed"})
    assert handler.offsets == [0, 3]


def test_first_batch_cut_at_last_run_started():
    old_round = [run_started(), text("旧回答"), EOD_MARKER]
    evts, _ = run([old_round + [run_started(), text("新"), text("回答")], [EOD_MARKER]])
    assert deltas(evts) == "新回答"
    assert evts[-1] == ("end", {"reason": "completed"})


def test_first_batch_without_run_started_keeps_everything():
    evts, _ = run([[text("a"), text("b")], [EOD_MARKER]])
    assert deltas(evts) == "ab"


def test_later_run_started_emits_reset():
    evts, _ = run([[run_started(), text("a")], [run_started(), text("b"), EOD_MARKER]])
    names = [name for name, _ in evts]
    assert names.count("reset") == 2  # 首批截断保留的 RUN_STARTED + 后续新一轮
    assert deltas(evts[names.index("reset", 2) :]) == "b"


def test_forwards_thinking_and_text_frames_as_is():
    answer = [
        frame(type="THINKING_START"),
        frame(type="THINKING_TEXT_MESSAGE_START"),
        frame(type="THINKING_TEXT_MESSAGE_CONTENT", delta="思考"),
        frame(type="THINKING_TEXT_MESSAGE_END"),
        frame(type="THINKING_END"),
        frame(type="TEXT_MESSAGE_START", messageId="m1", role="assistant"),
        text("正文"),
        frame(type="TEXT_MESSAGE_END", messageId="m1"),
    ]
    evts, _ = run([[run_started(), *answer], [EOD_MARKER]])
    forwarded = [data for name, data in evts if name == "agui"]
    assert forwarded == [json.loads(item[len("data: ") :]) for item in answer]
    assert deltas(evts, "THINKING_TEXT_MESSAGE_CONTENT") == "思考"
    assert deltas(evts) == "正文"


def test_filters_other_events_and_markers():
    noise = [
        frame(type="TOOL_CALL_ARGS", toolCallId="x", delta="{}"),
        frame(type="MESSAGES_SNAPSHOT", messages=[]),
        frame(type="RUN_FINISHED", threadId="s1", runId="r"),
        HEARTBEAT,
        "data: not-json\n\n",
    ]
    evts, _ = run([[run_started(), *noise, text("正文")], [EOD_MARKER]])
    assert [data["type"] for name, data in evts if name == "agui"] == ["TEXT_MESSAGE_CONTENT"]


def test_custom_event_types():
    tool = frame(type="TOOL_CALL_ARGS", toolCallId="x", delta="{}")
    evts, _ = run([[tool, text("a"), EOD_MARKER]], settings=StreamSettings(event_types=frozenset({"TOOL_CALL_ARGS"})))
    assert [data["type"] for name, data in evts if name == "agui"] == ["TOOL_CALL_ARGS"]


def test_waits_for_queue_without_reading_then_streams():
    evts, handler = run([[text("x"), EOD_MARKER]], exists_after=5.0)
    first_get = handler.log.index("get")
    assert all(call == "has_pending" for call in handler.log[:first_get])
    assert deltas(evts) == "x"


def test_not_ready_timeout():
    evts, handler = run([], exists_after=10_000, settings=StreamSettings(ready_timeout=30))
    assert evts[-1] == ("end", {"reason": "not_ready"})
    assert "get" not in handler.log  # 队列不存在时绝不调用会声明队列的读取


def test_finished_while_waiting_for_queue():
    evts, handler = run([], state=lambda: 4, exists_after=10_000)
    assert evts[-1] == ("end", {"reason": "finished"})
    assert "get" not in handler.log


def test_schedule_terminal_drains_once_then_ends():
    states = iter([2, 4])
    evts, _ = run(
        [[text("a")]],
        state=lambda: next(states, 4),
        settings=StreamSettings(state_check_interval=1, read_timeout=2),
    )
    assert deltas(evts) == "a"
    assert evts[-1] == ("end", {"reason": "finished"})


def test_queue_deleted_ends_stream():
    evts, _ = run([[text("a")], [text("never")]], delete_after_batches=1)
    assert deltas(evts) == "a"
    assert evts[-1] == ("end", {"reason": "finished"})


def test_schedule_missing_counts_as_finished():
    evts, _ = run([], state=lambda: None, settings=StreamSettings(state_check_interval=1))
    assert evts[-1] == ("end", {"reason": "finished"})


def test_ping_when_idle_and_max_duration():
    settings = StreamSettings(ping_interval=15, read_timeout=2, max_duration=60, state_check_interval=1000)
    evts, _ = run([], settings=settings)
    assert ("ping", None) in evts
    assert evts[-1] == ("end", {"reason": "timeout"})


def test_custom_output_key():
    evts, _ = run([[EOD_MARKER]], settings=StreamSettings(output_key="answer"))
    assert evts[0] == ("ready", {"output_key": "answer"})
