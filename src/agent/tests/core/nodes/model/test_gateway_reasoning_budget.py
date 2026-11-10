"""Exercise real gateway SSE parsing before quality recovery."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import THINKING_EXHAUSTED_MESSAGE, QualityGate
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from langchain_core.messages import HumanMessage


def _reasoning_stream_response(request):
    chunks = [
        {"delta": {"role": "assistant", "content": "", "reasoning_content": "thinking without answering"}},
        {"delta": {}, "finish_reason": "length"},
    ]
    payloads = [
        {
            "id": "chatcmpl-budget",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "test",
            "choices": [{"index": 0, **chunk}],
        }
        for chunk in chunks
    ]
    body = "".join("data: " + json.dumps(payload) + "\n\n" for payload in payloads) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=body)


def _gateway_chain(model, track):
    assembly = MagicMock()
    assembly.get_choice_tools.return_value = []
    assembly.get_chat_prompt_variables.return_value = {}
    assembly.get_chat_prompt_template.return_value.invoke.return_value.to_messages.return_value = [
        HumanMessage(content="A short request")
    ]
    chain = _build_model_chain(
        llm=model,
        context_assembly=assembly,
        max_retries=10,
        quality_gate=QualityGate(),
        use_structured_response=False,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
        track_memory_source=track,
    )
    return chain, ProcessorContext(state={"messages": []}, config={}, model_chain_state=ModelChainState())


@pytest.mark.parametrize("track", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_gateway_length_reason_stops_replay_with_and_without_memory(track, asynchronous):
    requests = []

    def respond(request):
        requests.append(request)
        return _reasoning_stream_response(request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    async_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        model = ChatModel.get_setup_instance(
            model="test",
            base_url="https://example.test/v1",
            api_key="test",
            streaming=True,
            http_client=client,
            http_async_client=async_client,
        )
        chain, context = _gateway_chain(model, track)
        result = await chain.ainvoke(context) if asynchronous else chain.invoke(context)
        assert result.response.content == THINKING_EXHAUSTED_MESSAGE
        assert result.response.response_metadata["finish_reason"] == "length"
        assert not result.response.response_metadata.get("memory_source_complete", False)
        assert len(requests) == 1
    finally:
        client.close()
        await async_client.aclose()
