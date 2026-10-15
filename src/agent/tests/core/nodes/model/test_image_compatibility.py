"""Image-capability mismatches never poison text turns with old image history."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from aidev_agent.core.nodes.model import model_chain as model_chain_module
from aidev_agent.core.nodes.model.model_chain import _build_model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import QualityGate
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from openai import BadRequestError


@pytest.fixture
def rejection():
    response = httpx.Response(400, request=httpx.Request("POST", "https://example.com/v1/chat/completions"))
    return BadRequestError("unsupported multimodal content: image_url", response=response, body=None)


@pytest.fixture(params=["image_url", "binary"])
def image(request):
    if request.param == "image_url":
        return {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}
    return {"type": "binary", "mime_type": "image/png", "url": "https://example.com/image.png", "outputId": "image.png"}


@pytest.fixture
def compatibility_chain(rejection, image):
    def build(*, reject=True, current_image=False, always_fail=False, tools=None):
        calls = []

        def invoke(messages):
            calls.append(deepcopy(messages))
            if reject and (len(calls) == 1 or always_fail):
                raise rejection
            return AIMessage(content="answer")

        assembly = Mock()
        query = [{"type": "text", "text": "question"}, image] if current_image else "question"
        assembly.get_chat_prompt_variables.return_value = {"history": [HumanMessage(content=[image])], "query": query}
        assembly.get_chat_prompt_template.return_value = ChatPromptTemplate.from_messages(
            [MessagesPlaceholder("history"), ("human", "{query}")]
        )
        assembly.get_choice_tools.return_value = tools or []
        llm = RunnableLambda(invoke)
        llm.bind_tools = Mock(return_value=llm)
        chain = _build_model_chain(
            llm=llm,
            context_assembly=assembly,
            max_retries=0,
            quality_gate=QualityGate(enable_judge_response=False),
            use_structured_response=False,
            enable_parallel_tool_calls=False,
            use_tool_call_promotion=False,
        )
        return chain, calls

    return build


@pytest.mark.parametrize("is_async", [False, True])
def test_history_image_rejection_retries_once_without_mutating_history(compatibility_chain, is_async, image):
    chain, calls = compatibility_chain()
    original = deepcopy(image)
    ctx = ProcessorContext(state={}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0))
    result = asyncio.run(chain.ainvoke(ctx)) if is_async else chain.invoke(ctx)
    assert result.response.content == "answer"
    assert len(calls) == 2
    assert calls[0][0].content == [original]
    assert all(item["type"] == "text" for item in calls[1][0].content)
    assert calls[1][-1].content == "question"
    assert image == original


@pytest.mark.parametrize("is_async", [False, True])
def test_supported_vision_model_keeps_images(compatibility_chain, is_async, image):
    chain, calls = compatibility_chain(reject=False, current_image=True)
    ctx = ProcessorContext(state={}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0))
    result = asyncio.run(chain.ainvoke(ctx)) if is_async else chain.invoke(ctx)
    assert result.response.content == "answer"
    assert len(calls) == 1
    assert calls[0][-1].content[-1] == image


@pytest.mark.parametrize("is_async", [False, True])
def test_current_image_without_reader_is_not_silently_dropped(compatibility_chain, is_async):
    chain, calls = compatibility_chain(current_image=True)
    ctx = ProcessorContext(state={}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0))
    with pytest.raises(BadRequestError):
        asyncio.run(chain.ainvoke(ctx)) if is_async else chain.invoke(ctx)
    assert len(calls) == 1


def test_current_image_with_reader_preserves_file_reference(rejection):
    image = {"type": "binary", "mime_type": "image/png", "outputId": "image.png"}
    messages = [HumanMessage(content=[image])]
    retried = model_chain_module._image_compatibility_messages(
        messages, rejection, [SimpleNamespace(name="read_image")]
    )
    assert "image.png" in retried[0].content[0]["text"]
    assert "read_image" in retried[0].content[0]["text"]
    assert messages[0].content == [image]


def test_unrelated_bad_request_is_not_retried(rejection, image):
    rejection = BadRequestError("invalid tool schema", response=rejection.response, body=None)
    assert (
        model_chain_module._image_compatibility_messages(
            [HumanMessage(content=[image]), HumanMessage(content="q")], rejection, []
        )
        is None
    )


def test_compatibility_failure_does_not_loop(compatibility_chain):
    chain, calls = compatibility_chain(always_fail=True)
    with pytest.raises(BadRequestError):
        chain.invoke(
            ProcessorContext(state={}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0))
        )
    assert len(calls) == 2


@pytest.mark.parametrize("is_async", [False, True])
def test_current_image_can_recover_through_registered_reader(compatibility_chain, image, is_async):
    image["outputId"] = "current.png"
    reader = StructuredTool.from_function(lambda path: "description", name="read_image", description="Read an image")
    chain, calls = compatibility_chain(current_image=True, tools=[reader])
    ctx = ProcessorContext(state={}, config={}, store=None, model_chain_state=ModelChainState(max_retries=0))
    result = asyncio.run(chain.ainvoke(ctx)) if is_async else chain.invoke(ctx)
    assert result.response.content == "answer"
    assert len(calls) == 2
    assert "current.png" in calls[1][-1].content[-1]["text"]
    assert "read_image" in calls[1][-1].content[-1]["text"]
    assert image["outputId"] == "current.png"
