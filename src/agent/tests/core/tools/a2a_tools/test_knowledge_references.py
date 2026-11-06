import json
from dataclasses import dataclass
from typing import Any, Literal

import pytest
from aidev_agent.api.bk_agent import Client as BkAgentApiClient
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.tools.a2a_tools.bkai_backend import BkAiBackend
from aidev_agent.core.tools.a2a_tools.local_backend import LocalBackend
from aidev_agent.core.tools.a2a_tools.provider import AgentBackendResolver, get_agent_tools
from aidev_agent.core.tools.a2a_tools.types import AgentResult, AgentSpec, KnowledgeReference
from aidev_agent.core.tools.a2a_tools.utils import build_enriched_result, collect_knowledge_references
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from pydantic import BaseModel, ConfigDict

PREVIEW = "https://example.com/agent-develop/knowledgebase?previewAnchorPath=%2F1%2Fa.md"
REFERENCE = {"name": "Guide", "url": "https://example.com/source", "originFile": PREVIEW}
FILE_REFERENCE = {"name": "a.md", "url": PREVIEW, "originFile": PREVIEW}
EVENT = {"type": "CUSTOM", "name": "knowledge_rag_result", "value": [REFERENCE]}


class MemoryWriter(BaseSessionWriter):
    def _do_create_content(self, payload, headers):
        return None


class LegacyAgentResult(BaseModel):
    """The result contract before references were introduced."""

    model_config = ConfigDict(frozen=True, use_enum_values=True)
    status: Literal["completed", "failed", "interrupted"]
    agent_type: str = ""
    result: str = ""
    error: str | None = None
    tool_calls: int = 0
    exit_reason: str = "completed"


@pytest.mark.parametrize("status", ["completed", "failed", "interrupted"])
@pytest.mark.parametrize("with_references", [False, True])
def test_old_result_consumers_and_frozen_result_keys_remain_compatible(status, with_references):
    old = LegacyAgentResult(status=status, agent_type="local", result="answer", tool_calls=2)
    references = [KnowledgeReference(name="Guide", url=REFERENCE["url"])] if with_references else []
    result = AgentResult(**old.model_dump(), references=references)
    serialized = result.model_dump_json()
    assert LegacyAgentResult.model_validate_json(serialized) == old
    assert {result: "cached"}[result] == "cached"
    if not with_references:
        assert json.loads(serialized) == old.model_dump()


@dataclass
class LocalContext:
    resource_manager: Any
    event_handler: Any = None
    session_code: str = ""
    session_context_data: Any = None


@pytest.fixture(params=[BkAiBackend, LocalBackend])
def backend_case(request, mocker):
    backend = request.param()
    if request.param is BkAiBackend:
        params = {"client": mocker.Mock(spec=BkAgentApiClient)}
        backend_type = "bkai"
    else:
        params = {"agent_cls": mocker.Mock(), "ctx": LocalContext(resource_manager=mocker.Mock())}
        backend_type = "local"
    mocker.patch.object(backend, "_prepare_session", return_value=[])
    return backend, AgentSpec(name="child", description="test", backend_type=backend_type, params=params)


@pytest.mark.parametrize(
    "event",
    [
        EVENT,
        {
            "event": "reference_doc",
            "documents": [
                {
                    "metadata": {
                        "display_name": REFERENCE["name"],
                        "path": REFERENCE["url"],
                        "preview_path": REFERENCE["originFile"],
                    }
                }
            ],
        },
    ],
)
def test_collect_references_deduplicates_current_run_sources(event):
    history = {"type": "MESSAGES_SNAPSHOT", "messages": [{"content": [REFERENCE]}]}
    references = collect_knowledge_references([history, event, event])
    assert [reference.model_dump() for reference in references] == [
        {"name": "Guide", "url": REFERENCE["url"], "preview_url": REFERENCE["originFile"]}
    ]


@pytest.mark.parametrize("value", [None, "bad", [None, {}, {"name": "no source"}]])
def test_invalid_reference_events_leave_old_result_shape_unchanged(value):
    references = collect_knowledge_references([{**EVENT, "value": value}])
    result = build_enriched_result(status="completed", summary="answer", references=references)
    assert result.result == "answer"
    assert "references" not in result.model_dump()


