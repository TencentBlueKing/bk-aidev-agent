"""Agent SSE 直推企微长连接的协议测试。"""

import json
from unittest.mock import patch

from aidev_wxbot.wxaibot.direct_stream import AgentStream, iter_direct_stream_frames


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n"


def test_chat_sse_is_converted_to_direct_frames_with_thinking_docs_and_terminal():
    stream = AgentStream(
        kind="chat",
        session_code="session-1",
        generator=iter(
            [
                _sse({"type": "RUN_STARTED", "run_id": "run-1"}),
                _sse({"type": "THINKING_TEXT_MESSAGE_CONTENT", "delta": "先查询" * 20}),
                _sse({"type": "TEXT_MESSAGE_CONTENT", "delta": "查询完成" * 20}),
                _sse(
                    {
                        "type": "CUSTOM",
                        "documents": [{"metadata": {"display_name": "日志", "path": "https://example.com/a b"}}],
                    }
                ),
                _sse({"type": "RUN_FINISHED", "run_id": "run-1"}),
            ]
        ),
    )
    run_ids = []

    frames = list(iter_direct_stream_frames(stream, "stream-1", on_run_started=run_ids.append))

    assert run_ids == ["run-1"]
    assert frames[0].content == f"<think>{'先查询' * 20}</think>"
    assert frames[1].content == f"<think>{'先查询' * 20}</think>{'查询完成' * 20}"
    assert frames[-1].finish
    assert "[1][日志](https://example.com/a%20b)" in frames[-1].content


def test_chat_run_error_becomes_explicit_terminal_frame():
    stream = AgentStream(
        kind="chat",
        session_code="session-1",
        generator=iter([_sse({"type": "RUN_ERROR", "message": "upstream timeout"})]),
    )

    frames = list(iter_direct_stream_frames(stream, "stream-1"))

    assert len(frames) == 1
    assert frames[0].finish
    assert frames[0].failed
    assert "upstream timeout" in frames[0].content


def test_chat_stream_eof_without_terminal_is_failed():
    agent_stream = AgentStream(
        kind="chat",
        session_code="session-1",
        generator=iter([_sse({"type": "TEXT_MESSAGE_CONTENT", "delta": "partial"})]),
    )

    frames = list(iter_direct_stream_frames(agent_stream, "stream-1"))

    assert frames[-1].finish
    assert frames[-1].failed
    assert "partial" in frames[-1].content
    assert "提前结束" in frames[-1].content


@patch("aidev_wxbot.wxaibot.direct_stream.AgentHelper.build_session_detail_url", return_value="/detail/s1")
def test_flow_sse_is_converted_to_direct_progress_and_terminal(mock_detail_url):
    stream = AgentStream(
        kind="flow",
        session_code="s1",
        generator=iter(
            [
                _sse({"type": "RUN_STARTED", "run_id": "flow-run"}),
                _sse({"type": "CUSTOM", "name": "flow_agent_start", "value": [{"task_id": "42"}]}),
                _sse(
                    {
                        "type": "CUSTOM",
                        "name": "flow_agent_result",
                        "value": [
                            {
                                "task_state": "RUNNING",
                                "nodes": {"n1": {"name": "查询日志", "state": "RUNNING"}},
                            }
                        ],
                    }
                ),
                _sse(
                    {
                        "type": "CUSTOM",
                        "name": "flow_agent_end",
                        "value": [{"task_id": "42", "task_outputs": [{"key": "result", "value": "ok"}]}],
                    }
                ),
            ]
        ),
    )

    frames = list(iter_direct_stream_frames(stream, "stream-flow"))

    assert not frames[0].finish
    assert "查询日志" in frames[0].content
    assert frames[-1].finish
    assert "result: ok" in frames[-1].content
    assert "[查看详情](/detail/s1)" in frames[-1].content
    mock_detail_url.assert_called_once_with("s1")
