"""Agent SSE 直推企微长连接的协议测试。"""

import json
from unittest.mock import patch

from aidev_wxbot.wxaibot.constants import STREAM_ERROR_REPLY
from aidev_wxbot.wxaibot.direct_stream import AgentStream, iter_direct_stream_frames


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n"


def test_run_id_is_read_from_the_real_wire_format():
    """AG-UI 按 camelCase 别名序列化，run id 在 runId 上。

    这里直接用框架的 encoder 造事件而不是手写 dict：之前的用例手写了 snake_case，
    于是取不到 run id 这件事一路没被发现，取消退化成 session 级信号，
    把同会话的下一轮一起毒死（下一轮开局即报「用户已取消」）。
    """
    from ag_ui.core.events import RunStartedEvent
    from ag_ui.encoder import EventEncoder

    started = EventEncoder().encode(RunStartedEvent(thread_id="session-1", run_id="run-1"))
    assert '"runId"' in started

    stream = AgentStream(kind="chat", session_code="session-1", generator=iter([started]))
    run_ids: list[str] = []

    list(iter_direct_stream_frames(stream, "stream-1", on_run_started=run_ids.append))

    assert run_ids == ["run-1"]


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


def test_terminal_frame_still_drains_the_agent_iterator_to_its_natural_end():
    consumed: list[str] = []

    def source():
        for chunk in (_sse({"type": "RUN_FINISHED"}), "data: [DONE]\n"):
            consumed.append(chunk)
            yield chunk

    stream = AgentStream(kind="chat", session_code="session-1", generator=source())

    frames = list(iter_direct_stream_frames(stream, "stream-1"))

    assert frames[-1].finish
    assert len(consumed) == 2


def _chat_frames(events: list[dict], stream_id: str = "stream-tool"):
    stream = AgentStream(kind="chat", session_code="s", generator=iter([_sse(event) for event in events]))
    return list(iter_direct_stream_frames(stream, stream_id))


def test_tool_call_start_is_pushed_before_the_result_arrives():
    """工具卡住时用户至少要看得到卡在哪个工具上，START 不能攒着不推。"""
    frames = _chat_frames(
        [
            {"type": "TOOL_CALL_START", "toolCallId": "t1", "toolCallName": "execute"},
            {"type": "TOOL_CALL_RESULT", "toolCallId": "t1", "content": "ok", "duration": 207, "isError": False},
            {"type": "RUN_FINISHED"},
        ]
    )

    assert not frames[0].finish
    assert "🔄" in frames[0].content
    assert "execute" in frames[0].content
    assert "调用中" in frames[0].content
    assert frames[0].content.endswith("\n\n")
    assert "🟢 **execute** · 已完成 · 207ms" in frames[-1].content


def test_tool_block_refreshes_in_place_and_interleaves_with_text():
    """同一 tool_call_id 原地刷新，工具块与正文按调用顺序排列。"""
    frames = _chat_frames(
        [
            {"type": "TOOL_CALL_START", "toolCallId": "c1", "toolCallName": "activate_skill"},
            {"type": "TOOL_CALL_ARGS", "toolCallId": "c1", "delta": '{"skill":"bklog"}'},
            {"type": "TOOL_CALL_END", "toolCallId": "c1"},
            {"type": "TOOL_CALL_RESULT", "toolCallId": "c1", "content": "activated", "duration": 12, "isError": False},
            {"type": "TEXT_MESSAGE_CONTENT", "delta": "接下来查询日志"},
            {"type": "TOOL_CALL_START", "toolCallId": "c2", "toolCallName": "execute"},
            {"type": "TOOL_CALL_ARGS", "toolCallId": "c2", "delta": '{"cmd":"ls"}'},
            # 下游偶尔发 snake_case，两种拼写都要认
            {"type": "TOOL_CALL_RESULT", "tool_call_id": "c2", "content": "done", "duration": 90, "is_error": False},
            {"type": "RUN_FINISHED"},
        ]
    )

    content = frames[-1].content
    assert "调用中" in frames[0].content
    assert "执行中" in frames[1].content
    assert "已完成" in frames[2].content
    assert "🟢 **activate_skill** `bklog` · 已完成 · 12ms" in content
    assert "🟢 **execute** · 已完成 · 90ms" in content
    assert "`ls`" not in content
    assert "接下来查询日志" in content
    # 成功的结果由正文复述，工具块里不再重复
    assert "activated" not in content
    assert content.index("activate_skill") < content.index("接下来查询日志") < content.index("execute")


