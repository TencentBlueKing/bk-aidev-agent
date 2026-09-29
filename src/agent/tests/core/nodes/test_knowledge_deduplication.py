"""Exercise result reuse through the real ToolNode and graph executors."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from aidev_agent.core.nodes.tool import build_tool_node
from aidev_agent.core.tools.knowledge import make_knowledge_retrieval_tool
from aidev_agent.pydantic_models import KnowledgeSettings
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, MessagesState, StateGraph


def _state(queries):
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": f"call-{i}", "name": "knowledge_retrieval", "args": {"query": query}}
                    for i, query in enumerate(queries)
                ],
            )
        ]
    }


@pytest.fixture
def retrieval_graph():
    calls = []
    lock = Lock()

    def build(*, enabled=True, failing=False, wrappers=None, async_wrappers=None):
        def retrieve(query: str):
            """Retrieve knowledge."""
            with lock:
                calls.append(query)
            time.sleep(0.02)
            if failing:
                raise ValueError("retrieval unavailable")
            return [query]

        tool = StructuredTool.from_function(
            retrieve, name="knowledge_retrieval", metadata={"deduplicate_in_tool_batch": enabled}
        )
        graph = StateGraph(MessagesState)
        graph.add_node("tools", build_tool_node([tool], wrappers=wrappers, async_wrappers=async_wrappers))
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        return graph.compile()

    return build, calls


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize(
    "queries,expected", [(["alpha", "alpha"], 1), (["alpha", "beta"], 2), (["alpha", " alpha"], 2)]
)
async def test_identical_calls_reuse_result_and_preserve_message_ids(retrieval_graph, async_mode, queries, expected):
    build, calls = retrieval_graph
    graph = build()
    result = await graph.ainvoke(_state(queries)) if async_mode else graph.invoke(_state(queries))
    messages = result["messages"][1:]
    assert len(calls) == expected
    assert [message.tool_call_id for message in messages] == ["call-0", "call-1"]
    assert len({message.id for message in messages}) == 2
    assert sum(bool(message.additional_kwargs.get("reused_tool_result")) for message in messages) == 2 - expected
    assert all(message.status == "success" for message in messages)


@pytest.mark.parametrize("async_mode", [False, True])
async def test_no_reuse_across_invocations_or_concurrent_requests(retrieval_graph, async_mode):
    build, calls = retrieval_graph
    graph = build()
    state = _state(["alpha", "alpha"])
    if async_mode:
        await asyncio.gather(graph.ainvoke(state), graph.ainvoke(state))
        await graph.ainvoke(state)
    else:
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(graph.invoke, [state, state]))
        graph.invoke(state)
    assert calls == ["alpha"] * 3


@pytest.mark.parametrize("async_mode", [False, True])
async def test_unmarked_tool_is_not_deduplicated(retrieval_graph, async_mode):
    build, calls = retrieval_graph
    graph = build(enabled=False)
    state = _state(["alpha", "alpha"])
    await graph.ainvoke(state) if async_mode else graph.invoke(state)
    assert calls == ["alpha", "alpha"]


@pytest.mark.parametrize("async_mode", [False, True])
async def test_error_replies_keep_each_call_id_and_later_invocation_can_retry(retrieval_graph, async_mode):
    build, calls = retrieval_graph
    graph = build(failing=True)
    for _ in range(2):
        result = await graph.ainvoke(_state(["a", "a"])) if async_mode else graph.invoke(_state(["a", "a"]))
        messages = result["messages"][1:]
        assert [message.tool_call_id for message in messages] == ["call-0", "call-1"]
        assert all(message.status == "error" for message in messages)
    assert len(calls) == 2


def test_builtin_knowledge_tool_enables_batch_reuse(mocker):
    tool = make_knowledge_retrieval_tool(mocker.Mock(), KnowledgeSettings(knowledge_bases=[{"id": 1}]))
    assert tool.metadata["deduplicate_in_tool_batch"] is True


@pytest.mark.parametrize("async_mode", [False, True])
async def test_custom_wrappers_run_for_every_call(retrieval_graph, async_mode):
    build, calls = retrieval_graph
    seen = []

    def wrapper(request, execute):
        seen.append(request.tool_call["id"])
        return execute(request)

    async def async_wrapper(request, execute):
        seen.append(request.tool_call["id"])
        return await execute(request)

    graph = build(wrappers=[wrapper], async_wrappers=[async_wrapper])
    await graph.ainvoke(_state(["a", "a"])) if async_mode else graph.invoke(_state(["a", "a"]))
    assert sorted(seen) == ["call-0", "call-1"]
    assert calls == ["a"]
