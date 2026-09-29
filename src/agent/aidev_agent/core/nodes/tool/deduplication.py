"""Single-flight knowledge retrieval scoped to one ToolNode invocation."""

import asyncio
import json
from concurrent.futures import Future
from contextvars import ContextVar
from threading import Lock

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest

DUPLICATE_WAIT_TIMEOUT_SECONDS = 60.0


class _Batch:
    def __init__(self):
        self.lock = Lock()
        self.results: dict[tuple[int, str], Future] = {}

    def claim(self, key):
        with self.lock:
            if key in self.results:
                return self.results[key], False
            future = self.results[key] = Future()
            return future, True


_batch: ContextVar[_Batch | None] = ContextVar("knowledge_tool_batch", default=None)


class KnowledgeToolNode(ToolNode):
    """Context is copied into ToolNode workers, never persisted in graph state."""

    def _func(self, input, config, runtime):
        token = _batch.set(_Batch())
        try:
            return super()._func(input, config, runtime)
        finally:
            _batch.reset(token)

    async def _afunc(self, input, config, runtime):
        token = _batch.set(_Batch())
        try:
            return await super()._afunc(input, config, runtime)
        finally:
            _batch.reset(token)


def _claim(request: ToolCallRequest):
    batch = _batch.get()
    metadata = request.tool.metadata if request.tool else None
    if batch is None or request.tool_call["name"] != "knowledge_retrieval":
        return None
    if not metadata or not metadata.get("deduplicate_in_tool_batch"):
        return None
    # Approval can select a different execution identity for each call.
    if metadata.get("approval"):
        return None
    try:
        key = json.dumps(request.tool_call["args"], sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return None
    return batch.claim((id(request.tool), key))


def _copy_result(result: ToolMessage, request: ToolCallRequest):
    return result.model_copy(
        deep=True,
        update={
            "id": None,
            "tool_call_id": request.tool_call["id"],
            "additional_kwargs": {**result.additional_kwargs, "reused_tool_result": True},
        },
    )


def deduplicate_sync(request, execute):
    claim = _claim(request)
    if claim is None:
        return execute(request)
    future, owner = claim
    if not owner:
        result = future.result(timeout=DUPLICATE_WAIT_TIMEOUT_SECONDS)
        return _copy_result(result, request) if isinstance(result, ToolMessage) else execute(request)
    try:
        result = execute(request)
        future.set_result(result.model_copy(deep=True) if isinstance(result, ToolMessage) else None)
        return result
    except BaseException as error:
        future.set_exception(error)
        raise


async def deduplicate_async(request, execute):
    claim = _claim(request)
    if claim is None:
        return await execute(request)
    future, owner = claim
    if not owner:
        # Cancelling a waiter must not cancel the shared owner's future.
        waiter = asyncio.wrap_future(future)
        # A timed-out/cancelled waiter may outlive this coroutine. Retrieve a later
        # exception so asyncio does not report an unobserved Future exception.
        waiter.add_done_callback(_observe_waiter_exception)
        result = await asyncio.wait_for(asyncio.shield(waiter), timeout=DUPLICATE_WAIT_TIMEOUT_SECONDS)
        return _copy_result(result, request) if isinstance(result, ToolMessage) else await execute(request)
    try:
        result = await execute(request)
        future.set_result(result.model_copy(deep=True) if isinstance(result, ToolMessage) else None)
        return result
    except BaseException as error:
        future.set_exception(error)
        raise


def _observe_waiter_exception(future: asyncio.Future) -> None:
    if not future.cancelled():
        future.exception()
