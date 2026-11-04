import json
import time
from unittest.mock import Mock, patch

import pytest
from aidev_wxbot.wxaibot.context import LlmChunkMsg
from aidev_wxbot.wxaibot.direct_stream import AgentStream, iter_direct_stream_frames
from aidev_wxbot.wxaibot.references import collect_reference_documents
from aidev_wxbot.wxaibot.stream import consume_chat_stream

REFERENCE = {"name": "Guide", "url": "https://example.com/source", "originFile": "https://example.com/preview"}
EVENT = {"type": "CUSTOM", "name": "knowledge_rag_result", "value": [REFERENCE]}


def sse(events):
    return iter("data: " + json.dumps(event) + "\n\n" for event in events)


@pytest.mark.parametrize(
    "event,expected",
    [
        (EVENT, {"display_name": "Guide", "path": REFERENCE["url"], "preview_path": REFERENCE["originFile"]}),
        (
            {"type": "CUSTOM", "documents": [{"metadata": {"display_name": "Old", "path": REFERENCE["url"], "id": 1}}]},
            {"display_name": "Old", "path": REFERENCE["url"], "id": 1},
        ),
        (
            {**EVENT, "value": [{"name": "Preview", "originFile": REFERENCE["originFile"]}]},
            {"display_name": "Preview", "path": REFERENCE["originFile"], "preview_path": REFERENCE["originFile"]},
        ),
    ],
)
def test_normalize_new_and_legacy_references_without_duplicates(event, expected):
    documents = []
    collect_reference_documents(event, documents)
    collect_reference_documents(event, documents)
    assert documents == [expected]


@pytest.mark.parametrize("value", [None, "bad", [None, {}, {"name": "no URL"}]])
def test_malformed_references_are_ignored(value):
    documents = []
    collect_reference_documents({**EVENT, "value": value}, documents)
    assert documents == []


def test_queue_transport_preserves_sdk_reference_events():
    events = [EVENT, EVENT, {"type": "TEXT_MESSAGE_CONTENT", "delta": "answer"}]
    with patch.object(LlmChunkMsg, "append_to_cache", autospec=True) as append:
        consume_chat_stream(sse(events), "example-stream", time.time(), Mock())
    message = append.call_args.args[0]
    assert message.content == "answer"
    assert len(message.docs) == 1
    assert "本次检索相关文档" in message.docs_content
    assert REFERENCE["url"] in message.docs_content


def test_direct_transport_appends_sdk_references_once():
    events = [
        {"type": "RUN_STARTED", "runId": "example-run"},
        EVENT,
        EVENT,
        {"type": "TEXT_MESSAGE_CONTENT", "delta": "answer"},
        {"type": "RUN_FINISHED"},
    ]
    stream = AgentStream(kind="chat", session_code="example-session", generator=sse(events))
    frames = list(iter_direct_stream_frames(stream, "example-stream"))
    assert frames[-1].finish
    assert "answer" in frames[-1].content
    assert "本次检索相关文档" in frames[-1].content
    assert frames[-1].content.count(REFERENCE["url"]) == 1
