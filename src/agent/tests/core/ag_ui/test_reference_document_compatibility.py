import copy
import json
from unittest.mock import Mock

import pytest
from ag_ui.core import EventType
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.reference_documents import (
    history_reference_documents,
    reference_documents_for_display,
    resolve_reference_links,
)
from aidev_agent.core.tools.a2a_tools.utils import collect_knowledge_references
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from aidev_agent.utils.migrations import migration_chat_session_context_from_chat_session_contents_v1

SOURCE = "https://example.com/docs/source"
PREVIEW = "https://example.com/base/agent-develop/knowledgebase?knowledgeName=A%2BB%20%26%20C&anchorPath=%2F1#part"
BROKEN_PREVIEW = PREVIEW.replace("/agent-develop/", "//agent-develop/")
LINK_DOCUMENT = {"name": "Guide", "url": SOURCE, "originFile": BROKEN_PREVIEW}
FILE_DOCUMENT = {"name": "a.md", "url": BROKEN_PREVIEW, "originFile": BROKEN_PREVIEW}


class MemoryWriter(BaseSessionWriter):
    def _do_create_content(self, payload, headers):
        return None


async def convert(documents):
    raw = {"name": "knowledge_rag_result", "data": {"message_id": "reference", "data": documents, "duration": 7}}
    original = copy.deepcopy(raw)
    agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
    events = [event async for event in agent._handle_on_custom_event(raw)]
    assert raw == original
    assert events[0].raw_event == original
    return events[0]


def persist(event):
    writer = MemoryWriter.__new__(MemoryWriter)
    writer._written_message_ids = set()
    writer._create_session_content = Mock()
    writer.handle_reference_document(event)
    kwargs = writer._create_session_content.call_args.kwargs
    return {
        "id": 7,
        "role": "activity",
        "status": "success",
        "content": json.loads(kwargs["content"]),
        "activity_type": kwargs["builtin_property"]["type"],
        "property": {"builtin_property": kwargs["builtin_property"]},
    }


def snapshot(records):
    session_context = migration_chat_session_context_from_chat_session_contents_v1(records)
    agent = ChatCompletionAgent(chat_history=[ChatPrompt.model_validate(each) for each in session_context])
    return agent._build_snapshot_agui_messages()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "document,origin",
    [(LINK_DOCUMENT, SOURCE), (FILE_DOCUMENT, ""), ({"url": SOURCE, "originFile": SOURCE}, "")],
)
async def test_agui_shows_original_link_only_for_external_knowledge(document, origin):
    event = await convert([document])
    assert event.type == EventType.CUSTOM
    assert event.name == "knowledge_rag_result"
    assert event.value[0]["url"] == (SOURCE if document["url"] == SOURCE and not origin else PREVIEW)
    assert event.value[0]["originFile"] == origin


@pytest.mark.asyncio
@pytest.mark.parametrize("origin_key", ["originFile", "origin_file"])
async def test_existing_preview_first_events_keep_their_source_and_preview(origin_key):
    event = await convert([{"name": "Guide", "url": BROKEN_PREVIEW, origin_key: SOURCE}])
    assert event.value[0]["url"] == PREVIEW
    assert event.value[0]["originFile"] == SOURCE
    assert event.value[0]["metadata"]["path"] == SOURCE


@pytest.mark.asyncio
@pytest.mark.parametrize("document,origin", [(LINK_DOCUMENT, SOURCE), (FILE_DOCUMENT, "")])
@pytest.mark.parametrize("activity_type", ["reference_document", "knowledge_rag"])
async def test_history_snapshot_matches_live_display_without_mutating_saved_records(document, origin, activity_type):
    event = await convert([document])
    record = persist(event)
    if activity_type == "knowledge_rag":
        record = {**record, "activity_type": activity_type, "content": {"reference_document": record["content"]}}
    original = copy.deepcopy(record)
    content = snapshot([record])[0]["content"]
    restored = (content if activity_type == "reference_document" else content["reference_document"])[0]
    assert record == original
    assert {key: restored[key] for key in ("name", "url", "originFile", "metadata")} == {
        key: event.value[0][key] for key in ("name", "url", "originFile", "metadata")
    }
    assert restored["origin_file_url"] == origin
    assert "origin_file" not in restored


@pytest.mark.asyncio
async def test_history_snapshot_reads_the_saved_activity_type_without_platform_flattening():
    record = persist(await convert([FILE_DOCUMENT]))
    record.pop("activity_type")
    restored = snapshot([record])[0]["content"][0]
    assert (restored["url"], restored["originFile"], restored["origin_file_url"]) == (PREVIEW, "", "")


