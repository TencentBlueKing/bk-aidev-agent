"""Exercise result reuse through the real ToolNode and graph executors."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import SimpleNamespace

import pytest
from aidev_agent.core.nodes.tool import build_tool_node
from aidev_agent.core.nodes.tool import deduplication as dedup
from aidev_agent.core.tools.knowledge import make_knowledge_retrieval_tool
from aidev_agent.pydantic_models import KnowledgeSettings
from langchain_core.messages import AIMessage, ToolMessage
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


@pytest.fixture
def batch_requests():
    batch = dedup._Batch()
    token = dedup._batch.set(batch)
    tool = SimpleNamespace(metadata={"deduplicate_in_tool_batch": True})
    requests = [
        SimpleNamespace(tool=tool, tool_call={"id": str(i), "name": "knowledge_retrieval", "args": {"query": "q"}})
        for i in range(2)
    ]
    try:
        yield batch, requests
    finally:
        dedup._batch.reset(token)


def test_claim_exception_releases_lock():
    batch = dedup._Batch()
    with pytest.raises(TypeError):
        batch.claim([])
    assert batch.lock.acquire(blocking=False)
    batch.lock.release()
    assert batch.claim("next")[1] is True


def test_sync_hung_owner_does_not_hold_lock_or_block_waiter_forever(batch_requests, monkeypatch):
    batch, (owner_request, waiter_request) = batch_requests
    monkeypatch.setattr(dedup, "DUPLICATE_WAIT_TIMEOUT_SECONDS", 0.02)
    entered, release = Event(), Event()

    def execute(request):
        entered.set()
        release.wait(2)
        return ToolMessage(content="ok", tool_call_id="0")

    def run_owner():
        token = dedup._batch.set(batch)
        try:
            return dedup.deduplicate_sync(owner_request, execute)
        finally:
            dedup._batch.reset(token)

    with ThreadPoolExecutor(max_workers=1) as executor:
        owner = executor.submit(run_owner)
        try:
            assert entered.wait(1)
            assert batch.claim("different query")[1] is True
            with pytest.raises(TimeoutError):
                dedup.deduplicate_sync(waiter_request, execute)
        finally:
            release.set()
        assert owner.result(timeout=1).content == "ok"


async def test_async_timeout_does_not_cancel_owner(batch_requests, monkeypatch):
    batch, (owner_request, waiter_request) = batch_requests
    monkeypatch.setattr(dedup, "DUPLICATE_WAIT_TIMEOUT_SECONDS", 0.02)
    entered, release = asyncio.Event(), asyncio.Event()

    async def execute(request):
        entered.set()
        await release.wait()
        return ToolMessage(content="ok", tool_call_id="0")

    owner = asyncio.create_task(dedup.deduplicate_async(owner_request, execute))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        with pytest.raises(TimeoutError):
            await dedup.deduplicate_async(waiter_request, execute)
        assert not owner.done()
        assert batch.claim("different query")[1] is True
    finally:
        release.set()
    assert (await asyncio.wait_for(owner, 1)).content == "ok"


@pytest.mark.parametrize("cancel_owner", [False, True])
async def test_cancellation_wakes_waiter_or_preserves_owner(batch_requests, cancel_owner):
    _, (owner_request, waiter_request) = batch_requests
    entered, release = asyncio.Event(), asyncio.Event()

    async def execute(request):
        entered.set()
        await release.wait()
        return ToolMessage(content="ok", tool_call_id="0")

    owner = asyncio.create_task(dedup.deduplicate_async(owner_request, execute))
    await asyncio.wait_for(entered.wait(), 1)
    waiter = asyncio.create_task(dedup.deduplicate_async(waiter_request, execute))
    await asyncio.sleep(0)
    (owner if cancel_owner else waiter).cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, 1)
        if cancel_owner:
            with pytest.raises(asyncio.CancelledError):
                await owner
        else:
            assert not owner.done()
    finally:
        release.set()
        await asyncio.gather(owner, waiter, return_exceptions=True)


@pytest.mark.parametrize("async_mode", [False, True])
async def test_unhandled_owner_exception_completes_shared_future(batch_requests, async_mode):
    batch, (owner_request, waiter_request) = batch_requests

    def execute(request):
        raise RuntimeError("owner failed")

    async def async_execute(request):
        return execute(request)

    for request in (owner_request, waiter_request):
        with pytest.raises(RuntimeError, match="owner failed"):
            if async_mode:
                await asyncio.wait_for(dedup.deduplicate_async(request, async_execute), 1)
            else:
                dedup.deduplicate_sync(request, execute)
    assert all(future.done() for future in batch.results.values())
    assert not batch.lock.locked()


@pytest.mark.parametrize(
    "args,approval", [({"query": "q"}, True), ({"query": object()}, False), ({"query": float("nan")}, False)]
)
def test_approval_and_invalid_arguments_do_not_claim(args, approval):
    batch = dedup._Batch()
    token = dedup._batch.set(batch)
    request = SimpleNamespace(
        tool=SimpleNamespace(metadata={"deduplicate_in_tool_batch": True, "approval": approval}),
        tool_call={"name": "knowledge_retrieval", "args": args},
    )
    try:
        assert dedup._claim(request) is None
        assert batch.results == {}
        assert batch.lock.acquire(blocking=False)
        batch.lock.release()
    finally:
        dedup._batch.reset(token)


async def test_cancelled_observer_does_not_raise():
    future = asyncio.get_running_loop().create_future()
    future.cancel()
    dedup._observe_waiter_exception(future)
    assert future.cancelled()
