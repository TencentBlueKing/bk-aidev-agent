import json
import time
from unittest.mock import Mock, patch

import pytest
from aidev_agent.core.ag_ui.reference_documents import reference_documents_for_display
from aidev_wxbot.wxaibot.context import LlmChunkMsg, format_reference_documents
from aidev_wxbot.wxaibot.direct_stream import AgentStream, iter_direct_stream_frames
from aidev_wxbot.wxaibot.references import collect_reference_documents
from aidev_wxbot.wxaibot.stream import consume_chat_stream

REFERENCE = {"name": "Guide", "url": "https://example.com/source", "originFile": "https://example.com/preview"}
EVENT = {"type": "CUSTOM", "name": "knowledge_rag_result", "value": [REFERENCE]}
CITED_EVENT = {
    **EVENT,
    "value": [
        {"name": "A", "url": "https://example.com/a", "citation_index": 1},
        {"name": "B", "url": "https://example.com/b", "citation_index": 2},
        {"name": "C", "url": "https://example.com/c", "citation_index": 3},
    ],
}
CITED_ANSWER = "- 结论一[3]\n- 结论二[1][3]"


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


@pytest.mark.parametrize("display_adapted", [False, True])
def test_queue_transport_preserves_sdk_reference_events(display_adapted):
    event = {**EVENT, "value": reference_documents_for_display(EVENT["value"])} if display_adapted else EVENT
    events = [event, event, {"type": "TEXT_MESSAGE_CONTENT", "delta": "answer"}]
    with patch.object(LlmChunkMsg, "append_to_cache", autospec=True) as append:
        consume_chat_stream(sse(events), "example-stream", time.time(), Mock())
    message = append.call_args.args[0]
    assert message.content == "answer"
    assert len(message.docs) == 1
    assert "本次检索相关文档" in message.docs_content
    assert REFERENCE["url"] in message.docs_content


@pytest.mark.parametrize("display_adapted", [False, True])
def test_direct_transport_appends_sdk_references_once(display_adapted):
    event = {**EVENT, "value": reference_documents_for_display(EVENT["value"])} if display_adapted else EVENT
    events = [
        {"type": "RUN_STARTED", "runId": "example-run"},
        event,
        event,
        {"type": "TEXT_MESSAGE_CONTENT", "delta": "answer"},
        {"type": "RUN_FINISHED"},
    ]
    stream = AgentStream(kind="chat", session_code="example-session", generator=sse(events))
    frames = list(iter_direct_stream_frames(stream, "example-stream"))
    assert frames[-1].finish
    assert "answer" in frames[-1].content
    assert "本次检索相关文档" in frames[-1].content
    assert frames[-1].content.count(REFERENCE["url"]) == 1


@pytest.mark.parametrize("display_adapted", [False, True])
def test_citation_numbers_survive_collection(display_adapted):
    event = {**CITED_EVENT, "value": reference_documents_for_display(CITED_EVENT["value"])}
    documents = []
    collect_reference_documents(event if display_adapted else CITED_EVENT, documents)
    assert [(document["display_name"], document["citation_index"]) for document in documents] == [
        ("A", 1),
        ("B", 2),
        ("C", 3),
    ]


def test_format_lists_only_cited_documents_in_a_separate_section():
    documents = []
    collect_reference_documents(CITED_EVENT, documents)
    text = format_reference_documents(documents, CITED_ANSWER)
    assert text == "\n\n---\n\n**参考文档**\n\n[1] [A](https://example.com/a)\n\n[3] [C](https://example.com/c)\n"


@pytest.mark.parametrize("transport", ["queue", "direct"])
def test_missing_markers_use_named_document_in_both_transports(transport):
    answer = "根据《共享Node优化报告》，内存占用下降。"
    event = {**CITED_EVENT, "value": [dict(item) for item in CITED_EVENT["value"]]}
    event["value"][0]["name"] = "共享Node优化报告"
    events = [event, {"type": "TEXT_MESSAGE_CONTENT", "delta": answer}, {"type": "RUN_FINISHED"}]
    if transport == "queue":
        with patch.object(LlmChunkMsg, "append_to_cache", autospec=True) as append:
            consume_chat_stream(sse(events), "example-stream", time.time(), Mock())
        content = append.call_args.args[0].docs_content
    else:
        stream = AgentStream(kind="chat", session_code="example-session", generator=sse(events))
        content = list(iter_direct_stream_frames(stream, "example-stream"))[-1].content
    assert "**参考文档**" in content
    assert "[1] [共享Node优化报告](https://example.com/a)" in content
    assert "https://example.com/b" not in content
    assert "https://example.com/c" not in content


@pytest.mark.parametrize("answer", ["没有标注", "编号对不上[9]"])
def test_format_falls_back_to_all_retrieved_documents(answer):
    documents = []
    collect_reference_documents(CITED_EVENT, documents)
    text = format_reference_documents(documents, answer)
    assert text.startswith("\n\n---\n\n**本次检索相关文档**\n\n")
    assert [paragraph.split(" ")[0] for paragraph in text.strip().split("\n\n")[2:]] == ["[1]", "[2]", "[3]"]


def test_queue_transport_lists_documents_cited_by_the_answer():
    events = [CITED_EVENT, {"type": "TEXT_MESSAGE_CONTENT", "delta": CITED_ANSWER}]
    with patch.object(LlmChunkMsg, "append_to_cache", autospec=True) as append:
        consume_chat_stream(sse(events), "example-stream", time.time(), Mock())
    message = append.call_args.args[0]
    assert "**参考文档**" in message.docs_content
    assert "https://example.com/b" not in message.docs_content


def test_queue_poll_appends_cited_documents_after_the_answer(settings):
    documents = []
    collect_reference_documents(CITED_EVENT, documents)
    body = {"content": CITED_ANSWER, "think_content": "思考", "is_finish": True, "docs": documents}
    client = Mock()
    client.get_queue_info.return_value = {"message_count": 1}
    client.get_message.side_effect = [{"body": body}]
    settings.MAX_MESSAGE_TIME = 300
    stream_id = f"example_{int(time.time())}"
    content = LlmChunkMsg(stream_id=stream_id).wxaibot_msg_json_from_cache(client)["stream"]["content"]
    assert content.startswith("<think>思考</think>" + CITED_ANSWER + "\n\n---\n\n**参考文档**\n\n")
    assert "https://example.com/b" not in content


def test_direct_transport_lists_documents_cited_by_the_answer():
    events = [
        {"type": "RUN_STARTED", "runId": "example-run"},
        CITED_EVENT,
        {"type": "TEXT_MESSAGE_CONTENT", "delta": CITED_ANSWER},
        {"type": "RUN_FINISHED"},
    ]
    stream = AgentStream(kind="chat", session_code="example-session", generator=sse(events))
    content = list(iter_direct_stream_frames(stream, "example-stream"))[-1].content
    assert content.endswith(
        "\n\n---\n\n**参考文档**\n\n[1] [A](https://example.com/a)\n\n[3] [C](https://example.com/c)\n"
    )
