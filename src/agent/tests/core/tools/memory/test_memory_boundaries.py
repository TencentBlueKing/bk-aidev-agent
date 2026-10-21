from datetime import datetime, timezone

import pytest
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.tools.memory import audit_model, message_timestamp
from aidev_agent.packages.langchain_core.models.mock import MockChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda


class StreamingModel(MockChatModel):
    streaming: bool = True


def test_audit_disables_streaming_without_mutating_answer_model():
    model = StreamingModel()
    isolated = audit_model(model)
    assert isolated.streaming is False
    assert isolated.callbacks == [] and isolated.cache is False
    assert model.streaming is True


def test_unsupported_runnable_cannot_leak_callbacks():
    with pytest.raises(ValueError, match="cannot isolate"):
        audit_model(RunnableLambda(lambda value: value))


def test_naive_message_time_is_explicitly_utc():
    assert message_timestamp(datetime(2026, 10, 1)) == datetime(2026, 10, 1, tzinfo=timezone.utc).isoformat()


@pytest.mark.parametrize("epoch", [None, True, 0, -1, "1"])
def test_invalid_epoch_rejects_discovery(runtime, epoch):
    runtime.manager.memory_schemas.return_value["memory_epoch"] = epoch
    with pytest.raises(ValueError, match="activation"):
        runtime.make_tools()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown_enabled"])
def test_incomplete_discovery_contract_is_rejected(runtime, mutation):
    policy = runtime.manager.memory_schemas.return_value
    if mutation == "missing":
        policy["schemas"].pop()
    elif mutation == "duplicate":
        policy["schemas"].append(policy["schemas"][0])
    else:
        policy["enabled"] = None
    with pytest.raises(ValueError, match="three"):
        runtime.make_tools()


def test_disabled_explicit_runtime_skips_all_requests(runtime):
    policy = runtime.manager.memory_schemas.return_value
    policy["enabled"] = False
    assert runtime.make_tools() == []
    tool = runtime.make_tool(policy["schemas"][0]["function"])
    assert tool.invoke({"query": "x"}) == "Personal memory is disabled."
    assert runtime.complete({"messages": [AIMessage(content="Answer", id="a")]}, {}) == {}
    runtime.manager.memory_tool.assert_not_called()
    runtime.manager.complete_memory_round.assert_not_called()


def test_runtime_cannot_change_agent_after_discovery(runtime):
    runtime.make_tools()
    _, context = runtime.context({})
    context["agent_code"] = "other-agent"
    with pytest.raises(ValueError, match="switch agents"):
        runtime.scoped_payload(context, {}, {})
    runtime.manager.memory_tool.assert_not_called()


def test_strict_tool_errors_propagate(runtime):
    tool = runtime.make_tools()[0]
    runtime.manager.memory_tool.side_effect = ConnectionError("offline")
    with pytest.raises(ConnectionError, match="offline"):
        tool.invoke({"query": "x"})


def test_strict_completion_errors_propagate(runtime):
    runtime.manager.complete_memory_round.side_effect = ConnectionError("offline")
    with pytest.raises(ConnectionError, match="offline"):
        runtime.complete({"messages": [AIMessage(content="Answer", id="a")]}, {})


def test_missing_reference_model_does_not_claim_retrieval_as_use(runtime):
    runtime.reference_model = None
    assert runtime.referenced_ids(AIMessage(content="Answer"), [{"memory_id": "unused"}]) == []


def test_fenced_audit_output_is_validated_and_deduplicated(runtime):
    runtime.reference_model.invoke.return_value = AIMessage(content='```json\n{"memory_ids":["used","used"]}\n```')
    assert runtime.referenced_ids(AIMessage(content="Answer"), [{"memory_id": "used"}]) == ["used"]


@pytest.mark.parametrize("references", ["used", [1], ["foreign"]])
def test_bad_reference_types_and_ids_are_rejected(runtime, references):
    answer = AIMessage(content="Answer", additional_kwargs={"personal_memory_references": references})
    with pytest.raises(ValueError, match="IDs retrieved"):
        runtime.referenced_ids(answer, [{"memory_id": "used"}])


@pytest.mark.parametrize(
    "finish_reason", ["length", "max_tokens", "content_filter", "incomplete", "LENGTH", "cancelled", "stopped", "error"]
)
def test_graph_does_not_commit_unfinished_response(runtime, finish_reason):
    graph, _ = (
        ReActAgentBuilder()
        .enable_personal_memory(runtime)
        ._build_graph(
            state_schema=dict,
            callbacks=[],
            debug=False,
            checkpointer=None,
            store=None,
            interrupt_before=None,
            interrupt_after=None,
            name=None,
            cache=None,
            knowledge_node=None,
            model_node=lambda state: state,
            tool_node=None,
            pv_node=None,
            tools=None,
        )
    )
    graph.invoke(
        {"messages": [AIMessage(content="Partial answer", id="a", response_metadata={"finish_reason": finish_reason})]}
    )
    runtime.manager.complete_memory_round.assert_not_called()
    runtime.reference_model.invoke.assert_not_called()


@pytest.mark.parametrize("finish_reason", [None, "", "stop", "end_turn"])
def test_successful_completion_omits_unfinished_history(runtime, finish_reason):
    runtime.complete(
        {
            "messages": [
                HumanMessage(content="Hi", id="u"),
                AIMessage(content="Truncated", id="partial", response_metadata={"finish_reason": "length"}),
                AIMessage(content="Filtered", id="filtered", response_metadata={"finish_reason": "content_filter"}),
                ToolMessage(content="Tool output", tool_call_id="call"),
                AIMessage(content="Complete", id="a", response_metadata={"finish_reason": finish_reason}),
            ]
        },
        {},
    )
    snapshot = runtime.manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    assert [item["message_id"] for item in snapshot] == ["u", "a"]
    assert all(item["complete"] is True for item in snapshot)


def test_empty_state_does_not_submit(runtime):
    assert runtime.complete({}, {}) == {}
    runtime.manager.complete_memory_round.assert_not_called()


def test_empty_filtered_snapshot_does_not_submit(runtime):
    runtime.manager.memory_schemas.return_value["enabled_at"] = "2026-10-09T00:00:00Z"
    runtime.complete(
        {"messages": [AIMessage(content="Old", id="a", response_metadata={"created_at": "2026-10-01T00:00:00Z"})]}, {}
    )
    runtime.manager.complete_memory_round.assert_not_called()
