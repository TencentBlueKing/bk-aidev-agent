"""无提供方完成事件的自定义 Runnable 仍保留原有输出和异常语义。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.core.nodes.model import model_chain
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda


def make_chain(quality_gate):
    assembly = SimpleNamespace(
        get_choice_tools=lambda ctx: [],
        get_chat_prompt_template=lambda ctx: ChatPromptTemplate.from_messages([("human", "Hello")]),
        get_chat_prompt_variables=lambda ctx: {},
    )
    return model_chain._build_model_chain(
        llm=RunnableLambda(lambda messages: AIMessage(content="Answer", id="custom-response")),
        context_assembly=assembly,
        max_retries=0,
        quality_gate=quality_gate,
        use_structured_response=False,
        enable_parallel_tool_calls=False,
        use_tool_call_promotion=False,
        track_memory_source=True,
    )


def context():
    return ProcessorContext(state={"messages": []}, config={}, store=None, model_chain_state=ModelChainState())


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_runnable_without_provider_event_preserves_response(mode, mocker):
    sync_event = mocker.patch.object(model_chain, "dispatch_custom_event")
    async_event = mocker.patch.object(model_chain, "adispatch_custom_event")
    chain = make_chain(lambda ctx: ctx)
    result = chain.invoke(context()) if mode == "sync" else await chain.ainvoke(context())
    assert result.response.content == "Answer"
    assert "memory_source_complete" not in result.response.response_metadata
    sync_event.assert_not_called()
    async_event.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["sync", "async"])
async def test_rejected_runnable_response_preserves_exception_without_finalization(mode, mocker):
    event = mocker.patch.object(model_chain, "dispatch_custom_event")
    chain = make_chain(Mock(side_effect=ValueError("quality rejected")))
    with pytest.raises(ValueError, match="quality rejected"):
        if mode == "sync":
            chain.invoke(context())
        else:
            await chain.ainvoke(context())
    event.assert_not_called()