@pytest.mark.parametrize(
    "content,activity_type",
    [([{"name": "plain", "url": SOURCE}], "reference_document"), ({"reference_document": "bad"}, "knowledge_rag")],
)
def test_history_keeps_unrecognized_reference_content(content, activity_type):
    assert history_reference_documents(content, activity_type) == content
    assert history_reference_documents(content, "flow_agent") is content


@pytest.mark.asyncio
@pytest.mark.parametrize("document,url", [(LINK_DOCUMENT, SOURCE), (FILE_DOCUMENT, "")])
async def test_new_agui_and_old_events_keep_the_same_agent_sources(document, url):
    event = await convert([document])
    native = {"type": "CUSTOM", "name": "knowledge_rag_result", "value": [document]}
    references = collect_knowledge_references([native, event.model_dump()])
    assert [(reference.url, reference.preview_url) for reference in references] == [(url, PREVIEW)]


@pytest.mark.parametrize("value", [None, "bad", {"unexpected": "shape"}])
def test_non_list_payloads_keep_the_existing_passthrough_behavior(value):
    assert reference_documents_for_display(value) is value


def test_display_adapter_keeps_extra_metadata_and_is_idempotent():
    document = {"name": "Guide", "url": "unused", "metadata": {"id": 1, "path": SOURCE, "preview_path": PREVIEW}}
    once = reference_documents_for_display([document])
    assert once[0]["metadata"]["id"] == 1
    assert once[0]["url"] == PREVIEW
    assert once[0]["originFile"] == SOURCE
    assert reference_documents_for_display(once) == once


@pytest.mark.parametrize("key", ["origin_file_url", "originFileUrl"])
def test_legacy_preview_first_fields_remain_available(key):
    document = {"name": "Guide", "url": BROKEN_PREVIEW, key: SOURCE}
    result = reference_documents_for_display([document])[0]
    assert result[key] == SOURCE
    assert result["url"] == PREVIEW
    assert result["originFile"] == SOURCE


@pytest.mark.parametrize(
    "source,preview,expected_url,expected_origin",
    [
        (SOURCE, "", SOURCE, ""),
        ("", PREVIEW, PREVIEW, ""),
        (BROKEN_PREVIEW, BROKEN_PREVIEW, PREVIEW, ""),
        (SOURCE, "https://example.com/a//b?x=1+2#fragment", "https://example.com/a//b?x=1+2#fragment", SOURCE),
        (SOURCE, "http://[", "http://[", SOURCE),
        (
            SOURCE + "?next=/agent-develop/knowledgebase",
            BROKEN_PREVIEW,
            PREVIEW,
            SOURCE + "?next=/agent-develop/knowledgebase",
        ),
        (
            SOURCE,
            "https://example.com//agent-develop/knowledgebase-other",
            "https://example.com//agent-develop/knowledgebase-other",
            SOURCE,
        ),
    ],
)
def test_only_available_links_are_used_and_unrelated_urls_are_preserved(source, preview, expected_url, expected_origin):
    result = reference_documents_for_display([{"url": source, "originFile": preview}])[0]
    assert result["name"]
    assert result["url"] == expected_url
    assert result["originFile"] == expected_origin


@pytest.mark.parametrize(
    "document", [None, "bad", {"name": "No links"}, {"url": 7, "originFile": None}, {"name": "x", "url": SOURCE}]
)
def test_documents_without_usable_reference_fields_pass_through(document):
    assert reference_documents_for_display([document]) == [document]


@pytest.mark.parametrize(
    "metadata,expected",
    [({"path": SOURCE}, (SOURCE, "")), ({"preview_path": PREVIEW}, (PREVIEW, "")), ({"path": " "}, None)],
)
def test_explicit_metadata_with_only_one_link_keeps_source_identity(metadata, expected):
    result = reference_documents_for_display([{"metadata": metadata}])[0]
    assert ((result["url"], result["originFile"]) if expected else result) == (expected or {"metadata": metadata})


@pytest.mark.parametrize(
    "document,expected",
    [
        ({"metadata": {"path": SOURCE, "preview_path": PREVIEW}}, (SOURCE, PREVIEW, SOURCE)),
        ({"metadata": {"path": PREVIEW, "preview_path": PREVIEW}}, (PREVIEW, PREVIEW, "")),
        ({"metadata": {"path": BROKEN_PREVIEW, "preview_path": PREVIEW}}, (PREVIEW, PREVIEW, "")),
        ({"url": SOURCE}, (SOURCE, "", SOURCE)),
        ({"url": BROKEN_PREVIEW}, ("", PREVIEW, "")),
    ],
)
def test_only_web_knowledge_resolves_an_external_link(document, expected):
    links = resolve_reference_links(document)
    assert (links.path, links.preview, links.external) == expected
