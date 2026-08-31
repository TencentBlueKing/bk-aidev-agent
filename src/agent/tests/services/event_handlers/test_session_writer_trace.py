# -*- coding: utf-8 -*-
"""Session content retains the entry trace after the request context changes."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter


@pytest.mark.parametrize("entry_trace", ["a" * 32, None])
def test_create_session_content_keeps_entry_trace(entry_trace):
    client = MagicMock()
    with patch("aidev_agent.services.event_handlers.base.get_current_trace_id", return_value=entry_trace) as current:
        writer = AGUISessionWriter("session", client, turn_id="turn")
        current.return_value = "b" * 32
        for role in ("user", "assistant"):
            writer._create_session_content(role, role, "hello", "complete", {})
        writer._update_session_content(1, "assistant", "updated", {})

    for call in client.api.create_chat_session_content.call_args_list:
        prop = call.kwargs["json"]["property"]
        assert prop.get("trace_id") == entry_trace
        assert prop["turn_id"] == "turn"
    assert "trace_id" not in client.api.update_chat_session_content.call_args.kwargs["json"]["property"]


def test_writers_do_not_share_trace_between_chat_requests():
    client = MagicMock()
    with patch("aidev_agent.services.event_handlers.base.get_current_trace_id", side_effect=["a" * 32, "b" * 32]):
        first = AGUISessionWriter("session", client)
        second = AGUISessionWriter("session", client)

    first._create_session_content("first", "user", "hello", "complete", {})
    second._create_session_content("second", "user", "hello again", "complete", {})

    assert [
        call.kwargs["json"]["property"]["trace_id"] for call in client.api.create_chat_session_content.call_args_list
    ] == ["a" * 32, "b" * 32]


def test_entry_trace_survives_writing_without_request_context():
    trace = pytest.importorskip("opentelemetry.trace")
    client = MagicMock()
    span = trace.NonRecordingSpan(trace.SpanContext(trace_id=int("a" * 32, 16), span_id=1, is_remote=False))
    with trace.use_span(span):
        writer = AGUISessionWriter("session", client)

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(writer._create_session_content, "message", "assistant", "hello", "complete", {}).result()

    payload = client.api.create_chat_session_content.call_args.kwargs["json"]
    assert payload["property"]["trace_id"] == "a" * 32
