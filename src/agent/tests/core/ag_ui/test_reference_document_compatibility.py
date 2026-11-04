import copy
import json
from unittest.mock import Mock

import pytest
from ag_ui.core import EventType
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.reference_documents import reference_documents_for_display
from aidev_agent.core.ag_ui.utils import contents_to_agui_messages
from aidev_agent.core.tools.a2a_tools.utils import collect_knowledge_references
from aidev_agent.services.event_handlers.base import BaseSessionWriter

SOURCE = "https://example.com/docs/source"
PREVIEW = "https://example.com/base/agent-develop/knowledgebase?knowledgeName=A%2BB%20%26%20C&anchorPath=%2F1#part"
BROKEN_PREVIEW = PREVIEW.replace("/agent-develop/", "//agent-develop/")
NATIVE_DOCUMENT = {"name": "Guide", "url": SOURCE, "originFile": BROKEN_PREVIEW}


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


@pytest.mark.asyncio
async def test_agui_adapts_links_without_changing_native_retrieval():
    event = await convert([NATIVE_DOCUMENT])
    assert event.type == EventType.CUSTOM
    assert event.name == "knowledge_rag_result"
    assert event.value[0]["url"] == PREVIEW
    assert event.value[0]["originFile"] == SOURCE
    assert event.value[0]["metadata"]["path"] == SOURCE
    assert event.value[0]["metadata"]["preview_path"] == PREVIEW


@pytest.mark.asyncio
@pytest.mark.parametrize("origin_key", ["originFile", "origin_file"])
async def test_existing_preview_first_events_keep_their_source_and_preview(origin_key):
    event = await convert([{"name": "Guide", "url": BROKEN_PREVIEW, origin_key: SOURCE}])
    assert event.value[0]["url"] == PREVIEW
    assert event.value[0]["originFile"] == SOURCE
    assert event.value[0]["metadata"]["path"] == SOURCE


@pytest.mark.parametrize("origin_key", ["originFile", "origin_file"])
@pytest.mark.parametrize("activity_type", ["reference_document", "knowledge_rag"])
def test_history_adapts_old_documents_without_mutating_saved_records(origin_key, activity_type):
    document = {"name": "Guide", "url": SOURCE, origin_key: BROKEN_PREVIEW}
    content = [document] if activity_type == "reference_document" else {"reference_document": [document]}
    records = [{"id": "old", "role": "activity", "activity_type": activity_type, "content": content}]
    original = copy.deepcopy(records)
    result = contents_to_agui_messages(records)[0].content
    docs = result if isinstance(result, list) else result["referenceDocument"]
    assert docs[0]["url"] == PREVIEW
    assert docs[0]["originFile"] == SOURCE
    assert records == original


@pytest.mark.asyncio
async def test_new_agui_and_old_events_keep_the_same_agent_sources():
    event = await convert([NATIVE_DOCUMENT])
    native = {"type": "CUSTOM", "name": "knowledge_rag_result", "value": [NATIVE_DOCUMENT]}
    references = collect_knowledge_references([native, event.model_dump()])
    assert len(references) == 1
    assert references[0].url == SOURCE


@pytest.mark.asyncio
async def test_live_and_persisted_references_have_the_same_display_contract():
    event = await convert([NATIVE_DOCUMENT])
    writer = MemoryWriter.__new__(MemoryWriter)
    writer._written_message_ids = set()
    writer._create_session_content = Mock()
    writer.handle_reference_document(event)
    saved = json.loads(writer._create_session_content.call_args.kwargs["content"])
    assert saved[0]["url"] == SOURCE
    assert saved[0]["origin_file"] == BROKEN_PREVIEW
    record = {"id": "old", "role": "activity", "activity_type": "reference_document", "content": saved}
    restored = contents_to_agui_messages([record])[0].content[0]
    for key in ("name", "url", "originFile", "metadata"):
        assert restored[key] == event.value[0][key]
    assert restored["origin_file"] == BROKEN_PREVIEW


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
    "source,preview,expected_source,expected_preview",
    [
        (SOURCE, "", SOURCE, SOURCE),
        ("", PREVIEW, PREVIEW, PREVIEW),
        (BROKEN_PREVIEW, BROKEN_PREVIEW, PREVIEW, PREVIEW),
        (SOURCE, "https://example.com/a//b?x=1+2#fragment", SOURCE, "https://example.com/a//b?x=1+2#fragment"),
        (SOURCE, "http://[", SOURCE, "http://["),
        (
            SOURCE + "?next=/agent-develop/knowledgebase",
            BROKEN_PREVIEW,
            SOURCE + "?next=/agent-develop/knowledgebase",
            PREVIEW,
        ),
        (
            SOURCE,
            "https://example.com//agent-develop/knowledgebase-other",
            SOURCE,
            "https://example.com//agent-develop/knowledgebase-other",
        ),
    ],
)
def test_only_available_links_are_used_and_unrelated_urls_are_preserved(
    source, preview, expected_source, expected_preview
):
    result = reference_documents_for_display([{"url": source, "originFile": preview}])[0]
    assert result["name"]
    assert result["url"] == expected_preview
    assert result["originFile"] == expected_source


@pytest.mark.parametrize("document", [None, "bad", {"name": "No links"}, {"url": 7, "originFile": None}])
def test_documents_without_usable_reference_fields_pass_through(document):
    assert reference_documents_for_display([document]) == [document]


@pytest.mark.parametrize("metadata,expected", [({"path": SOURCE}, SOURCE), ({"preview_path": PREVIEW}, PREVIEW)])
def test_explicit_metadata_with_only_one_link_keeps_source_identity(metadata, expected):
    result = reference_documents_for_display([{"metadata": metadata}])[0]
    assert result["url"] == expected
    assert result["originFile"] == expected
    assert result["metadata"]["path"] == metadata.get("path", "")
