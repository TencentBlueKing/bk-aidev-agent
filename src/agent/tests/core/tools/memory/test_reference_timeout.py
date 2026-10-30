"""Reference auditing bounds HTTP waits without changing the answer model."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.tools.memory import PersonalMemoryRuntime, audit_model
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


@pytest.fixture
def held_audit():
    entered, release = Event(), Event()
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            entered.set()
            release.wait(4)
            self.send_response(500)
            self.send_header("Content-Length", "0")
            with suppress(BrokenPipeError, ConnectionResetError):
                self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    model = ChatModel.get_setup_instance(
        model="synthetic",
        base_url=f"http://127.0.0.1:{server.server_port}/v1",
        auth_headers={"bk_app_code": "synthetic", "bk_app_secret": "synthetic"},
        fallback_model=None,
    )
    yield model, entered, release, calls
    release.set()
    model.root_client.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=1)


def runtime_with_hit(model, **options):
    manager = MagicMock()
    context = {
        "username": "alice",
        "agent_code": "agent",
        "session_id": "session",
        "session_date": "2026-10-22",
        "messages": [],
    }
    runtime = PersonalMemoryRuntime(lambda _: context, manager=manager, reference_model=model, **options)
    runtime.policy = {"enabled": True, "agent_code": "agent", "version": "1.0.0"}
    state = {
        "messages": [
            HumanMessage(id="u", content="Preference?"),
            ToolMessage(
                content="hit",
                tool_call_id="search",
                artifact={"personal_memory_hits": [{"memory_id": "m", "text": "Python"}]},
            ),
            AIMessage(id="a", content="Use Python."),
        ]
    }
    return runtime, manager, state


def memory_graph(runtime):
    return (
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
        )[0]
    )


def test_cancelled_audit_releases_executor_without_server_response(held_audit):
    model, entered, release, calls = held_audit
    runtime, manager, state = runtime_with_hit(model, reference_timeout=0.05)

    async def exercise():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        task = asyncio.create_task(memory_graph(runtime).ainvoke(state))
        try:
            for _ in range(200):
                if entered.is_set():
                    break
                await asyncio.sleep(0.005)
            assert entered.is_set()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            following = loop.run_in_executor(None, lambda: "next task")
            assert await asyncio.wait_for(following, 1) == "next task"
            assert not release.is_set()
            manager.complete_memory_round.assert_called_once()
            assert manager.complete_memory_round.call_args.args[0]["memory_ids"] == []
            assert len(calls) == 1 and calls[0]["stream"] is False
        finally:
            release.set()
            await model.root_async_client.close()

    asyncio.run(exercise())
    assert model.root_client.timeout is None
    assert model.root_client.max_retries == 2


@pytest.mark.parametrize("wrapper", ["plain", "bound", "fallback"])
def test_actual_http_timeout_degrades_to_empty_references(held_audit, wrapper):
    model, _, release, calls = held_audit
    reference = model
    if wrapper == "bound":
        reference = model.bind(timeout=None, stream=True)
    elif wrapper == "fallback":
        reference = model.with_fallbacks([model])
    runtime, manager, state = runtime_with_hit(reference, reference_timeout=0.05)
    assert runtime.complete(state, {}) == {}
    assert not release.is_set()
    assert len(calls) == (2 if wrapper == "fallback" else 1)
    assert all(call["stream"] is False for call in calls)
    manager.complete_memory_round.assert_called_once()
    assert manager.complete_memory_round.call_args.args[0]["memory_ids"] == []
    assert model.root_client.timeout is None and model.root_client.max_retries == 2
    asyncio.run(model.root_async_client.close())


def test_audit_client_options_are_independent_and_default_is_finite(held_audit):
    model, _, _, _ = held_audit
    isolated = audit_model(model)
    assert isolated.request_timeout == isolated.root_client.timeout == isolated.root_async_client.timeout == 2
    assert isolated.max_retries == isolated.root_client.max_retries == isolated.root_async_client.max_retries == 0
    assert isolated.client is isolated.root_client.chat.completions
    assert isolated.async_client is isolated.root_async_client.chat.completions
    assert isolated.root_client is not model.root_client
    assert isolated.root_async_client is not model.root_async_client
    assert model.request_timeout is None and model.root_client.timeout is None
    assert model.root_client.max_retries == 2
    asyncio.run(model.root_async_client.close())


@pytest.mark.parametrize("missing_root", ["root_client", "root_async_client"])
def test_unbounded_external_completion_client_skips_reference_audit(held_audit, missing_root):
    model, _, _, calls = held_audit
    external = model.model_copy(update={missing_root: None})
    runtime, manager, state = runtime_with_hit(external)
    runtime.complete(state, {})
    assert calls == []
    assert manager.complete_memory_round.call_args.args[0]["memory_ids"] == []
    asyncio.run(model.root_async_client.close())


@pytest.mark.parametrize("timeout", [None, True, 0, -1, float("inf"), float("nan"), "2"])
def test_reference_timeout_must_be_positive_and_finite(timeout):
    with pytest.raises(ValueError, match="positive finite"):
        PersonalMemoryRuntime(lambda _: {}, manager=MagicMock(), reference_timeout=timeout)