@pytest.mark.parametrize("field", ["url", "originFile"])
def test_reference_without_title_keeps_a_usable_label(field):
    references = collect_knowledge_references([{**EVENT, "value": [{field: REFERENCE["url"]}]}])
    assert references[0].name == REFERENCE["url"]
    assert (references[0].url or references[0].preview_url) == REFERENCE["url"]


@pytest.mark.parametrize(
    "document",
    [FILE_REFERENCE, {"metadata": {"display_name": "a.md", "path": PREVIEW, "preview_path": PREVIEW}}],
)
def test_uploaded_and_zip_knowledge_only_keep_the_preview(document):
    references = collect_knowledge_references([{**EVENT, "value": [document]}])
    assert [reference.model_dump() for reference in references] == [{"name": "a.md", "url": "", "preview_url": PREVIEW}]


def test_backends_preserve_references_in_serialized_result(backend_case, mocker):
    backend, spec = backend_case
    mocker.patch.object(backend, "_run_subagent", return_value=("answer", [EVENT], 1))
    result = backend.execute(spec, "question", session_code="example-session")
    serialized = json.loads(result.model_dump_json())
    assert serialized["result"] == "answer"
    assert serialized["references"][0]["url"] == REFERENCE["url"]
    assert serialized["references"][0]["preview_url"] == REFERENCE["originFile"]


def run_agent_tool(tool_name, references, mocker, dispatch):
    backend = mocker.Mock()
    backend.execute.return_value = AgentResult(status="completed", result="answer", references=references)
    resolver = AgentBackendResolver().register("bkai", mocker.Mock(return_value=backend))
    spec = AgentSpec(name="child", description="test", backend_type="bkai")
    tool = next(tool for tool in get_agent_tools([spec], resolver) if tool.name == tool_name)
    mocker.patch("aidev_agent.core.tools.a2a_tools.provider.dispatch_custom_event", side_effect=dispatch)
    args = {"agent_name": "child"} if tool_name == "Agent" else {"member_name": "member"}
    state = {"bk_agent_team": {"member": {"agent_name": "child", "session_code": "example-session"}}}
    return json.loads(tool.func(message="question", config={"callbacks": [object()]}, state=state, **args))


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["Agent", "sendMessages"])
@pytest.mark.parametrize(
    "reference,origin",
    [
        (KnowledgeReference(name="Guide", url=REFERENCE["url"], preview_url=PREVIEW), REFERENCE["url"]),
        (KnowledgeReference(name="a.md", preview_url=PREVIEW), ""),
    ],
)
async def test_provider_replays_references_as_a_complete_knowledge_retrieval(tool_name, reference, origin, mocker):
    dispatched = []
    result = run_agent_tool(tool_name, [reference], mocker, lambda name, data, config: dispatched.append((name, data)))
    assert result["references"][0]["url"] == reference.url
    assert [name for name, _ in dispatched] == ["knowledge_rag_start", "knowledge_rag_result", "knowledge_rag_end"]
    agent = AidevAGUIAgent.__new__(AidevAGUIAgent)
    raw = {"name": dispatched[1][0], "data": dispatched[1][1]}
    event = [each async for each in agent._handle_on_custom_event(raw)][0]
    assert (event.value[0]["name"], event.value[0]["url"], event.value[0]["originFile"]) == (
        reference.name,
        PREVIEW,
        origin,
    )
    writer = MemoryWriter.__new__(MemoryWriter)
    writer._written_message_ids, writer._create_session_content = set(), mocker.Mock()
    writer.handle_reference_document(event)
    assert writer._create_session_content.call_args.kwargs["builtin_property"]["type"] == "reference_document"


def test_provider_skips_retrieval_events_without_references(mocker):
    dispatch = mocker.Mock()
    result = run_agent_tool("Agent", [], mocker, dispatch)
    assert "references" not in result
    dispatch.assert_not_called()