def test_failed_tool_shows_the_reason():
    frames = _chat_frames(
        [
            {"type": "TOOL_CALL_START", "toolCallId": "e1", "toolCallName": "execute"},
            {
                "type": "TOOL_CALL_RESULT",
                "toolCallId": "e1",
                "content": "PaaS SandboxError: 1640001 用户认证失败",
                "duration": 60000,
                "isError": True,
            },
            {"type": "RUN_FINISHED"},
        ]
    )

    content = frames[-1].content
    assert "🔴 **execute** · 执行失败 · 60.0s" in content
    assert "1640001" in content
    assert "用户认证失败" not in content


def test_sensitive_tool_args_and_raw_error_are_not_exposed():
    frames = _chat_frames(
        [
            {"type": "TOOL_CALL_START", "toolCallId": "e1", "toolCallName": "execute"},
            {
                "type": "TOOL_CALL_ARGS",
                "toolCallId": "e1",
                "delta": '{"password":"do-not-display","query":"token=redacted-value"}',
            },
            {
                "type": "TOOL_CALL_RESULT",
                "toolCallId": "e1",
                "content": "Traceback /srv/app.py authorization=Bearer redacted-value https://internal.example",
                "isError": True,
            },
            {"type": "RUN_FINISHED"},
        ]
    )

    content = frames[-1].content
    assert "执行失败，详细原因请查看服务日志" in content
    for sensitive_text in (
        "do-not-display",
        "token=redacted-value",
        "Bearer redacted-value",
        "/srv/app.py",
        "internal.example",
    ):
        assert sensitive_text not in content


def test_tool_block_and_thinking_coexist():
    """thinking 走 <think> 折叠区，工具块留在正文，两者不能互相吞掉。"""
    frames = _chat_frames(
        [
            {"type": "THINKING_TEXT_MESSAGE_CONTENT", "delta": "需要先激活技能"},
            {"type": "TOOL_CALL_START", "toolCallId": "t1", "toolCallName": "activate_skill"},
            {"type": "TOOL_CALL_RESULT", "toolCallId": "t1", "content": "ok", "duration": 5, "isError": False},
            {"type": "RUN_FINISHED"},
        ]
    )

    content = frames[-1].content
    assert content.startswith("<think>需要先激活技能</think>")
    assert "🟢 **activate_skill** · 已完成 · 5ms" in content


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
    assert frames[0].content == STREAM_ERROR_REPLY
    assert "upstream timeout" not in frames[0].content


@patch(
    "aidev_wxbot.wxaibot.direct_stream.AgentHelper.build_session_detail_url",
    return_value="https://agent.example.com/chat-window/?session=session-1",
)
def test_pending_tool_approval_is_pushed_with_safe_ticket_link(mock_detail_url):
    frames = _chat_frames(
        [
            {"type": "TEXT_MESSAGE_CONTENT", "delta": "我将获取 Skill 的详细信息。"},
            {
                "type": "RUN_FINISHED",
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [
                        {
                            "id": "int-approval-call-1-DE001",
                            "reason": "aidev:tool_approval",
                            "message": "执行工具前需要人工审批。",
                            "callbackToken": "must-not-leak",
                            "metadata": {
                                "ticket": {
                                    "sn": "DE001",
                                    "title": "执行「retrieve_private_v1_skills」需要审批",
                                    "url": "https://itsm.example.com/ticket/DE001?a=1 2",
                                }
                            },
                        }
                    ],
                },
            },
        ]
    )

    assert frames[-1].finish
    assert frames[-1].pending_approval
    assert "我将获取 Skill 的详细信息。" in frames[-1].content
    assert "等待工具审批" in frames[-1].content
    assert "DE001" in frames[-1].content
    assert "[查看并处理审批](https://itsm.example.com/ticket/DE001?a=1%202)" in frames[-1].content
    assert "[查看会话进度](https://agent.example.com/chat-window/?session=session-1)" in frames[-1].content
    assert "must-not-leak" not in frames[-1].content
    mock_detail_url.assert_called_once_with("s")


@patch("aidev_wxbot.wxaibot.direct_stream.AgentHelper.build_session_detail_url", return_value="")
def test_pending_tool_approval_drops_non_http_ticket_url(_mock_detail_url):
    frames = _chat_frames(
        [
            {
                "type": "RUN_FINISHED",
                "outcome": {
                    "type": "interrupt",
                    "interrupts": [
                        {
                            "reason": "aidev:tool_approval",
                            "metadata": {"ticket": {"sn": "DE002", "url": "javascript:alert(1)"}},
                        }
                    ],
                },
            }
        ]
    )

    assert "DE002" in frames[-1].content
    assert "javascript" not in frames[-1].content


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
