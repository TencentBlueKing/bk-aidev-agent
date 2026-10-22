"""Original source contracts survive completion, persistence, and API failures."""

import asyncio
import copy
import json
from unittest.mock import MagicMock

import pytest
from aidev_agent.api.bk_aidev import Client
from aidev_agent.services.agent.memory import automatic_personal_memory, completed_history
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.message_metadata import assistant_source_text
from langchain_core.messages import AIMessage
from requests import Response

from .test_memory_native_source import capture


@pytest.fixture
def contract_manager():
    manager = MagicMock()
    manager.memory_schemas.return_value = {
        "enabled": True,
        "agent_code": "agent",
        "memory_epoch": 1,
        "enabled_at": None,
        "schemas": [
            {"function": {"name": name, "description": "Memory", "parameters": {"type": "object", "properties": {}}}}
            for name in ("memory_write", "memory_update", "memory_search")
        ],
    }
    return manager


@pytest.fixture
def source_writer():
    client, rows = MagicMock(), []

    def create(*, json, headers):
        rows.append(copy.deepcopy(json))
        return {"data": {"id": 1}}

    def update(*, path_params, json, headers, timeout=None):
        rows[0].update(copy.deepcopy(json))

    client.api.create_chat_session_content.side_effect = create
    client.api.update_chat_session_content.side_effect = update
    return AGUISessionWriter("s", client, username="alice"), rows


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("body", ["\n  Keep Case\n\n", "    indented code  \n", "\tKeep\r\n\r\n"])
def test_verbatim_body_survives_current_writer_and_next_round(contract_manager, source_writer, structured, body):
    text = json.dumps({"action": "Final Answer", "action_input": body}) if structured else body
    events, answer = asyncio.run(capture(text, structured, False))
    writer, rows = source_writer
    for event in events:
        writer(event)
    runtime = automatic_personal_memory(contract_manager, "alice", "s", [], [], agent_code="agent")
    runtime.complete({"messages": [answer]}, {})
    current = contract_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    restored = completed_history(
        [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows], "s"
    )
    assert assistant_source_text(answer) == body
    assert restored == current and current[0]["text"] == body
    assert rows[0]["content"] == text.strip()


@pytest.mark.parametrize("proof", [{"status": "complete"}, {"builtin_property": {"memory_source_complete": True}}])
@pytest.mark.parametrize("cutoff", [None, "2026-10-21T00:00:00Z"])
def test_explicit_completion_keeps_unknown_time_until_activation_cutoff(contract_manager, proof, cutoff):
    record = {"id": "old", "role": "assistant", "content": "\n Keep Case\n", **proof}
    contract_manager.memory_schemas.return_value["enabled_at"] = cutoff
    runtime = automatic_personal_memory(contract_manager, "alice", "s", [record], [], agent_code="agent")
    source = runtime.context({})[1]["messages"][0]
    assert source == {"message_id": "old", "role": "assistant", "text": "\n Keep Case\n", "complete": True}
    runtime.complete({"messages": [AIMessage(id="next", content="Next answer")]}, {})
    sent = contract_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert (source in sent) is (cutoff is None)


@pytest.mark.parametrize("cutoff", [None, "2026-10-21T00:00:00Z"])
def test_completed_host_message_without_time_is_not_globally_dropped(contract_manager, cutoff):
    contract_manager.memory_schemas.return_value["enabled_at"] = cutoff
    answer = AIMessage(id="old", content="Host answer", response_metadata={"memory_source_complete": True})
    runtime = automatic_personal_memory(contract_manager, "alice", "s", [], [answer], agent_code="agent")
    source = runtime.context({})[1]["messages"][0]
    assert source["text"] == "Host answer" and "timestamp" not in source
    runtime.complete({"messages": [AIMessage(id="next", content="Next answer")]}, {})
    sent = contract_manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert (source in sent) is (cutoff is None)


@pytest.mark.parametrize("body", ["", " \n\t", "<think>private</think>\n\n"])
def test_empty_visible_body_is_still_excluded(contract_manager, body):
    runtime = automatic_personal_memory(contract_manager, "alice", "s", [], [], agent_code="agent")
    runtime.complete({"messages": [AIMessage(id="empty", content=body)]}, {})
    contract_manager.complete_memory_round.assert_not_called()


@pytest.mark.parametrize(
    "status,code,message,forgotten",
    [
        (400, "400", ["FORGOTTEN_CONTENT: 重复写入不能恢复已遗忘记忆"], True),
        (400, "400", "FORGOTTEN_CONTENT: 重复写入不能恢复已遗忘记忆", True),
        (400, "400", ["OTHER: invalid request"], False),
        (403, "403", "FORGOTTEN_CONTENT: denied", False),
        (500, "500", "FORGOTTEN_CONTENT: server failure", False),
    ],
)
def test_real_client_validation_preserves_forgotten_business_error(
    contract_manager, monkeypatch, status, code, message, forgotten
):
    client = Client(endpoint="http://127.0.0.1:45678/")
    response = Response()
    response.status_code = status
    response._content = json.dumps({"error": {"code": code, "message": message, "data": message}}).encode()
    monkeypatch.setattr(client.session, "request", lambda **kwargs: response)
    contract_manager.memory_tool.side_effect = lambda payload, **kwargs: client.api.memory_tool(json=payload)
    runtime = automatic_personal_memory(contract_manager, "alice", "s", [], [], agent_code="agent")
    result = runtime.make_tools()[0].invoke({})
    if forgotten:
        assert json.loads(result) == {
            "code": "FORGOTTEN_CONTENT",
            "message": "该内容已被用户遗忘，本次未保存。",
            "retryable": False,
        }
    else:
        assert result == "Personal memory is temporarily unavailable."


@pytest.mark.parametrize("raw", [b"invalid json", b"[]", b"{}", b'{"error":[]}', b'{"error":{"code":"403"}}'])
def test_unknown_validation_envelopes_remain_unavailable(contract_manager, monkeypatch, raw):
    client = Client(endpoint="http://127.0.0.1:45678/")
    response = Response()
    response.status_code, response._content = 400, raw
    monkeypatch.setattr(client.session, "request", lambda **kwargs: response)
    contract_manager.memory_tool.side_effect = lambda payload, **kwargs: client.api.memory_tool(json=payload)
    runtime = automatic_personal_memory(contract_manager, "alice", "s", [], [], agent_code="agent")
    assert runtime.make_tools()[0].invoke({}) == "Personal memory is temporarily unavailable."
