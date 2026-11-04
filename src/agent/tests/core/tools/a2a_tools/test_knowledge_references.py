import json
from dataclasses import dataclass
from typing import Any

import pytest
from aidev_agent.api.bk_agent import Client as BkAgentApiClient
from aidev_agent.core.tools.a2a_tools.bkai_backend import BkAiBackend
from aidev_agent.core.tools.a2a_tools.local_backend import LocalBackend
from aidev_agent.core.tools.a2a_tools.provider import AgentBackendResolver, get_agent_tools
from aidev_agent.core.tools.a2a_tools.types import AgentResult, AgentSpec, KnowledgeReference
from aidev_agent.core.tools.a2a_tools.utils import build_enriched_result, collect_knowledge_references

REFERENCE = {"name": "Guide", "url": "https://example.com/source", "originFile": "https://example.com/preview"}
EVENT = {"type": "CUSTOM", "name": "knowledge_rag_result", "value": [REFERENCE]}


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


def test_backends_preserve_references_in_serialized_result(backend_case, mocker):
    backend, spec = backend_case
    mocker.patch.object(backend, "_run_subagent", return_value=("answer", [EVENT], 1))
    result = backend.execute(spec, "question", session_code="example-session")
    serialized = json.loads(result.model_dump_json())
    assert serialized["result"] == "answer"
    assert serialized["references"][0]["url"] == REFERENCE["url"]
    assert serialized["references"][0]["preview_url"] == REFERENCE["originFile"]


@pytest.mark.parametrize("tool_name", ["Agent", "sendMessages"])
def test_provider_keeps_references_for_model_and_frontend(tool_name, mocker):
    reference = KnowledgeReference(name="Guide", url=REFERENCE["url"], preview_url=REFERENCE["originFile"])
    backend = mocker.Mock()
    backend.execute.return_value = AgentResult(status="completed", result="answer", references=[reference])
    resolver = AgentBackendResolver().register("bkai", mocker.Mock(return_value=backend))
    spec = AgentSpec(name="child", description="test", backend_type="bkai")
    tool = next(tool for tool in get_agent_tools([spec], resolver) if tool.name == tool_name)
    dispatch = mocker.patch("aidev_agent.core.tools.a2a_tools.provider.dispatch_custom_event")
    args = {"agent_name": "child"} if tool_name == "Agent" else {"member_name": "member"}
    state = {"bk_agent_team": {"member": {"agent_name": "child", "session_code": "example-session"}}}
    result = json.loads(tool.func(message="question", config={"callbacks": [object()]}, state=state, **args))
    assert result["references"][0]["url"] == REFERENCE["url"]
    assert dispatch.call_args.args == ("knowledge_rag_result",)
    assert dispatch.call_args.kwargs["data"]["data"] == [REFERENCE]
